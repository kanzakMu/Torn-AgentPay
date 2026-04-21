from __future__ import annotations

import threading
import time
from pathlib import Path

from fastapi import FastAPI

from seller import (
    PaymentRecoveryWorker,
    PaymentRecoveryWorkerConfig,
    TronSettlementConfirmation,
    TronSettlementExecution,
    TronSettlementService,
)
from seller.gateway import GatewayConfig, GatewayRuntime, install_gateway
from shared import MerchantRoute, PaymentRecord, SqlitePaymentStore


def test_payment_recovery_worker_lists_and_executes_unfinished_payments() -> None:
    class FakeSettlementService:
        def __init__(self) -> None:
            self.runtime = None

        def execute_payment(self, payment_id: str):
            raise AssertionError("not used in this test")

        def execute_pending(self):
            record = self.runtime.payment_store.get("pay_worker_1")
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "status_reason": "settlement submitted to chain",
                    "tx_id": "trx_worker_1",
                }
            )
            self.runtime.payment_store.upsert(updated)
            return [updated]

        def reconcile_submitted(self):
            record = self.runtime.payment_store.get("pay_worker_1")
            updated = record.model_copy(
                update={
                    "status": "settled",
                    "status_reason": "settlement confirmed on chain",
                    "confirmation_status": "confirmed",
                    "confirmed_at": int(time.time()),
                    "settled_at": int(time.time()),
                }
            )
            self.runtime.payment_store.upsert(updated)
            return [updated]

    app = FastAPI()
    settlement_service = FakeSettlementService()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            routes=[MerchantRoute(path="/tools/research", price_atomic=250_000)],
        ),
        settlement_service=settlement_service,
    )
    settlement_service.runtime = runtime
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_worker_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_worker_1",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=int(time.time()) + 300,
            status="authorized",
        )
    )
    worker = PaymentRecoveryWorker(runtime)

    summary = worker.run_once()

    assert summary["unfinished_count"] == 1
    assert summary["executed_count"] == 1
    assert summary["recovered_count"] == 0
    assert summary["reconciled_count"] == 1
    assert summary["logs"] == []
    assert runtime.get_payment("pay_worker_1").status == "settled"


def test_payment_recovery_worker_retries_retryable_failed_payments() -> None:
    class FakeSettlementService:
        def __init__(self) -> None:
            self.runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "status_reason": "settlement resubmitted to chain",
                    "tx_id": "trx_worker_retry_1",
                    "error_code": None,
                    "error_message": None,
                    "error_retryable": None,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            return []

        def reconcile_submitted(self):
            record = self.runtime.payment_store.get("pay_worker_retry_1")
            updated = record.model_copy(
                update={
                    "status": "settled",
                    "status_reason": "settlement confirmed on chain",
                    "confirmation_status": "confirmed",
                    "confirmed_at": int(time.time()),
                    "settled_at": int(time.time()),
                }
            )
            self.runtime.payment_store.upsert(updated)
            return [updated]

    app = FastAPI()
    settlement_service = FakeSettlementService()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            routes=[MerchantRoute(path="/tools/research", price_atomic=250_000)],
        ),
        settlement_service=settlement_service,
    )
    settlement_service.runtime = runtime
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_worker_retry_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_worker_retry_1",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=int(time.time()) + 300,
            status="failed",
            error_code="settlement_confirmation_failed",
            error_message="temporary confirmation outage",
            error_retryable=True,
            tx_id="trx_old_1",
        )
    )
    worker = PaymentRecoveryWorker(runtime)

    summary = worker.run_once()

    assert summary["unfinished_count"] == 1
    assert summary["executed_count"] == 0
    assert summary["recovered_count"] == 1
    assert summary["reconciled_count"] == 1
    assert summary["logs"] == []
    assert runtime.get_payment("pay_worker_retry_1").status == "settled"


def test_payment_recovery_worker_respects_retryable_failure_limit() -> None:
    class FakeSettlementService:
        def __init__(self) -> None:
            self.runtime = None
            self.execute_calls = 0

        def execute_payment(self, payment_id: str):
            self.execute_calls += 1
            raise AssertionError("retry-limited payment should not be executed again")

        def execute_pending(self):
            return []

        def reconcile_submitted(self):
            return []

    app = FastAPI()
    settlement_service = FakeSettlementService()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            routes=[MerchantRoute(path="/tools/research", price_atomic=250_000)],
        ),
        settlement_service=settlement_service,
    )
    settlement_service.runtime = runtime
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_worker_retry_limit",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_worker_retry_limit",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=int(time.time()) + 300,
            status="failed",
            error_code="settlement_confirmation_failed",
            error_message="temporary confirmation outage",
            error_retryable=True,
            confirmation_attempts=5,
        )
    )
    worker = PaymentRecoveryWorker(
        runtime,
        config=PaymentRecoveryWorkerConfig(max_retryable_failures=5),
    )

    summary = worker.run_once()

    assert summary["recovered_count"] == 0
    assert settlement_service.execute_calls == 0
    assert runtime.get_payment("pay_worker_retry_limit").status == "failed"


def test_payment_recovery_workers_do_not_double_execute_or_confirm_sqlite_records(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "payments.db"
    store_one = SqlitePaymentStore(sqlite_path)
    store_two = SqlitePaymentStore(sqlite_path)
    executor_calls = {"count": 0}
    confirmer_calls = {"count": 0}
    counter_lock = threading.Lock()

    class SharedExecutor:
        def execute(self, plan):
            with counter_lock:
                executor_calls["count"] += 1
            time.sleep(0.15)
            return TronSettlementExecution(
                tx_id="trx_sqlite_worker_1",
                channel_id=plan.channel_id,
                buyer_address=plan.buyer_address,
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                amount_atomic=plan.amount_atomic,
                voucher_nonce=plan.voucher_nonce,
                request_deadline=plan.request_deadline,
                request_digest="digest_sqlite_worker_1",
            )

    class SharedConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            with counter_lock:
                confirmer_calls["count"] += 1
            time.sleep(0.05)
            return TronSettlementConfirmation(
                tx_id=tx_id,
                status="confirmed",
                confirmed=True,
                block_timestamp=int(time.time()),
            )

    config = GatewayConfig(
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
        sqlite_path=str(sqlite_path),
        routes=[MerchantRoute(path="/tools/research", price_atomic=250_000)],
    )
    runtime_one = GatewayRuntime(
        config=config,
        payment_store=store_one,
        settlement_service=TronSettlementService(
            payment_store=store_one,
            executor=SharedExecutor(),
            confirmer=SharedConfirmer(),
            full_host="http://tron.local",
            seller_private_key="seller_pk",
            chain_id=31337,
        ),
    )
    runtime_two = GatewayRuntime(
        config=config,
        payment_store=store_two,
        settlement_service=TronSettlementService(
            payment_store=store_two,
            executor=SharedExecutor(),
            confirmer=SharedConfirmer(),
            full_host="http://tron.local",
            seller_private_key="seller_pk",
            chain_id=31337,
        ),
    )
    store_one.upsert(
        PaymentRecord(
            payment_id="pay_sqlite_worker_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_sqlite_worker_1",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=int(time.time()) + 300,
            status="authorized",
        )
    )

    worker_one = PaymentRecoveryWorker(runtime_one)
    worker_two = PaymentRecoveryWorker(runtime_two)
    summaries: list[dict[str, object]] = []

    def run_worker(worker: PaymentRecoveryWorker) -> None:
        summaries.append(worker.run_once())

    thread_one = threading.Thread(target=run_worker, args=(worker_one,))
    thread_two = threading.Thread(target=run_worker, args=(worker_two,))
    thread_one.start()
    thread_two.start()
    thread_one.join()
    thread_two.join()

    final_record = store_one.get("pay_sqlite_worker_1")

    assert len(summaries) == 2
    assert executor_calls["count"] == 1
    assert confirmer_calls["count"] == 1
    assert final_record is not None
    assert final_record.status == "settled"
    assert final_record.confirmation_status == "confirmed"


def test_payment_recovery_workers_handle_multi_record_sqlite_contention(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "payments.db"
    stores = [SqlitePaymentStore(sqlite_path) for _ in range(4)]
    executor_calls = {"count": 0}
    confirmer_calls = {"count": 0}
    counter_lock = threading.Lock()

    class SharedExecutor:
        def execute(self, plan):
            with counter_lock:
                executor_calls["count"] += 1
            time.sleep(0.03)
            return TronSettlementExecution(
                tx_id=f"trx_{plan.channel_id[-6:]}",
                channel_id=plan.channel_id,
                buyer_address=plan.buyer_address,
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                amount_atomic=plan.amount_atomic,
                voucher_nonce=plan.voucher_nonce,
                request_deadline=plan.request_deadline,
                request_digest="digest_multi_worker",
            )

    class SharedConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            with counter_lock:
                confirmer_calls["count"] += 1
            time.sleep(0.01)
            return TronSettlementConfirmation(
                tx_id=tx_id,
                status="confirmed",
                confirmed=True,
                block_timestamp=int(time.time()),
            )

    config = GatewayConfig(
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
        sqlite_path=str(sqlite_path),
        routes=[MerchantRoute(path="/tools/research", price_atomic=250_000)],
    )
    runtimes = [
        GatewayRuntime(
            config=config,
            payment_store=store,
            settlement_service=TronSettlementService(
                payment_store=store,
                executor=SharedExecutor(),
                confirmer=SharedConfirmer(),
                full_host="http://tron.local",
                seller_private_key="seller_pk",
                chain_id=31337,
            ),
        )
        for store in stores
    ]
    for index in range(6):
        stores[0].upsert(
            PaymentRecord(
                payment_id=f"pay_sqlite_batch_{index}",
                route_path="/tools/research",
                amount_atomic=250_000,
                chain="tron",
                buyer_address="TRX_BUYER",
                seller_address="TRX_SELLER",
                channel_id=f"channel_sqlite_batch_{index}",
                contract_address="TRX_CONTRACT",
                token_address="TRX_USDT",
                voucher_nonce=index + 1,
                expires_at=9_999_999_999,
                request_deadline=int(time.time()) + 300,
                status="authorized",
            )
        )

    workers = [PaymentRecoveryWorker(runtime) for runtime in runtimes]
    threads = [threading.Thread(target=worker.run_once) for worker in workers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    final_records = [stores[0].get(f"pay_sqlite_batch_{index}") for index in range(6)]

    assert executor_calls["count"] == 6
    assert confirmer_calls["count"] == 6
    assert all(record is not None and record.status == "settled" for record in final_records)

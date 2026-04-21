import os
from pathlib import Path
import time

import pytest

from seller import (
    TronSettlementConfirmation,
    TronSettlementExecution,
    TronSettlementService,
    build_default_tron_settlement_executor,
    build_default_tron_settlement_confirmer,
    build_local_smoke_tron_settlement_executor,
    build_local_smoke_tron_settlement_confirmer,
)
from shared import InMemoryPaymentStore, PaymentRecord


def _pending_payment(**overrides) -> PaymentRecord:
    payload = {
        "payment_id": "pay_123",
        "route_path": "/tools/research",
        "amount_atomic": 250_000,
        "chain": "tron",
        "buyer_address": "TRX_BUYER",
        "seller_address": "TRX_SELLER",
        "channel_id": "channel_123",
        "contract_address": "TRX_CONTRACT",
        "token_address": "TRX_USDT",
        "voucher_nonce": 7,
        "expires_at": 9_999_999_999,
        "request_deadline": int(time.time()) + 300,
        "request_method": "POST",
        "request_path": "/tools/research",
        "request_body": '{"topic":"tron"}',
        "status": "pending",
    }
    payload.update(overrides)
    return PaymentRecord(**payload)


def test_default_tron_settlement_executor_points_to_claim_script() -> None:
    executor = build_default_tron_settlement_executor(repository_root="e:/trade/aimicropay-tron")
    assert executor.command == ("node", "scripts/claim_payment_exec.js")
    assert executor.cwd.endswith("aimicropay-tron")


def test_default_tron_settlement_confirmer_points_to_confirm_script() -> None:
    confirmer = build_default_tron_settlement_confirmer(repository_root="e:/trade/aimicropay-tron")
    assert confirmer.command == ("node", "scripts/confirm_transaction_exec.js")
    assert confirmer.cwd.endswith("aimicropay-tron")


def test_local_smoke_tron_settlement_executor_points_to_smoke_script() -> None:
    executor = build_local_smoke_tron_settlement_executor(repository_root="e:/trade/aimicropay-tron")
    expected_npx = "npx.cmd" if os.name == "nt" else "npx"
    assert executor.command == (expected_npx, "hardhat", "run", "scripts/local_smoke_pipeline.js")
    assert executor.cwd.endswith("aimicropay-tron")


def test_local_smoke_tron_settlement_confirmer_uses_immediate_finality() -> None:
    confirmer = build_local_smoke_tron_settlement_confirmer(repository_root="e:/trade/aimicropay-tron")
    assert confirmer.immediate_finality is True


def test_settlement_service_executes_pending_payment() -> None:
    store = InMemoryPaymentStore()
    store.upsert(_pending_payment())
    store.upsert(_pending_payment(payment_id="pay_other", chain="sol", status="pending"))

    class FakeExecutor:
        def __init__(self) -> None:
            self.last_plan = None

        def execute(self, plan):
            self.last_plan = plan
            return TronSettlementExecution(
                tx_id="trx_claim_1",
                channel_id=plan.channel_id,
                buyer_address=plan.buyer_address,
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                amount_atomic=plan.amount_atomic,
                voucher_nonce=plan.voucher_nonce,
                request_deadline=plan.request_deadline,
                request_digest="digest_1",
            )

    class FakeConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            raise AssertionError("reconciliation is not part of execute_pending")

    executor = FakeExecutor()
    service = TronSettlementService(
        payment_store=store,
        executor=executor,
        confirmer=FakeConfirmer(),
        full_host="http://tron.local",
        seller_private_key="seller_pk",
        chain_id=728126428,
    )

    records = service.execute_pending()

    assert len(records) == 1
    assert records[0].payment_id == "pay_123"
    assert records[0].status == "submitted"
    assert records[0].tx_id == "trx_claim_1"
    assert executor.last_plan.request_path == "/tools/research"
    assert executor.last_plan.request_body == '{"topic":"tron"}'
    assert store.get("pay_other").status == "pending"


def test_settlement_service_marks_failed_when_execution_errors() -> None:
    store = InMemoryPaymentStore()
    store.upsert(_pending_payment(buyer_address=None))

    class FailingExecutor:
        def execute(self, plan):
            raise AssertionError("should not reach executor when plan is invalid")

    class FakeConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            raise AssertionError("not used")

    service = TronSettlementService(
        payment_store=store,
        executor=FailingExecutor(),
        confirmer=FakeConfirmer(),
        full_host="http://tron.local",
        seller_private_key="seller_pk",
        chain_id=728126428,
    )

    record = service.execute_payment("pay_123")

    assert record.status == "failed"
    assert record.error_code == "settlement_execution_failed"
    assert "buyer_address" in (record.error_message or "")


def test_local_smoke_settlement_executor_can_submit_payment() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    if not (repository_root / "node_modules" / "hardhat").exists():
        pytest.skip("local hardhat dependencies are not installed")

    store = InMemoryPaymentStore()
    store.upsert(
        _pending_payment(
            payment_id="pay_local_smoke",
            buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            channel_id="0xplaceholder",
            contract_address="0xplaceholder",
            token_address="0xplaceholder",
            voucher_nonce=1,
            request_deadline=int(time.time()) + 300,
            expires_at=9_999_999_999,
        )
    )
    service = TronSettlementService(
        payment_store=store,
        executor=build_local_smoke_tron_settlement_executor(repository_root=repository_root),
        confirmer=build_local_smoke_tron_settlement_confirmer(repository_root=repository_root),
        full_host="http://tron.local",
        seller_private_key="seller_pk",
        chain_id=31337,
    )

    record = service.execute_payment("pay_local_smoke")

    assert record.status == "submitted"
    assert record.tx_id is not None
    assert store.get("pay_local_smoke").status == "submitted"


def test_settlement_service_marks_failed_when_request_deadline_has_expired() -> None:
    store = InMemoryPaymentStore()
    store.upsert(_pending_payment(request_deadline=int(time.time()) - 1))

    class FakeExecutor:
        def execute(self, plan):
            raise AssertionError("expired request should fail before executor")

    class FakeConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            raise AssertionError("not used")

    service = TronSettlementService(
        payment_store=store,
        executor=FakeExecutor(),
        confirmer=FakeConfirmer(),
        full_host="http://tron.local",
        seller_private_key="seller_pk",
        chain_id=728126428,
    )

    record = service.execute_payment("pay_123")

    assert record.status == "expired"
    assert record.error_code == "request_deadline_expired"
    assert record.error_message == "request deadline expired before settlement execution"


def test_reconcile_payment_marks_submitted_payment_as_settled() -> None:
    store = InMemoryPaymentStore()
    store.upsert(_pending_payment(status="submitted", tx_id="trx_claim_1"))

    class FakeExecutor:
        def execute(self, plan):
            raise AssertionError("not used")

    class ConfirmingConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            return TronSettlementConfirmation(
                tx_id=tx_id,
                status="confirmed",
                confirmed=True,
                block_number=123,
                block_timestamp=int(time.time()),
            )

    service = TronSettlementService(
        payment_store=store,
        executor=FakeExecutor(),
        confirmer=ConfirmingConfirmer(),
        full_host="http://tron.local",
        seller_private_key="seller_pk",
        chain_id=728126428,
    )

    record = service.reconcile_payment("pay_123")

    assert record.status == "settled"
    assert record.confirmation_status == "confirmed"
    assert record.settled_at is not None
    assert store.get("pay_123").status == "settled"


def test_reconcile_payment_keeps_submitted_when_confirmation_is_pending() -> None:
    store = InMemoryPaymentStore()
    store.upsert(_pending_payment(status="submitted", tx_id="trx_claim_1"))

    class FakeExecutor:
        def execute(self, plan):
            raise AssertionError("not used")

    class PendingConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            return TronSettlementConfirmation(
                tx_id=tx_id,
                status="pending",
                confirmed=False,
            )

    service = TronSettlementService(
        payment_store=store,
        executor=FakeExecutor(),
        confirmer=PendingConfirmer(),
        full_host="http://tron.local",
        seller_private_key="seller_pk",
        chain_id=728126428,
    )

    record = service.reconcile_payment("pay_123")

    assert record.status == "submitted"
    assert record.confirmation_status == "pending"
    assert record.confirmation_attempts == 1


def test_reconcile_payment_keeps_submitted_when_confirmation_temporarily_errors() -> None:
    store = InMemoryPaymentStore()
    store.upsert(_pending_payment(status="submitted", tx_id="trx_claim_1"))

    class FakeExecutor:
        def execute(self, plan):
            raise AssertionError("not used")

    class ErroringConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            raise RuntimeError("temporary confirmer outage")

    service = TronSettlementService(
        payment_store=store,
        executor=FakeExecutor(),
        confirmer=ErroringConfirmer(),
        full_host="http://tron.local",
        seller_private_key="seller_pk",
        chain_id=728126428,
    )

    record = service.reconcile_payment("pay_123")

    assert record.status == "submitted"
    assert record.error_code == "settlement_confirmation_failed"
    assert record.error_retryable is True
    assert record.confirmation_status == "failed"


def test_reconcile_payment_marks_failed_after_retry_budget_exhausted() -> None:
    store = InMemoryPaymentStore()
    store.upsert(_pending_payment(status="submitted", tx_id="trx_claim_1", confirmation_attempts=1))

    class FakeExecutor:
        def execute(self, plan):
            raise AssertionError("not used")

    class ErroringConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            raise RuntimeError("temporary confirmer outage")

    service = TronSettlementService(
        payment_store=store,
        executor=FakeExecutor(),
        confirmer=ErroringConfirmer(),
        full_host="http://tron.local",
        seller_private_key="seller_pk",
        chain_id=728126428,
        max_confirmation_attempts=2,
    )

    record = service.reconcile_payment("pay_123")

    assert record.status == "failed"
    assert record.error_code == "settlement_confirmation_retry_exhausted"
    assert record.error_retryable is False

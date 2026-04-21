from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path

from seller import (
    GatewayConfig,
    GatewayRuntime,
    GatewaySettlementConfig,
    PaymentRecoveryWorker,
    PaymentRecoveryWorkerConfig,
    TronSettlementConfirmation,
    TronSettlementExecution,
    TronSettlementService,
)
from shared import PaymentRecord, SqlitePaymentStore


class DrillExecutor:
    def __init__(self, *, delay_s: float = 0.0, retryable_fail_stride: int = 0) -> None:
        self.delay_s = delay_s
        self.retryable_fail_stride = retryable_fail_stride
        self._attempts: dict[int, int] = {}
        self._lock = threading.Lock()

    def execute(self, plan) -> TronSettlementExecution:
        if self.delay_s:
            time.sleep(self.delay_s)
        nonce = int(plan.voucher_nonce)
        with self._lock:
            attempt = self._attempts.get(nonce, 0) + 1
            self._attempts[nonce] = attempt
        if self.retryable_fail_stride and nonce % self.retryable_fail_stride == 0 and attempt == 1:
            raise RuntimeError(f"temporary execute failure for nonce {nonce}")
        return TronSettlementExecution(
            tx_id=f"trx_{nonce}_{attempt}",
            channel_id=plan.channel_id,
            buyer_address=plan.buyer_address,
            seller_address=plan.seller_address,
            token_address=plan.token_address,
            amount_atomic=plan.amount_atomic,
            voucher_nonce=plan.voucher_nonce,
            request_deadline=plan.request_deadline,
            request_digest=plan.request_digest or f"digest_{nonce}",
        )


class DrillConfirmer:
    def __init__(
        self,
        *,
        delay_s: float = 0.0,
        pending_stride: int = 0,
        retryable_error_stride: int = 0,
        terminal_fail_stride: int = 0,
    ) -> None:
        self.delay_s = delay_s
        self.pending_stride = pending_stride
        self.retryable_error_stride = retryable_error_stride
        self.terminal_fail_stride = terminal_fail_stride
        self._attempts: dict[str, int] = {}
        self._lock = threading.Lock()

    def confirm(self, *, full_host: str, tx_id: str) -> TronSettlementConfirmation:
        if self.delay_s:
            time.sleep(self.delay_s)
        nonce = _nonce_from_tx_id(tx_id)
        with self._lock:
            attempt = self._attempts.get(tx_id, 0) + 1
            self._attempts[tx_id] = attempt
        if self.terminal_fail_stride and nonce % self.terminal_fail_stride == 0:
            return TronSettlementConfirmation(
                tx_id=tx_id,
                status="failed",
                confirmed=False,
                error_message=f"terminal confirmation failure for nonce {nonce}",
            )
        if self.retryable_error_stride and nonce % self.retryable_error_stride == 0 and attempt == 1:
            raise RuntimeError(f"temporary confirmer outage for nonce {nonce}")
        if self.pending_stride and nonce % self.pending_stride == 0 and attempt == 1:
            return TronSettlementConfirmation(
                tx_id=tx_id,
                status="pending",
                confirmed=False,
            )
        now = int(time.time())
        return TronSettlementConfirmation(
            tx_id=tx_id,
            status="confirmed",
            confirmed=True,
            block_number=10_000 + nonce,
            block_timestamp=now,
        )


def build_stress_drill_runtime(
    *,
    sqlite_path: str | Path,
    execute_delay_s: float = 0.0,
    confirm_delay_s: float = 0.0,
    execute_retryable_fail_stride: int = 7,
    confirm_pending_stride: int = 5,
    confirm_retryable_error_stride: int = 11,
    confirm_terminal_fail_stride: int = 6,
    processing_lock_ttl_s: int = 60,
    max_confirmation_attempts: int = 4,
) -> GatewayRuntime:
    payment_store = SqlitePaymentStore(sqlite_path)
    settlement_service = TronSettlementService(
        payment_store=payment_store,
        executor=DrillExecutor(
            delay_s=execute_delay_s,
            retryable_fail_stride=execute_retryable_fail_stride,
        ),
        confirmer=DrillConfirmer(
            delay_s=confirm_delay_s,
            pending_stride=confirm_pending_stride,
            retryable_error_stride=confirm_retryable_error_stride,
            terminal_fail_stride=confirm_terminal_fail_stride,
        ),
        full_host="http://127.0.0.1:9090",
        seller_private_key="seller_private_key",
        chain_id=31337,
        processing_lock_ttl_s=processing_lock_ttl_s,
        max_confirmation_attempts=max_confirmation_attempts,
    )
    return GatewayRuntime(
        GatewayConfig(
            service_name="Stress Drill Merchant",
            service_description="Synthetic off-chain drill runtime",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            chain_id=31337,
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://127.0.0.1:9090",
                seller_private_key="seller_private_key",
                chain_id=31337,
                executor_backend="local_smoke",
                processing_lock_ttl_s=processing_lock_ttl_s,
                max_confirmation_attempts=max_confirmation_attempts,
            ),
            sqlite_path=str(sqlite_path),
        ),
        payment_store=payment_store,
        settlement_service=settlement_service,
    )


def seed_drill_payments(runtime: GatewayRuntime, *, payment_count: int) -> list[PaymentRecord]:
    seeded: list[PaymentRecord] = []
    deadline = int(time.time()) + 600
    for index in range(1, payment_count + 1):
        record = PaymentRecord(
            payment_id=f"pay_drill_{index}",
            idempotency_key=f"idem_drill_{index}",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address=f"TRX_BUYER_{index}",
            seller_address="TRX_SELLER",
            channel_id=f"channel_drill_{index}",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=index,
            expires_at=deadline + 3_600,
            request_deadline=deadline,
            request_method="POST",
            request_path="/tools/research",
            request_body=json.dumps({"query": f"stress-{index}"}),
            request_digest=f"digest_drill_{index}",
            buyer_signature=f"sig_drill_{index}",
            status="authorized",
        )
        seeded.append(runtime.record_payment(record))
    return seeded


def run_offchain_stress_drill(
    *,
    payment_count: int = 30,
    worker_count: int = 4,
    max_rounds: int = 5,
    sqlite_path: str | Path | None = None,
) -> dict[str, object]:
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if sqlite_path is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="aimipay-drill-")
        sqlite_path = Path(temp_dir.name) / "payments.db"
    runtime = build_stress_drill_runtime(sqlite_path=sqlite_path)
    seed_drill_payments(runtime, payment_count=payment_count)
    workers = [
        PaymentRecoveryWorker(
            runtime,
            config=PaymentRecoveryWorkerConfig(max_retryable_failures=6),
        )
        for _ in range(worker_count)
    ]

    rounds: list[dict[str, object]] = []
    try:
        for round_number in range(1, max_rounds + 1):
            batch: list[dict[str, object]] = []
            threads: list[threading.Thread] = []
            for worker in workers:
                thread = threading.Thread(target=lambda w=worker: batch.append(w.run_once()))
                thread.start()
                threads.append(thread)
            for thread in threads:
                thread.join()
            round_summary = _summarize_round(runtime=runtime, round_number=round_number, worker_runs=batch)
            rounds.append(round_summary)
            if round_summary["unfinished_count"] == 0:
                break

        records = runtime.recover_payments()
        final_status_counts = _status_counts(records)
        metrics = runtime.metrics.snapshot()
        return {
            "storage_backend": "sqlite",
            "sqlite_path": str(sqlite_path),
            "payment_count": payment_count,
            "worker_count": worker_count,
            "rounds": rounds,
            "final_status_counts": final_status_counts,
            "unfinished_count": sum(
                count for status, count in final_status_counts.items() if status in {"pending", "authorized", "submitted"}
            ),
            "metrics": metrics,
        }
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def format_drill_summary(summary: dict[str, object]) -> str:
    lines = [
        "AimiPay Off-Chain Stress Drill",
        f"storage backend: {summary['storage_backend']}",
        f"workers: {summary['worker_count']}",
        f"payments: {summary['payment_count']}",
        f"unfinished after drill: {summary['unfinished_count']}",
        f"final status counts: {summary['final_status_counts']}",
    ]
    rounds = summary.get("rounds", [])
    if rounds:
        lines.append(f"rounds executed: {len(rounds)}")
    return "\n".join(lines)


def _summarize_round(
    *,
    runtime: GatewayRuntime,
    round_number: int,
    worker_runs: list[dict[str, object]],
) -> dict[str, object]:
    records = runtime.recover_payments()
    status_counts = _status_counts(records)
    unfinished_count = sum(
        count for status, count in status_counts.items() if status in {"pending", "authorized", "submitted"}
    )
    return {
        "round": round_number,
        "worker_runs": len(worker_runs),
        "unfinished_count": unfinished_count,
        "status_counts": status_counts,
    }


def _status_counts(records: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        status = str(getattr(record, "status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _nonce_from_tx_id(tx_id: str) -> int:
    parts = tx_id.split("_")
    if len(parts) < 2:
        return 0
    return int(parts[1])


if __name__ == "__main__":
    summary = run_offchain_stress_drill()
    print(format_drill_summary(summary))

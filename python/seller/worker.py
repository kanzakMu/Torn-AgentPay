from __future__ import annotations

from dataclasses import dataclass, field

from shared import coerce_error, error_payload

from .observability import RuntimeMetrics, StructuredEventLogger


@dataclass(slots=True)
class PaymentRecoveryWorkerConfig:
    max_retryable_failures: int = 5
    include_retryable_failed: bool = True


@dataclass(slots=True)
class PaymentRecoveryWorker:
    gateway: object
    config: PaymentRecoveryWorkerConfig = field(default_factory=PaymentRecoveryWorkerConfig)
    metrics: RuntimeMetrics | None = None
    event_logger: StructuredEventLogger | None = None

    def __post_init__(self) -> None:
        if self.metrics is None and hasattr(self.gateway, "metrics"):
            self.metrics = self.gateway.metrics
        if self.event_logger is None and hasattr(self.gateway, "event_logger"):
            self.event_logger = self.gateway.event_logger

    def list_unfinished_payments(self) -> list[object]:
        statuses = ["pending", "authorized", "submitted"]
        if self.config.include_retryable_failed:
            statuses.append("failed")
        records = self.gateway.recover_payments(statuses=statuses)
        return [
            record
            for record in records
            if getattr(record, "status", None) != "failed"
            or (
                bool(getattr(record, "error_retryable", False))
                and int(getattr(record, "confirmation_attempts", 0)) < self.config.max_retryable_failures
            )
        ]

    def recover(
        self,
        *,
        payment_id: str | None = None,
        idempotency_key: str | None = None,
        channel_id: str | None = None,
        statuses: list[str] | None = None,
    ) -> list[object]:
        return list(
            self.gateway.recover_payments(
                payment_id=payment_id,
                idempotency_key=idempotency_key,
                channel_id=channel_id,
                statuses=statuses,
            )
        )

    def retry_failed_payments(self) -> list[object]:
        recovered: list[object] = []
        if not self.config.include_retryable_failed:
            return recovered
        for record in self.recover(statuses=["failed"]):
            if not bool(getattr(record, "error_retryable", False)):
                continue
            if int(getattr(record, "confirmation_attempts", 0)) >= self.config.max_retryable_failures:
                self._metric("worker_retry_skipped_total")
                self._event(
                    "worker_retry_skipped",
                    payment_id=getattr(record, "payment_id", None),
                    attempts=int(getattr(record, "confirmation_attempts", 0)),
                )
                continue
            payments = self.gateway.execute_settlements(payment_id=record.payment_id)
            recovered.extend(payments)
        return recovered

    def run_once(self) -> dict[str, object]:
        self._metric("worker_runs_total")
        unfinished = self.list_unfinished_payments()
        logs: list[dict] = []
        try:
            executed = self.gateway.execute_settlements()
        except Exception as exc:
            executed = []
            self._metric("worker_errors_total")
            logs.append(error_payload(coerce_error(exc, default_code="settlement_execution_failed")))
        try:
            recovered = self.retry_failed_payments()
        except Exception as exc:
            recovered = []
            self._metric("worker_errors_total")
            logs.append(error_payload(coerce_error(exc, default_code="settlement_execution_failed")))
        try:
            reconciled = self.gateway.reconcile_settlements()
        except Exception as exc:
            reconciled = []
            self._metric("worker_errors_total")
            logs.append(error_payload(coerce_error(exc, default_code="settlement_confirmation_failed")))
        self._metric("worker_executed_total", len(executed))
        self._metric("worker_recovered_total", len(recovered))
        self._metric("worker_reconciled_total", len(reconciled))
        self._metric("worker_unfinished_total", len(unfinished))
        self._event(
            "worker_run_completed",
            unfinished_count=len(unfinished),
            executed_count=len(executed),
            recovered_count=len(recovered),
            reconciled_count=len(reconciled),
            error_count=len(logs),
        )
        return {
            "unfinished_count": len(unfinished),
            "executed_count": len(executed),
            "recovered_count": len(recovered),
            "reconciled_count": len(reconciled),
            "logs": logs,
        }

    def _metric(self, key: str, amount: int = 1) -> None:
        if self.metrics is not None:
            self.metrics.incr(key, amount)

    def _event(self, event: str, **payload: object) -> None:
        if self.event_logger is not None:
            self.event_logger.emit(event, **payload)

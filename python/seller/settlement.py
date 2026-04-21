from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from shared import InMemoryPaymentStore, PaymentRecord, aimipay_error

from .observability import RuntimeMetrics, StructuredEventLogger


SettlementExecutorBackend = Literal["claim_script", "local_smoke"]


@dataclass(slots=True)
class TronSettlementPlan:
    full_host: str
    seller_private_key: str
    chain_id: int
    contract_address: str
    channel_id: str
    buyer_address: str
    seller_address: str
    token_address: str
    amount_atomic: int
    voucher_nonce: int
    expires_at: int
    request_deadline: int
    request_method: str = "POST"
    request_path: str = "/"
    request_body: str = ""
    request_digest: str | None = None
    buyer_signature: str | None = None

    def to_dict(self) -> dict:
        payload = {
            "full_host": self.full_host,
            "seller_private_key": self.seller_private_key,
            "chain_id": self.chain_id,
            "contract_address": self.contract_address,
            "channel_id": self.channel_id,
            "buyer_address": self.buyer_address,
            "seller_address": self.seller_address,
            "token_address": self.token_address,
            "amount_atomic": self.amount_atomic,
            "voucher_nonce": self.voucher_nonce,
            "expires_at": self.expires_at,
            "request_deadline": self.request_deadline,
            "method": self.request_method,
            "path": self.request_path,
            "body": self.request_body,
        }
        if self.request_digest:
            payload["request_digest"] = self.request_digest
        if self.buyer_signature:
            payload["signature"] = self.buyer_signature
        return payload


@dataclass(slots=True)
class TronSettlementExecution:
    tx_id: str
    channel_id: str
    buyer_address: str
    seller_address: str
    token_address: str
    amount_atomic: int
    voucher_nonce: int
    request_deadline: int
    request_digest: str


@dataclass(slots=True)
class TronSettlementConfirmation:
    tx_id: str
    status: Literal["pending", "confirmed", "failed"]
    confirmed: bool
    block_number: int | None = None
    block_timestamp: int | None = None
    error_message: str | None = None


@dataclass(slots=True)
class TronSettlementExecutor:
    command: tuple[str, ...]
    cwd: str
    extra_env: dict[str, str] | None = None

    def execute(self, plan: TronSettlementPlan) -> TronSettlementExecution:
        with tempfile.TemporaryDirectory(prefix="aimipay-tron-claim-") as temp_dir:
            plan_file = Path(temp_dir) / "claim_payment_plan.json"
            plan_file.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            env = os.environ.copy()
            env["AIMICROPAY_PLAN_FILE"] = str(plan_file)
            if self.extra_env:
                env.update(self.extra_env)
            completed = subprocess.run(
                [*self.command],
                cwd=self.cwd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
        payload = _parse_json_output(completed.stdout)
        return TronSettlementExecution(
            tx_id=str(payload["tx_id"]),
            channel_id=str(payload["channel_id"]),
            buyer_address=str(payload["buyer_address"]),
            seller_address=str(payload["seller_address"]),
            token_address=str(payload["token_address"]),
            amount_atomic=int(payload["amount_atomic"]),
            voucher_nonce=int(payload["voucher_nonce"]),
            request_deadline=int(payload["request_deadline"]),
            request_digest=str(payload["request_digest"]),
        )


@dataclass(slots=True)
class TronSettlementConfirmer:
    command: tuple[str, ...]
    cwd: str
    extra_env: dict[str, str] | None = None
    immediate_finality: bool = False

    def confirm(self, *, full_host: str, tx_id: str) -> TronSettlementConfirmation:
        if self.immediate_finality:
            return TronSettlementConfirmation(tx_id=tx_id, status="confirmed", confirmed=True)
        with tempfile.TemporaryDirectory(prefix="aimipay-tron-confirm-") as temp_dir:
            plan_file = Path(temp_dir) / "confirm_transaction_plan.json"
            plan_file.write_text(
                json.dumps({"full_host": full_host, "tx_id": tx_id}),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["AIMICROPAY_PLAN_FILE"] = str(plan_file)
            if self.extra_env:
                env.update(self.extra_env)
            completed = subprocess.run(
                [*self.command],
                cwd=self.cwd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
        payload = _parse_json_output(completed.stdout)
        return TronSettlementConfirmation(
            tx_id=str(payload["tx_id"]),
            status=str(payload["status"]),
            confirmed=bool(payload["confirmed"]),
            block_number=None if payload.get("block_number") is None else int(payload["block_number"]),
            block_timestamp=None if payload.get("block_timestamp") is None else int(payload["block_timestamp"]),
            error_message=None if payload.get("error_message") is None else str(payload["error_message"]),
        )


@dataclass(slots=True)
class TronSettlementServiceConfig:
    repository_root: str
    full_host: str
    seller_private_key: str
    chain_id: int
    executor_backend: SettlementExecutorBackend = "claim_script"
    extra_env: dict[str, str] | None = None
    processing_lock_ttl_s: int = 300
    max_confirmation_attempts: int = 10


@dataclass(slots=True)
class TronSettlementService:
    payment_store: InMemoryPaymentStore
    executor: TronSettlementExecutor
    confirmer: TronSettlementConfirmer
    full_host: str
    seller_private_key: str
    chain_id: int
    chain: str = "tron"
    processing_lock_ttl_s: int = 300
    max_confirmation_attempts: int = 10
    metrics: RuntimeMetrics | None = None
    event_logger: StructuredEventLogger | None = None

    def pending_payments(self) -> list[PaymentRecord]:
        pending = self.payment_store.list(status="pending", chain=self.chain)
        authorized = self.payment_store.list(status="authorized", chain=self.chain)
        return [*pending, *authorized]

    def submitted_payments(self) -> list[PaymentRecord]:
        return self.payment_store.list(status="submitted", chain=self.chain)

    def build_plan(self, record: PaymentRecord) -> TronSettlementPlan:
        if record.chain != self.chain:
            raise aimipay_error(
                "unsupported_chain",
                message=f"unsupported chain for settlement: {record.chain}",
                details={"chain": record.chain, "supported_chain": self.chain},
            )

        missing: list[str] = []
        required_fields = {
            "buyer_address": record.buyer_address,
            "seller_address": record.seller_address,
            "channel_id": record.channel_id,
            "contract_address": record.contract_address,
            "token_address": record.token_address,
            "voucher_nonce": record.voucher_nonce,
            "expires_at": record.expires_at,
            "request_deadline": record.request_deadline,
        }
        for field_name, value in required_fields.items():
            if value is None or value == "":
                missing.append(field_name)
        if missing:
            raise aimipay_error(
                "missing_settlement_fields",
                message=f"payment record missing settlement fields: {', '.join(missing)}",
                details={"missing_fields": missing},
            )

        return TronSettlementPlan(
            full_host=self.full_host,
            seller_private_key=self.seller_private_key,
            chain_id=self.chain_id,
            contract_address=str(record.contract_address),
            channel_id=str(record.channel_id),
            buyer_address=str(record.buyer_address),
            seller_address=str(record.seller_address),
            token_address=str(record.token_address),
            amount_atomic=int(record.amount_atomic),
            voucher_nonce=int(record.voucher_nonce),
            expires_at=int(record.expires_at),
            request_deadline=int(record.request_deadline),
            request_method=record.request_method or "POST",
            request_path=record.request_path or record.route_path or "/",
            request_body=record.request_body or "",
            request_digest=record.request_digest,
            buyer_signature=record.buyer_signature,
        )

    def execute_payment(self, payment_id: str) -> PaymentRecord:
        record = self.payment_store.get(payment_id)
        if record is None:
            raise aimipay_error("payment_not_found", details={"payment_id": payment_id}, status_code=404)
        if record.status not in {"pending", "authorized", "failed"}:
            return record
        if record.status == "failed" and not record.error_retryable:
            return record
        token = f"execution:{uuid.uuid4().hex}"
        if hasattr(self.payment_store, "acquire_processing_lock"):
            locked = self.payment_store.acquire_processing_lock(
                payment_id,
                stage="execution",
                token=token,
                ttl_s=self.processing_lock_ttl_s,
            )
            if locked is None:
                current = self.payment_store.get(payment_id)
                if current is None:
                    raise aimipay_error("payment_not_found", details={"payment_id": payment_id}, status_code=404)
                self._metric("settlement_execution_lock_skipped_total")
                return current
            record = locked
        return self._execute_record(record)

    def execute_pending(self) -> list[PaymentRecord]:
        if hasattr(self.payment_store, "claim_for_processing"):
            token = f"execution-batch:{uuid.uuid4().hex}"
            records = self.payment_store.claim_for_processing(
                statuses=["pending", "authorized"],
                stage="execution",
                token=token,
                ttl_s=self.processing_lock_ttl_s,
                chain=self.chain,
            )
            return [self._execute_record(record) for record in records]
        return [self.execute_payment(record.payment_id) for record in self.pending_payments()]

    def reconcile_payment(self, payment_id: str) -> PaymentRecord:
        record = self.payment_store.get(payment_id)
        if record is None:
            raise aimipay_error("payment_not_found", details={"payment_id": payment_id}, status_code=404)
        if record.status != "submitted":
            return record
        token = f"confirmation:{uuid.uuid4().hex}"
        if hasattr(self.payment_store, "acquire_processing_lock"):
            locked = self.payment_store.acquire_processing_lock(
                payment_id,
                stage="confirmation",
                token=token,
                ttl_s=self.processing_lock_ttl_s,
            )
            if locked is None:
                current = self.payment_store.get(payment_id)
                if current is None:
                    raise aimipay_error("payment_not_found", details={"payment_id": payment_id}, status_code=404)
                self._metric("settlement_confirmation_lock_skipped_total")
                return current
            record = locked
        return self._reconcile_record(record)

    def reconcile_submitted(self) -> list[PaymentRecord]:
        if hasattr(self.payment_store, "claim_for_processing"):
            token = f"confirmation-batch:{uuid.uuid4().hex}"
            records = self.payment_store.claim_for_processing(
                statuses=["submitted"],
                stage="confirmation",
                token=token,
                ttl_s=self.processing_lock_ttl_s,
                chain=self.chain,
            )
            return [self._reconcile_record(record) for record in records]
        return [self.reconcile_payment(record.payment_id) for record in self.submitted_payments()]

    def _execute_record(self, record: PaymentRecord) -> PaymentRecord:
        try:
            plan = self.build_plan(record)
            if plan.request_deadline < int(time.time()):
                expired_record = record.model_copy(
                    update={
                        "status": "expired",
                        "status_reason": "request deadline expired before settlement execution",
                        "error_code": "request_deadline_expired",
                        "error_message": "request deadline expired before settlement execution",
                        "error_retryable": False,
                        "processing_stage": None,
                        "processing_token": None,
                        "processing_started_at": None,
                    }
                )
                self._metric("settlement_expired_total")
                self._event("settlement_execute_expired", payment_id=record.payment_id)
                return self.payment_store.upsert(expired_record)
            execution = self.executor.execute(plan)
        except Exception as exc:
            failed_record = record.model_copy(
                update={
                    "status": "failed",
                    "error_code": "settlement_execution_failed",
                    "error_message": str(exc),
                    "error_retryable": True,
                    "processing_stage": None,
                    "processing_token": None,
                    "processing_started_at": None,
                }
            )
            self._metric("settlement_execution_failed_total")
            self._event("settlement_execute_failed", payment_id=record.payment_id, error=str(exc))
            return self.payment_store.upsert(failed_record)

        submitted_record = record.model_copy(
            update={
                "status": "submitted",
                "status_reason": "settlement submitted to chain",
                "tx_id": execution.tx_id,
                "error_code": None,
                "error_message": None,
                "error_retryable": None,
                "processing_stage": None,
                "processing_token": None,
                "processing_started_at": None,
            }
        )
        self._metric("settlement_executed_total")
        self._event("settlement_execute_submitted", payment_id=record.payment_id, tx_id=execution.tx_id)
        return self.payment_store.upsert(submitted_record)

    def _reconcile_record(self, record: PaymentRecord) -> PaymentRecord:
        if record.status != "submitted":
            return record
        if not record.tx_id:
            failed_record = record.model_copy(
                update={
                    "status": "failed",
                    "status_reason": "submitted payment is missing transaction id",
                    "error_code": "settlement_tx_missing",
                    "error_message": "submitted payment is missing transaction id",
                    "error_retryable": False,
                    "confirmation_status": "failed",
                    "confirmation_error": "submitted payment is missing transaction id",
                    "confirmation_attempts": record.confirmation_attempts + 1,
                    "processing_stage": None,
                    "processing_token": None,
                    "processing_started_at": None,
                }
            )
            self._metric("settlement_confirmation_failed_total")
            self._event("settlement_confirm_missing_tx", payment_id=record.payment_id)
            return self.payment_store.upsert(failed_record)
        try:
            confirmation = self.confirmer.confirm(full_host=self.full_host, tx_id=record.tx_id)
        except Exception as exc:
            attempts = record.confirmation_attempts + 1
            if attempts >= self.max_confirmation_attempts:
                terminal_record = record.model_copy(
                    update={
                        "status": "failed",
                        "status_reason": "settlement confirmation retry limit reached",
                        "error_code": "settlement_confirmation_retry_exhausted",
                        "error_message": str(exc),
                        "error_retryable": False,
                        "confirmation_status": "failed",
                        "confirmation_error": str(exc),
                        "confirmation_attempts": attempts,
                        "processing_stage": None,
                        "processing_token": None,
                        "processing_started_at": None,
                    }
                )
                self._metric("settlement_confirmation_retry_exhausted_total")
                self._event(
                    "settlement_confirm_retry_exhausted",
                    payment_id=record.payment_id,
                    attempts=attempts,
                    error=str(exc),
                )
                return self.payment_store.upsert(terminal_record)
            retryable_record = record.model_copy(
                update={
                    "status": "submitted",
                    "status_reason": "settlement confirmation temporarily unavailable",
                    "error_code": "settlement_confirmation_failed",
                    "error_message": str(exc),
                    "error_retryable": True,
                    "confirmation_status": "failed",
                    "confirmation_error": str(exc),
                    "confirmation_attempts": attempts,
                    "processing_stage": None,
                    "processing_token": None,
                    "processing_started_at": None,
                }
            )
            self._metric("settlement_confirmation_failed_total")
            self._event(
                "settlement_confirm_retryable_failure",
                payment_id=record.payment_id,
                attempts=attempts,
                error=str(exc),
            )
            return self.payment_store.upsert(retryable_record)

        attempts = record.confirmation_attempts + 1
        if confirmation.status == "confirmed":
            settled_at = confirmation.block_timestamp or int(time.time())
            settled_record = record.model_copy(
                update={
                    "status": "settled",
                    "status_reason": "settlement confirmed on chain",
                    "error_code": None,
                    "error_message": None,
                    "error_retryable": None,
                    "confirmation_status": "confirmed",
                    "confirmation_error": None,
                    "confirmation_attempts": attempts,
                    "settled_at": settled_at,
                    "confirmed_at": settled_at,
                    "processing_stage": None,
                    "processing_token": None,
                    "processing_started_at": None,
                }
            )
            self._metric("settlement_confirmed_total")
            self._event("settlement_confirmed", payment_id=record.payment_id, tx_id=record.tx_id)
            return self.payment_store.upsert(settled_record)
        if confirmation.status == "failed":
            failed_record = record.model_copy(
                update={
                    "status": "failed",
                    "status_reason": "settlement transaction failed on chain",
                    "error_code": "settlement_transaction_reverted",
                    "error_message": confirmation.error_message or "settlement transaction failed on chain",
                    "error_retryable": False,
                    "confirmation_status": "failed",
                    "confirmation_error": confirmation.error_message,
                    "confirmation_attempts": attempts,
                    "processing_stage": None,
                    "processing_token": None,
                    "processing_started_at": None,
                }
            )
            self._metric("settlement_reverted_total")
            self._event("settlement_reverted", payment_id=record.payment_id, tx_id=record.tx_id)
            return self.payment_store.upsert(failed_record)

        pending_record = record.model_copy(
            update={
                "confirmation_status": "pending",
                "confirmation_error": confirmation.error_message,
                "confirmation_attempts": attempts,
                "processing_stage": None,
                "processing_token": None,
                "processing_started_at": None,
            }
        )
        self._metric("settlement_confirmation_pending_total")
        self._event(
            "settlement_confirmation_pending",
            payment_id=record.payment_id,
            tx_id=record.tx_id,
            attempts=attempts,
        )
        return self.payment_store.upsert(pending_record)

    def _metric(self, key: str, amount: int = 1) -> None:
        if self.metrics is not None:
            self.metrics.incr(key, amount)

    def _event(self, event: str, **payload: object) -> None:
        if self.event_logger is not None:
            self.event_logger.emit(event, **payload)


def build_default_tron_settlement_executor(
    *,
    repository_root: str | os.PathLike[str],
    extra_env: dict[str, str] | None = None,
) -> TronSettlementExecutor:
    repo = Path(repository_root)
    return TronSettlementExecutor(
        command=("node", "scripts/claim_payment_exec.js"),
        cwd=str(repo),
        extra_env=extra_env,
    )


def build_default_tron_settlement_confirmer(
    *,
    repository_root: str | os.PathLike[str],
    extra_env: dict[str, str] | None = None,
) -> TronSettlementConfirmer:
    repo = Path(repository_root)
    return TronSettlementConfirmer(
        command=("node", "scripts/confirm_transaction_exec.js"),
        cwd=str(repo),
        extra_env=extra_env,
    )


def build_local_smoke_tron_settlement_confirmer(
    *,
    repository_root: str | os.PathLike[str],
    extra_env: dict[str, str] | None = None,
) -> TronSettlementConfirmer:
    repo = Path(repository_root)
    return TronSettlementConfirmer(
        command=("node", "scripts/confirm_transaction_exec.js"),
        cwd=str(repo),
        extra_env=extra_env,
        immediate_finality=True,
    )


def build_local_smoke_tron_settlement_executor(
    *,
    repository_root: str | os.PathLike[str],
    extra_env: dict[str, str] | None = None,
) -> TronSettlementExecutor:
    repo = Path(repository_root)
    npx_command = "npx.cmd" if os.name == "nt" else "npx"
    return TronSettlementExecutor(
        command=(npx_command, "hardhat", "run", "scripts/local_smoke_pipeline.js"),
        cwd=str(repo),
        extra_env=extra_env,
    )


def build_default_tron_settlement_service(
    *,
    payment_store: InMemoryPaymentStore,
    config: TronSettlementServiceConfig,
) -> TronSettlementService:
    if config.executor_backend == "local_smoke":
        executor = build_local_smoke_tron_settlement_executor(
            repository_root=config.repository_root,
            extra_env=config.extra_env,
        )
        confirmer = build_local_smoke_tron_settlement_confirmer(
            repository_root=config.repository_root,
            extra_env=config.extra_env,
        )
    else:
        executor = build_default_tron_settlement_executor(
            repository_root=config.repository_root,
            extra_env=config.extra_env,
        )
        confirmer = build_default_tron_settlement_confirmer(
            repository_root=config.repository_root,
            extra_env=config.extra_env,
        )
    return TronSettlementService(
        payment_store=payment_store,
        executor=executor,
        confirmer=confirmer,
        full_host=config.full_host,
        seller_private_key=config.seller_private_key,
        chain_id=config.chain_id,
        processing_lock_ttl_s=config.processing_lock_ttl_s,
        max_confirmation_attempts=config.max_confirmation_attempts,
    )


def _parse_json_output(stdout: str) -> dict:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("settlement executor returned no output")
    return json.loads(lines[-1])

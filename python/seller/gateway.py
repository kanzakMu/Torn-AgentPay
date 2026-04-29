from __future__ import annotations

import time
from dataclasses import dataclass, field
import secrets
import hashlib
import hmac
import json

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response, status
from .settlement import TronSettlementServiceConfig, build_default_tron_settlement_service
from .observability import RuntimeMetrics, StructuredEventLogger, build_runtime_summary, validate_runtime_config

from shared import (
    AimiPayError,
    ChainInfo,
    CreatePaymentIntentRequest,
    CreatePaymentRequest,
    InMemoryPaymentStore,
    MerchantPlan,
    MerchantRoute,
    OpenChannelRequest,
    OpenChannelResponse,
    OperatorPaymentActionRequest,
    PaymentRecord,
    SqlitePaymentStore,
    SettlementExecuteRequest,
    aimipay_error,
    build_payment_lifecycle,
    build_manifest,
    build_protocol_reference,
    error_payload,
    make_channel_id,
    make_payment_id,
)


@dataclass(slots=True)
class GatewaySettlementConfig:
    repository_root: str
    full_host: str
    seller_private_key: str
    chain_id: int
    executor_backend: str = "claim_script"
    extra_env: dict[str, str] | None = None
    processing_lock_ttl_s: int = 300
    max_confirmation_attempts: int = 10

    def tron_service_config(self) -> TronSettlementServiceConfig:
        return TronSettlementServiceConfig(
            repository_root=self.repository_root,
            full_host=self.full_host,
            seller_private_key=self.seller_private_key,
            chain_id=self.chain_id,
            executor_backend=self.executor_backend,
            extra_env=self.extra_env,
            processing_lock_ttl_s=self.processing_lock_ttl_s,
            max_confirmation_attempts=self.max_confirmation_attempts,
        )


@dataclass(slots=True)
class GatewayConfig:
    service_name: str
    service_description: str
    seller_address: str
    contract_address: str
    token_address: str
    network: str = "nile"
    asset_symbol: str = "USDT"
    asset_decimals: int = 6
    chain_id: int | None = None
    default_deposit_atomic: int = 1_000_000
    default_channel_ttl_s: int = 3600
    admin_token: str | None = None
    admin_token_sha256: str | None = None
    admin_read_token: str | None = None
    admin_read_token_sha256: str | None = None
    audit_log_path: str | None = None
    webhook_urls: list[str] = field(default_factory=list)
    webhook_secret: str | None = None
    routes: list[MerchantRoute] = field(default_factory=list)
    plans: list[MerchantPlan] = field(default_factory=list)
    management_prefix: str = "/_aimipay"
    settlement: GatewaySettlementConfig | None = None
    sqlite_path: str | None = None

    def primary_chain(self) -> ChainInfo:
        effective_chain_id = self.chain_id
        if effective_chain_id is None and self.settlement is not None:
            effective_chain_id = self.settlement.chain_id
        settlement_backend = None if self.settlement is None else self.settlement.executor_backend
        return ChainInfo(
            chain_id=effective_chain_id,
            settlement_backend=settlement_backend,
            seller_address=self.seller_address,
            contract_address=self.contract_address,
            asset_address=self.token_address,
            asset_symbol=self.asset_symbol,
            asset_decimals=self.asset_decimals,
            network=self.network,
        )


class GatewayRuntime:
    def __init__(
        self,
        config: GatewayConfig,
        payment_store: InMemoryPaymentStore | SqlitePaymentStore | None = None,
        settlement_service: object | None = None,
    ) -> None:
        self.config = config
        self.payment_store = payment_store or InMemoryPaymentStore()
        self.settlement_service = settlement_service
        self.metrics = RuntimeMetrics()
        self.event_logger = StructuredEventLogger(audit_log_path=config.audit_log_path)
        self.webhook_outbox: list[dict] = []
        if self.settlement_service is not None:
            if hasattr(self.settlement_service, "metrics"):
                self.settlement_service.metrics = self.metrics
            if hasattr(self.settlement_service, "event_logger"):
                self.settlement_service.event_logger = self.event_logger

    def manifest(self, *, base_url: str | None = None) -> dict:
        return build_manifest(
            service_name=self.config.service_name,
            service_description=self.config.service_description,
            primary_chain=self.config.primary_chain(),
            routes=self.config.routes,
            plans=self.config.plans,
            management_prefix=self.config.management_prefix,
            base_url=base_url,
            seller_private_key=None if self.config.settlement is None else self.config.settlement.seller_private_key,
        )

    def discover(self, *, base_url: str | None = None) -> dict:
        manifest = self.manifest(base_url=base_url)
        management_base_url = (
            f"{base_url}{self.config.management_prefix.rstrip('/')}"
            if base_url
            else self.config.management_prefix.rstrip("/")
        )
        return {
            "seller": self.config.seller_address,
            "chain": "tron",
            "chain_id": manifest["primary_chain"].get("chain_id"),
            "settlement_backend": manifest["primary_chain"].get("settlement_backend"),
            "channel_scheme": "tron-contract",
            "contract_address": self.config.contract_address,
            "token_address": self.config.token_address,
            "default_deposit_atomic": self.config.default_deposit_atomic,
            "default_channel_ttl_s": self.config.default_channel_ttl_s,
            "service_name": self.config.service_name,
            "service_description": self.config.service_description,
            "routes": manifest["routes"],
            "plans": manifest["plans"],
            "manifest_url": manifest["endpoints"]["discover"],
            "protocol_reference_url": manifest["endpoints"]["protocol_reference"],
            "create_payment_intent_url": manifest["endpoints"]["create_payment_intent"],
            "reconcile_settlements_url": manifest["endpoints"]["reconcile_settlements"],
            "recover_payments_url": manifest["endpoints"]["recover_payments"],
            "list_pending_payments_url": manifest["endpoints"]["list_pending_payments"],
            "payment_status_template": manifest["endpoints"]["payment_status_template"],
            "ops_health_url": manifest["endpoints"]["ops_health"],
            "agent_status_url": manifest["endpoints"]["agent_status"],
            "ops_payment_action_template": manifest["endpoints"]["ops_payment_action_template"],
            "capability_registry_url": f"{management_base_url}/registry/capabilities",
            "http402_conformance_url": f"{management_base_url}/protocol/http402-conformance",
            "billing_summary_url": f"{management_base_url}/ops/billing/summary",
            "receipts_url": f"{management_base_url}/ops/receipts",
            "webhook_outbox_url": f"{management_base_url}/ops/webhooks/outbox",
        }

    def protocol_reference(self) -> dict:
        return build_protocol_reference()

    def open_channel(self, request: OpenChannelRequest) -> OpenChannelResponse:
        deposit_atomic = request.deposit_atomic or self.config.default_deposit_atomic
        ttl_s = request.ttl_s or self.config.default_channel_ttl_s
        expires_at = int(time.time()) + ttl_s
        channel_salt = request.channel_salt or f"0x{secrets.token_hex(32)}"
        channel_id = None
        channel_id_source = "unavailable"
        try:
            channel_id = make_channel_id(
                buyer_address=request.buyer_address,
                seller_address=self.config.seller_address,
                token_address=self.config.token_address,
                channel_salt=channel_salt,
            )
            channel_id_source = "chain_derived"
        except Exception:
            channel_id = None
            channel_id_source = "unavailable"
        self.metrics.incr("channels_opened_total")
        self.event_logger.emit(
            "channel_opened",
            buyer_address=request.buyer_address,
            route_path=request.route_path,
            channel_id_source=channel_id_source,
        )
        return OpenChannelResponse(
            channel_id=channel_id,
            channel_id_source=channel_id_source,
            chain="tron",
            chain_id=self.config.primary_chain().chain_id,
            channel_scheme="tron-contract",
            seller=self.config.seller_address,
            contract_address=self.config.contract_address,
            token_address=self.config.token_address,
            deposit_atomic=deposit_atomic,
            expires_at=expires_at,
            channel_salt=channel_salt,
        )

    def record_payment(self, record: PaymentRecord) -> PaymentRecord:
        return self.payment_store.upsert(record)

    def create_payment_intent(self, request: CreatePaymentIntentRequest | CreatePaymentRequest) -> PaymentRecord:
        if request.request_deadline <= int(time.time()):
            raise aimipay_error(
                "request_deadline_expired",
                message="request_deadline is already expired",
                details={"request_deadline": request.request_deadline},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        amount_atomic = request.amount_atomic
        if amount_atomic is None:
            amount_atomic = self._resolve_route_amount(
                route_path=request.route_path,
                method=request.request_method,
            )
        if amount_atomic is None:
            raise aimipay_error(
                "amount_required",
                details={"route_path": request.route_path, "method": request.request_method},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        settlement_backend = None if self.config.settlement is None else self.config.settlement.executor_backend
        if settlement_backend == "claim_script" and (
            not request.request_digest or not request.buyer_signature
        ):
            raise aimipay_error(
                "missing_buyer_authorization",
                details={"settlement_backend": settlement_backend},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        record = PaymentRecord(
            payment_id=request.payment_id or make_payment_id(),
            idempotency_key=request.idempotency_key,
            route_path=request.route_path,
            amount_atomic=amount_atomic,
            chain="tron",
            buyer_address=request.buyer_address,
            seller_address=self.config.seller_address,
            channel_id=request.channel_id,
            contract_address=self.config.contract_address,
            token_address=self.config.token_address,
            voucher_nonce=request.voucher_nonce,
            expires_at=request.expires_at,
            request_deadline=request.request_deadline,
            request_method=request.request_method,
            request_path=request.request_path or request.route_path or "/",
            request_body=request.request_body,
            request_digest=request.request_digest,
            buyer_signature=request.buyer_signature,
            status="authorized",
            status_reason="payment intent created and ready for settlement",
        )
        stored = self._touch_payment(self.payment_store.create_or_get(record))
        self.metrics.incr("payment_intents_created_total")
        self.event_logger.emit(
            "payment_intent_created",
            payment_id=stored.payment_id,
            route_path=stored.route_path,
            amount_atomic=stored.amount_atomic,
        )
        self._record_webhook_event("payment.intent_created", stored)
        return stored

    def create_payment(self, request: CreatePaymentRequest) -> PaymentRecord:
        return self.create_payment_intent(request)

    def get_payment(self, payment_id: str) -> PaymentRecord | None:
        record = self.payment_store.get(payment_id)
        if record is None:
            return None
        self.metrics.incr("payment_status_queries_total")
        return self._touch_payment(record)

    def recover_payments(
        self,
        *,
        payment_id: str | None = None,
        idempotency_key: str | None = None,
        channel_id: str | None = None,
        statuses: list[str] | None = None,
    ) -> list[PaymentRecord]:
        records = self.payment_store.recover(
            payment_id=payment_id,
            idempotency_key=idempotency_key,
            channel_id=channel_id,
            statuses=statuses,
        )
        self.metrics.incr("payment_recover_queries_total")
        return [self._touch_payment(record) for record in records]

    def list_pending_payments(self) -> list[PaymentRecord]:
        return self.recover_payments(statuses=["pending", "authorized", "submitted"])

    def execute_settlements(self, *, payment_id: str | None = None) -> list[PaymentRecord]:
        if self.settlement_service is None:
            raise aimipay_error("settlement_not_configured", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        if payment_id:
            records = [self._touch_payment(self.settlement_service.execute_payment(payment_id))]
        else:
            records = [self._touch_payment(record) for record in self.settlement_service.execute_pending()]
        self.metrics.incr("settlement_execute_requests_total")
        self.metrics.incr("settlement_execute_records_total", len(records))
        self._update_status_metrics(records)
        for record in records:
            self._record_webhook_event(f"payment.{record.status}", record)
        return records

    def reconcile_settlements(self, *, payment_id: str | None = None) -> list[PaymentRecord]:
        if self.settlement_service is None:
            raise aimipay_error("settlement_not_configured", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        if payment_id:
            if not hasattr(self.settlement_service, "reconcile_payment"):
                record = self.get_payment(payment_id)
                if record is None:
                    raise aimipay_error(
                        "payment_not_found",
                        details={"payment_id": payment_id},
                        status_code=status.HTTP_404_NOT_FOUND,
                    )
                records = [self._touch_payment(record)]
            else:
                records = [self._touch_payment(self.settlement_service.reconcile_payment(payment_id))]
            self.metrics.incr("settlement_reconcile_requests_total")
            self.metrics.incr("settlement_reconcile_records_total", len(records))
            self._update_status_metrics(records)
            for record in records:
                self._record_webhook_event(f"payment.{record.status}", record)
            return records
        if not hasattr(self.settlement_service, "reconcile_submitted"):
            return []
        records = [self._touch_payment(record) for record in self.settlement_service.reconcile_submitted()]
        self.metrics.incr("settlement_reconcile_requests_total")
        self.metrics.incr("settlement_reconcile_records_total", len(records))
        self._update_status_metrics(records)
        for record in records:
            self._record_webhook_event(f"payment.{record.status}", record)
        return records

    def capability_registry(self) -> dict:
        return {
            "schema_version": "aimipay.capability-registry.v1",
            "generated_at": int(time.time()),
            "service": {
                "name": self.config.service_name,
                "description": self.config.service_description,
                "seller_address": self.config.seller_address,
                "network": self.config.network,
                "asset": {
                    "symbol": self.config.asset_symbol,
                    "decimals": self.config.asset_decimals,
                    "address": self.config.token_address,
                },
            },
            "capabilities": [
                self._capability_entry(route)
                for route in self.config.routes
                if route.enabled and route.supports_auto_purchase
            ],
            "plans": [plan.model_dump(mode="json") for plan in self.config.plans if plan.enabled],
            "agent_hints": {
                "default_decision": "auto_purchase_when_budget_allows",
                "payment_protocols": ["aimipay.http402.v1", "aimipay.payment-intent.v1"],
                "risk_controls": ["budget_hint", "requires_human_approval", "safe_retry_policy"],
            },
        }

    def http402_conformance(self) -> dict:
        return {
            "schema_version": "aimipay.http402-conformance.v1",
            "generated_at": int(time.time()),
            "profile": "aimipay-http402-tron-v1",
            "inspired_by": ["x402-http-402-payment-required", "agentic-commerce-payment-intent"],
            "implemented": [
                "HTTP 402 response with machine-readable payment requirements",
                "X-PAYMENT request header",
                "X-AIMIPAY-PAYMENT-ID fallback request header",
                "X-PAYMENT-RESPONSE receipt header",
                "route and request path binding",
                "minimum amount enforcement",
                "buyer auto-retry lifecycle",
                "agent-readable error recovery hints",
            ],
            "headers": {
                "request": ["X-PAYMENT", "X-AIMIPAY-PAYMENT-ID"],
                "response": ["X-PAYMENT-RESPONSE"],
            },
            "compatibility_modes": {
                "x402_style": {
                    "enabled": True,
                    "payment_required_status": 402,
                    "payment_request_header": "X-PAYMENT",
                    "payment_response_header": "X-PAYMENT-RESPONSE",
                    "facilitator_api_wire_compatible": False,
                },
                "ap2_mandate_style": {
                    "enabled": True,
                    "wire_compatible_with_visa_ap2": False,
                    "mandate_endpoint": f"{self.config.management_prefix.rstrip('/')}/protocol/agentic-commerce-mandate-template",
                },
            },
            "resource_binding": {
                "route_path_required": True,
                "request_path_required_when_present": True,
                "minimum_amount_atomic_enforced": True,
            },
            "settlement": {
                "chain": "tron",
                "channel_scheme": "tron-contract",
                "asset_symbol": self.config.asset_symbol,
            },
            "not_yet_claimed": [
                "coinbase-x402-wire-compatible-facilitator-api",
                "visa-ap2-mandate-wire-format",
            ],
        }

    def agentic_commerce_mandate_template(self) -> dict:
        return {
            "schema_version": "aimipay.agentic-commerce-mandate-template.v1",
            "generated_at": int(time.time()),
            "purpose": "Describe the fields an AI host should preserve before spending user funds.",
            "compatibility_note": "AP2-inspired authorization object, not a Visa AP2 wire-compatible message.",
            "required_fields": [
                "buyer_address",
                "merchant_base_url",
                "capability_id",
                "max_amount_atomic",
                "asset_symbol",
                "expires_at",
                "human_approval_required",
            ],
            "example": {
                "buyer_address": "TRX_BUYER",
                "merchant_base_url": "https://merchant.example",
                "capability_id": "coding-agent-fix",
                "max_amount_atomic": 1_000_000,
                "asset_symbol": self.config.asset_symbol,
                "expires_at": int(time.time()) + 900,
                "human_approval_required": False,
                "reason": "User allowed the coding agent to buy one tool call under budget.",
            },
        }

    def billing_summary(self) -> dict:
        records = [self._touch_payment(record) for record in self.payment_store.list()]
        totals = {
            "authorized_atomic": 0,
            "submitted_atomic": 0,
            "settled_atomic": 0,
            "failed_atomic": 0,
            "expired_atomic": 0,
        }
        status_counts: dict[str, int] = {}
        by_route: dict[str, dict] = {}
        for record in records:
            status_name = record.status or "unknown"
            amount = record.amount_atomic or 0
            status_counts[status_name] = status_counts.get(status_name, 0) + 1
            total_key = f"{status_name}_atomic"
            if total_key in totals:
                totals[total_key] += amount
            route_key = record.route_path or "unknown"
            route_summary = by_route.setdefault(
                route_key,
                {
                    "route_path": route_key,
                    "payments_count": 0,
                    "status_counts": {},
                    "authorized_atomic": 0,
                    "submitted_atomic": 0,
                    "settled_atomic": 0,
                    "failed_atomic": 0,
                    "expired_atomic": 0,
                },
            )
            route_summary["payments_count"] += 1
            route_summary["status_counts"][status_name] = route_summary["status_counts"].get(status_name, 0) + 1
            if total_key in route_summary:
                route_summary[total_key] += amount
        return {
            "schema_version": "aimipay.billing-summary.v1",
            "generated_at": int(time.time()),
            "asset": {
                "symbol": self.config.asset_symbol,
                "decimals": self.config.asset_decimals,
                "address": self.config.token_address,
            },
            "payments_count": len(records),
            "status_counts": status_counts,
            "totals": totals,
            "routes": list(by_route.values()),
        }

    def billing_statement(
        self,
        *,
        period_start: int | None = None,
        period_end: int | None = None,
    ) -> dict:
        records = [self._touch_payment(record) for record in self.payment_store.list()]
        if period_start is not None:
            records = [record for record in records if (record.created_at or 0) >= period_start]
        if period_end is not None:
            records = [record for record in records if (record.created_at or 0) <= period_end]
        settled = [record for record in records if record.status == "settled"]
        failed = [record for record in records if record.status in {"failed", "expired"}]
        gross_atomic = sum(record.amount_atomic or 0 for record in settled)
        statement = {
            "schema_version": "aimipay.billing-statement.v1",
            "generated_at": int(time.time()),
            "period": {
                "start": period_start,
                "end": period_end,
            },
            "merchant": {
                "service_name": self.config.service_name,
                "seller_address": self.config.seller_address,
            },
            "asset": {
                "symbol": self.config.asset_symbol,
                "decimals": self.config.asset_decimals,
                "address": self.config.token_address,
            },
            "payments": {
                "settled_count": len(settled),
                "failed_or_expired_count": len(failed),
                "gross_settled_atomic": gross_atomic,
            },
            "line_items": [self.payment_receipt(record) for record in records],
        }
        statement["statement_hash"] = _canonical_sha256(statement)
        return statement

    def payout_report(self, *, period_start: int | None = None, period_end: int | None = None) -> dict:
        statement = self.billing_statement(period_start=period_start, period_end=period_end)
        gross_atomic = statement["payments"]["gross_settled_atomic"]
        report = {
            "schema_version": "aimipay.payout-report.v1",
            "generated_at": int(time.time()),
            "period": statement["period"],
            "seller_address": self.config.seller_address,
            "asset_symbol": self.config.asset_symbol,
            "gross_settled_atomic": gross_atomic,
            "platform_fee_atomic": 0,
            "net_payout_atomic": gross_atomic,
            "source_statement_hash": statement["statement_hash"],
        }
        report["payout_report_hash"] = _canonical_sha256(report)
        return report

    def list_receipts(
        self,
        *,
        status_filter: str | None = None,
        route_path: str | None = None,
        limit: int = 100,
    ) -> dict:
        statuses = None if status_filter is None else {item.strip() for item in status_filter.split(",") if item.strip()}
        records = [self._touch_payment(record) for record in self.payment_store.list()]
        if statuses is not None:
            records = [record for record in records if record.status in statuses]
        if route_path is not None:
            records = [record for record in records if record.route_path == route_path]
        records = sorted(records, key=lambda record: ((record.updated_at or 0), record.payment_id), reverse=True)
        bounded_limit = max(1, min(limit, 500))
        return {
            "schema_version": "aimipay.receipt-list.v1",
            "generated_at": int(time.time()),
            "count": len(records[:bounded_limit]),
            "total_matching": len(records),
            "receipts": [self.payment_receipt(record) for record in records[:bounded_limit]],
        }

    def payment_receipt(self, record: PaymentRecord) -> dict:
        normalized = self._touch_payment(record)
        return {
            "schema_version": "aimipay.receipt.v1",
            "payment_id": normalized.payment_id,
            "status": normalized.status,
            "route_path": normalized.route_path,
            "request_path": normalized.request_path,
            "amount_atomic": normalized.amount_atomic,
            "asset_symbol": self.config.asset_symbol,
            "asset_decimals": self.config.asset_decimals,
            "buyer_address": normalized.buyer_address,
            "seller_address": normalized.seller_address,
            "channel_id": normalized.channel_id,
            "tx_id": normalized.tx_id,
            "created_at": normalized.created_at,
            "updated_at": normalized.updated_at,
            "settled_at": normalized.settled_at,
            "confirmed_at": normalized.confirmed_at,
            "receipt_hash": _canonical_sha256(
                {
                    "payment_id": normalized.payment_id,
                    "status": normalized.status,
                    "route_path": normalized.route_path,
                    "amount_atomic": normalized.amount_atomic,
                    "tx_id": normalized.tx_id,
                    "settled_at": normalized.settled_at,
                }
            ),
        }

    def health_report(self) -> dict:
        checks = validate_runtime_config(self.config)
        unfinished = len(self.list_pending_payments())
        self.metrics.set_gauge("unfinished_payments", unfinished)
        summary = build_runtime_summary(metrics=self.metrics, checks=checks["checks"])
        return {
            "ok": bool(checks["ok"]),
            "service_name": self.config.service_name,
            "settlement_backend": None if self.config.settlement is None else self.config.settlement.executor_backend,
            "storage_backend": "sqlite" if self.config.sqlite_path else "memory",
            "checks": checks["checks"],
            "metrics": self.metrics.snapshot(),
            "summary": summary,
        }

    def prometheus_metrics(self) -> str:
        checks = validate_runtime_config(self.config)
        unfinished = len(self.list_pending_payments())
        self.metrics.set_gauge("unfinished_payments", unfinished)
        summary = build_runtime_summary(metrics=self.metrics, checks=checks["checks"])
        export = self.metrics.to_prometheus(namespace="aimipay")
        export += f'aimipay_runtime_ok {1 if checks["ok"] else 0}\n'
        export += f'aimipay_runtime_health{{level="{summary["health"]}"}} 1\n'
        return export

    def diagnostic_bundle(self) -> dict:
        health = self.health_report()
        pending = self.list_pending_payments()
        return {
            "schema_version": "aimipay.diagnostic-bundle.v1",
            "generated_at": int(time.time()),
            "health": health,
            "security": {
                "admin_token_configured": bool(
                    self.config.admin_token
                    or self.config.admin_token_sha256
                    or self.config.admin_read_token
                    or self.config.admin_read_token_sha256
                ),
                "audit_log_configured": bool(self.config.audit_log_path),
                "storage_backend": "sqlite" if self.config.sqlite_path else "memory",
            },
            "payments": {
                "pending_count": len(pending),
                "pending": [self.serialize_payment(record) for record in pending[:50]],
            },
            "redaction": {
                "private_keys": "redacted",
                "admin_tokens": "redacted",
                "signatures": "redacted",
            },
        }

    def agent_status(self) -> dict:
        health = self.health_report()
        pending = self.list_pending_payments()
        checks = list(health.get("checks") or [])
        blockers = [
            {
                "name": item.get("name"),
                "detail": item.get("detail"),
            }
            for item in checks
            if item.get("level") in {"error", "critical"} or item.get("ok") is False
        ]
        warnings = [
            {
                "name": item.get("name"),
                "detail": item.get("detail"),
            }
            for item in checks
            if item.get("level") == "warning"
        ]
        status_counts: dict[str, int] = {}
        for record in pending:
            status_name = record.status or "unknown"
            status_counts[status_name] = status_counts.get(status_name, 0) + 1
        next_actions: list[dict[str, str]] = []
        if blockers:
            next_actions.append(
                {
                    "action": "fix_runtime_configuration",
                    "reason": "runtime checks have blocking failures",
                }
            )
        if pending:
            next_actions.append(
                {
                    "action": "recover_or_finalize_pending_payments",
                    "reason": "unfinished payments are present",
                }
            )
        if not blockers and not pending:
            next_actions.append(
                {
                    "action": "ready",
                    "reason": "merchant payment gateway is ready for agent purchases",
                }
            )
        return {
            "schema_version": "aimipay.agent-status.v1",
            "generated_at": int(time.time()),
            "service": {
                "name": self.config.service_name,
                "description": self.config.service_description,
                "seller_address": self.config.seller_address,
                "chain": "tron",
                "chain_id": self.config.primary_chain().chain_id,
                "settlement_backend": None if self.config.settlement is None else self.config.settlement.executor_backend,
                "storage_backend": "sqlite" if self.config.sqlite_path else "memory",
            },
            "readiness": {
                "ready": bool(health.get("ok")) and not blockers,
                "health": health.get("summary", {}).get("health"),
                "blockers": blockers,
                "warnings": warnings,
                "checks": checks,
            },
            "capabilities": {
                "routes": [route.model_dump(mode="json") for route in self.config.routes if route.enabled],
                "plans": [plan.model_dump(mode="json") for plan in self.config.plans if plan.enabled],
            },
            "payments": {
                "unfinished_count": len(pending),
                "status_counts": status_counts,
                "latest_unfinished": [self.serialize_payment(record) for record in pending[:10]],
            },
            "security": {
                "admin_read_protected": bool(
                    self.config.admin_token
                    or self.config.admin_token_sha256
                    or self.config.admin_read_token
                    or self.config.admin_read_token_sha256
                ),
                "audit_log_configured": bool(self.config.audit_log_path),
            },
            "next_actions": next_actions,
        }

    def apply_operator_action(self, payment_id: str, action: OperatorPaymentActionRequest) -> PaymentRecord:
        record = self.payment_store.get(payment_id)
        if record is None:
            raise aimipay_error(
                "payment_not_found",
                details={"payment_id": payment_id},
                status_code=status.HTTP_404_NOT_FOUND,
            )
        note = action.note.strip()
        now = action.settled_at or int(time.time())
        if action.action == "mark_settled":
            updated = record.model_copy(
                update={
                    "status": "settled",
                    "status_reason": "payment manually marked as settled",
                    "error_code": None,
                    "error_message": None,
                    "error_retryable": None,
                    "confirmation_status": "manual",
                    "confirmation_error": None,
                    "settled_at": now,
                    "confirmed_at": now,
                    "tx_id": action.tx_id or record.tx_id,
                    "processing_stage": None,
                    "processing_token": None,
                    "processing_started_at": None,
                }
            )
            metric_key = "operator_mark_settled_total"
            event_name = "operator_mark_settled"
        elif action.action == "mark_compensated":
            updated = record.model_copy(
                update={
                    "status": "failed",
                    "status_reason": "manual compensation recorded",
                    "error_code": "manual_compensation_recorded",
                    "error_message": note,
                    "error_retryable": False,
                    "confirmation_status": record.confirmation_status,
                    "processing_stage": None,
                    "processing_token": None,
                    "processing_started_at": None,
                }
            )
            metric_key = "operator_mark_compensated_total"
            event_name = "operator_mark_compensated"
        else:
            updated = record.model_copy(
                update={
                    "status": "failed",
                    "status_reason": "payment requires manual intervention",
                    "error_code": "manual_intervention_required",
                    "error_message": note,
                    "error_retryable": False,
                    "processing_stage": None,
                    "processing_token": None,
                    "processing_started_at": None,
                }
            )
            metric_key = "operator_mark_failed_total"
            event_name = "operator_mark_failed"
        stored = self.payment_store.upsert(updated)
        self.metrics.incr(metric_key)
        self._update_status_metrics([stored])
        self.event_logger.emit(
            event_name,
            payment_id=stored.payment_id,
            action=action.action,
            note=note,
        )
        self._record_webhook_event(f"payment.{stored.status}", stored)
        return stored

    def _resolve_route_amount(self, *, route_path: str | None, method: str) -> int | None:
        if not route_path:
            return None
        normalized_method = method.upper()
        for route in self.config.routes:
            if route.path == route_path and route.method.upper() == normalized_method:
                return route.price_atomic
        return None

    def serialize_payment(self, record: PaymentRecord) -> dict:
        normalized = self._touch_payment(record)
        payload = normalized.model_dump(mode="json")
        payload.pop("processing_stage", None)
        payload.pop("processing_token", None)
        payload.pop("processing_started_at", None)
        payload.update(build_payment_lifecycle(normalized))
        payload["payment_intent_id"] = normalized.payment_id
        if normalized.error_code:
            payload["error"] = error_payload(
                normalized.error_code,
                normalized.error_message,
                retryable=normalized.error_retryable,
            )["error"]
        return payload

    def _capability_entry(self, route: MerchantRoute) -> dict:
        payload = route.model_dump(mode="json")
        payload["payment"] = {
            "protocol": "aimipay.http402.v1",
            "amount_atomic": route.price_atomic,
            "asset_symbol": self.config.asset_symbol,
            "asset_decimals": self.config.asset_decimals,
            "pricing_model": route.pricing_model,
            "usage_unit": route.usage_unit,
        }
        payload["agent_decision"] = {
            "auto_purchase_allowed": bool(route.supports_auto_purchase and not route.requires_human_approval),
            "requires_human_approval": route.requires_human_approval,
            "budget_hint": None if route.budget_hint is None else route.budget_hint.model_dump(mode="json"),
            "safe_retry_policy": route.safe_retry_policy,
        }
        return payload

    def _record_webhook_event(self, event_type: str, record: PaymentRecord) -> None:
        if not self.config.webhook_urls:
            return
        event = {
            "schema_version": "aimipay.webhook-event.v1",
            "event_id": f"evt_{secrets.token_hex(16)}",
            "type": event_type,
            "created_at": int(time.time()),
            "delivery": {
                "mode": "outbox",
                "targets": list(self.config.webhook_urls),
                "signed": bool(self.config.webhook_secret),
            },
            "payment": self.serialize_payment(record),
        }
        if self.config.webhook_secret:
            event["signature_algorithm"] = "hmac-sha256"
            event["signature"] = _hmac_sha256(self.config.webhook_secret, event)
        self.webhook_outbox.append(event)
        del self.webhook_outbox[:-1000]

    def _update_status_metrics(self, records: list[PaymentRecord]) -> None:
        for record in records:
            self.metrics.incr(f"payments_status_{record.status}_total")

    def _touch_payment(self, record: PaymentRecord) -> PaymentRecord:
        now = int(time.time())
        if record.status in {"settled", "failed", "expired", "submitted"}:
            return record
        if record.request_deadline is not None and record.request_deadline < now:
            updated = record.model_copy(
                update={
                    "status": "expired",
                    "status_reason": "request deadline expired before settlement",
                    "error_code": "request_deadline_expired",
                    "error_message": "request deadline expired before settlement",
                    "error_retryable": False,
                }
            )
            return self.payment_store.upsert(updated)
        if record.expires_at is not None and record.expires_at < now:
            updated = record.model_copy(
                update={
                    "status": "expired",
                    "status_reason": "payment channel expired before settlement",
                    "error_code": "payment_expired",
                    "error_message": "payment channel expired before settlement",
                    "error_retryable": False,
                }
            )
            return self.payment_store.upsert(updated)
        return record


def install_gateway(
    app: FastAPI,
    config: GatewayConfig,
    *,
    settlement_service: object | None = None,
) -> GatewayRuntime:
    payment_store: InMemoryPaymentStore | SqlitePaymentStore
    if config.sqlite_path:
        payment_store = SqlitePaymentStore(config.sqlite_path)
    else:
        payment_store = InMemoryPaymentStore()
    if settlement_service is None and config.settlement is not None:
        settlement_service = build_default_tron_settlement_service(
            payment_store=payment_store,
            config=config.settlement.tron_service_config(),
        )
    runtime = GatewayRuntime(
        config=config,
        payment_store=payment_store,
        settlement_service=settlement_service,
    )
    router = APIRouter(prefix=config.management_prefix.rstrip("/"))

    @app.get("/.well-known/aimipay.json", include_in_schema=False)
    async def well_known(request: Request) -> dict:
        return runtime.manifest(base_url=str(request.base_url).rstrip("/"))

    @router.get("/discover")
    async def discover(request: Request) -> dict:
        return runtime.discover(base_url=str(request.base_url).rstrip("/"))

    @router.get("/ops/health")
    async def ops_health(request: Request) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        return runtime.health_report()

    @router.get("/ops/metrics")
    async def ops_metrics(request: Request) -> Response:
        _require_admin_access(request, runtime.config, action="read")
        return Response(content=runtime.prometheus_metrics(), media_type="text/plain; version=0.0.4")

    @router.get("/ops/diagnostics")
    async def ops_diagnostics(request: Request) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        runtime.event_logger.emit("admin_diagnostics_requested", caller=_caller_host(request))
        return runtime.diagnostic_bundle()

    @router.get("/ops/agent-status")
    async def ops_agent_status(request: Request) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        runtime.event_logger.emit("admin_agent_status_requested", caller=_caller_host(request))
        return runtime.agent_status()

    @router.get("/ops/billing/summary")
    async def ops_billing_summary(request: Request) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        runtime.event_logger.emit("admin_billing_summary_requested", caller=_caller_host(request))
        return runtime.billing_summary()

    @router.get("/ops/billing/statement")
    async def ops_billing_statement(
        request: Request,
        period_start: int | None = None,
        period_end: int | None = None,
    ) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        runtime.event_logger.emit("admin_billing_statement_requested", caller=_caller_host(request))
        return runtime.billing_statement(period_start=period_start, period_end=period_end)

    @router.get("/ops/payouts/report")
    async def ops_payout_report(
        request: Request,
        period_start: int | None = None,
        period_end: int | None = None,
    ) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        runtime.event_logger.emit("admin_payout_report_requested", caller=_caller_host(request))
        return runtime.payout_report(period_start=period_start, period_end=period_end)

    @router.get("/ops/receipts")
    async def ops_receipts(
        request: Request,
        status_filter: str | None = None,
        route_path: str | None = None,
        limit: int = 100,
    ) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        runtime.event_logger.emit("admin_receipts_requested", caller=_caller_host(request))
        return runtime.list_receipts(status_filter=status_filter, route_path=route_path, limit=limit)

    @router.get("/ops/webhooks/outbox")
    async def ops_webhook_outbox(request: Request, limit: int = 100) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        runtime.event_logger.emit("admin_webhook_outbox_requested", caller=_caller_host(request))
        bounded_limit = max(1, min(limit, 500))
        events = runtime.webhook_outbox[-bounded_limit:]
        return {
            "schema_version": "aimipay.webhook-outbox.v1",
            "generated_at": int(time.time()),
            "count": len(events),
            "total_buffered": len(runtime.webhook_outbox),
            "events": events,
        }

    @router.post("/ops/payments/{payment_id}/action")
    async def ops_payment_action(request: Request, payment_id: str, payload: OperatorPaymentActionRequest) -> dict:
        _require_admin_access(request, runtime.config, action="write")
        runtime.event_logger.emit("admin_payment_action_requested", payment_id=payment_id, action=payload.action, caller=_caller_host(request))
        try:
            record = runtime.apply_operator_action(payment_id, payload)
        except AimiPayError as exc:
            raise _as_http_exception(exc) from exc
        return runtime.serialize_payment(record)

    @router.get("/protocol/reference")
    async def protocol_reference() -> dict:
        return runtime.protocol_reference()

    @router.get("/protocol/http402-conformance")
    async def protocol_http402_conformance() -> dict:
        return runtime.http402_conformance()

    @router.get("/protocol/agentic-commerce-mandate-template")
    async def protocol_agentic_commerce_mandate_template() -> dict:
        return runtime.agentic_commerce_mandate_template()

    @router.get("/registry/capabilities")
    async def registry_capabilities() -> dict:
        return runtime.capability_registry()

    @router.post("/channels/open")
    async def open_channel(payload: OpenChannelRequest) -> dict:
        return runtime.open_channel(payload).model_dump(mode="json")

    @router.post("/payment-intents")
    async def create_payment_intent(payload: CreatePaymentIntentRequest) -> dict:
        try:
            record = runtime.create_payment_intent(payload)
        except AimiPayError as exc:
            raise _as_http_exception(exc) from exc
        return runtime.serialize_payment(record)

    @router.get("/payments/pending")
    async def pending_payments(request: Request) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        records = runtime.list_pending_payments()
        return {
            "count": len(records),
            "payments": [runtime.serialize_payment(record) for record in records],
        }

    @router.get("/payments/recover")
    async def recover_payments(
        request: Request,
        payment_id: str | None = None,
        idempotency_key: str | None = None,
        channel_id: str | None = None,
        status_filter: str | None = None,
    ) -> dict:
        _require_admin_access(request, runtime.config, action="read")
        statuses = None if status_filter is None else [item.strip() for item in status_filter.split(",") if item.strip()]
        records = runtime.recover_payments(
            payment_id=payment_id,
            idempotency_key=idempotency_key,
            channel_id=channel_id,
            statuses=statuses,
        )
        return {
            "count": len(records),
            "payments": [runtime.serialize_payment(record) for record in records],
        }

    @router.get("/payments/{payment_id}")
    async def payment_status(payment_id: str) -> dict:
        record = runtime.get_payment(payment_id)
        if record is None:
            raise _as_http_exception(
                aimipay_error(
                    "payment_not_found",
                    details={"payment_id": payment_id},
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            )
        return runtime.serialize_payment(record)

    @router.post("/payments")
    async def create_payment(payload: CreatePaymentRequest) -> dict:
        try:
            record = runtime.create_payment(payload)
        except AimiPayError as exc:
            raise _as_http_exception(exc) from exc
        return runtime.serialize_payment(record)

    @router.post("/settlements/execute")
    async def execute_settlements(request: Request, payload: SettlementExecuteRequest) -> dict:
        _require_admin_access(request, runtime.config, action="write")
        runtime.event_logger.emit("admin_settlement_execute_requested", payment_id=payload.payment_id, caller=_caller_host(request))
        try:
            records = runtime.execute_settlements(payment_id=payload.payment_id)
        except AimiPayError as exc:
            raise _as_http_exception(exc) from exc
        return {
            "executed_count": len(records),
            "payments": [runtime.serialize_payment(record) for record in records],
        }

    @router.post("/settlements/reconcile")
    async def reconcile_settlements(request: Request, payload: SettlementExecuteRequest) -> dict:
        _require_admin_access(request, runtime.config, action="write")
        runtime.event_logger.emit("admin_settlement_reconcile_requested", payment_id=payload.payment_id, caller=_caller_host(request))
        try:
            records = runtime.reconcile_settlements(payment_id=payload.payment_id)
        except AimiPayError as exc:
            raise _as_http_exception(exc) from exc
        return {
            "reconciled_count": len(records),
            "payments": [runtime.serialize_payment(record) for record in records],
        }

    app.include_router(router)
    app.state.aimipay_gateway = runtime
    return runtime


def _as_http_exception(exc: AimiPayError) -> HTTPException:
    status_code = exc.status_code or status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=error_payload(exc))


def _canonical_sha256(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _hmac_sha256(secret: str, payload: dict) -> str:
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _require_admin_access(request: Request, config: GatewayConfig, *, action: str) -> None:
    tokens = _accepted_admin_secrets(config, action=action)
    if tokens:
        auth = request.headers.get("authorization", "")
        header_token = request.headers.get("x-aimipay-admin-token", "")
        bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if _token_matches(bearer, tokens) or _token_matches(header_token, tokens):
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "admin_token_required"})

    host = _caller_host(request)
    if host in {"127.0.0.1", "localhost", "::1", "testclient"}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "admin_access_requires_localhost_or_token"})


def _accepted_admin_secrets(config: GatewayConfig, *, action: str) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    if action == "read":
        if config.admin_read_token:
            values.append(("plain", config.admin_read_token.strip()))
        if config.admin_read_token_sha256:
            values.append(("sha256", config.admin_read_token_sha256.strip()))
    if config.admin_token:
        values.append(("plain", config.admin_token.strip()))
    if config.admin_token_sha256:
        values.append(("sha256", config.admin_token_sha256.strip()))
    return [(kind, value) for kind, value in values if value]


def _token_matches(candidate: str, accepted: list[tuple[str, str]]) -> bool:
    if not candidate:
        return False
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    for kind, expected in accepted:
        if kind == "plain" and secrets.compare_digest(candidate, expected):
            return True
        if kind == "sha256" and secrets.compare_digest(digest, expected.lower()):
            return True
    return False


def _caller_host(request: Request) -> str:
    if request.client is None:
        return ""
    return (request.client.host or "").lower()

import os
import hashlib
from pathlib import Path
import time

import pytest
import seller.gateway as gateway_module
import seller.settlement as settlement_module
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seller import (
    AimiPayFacilitator,
    GatewaySettlementConfig,
    HostedMerchant,
    SqliteHostedGatewayRegistry,
    TronSettlementExecution,
    WebhookDeliveryWorker,
    hosted_api_key_hash,
    install_facilitator,
    install_hosted_gateway,
    install_sellable_capability,
)
from seller.gateway import GatewayConfig, install_gateway
from seller.x402_compat import decode_x402_payment, encode_x402_payment
from shared import CapabilityBudgetHint, MerchantPlan, MerchantRoute, PaymentRecord
from shared import create_intent_mandate, create_payment_mandate, verify_mandate_signature
from examples.coding_agent_paid_flow_demo import run_demo as run_coding_agent_paid_flow_demo
from examples.hosted_gateway_app import build_app as build_hosted_gateway_example_app


def _build_app() -> tuple[TestClient, object]:
    app = FastAPI()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            contract_address="0x1000000000000000000000000000000000000001",
            token_address="0x2000000000000000000000000000000000000002",
            routes=[
                MerchantRoute(
                    path="/tools/research",
                    method="POST",
                    price_atomic=250_000,
                    description="Paid research route",
                    capability_id="research-web-search",
                    capability_type="web_search",
                    pricing_model="fixed_per_call",
                    usage_unit="request",
                    delivery_mode="sync",
                    response_format="json",
                    auth_requirements=["request_digest", "buyer_signature"],
                    capability_tags=["search", "research", "web"],
                    budget_hint=CapabilityBudgetHint(
                        typical_units=3,
                        min_units=1,
                        suggested_prepaid_atomic=750_000,
                        notes="Typical coding task needs 3 paid searches",
                    ),
                )
            ],
            plans=[
                MerchantPlan(
                    plan_id="pro-monthly",
                    name="Pro Monthly",
                    amount_atomic=9_900_000,
                    subscribe_path="/billing/subscribe",
                )
            ],
        ),
    )
    return TestClient(app), runtime


def test_well_known_manifest_exposes_tron_metadata() -> None:
    client, _ = _build_app()

    response = client.get("/.well-known/aimipay.json")
    assert response.status_code == 200
    payload = response.json()

    assert payload["kind"] == "aimipay-merchant"
    assert payload["primary_chain"]["chain"] == "tron"
    assert payload["primary_chain"]["channel_scheme"] == "tron-contract"
    assert payload["primary_chain"]["contract_address"] == "0x1000000000000000000000000000000000000001"
    assert payload["routes"][0]["capability_id"] == "research-web-search"
    assert payload["routes"][0]["capability_type"] == "web_search"
    assert payload["routes"][0]["usage_unit"] == "request"
    assert payload["routes"][0]["auth_requirements"] == ["request_digest", "buyer_signature"]
    assert payload["routes"][0]["budget_hint"]["suggested_prepaid_atomic"] == 750_000
    assert payload["endpoints"]["protocol_reference"].endswith("/_aimipay/protocol/reference")
    assert payload["endpoints"]["create_payment_intent"].endswith("/_aimipay/payment-intents")
    assert payload["endpoints"]["reconcile_settlements"].endswith("/_aimipay/settlements/reconcile")
    assert payload["endpoints"]["ops_health"].endswith("/_aimipay/ops/health")
    assert payload["routes"][0]["path"] == "/tools/research"
    assert payload["plans"][0]["plan_id"] == "pro-monthly"


def test_well_known_manifest_exposes_signed_seller_profile_when_private_key_available() -> None:
    seller_private_key = "0x59c6995e998f97a5a0044966f0945382d7f4a3f1f3f7e61a821a3d1d021b6d2d"
    seller_address = "TVaEiLLej394ZxVmHZXYg3HprssbpdcsmW"
    app = FastAPI()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address=seller_address,
            contract_address="0x1000000000000000000000000000000000000001",
            token_address="0x2000000000000000000000000000000000000002",
            routes=[MerchantRoute(path="/tools/research", price_atomic=250_000)],
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://tron.local",
                seller_private_key=seller_private_key,
                chain_id=31337,
                executor_backend="claim_script",
            ),
        ),
    )
    client = TestClient(app)

    response = client.get("/.well-known/aimipay.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "aimipay.manifest.v1"
    assert payload["seller_profile"]["schema_version"] == "aimipay.seller-profile.v1"
    assert payload["seller_profile"]["seller_address"] == seller_address
    assert payload["seller_profile_signature"]["payload_kind"] == "seller_profile"
    assert payload["manifest_signature"]["payload_kind"] == "seller_manifest"


def test_protocol_reference_exposes_single_source_rules() -> None:
    client, _ = _build_app()

    response = client.get("/_aimipay/protocol/reference")

    assert response.status_code == 200
    payload = response.json()
    assert payload["protocol_version"] == "aimipay-tron-v1"
    assert payload["channel_id"]["single_source"] == "scripts/protocol.js::channelIdOf"
    assert "request_deadline" in payload["time_fields"]
    assert payload["agent_facing_protocol"]["schema_version"] == "aimipay.agent-protocol.v1"
    assert payload["agent_facing_protocol"]["tool_mapping"]["state"] == "aimipay.get_agent_state"


def test_discover_and_open_channel_return_tron_defaults() -> None:
    client, _ = _build_app()

    discover = client.get("/_aimipay/discover")
    assert discover.status_code == 200
    discovery = discover.json()
    assert discovery["chain"] == "tron"
    assert discovery["channel_scheme"] == "tron-contract"
    assert discovery["contract_address"] == "0x1000000000000000000000000000000000000001"
    assert discovery["ops_health_url"].endswith("/_aimipay/ops/health")

    open_response = client.post(
        "/_aimipay/channels/open",
        json={
            "buyer_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            "route_path": "/tools/research",
        },
    )
    assert open_response.status_code == 200
    payload = open_response.json()
    assert payload["chain"] == "tron"
    assert payload["seller"] == "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
    assert payload["contract_address"] == "0x1000000000000000000000000000000000000001"
    assert payload["token_address"] == "0x2000000000000000000000000000000000000002"
    assert payload["deposit_atomic"] == 1_000_000
    assert payload["channel_id_source"] == "chain_derived"
    assert payload["channel_id"].startswith("0x")
    assert payload["channel_salt"].startswith("0x")
    assert len(payload["channel_salt"]) == 66


def test_payment_status_returns_recorded_payment() -> None:
    client, runtime = _build_app()
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_123",
            route_path="/tools/research",
            amount_atomic=250_000,
            status="submitted",
            tx_id="trx_tx_123",
        )
    )

    response = client.get("/_aimipay/payments/pay_123")
    assert response.status_code == 200
    payload = response.json()
    assert payload["payment_id"] == "pay_123"
    assert payload["status"] == "submitted"
    assert payload["tx_id"] == "trx_tx_123"
    assert payload["next_step"] == "confirm_settlement"


def test_payment_status_is_read_only_for_submitted_payment() -> None:
    app = FastAPI()

    class FakeSettlementService:
        def __init__(self) -> None:
            self.reconcile_calls = 0

        def reconcile_payment(self, payment_id: str):
            self.reconcile_calls += 1
            raise AssertionError("payment status endpoint should not trigger reconcile")

    settlement_service = FakeSettlementService()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
        ),
        settlement_service=settlement_service,
    )
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_read_only_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            status="submitted",
            tx_id="trx_read_only_1",
        )
    )
    client = TestClient(app)

    response = client.get("/_aimipay/payments/pay_read_only_1")

    assert response.status_code == 200
    assert response.json()["status"] == "submitted"
    assert settlement_service.reconcile_calls == 0


def test_ops_health_reports_metrics_and_config_checks(tmp_path) -> None:
    sqlite_path = tmp_path / "payments.db"
    app = FastAPI()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            sqlite_path=str(sqlite_path),
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://tron.local",
                seller_private_key="seller_pk",
                chain_id=31337,
                executor_backend="claim_script",
                processing_lock_ttl_s=120,
                max_confirmation_attempts=7,
            ),
            routes=[MerchantRoute(path="/tools/research", price_atomic=250_000)],
        ),
    )
    client = TestClient(app)
    create_response = client.post(
        "/_aimipay/payment-intents",
        json={
            "payment_id": "pay_ops_1",
            "route_path": "/tools/research",
            "buyer_address": "TRX_BUYER",
            "channel_id": "channel_ops_1",
            "voucher_nonce": 1,
            "expires_at": 9_999_999_999,
            "request_deadline": int(time.time()) + 300,
            "request_digest": "0x" + "11" * 32,
            "buyer_signature": "0x" + "22" * 65,
        },
    )

    assert create_response.status_code == 200

    response = client.get("/_aimipay/ops/health")

    assert response.status_code == 200
    payload = response.json()
    assert "checks" in payload
    assert "metrics" in payload
    assert payload["summary"]["health"] in {"ok", "degraded"}
    assert payload["metrics"]["counters"]["payment_intents_created_total"] >= 1
    assert payload["metrics"]["gauges"]["unfinished_payments"] >= 1
    assert any(item["name"] == "repository_root_exists" for item in payload["checks"])


def test_ops_metrics_exports_prometheus_payload(tmp_path) -> None:
    sqlite_path = tmp_path / "payments.db"
    app = FastAPI()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            sqlite_path=str(sqlite_path),
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://tron.local",
                seller_private_key="seller_pk",
                chain_id=31337,
                executor_backend="claim_script",
            ),
        ),
    )
    client = TestClient(app)

    response = client.get("/_aimipay/ops/metrics")

    assert response.status_code == 200
    assert "aimipay_runtime_ok" in response.text
    assert "aimipay_runtime_health" in response.text


def test_ops_payment_action_can_record_manual_compensation() -> None:
    client, runtime = _build_app()
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_manual_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            status="submitted",
            tx_id="trx_manual_1",
        )
    )

    response = client.post(
        "/_aimipay/ops/payments/pay_manual_1/action",
        json={"action": "mark_compensated", "note": "refunded through support workflow"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["error_code"] == "manual_compensation_recorded"
    assert payload["error_message"] == "refunded through support workflow"


def test_ops_endpoints_require_admin_token_when_configured() -> None:
    app = FastAPI()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            admin_token="secret-admin-token",
        ),
    )
    client = TestClient(app)

    denied = client.get("/_aimipay/ops/health")
    allowed = client.get("/_aimipay/ops/health", headers={"X-AimiPay-Admin-Token": "secret-admin-token"})

    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_ops_endpoints_accept_hashed_admin_token_and_write_audit_log(tmp_path) -> None:
    app = FastAPI()
    audit_log = tmp_path / "audit.jsonl"
    token = "hashed-admin-token-123"
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            admin_token_sha256=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            audit_log_path=str(audit_log),
        ),
    )
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_audit_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            status="submitted",
            tx_id="trx_audit_1",
        )
    )
    client = TestClient(app)

    response = client.post(
        "/_aimipay/ops/payments/pay_audit_1/action",
        headers={"Authorization": f"Bearer {token}"},
        json={"action": "mark_failed", "note": "operator rejected"},
    )

    assert response.status_code == 200
    assert audit_log.exists()
    assert "admin_payment_action_requested" in audit_log.read_text(encoding="utf-8")


def test_ops_diagnostics_returns_redacted_bundle() -> None:
    app = FastAPI()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
        ),
    )
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_diag_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            status="authorized",
        )
    )
    client = TestClient(app)

    response = client.get("/_aimipay/ops/diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "aimipay.diagnostic-bundle.v1"
    assert payload["payments"]["pending_count"] == 1
    assert payload["redaction"]["private_keys"] == "redacted"


def test_ops_agent_status_returns_ai_readable_summary() -> None:
    app = FastAPI()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            routes=[
                MerchantRoute(
                    path="/tools/research",
                    method="POST",
                    price_atomic=250_000,
                    capability_id="research-web-search",
                    capability_type="web_search",
                )
            ],
        ),
    )
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_agent_status_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            status="authorized",
        )
    )
    client = TestClient(app)

    response = client.get("/_aimipay/ops/agent-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "aimipay.agent-status.v1"
    assert payload["service"]["name"] == "Research Copilot"
    assert payload["capabilities"]["routes"][0]["capability_id"] == "research-web-search"
    assert payload["payments"]["unfinished_count"] == 1
    assert payload["payments"]["status_counts"]["authorized"] == 1
    actions = {item["action"] for item in payload["next_actions"]}
    assert "recover_or_finalize_pending_payments" in actions


def test_registry_and_http402_conformance_are_agent_readable() -> None:
    client, _ = _build_app()

    registry_response = client.get("/_aimipay/registry/capabilities")
    conformance_response = client.get("/_aimipay/protocol/http402-conformance")
    mandate_response = client.get("/_aimipay/protocol/agentic-commerce-mandate-template")

    assert registry_response.status_code == 200
    registry = registry_response.json()
    assert registry["schema_version"] == "aimipay.capability-registry.v1"
    assert registry["capabilities"][0]["capability_id"] == "research-web-search"
    assert registry["capabilities"][0]["payment"]["protocol"] == "aimipay.http402.v1"
    assert registry["capabilities"][0]["agent_decision"]["auto_purchase_allowed"] is True

    assert conformance_response.status_code == 200
    conformance = conformance_response.json()
    assert conformance["schema_version"] == "aimipay.http402-conformance.v1"
    assert "X-PAYMENT" in conformance["headers"]["request"]
    assert conformance["resource_binding"]["minimum_amount_atomic_enforced"] is True
    assert conformance["compatibility_modes"]["x402_style"]["enabled"] is True

    assert mandate_response.status_code == 200
    mandate = mandate_response.json()
    assert mandate["schema_version"] == "aimipay.agentic-commerce-mandate-template.v1"
    assert "max_amount_atomic" in mandate["required_fields"]


def test_ops_billing_summary_and_receipts_are_machine_readable() -> None:
    client, runtime = _build_app()
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_bill_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            buyer_address="TRX_BUYER",
            channel_id="channel_bill_1",
            request_deadline=int(time.time()) + 300,
            expires_at=int(time.time()) + 600,
            status="settled",
            tx_id="0xsettled",
            settled_at=1_700_000_000,
            confirmed_at=1_700_000_001,
        )
    )
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_bill_2",
            route_path="/tools/research",
            amount_atomic=250_000,
            buyer_address="TRX_BUYER",
            channel_id="channel_bill_2",
            request_deadline=int(time.time()) + 300,
            expires_at=int(time.time()) + 600,
            status="authorized",
        )
    )

    summary_response = client.get("/_aimipay/ops/billing/summary")
    receipts_response = client.get("/_aimipay/ops/receipts", params={"status_filter": "settled"})

    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["schema_version"] == "aimipay.billing-summary.v1"
    assert summary["payments_count"] == 2
    assert summary["totals"]["settled_atomic"] == 250_000
    assert summary["totals"]["authorized_atomic"] == 250_000
    assert summary["routes"][0]["route_path"] == "/tools/research"

    assert receipts_response.status_code == 200
    receipts = receipts_response.json()
    assert receipts["schema_version"] == "aimipay.receipt-list.v1"
    assert receipts["count"] == 1
    assert receipts["receipts"][0]["payment_id"] == "pay_bill_1"
    assert receipts["receipts"][0]["tx_id"] == "0xsettled"
    assert receipts["receipts"][0]["receipt_hash"]

    statement_response = client.get("/_aimipay/ops/billing/statement")
    payout_response = client.get("/_aimipay/ops/payouts/report")

    assert statement_response.status_code == 200
    statement = statement_response.json()
    assert statement["schema_version"] == "aimipay.billing-statement.v1"
    assert statement["payments"]["gross_settled_atomic"] == 250_000
    assert statement["statement_hash"]

    assert payout_response.status_code == 200
    payout = payout_response.json()
    assert payout["schema_version"] == "aimipay.payout-report.v1"
    assert payout["net_payout_atomic"] == 250_000


def test_webhook_outbox_records_payment_lifecycle_events() -> None:
    app = FastAPI()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            contract_address="0x1000000000000000000000000000000000000001",
            token_address="0x2000000000000000000000000000000000000002",
            webhook_urls=["https://merchant.example/webhooks/aimipay"],
            webhook_secret="webhook-secret",
            routes=[MerchantRoute(path="/tools/research", method="POST", price_atomic=250_000)],
        ),
    )
    client = TestClient(app)
    create_response = client.post(
        "/_aimipay/payment-intents",
        json={
            "route_path": "/tools/research",
            "buyer_address": "TRX_BUYER",
            "channel_id": "channel_webhook_1",
            "voucher_nonce": 1,
            "expires_at": int(time.time()) + 600,
            "request_deadline": int(time.time()) + 300,
        },
    )
    payment_id = create_response.json()["payment_id"]
    client.post(
        f"/_aimipay/ops/payments/{payment_id}/action",
        json={"action": "mark_settled", "note": "verified against tx", "tx_id": "0xwebhook"},
    )

    response = client.get("/_aimipay/ops/webhooks/outbox")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "aimipay.webhook-outbox.v1"
    assert payload["count"] == 2
    assert payload["events"][0]["type"] == "payment.intent_created"
    assert payload["events"][1]["type"] == "payment.settled"
    assert payload["events"][1]["delivery"]["signed"] is True
    assert payload["events"][1]["signature"].startswith("sha256=")


def test_hosted_gateway_exposes_multi_tenant_catalog_and_protected_admin_summary() -> None:
    app = FastAPI()
    install_hosted_gateway(
        app,
        [
            HostedMerchant(
                merchant_id="research",
                api_key_sha256=hosted_api_key_hash("merchant-secret"),
                config=GatewayConfig(
                    service_name="Research Copilot",
                    service_description="Pay-per-use research",
                    seller_address="TRX_SELLER_A",
                    contract_address="TRX_CONTRACT",
                    token_address="TRX_USDT",
                    routes=[
                        MerchantRoute(
                            path="/tools/research",
                            method="POST",
                            price_atomic=250_000,
                            capability_id="research-web-search",
                            capability_type="web_search",
                        )
                    ],
                ),
            ),
            HostedMerchant(
                merchant_id="coding",
                config=GatewayConfig(
                    service_name="Coding Toolsmith",
                    service_description="Paid coding tools",
                    seller_address="TRX_SELLER_B",
                    contract_address="TRX_CONTRACT",
                    token_address="TRX_USDT",
                    routes=[
                        MerchantRoute(
                            path="/tools/code-review",
                            method="POST",
                            price_atomic=400_000,
                            capability_id="coding-agent-code-review",
                            capability_type="code_review",
                        )
                    ],
                ),
            ),
        ],
    )
    client = TestClient(app)

    catalog = client.get("/_aimipay/hosted/merchants").json()
    marketplace = client.get("/_aimipay/marketplace/capabilities").json()
    denied = client.get("/_aimipay/hosted/merchants/research/admin-summary")
    allowed = client.get(
        "/_aimipay/hosted/merchants/research/admin-summary",
        headers={"X-AimiPay-Merchant-Key": "merchant-secret"},
    )

    assert catalog["schema_version"] == "aimipay.hosted-merchant-catalog.v1"
    assert catalog["merchant_count"] == 2
    assert marketplace["schema_version"] == "aimipay.marketplace-capability-index.v1"
    assert {item["merchant_id"] for item in marketplace["capabilities"]} == {"research", "coding"}
    assert denied.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["schema_version"] == "aimipay.hosted-admin-summary.v1"


def test_hosted_gateway_example_app_exposes_marketplace_and_merchant_manifests() -> None:
    app = build_hosted_gateway_example_app()
    client = TestClient(app)

    root = client.get("/")
    merchants = client.get("/_aimipay/hosted/merchants")
    marketplace = client.get("/_aimipay/marketplace/capabilities")
    manifest = client.get("/merchants/research/.well-known/aimipay.json")
    denied = client.get("/_aimipay/hosted/merchants/research/admin-summary")
    allowed = client.get(
        "/_aimipay/hosted/merchants/research/admin-summary",
        headers={"X-AimiPay-Merchant-Key": "research-secret"},
    )

    assert root.status_code == 200
    assert merchants.json()["merchant_count"] == 2
    assert marketplace.json()["capability_count"] == 2
    assert manifest.json()["service_name"] == "Research Copilot"
    assert denied.status_code == 401
    assert allowed.status_code == 200


def test_sqlite_hosted_registry_persists_merchant_config(tmp_path) -> None:
    sqlite_path = tmp_path / "hosted.db"
    registry = SqliteHostedGatewayRegistry(str(sqlite_path))
    registry.add_merchant(
        HostedMerchant(
            merchant_id="research",
            api_key_sha256=hosted_api_key_hash("merchant-secret"),
            config=GatewayConfig(
                service_name="Research Copilot",
                service_description="Pay-per-use research",
                seller_address="TRX_SELLER",
                contract_address="TRX_CONTRACT",
                token_address="TRX_USDT",
                routes=[MerchantRoute(path="/tools/research", price_atomic=250_000)],
            ),
        )
    )

    restored = SqliteHostedGatewayRegistry(str(sqlite_path))

    assert restored.get("research").config.service_name == "Research Copilot"
    assert restored.get("research").api_key_sha256 == hosted_api_key_hash("merchant-secret")


def test_x402_header_helpers_and_facilitator_verify_settle() -> None:
    client, runtime = _build_app()
    app = client.app
    install_facilitator(app, runtime)
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_facilitator_1",
            route_path="/tools/research",
            request_path="/tools/research",
            amount_atomic=250_000,
            status="settled",
            tx_id="0xfacilitated",
        )
    )
    encoded = encode_x402_payment({"payment_id": "pay_facilitator_1"})

    assert decode_x402_payment(encoded)["payment_id"] == "pay_facilitator_1"

    verify_response = client.post(
        "/_aimipay/facilitator/verify",
        json={"payment": encoded, "resource": "/tools/research", "amount_atomic": 250_000},
    )
    settle_response = client.post("/_aimipay/facilitator/settle", json={"payment": encoded})

    assert verify_response.status_code == 200
    assert verify_response.json()["valid"] is True
    assert settle_response.status_code == 200
    assert settle_response.json()["payment"]["success"] is True
    assert settle_response.json()["payment"]["paymentId"] == "pay_facilitator_1"


def test_webhook_delivery_worker_records_attempts() -> None:
    app = FastAPI()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            webhook_urls=["https://merchant.example/webhook"],
            routes=[MerchantRoute(path="/tools/research", price_atomic=250_000)],
        ),
    )
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_webhook_delivery_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            status="settled",
        )
    )
    runtime._record_webhook_event("payment.settled", runtime.get_payment("pay_webhook_delivery_1"))

    class FakeHttpClient:
        def post(self, target, json):
            return type("Response", (), {"status_code": 204})()

    report = WebhookDeliveryWorker(runtime=runtime, http_client=FakeHttpClient()).deliver_pending()

    assert report["schema_version"] == "aimipay.webhook-delivery-report.v1"
    assert report["attempt_count"] == 1
    assert runtime.webhook_outbox[0]["delivery_attempts"][0]["ok"] is True


def test_mandates_can_be_signed_verified_and_bound_to_payment() -> None:
    secret = "mandate-secret"
    intent = create_intent_mandate(
        buyer_address="TRX_BUYER",
        merchant_base_url="https://merchant.example",
        capability_id="research-web-search",
        max_amount_atomic=300_000,
        expires_at=int(time.time()) + 600,
        secret=secret,
    )
    payment = create_payment_mandate(
        intent_mandate=intent,
        payment_id="pay_mandate_1",
        seller_address="TRX_SELLER",
        route_path="/tools/research",
        amount_atomic=250_000,
        expires_at=int(time.time()) + 300,
        secret=secret,
    )

    assert verify_mandate_signature(intent.model_dump(mode="json"), secret=secret, signature=intent.signature)
    assert verify_mandate_signature(payment.model_dump(mode="json"), secret=secret, signature=payment.signature)
    assert payment.intent_mandate_id == intent.mandate_id
    with pytest.raises(ValueError, match="exceeds"):
        create_payment_mandate(
            intent_mandate=intent,
            payment_id="pay_mandate_2",
            seller_address="TRX_SELLER",
            route_path="/tools/research",
            amount_atomic=400_000,
            expires_at=int(time.time()) + 300,
        )


def test_coding_agent_paid_flow_demo_runs_end_to_end() -> None:
    result = run_coding_agent_paid_flow_demo()

    assert result["schema_version"] == "aimipay.demo.coding-agent-paid-flow.v1"
    assert result["resource"]["kind"] == "code_review_result"
    assert result["payment_response"]["status"] == "settled"
    assert result["payment_response"]["route_path"] == "/tools/code-review"


def test_ops_payment_action_can_mark_manual_settlement() -> None:
    client, runtime = _build_app()
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_manual_settle_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            status="submitted",
            tx_id="trx_manual_settle_1",
        )
    )

    response = client.post(
        "/_aimipay/ops/payments/pay_manual_settle_1/action",
        json={"action": "mark_settled", "note": "verified against external receipt", "settled_at": 1700000000},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "settled"
    assert payload["confirmation_status"] == "manual"
    assert payload["settled_at"] == 1700000000


def test_create_payment_records_pending_payment() -> None:
    client, _ = _build_app()
    request_deadline = int(time.time()) + 300

    response = client.post(
        "/_aimipay/payment-intents",
        json={
            "payment_id": "pay_created_1",
            "route_path": "/tools/research",
            "buyer_address": "TRX_BUYER",
            "channel_id": "channel_123",
            "voucher_nonce": 3,
            "expires_at": 9_999_999_999,
            "request_deadline": request_deadline,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["payment_id"] == "pay_created_1"
    assert payload["payment_intent_id"] == "pay_created_1"
    assert payload["status"] == "authorized"
    assert payload["next_step"] == "execute_settlement"
    assert payload["safe_to_retry"] is True
    assert payload["amount_atomic"] == 250_000
    assert payload["seller_address"] == "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
    assert payload["contract_address"] == "0x1000000000000000000000000000000000000001"
    assert payload["token_address"] == "0x2000000000000000000000000000000000000002"


def test_create_payment_requires_auth_for_claim_script_backend() -> None:
    app = FastAPI()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://tron.local",
                seller_private_key="seller_pk",
                chain_id=31337,
                executor_backend="claim_script",
            ),
            routes=[
                MerchantRoute(
                    path="/tools/research",
                    method="POST",
                    price_atomic=250_000,
                    description="Paid research route",
                )
            ],
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/_aimipay/payments",
        json={
            "payment_id": "pay_missing_auth",
            "route_path": "/tools/research",
            "buyer_address": "TRX_BUYER",
            "channel_id": "channel_123",
            "voucher_nonce": 3,
            "expires_at": 9_999_999_999,
            "request_deadline": int(time.time()) + 300,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "missing_buyer_authorization"
    assert response.json()["detail"]["error"]["retryable"] is False


def test_create_payment_reuses_existing_record_for_same_idempotency_key() -> None:
    client, _ = _build_app()
    payload = {
        "idempotency_key": "req_123",
        "route_path": "/tools/research",
        "buyer_address": "TRX_BUYER",
        "channel_id": "channel_123",
        "voucher_nonce": 3,
        "expires_at": 9_999_999_999,
        "request_deadline": int(time.time()) + 300,
    }

    first = client.post("/_aimipay/payment-intents", json=payload)
    second = client.post("/_aimipay/payment-intents", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["payment_id"] == second.json()["payment_id"]


def test_create_payment_rejects_conflicting_idempotency_key() -> None:
    client, _ = _build_app()
    first = client.post(
        "/_aimipay/payment-intents",
        json={
            "idempotency_key": "req_conflict",
            "route_path": "/tools/research",
            "buyer_address": "TRX_BUYER",
            "channel_id": "channel_123",
            "voucher_nonce": 3,
            "expires_at": 9_999_999_999,
            "request_deadline": int(time.time()) + 300,
        },
    )
    second = client.post(
        "/_aimipay/payment-intents",
        json={
            "idempotency_key": "req_conflict",
            "route_path": "/tools/research",
            "buyer_address": "TRX_BUYER",
            "channel_id": "channel_999",
            "voucher_nonce": 4,
            "expires_at": 9_999_999_999,
            "request_deadline": int(time.time()) + 300,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"]["error"]["code"] == "idempotency_conflict"


def test_create_payment_rejects_expired_request_deadline() -> None:
    client, _ = _build_app()

    response = client.post(
        "/_aimipay/payment-intents",
        json={
            "route_path": "/tools/research",
            "buyer_address": "TRX_BUYER",
            "channel_id": "channel_123",
            "voucher_nonce": 3,
            "expires_at": 9_999_999_999,
            "request_deadline": int(time.time()) - 1,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "request_deadline_expired"


def test_recover_payments_can_query_by_idempotency_key_and_channel_id() -> None:
    client, _ = _build_app()
    response = client.post(
        "/_aimipay/payment-intents",
        json={
            "payment_id": "pay_recover_1",
            "idempotency_key": "idem_recover_1",
            "route_path": "/tools/research",
            "buyer_address": "TRX_BUYER",
            "channel_id": "channel_recover_1",
            "voucher_nonce": 1,
            "expires_at": 9_999_999_999,
            "request_deadline": int(time.time()) + 300,
        },
    )

    assert response.status_code == 200

    by_idem = client.get("/_aimipay/payments/recover", params={"idempotency_key": "idem_recover_1"})
    by_channel = client.get("/_aimipay/payments/recover", params={"channel_id": "channel_recover_1"})

    assert by_idem.status_code == 200
    assert by_idem.json()["count"] == 1
    assert by_idem.json()["payments"][0]["payment_id"] == "pay_recover_1"
    assert by_channel.status_code == 200
    assert by_channel.json()["payments"][0]["payment_id"] == "pay_recover_1"


def test_pending_payments_lists_authorized_records() -> None:
    client, _ = _build_app()
    create_response = client.post(
        "/_aimipay/payment-intents",
        json={
            "payment_id": "pay_pending_lifecycle",
            "route_path": "/tools/research",
            "buyer_address": "TRX_BUYER",
            "channel_id": "channel_pending_1",
            "voucher_nonce": 2,
            "expires_at": 9_999_999_999,
            "request_deadline": int(time.time()) + 300,
        },
    )

    assert create_response.status_code == 200

    pending_response = client.get("/_aimipay/payments/pending")

    assert pending_response.status_code == 200
    payload = pending_response.json()
    assert payload["count"] >= 1
    assert any(item["payment_id"] == "pay_pending_lifecycle" for item in payload["payments"])


def test_settlement_execute_requires_service() -> None:
    client, _ = _build_app()

    response = client.post("/_aimipay/settlements/execute", json={})

    assert response.status_code == 503
    assert response.json()["detail"]["error"]["code"] == "settlement_not_configured"


def test_settlement_execute_runs_for_target_payment() -> None:
    app = FastAPI()

    class FakeSettlementService:
        def __init__(self) -> None:
            self.executed_payment_id = None
            self.reconciled_payment_id = None

        def execute_payment(self, payment_id: str):
            self.executed_payment_id = payment_id
            return PaymentRecord(
                payment_id=payment_id,
                route_path="/tools/research",
                amount_atomic=250_000,
                status="submitted",
                tx_id="trx_claim_123",
                buyer_address="TRX_BUYER",
                seller_address="TRX_SELLER",
                channel_id="channel_123",
                contract_address="TRX_CONTRACT",
                token_address="TRX_USDT",
                voucher_nonce=9,
                expires_at=9_999_999_999,
                request_deadline=1_700_000_000,
            )

        def execute_pending(self):
            return [
                TronSettlementExecution(
                    tx_id="unused",
                    channel_id="unused",
                    buyer_address="unused",
                    seller_address="unused",
                    token_address="unused",
                    amount_atomic=0,
                    voucher_nonce=0,
                    request_deadline=0,
                    request_digest="unused",
                )
            ]

        def reconcile_payment(self, payment_id: str):
            self.reconciled_payment_id = payment_id
            return PaymentRecord(
                payment_id=payment_id,
                route_path="/tools/research",
                amount_atomic=250_000,
                status="settled",
                tx_id="trx_claim_123",
                buyer_address="TRX_BUYER",
                seller_address="TRX_SELLER",
                channel_id="channel_123",
                contract_address="TRX_CONTRACT",
                token_address="TRX_USDT",
                voucher_nonce=9,
                expires_at=9_999_999_999,
                request_deadline=1_700_000_000,
                confirmation_status="confirmed",
                settled_at=int(time.time()),
            )

    settlement_service = FakeSettlementService()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
        ),
        settlement_service=settlement_service,
    )
    client = TestClient(app)

    response = client.post("/_aimipay/settlements/execute", json={"payment_id": "pay_123"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["executed_count"] == 1
    assert payload["payments"][0]["payment_id"] == "pay_123"
    assert payload["payments"][0]["status"] == "submitted"
    assert payload["payments"][0]["tx_id"] == "trx_claim_123"
    assert settlement_service.executed_payment_id == "pay_123"

    reconcile_response = client.post("/_aimipay/settlements/reconcile", json={"payment_id": "pay_123"})

    assert reconcile_response.status_code == 200
    reconcile_payload = reconcile_response.json()
    assert reconcile_payload["reconciled_count"] == 1
    assert reconcile_payload["payments"][0]["status"] == "settled"
    assert settlement_service.reconciled_payment_id == "pay_123"


def test_install_gateway_auto_wires_default_settlement_service(monkeypatch) -> None:
    payment_store_seen = None
    settlement_config_seen = None

    class FakeSettlementService:
        def execute_payment(self, payment_id: str):
            raise AssertionError("not used in this test")

        def execute_pending(self):
            return []

    def fake_builder(*, payment_store, config):
        nonlocal payment_store_seen, settlement_config_seen
        payment_store_seen = payment_store
        settlement_config_seen = config
        return FakeSettlementService()

    monkeypatch.setattr(gateway_module, "build_default_tron_settlement_service", fake_builder)

    app = FastAPI()
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://tron.local",
                seller_private_key="seller_pk",
                chain_id=728126428,
            ),
        ),
    )

    assert runtime.settlement_service.__class__.__name__ == "FakeSettlementService"
    assert payment_store_seen is runtime.payment_store
    assert settlement_config_seen.repository_root == "e:/trade/aimicropay-tron"
    assert settlement_config_seen.full_host == "http://tron.local"
    assert settlement_config_seen.chain_id == 728126428
    assert settlement_config_seen.executor_backend == "claim_script"


def test_auto_wired_settlement_execute_updates_payment_status(monkeypatch) -> None:
    class FakeExecutor:
        def execute(self, plan):
            return TronSettlementExecution(
                tx_id="trx_claim_789",
                channel_id=plan.channel_id,
                buyer_address=plan.buyer_address,
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                amount_atomic=plan.amount_atomic,
                voucher_nonce=plan.voucher_nonce,
                request_deadline=plan.request_deadline,
                request_digest="digest_789",
            )

    class FakeConfirmer:
        def confirm(self, *, full_host: str, tx_id: str):
            return settlement_module.TronSettlementConfirmation(
                tx_id=tx_id,
                status="pending",
                confirmed=False,
            )

    monkeypatch.setattr(
        settlement_module,
        "build_default_tron_settlement_executor",
        lambda **kwargs: FakeExecutor(),
    )
    monkeypatch.setattr(
        settlement_module,
        "build_default_tron_settlement_confirmer",
        lambda **kwargs: FakeConfirmer(),
    )

    app = FastAPI()
    client = TestClient(app)
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://tron.local",
                seller_private_key="seller_pk",
                chain_id=728126428,
            ),
        ),
    )
    future_deadline = int(time.time()) + 300
    runtime.record_payment(
        PaymentRecord(
            payment_id="pay_pending_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_123",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=12,
            expires_at=9_999_999_999,
            request_deadline=future_deadline,
            request_method="POST",
            request_path="/tools/research",
            request_body='{"topic":"tron"}',
            status="pending",
        )
    )

    execute_response = client.post("/_aimipay/settlements/execute", json={})

    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload["executed_count"] == 1
    assert execute_payload["payments"][0]["payment_id"] == "pay_pending_1"
    assert execute_payload["payments"][0]["status"] == "submitted"
    assert execute_payload["payments"][0]["tx_id"] == "trx_claim_789"

    status_response = client.get("/_aimipay/payments/pay_pending_1")

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["payment_id"] == "pay_pending_1"
    assert status_payload["status"] == "submitted"
    assert status_payload["tx_id"] == "trx_claim_789"


def test_gateway_local_smoke_settlement_requires_explicit_reconcile_for_finality() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    if not (repository_root / "node_modules" / "hardhat").exists():
        pytest.skip("local hardhat dependencies are not installed")

    app = FastAPI()
    client = TestClient(app)
    runtime = install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            settlement=GatewaySettlementConfig(
                repository_root=str(repository_root),
                full_host="http://tron.local",
                seller_private_key="seller_pk",
                chain_id=31337,
                executor_backend="local_smoke",
            ),
        ),
    )
    future_deadline = int(time.time()) + 300
    create_response = client.post(
        "/_aimipay/payments",
        json={
            "payment_id": "pay_gateway_local_smoke",
            "route_path": "/tools/research",
            "amount_atomic": 250_000,
            "buyer_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            "channel_id": "0xplaceholder",
            "voucher_nonce": 1,
            "expires_at": 9_999_999_999,
            "request_deadline": future_deadline,
            "request_method": "POST",
            "request_path": "/tools/research",
            "request_body": '{"topic":"tron"}',
        },
    )

    assert create_response.status_code == 200

    execute_response = client.post("/_aimipay/settlements/execute", json={"payment_id": "pay_gateway_local_smoke"})

    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload["executed_count"] == 1
    assert execute_payload["payments"][0]["payment_id"] == "pay_gateway_local_smoke"
    assert execute_payload["payments"][0]["status"] == "submitted"
    assert execute_payload["payments"][0]["tx_id"] is not None

    status_response = client.get("/_aimipay/payments/pay_gateway_local_smoke")

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["payment_id"] == "pay_gateway_local_smoke"
    assert status_payload["status"] == "submitted"
    assert status_payload["tx_id"] is not None

    reconcile_response = client.post("/_aimipay/settlements/reconcile", json={"payment_id": "pay_gateway_local_smoke"})

    assert reconcile_response.status_code == 200
    reconcile_payload = reconcile_response.json()
    assert reconcile_payload["payments"][0]["status"] == "settled"
    assert reconcile_payload["payments"][0]["confirmation_status"] == "confirmed"


def test_install_sellable_capability_publishes_routes_and_plans() -> None:
    app = FastAPI()
    runtime = install_sellable_capability(
        app,
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
    )
    runtime.publish_usage_route(
        MerchantRoute(
            path="/tools/research",
            method="POST",
            price_atomic=250_000,
            capability_id="research-web-search",
            capability_type="web_search",
            pricing_model="fixed_per_call",
            usage_unit="request",
            delivery_mode="sync",
        )
    )
    runtime.publish_plan(
        MerchantPlan(
            plan_id="pro-monthly",
            name="Pro Monthly",
            amount_atomic=9_900_000,
            subscribe_path="/billing/subscribe",
        )
    )
    client = TestClient(app)

    response = client.get("/.well-known/aimipay.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["routes"][0]["capability_id"] == "research-web-search"
    assert payload["plans"][0]["plan_id"] == "pro-monthly"


def test_install_sellable_capability_publish_api_and_mcp_tool() -> None:
    app = FastAPI()
    runtime = install_sellable_capability(
        app,
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
    )
    runtime.publish_api(
        path="/tools/research",
        price_atomic=250_000,
        capability_type="web_search",
        description="Paid research API",
        auth_requirements=["request_digest", "buyer_signature"],
        budget_hint=CapabilityBudgetHint(
            typical_units=3,
            min_units=1,
            suggested_prepaid_atomic=750_000,
            notes="Typical coding task needs 3 paid searches",
        ),
    )
    runtime.publish_mcp_tool(
        path="/mcp/browser.search",
        price_atomic=150_000,
        description="Paid MCP browser search tool",
    )
    client = TestClient(app)

    response = client.get("/.well-known/aimipay.json")

    assert response.status_code == 200
    payload = response.json()
    routes = payload["routes"]
    assert routes[0]["capability_type"] == "web_search"
    assert "api" in routes[0]["capability_tags"]
    assert routes[0]["budget_hint"]["suggested_prepaid_atomic"] == 750_000
    assert routes[1]["capability_type"] == "mcp_tool"
    assert routes[1]["usage_unit"] == "tool_call"
    assert "mcp" in routes[1]["capability_tags"]
    assert routes[1]["capability_id"] == "mcp_tool-mcp-browser-search"


def test_paid_api_returns_http402_payment_requirements_until_paid() -> None:
    app = FastAPI()
    runtime = install_sellable_capability(
        app,
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
        chain_id=31337,
    )

    @runtime.paid_api(
        path="/tools/research",
        price_atomic=250_000,
        capability_type="web_search",
        capability_id="research-web-search",
        description="Paid research API",
    )
    def research_tool(body: dict) -> dict:
        return {"ok": True, "query": body.get("query")}

    client = TestClient(app)

    response = client.post("/tools/research", json={"query": "agent payments"})

    assert response.status_code == 402
    assert response.headers["payment-required"] == "true"
    payload = response.json()
    assert payload["schema_version"] == "aimipay.http402.v1"
    assert payload["kind"] == "payment_required"
    assert payload["x402_compat"]["request_header"] == "X-PAYMENT"
    requirement = payload["accepts"][0]
    assert requirement["scheme"] == "aimipay-tron-v1"
    assert requirement["chain"] == "tron"
    assert requirement["chain_id"] == 31337
    assert requirement["asset"] == "TRX_USDT"
    assert requirement["pay_to"] == "TRX_SELLER"
    assert requirement["amount_atomic"] == 250_000
    assert requirement["resource"].endswith("/tools/research")
    assert requirement["capability_id"] == "research-web-search"
    assert requirement["extra"]["payment_intents_url"].endswith("/_aimipay/payment-intents")
    assert payload["next_actions"][0]["tool"] == "aimipay.quote_budget"


def test_paid_api_rejects_unsettled_payment_and_suggests_finalize() -> None:
    app = FastAPI()
    runtime = install_sellable_capability(
        app,
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
    )

    @runtime.paid_api(path="/tools/research", price_atomic=250_000, capability_type="web_search")
    def research_tool() -> dict:
        return {"ok": True}

    runtime.gateway.record_payment(
        PaymentRecord(
            payment_id="pay_pending",
            amount_atomic=250_000,
            status="submitted",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            route_path="/tools/research",
        )
    )
    client = TestClient(app)

    response = client.post("/tools/research", headers={"X-AIMIPAY-PAYMENT-ID": "pay_pending"})

    assert response.status_code == 402
    payload = response.json()
    assert payload["error"] == "payment_not_settled"
    assert payload["payment_id"] == "pay_pending"
    assert payload["payment_status"] == "submitted"
    assert payload["next_actions"][0]["tool"] == "aimipay.finalize_payment"


def test_paid_api_allows_settled_payment_with_x_payment_header() -> None:
    app = FastAPI()
    runtime = install_sellable_capability(
        app,
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
    )

    @runtime.paid_api(path="/tools/research", price_atomic=250_000, capability_type="web_search")
    def research_tool(body: dict) -> dict:
        return {"ok": True, "query": body["query"]}

    runtime.gateway.record_payment(
        PaymentRecord(
            payment_id="pay_settled",
            amount_atomic=250_000,
            status="settled",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            route_path="/tools/research",
        )
    )
    client = TestClient(app)

    response = client.post("/tools/research", headers={"X-PAYMENT": '{"payment_id":"pay_settled"}'}, json={"query": "x402"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "query": "x402"}
    payment_response = response.headers["x-payment-response"]
    assert '"schema_version":"aimipay.http402-payment-response.v1"' in payment_response
    assert '"payment_id":"pay_settled"' in payment_response
    assert '"kind":"payment_receipt"' in payment_response


def test_paid_api_rejects_payment_bound_to_different_resource() -> None:
    app = FastAPI()
    runtime = install_sellable_capability(
        app,
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
    )

    @runtime.paid_api(path="/tools/research", price_atomic=250_000, capability_type="web_search")
    def research_tool() -> dict:
        return {"ok": True}

    runtime.gateway.record_payment(
        PaymentRecord(
            payment_id="pay_other",
            amount_atomic=250_000,
            status="settled",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            route_path="/tools/other",
            request_path="/tools/other",
        )
    )
    client = TestClient(app)

    response = client.post("/tools/research", headers={"X-AIMIPAY-PAYMENT-ID": "pay_other"})

    assert response.status_code == 402
    payload = response.json()
    assert payload["error"] == "payment_resource_mismatch"
    assert payload["payment_id"] == "pay_other"


def test_paid_api_rejects_payment_below_required_amount() -> None:
    app = FastAPI()
    runtime = install_sellable_capability(
        app,
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
    )

    @runtime.paid_api(path="/tools/research", price_atomic=250_000, capability_type="web_search")
    def research_tool() -> dict:
        return {"ok": True}

    runtime.gateway.record_payment(
        PaymentRecord(
            payment_id="pay_too_small",
            amount_atomic=100_000,
            status="settled",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            route_path="/tools/research",
            request_path="/tools/research",
        )
    )
    client = TestClient(app)

    response = client.post("/tools/research", headers={"X-AIMIPAY-PAYMENT-ID": "pay_too_small"})

    assert response.status_code == 402
    payload = response.json()
    assert payload["error"] == "payment_amount_insufficient"
    assert payload["accepts"][0]["amount_atomic"] == 250_000

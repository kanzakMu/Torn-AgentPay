import os
from pathlib import Path
import time

import pytest
import seller.gateway as gateway_module
import seller.settlement as settlement_module
from fastapi import FastAPI
from fastapi.testclient import TestClient

from seller import GatewaySettlementConfig, TronSettlementExecution, install_sellable_capability
from seller.gateway import GatewayConfig, install_gateway
from shared import CapabilityBudgetHint, MerchantPlan, MerchantRoute, PaymentRecord


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

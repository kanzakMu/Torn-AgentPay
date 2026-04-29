import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from buyer import (
    AgentPaymentsRuntime,
    AimiPayAgentAdapter,
    BuyerBudgetPolicy,
    BuyerClient,
    BuyerMarket,
    MarketSelectionPolicy,
    BuyerWallet,
    OpenChannelExecution,
    TronProvisioner,
    install_agent_payments,
)
from buyer.provisioner import build_default_tron_provisioner
from seller import install_sellable_capability
from seller.gateway import GatewayConfig, GatewaySettlementConfig, install_gateway
from shared import CapabilityBudgetHint, MerchantRoute
from shared.protocol_native import channel_id_of

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _build_gateway_app(
    *,
    settlement_service=None,
    seller_address: str = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    contract_address: str = "0x1000000000000000000000000000000000000001",
    token_address: str = "0x2000000000000000000000000000000000000002",
    settlement: GatewaySettlementConfig | None = None,
    routes: list[MerchantRoute] | None = None,
) -> FastAPI:
    app = FastAPI()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address=seller_address,
            contract_address=contract_address,
            token_address=token_address,
            network="local-smoke",
            chain_id=31337,
            routes=routes
            or [
                MerchantRoute(
                    path="/tools/research",
                    method="POST",
                    price_atomic=250_000,
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
            settlement=settlement,
        ),
        settlement_service=settlement_service,
    )
    return app


class _FakeProvisioner:
    def provision(self, plan):
        buyer_address = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        return OpenChannelExecution(
            approve_tx_id="approve_1",
            open_tx_id="open_1",
            channel_id=channel_id_of(
                buyer_address=buyer_address,
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_salt=plan.channel_salt,
            ),
            buyer_address=buyer_address,
            seller_address=plan.seller_address,
            contract_address=plan.contract_address,
            token_address=plan.token_address,
            deposit_atomic=plan.deposit_atomic,
            expires_at=plan.expires_at,
            channel_salt=plan.channel_salt,
        )


class _SettlingService:
    def __init__(self) -> None:
        self.store = None

    def execute_payment(self, payment_id: str):
        record = self.store.get(payment_id)
        record.status = "submitted"
        record.tx_id = "tx_1"
        return self.store.upsert(record)

    def reconcile_payment(self, payment_id: str):
        record = self.store.get(payment_id)
        record.status = "settled"
        record.confirmation_status = "confirmed"
        record.tx_id = record.tx_id or "tx_1"
        return self.store.upsert(record)


def test_default_tron_provisioner_points_to_open_script() -> None:
    provisioner = build_default_tron_provisioner(repository_root=REPOSITORY_ROOT)
    assert provisioner.command == ("node", "scripts/open_channel_exec.js")
    assert Path(provisioner.cwd).resolve() == REPOSITORY_ROOT.resolve()


def test_tron_provisioner_executes_command_and_parses_json() -> None:
    provisioner = TronProvisioner(
        command=(
            sys.executable,
            "-c",
            (
                "import json; "
                "print(json.dumps({"
                "'approve_tx_id':'approve_1',"
                "'open_tx_id':'open_1',"
                "'buyer_address':'TRX_BUYER',"
                "'seller_address':'TRX_SELLER',"
                "'token_address':'TRX_USDT',"
                "'channel_id':'channel_1',"
                "'contract_address':'TRX_CONTRACT',"
                "'deposit_atomic':1000000,"
                "'expires_at':9999999999"
                "}))"
            ),
        ),
        cwd=str(REPOSITORY_ROOT),
    )
    result = provisioner.provision(
        plan=type(
            "Plan",
            (),
            {
                "to_dict": lambda self: {
                    "full_host": "http://tron.local",
                    "buyer_private_key": "buyer_pk",
                    "contract_address": "TRX_CONTRACT",
                    "seller_address": "TRX_SELLER",
                    "token_address": "TRX_USDT",
                    "deposit_atomic": 1_000_000,
                    "expires_at": 9999999999,
                }
            },
        )()
    )
    assert result.open_tx_id == "open_1"
    assert result.channel_id == "channel_1"


def test_buyer_client_handles_http402_paid_resource_end_to_end() -> None:
    service = _SettlingService()
    app = FastAPI()
    runtime = install_sellable_capability(
        app,
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        contract_address="0x1000000000000000000000000000000000000001",
        token_address="0x2000000000000000000000000000000000000002",
        chain_id=31337,
        settlement=GatewaySettlementConfig(
            repository_root=str(REPOSITORY_ROOT),
            full_host="http://tron.local",
            seller_private_key="seller_pk",
            chain_id=31337,
            executor_backend="local_smoke",
        ),
        settlement_service=service,
    )
    service.store = runtime.gateway.payment_store

    @runtime.paid_api(
        path="/tools/research",
        price_atomic=250_000,
        capability_type="web_search",
        capability_id="research-web-search",
    )
    def research_tool(body: dict) -> dict:
        return {"ok": True, "query": body["query"]}

    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="buyer_pk",
        ),
        provisioner=_FakeProvisioner(),
        http_client=http_client,
        repository_root=str(REPOSITORY_ROOT),
    )

    result = client.request_paid_resource(
        "/tools/research",
        json_body={"query": "x402"},
        budget_limit_atomic=300_000,
    )

    assert result["paid"] is True
    assert result["response"].status_code == 200
    assert result["response"].json() == {"ok": True, "query": "x402"}
    assert result["payment"]["status"] == "settled"
    assert result["payment_required"]["schema_version"] == "aimipay.http402.v1"
    assert result["payment_header"]["schema_version"] == "aimipay.payment-header.v1"
    assert result["payment_response"]["kind"] == "payment_receipt"
    assert result["payment_response"]["payment_id"] == result["payment"]["payment_id"]
    assert result["payment_response"]["route_path"] == "/tools/research"


def test_buyer_client_discovers_and_opens_channel() -> None:
    app = _build_gateway_app()
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def __init__(self) -> None:
            self.last_plan = None

        def provision(self, plan):
            self.last_plan = plan
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_1",
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    provisioner = FakeProvisioner()
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=provisioner,
        http_client=http_client,
    )

    manifest = client.fetch_manifest()
    assert manifest["primary_chain"]["chain"] == "tron"

    discovery = client.discover()
    assert discovery["chain"] == "tron"

    session = client.ensure_channel_for_route(route_path="/tools/research", method="POST")
    assert session["channel_id"] == "channel_1"
    assert session["contract_address"] == "0x1000000000000000000000000000000000000001"
    assert session["token_address"] == "0x2000000000000000000000000000000000000002"
    assert provisioner.last_plan.full_host == "http://tron.local"
    assert provisioner.last_plan.buyer_private_key == "buyer_pk"


def test_buyer_client_can_resolve_full_host_from_merchant_network() -> None:
    app = _build_gateway_app()
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def __init__(self) -> None:
            self.last_plan = None

        def provision(self, plan):
            self.last_plan = plan
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_1",
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    provisioner = FakeProvisioner()
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host=None,
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=provisioner,
        http_client=http_client,
    )

    session = client.ensure_channel_for_route(route_path="/tools/research", method="POST")

    assert session["channel_id"] == "channel_1"
    assert provisioner.last_plan.full_host == "http://127.0.0.1:9090"


def test_buyer_client_lists_capability_offers() -> None:
    app = _build_gateway_app()
    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
    )

    offers = client.list_capability_offers()

    assert len(offers) == 1
    offer = offers[0]
    assert offer["capability_id"] == "research-web-search"
    assert offer["capability_type"] == "web_search"
    assert offer["pricing_model"] == "fixed_per_call"
    assert offer["usage_unit"] == "request"
    assert offer["unit_price_atomic"] == 250_000
    assert offer["delivery_mode"] == "sync"
    assert offer["auth_requirements"] == ["request_digest", "buyer_signature"]
    assert offer["budget_hint"]["suggested_prepaid_atomic"] == 750_000
    assert offer["settlement_backend"] is None


def test_buyer_client_prefers_discover_chain_addresses_over_manifest() -> None:
    app = FastAPI()

    @app.get("/.well-known/aimipay.json")
    async def well_known() -> dict:
        return {
            "service_name": "Research Copilot",
            "service_description": "Pay-per-use research and market data",
            "primary_chain": {
                "chain": "tron",
                "chain_id": 31337,
                "settlement_backend": "claim_script",
                "seller_address": "TRX_SELLER_MANIFEST",
                "contract_address": "TRX_CONTRACT_MANIFEST",
                "asset_address": "TRX_USDT_MANIFEST",
            },
            "routes": [
                {
                    "path": "/tools/research",
                    "method": "POST",
                    "price_atomic": 250_000,
                    "capability_id": "research-web-search",
                    "capability_type": "web_search",
                }
            ],
            "plans": [],
            "endpoints": {
                "management": "http://merchant.test/_aimipay",
            },
        }

    @app.get("/_aimipay/discover")
    async def discover() -> dict:
        return {
            "seller": "TRX_SELLER_DISCOVER",
            "chain": "tron",
            "chain_id": 3448148188,
            "settlement_backend": "claim_script",
            "contract_address": "TRX_CONTRACT_DISCOVER",
            "token_address": "TRX_USDT_DISCOVER",
            "routes": [],
            "plans": [],
        }

    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
    )

    offer = client.list_capability_offers()[0]

    assert offer["chain_id"] == 3448148188
    assert offer["seller_address"] == "TRX_SELLER_DISCOVER"
    assert offer["contract_address"] == "TRX_CONTRACT_DISCOVER"
    assert offer["token_address"] == "TRX_USDT_DISCOVER"


def test_buyer_client_verifies_signed_manifest() -> None:
    seller_private_key = "0x59c6995e998f97a5a0044966f0945382d7f4a3f1f3f7e61a821a3d1d021b6d2d"
    seller_address = "TVaEiLLej394ZxVmHZXYg3HprssbpdcsmW"
    app = FastAPI()
    gateway_runtime = install_gateway(
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
    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
    )

    manifest = client.fetch_manifest()

    assert manifest["_attestation"]["seller_profile_signed"] is True
    assert manifest["_attestation"]["seller_profile_verified"] is True
    assert manifest["_attestation"]["manifest_signed"] is True
    assert manifest["_attestation"]["manifest_verified"] is True


def test_buyer_client_flags_tampered_signed_manifest() -> None:
    seller_private_key = "0x59c6995e998f97a5a0044966f0945382d7f4a3f1f3f7e61a821a3d1d021b6d2d"
    seller_address = "TVaEiLLej394ZxVmHZXYg3HprssbpdcsmW"
    app = FastAPI()
    gateway_runtime = install_gateway(
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

    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
    )

    manifest = gateway_runtime.manifest(base_url="http://merchant.test")
    manifest["service_description"] = "tampered"
    attestation = client.verify_manifest_attestation(manifest)

    assert attestation["manifest_signed"] is True
    assert attestation["manifest_verified"] is False
    assert "manifest_signature_invalid" in attestation["errors"]


def test_buyer_client_uses_discover_chain_id_when_manifest_omits_it(monkeypatch) -> None:
    app = _build_gateway_app(
        settlement=GatewaySettlementConfig(
            repository_root="e:/trade/aimicropay-tron",
            full_host="http://tron.local",
            seller_private_key="seller_pk",
            chain_id=31337,
            executor_backend="claim_script",
        ),
    )
    http_client = TestClient(app, base_url="http://merchant.test")

    original_fetch_manifest = BuyerClient.fetch_manifest

    def patched_fetch_manifest(self):
        payload = original_fetch_manifest(self)
        payload["primary_chain"]["chain_id"] = None
        payload["primary_chain"]["contract_address"] = "TRX_CONTRACT_MANIFEST"
        payload["primary_chain"]["asset_address"] = "TRX_USDT_MANIFEST"
        self._manifest_cache = payload
        return payload

    monkeypatch.setattr(BuyerClient, "fetch_manifest", patched_fetch_manifest)

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id=channel_id_of(
                    buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                    seller_address=plan.seller_address,
                    token_address=plan.token_address,
                ),
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    seen_args = {}

    def fake_voucher_builder(**kwargs):
        seen_args.update(kwargs)
        return type(
            "VoucherPayload",
            (),
            {
                "request_digest": "0xdigest_1",
                "voucher_digest": "0xvoucher_1",
                "buyer_signature": "0xsig_1",
            },
        )()

    monkeypatch.setattr("buyer.client.build_payment_voucher", fake_voucher_builder)

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        ),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    result = client.pay_route(
        route_path="/tools/research",
        method="POST",
        request_body='{"topic":"tron"}',
        auto_execute=False,
    )

    assert result["payment"]["request_digest"] == "0xdigest_1"
    assert seen_args["chain_id"] == 31337
    assert seen_args["contract_address"] == result["session"]["contract_address"]
    assert seen_args["token_address"] == result["session"]["token_address"]


def test_buyer_client_can_create_payment_intent_and_recover_it() -> None:
    app = _build_gateway_app()
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id=channel_id_of(
                    buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                    seller_address=plan.seller_address,
                    token_address=plan.token_address,
                ),
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        ),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    session = client.ensure_channel_for_route(route_path="/tools/research")
    payment = client.create_payment_intent(
        channel_session=session,
        route_path="/tools/research",
        request_body='{"topic":"tron"}',
        idempotency_key="idem_buyer_1",
    )
    recovered = client.recover_payment(idempotency_key="idem_buyer_1")
    pending = client.list_pending_payments()

    assert payment["status"] == "authorized"
    assert payment["next_step"] == "execute_settlement"
    assert recovered["count"] == 1
    assert recovered["payments"][0]["payment_id"] == payment["payment_id"]
    assert pending["count"] >= 1


def test_buyer_client_can_reconcile_submitted_payment() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_1",
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used")

        def reconcile_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "settled",
                    "confirmation_status": "confirmed",
                    "settled_at": 1_700_000_000,
                    "confirmed_at": 1_700_000_000,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

    settlement_service = FakeSettlementService()
    app = _build_gateway_app(settlement_service=settlement_service)
    settlement_service.runtime = app.state.aimipay_gateway
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id=channel_id_of(
                    buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                    seller_address=plan.seller_address,
                    token_address=plan.token_address,
                ),
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    session = client.ensure_channel_for_route(route_path="/tools/research")
    payment = client.create_payment_intent(
        channel_session=session,
        route_path="/tools/research",
        request_body='{"topic":"tron"}',
    )
    submitted = client.execute_payment(payment["payment_id"])
    settled = client.reconcile_payment(payment["payment_id"])

    assert submitted["status"] == "submitted"
    assert settled["status"] == "settled"
    assert settled["confirmation_status"] == "confirmed"


def test_buyer_client_can_finalize_payment_to_terminal_state() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_finalize_1",
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used")

        def reconcile_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            attempts = int(record.confirmation_attempts)
            if attempts == 0:
                updated = record.model_copy(
                    update={
                        "status": "submitted",
                        "confirmation_status": "pending",
                        "confirmation_attempts": 1,
                    }
                )
            else:
                updated = record.model_copy(
                    update={
                        "status": "settled",
                        "confirmation_status": "confirmed",
                        "confirmation_attempts": attempts + 1,
                        "settled_at": 1_700_000_001,
                        "confirmed_at": 1_700_000_001,
                    }
                )
            self.runtime.payment_store.upsert(updated)
            return updated

    settlement_service = FakeSettlementService()
    app = _build_gateway_app(settlement_service=settlement_service)
    settlement_service.runtime = app.state.aimipay_gateway
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id=channel_id_of(
                    buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                    seller_address=plan.seller_address,
                    token_address=plan.token_address,
                ),
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        ),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    session = client.ensure_channel_for_route(route_path="/tools/research")
    payment = client.create_payment_intent(
        channel_session=session,
        route_path="/tools/research",
        request_body='{"topic":"tron"}',
    )

    finalized = client.finalize_payment(payment["payment_id"], max_attempts=4)

    assert finalized["status"] == "settled"
    assert finalized["confirmation_status"] == "confirmed"


def test_buyer_client_supports_prepare_submit_confirm_purchase_flow() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_prepare_submit_confirm_1",
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used")

        def reconcile_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "settled",
                    "confirmation_status": "confirmed",
                    "confirmation_attempts": int(record.confirmation_attempts) + 1,
                    "settled_at": 1_700_000_001,
                    "confirmed_at": 1_700_000_001,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

    settlement_service = FakeSettlementService()
    app = _build_gateway_app(settlement_service=settlement_service)
    settlement_service.runtime = app.state.aimipay_gateway
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id=channel_id_of(
                    buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                    seller_address=plan.seller_address,
                    token_address=plan.token_address,
                ),
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        ),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    prepared = client.prepare_purchase(capability_id="research-web-search")
    submitted = client.submit_purchase(
        prepared_purchase=prepared,
        request_body='{"topic":"tron"}',
        auto_execute=False,
    )
    confirmed = client.confirm_purchase(submitted["payment"]["payment_id"])

    assert prepared["offer"]["capability_id"] == "research-web-search"
    assert submitted["payment"]["status"] == "authorized"
    assert confirmed["status"] == "settled"


def test_agent_adapter_returns_agent_friendly_lifecycle_shape() -> None:
    app = _build_gateway_app()
    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
    )
    adapter = AimiPayAgentAdapter(client)

    offers = adapter.list_offers()
    estimate = adapter.estimate_budget(capability_id="research-web-search")

    assert offers["schema_version"] == "aimipay.agent-protocol.v1"
    assert offers["kind"] == "capability_catalog"
    assert offers["next_step"] == "quote_budget"
    assert len(offers["offers"]) == 1
    assert estimate["schema_version"] == "aimipay.agent-protocol.v1"
    assert estimate["kind"] == "budget_quote"
    assert estimate["estimated_cost_atomic"] == 750_000
    assert estimate["auto_decision"]["action"] == "buy_now"
    assert estimate["next_step"] == "prepare_purchase"


def test_buyer_client_estimates_capability_budget_from_budget_hint() -> None:
    app = _build_gateway_app()
    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
    )

    estimate = client.estimate_capability_budget(capability_id="research-web-search")

    assert estimate["budget"]["capability_id"] == "research-web-search"
    assert estimate["budget"]["units"] == 3
    assert estimate["budget"]["unit_amount_atomic"] == 250_000
    assert estimate["budget"]["estimated_total_atomic"] == 750_000
    assert estimate["budget"]["suggested_prepaid_atomic"] == 750_000
    assert estimate["decision"]["action"] == "buy_now"
    assert estimate["decision"]["route_path"] == "/tools/research"


def test_buyer_client_marks_budget_that_exceeds_limit_as_needs_approval() -> None:
    app = _build_gateway_app()
    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
    )

    estimate = client.estimate_capability_budget(
        capability_id="research-web-search",
        expected_units=4,
        budget_limit_atomic=900_000,
    )

    assert estimate["budget"]["estimated_total_atomic"] == 1_000_000
    assert estimate["decision"]["action"] == "needs_approval"
    assert estimate["decision"]["reason"] == "estimated cost exceeds budget limit"


def test_buyer_budget_policy_can_block_or_require_approval() -> None:
    app = _build_gateway_app()
    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
        budget_policy=BuyerBudgetPolicy(
            policy_name="strict-agent-wallet",
            per_purchase_limit_atomic=500_000,
            daily_limit_atomic=900_000,
        ),
        spent_today_atomic=600_000,
    )

    estimate = client.estimate_capability_budget(capability_id="research-web-search")

    assert estimate["decision"]["action"] == "needs_approval"
    policy = estimate["decision"]["budget_policy"]
    assert policy["schema_version"] == "aimipay.buyer-budget-policy-evaluation.v1"
    assert {item["code"] for item in policy["violations"]} == {
        "per_purchase_limit_exceeded",
        "daily_limit_exceeded",
    }

    client.budget_policy = BuyerBudgetPolicy(
        policy_name="blocked-seller",
        blocked_sellers={estimate["decision"]["seller_address"]},
    )
    blocked = client.estimate_capability_budget(capability_id="research-web-search")

    assert blocked["decision"]["action"] == "blocked"
    assert blocked["decision"]["budget_policy"]["violations"][0]["code"] == "seller_blocked"


def test_buyer_client_buy_capability_runs_purchase_flow() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_1",
                    "error_code": None,
                    "error_message": None,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used in this test")

    settlement_service = FakeSettlementService()
    app = _build_gateway_app(settlement_service=settlement_service)
    settlement_service.runtime = app.state.aimipay_gateway
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id=channel_id_of(
                    buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                    seller_address=plan.seller_address,
                    token_address=plan.token_address,
                ),
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="buyer_pk",
        ),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    result = client.buy_capability(
        capability_id="research-web-search",
        request_body='{"topic":"tron"}',
    )

    assert result["decision"]["action"] == "buy_now"
    assert result["budget"]["estimated_total_atomic"] == 750_000
    assert result["session"]["channel_id"].startswith("0x")
    assert result["session"]["deposit_atomic"] == 750_000
    assert result["payment"]["status"] == "submitted"
    assert result["payment"]["amount_atomic"] == 750_000
    assert result["payment"]["tx_id"] == "trx_claim_1"


def test_buyer_client_buy_capability_requires_approval_when_budget_exceeded() -> None:
    app = _build_gateway_app()
    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
    )

    with pytest.raises(ValueError, match="estimated cost exceeds budget limit"):
        client.buy_capability(
            capability_id="research-web-search",
            expected_units=4,
            budget_limit_atomic=900_000,
        )


def test_buyer_client_selects_lowest_cost_offer_for_capability_type() -> None:
    app = _build_gateway_app(
        routes=[
            MerchantRoute(
                path="/tools/research",
                method="POST",
                price_atomic=250_000,
                capability_id="research-web-search",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=750_000),
            ),
            MerchantRoute(
                path="/tools/search-lite",
                method="POST",
                price_atomic=100_000,
                capability_id="research-web-search-lite",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=300_000),
            ),
        ]
    )
    http_client = TestClient(app, base_url="http://merchant.test")
    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_client=http_client,
    )

    selection = client.select_capability_offer(capability_type="web_search")

    assert selection["selected"]["offer"]["capability_id"] == "research-web-search-lite"
    assert selection["selected"]["budget"]["estimated_total_atomic"] == 300_000
    assert len(selection["candidates"]) == 2


def test_buyer_client_pay_for_task_uses_selected_offer() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_2",
                    "error_code": None,
                    "error_message": None,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used in this test")

    settlement_service = FakeSettlementService()
    app = _build_gateway_app(
        settlement_service=settlement_service,
        routes=[
            MerchantRoute(
                path="/tools/research",
                method="POST",
                price_atomic=250_000,
                capability_id="research-web-search",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=750_000),
            ),
            MerchantRoute(
                path="/tools/search-lite",
                method="POST",
                price_atomic=100_000,
                capability_id="research-web-search-lite",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=300_000),
            ),
        ],
    )
    settlement_service.runtime = app.state.aimipay_gateway
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_1",
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    result = client.pay_for_task(
        task_context="Need a cheap web search for coding research",
        capability_type="web_search",
        request_body='{"topic":"tron"}',
    )

    assert result["selection"]["selected"]["offer"]["capability_id"] == "research-web-search-lite"
    assert result["offer"]["capability_id"] == "research-web-search-lite"
    assert result["budget"]["estimated_total_atomic"] == 300_000
    assert result["session"]["route_path"] == "/tools/search-lite"
    assert result["payment"]["amount_atomic"] == 300_000
    assert result["payment"]["tx_id"] == "trx_claim_2"


def test_buyer_market_selects_lowest_cost_offer_across_merchants() -> None:
    app_a = _build_gateway_app(
        routes=[
            MerchantRoute(
                path="/tools/research",
                method="POST",
                price_atomic=250_000,
                capability_id="research-web-search",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=750_000),
            )
        ]
    )
    app_b = _build_gateway_app(
        seller_address="TRX_SELLER_B",
        contract_address="TRX_CONTRACT_B",
        token_address="TRX_USDT_B",
        routes=[
            MerchantRoute(
                path="/tools/search-lite",
                method="POST",
                price_atomic=100_000,
                capability_id="research-web-search-lite",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=300_000),
            )
        ],
    )
    market = BuyerMarket(
        merchant_base_urls=["http://merchant-a.test", "http://merchant-b.test"],
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_clients={
            "http://merchant-a.test": TestClient(app_a, base_url="http://merchant-a.test"),
            "http://merchant-b.test": TestClient(app_b, base_url="http://merchant-b.test"),
        },
    )

    selection = market.select_market_capability_offer(capability_type="web_search")

    assert selection["selected"]["offer"]["merchant_base_url"] == "http://merchant-b.test"
    assert selection["selected"]["offer"]["capability_id"] == "research-web-search-lite"
    assert selection["selected"]["budget"]["estimated_total_atomic"] == 300_000
    assert selection["selected"]["decision"]["score"] is not None
    assert "price" in selection["selected"]["decision"]["score_breakdown"]
    assert len(selection["candidates"]) == 2


def test_buyer_market_prefers_claim_script_backend_when_prices_are_similar() -> None:
    app_a = _build_gateway_app(
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
                price_atomic=120_000,
                capability_id="research-web-search",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                auth_requirements=["request_digest", "buyer_signature"],
                budget_hint=CapabilityBudgetHint(typical_units=2, suggested_prepaid_atomic=240_000),
            )
        ],
    )
    app_b = _build_gateway_app(
        seller_address="TRX_SELLER_B",
        contract_address="TRX_CONTRACT_B",
        token_address="TRX_USDT_B",
        settlement=GatewaySettlementConfig(
            repository_root="e:/trade/aimicropay-tron",
            full_host="http://tron.local",
            seller_private_key="seller_pk",
            chain_id=31337,
            executor_backend="local_smoke",
        ),
        routes=[
            MerchantRoute(
                path="/tools/search-lite",
                method="POST",
                price_atomic=100_000,
                capability_id="research-web-search-lite",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=2, suggested_prepaid_atomic=200_000),
            )
        ],
    )
    market = BuyerMarket(
        merchant_base_urls=["http://merchant-a.test", "http://merchant-b.test"],
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_clients={
            "http://merchant-a.test": TestClient(app_a, base_url="http://merchant-a.test"),
            "http://merchant-b.test": TestClient(app_b, base_url="http://merchant-b.test"),
        },
    )

    selection = market.select_market_capability_offer(
        capability_type="web_search",
        expected_units=2,
    )

    assert selection["selected"]["offer"]["merchant_base_url"] == "http://merchant-a.test"
    assert selection["selected"]["decision"]["score_breakdown"]["settlement_backend"] == 20.0
    assert selection["selected"]["decision"]["score"] >= selection["candidates"][1]["decision"]["score"]


def test_buyer_market_selection_policy_can_prefer_lower_auth_complexity() -> None:
    app_a = _build_gateway_app(
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
                price_atomic=100_000,
                capability_id="research-web-search",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                auth_requirements=["request_digest", "buyer_signature"],
                budget_hint=CapabilityBudgetHint(typical_units=2, suggested_prepaid_atomic=200_000),
            )
        ],
    )
    app_b = _build_gateway_app(
        seller_address="TRX_SELLER_B",
        contract_address="TRX_CONTRACT_B",
        token_address="TRX_USDT_B",
        settlement=GatewaySettlementConfig(
            repository_root="e:/trade/aimicropay-tron",
            full_host="http://tron.local",
            seller_private_key="seller_pk",
            chain_id=31337,
            executor_backend="local_smoke",
        ),
        routes=[
            MerchantRoute(
                path="/tools/search-lite",
                method="POST",
                price_atomic=120_000,
                capability_id="research-web-search-lite",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                auth_requirements=[],
                budget_hint=CapabilityBudgetHint(typical_units=2, suggested_prepaid_atomic=240_000),
            )
        ],
    )
    market = BuyerMarket(
        merchant_base_urls=["http://merchant-a.test", "http://merchant-b.test"],
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        http_clients={
            "http://merchant-a.test": TestClient(app_a, base_url="http://merchant-a.test"),
            "http://merchant-b.test": TestClient(app_b, base_url="http://merchant-b.test"),
        },
        selection_policy=MarketSelectionPolicy(
            policy_name="low-auth-preferred",
            price_weight=0.1,
            settlement_backend_weight=0.2,
            delivery_mode_weight=0.5,
            auth_complexity_weight=5.0,
        ),
    )

    selection = market.select_market_capability_offer(
        capability_type="web_search",
        expected_units=2,
    )

    assert selection["selected"]["offer"]["merchant_base_url"] == "http://merchant-b.test"
    assert selection["selected"]["decision"]["selection_policy"] == "low-auth-preferred"
    assert selection["selected"]["decision"]["score_breakdown"]["auth_complexity"] > 10.0


def test_buyer_market_pay_for_task_uses_selected_merchant() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_market",
                    "error_code": None,
                    "error_message": None,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used in this test")

    settlement_service_a = FakeSettlementService()
    settlement_service_b = FakeSettlementService()
    app_a = _build_gateway_app(
        settlement_service=settlement_service_a,
        routes=[
            MerchantRoute(
                path="/tools/research",
                method="POST",
                price_atomic=250_000,
                capability_id="research-web-search",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=750_000),
            )
        ],
    )
    app_b = _build_gateway_app(
        settlement_service=settlement_service_b,
        seller_address="TRX_SELLER_B",
        contract_address="TRX_CONTRACT_B",
        token_address="TRX_USDT_B",
        routes=[
            MerchantRoute(
                path="/tools/search-lite",
                method="POST",
                price_atomic=100_000,
                capability_id="research-web-search-lite",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=300_000),
            )
        ],
    )
    settlement_service_a.runtime = app_a.state.aimipay_gateway
    settlement_service_b.runtime = app_b.state.aimipay_gateway

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_market",
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    market = BuyerMarket(
        merchant_base_urls=["http://merchant-a.test", "http://merchant-b.test"],
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=FakeProvisioner(),
        http_clients={
            "http://merchant-a.test": TestClient(app_a, base_url="http://merchant-a.test"),
            "http://merchant-b.test": TestClient(app_b, base_url="http://merchant-b.test"),
        },
    )

    result = market.pay_for_task(
        task_context="Need a cheap web search for coding research",
        capability_type="web_search",
        request_body='{"topic":"tron"}',
    )

    assert result["selection"]["selected"]["offer"]["merchant_base_url"] == "http://merchant-b.test"
    assert result["offer"]["capability_id"] == "research-web-search-lite"
    assert result["budget"]["estimated_total_atomic"] == 300_000
    assert result["payment"]["amount_atomic"] == 300_000
    assert result["payment"]["tx_id"] == "trx_claim_market"


def test_install_agent_payments_supports_market_task_purchase() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_runtime",
                    "error_code": None,
                    "error_message": None,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used in this test")

    settlement_service_a = FakeSettlementService()
    settlement_service_b = FakeSettlementService()
    app_a = _build_gateway_app(
        settlement_service=settlement_service_a,
        routes=[
            MerchantRoute(
                path="/tools/research",
                method="POST",
                price_atomic=250_000,
                capability_id="research-web-search",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=750_000),
            )
        ],
    )
    app_b = _build_gateway_app(
        settlement_service=settlement_service_b,
        seller_address="TRX_SELLER_B",
        contract_address="TRX_CONTRACT_B",
        token_address="TRX_USDT_B",
        routes=[
            MerchantRoute(
                path="/tools/search-lite",
                method="POST",
                price_atomic=100_000,
                capability_id="research-web-search-lite",
                capability_type="web_search",
                pricing_model="fixed_per_call",
                usage_unit="request",
                delivery_mode="sync",
                budget_hint=CapabilityBudgetHint(typical_units=3, suggested_prepaid_atomic=300_000),
            )
        ],
    )
    settlement_service_a.runtime = app_a.state.aimipay_gateway
    settlement_service_b.runtime = app_b.state.aimipay_gateway

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_runtime",
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    runtime = install_agent_payments(
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=FakeProvisioner(),
        merchant_base_urls=["http://merchant-a.test", "http://merchant-b.test"],
        http_clients={
            "http://merchant-a.test": TestClient(app_a, base_url="http://merchant-a.test"),
            "http://merchant-b.test": TestClient(app_b, base_url="http://merchant-b.test"),
        },
    )

    assert isinstance(runtime, AgentPaymentsRuntime)

    result = runtime.pay_for_task(
        task_context="Need the cheapest web search provider",
        capability_type="web_search",
        request_body='{"topic":"tron"}',
    )

    assert result["selection"]["selected"]["offer"]["merchant_base_url"] == "http://merchant-b.test"
    assert result["payment"]["tx_id"] == "trx_claim_runtime"


def test_install_agent_payments_can_work_without_full_host_when_merchant_exposes_network() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_runtime_auto_host",
                    "error_code": None,
                    "error_message": None,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used in this test")

    settlement_service = FakeSettlementService()
    app = _build_gateway_app(settlement_service=settlement_service)
    settlement_service.runtime = app.state.aimipay_gateway

    class FakeProvisioner:
        def __init__(self) -> None:
            self.last_plan = None

        def provision(self, plan):
            self.last_plan = plan
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_runtime_auto_host",
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    provisioner = FakeProvisioner()
    runtime = install_agent_payments(
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=provisioner,
        merchant_base_url="http://merchant.test",
        http_clients={"http://merchant.test": TestClient(app, base_url="http://merchant.test")},
    )

    result = runtime.pay_for_task(
        task_context="Need web search without explicit chain RPC config",
        capability_type="web_search",
        request_body='{"topic":"tron"}',
    )

    assert result["payment"]["tx_id"] == "trx_claim_runtime_auto_host"
    assert provisioner.last_plan.full_host == "http://127.0.0.1:9090"


def test_agent_payments_runtime_disable_auto_purchase_blocks_task_payment() -> None:
    runtime = install_agent_payments(
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=type("NoopProvisioner", (), {"provision": lambda self, plan: None})(),
        merchant_base_urls=["http://merchant-a.test"],
    )
    runtime.disable_auto_purchase()

    with pytest.raises(RuntimeError, match="auto purchase is disabled"):
        runtime.pay_for_task(
            task_context="Need web search",
            capability_type="web_search",
        )


def test_buyer_client_can_create_and_execute_payment() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_1",
                    "error_code": None,
                    "error_message": None,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used in this test")

    settlement_service = FakeSettlementService()
    app = _build_gateway_app(settlement_service=settlement_service)
    settlement_service.runtime = app.state.aimipay_gateway
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_1",
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    result = client.pay_route(
        route_path="/tools/research",
        method="POST",
        request_body='{"topic":"tron"}',
    )

    assert result["session"]["channel_id"] == "channel_1"
    assert result["payment"]["status"] == "submitted"
    assert result["payment"]["tx_id"] == "trx_claim_1"

    stored_payment = client.get_payment(result["payment"]["payment_id"])
    assert stored_payment["status"] == "submitted"
    assert stored_payment["tx_id"] == "trx_claim_1"


def test_buyer_client_pay_route_can_auto_finalize() -> None:
    class FakeSettlementService:
        runtime = None

        def execute_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "submitted",
                    "tx_id": "trx_claim_auto_finalize_1",
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

        def execute_pending(self):
            raise AssertionError("not used in this test")

        def reconcile_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "settled",
                    "confirmation_status": "confirmed",
                    "settled_at": 1_700_000_002,
                    "confirmed_at": 1_700_000_002,
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

    settlement_service = FakeSettlementService()
    app = _build_gateway_app(settlement_service=settlement_service)
    settlement_service.runtime = app.state.aimipay_gateway
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_1",
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    result = client.pay_route(
        route_path="/tools/research",
        method="POST",
        request_body='{"topic":"tron"}',
        auto_finalize=True,
    )

    assert result["payment"]["status"] == "settled"
    assert result["payment"]["confirmation_status"] == "confirmed"


def test_buyer_client_builds_request_digest_and_signature(monkeypatch) -> None:
    app = _build_gateway_app(
        settlement=GatewaySettlementConfig(
            repository_root="e:/trade/aimicropay-tron",
            full_host="http://tron.local",
            seller_private_key="seller_pk",
            chain_id=31337,
            executor_backend="claim_script",
        ),
    )
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id=channel_id_of(
                    buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                    seller_address=plan.seller_address,
                    token_address=plan.token_address,
                ),
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    seen_args = {}

    def fake_voucher_builder(**kwargs):
        seen_args.update(kwargs)
        return type(
            "VoucherPayload",
            (),
            {
                "request_digest": "0xdigest_1",
                "voucher_digest": "0xvoucher_1",
                "buyer_signature": "0xsig_1",
            },
        )()

    monkeypatch.setattr("buyer.client.build_payment_voucher", fake_voucher_builder)

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        ),
        provisioner=FakeProvisioner(),
        http_client=http_client,
        repository_root="e:/trade/aimicropay-tron",
    )

    result = client.pay_route(
        route_path="/tools/research",
        method="POST",
        request_body='{"topic":"tron"}',
        auto_execute=False,
    )

    payment = result["payment"]
    assert payment["request_digest"] == "0xdigest_1"
    assert payment["buyer_signature"] == "0xsig_1"
    assert seen_args["chain_id"] == 31337
    assert seen_args["channel_id"].startswith("0x")
    assert seen_args["amount_atomic"] == 250_000


def test_buyer_client_can_build_authorization_without_repository_root() -> None:
    app = _build_gateway_app(
        settlement=GatewaySettlementConfig(
            repository_root="e:/trade/aimicropay-tron",
            full_host="http://tron.local",
            seller_private_key="seller_pk",
            chain_id=31337,
            executor_backend="claim_script",
        ),
    )
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id=channel_id_of(
                    buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                    seller_address=plan.seller_address,
                    token_address=plan.token_address,
                ),
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        ),
        provisioner=FakeProvisioner(),
        http_client=http_client,
    )

    result = client.pay_route(
        route_path="/tools/research",
        method="POST",
        request_body='{"topic":"tron"}',
        auto_execute=False,
    )

    assert result["payment"]["request_digest"].startswith("0x")
    assert result["payment"]["buyer_signature"].startswith("0x")


def test_buyer_client_can_pay_route_against_local_smoke_gateway(monkeypatch) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    if not (repository_root / "node_modules" / "hardhat").exists():
        pytest.skip("local hardhat dependencies are not installed")

    app = _build_gateway_app(
        seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        settlement=GatewaySettlementConfig(
            repository_root=str(repository_root),
            full_host="http://tron.local",
            seller_private_key="seller_pk",
            chain_id=31337,
            executor_backend="local_smoke",
        ),
    )
    http_client = TestClient(app, base_url="http://merchant.test")

    class FakeProvisioner:
        def provision(self, plan):
            return OpenChannelExecution(
                approve_tx_id="approve_1",
                open_tx_id="open_1",
                buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_1",
                contract_address=plan.contract_address,
                deposit_atomic=plan.deposit_atomic,
                expires_at=plan.expires_at,
            )

    called = {"voucher_builder": False}

    def fake_voucher_builder(*, repository_root: str, plan: dict) -> dict:
        called["voucher_builder"] = True
        return {
            "request_digest": "should_not_be_used",
            "buyer_signature": "should_not_be_used",
        }

    monkeypatch.setattr("buyer.client.build_payment_voucher", fake_voucher_builder)

    client = BuyerClient(
        merchant_base_url="http://merchant.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="buyer_pk",
        ),
        provisioner=FakeProvisioner(),
        http_client=http_client,
        repository_root=str(repository_root),
    )

    result = client.pay_route(
        route_path="/tools/research",
        method="POST",
        request_body='{"topic":"tron"}',
    )

    assert called["voucher_builder"] is False
    assert result["payment"]["status"] == "submitted"
    assert result["payment"]["tx_id"] is not None

from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi.testclient import TestClient

from buyer import AimiPayMcpServer, BuyerWallet, OpenChannelExecution, install_agent_payments
from seller.gateway import GatewayConfig, install_gateway
from shared import CapabilityBudgetHint, MerchantRoute
from fastapi import FastAPI


def _build_runtime():
    app = FastAPI()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            chain_id=31337,
            routes=[
                MerchantRoute(
                    path="/tools/research",
                    method="POST",
                    price_atomic=250_000,
                    capability_id="research-web-search",
                    capability_type="web_search",
                    pricing_model="fixed_per_call",
                    usage_unit="request",
                    budget_hint=CapabilityBudgetHint(
                        typical_units=3,
                        suggested_prepaid_atomic=750_000,
                    ),
                )
            ],
        ),
    )

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

    return install_agent_payments(
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=FakeProvisioner(),
        merchant_base_url="http://merchant.test",
        http_clients={"http://merchant.test": TestClient(app, base_url="http://merchant.test")},
    )


def test_mcp_server_lists_tools() -> None:
    server = AimiPayMcpServer(_build_runtime())

    response = server.handle_request({"id": "1", "method": "tools/list"})

    assert response["id"] == "1"
    tools = response["result"]["tools"]
    assert any(tool["name"] == "aimipay.get_protocol_manifest" for tool in tools)
    assert any(tool["name"] == "aimipay.list_offers" for tool in tools)
    assert any(tool["name"] == "aimipay.quote_budget" for tool in tools)
    assert any(tool["name"] == "aimipay.plan_purchase" for tool in tools)
    assert any(tool["name"] == "aimipay.prepare_purchase" for tool in tools)
    assert any(tool["name"] == "aimipay.submit_purchase" for tool in tools)
    assert any(tool["name"] == "aimipay.confirm_purchase" for tool in tools)
    assert any(tool["name"] == "aimipay.get_merchant_status" for tool in tools)
    assert any(tool["name"] == "aimipay.get_agent_state" for tool in tools)
    assert any(tool["name"] == "aimipay.recover_payment" for tool in tools)
    assert any(tool["name"] == "aimipay.reconcile_payment" for tool in tools)
    assert any(tool["name"] == "aimipay.finalize_payment" for tool in tools)
    assert any(tool["name"] == "aimipay.check_wallet_funding" for tool in tools)
    assert any(tool["name"] == "aimipay.create_wallet" for tool in tools)
    assert any(tool["name"] == "aimipay.run_onboarding" for tool in tools)
    assert any(tool["name"] == "aimipay.set_merchant_url" for tool in tools)
    assert any(tool["name"] == "aimipay.get_startup_onboarding" for tool in tools)


def test_mcp_server_initialize_and_initialized() -> None:
    server = AimiPayMcpServer(_build_runtime())

    initialize = server.handle_request({"jsonrpc": "2.0", "id": "init", "method": "initialize"})
    initialized = server.handle_request({"jsonrpc": "2.0", "id": "ready", "method": "initialized"})

    assert initialize["jsonrpc"] == "2.0"
    assert initialize["result"]["protocolVersion"] == "2024-11-05"
    assert initialize["result"]["serverInfo"]["name"] == "aimipay-tron"
    assert "instructions" in initialize["result"]
    assert "aimipay/startupOnboarding" in initialize["result"]["meta"]
    assert "aimipay/startupCard" in initialize["result"]["meta"]
    assert initialized["result"] == {}


def test_mcp_server_can_call_tools() -> None:
    server = AimiPayMcpServer(_build_runtime())

    list_response = server.handle_request(
        {
            "id": "2",
            "method": "tools/call",
            "params": {
                "name": "aimipay.list_offers",
                "arguments": {},
            },
        }
    )
    estimate_response = server.handle_request(
        {
            "id": "3",
            "method": "tools/call",
            "params": {
                "name": "aimipay.estimate_budget",
                "arguments": {"capability_id": "research-web-search"},
            },
        }
    )

    list_payload = list_response["result"]["structuredContent"]
    estimate_payload = estimate_response["result"]["structuredContent"]
    assert list_payload["schema_version"] == "aimipay.agent-protocol.v1"
    assert list_payload["kind"] == "capability_catalog"
    assert list_payload["next_step"] == "quote_budget"
    assert len(list_payload["offers"]) == 1
    assert estimate_payload["schema_version"] == "aimipay.agent-protocol.v1"
    assert estimate_payload["kind"] == "budget_quote"
    assert estimate_payload["estimated_cost_atomic"] == 750_000
    assert estimate_payload["auto_decision"]["action"] == "buy_now"


def test_mcp_server_returns_protocol_manifest() -> None:
    server = AimiPayMcpServer(_build_runtime())

    response = server.handle_request(
        {
            "id": "manifest",
            "method": "tools/call",
            "params": {
                "name": "aimipay.get_protocol_manifest",
                "arguments": {},
            },
        }
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["schema_version"] == "aimipay.capabilities.v1"
    assert "aimipay.get_agent_state" in payload["default_flow"]
    assert payload["error_recovery_actions"]["budget_exceeded"]["agent_action"] == "request_human_approval"
    assert payload["host_contract"]["preserve_payment_id_for_recovery"] is True


def test_mcp_server_returns_ai_protocol_budget_plan_and_state() -> None:
    server = AimiPayMcpServer(_build_runtime())

    quote_response = server.handle_request(
        {
            "id": "quote",
            "method": "tools/call",
            "params": {
                "name": "aimipay.quote_budget",
                "arguments": {
                    "capability_id": "research-web-search",
                    "expected_units": 2,
                    "budget_limit_atomic": 600_000,
                },
            },
        }
    )
    plan_response = server.handle_request(
        {
            "id": "plan",
            "method": "tools/call",
            "params": {
                "name": "aimipay.plan_purchase",
                "arguments": {
                    "capability_type": "web_search",
                    "expected_units": 2,
                    "budget_limit_atomic": 600_000,
                },
            },
        }
    )
    state_response = server.handle_request(
        {
            "id": "state",
            "method": "tools/call",
            "params": {
                "name": "aimipay.get_agent_state",
                "arguments": {},
            },
        }
    )

    quote = quote_response["result"]["structuredContent"]
    plan = plan_response["result"]["structuredContent"]
    state = state_response["result"]["structuredContent"]
    assert quote["kind"] == "budget_quote"
    assert quote["auto_decision"]["allowed"] is True
    assert quote["next_actions"][0]["action"] == "prepare_purchase"
    assert plan["kind"] == "purchase_plan"
    assert plan["selection"]["selected"]["offer"]["capability_id"] == "research-web-search"
    assert state["kind"] == "agent_state"
    assert state["capability_catalog"]["count"] == 1


def test_mcp_server_can_return_merchant_status() -> None:
    server = AimiPayMcpServer(_build_runtime())

    response = server.handle_request(
        {
            "id": "merchant-status",
            "method": "tools/call",
            "params": {
                "name": "aimipay.get_merchant_status",
                "arguments": {},
            },
        }
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["schema_version"] == "aimipay.agent-status.v1"
    assert payload["service"]["name"] == "Research Copilot"
    assert payload["capabilities"]["routes"][0]["capability_id"] == "research-web-search"
    assert payload["next_step"] in {"ready_to_purchase", "review_merchant_readiness"}


def test_mcp_server_can_call_wallet_funding_tool(tmp_path) -> None:
    server = AimiPayMcpServer(_build_runtime())
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "AIMIPAY_BUYER_ADDRESS=TRX_BUYER\nAIMIPAY_BUYER_PRIVATE_KEY=buyer_private_key\n",
        encoding="utf-8",
    )

    response = server.handle_request(
        {
            "id": "wallet-funding",
            "method": "tools/call",
            "params": {
                "name": "aimipay.check_wallet_funding",
                "arguments": {"env_file": str(env_file)},
            },
        }
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["wallet_ready"] is False
    assert payload["next_step"] == "create_wallet"


def test_mcp_server_can_call_create_wallet_tool(tmp_path) -> None:
    server = AimiPayMcpServer(_build_runtime())
    env_file = tmp_path / ".env.local"
    wallet_file = tmp_path / ".wallets" / "buyer-wallet.json"
    env_file.write_text("", encoding="utf-8")

    response = server.handle_request(
        {
            "id": "create-wallet",
            "method": "tools/call",
            "params": {
                "name": "aimipay.create_wallet",
                "arguments": {
                    "env_file": str(env_file),
                    "wallet_file": str(wallet_file),
                },
            },
        }
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["wallet"]["wallet_created"] is True
    assert wallet_file.exists()
    assert payload["next_step"] == "ready_to_purchase"


def test_mcp_server_can_run_onboarding_tool(tmp_path) -> None:
    server = AimiPayMcpServer(_build_runtime())
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    env_file = python_dir / ".env.local"
    env_file.write_text("AIMIPAY_SETTLEMENT_BACKEND=local_smoke\n", encoding="utf-8")

    response = server.handle_request(
        {
            "id": "run-onboarding",
            "method": "tools/call",
            "params": {
                "name": "aimipay.run_onboarding",
                "arguments": {
                    "env_file": str(env_file),
                    "wallet_file": str(python_dir / ".wallets" / "buyer-wallet.json"),
                },
            },
        }
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["wallet"]["wallet_created"] is True
    assert payload["funding"]["next_step"] == "ready_to_purchase"
    assert Path(payload["saved_report"]).exists()


def test_mcp_server_can_set_merchant_url_and_refresh_onboarding(tmp_path) -> None:
    server = AimiPayMcpServer(_build_runtime())
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    env_file = python_dir / ".env.local"
    env_file.write_text("", encoding="utf-8")

    response = server.handle_request(
        {
            "id": "set-merchant-url",
            "method": "tools/call",
            "params": {
                "name": "aimipay.set_merchant_url",
                "arguments": {
                    "merchant_url": "http://merchant.test",
                    "env_file": str(env_file),
                },
            },
        }
    )

    payload = response["result"]["structuredContent"]
    assert response["result"]["isError"] is False
    assert payload["setup"]["merchant_urls"] == ["http://merchant.test"]
    assert payload["onboarding"]["merchant"]["selected_url"] == "http://merchant.test"
    assert payload["onboarding"]["merchant"]["offers"]["count"] == 1
    assert payload["next_step"] == "review_offers"


def test_mcp_server_can_return_startup_onboarding_payload() -> None:
    server = AimiPayMcpServer(
        _build_runtime(),
        startup_onboarding={
            "completed": False,
            "next_step": "fund_wallet",
            "action_required": "fund_wallet",
            "saved_report": "E:/tmp/onboarding.json",
            "funding": {
                "host_action": {
                    "action": "fund_wallet",
                    "message": "Fund the wallet before buying.",
                    "checklist": ["Add TRX", "Add USDT"],
                }
            },
            "merchant": {
                "merchant_urls": ["https://merchant.example"],
                "selected_url": "https://merchant.example",
                "service_name": "Example Merchant",
                "offers": {"count": 2, "items": [{"capability_id": "search", "route_path": "/tools/search"}]},
                "host_action": {
                    "action": "review_offers",
                    "message": "Merchant connected and offers discovered.",
                },
            }
        },
    )

    response = server.handle_request(
        {
            "id": "startup-onboarding",
            "method": "tools/call",
            "params": {
                "name": "aimipay.get_startup_onboarding",
                "arguments": {},
            },
        }
    )

    payload = response["result"]["structuredContent"]
    assert payload["present"] is True
    assert payload["next_step"] == "fund_wallet"
    assert payload["host_action"]["action"] == "fund_wallet"
    assert payload["merchant"]["selected_url"] == "https://merchant.example"
    assert payload["merchant"]["offers"]["count"] == 2


def test_mcp_server_initialize_includes_startup_card_schema() -> None:
    server = AimiPayMcpServer(
        _build_runtime(),
        startup_onboarding={
            "completed": False,
            "next_step": "review_offers",
            "action_required": None,
            "saved_report": "E:/tmp/onboarding.json",
            "funding": {
                "host_action": {
                    "action": "ready_to_purchase",
                    "title": "Wallet Ready",
                    "message": "Wallet onboarding is complete.",
                    "checklist": ["Wallet saved locally"],
                    "resources": [{"label": "Testnet Faucet", "url": "https://example.test/faucet"}],
                }
            },
            "merchant": {
                "merchant_urls": ["https://merchant.example"],
                "selected_url": "https://merchant.example",
                "service_name": "Example Merchant",
                "offers": {
                    "count": 2,
                    "items": [
                        {"capability_id": "search", "route_path": "/tools/search"},
                        {"capability_id": "translate", "route_path": "/tools/translate"},
                    ],
                },
                "host_action": {
                    "action": "review_offers",
                    "title": "Merchant Connected",
                    "message": "Merchant connected and offers discovered.",
                    "checklist": ["Merchant URL: https://merchant.example", "Offers discovered: 2"],
                    "fields": [
                        {
                            "name": "merchant_url",
                            "label": "Merchant URL",
                            "type": "url",
                            "required": True,
                            "value": "https://merchant.example",
                        }
                    ],
                    "resources": [{"label": "Manifest", "url": "https://merchant.example/.well-known/aimipay.json"}],
                    "offers_preview": [{"capability_id": "search", "route_path": "/tools/search"}],
                },
            }
        },
    )

    response = server.handle_request({"jsonrpc": "2.0", "id": "init", "method": "initialize"})
    card = response["result"]["meta"]["aimipay/startupCard"]

    assert card["schema_version"] == "aimipay.startup-card.v1"
    assert card["kind"] == "onboarding_card"
    assert card["visible"] is True
    assert card["primary_action"]["action"] == "review_offers"
    assert card["primary_action"]["label"] == "Review Offers"
    assert card["resources"][0]["label"] == "Testnet Faucet"
    assert card["fields"][0]["name"] == "merchant_url"
    assert card["fields"][0]["value"] == "https://merchant.example"
    assert card["offers_preview"][0]["capability_id"] == "search"


def test_mcp_server_can_call_reconcile_tool() -> None:
    app = FastAPI()

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
            return []

        def reconcile_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "settled",
                    "confirmation_status": "confirmed",
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

    settlement_service = FakeSettlementService()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            chain_id=31337,
            routes=[
                MerchantRoute(
                    path="/tools/research",
                    method="POST",
                    price_atomic=250_000,
                    capability_id="research-web-search",
                    capability_type="web_search",
                    pricing_model="fixed_per_call",
                    usage_unit="request",
                    budget_hint=CapabilityBudgetHint(
                        typical_units=3,
                        suggested_prepaid_atomic=750_000,
                    ),
                )
            ],
        ),
        settlement_service=settlement_service,
    )
    settlement_service.runtime = app.state.aimipay_gateway

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

    runtime = install_agent_payments(
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=FakeProvisioner(),
        merchant_base_url="http://merchant.test",
        http_clients={"http://merchant.test": TestClient(app, base_url="http://merchant.test")},
    )
    server = AimiPayMcpServer(runtime)

    session = runtime.connect_merchant().ensure_channel_for_route(route_path="/tools/research")
    payment = runtime.connect_merchant().create_payment_intent(
        channel_session=session,
        route_path="/tools/research",
        request_body='{"topic":"tron"}',
    )
    runtime.connect_merchant().execute_payment(payment["payment_id"])

    response = server.handle_request(
        {
            "id": "reconcile",
            "method": "tools/call",
            "params": {
                "name": "aimipay.reconcile_payment",
                "arguments": {"payment_id": payment["payment_id"]},
            },
        }
    )

    assert response["result"]["isError"] is False
    assert response["result"]["structuredContent"]["payment"]["status"] == "settled"


def test_mcp_server_can_call_finalize_tool() -> None:
    app = FastAPI()

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
            return []

        def reconcile_payment(self, payment_id: str):
            record = self.runtime.payment_store.get(payment_id)
            updated = record.model_copy(
                update={
                    "status": "settled",
                    "confirmation_status": "confirmed",
                }
            )
            self.runtime.payment_store.upsert(updated)
            return updated

    settlement_service = FakeSettlementService()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TRX_SELLER",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            chain_id=31337,
            routes=[
                MerchantRoute(
                    path="/tools/research",
                    method="POST",
                    price_atomic=250_000,
                    capability_id="research-web-search",
                    capability_type="web_search",
                    pricing_model="fixed_per_call",
                    usage_unit="request",
                    budget_hint=CapabilityBudgetHint(
                        typical_units=3,
                        suggested_prepaid_atomic=750_000,
                    ),
                )
            ],
        ),
        settlement_service=settlement_service,
    )
    settlement_service.runtime = app.state.aimipay_gateway

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

    runtime = install_agent_payments(
        full_host="http://tron.local",
        wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
        provisioner=FakeProvisioner(),
        merchant_base_url="http://merchant.test",
        http_clients={"http://merchant.test": TestClient(app, base_url="http://merchant.test")},
    )
    server = AimiPayMcpServer(runtime)

    session = runtime.connect_merchant().ensure_channel_for_route(route_path="/tools/research")
    payment = runtime.connect_merchant().create_payment_intent(
        channel_session=session,
        route_path="/tools/research",
        request_body='{"topic":"tron"}',
    )

    response = server.handle_request(
        {
            "id": "finalize",
            "method": "tools/call",
            "params": {
                "name": "aimipay.finalize_payment",
                "arguments": {"payment_id": payment["payment_id"]},
            },
        }
    )

    assert response["result"]["isError"] is False
    assert response["result"]["structuredContent"]["payment"]["status"] == "settled"


def test_mcp_server_returns_tool_error_in_result_shape() -> None:
    server = AimiPayMcpServer(_build_runtime())

    response = server.handle_request(
        {
            "id": "error-tool",
            "method": "tools/call",
            "params": {
                "name": "aimipay.estimate_budget",
                "arguments": {},
            },
        }
    )

    assert response["result"]["isError"] is True
    assert response["result"]["structuredContent"]["error"]["code"] == "mcp_invalid_params"


def test_mcp_server_returns_standard_method_error() -> None:
    server = AimiPayMcpServer(_build_runtime())

    response = server.handle_request({"jsonrpc": "2.0", "id": "bad", "method": "unknown/method"})

    assert response["jsonrpc"] == "2.0"
    assert response["error"]["code"] == -32601
    assert response["error"]["data"]["error"]["code"] == "mcp_method_not_found"


def test_mcp_server_stdio_loop_emits_json_responses() -> None:
    server = AimiPayMcpServer(_build_runtime())
    source = io.StringIO(json.dumps({"id": "1", "method": "tools/list"}) + "\n")
    sink = io.StringIO()

    server.serve_stdio(in_stream=source, out_stream=sink)

    sink.seek(0)
    payload = json.loads(sink.readline())
    assert payload["id"] == "1"
    assert "tools" in payload["result"]


def test_mcp_server_stdio_loop_returns_parse_error() -> None:
    server = AimiPayMcpServer(_build_runtime())
    source = io.StringIO("{not-json}\n")
    sink = io.StringIO()

    server.serve_stdio(in_stream=source, out_stream=sink)

    sink.seek(0)
    payload = json.loads(sink.readline())
    assert payload["error"]["code"] == -32700
    assert payload["error"]["data"]["error"]["code"] == "mcp_parse_error"

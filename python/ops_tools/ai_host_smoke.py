from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from buyer import AimiPayMcpServer, BuyerWallet, OpenChannelExecution, install_agent_payments
from seller.gateway import GatewayConfig, install_gateway
from shared import CapabilityBudgetHint, MerchantRoute


def run_ai_host_smoke(*, output_json: bool = False) -> dict[str, Any]:
    server = AimiPayMcpServer(_build_demo_runtime())
    calls = [
        ("manifest", "aimipay.get_protocol_manifest", {}),
        ("state", "aimipay.get_agent_state", {}),
        ("offers", "aimipay.list_offers", {}),
        (
            "quote",
            "aimipay.quote_budget",
            {
                "capability_id": "research-web-search",
                "expected_units": 2,
                "budget_limit_atomic": 600_000,
            },
        ),
        (
            "plan",
            "aimipay.plan_purchase",
            {
                "capability_type": "web_search",
                "expected_units": 2,
                "budget_limit_atomic": 600_000,
            },
        ),
        (
            "pending",
            "aimipay.list_pending_payments",
            {},
        ),
    ]
    transcript = [_call_tool(server, label, tool, args) for label, tool, args in calls]
    ok = all(item["ok"] for item in transcript)
    required_kinds = {
        "manifest": "aimipay.capabilities.v1",
        "state": "agent_state",
        "offers": "capability_catalog",
        "quote": "budget_quote",
        "plan": "purchase_plan",
        "pending": "payment_recovery",
    }
    assertions = []
    for item in transcript:
        payload = item.get("payload") or {}
        expected = required_kinds[item["label"]]
        actual = payload.get("schema_version") if item["label"] == "manifest" else payload.get("kind")
        assertions.append(
            {
                "label": item["label"],
                "ok": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )
    report = {
        "schema_version": "aimipay.ai-host-smoke.v1",
        "ok": ok and all(item["ok"] for item in assertions),
        "host": "generic-mcp",
        "scenario": "install-free AI host protocol smoke",
        "transcript": transcript,
        "assertions": assertions,
        "next_actions": [
            {
                "action": "wire_external_host",
                "reason": "The AI-facing protocol tools returned stable structured payloads.",
            }
        ],
    }
    if output_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a local AI-host smoke test against the AimiPay MCP surface.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_ai_host_smoke(output_json=args.json)
    if not args.json:
        print(_format_report(report))
    return 0 if report["ok"] else 1


def _call_tool(server: AimiPayMcpServer, label: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": label,
            "method": "tools/call",
            "params": {
                "name": tool,
                "arguments": arguments,
            },
        }
    )
    result = response.get("result") or {}
    payload = result.get("structuredContent")
    return {
        "label": label,
        "tool": tool,
        "ok": bool(result) and not result.get("isError", False),
        "payload": payload,
        "error": (payload or {}).get("error"),
        "next_actions": (payload or {}).get("next_actions", []),
    }


def _build_demo_runtime():
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
                approve_tx_id="approve_smoke",
                open_tx_id="open_smoke",
                buyer_address="TRX_BUYER",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_id="channel_smoke",
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
        repository_root=Path(__file__).resolve().parents[2],
    )


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay AI Host Smoke",
        f"- ok: {report['ok']}",
        f"- host: {report['host']}",
        f"- scenario: {report['scenario']}",
    ]
    for item in report["transcript"]:
        lines.append(f"- {item['label']}: {item['tool']} ok={item['ok']}")
    for assertion in report["assertions"]:
        lines.append(
            f"- assert {assertion['label']}: expected={assertion['expected']} actual={assertion['actual']} ok={assertion['ok']}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

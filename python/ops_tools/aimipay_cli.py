from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aimipay", description="AimiPay developer CLI")
    subcommands = parser.add_subparsers(dest="command", required=True)

    merchant_parser = subcommands.add_parser("merchant", help="Merchant developer workflow")
    merchant_commands = merchant_parser.add_subparsers(dest="merchant_command", required=True)

    init_parser = merchant_commands.add_parser("init", help="Create a minimal merchant config scaffold")
    init_parser.add_argument("--output", default="aimipay.merchant.json")
    init_parser.add_argument("--service-name", default="Research Copilot")
    init_parser.add_argument("--seller-address", default="TRX_SELLER")

    verify_parser = merchant_commands.add_parser("verify", help="Verify a merchant config scaffold")
    verify_parser.add_argument("--config", default="aimipay.merchant.json")

    dev_parser = merchant_commands.add_parser("dev", help="Print the local merchant dev command")
    dev_parser.add_argument("--app", default="python/examples/http402_paid_api_app.py")

    demo_parser = subcommands.add_parser("demo", help="Print runnable demo entrypoints")
    demo_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "merchant" and args.merchant_command == "init":
        payload = {
            "schema_version": "aimipay.merchant-config.v1",
            "service_name": args.service_name,
            "service_description": "Paid API for AI agents",
            "seller_address": args.seller_address,
            "contract_address": "TRX_CONTRACT",
            "token_address": "TRX_USDT",
            "routes": [
                {
                    "path": "/tools/research",
                    "method": "POST",
                    "price_atomic": 250_000,
                    "capability_id": "research-web-search",
                    "capability_type": "web_search",
                }
            ],
        }
        Path(args.output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"ok": True, "written": args.output}, indent=2))
        return 0
    if args.command == "merchant" and args.merchant_command == "verify":
        config_path = Path(args.config)
        if not config_path.exists():
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": "merchant_config_not_found",
                        "config": args.config,
                        "next_action": "Run: PYTHONPATH=python python -m ops_tools.aimipay_cli merchant init",
                    },
                    indent=2,
                )
            )
            return 1
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        missing = [
            key
            for key in ["service_name", "seller_address", "contract_address", "token_address", "routes"]
            if not payload.get(key)
        ]
        print(json.dumps({"ok": not missing, "missing": missing}, indent=2))
        return 0 if not missing else 1
    if args.command == "merchant" and args.merchant_command == "dev":
        print(f"PYTHONPATH=python uvicorn {args.app.replace('/', '.').removesuffix('.py')}:app --reload")
        return 0
    if args.command == "demo":
        payload = {
            "http402_paid_api": "PYTHONPATH=python python python/examples/http402_paid_api_app.py",
            "coding_agent_vertical": "PYTHONPATH=python python python/examples/coding_agent_paid_tools_app.py",
            "coding_agent_paid_flow": "PYTHONPATH=python python python/examples/coding_agent_paid_flow_demo.py",
            "ai_host_smoke": "cd python && PYTHONPATH=. python -m ops_tools.ai_host_smoke --json",
        }
        print(json.dumps(payload, indent=2) if args.json else "\n".join(payload.values()))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

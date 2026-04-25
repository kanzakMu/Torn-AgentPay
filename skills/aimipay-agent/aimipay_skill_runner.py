from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AimiPay AI-facing protocol tools from a skill-only install.")
    parser.add_argument(
        "command",
        choices=[
            "list-tools",
            "doctor",
            "protocol-manifest",
            "get-agent-state",
            "list-offers",
            "quote-budget",
            "plan-purchase",
            "get-payment-status",
            "list-pending-payments",
            "recover-payment",
        ],
    )
    parser.add_argument("--runtime-config", default=str(Path(__file__).with_name("skill-runtime.json")))
    parser.add_argument("--merchant-base-url")
    parser.add_argument("--capability-id")
    parser.add_argument("--capability-type")
    parser.add_argument("--expected-units", type=int)
    parser.add_argument("--budget-limit-atomic", type=int)
    parser.add_argument("--payment-id")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--channel-id")
    parser.add_argument("--admin-token")
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args(argv)

    config = _load_runtime_config(Path(args.runtime_config))
    if args.command == "doctor":
        payload = _doctor_payload(config, Path(args.runtime_config))
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    _prepare_repo_imports(config)
    _load_env_file(Path(config["env_file"]))

    from agent_entrypoints.aimipay_mcp_stdio import build_server

    server = build_server()
    if args.command == "list-tools":
        payload = {"tools": server.list_tools()}
    elif args.command == "protocol-manifest":
        payload = server.call_tool("aimipay.get_protocol_manifest", {})
    else:
        tool_name, arguments = _tool_call(args)
        if args.merchant_base_url:
            arguments["merchant_base_url"] = args.merchant_base_url
        response = server.handle_request(
            {
                "id": "skill-runner",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            }
        )
        result = response.get("result") or {}
        if result.get("isError"):
            print(json.dumps(result.get("structuredContent"), indent=2, sort_keys=True))
            return 1
        payload = result.get("structuredContent")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _load_runtime_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"runtime config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _prepare_repo_imports(config: dict[str, Any]) -> None:
    repo_root = Path(config["repository_root"]).resolve()
    python_dir = repo_root / "python"
    vendor_dir = python_dir / ".vendor"
    for item in [python_dir, vendor_dir]:
        if str(item) not in sys.path:
            sys.path.insert(0, str(item))
    os.environ["AIMIPAY_REPOSITORY_ROOT"] = str(repo_root)
    if config.get("merchant_urls"):
        os.environ["AIMIPAY_MERCHANT_URLS"] = ",".join(config["merchant_urls"])
    if config.get("full_host"):
        os.environ["AIMIPAY_FULL_HOST"] = config["full_host"]


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _tool_call(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    if args.command == "protocol-manifest":
        return "aimipay.get_protocol_manifest", {}
    if args.command == "get-agent-state":
        return "aimipay.get_agent_state", _compact({"admin_token": args.admin_token})
    if args.command == "list-offers":
        return "aimipay.list_offers", {}
    if args.command == "quote-budget":
        return "aimipay.quote_budget", _compact(
            {
                "capability_id": args.capability_id,
                "expected_units": args.expected_units,
                "budget_limit_atomic": args.budget_limit_atomic,
            }
        )
    if args.command == "plan-purchase":
        return "aimipay.plan_purchase", _compact(
            {
                "capability_id": args.capability_id,
                "capability_type": args.capability_type,
                "expected_units": args.expected_units,
                "budget_limit_atomic": args.budget_limit_atomic,
            }
        )
    if args.command == "get-payment-status":
        return "aimipay.get_payment_status", _compact({"payment_id": args.payment_id})
    if args.command == "list-pending-payments":
        return "aimipay.list_pending_payments", {}
    if args.command == "recover-payment":
        return "aimipay.recover_payment", _compact(
            {
                "payment_id": args.payment_id,
                "idempotency_key": args.idempotency_key,
                "channel_id": args.channel_id,
            }
        )
    raise ValueError(f"unsupported command: {args.command}")


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _doctor_payload(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    repo_root = Path(config.get("repository_root", "")).expanduser()
    python_dir = repo_root / "python"
    env_file = Path(config.get("env_file", "")).expanduser()
    runner = config_path.with_name(config.get("runner", "aimipay_skill_runner.py"))
    merchant_urls = [item for item in config.get("merchant_urls", []) if item]
    checks = [
        {
            "name": "runtime_config",
            "ok": config_path.exists(),
            "path": str(config_path),
        },
        {
            "name": "repository_root",
            "ok": repo_root.exists(),
            "path": str(repo_root),
        },
        {
            "name": "python_package",
            "ok": python_dir.exists(),
            "path": str(python_dir),
        },
        {
            "name": "env_file",
            "ok": env_file.exists(),
            "path": str(env_file),
        },
        {
            "name": "skill_runner",
            "ok": runner.exists(),
            "path": str(runner),
        },
        {
            "name": "merchant_urls",
            "ok": bool(merchant_urls),
            "value": merchant_urls,
        },
    ]
    missing = [item for item in checks if not item["ok"]]
    next_actions: list[dict[str, Any]] = []
    if missing:
        next_actions.append(
            {
                "action": "run_onboarding",
                "command": f'python "{runner}" get-agent-state',
                "reason": "The skill is installed, but local runtime state is incomplete.",
            }
        )
    else:
        next_actions.append(
            {
                "action": "get_agent_state",
                "command": f'python "{runner}" get-agent-state',
                "reason": "Skill runtime files are present; ask AimiPay for readiness and next actions.",
            }
        )
        next_actions.append(
            {
                "action": "protocol_manifest",
                "command": f'python "{runner}" protocol-manifest',
                "reason": "Expose the stable tool flow and recovery matrix to the AI host.",
            }
        )
    return {
        "schema_version": "aimipay.skill-doctor.v1",
        "ok": not missing,
        "checks": checks,
        "next_actions": next_actions,
        "available_commands": [
            "doctor",
            "protocol-manifest",
            "list-tools",
            "get-agent-state",
            "list-offers",
            "quote-budget",
            "plan-purchase",
            "get-payment-status",
            "list-pending-payments",
            "recover-payment",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())

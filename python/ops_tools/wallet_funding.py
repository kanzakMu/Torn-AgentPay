from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from buyer.wallet import BuyerWallet


def inspect_wallet_funding(
    *,
    repository_root: str | Path | None = None,
    env_file: str | Path | None = None,
    output_json: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    repo_root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    env_path = Path(env_file or repo_root / "python" / ".env.local").resolve()

    values = _read_env_values(env_path)
    wallet_ready = BuyerWallet.env_has_configured_wallet(env_path)
    settlement_backend = values.get("AIMIPAY_SETTLEMENT_BACKEND", "local_smoke")
    full_host = values.get("AIMIPAY_FULL_HOST", "")
    token_address = values.get("AIMIPAY_TOKEN_ADDRESS", "")
    merchant_urls = [item.strip() for item in values.get("AIMIPAY_MERCHANT_URLS", "").split(",") if item.strip()]
    network_name = values.get("AIMIPAY_NETWORK_NAME", _default_network_name(settlement_backend, full_host))
    faucet_url = values.get("AIMIPAY_FAUCET_URL", "")
    funding_guide_url = values.get("AIMIPAY_FUNDING_GUIDE_URL", "")
    min_trx_sun = int(values.get("AIMIPAY_MIN_TRX_BALANCE_SUN", "1000000") or 1000000)
    min_token_atomic = int(values.get("AIMIPAY_MIN_TOKEN_BALANCE_ATOMIC", "1000000") or 1000000)

    report: dict[str, Any] = {
        "ok": True,
        "wallet_ready": wallet_ready,
        "settlement_backend": settlement_backend,
        "network_name": network_name,
        "full_host": full_host,
        "merchant_urls": merchant_urls,
        "buyer_address": values.get("AIMIPAY_BUYER_ADDRESS", ""),
        "token_address": token_address,
        "faucet_url": faucet_url,
        "funding_guide_url": funding_guide_url,
        "minimums": {
            "trx_balance_sun": min_trx_sun,
            "token_balance_atomic": min_token_atomic,
        },
        "funding_probe": None,
        "guidance": [],
        "checklist": [],
        "host_action": None,
    }

    if not wallet_ready:
        report["guidance"] = [
            "create a buyer wallet first with `python -m ops_tools.wallet_setup --force-create`",
        ]
        report["checklist"] = _build_checklist(report)
        report["host_action"] = _host_action(report, next_step="create_wallet")
    elif not full_host and merchant_urls:
        report["guidance"] = [
            "merchant-driven network mode is active; chain RPC and token settings will be resolved from the merchant manifest/discover endpoints",
            "connect to the merchant and run offer discovery before the first live funding check",
        ]
        report["checklist"] = _build_checklist(report)
        report["host_action"] = _host_action(report, next_step="connect_merchant")
    elif settlement_backend == "local_smoke":
        report["guidance"] = [
            "local_smoke demo does not require live Tron funding; you can run the local demo immediately",
            "for Nile or mainnet usage, fund the buyer wallet with TRX for gas and USDT for payments",
        ]
        report["checklist"] = _build_checklist(report)
        report["host_action"] = _host_action(report, next_step="ready_to_purchase")
    else:
        report["funding_probe"] = _probe_wallet_funding(
            repo_root=repo_root,
            full_host=full_host,
            buyer_address=values.get("AIMIPAY_BUYER_ADDRESS", ""),
            token_address=token_address,
            min_trx_sun=min_trx_sun,
            min_token_atomic=min_token_atomic,
        )
        report["guidance"] = _funding_guidance(
            report["funding_probe"],
            network_name=network_name,
            faucet_url=faucet_url,
            funding_guide_url=funding_guide_url,
        )
        report["checklist"] = _build_checklist(report)
        report["host_action"] = _host_action(report, next_step=_resolve_live_next_step(report))
    report["next_step"] = report["host_action"]["action"]
    report["action_required"] = None if report["next_step"] == "ready_to_purchase" else report["next_step"]

    if emit_output:
        if output_json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(_format_report(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect whether the local AimiPay buyer wallet looks ready to fund payments.")
    parser.add_argument("--repository-root")
    parser.add_argument("--env-file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = inspect_wallet_funding(
        repository_root=args.repository_root,
        env_file=args.env_file,
        output_json=args.json,
        emit_output=True,
    )
    return 0 if report["ok"] else 1


def _probe_wallet_funding(
    *,
    repo_root: Path,
    full_host: str,
    buyer_address: str,
    token_address: str,
    min_trx_sun: int,
    min_token_atomic: int,
) -> dict[str, Any]:
    node_path = shutil_which("node")
    script_path = repo_root / "scripts" / "check_wallet_balances.js"
    if not node_path:
        return {"status": "unavailable", "reason": "node not found"}
    if not script_path.exists():
        return {"status": "unavailable", "reason": f"missing script: {script_path}"}

    plan = {
        "full_host": full_host,
        "buyer_address": buyer_address,
        "token_address": token_address,
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(plan, handle)
        temp_plan = Path(handle.name)
    env = os.environ.copy()
    env["AIMICROPAY_PLAN_FILE"] = str(temp_plan)
    try:
        completed = subprocess.run(
            [node_path, str(script_path)],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    finally:
        temp_plan.unlink(missing_ok=True)
    if completed.returncode != 0:
        return {
            "status": "error",
            "reason": (completed.stderr or completed.stdout or "unknown funding probe error").strip(),
        }
    payload = json.loads(completed.stdout.strip())
    trx_balance_sun = int(payload.get("trx_balance_sun") or 0)
    token_balance_atomic = int(payload.get("token_balance_atomic") or 0)
    return {
        "status": "ok",
        "trx_balance_sun": trx_balance_sun,
        "token_balance_atomic": token_balance_atomic,
        "has_trx_for_gas": trx_balance_sun > 0,
        "has_token_balance": token_balance_atomic > 0 if payload.get("token_probe_status") == "ok" else None,
        "meets_min_trx_balance": trx_balance_sun >= min_trx_sun,
        "meets_min_token_balance": token_balance_atomic >= min_token_atomic if payload.get("token_probe_status") == "ok" else None,
        "token_probe_status": payload.get("token_probe_status"),
    }


def _funding_guidance(
    probe: dict[str, Any],
    *,
    network_name: str,
    faucet_url: str,
    funding_guide_url: str,
) -> list[str]:
    status = probe.get("status")
    if status != "ok":
        steps = [
            f"could not probe wallet balances automatically for {network_name}",
            "confirm the buyer wallet has TRX for gas and USDT for payments before using a live Tron environment",
        ]
        if faucet_url:
            steps.append(f"if this is a testnet, use the configured faucet: {faucet_url}")
        if funding_guide_url:
            steps.append(f"follow the funding guide: {funding_guide_url}")
        return steps
    steps: list[str] = []
    if not probe.get("has_trx_for_gas"):
        steps.append(f"fund the buyer wallet with TRX for gas on {network_name}")
    elif probe.get("meets_min_trx_balance") is False:
        steps.append("top up TRX; the wallet is funded but below the configured minimum gas balance")
    token_status = probe.get("has_token_balance")
    if token_status is False:
        steps.append("fund the buyer wallet with USDT on the configured token contract before purchasing")
    elif probe.get("meets_min_token_balance") is False:
        steps.append("top up USDT; the wallet is funded but below the configured minimum payment balance")
    elif token_status is None:
        steps.append("token balance was not probed; confirm USDT funding manually if you plan to buy paid capabilities")
    if faucet_url and (
        not probe.get("has_trx_for_gas")
        or token_status is False
        or probe.get("meets_min_trx_balance") is False
        or probe.get("meets_min_token_balance") is False
    ):
        steps.append(f"testnet faucet: {faucet_url}")
    if funding_guide_url:
        steps.append(f"funding guide: {funding_guide_url}")
    if not steps:
        steps.append("buyer wallet already shows non-zero TRX and token funding signals")
    return steps


def _read_env_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay Wallet Funding Check",
        f"- wallet ready: {report['wallet_ready']}",
        f"- settlement backend: {report['settlement_backend']}",
        f"- network name: {report['network_name']}",
        f"- buyer address: {report['buyer_address']}",
    ]
    if report.get("funding_probe"):
        lines.append(f"- funding probe: {report['funding_probe']}")
    minimums = report.get("minimums") or {}
    lines.append(f"- minimum trx balance (sun): {minimums.get('trx_balance_sun')}")
    lines.append(f"- minimum token balance (atomic): {minimums.get('token_balance_atomic')}")
    if report.get("guidance"):
        lines.append("- guidance:")
        lines.extend(f"  - {step}" for step in report["guidance"])
    checklist = report.get("checklist") or []
    if checklist:
        lines.append("- checklist:")
        lines.extend(f"  - {step}" for step in checklist)
    host_action = report.get("host_action") or {}
    if host_action:
        lines.append(f"- host action: {host_action.get('action')}")
    return "\n".join(lines)


def _build_checklist(report: dict[str, Any]) -> list[str]:
    checklist = [
        "confirm the buyer wallet address is saved and backed up locally",
    ]
    merchant_urls = list(report.get("merchant_urls") or [])
    if merchant_urls and not report.get("full_host"):
        checklist.append(f"confirm the merchant URL is correct: {merchant_urls[0]}")
        checklist.append("discover the merchant first so the buyer can resolve network settings automatically")
        return checklist
    if report.get("settlement_backend") == "local_smoke":
        checklist.append("run the local demo; live Tron funding is not required for local_smoke")
    else:
        checklist.append(f"confirm the buyer wallet is funded on {report.get('network_name')}")
        checklist.append("ensure the wallet has TRX for gas and USDT for payments")
        if report.get("faucet_url"):
            checklist.append(f"use the configured faucet if this is a testnet: {report['faucet_url']}")
        if report.get("funding_guide_url"):
            checklist.append(f"follow the funding guide: {report['funding_guide_url']}")
    return checklist


def _default_network_name(settlement_backend: str, full_host: str) -> str:
    lowered = (full_host or "").lower()
    if settlement_backend == "local_smoke":
        return "local-smoke"
    if "nile" in lowered:
        return "tron-nile"
    if "shasta" in lowered:
        return "tron-shasta"
    if "trongrid.io" in lowered or "tron" in lowered:
        return "tron"
    return "custom-tron"


def _resolve_live_next_step(report: dict[str, Any]) -> str:
    probe = report.get("funding_probe") or {}
    if probe.get("status") != "ok":
        return "fund_wallet"
    if probe.get("meets_min_trx_balance") is False or probe.get("meets_min_token_balance") is False:
        return "fund_wallet"
    return "ready_to_purchase"


def _host_action(report: dict[str, Any], *, next_step: str) -> dict[str, Any]:
    action_map = {
        "create_wallet": "Create a buyer wallet before the agent attempts paid purchases.",
        "fund_wallet": "Fund the buyer wallet with TRX gas and payment tokens before continuing.",
        "connect_merchant": "Connect to the merchant first; chain RPC and token settings will be discovered automatically.",
        "ready_to_purchase": "Wallet onboarding is complete; the agent can continue to budget checks and purchases.",
    }
    resources = []
    if report.get("faucet_url"):
        resources.append({"label": "Testnet Faucet", "url": report["faucet_url"]})
    if report.get("funding_guide_url"):
        resources.append({"label": "Funding Guide", "url": report["funding_guide_url"]})
    return {
        "action": next_step,
        "title": next_step.replace("_", " ").title(),
        "message": action_map[next_step],
        "network_name": report.get("network_name"),
        "buyer_address": report.get("buyer_address"),
        "checklist": list(report.get("checklist") or []),
        "resources": resources,
        "minimums": dict(report.get("minimums") or {}),
    }


def shutil_which(command: str) -> str | None:
    from shutil import which

    return which(command)


if __name__ == "__main__":
    raise SystemExit(main())

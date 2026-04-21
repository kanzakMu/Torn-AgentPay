from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from examples.env_loader import load_env_file
from shared.network_profiles import parse_env_file
from ops_tools.wallet_funding import inspect_wallet_funding
from ops_tools.wallet_setup import ensure_local_buyer_wallet


def run_agent_onboarding(
    *,
    repository_root: str | Path | None = None,
    env_file: str | Path | None = None,
    wallet_file: str | Path | None = None,
    force_create_wallet: bool = False,
    output_json: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    repo_root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    resolved_env = Path(env_file or repo_root / "python" / ".env.local").resolve()
    resolved_wallet = Path(wallet_file or repo_root / "python" / ".wallets" / "buyer-wallet.json").resolve()
    onboarding_file = repo_root / "python" / ".agent" / "onboarding-report.json"

    wallet = ensure_local_buyer_wallet(
        repository_root=repo_root,
        env_file=resolved_env,
        wallet_file=resolved_wallet,
        force_create=force_create_wallet,
        output_json=False,
        emit_output=False,
    )
    load_env_file(resolved_env, override=True)
    funding = inspect_wallet_funding(
        repository_root=repo_root,
        env_file=resolved_env,
        output_json=False,
        emit_output=False,
    )
    env_values = parse_env_file(resolved_env)
    merchant_urls = [item.strip() for item in env_values.get("AIMIPAY_MERCHANT_URLS", "").split(",") if item.strip()]
    merchant_probe = _probe_merchant_targets(merchant_urls)
    next_step = funding.get("next_step")
    action_required = funding.get("action_required")
    completed = funding.get("next_step") == "ready_to_purchase"
    if funding.get("next_step") in {"ready_to_purchase", "connect_merchant"}:
        if not merchant_urls:
            next_step = "connect_merchant"
            action_required = "connect_merchant"
            completed = False
        elif merchant_probe.get("offers", {}).get("count", 0) > 0:
            next_step = "review_offers"
            action_required = None
            completed = True
        elif merchant_probe.get("ok"):
            next_step = "discover_offers"
            action_required = None
            completed = True
    report = {
        "ok": True,
        "wallet": wallet,
        "funding": funding,
        "merchant": merchant_probe,
        "next_step": next_step,
        "action_required": action_required,
        "completed": completed,
    }
    onboarding_file.parent.mkdir(parents=True, exist_ok=True)
    onboarding_file.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    report["saved_report"] = str(onboarding_file)
    if emit_output:
        if output_json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(_format_report(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run first-start AimiPay agent onboarding.")
    parser.add_argument("--repository-root")
    parser.add_argument("--env-file")
    parser.add_argument("--wallet-file")
    parser.add_argument("--force-create-wallet", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_agent_onboarding(
        repository_root=args.repository_root,
        env_file=args.env_file,
        wallet_file=args.wallet_file,
        force_create_wallet=args.force_create_wallet,
        output_json=args.json,
        emit_output=True,
    )
    return 0 if report["ok"] else 1


def _format_report(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "AimiPay Agent Onboarding",
            f"- completed: {report['completed']}",
            f"- next step: {report['next_step']}",
            f"- action required: {report['action_required']}",
            f"- merchant urls: {', '.join((report.get('merchant') or {}).get('merchant_urls') or [])}",
            f"- saved report: {report['saved_report']}",
        ]
    )


def _probe_merchant_targets(merchant_urls: list[str]) -> dict[str, Any]:
    if not merchant_urls:
        return {
            "present": False,
            "merchant_urls": [],
            "host_action": {
                "action": "connect_merchant",
                "title": "Connect Merchant",
                "message": "Add the merchant URL you want this buyer to use before the first paid purchase.",
                "checklist": [
                    "Paste the merchant base URL into the buyer install form.",
                    "Reconnect so the buyer can fetch manifest and offer metadata.",
                ],
                "fields": [
                    {
                        "name": "merchant_url",
                        "label": "Merchant URL",
                        "type": "url",
                        "required": True,
                        "placeholder": "https://merchant.example",
                        "value": "",
                    }
                ],
                "resources": [],
            },
        }

    target_url = merchant_urls[0]
    payload: dict[str, Any] = {
        "present": True,
        "merchant_urls": merchant_urls,
        "selected_url": target_url,
        "ok": False,
        "service_name": None,
        "discover": None,
        "offers": {"count": 0, "items": []},
    }
    try:
        with httpx.Client(base_url=target_url.rstrip("/"), trust_env=_should_trust_env(target_url), timeout=5.0) as client:
            manifest_response = client.get("/.well-known/aimipay.json")
            manifest_response.raise_for_status()
            manifest = manifest_response.json()
            discover_url = manifest["endpoints"]["management"].rstrip("/") + "/discover"
            discover_response = client.get(discover_url)
            discover_response.raise_for_status()
            discover = discover_response.json()
    except Exception as exc:
        payload["error"] = str(exc)
        payload["host_action"] = {
            "action": "connect_merchant",
            "title": "Check Merchant URL",
            "message": "The configured merchant URL did not return a valid AimiPay manifest yet.",
            "checklist": [
                f"Confirm the merchant URL is correct: {target_url}",
                "Make sure the merchant runtime is running and exposes /.well-known/aimipay.json.",
            ],
            "fields": [
                {
                    "name": "merchant_url",
                    "label": "Merchant URL",
                    "type": "url",
                    "required": True,
                    "value": target_url,
                }
            ],
            "resources": [],
        }
        return payload

    offers = []
    for route in manifest.get("routes", []):
        offers.append(
            {
                "capability_id": route.get("capability_id") or route.get("path"),
                "route_path": route.get("path"),
                "capability_type": route.get("capability_type", "api"),
                "price_atomic": route.get("price_atomic", 0),
            }
        )
    payload.update(
        {
            "ok": True,
            "service_name": manifest.get("service_name"),
            "discover": {
                "chain": discover.get("chain"),
                "settlement_backend": discover.get("settlement_backend"),
                "contract_address": discover.get("contract_address"),
                "token_address": discover.get("token_address"),
            },
            "offers": {
                "count": len(offers),
                "items": offers[:5],
            },
            "host_action": {
                "action": "review_offers" if offers else "discover_offers",
                "title": "Merchant Connected",
                "message": f"Connected to {manifest.get('service_name') or target_url} and loaded offer metadata.",
                "checklist": [
                    f"Merchant URL: {target_url}",
                    f"Offers discovered: {len(offers)}",
                ],
                "fields": [
                    {
                        "name": "merchant_url",
                        "label": "Merchant URL",
                        "type": "url",
                        "required": True,
                        "value": target_url,
                    }
                ],
                "resources": [
                    {"label": "Manifest", "url": f"{target_url.rstrip('/')}/.well-known/aimipay.json"},
                    {"label": "Discover", "url": discover_url},
                ],
                "offers_preview": offers[:3],
            },
        }
    )
    return payload


def _should_trust_env(base_url: str) -> bool:
    from urllib.parse import urlparse

    host = (urlparse(base_url).hostname or "").lower()
    return host not in {"127.0.0.1", "localhost", "::1"}


if __name__ == "__main__":
    raise SystemExit(main())

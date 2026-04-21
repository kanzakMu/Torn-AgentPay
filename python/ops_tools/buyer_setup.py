from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shared.network_profiles import MANAGED_NETWORK_KEYS, apply_network_profile_to_values, parse_env_file, write_env_file


def prepare_buyer_install_env(
    *,
    repository_root: str | Path | None = None,
    env_file: str | Path | None = None,
    merchant_urls: list[str] | None = None,
    network_profile: str | None = None,
    output_json: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    env_path = Path(env_file or root / "python" / ".env.local").resolve()
    values = parse_env_file(env_path)

    target_urls = [item.strip() for item in (merchant_urls or []) if item.strip()]
    if target_urls:
        values["AIMIPAY_MERCHANT_URLS"] = ",".join(target_urls)
    elif "AIMIPAY_MERCHANT_URLS" not in values:
        values["AIMIPAY_MERCHANT_URLS"] = "http://127.0.0.1:8000"

    profile = None
    if network_profile:
        values, profile = apply_network_profile_to_values(
            values,
            profile_name=network_profile,
            repository_root=root,
        )
    elif target_urls:
        values["AIMIPAY_NETWORK_PROFILE"] = "custom"
        for key in MANAGED_NETWORK_KEYS:
            values[key] = ""

    write_env_file(env_path, values)
    report = {
        "ok": True,
        "env_file": str(env_path),
        "merchant_urls": target_urls or [item.strip() for item in values["AIMIPAY_MERCHANT_URLS"].split(",") if item.strip()],
        "network_profile": values.get("AIMIPAY_NETWORK_PROFILE"),
        "full_host": values.get("AIMIPAY_FULL_HOST", ""),
        "profile_ready": profile.get("profile_ready", True) if profile else None,
    }
    if emit_output:
        if output_json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(_format_report(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare the buyer install env with merchant URLs and an optional network profile.")
    parser.add_argument("--repository-root")
    parser.add_argument("--env-file")
    parser.add_argument("--merchant-url", action="append", dest="merchant_urls")
    parser.add_argument("--network-profile")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = prepare_buyer_install_env(
        repository_root=args.repository_root,
        env_file=args.env_file,
        merchant_urls=args.merchant_urls,
        network_profile=args.network_profile,
        output_json=args.json,
        emit_output=True,
    )
    return 0 if report["ok"] else 1


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay Buyer Setup",
        f"- env file: {report['env_file']}",
        f"- merchant urls: {', '.join(report['merchant_urls'])}",
        f"- network profile: {report.get('network_profile') or 'none'}",
    ]
    if report.get("full_host"):
        lines.append(f"- chain rpc: {report['full_host']}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

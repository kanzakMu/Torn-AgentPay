from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ops_tools.install_agent_package import install_agent_package


HOST_CHOICES = ["codex", "mcp", "claude", "cua", "openclaw", "hermes", "all", "skill"]


def install_ai_host(
    *,
    repository_root: str | Path | None = None,
    host: str = "codex",
    mode: str = "home-local",
    install_root: str | Path | None = None,
    merchant_url: str | None = None,
    full_host: str | None = None,
    env_file: str | Path | None = None,
    run_verify: bool = True,
    run_onboarding: bool = True,
    output_json: bool = False,
) -> dict[str, Any]:
    report = install_agent_package(
        repository_root=repository_root,
        target=host,
        mode=mode,
        install_root=install_root,
        merchant_url=merchant_url,
        full_host=full_host,
        env_file=env_file,
        run_verify=run_verify,
        run_onboarding=run_onboarding,
        output_json=False,
    )
    host_report = {
        "ok": report["ok"],
        "host": host,
        "mode": report["mode"],
        "installed": report["installed"],
        "generated_host_configs": report["generated_host_configs"],
        "install_report_path": report.get("install_report_path"),
        "next_steps_path": report.get("next_steps_path"),
        "next_steps": report.get("next_steps", []),
        "startup_onboarding": report.get("startup_onboarding"),
    }
    if output_json:
        print(json.dumps(host_report, indent=2, sort_keys=True))
    else:
        print(_format_host_report(host_report))
    return host_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-command installer for external AI hosts.")
    parser.add_argument("--repository-root")
    parser.add_argument("--host", choices=HOST_CHOICES, default="codex")
    parser.add_argument("--mode", choices=["repo-local", "home-local"], default="home-local")
    parser.add_argument("--install-root")
    parser.add_argument("--merchant-url")
    parser.add_argument("--full-host")
    parser.add_argument("--env-file")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--skip-onboarding", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = install_ai_host(
        repository_root=args.repository_root,
        host=args.host,
        mode=args.mode,
        install_root=args.install_root,
        merchant_url=args.merchant_url,
        full_host=args.full_host,
        env_file=args.env_file,
        run_verify=not args.skip_verify,
        run_onboarding=not args.skip_onboarding,
        output_json=args.json,
    )
    return 0 if report["ok"] else 1


def _format_host_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay External AI Host Installer",
        f"- ok: {report['ok']}",
        f"- host: {report['host']}",
        f"- mode: {report['mode']}",
    ]
    for key, value in report.get("installed", {}).items():
        lines.append(f"- installed {key}: {value}")
    for key, value in report.get("generated_host_configs", {}).items():
        lines.append(f"- generated {key} config: {value}")
    if report.get("next_steps_path"):
        lines.append(f"- next steps guide: {report['next_steps_path']}")
    for item in report.get("next_steps", []):
        lines.append(f"- next action [{item['target']}]: {item['action']}")
    onboarding = report.get("startup_onboarding")
    if onboarding:
        lines.append(f"- onboarding next step: {onboarding.get('next_step')}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

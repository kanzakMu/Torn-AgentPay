from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ops_tools.install_agent_package import install_agent_package


def install_aimipay_skill(
    *,
    repository_root: str | Path | None = None,
    mode: str = "home-local",
    install_root: str | Path | None = None,
    merchant_url: str | None = None,
    env_file: str | Path | None = None,
    run_verify: bool = True,
    output_json: bool = False,
) -> dict[str, Any]:
    report = install_agent_package(
        repository_root=repository_root,
        target="skill",
        mode=mode,
        install_root=install_root,
        merchant_url=merchant_url,
        env_file=env_file,
        run_verify=run_verify,
        run_onboarding=False,
        output_json=False,
    )
    skill_report = {
        "ok": report["ok"],
        "mode": report["mode"],
        "skill_path": report["installed"].get("skill"),
        "merchant_url": merchant_url,
        "verify": report.get("verify"),
        "next_step": "restart_agent_or_reload_skills",
    }
    if output_json:
        print(json.dumps(skill_report, indent=2, sort_keys=True))
    else:
        print(_format_skill_report(skill_report))
    return skill_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install only the AimiPay Codex skill.")
    parser.add_argument("--repository-root")
    parser.add_argument("--mode", choices=["repo-local", "home-local"], default="home-local")
    parser.add_argument("--install-root")
    parser.add_argument("--merchant-url")
    parser.add_argument("--env-file")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = install_aimipay_skill(
        repository_root=args.repository_root,
        mode=args.mode,
        install_root=args.install_root,
        merchant_url=args.merchant_url,
        env_file=args.env_file,
        run_verify=not args.skip_verify,
        output_json=args.json,
    )
    return 0 if report["ok"] else 1


def _format_skill_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay Skill Install",
        f"- ok: {report['ok']}",
        f"- mode: {report['mode']}",
        f"- skill path: {report.get('skill_path') or 'not installed'}",
        f"- next step: {report['next_step']}",
    ]
    if report.get("merchant_url"):
        lines.append(f"- merchant url: {report['merchant_url']}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

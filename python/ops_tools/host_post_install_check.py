from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from ops_tools.install_agent_package import _expand_target, _target_layout
from ops_tools.verify_agent_installation import verify_agent_installation


def run_host_post_install_check(
    *,
    repository_root: str | Path | None = None,
    host: str = "codex",
    mode: str = "home-local",
    install_root: str | Path | None = None,
    expected_targets: list[str] | None = None,
    run_protocol_smoke: bool = True,
    output_json: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    install_plan = set(expected_targets or _expand_target(host))
    layout = _target_layout(mode=mode, repo_root=repo_root, install_root=install_root)
    verify = verify_agent_installation(
        repository_root=repo_root,
        mode=mode,
        install_root=install_root,
        expected_targets=sorted(install_plan),
        output_json=False,
    )
    checks: list[dict[str, Any]] = []
    checks.extend(_prefix_checks("verify", verify.get("checks", [])))

    if "skill" in install_plan:
        checks.extend(_skill_doctor_checks(layout["skill_root"] / "aimipay-agent"))

    if "connector" in install_plan:
        checks.extend(_capability_manifest_checks(layout["connector_root"] / "aimipay.capabilities.json"))

    smoke: dict[str, Any] | None = None
    if run_protocol_smoke:
        from ops_tools.ai_host_smoke import run_ai_host_smoke

        smoke = run_ai_host_smoke(output_json=False)
        checks.append(
            {
                "name": "protocol_smoke",
                "ok": bool(smoke.get("ok")),
                "detail": "AI-facing manifest/state/offers/quote/plan/recovery smoke",
            }
        )

    failed = [item for item in checks if not item.get("ok")]
    report = {
        "schema_version": "aimipay.post-install-check.v1",
        "ok": not failed,
        "host": host,
        "mode": mode,
        "repository_root": str(repo_root),
        "expected_targets": sorted(install_plan),
        "checks": checks,
        "failed": failed,
        "verify": {
            "ok": verify.get("ok"),
            "expected_targets": verify.get("expected_targets"),
            "target_root": verify.get("target_root"),
        },
        "protocol_smoke": _smoke_summary(smoke) if smoke else None,
        "next_actions": _next_actions(failed),
    }
    if output_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_format_report(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run post-install self-checks for an external AimiPay AI host install.")
    parser.add_argument("--repository-root")
    parser.add_argument("--host", default="codex")
    parser.add_argument("--mode", choices=["repo-local", "home-local"], default="home-local")
    parser.add_argument("--install-root")
    parser.add_argument("--expected-target", action="append", dest="expected_targets")
    parser.add_argument("--skip-protocol-smoke", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_host_post_install_check(
        repository_root=args.repository_root,
        host=args.host,
        mode=args.mode,
        install_root=args.install_root,
        expected_targets=args.expected_targets,
        run_protocol_smoke=not args.skip_protocol_smoke,
        output_json=args.json,
    )
    return 0 if report["ok"] else 1


def _prefix_checks(prefix: str, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": f"{prefix}.{item.get('name')}",
            "ok": bool(item.get("ok")),
            "detail": item.get("detail", ""),
        }
        for item in checks
    ]


def _skill_doctor_checks(skill_root: Path) -> list[dict[str, Any]]:
    runtime_config_path = skill_root / "skill-runtime.json"
    runner_path = skill_root / "aimipay_skill_runner.py"
    checks = [
        {"name": "skill.runtime_config_present", "ok": runtime_config_path.exists(), "detail": str(runtime_config_path)},
        {"name": "skill.runner_present", "ok": runner_path.exists(), "detail": str(runner_path)},
    ]
    if not runtime_config_path.exists() or not runner_path.exists():
        return checks

    try:
        config = json.loads(runtime_config_path.read_text(encoding="utf-8"))
        spec = importlib.util.spec_from_file_location("aimipay_installed_skill_runner", runner_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load installed skill runner")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        doctor = module._doctor_payload(config, runtime_config_path)
        checks.append(
            {
                "name": "skill.doctor_ok",
                "ok": bool(doctor.get("ok")),
                "detail": json.dumps(
                    {
                        "next_actions": doctor.get("next_actions", []),
                        "available_commands": doctor.get("available_commands", []),
                    },
                    sort_keys=True,
                ),
            }
        )
        checks.append(
            {
                "name": "skill.protocol_manifest_command_present",
                "ok": "protocol-manifest" in set(doctor.get("available_commands", [])),
                "detail": ",".join(doctor.get("available_commands", [])),
            }
        )
    except Exception as exc:
        checks.append({"name": "skill.doctor_ok", "ok": False, "detail": str(exc)})
    return checks


def _capability_manifest_checks(path: Path) -> list[dict[str, Any]]:
    checks = [{"name": "connector.capability_manifest_present", "ok": path.exists(), "detail": str(path)}]
    if not path.exists():
        return checks
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        checks.extend(
            [
                {
                    "name": "connector.capability_manifest_schema",
                    "ok": payload.get("schema_version") == "aimipay.capabilities.v1",
                    "detail": str(payload.get("schema_version")),
                },
                {
                    "name": "connector.capability_manifest_has_state_flow",
                    "ok": "aimipay.get_agent_state" in set(payload.get("default_flow", [])),
                    "detail": ",".join(payload.get("default_flow", [])),
                },
                {
                    "name": "connector.capability_manifest_has_recovery",
                    "ok": bool(payload.get("error_recovery_actions", {}).get("settlement_pending")),
                    "detail": "settlement_pending",
                },
            ]
        )
    except Exception as exc:
        checks.append({"name": "connector.capability_manifest_schema", "ok": False, "detail": str(exc)})
    return checks


def _smoke_summary(smoke: dict[str, Any] | None) -> dict[str, Any] | None:
    if smoke is None:
        return None
    return {
        "ok": smoke.get("ok"),
        "schema_version": smoke.get("schema_version"),
        "assertions": smoke.get("assertions", []),
    }


def _next_actions(failed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not failed:
        return [
            {
                "action": "restart_or_reload_host",
                "reason": "Installed artifacts and AI-facing protocol smoke checks passed.",
            }
        ]
    return [
        {
            "action": "inspect_failed_checks",
            "reason": f"{len(failed)} post-install checks failed.",
            "failed_checks": [item.get("name") for item in failed],
        }
    ]


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay Post-Install Self Check",
        f"- ok: {report['ok']}",
        f"- host: {report['host']}",
        f"- mode: {report['mode']}",
    ]
    for item in report.get("checks", []):
        state = "ok" if item.get("ok") else "failed"
        lines.append(f"- {item['name']}: {state} ({item.get('detail', '')})")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

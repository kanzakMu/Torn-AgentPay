from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any


HOST_TARGETS = {"codex", "mcp", "claude", "cua", "openclaw", "hermes"}
BASE_TARGETS = {"skill", "plugin", "connector"}
HOST_CONFIG_NAMES = {
    "codex": ("codex", "codex-package.json"),
    "mcp": ("mcp", "generic_mcp_server.json"),
    "claude": ("claude", "claude_desktop_config.json"),
    "cua": ("cua", "cua_mcp_config.json"),
    "openclaw": ("openclaw", "openclaw_mcp_config.json"),
    "hermes": ("hermes", "hermes_mcp_config.json"),
}


def install_agent_package(
    *,
    repository_root: str | Path | None = None,
    target: str = "all",
    mode: str = "repo-local",
    install_root: str | Path | None = None,
    merchant_url: str | None = None,
    full_host: str | None = None,
    env_file: str | Path | None = None,
    run_verify: bool = True,
    run_onboarding: bool = True,
    output_json: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    layout = _target_layout(mode=mode, repo_root=repo_root, install_root=install_root)
    install_plan = _expand_target(target)
    env_values = _install_env_values(
        repo_root=repo_root,
        merchant_url=merchant_url,
        full_host=full_host,
        env_file=env_file,
    )
    source_skill = repo_root / "skills" / "aimipay-agent"
    source_plugin = repo_root / "plugins" / "aimipay-agent"
    source_marketplace = repo_root / ".agents" / "plugins" / "marketplace.json"
    source_connector = repo_root / "agent-dist" / "connector-package.json"
    source_core = repo_root / "agent-dist" / "aimipay-agent-core.json"
    installed: dict[str, str] = {}
    generated_host_configs: dict[str, str] = {}

    if "skill" in install_plan:
        skill_dest = layout["skill_root"] / "aimipay-agent"
        _copy_tree(source_skill, skill_dest)
        _write_skill_runtime_config(
            skill_dest,
            repo_root=repo_root,
            env_values=env_values,
            env_file=env_file,
        )
        installed["skill"] = str(skill_dest)

    if "plugin" in install_plan:
        plugin_dest = layout["plugin_root"] / "aimipay-agent"
        _copy_tree(source_plugin, plugin_dest)
        installed["plugin"] = str(plugin_dest)
        marketplace_dest = layout["marketplace_path"]
        marketplace_dest.parent.mkdir(parents=True, exist_ok=True)
        marketplace_dest.write_text(source_marketplace.read_text(encoding="utf-8"), encoding="utf-8")
        installed["marketplace"] = str(marketplace_dest)
        _patch_plugin_mcp(
            plugin_dest / ".mcp.json",
            repo_root=repo_root,
            env_values=env_values,
        )

    if "connector" in install_plan:
        connector_dest = layout["connector_root"] / "connector-package.json"
        connector_dest.parent.mkdir(parents=True, exist_ok=True)
        connector_dest.write_text(source_connector.read_text(encoding="utf-8"), encoding="utf-8")
        installed["connector"] = str(connector_dest)
        core_dest = layout["connector_root"] / "aimipay-agent-core.json"
        core_dest.write_text(source_core.read_text(encoding="utf-8"), encoding="utf-8")
        installed["agent_core"] = str(core_dest)

    for host_target in sorted(HOST_TARGETS & install_plan):
        generated = _generate_host_config(
            host_target=host_target,
            repo_root=repo_root,
            host_root=layout["host_config_root"],
            env_values=env_values,
            plugin_root=layout["plugin_root"],
            skill_root=layout["skill_root"],
            connector_root=layout["connector_root"],
        )
        generated_host_configs[host_target] = str(generated)

    report: dict[str, Any] = {
        "ok": True,
        "mode": mode,
        "requested_target": target,
        "install_plan": sorted(install_plan),
        "environment": env_values,
        "target_root": {key: str(value) for key, value in layout.items()},
        "installed": installed,
        "generated_host_configs": generated_host_configs,
    }
    report["next_steps"] = _build_next_steps(report)

    if run_verify:
        from ops_tools.verify_agent_installation import verify_agent_installation

        verify_report = verify_agent_installation(
            repository_root=repo_root,
            mode=mode,
            install_root=install_root,
            expected_targets=sorted(install_plan),
            output_json=False,
        )
        report["verify"] = verify_report
        report["ok"] = report["ok"] and verify_report["ok"]

    if run_onboarding:
        from ops_tools.agent_onboarding import run_agent_onboarding
        from ops_tools.buyer_setup import prepare_buyer_install_env

        target_env_file = Path(env_file).resolve() if env_file else (repo_root / "python" / ".env.local")
        prepare_buyer_install_env(
            repository_root=repo_root,
            env_file=target_env_file,
            merchant_urls=env_values["AIMIPAY_MERCHANT_URLS"].split(","),
            output_json=False,
            emit_output=False,
        )

        onboarding_report = run_agent_onboarding(
            repository_root=repo_root,
            env_file=target_env_file,
            output_json=False,
            emit_output=False,
        )
        report["startup_onboarding"] = onboarding_report

    report["next_steps"] = _build_next_steps(report)
    report["install_report_path"] = str(_write_install_report(layout["host_config_root"], report))
    report["next_steps_path"] = str(_write_next_steps_markdown(layout["host_config_root"], report))

    if output_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_format_report(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install the AimiPay package for AI agent hosts.")
    parser.add_argument("--repository-root")
    parser.add_argument(
        "--target",
        choices=[
            "all",
            "skill",
            "plugin",
            "connector",
            "codex",
            "mcp",
            "claude",
            "cua",
            "openclaw",
            "hermes",
        ],
        default="all",
    )
    parser.add_argument("--mode", choices=["repo-local", "home-local"], default="repo-local")
    parser.add_argument("--install-root")
    parser.add_argument("--merchant-url")
    parser.add_argument("--full-host")
    parser.add_argument("--env-file")
    parser.add_argument("--skip-verify", action="store_true")
    parser.add_argument("--skip-onboarding", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    install_agent_package(
        repository_root=args.repository_root,
        target=args.target,
        mode=args.mode,
        install_root=args.install_root,
        merchant_url=args.merchant_url,
        full_host=args.full_host,
        env_file=args.env_file,
        run_verify=not args.skip_verify,
        run_onboarding=not args.skip_onboarding,
        output_json=args.json,
    )
    return 0


def _expand_target(target: str) -> set[str]:
    if target == "all":
        return set(BASE_TARGETS | HOST_TARGETS)
    if target == "codex":
        return {"skill", "plugin", "connector", "codex"}
    if target == "mcp":
        return {"connector", "mcp"}
    if target in {"claude", "cua", "openclaw", "hermes"}:
        return {"connector", target}
    return {target}


def _target_layout(*, mode: str, repo_root: Path, install_root: str | Path | None) -> dict[str, Path]:
    if mode == "repo-local":
        return {
            "skill_root": repo_root / "skills",
            "plugin_root": repo_root / "plugins",
            "marketplace_path": repo_root / ".agents" / "plugins" / "marketplace.json",
            "connector_root": repo_root / "agent-dist",
            "host_config_root": repo_root / "agent-dist" / "generated-hosts",
        }
    if install_root is not None:
        base = Path(install_root).resolve()
        codex_home = base / ".codex"
        home_root = base
    else:
        home_root = Path.home()
        codex_home = Path(os.environ.get("CODEX_HOME", home_root / ".codex")).resolve()
    return {
        "skill_root": codex_home / "skills",
        "plugin_root": home_root / "plugins",
        "marketplace_path": home_root / ".agents" / "plugins" / "marketplace.json",
        "connector_root": codex_home / "agent-dist",
        "host_config_root": codex_home / "agent-hosts",
    }


def _copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def _patch_plugin_mcp(mcp_path: Path, *, repo_root: Path, env_values: dict[str, str]) -> None:
    payload = json.loads(mcp_path.read_text(encoding="utf-8"))
    server = payload["mcpServers"]["aimipay-agent"]
    server["command"] = sys.executable
    server["env"] = _server_env(repo_root=repo_root, env_values=env_values, existing=server.get("env"))
    mcp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_skill_runtime_config(
    skill_root: Path,
    *,
    repo_root: Path,
    env_values: dict[str, str],
    env_file: str | Path | None,
) -> None:
    runtime_config = {
        "schema_version": "aimipay.skill-runtime.v1",
        "repository_root": str(repo_root),
        "python_executable": sys.executable,
        "env_file": str(Path(env_file).resolve() if env_file else repo_root / "python" / ".env.local"),
        "merchant_urls": [
            item.strip()
            for item in env_values.get("AIMIPAY_MERCHANT_URLS", "").split(",")
            if item.strip()
        ],
        "full_host": env_values.get("AIMIPAY_FULL_HOST"),
        "runner": "aimipay_skill_runner.py",
    }
    (skill_root / "skill-runtime.json").write_text(
        json.dumps(runtime_config, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _generate_host_config(
    *,
    host_target: str,
    repo_root: Path,
    host_root: Path,
    env_values: dict[str, str],
    plugin_root: Path,
    skill_root: Path,
    connector_root: Path,
) -> Path:
    if host_target == "codex":
        payload = {
            "name": "aimipay-codex-package",
            "plugin_root": str(plugin_root / "aimipay-agent"),
            "skill_root": str(skill_root / "aimipay-agent"),
            "connector_manifest": str(connector_root / "connector-package.json"),
            "entrypoint": {
                "command": sys.executable,
                "args": ["-m", "agent_entrypoints.aimipay_mcp_stdio"],
                "env": _server_env(repo_root=repo_root, env_values=env_values),
            },
            "startup_hint": {
                "merchant_urls": env_values["AIMIPAY_MERCHANT_URLS"].split(","),
                "merchant_driven": True,
            },
        }
        destination = host_root / "codex" / "codex-package.json"
        return _write_json(destination, payload)

    template_map = {
        "mcp": repo_root / "agent-dist" / "hosts" / "generic" / "generic_mcp_server.template.json",
        "claude": repo_root / "agent-dist" / "hosts" / "claude-desktop" / "claude_desktop_config.template.json",
        "cua": repo_root / "agent-dist" / "hosts" / "cua" / "cua_mcp_config.template.json",
        "openclaw": repo_root / "agent-dist" / "hosts" / "openclaw" / "openclaw_mcp_config.template.json",
        "hermes": repo_root / "agent-dist" / "hosts" / "hermes" / "hermes_mcp_config.template.json",
    }
    destination_name = {
        "mcp": "generic_mcp_server.json",
        "claude": "claude_desktop_config.json",
        "cua": "cua_mcp_config.json",
        "openclaw": "openclaw_mcp_config.json",
        "hermes": "hermes_mcp_config.json",
    }[host_target]
    payload = json.loads(template_map[host_target].read_text(encoding="utf-8"))
    _patch_host_template(payload, repo_root=repo_root, env_values=env_values)
    destination = host_root / host_target / destination_name
    return _write_json(destination, payload)


def _patch_host_template(payload: dict[str, Any], *, repo_root: Path, env_values: dict[str, str]) -> None:
    patched_env = _server_env(repo_root=repo_root, env_values=env_values)
    if "mcpServers" in payload:
        for server in payload["mcpServers"].values():
            server["command"] = sys.executable
            server["env"] = patched_env
    elif "servers" in payload:
        for server in payload["servers"]:
            server["command"] = sys.executable
            server["env"] = patched_env


def _server_env(
    *,
    repo_root: Path,
    env_values: dict[str, str],
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(existing or {})
    payload["PYTHONPATH"] = os.pathsep.join([str(repo_root / "python"), str(repo_root / "python" / ".vendor")])
    payload["AIMIPAY_REPOSITORY_ROOT"] = str(repo_root)
    payload["AIMIPAY_MERCHANT_URLS"] = env_values["AIMIPAY_MERCHANT_URLS"]
    if env_values.get("AIMIPAY_FULL_HOST"):
        payload["AIMIPAY_FULL_HOST"] = env_values["AIMIPAY_FULL_HOST"]
    else:
        payload.pop("AIMIPAY_FULL_HOST", None)
    if env_values.get("AIMIPAY_BUYER_ADDRESS"):
        payload["AIMIPAY_BUYER_ADDRESS"] = env_values["AIMIPAY_BUYER_ADDRESS"]
    if env_values.get("AIMIPAY_BUYER_PRIVATE_KEY"):
        payload["AIMIPAY_BUYER_PRIVATE_KEY"] = env_values["AIMIPAY_BUYER_PRIVATE_KEY"]
    return payload


def _install_env_values(
    *,
    repo_root: Path,
    merchant_url: str | None,
    full_host: str | None,
    env_file: str | Path | None,
) -> dict[str, str]:
    values = _read_env_values(Path(env_file).resolve()) if env_file else _read_env_values(repo_root / "python" / ".env.local")
    resolved = {
        "AIMIPAY_MERCHANT_URLS": merchant_url or values.get("AIMIPAY_MERCHANT_URLS", "http://127.0.0.1:8000"),
        "AIMIPAY_FULL_HOST": full_host or values.get("AIMIPAY_FULL_HOST", ""),
        "AIMIPAY_BUYER_ADDRESS": values.get("AIMIPAY_BUYER_ADDRESS", ""),
        "AIMIPAY_BUYER_PRIVATE_KEY": values.get("AIMIPAY_BUYER_PRIVATE_KEY", ""),
    }
    return resolved


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


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay Agent Package Installer",
        f"- mode: {report['mode']}",
        f"- requested target: {report['requested_target']}",
        f"- install plan: {', '.join(report['install_plan'])}",
    ]
    for key, value in report.get("installed", {}).items():
        lines.append(f"- installed {key}: {value}")
    for key, value in report.get("generated_host_configs", {}).items():
        lines.append(f"- generated {key} config: {value}")
    verify = report.get("verify")
    if verify is not None:
        lines.append(f"- verify ok: {verify['ok']}")
    onboarding = report.get("startup_onboarding")
    if onboarding is not None:
        lines.append(f"- startup onboarding next step: {onboarding.get('next_step')}")
    if report.get("install_report_path"):
        lines.append(f"- install report: {report['install_report_path']}")
    if report.get("next_steps_path"):
        lines.append(f"- next steps: {report['next_steps_path']}")
    for item in report.get("next_steps", []):
        lines.append(f"- next action [{item['target']}]: {item['action']}")
    return "\n".join(lines)


def _build_next_steps(report: dict[str, Any]) -> list[dict[str, Any]]:
    installed = report.get("installed", {})
    generated = report.get("generated_host_configs", {})
    steps: list[dict[str, Any]] = []
    if "skill" in installed:
        skill_path = Path(installed["skill"])
        steps.append(
            {
                "target": "skill",
                "action": "reload_or_restart_agent_skills",
                "path": str(skill_path),
                "runner": str(skill_path / "aimipay_skill_runner.py"),
                "example": f'python "{skill_path / "aimipay_skill_runner.py"}" get-agent-state',
            }
        )
    if "codex" in generated:
        steps.append(
            {
                "target": "codex",
                "action": "restart_codex_or_import_generated_package",
                "path": generated["codex"],
                "note": "Codex can use the installed skill, plugin, connector manifest, and MCP entrypoint from this package.",
            }
        )
    if "mcp" in generated:
        steps.append(
            {
                "target": "mcp",
                "action": "point_mcp_host_to_generated_config",
                "path": generated["mcp"],
                "note": "Use this generic MCP server config if the host accepts a standalone MCP JSON file.",
            }
        )
    for target in ["claude", "cua", "openclaw", "hermes"]:
        if target in generated:
            steps.append(
                {
                    "target": target,
                    "action": "merge_generated_mcp_config_then_restart_host",
                    "path": generated[target],
                    "note": f"Merge or copy this generated config into the {target} host configuration, then restart the host.",
                }
            )
    return steps


def _write_install_report(host_root: Path, report: dict[str, Any]) -> Path:
    path = host_root / "aimipay-install-report.json"
    payload = dict(report)
    payload.pop("verify", None)
    return _write_json(path, payload)


def _write_next_steps_markdown(host_root: Path, report: dict[str, Any]) -> Path:
    path = host_root / "aimipay-install-next-steps.md"
    lines = [
        "# AimiPay Agent Host Install",
        "",
        f"- ok: {report.get('ok')}",
        f"- mode: {report.get('mode')}",
        f"- requested target: {report.get('requested_target')}",
        f"- install plan: {', '.join(report.get('install_plan') or [])}",
        "",
        "## Installed Artifacts",
    ]
    for key, value in (report.get("installed") or {}).items():
        lines.append(f"- {key}: `{value}`")
    if report.get("generated_host_configs"):
        lines.extend(["", "## Generated Host Configs"])
        for key, value in report["generated_host_configs"].items():
            lines.append(f"- {key}: `{value}`")
    if report.get("next_steps"):
        lines.extend(["", "## Next Steps"])
        for item in report["next_steps"]:
            lines.append(f"- `{item['target']}`: {item['action']}")
            if item.get("path"):
                lines.append(f"  path: `{item['path']}`")
            if item.get("example"):
                lines.append(f"  example: `{item['example']}`")
            if item.get("note"):
                lines.append(f"  note: {item['note']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())

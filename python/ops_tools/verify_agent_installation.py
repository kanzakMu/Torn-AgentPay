from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ops_tools.install_agent_package import _expand_target, _target_layout


HOST_CONFIG_FILES = {
    "codex": ("codex", "codex-package.json"),
    "mcp": ("mcp", "generic_mcp_server.json"),
    "claude": ("claude", "claude_desktop_config.json"),
    "cua": ("cua", "cua_mcp_config.json"),
    "openclaw": ("openclaw", "openclaw_mcp_config.json"),
    "hermes": ("hermes", "hermes_mcp_config.json"),
}


def verify_agent_installation(
    *,
    repository_root: str | Path | None = None,
    mode: str = "home-local",
    install_root: str | Path | None = None,
    expected_targets: list[str] | None = None,
    output_json: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    layout = _target_layout(mode=mode, repo_root=repo_root, install_root=install_root)
    install_plan = set(expected_targets or _expand_target("all"))

    skill_path = layout["skill_root"] / "aimipay-agent" / "SKILL.md"
    plugin_root = layout["plugin_root"] / "aimipay-agent"
    plugin_manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    plugin_mcp_path = plugin_root / ".mcp.json"
    marketplace_path = layout["marketplace_path"]
    connector_path = layout["connector_root"] / "connector-package.json"
    core_path = layout["connector_root"] / "aimipay-agent-core.json"
    capability_manifest_path = layout["connector_root"] / "aimipay.capabilities.json"

    checks = []
    details: dict[str, Any] = {}

    if "skill" in install_plan:
        checks.append(_check("skill_installed", skill_path.exists(), str(skill_path)))
    if "plugin" in install_plan:
        checks.extend(
            [
                _check("plugin_manifest_installed", plugin_manifest_path.exists(), str(plugin_manifest_path)),
                _check("plugin_mcp_installed", plugin_mcp_path.exists(), str(plugin_mcp_path)),
                _check("marketplace_present", marketplace_path.exists(), str(marketplace_path)),
            ]
        )
    if "connector" in install_plan:
        checks.extend(
            [
                _check("connector_installed", connector_path.exists(), str(connector_path)),
                _check("agent_core_installed", core_path.exists(), str(core_path)),
                _check("capability_manifest_installed", capability_manifest_path.exists(), str(capability_manifest_path)),
            ]
        )
        if capability_manifest_path.exists():
            capability_manifest = json.loads(capability_manifest_path.read_text(encoding="utf-8"))
            details["capability_manifest"] = capability_manifest
            checks.extend(
                [
                    _check(
                        "capability_manifest_schema_expected",
                        capability_manifest.get("schema_version") == "aimipay.capabilities.v1",
                        str(capability_manifest.get("schema_version", "")),
                    ),
                    _check(
                        "capability_manifest_has_protocol_manifest_tool",
                        any(
                            item.get("name") == "aimipay.get_protocol_manifest"
                            for item in capability_manifest.get("tools", [])
                        ),
                        "aimipay.get_protocol_manifest",
                    ),
                ]
            )

    if plugin_mcp_path.exists():
        payload = json.loads(plugin_mcp_path.read_text(encoding="utf-8"))
        server = payload.get("mcpServers", {}).get("aimipay-agent", {})
        details["mcp_server"] = server
        if "plugin" in install_plan:
            checks.extend(
                [
                    _check("mcp_command_present", bool(server.get("command")), str(server.get("command", ""))),
                    _check(
                        "mcp_entrypoint_expected",
                        server.get("args") == ["-m", "agent_entrypoints.aimipay_mcp_stdio"],
                        json.dumps(server.get("args", [])),
                    ),
                    _check(
                        "mcp_repo_root_bound",
                        server.get("env", {}).get("AIMIPAY_REPOSITORY_ROOT") == str(repo_root),
                        server.get("env", {}).get("AIMIPAY_REPOSITORY_ROOT", ""),
                    ),
                    _check(
                        "mcp_pythonpath_present",
                        bool(server.get("env", {}).get("PYTHONPATH")),
                        server.get("env", {}).get("PYTHONPATH", ""),
                    ),
                ]
            )

    if marketplace_path.exists():
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        details["marketplace"] = marketplace
        plugin_names = {item.get("name") for item in marketplace.get("plugins", [])}
        if "plugin" in install_plan:
            checks.append(
                _check(
                    "marketplace_has_aimipay_agent",
                    "aimipay-agent" in plugin_names,
                    ",".join(sorted(name for name in plugin_names if name)),
                )
            )

    generated_configs: dict[str, Any] = {}
    for host_target, (folder_name, file_name) in HOST_CONFIG_FILES.items():
        if host_target not in install_plan:
            continue
        config_path = layout["host_config_root"] / folder_name / file_name
        checks.append(_check(f"{host_target}_config_present", config_path.exists(), str(config_path)))
        if config_path.exists():
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            generated_configs[host_target] = payload
            checks.append(
                _check(
                    f"{host_target}_config_repo_root_bound",
                    _payload_has_repo_root(payload, str(repo_root)),
                    str(repo_root),
                )
            )
            checks.append(
                _check(
                    f"{host_target}_config_merchant_urls_present",
                    _payload_has_merchant_urls(payload),
                    _payload_merchant_urls(payload),
                )
            )

    details["generated_host_configs"] = generated_configs
    ok = all(item["ok"] for item in checks)
    report = {
        "ok": ok,
        "mode": mode,
        "repository_root": str(repo_root),
        "target_root": {key: str(value) for key, value in layout.items()},
        "expected_targets": sorted(install_plan),
        "checks": checks,
        "details": details,
    }
    if output_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_format_report(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify that the AimiPay agent package is installed and wired correctly.")
    parser.add_argument("--repository-root")
    parser.add_argument("--mode", choices=["repo-local", "home-local"], default="home-local")
    parser.add_argument("--install-root")
    parser.add_argument(
        "--expected-target",
        action="append",
        dest="expected_targets",
        choices=["skill", "plugin", "connector", "codex", "mcp", "claude", "cua", "openclaw", "hermes"],
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = verify_agent_installation(
        repository_root=args.repository_root,
        mode=args.mode,
        install_root=args.install_root,
        expected_targets=args.expected_targets,
        output_json=args.json,
    )
    return 0 if report["ok"] else 1


def _payload_has_repo_root(payload: dict[str, Any], repo_root: str) -> bool:
    if "entrypoint" in payload:
        return payload.get("entrypoint", {}).get("env", {}).get("AIMIPAY_REPOSITORY_ROOT") == repo_root
    if "mcpServers" in payload:
        for server in payload["mcpServers"].values():
            if server.get("env", {}).get("AIMIPAY_REPOSITORY_ROOT") == repo_root:
                return True
    if "servers" in payload:
        for server in payload["servers"]:
            if server.get("env", {}).get("AIMIPAY_REPOSITORY_ROOT") == repo_root:
                return True
    return False


def _payload_has_merchant_urls(payload: dict[str, Any]) -> bool:
    return bool(_payload_merchant_urls(payload))


def _payload_merchant_urls(payload: dict[str, Any]) -> str:
    if "entrypoint" in payload:
        return payload.get("entrypoint", {}).get("env", {}).get("AIMIPAY_MERCHANT_URLS", "")
    if "mcpServers" in payload:
        for server in payload["mcpServers"].values():
            value = server.get("env", {}).get("AIMIPAY_MERCHANT_URLS", "")
            if value:
                return value
    if "servers" in payload:
        for server in payload["servers"]:
            value = server.get("env", {}).get("AIMIPAY_MERCHANT_URLS", "")
            if value:
                return value
    return ""


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay Agent Installation Verify",
        f"- ok: {report['ok']}",
        f"- mode: {report['mode']}",
        f"- expected targets: {', '.join(report['expected_targets'])}",
    ]
    for item in report.get("checks", []):
        state = "ok" if item["ok"] else "missing"
        lines.append(f"- {item['name']}: {state} ({item['detail']})")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

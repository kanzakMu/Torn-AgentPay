from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shared.network_profiles import (
    MANAGED_NETWORK_KEYS,
    apply_network_profile_to_values,
    parse_env_file,
    write_env_file,
)


def apply_network_profile(
    *,
    env_file: str | Path,
    profile_name: str,
    repository_root: str | Path | None = None,
    output_json: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    env_path = Path(env_file).resolve()
    values = parse_env_file(env_path)
    updated, profile = apply_network_profile_to_values(
        values,
        profile_name=profile_name,
        repository_root=repository_root,
    )
    write_env_file(env_path, updated)
    report = {
        "ok": True,
        "env_file": str(env_path),
        "profile": profile_name,
        "display_name": profile.get("display_name", profile_name),
        "profile_ready": profile.get("profile_ready", True),
        "managed_values": {key: updated.get(key, "") for key in MANAGED_NETWORK_KEYS},
        "warnings": list(profile.get("warnings", [])),
    }
    if emit_output:
        if output_json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(_format_report(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply an AimiPay network profile to an env file.")
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--repository-root")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = apply_network_profile(
        env_file=args.env_file,
        profile_name=args.profile,
        repository_root=args.repository_root,
        output_json=args.json,
        emit_output=True,
    )
    return 0 if report["ok"] else 1


def _format_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay Network Profile",
        f"- profile: {report['profile']}",
        f"- display name: {report['display_name']}",
        f"- env file: {report['env_file']}",
        f"- profile ready: {report['profile_ready']}",
    ]
    if report["warnings"]:
        for warning in report["warnings"]:
            lines.append(f"- warning: {warning}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())

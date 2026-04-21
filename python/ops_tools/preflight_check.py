from __future__ import annotations

import argparse
import json

from .preflight import build_gateway_config_from_env, build_preflight_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AimiPay off-chain preflight checks from environment.")
    parser.add_argument("--env-file")
    parser.add_argument("--backup-dir")
    parser.add_argument("--snapshot-path")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    config = build_gateway_config_from_env(env_file=args.env_file)
    report = build_preflight_report(
        config,
        backup_dir=args.backup_dir,
        snapshot_path=args.snapshot_path,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.strict and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

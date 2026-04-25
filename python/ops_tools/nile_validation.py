from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from examples.env_loader import load_env_file
from .security_preflight import build_security_preflight_report


def run_nile_validation(
    *,
    repository_root: str | Path,
    env_file: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repository_root).resolve()
    if env_file is not None:
        load_env_file(env_file, override=True)
    preflight = build_security_preflight_report(env_file=env_file, production=False)
    steps: list[dict[str, Any]] = []
    if dry_run:
        return {
            "ok": True,
            "network": "nile",
            "dry_run": True,
            "preflight": preflight,
            "steps": [{"name": "dry_run", "ok": True, "detail": "no chain transactions submitted"}],
        }

    with tempfile.TemporaryDirectory(prefix="aimipay-nile-validation-") as temp_dir:
        plan_path = Path(temp_dir) / "nile-smoke-plan.json"
        plan = {
            "full_host": "https://nile.trongrid.io",
            "request_deadline": int(time.time()) + 300,
        }
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        completed = subprocess.run(
            ["node", "scripts/local_smoke_pipeline.js", str(plan_path)],
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
        )
    ok = completed.returncode == 0
    payload = _parse_last_json(completed.stdout) if ok else None
    steps.append(
        {
            "name": "nile_smoke",
            "ok": ok,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-2000:],
            "stderr": completed.stderr[-2000:],
            "payload": payload,
        }
    )
    return {
        "ok": ok,
        "network": "nile",
        "dry_run": False,
        "preflight": preflight,
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Nile validation workflow for Torn-AgentPay.")
    parser.add_argument("--repository-root", default=Path(__file__).resolve().parents[2])
    parser.add_argument("--env-file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run_nile_validation(
        repository_root=args.repository_root,
        env_file=args.env_file,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"nile validation: {'ok' if report['ok'] else 'failed'}")
    return 0 if report["ok"] else 1


def _parse_last_json(stdout: str) -> dict[str, Any] | None:
    for line in reversed([item.strip() for item in stdout.splitlines() if item.strip()]):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from .build_release_artifacts import build_release_artifacts
from .validate_release_artifacts import validate_release_artifacts


def build_clean_release(
    *,
    repository_root: str | Path,
    output_dir: str | Path,
    force: bool = False,
) -> dict[str, Any]:
    repo_root = Path(repository_root).resolve()
    dist_root = Path(output_dir).resolve()
    if dist_root == repo_root or repo_root in dist_root.parents and dist_root.name in {".", ""}:
        raise ValueError("output_dir must not be the repository root")
    if dist_root.exists():
        if not force:
            raise FileExistsError(f"output_dir already exists: {dist_root}")
        shutil.rmtree(dist_root)
    report = build_release_artifacts(repository_root=repo_root, output_dir=dist_root)
    validation = validate_release_artifacts(dist_dir=dist_root)
    clean_report = {
        "ok": bool(validation["ok"]),
        "repository_root": str(repo_root),
        "output_dir": str(dist_root),
        "build": report,
        "validation": validation,
    }
    (dist_root / "clean-release-report.json").write_text(
        json.dumps(clean_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not validation["ok"]:
        raise RuntimeError(f"release artifact validation failed: {validation}")
    return clean_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a clean Torn-AgentPay release directory and validate it.")
    parser.add_argument("--repository-root", default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = build_clean_release(
        repository_root=args.repository_root,
        output_dir=args.output_dir,
        force=args.force,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"clean release: {report['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

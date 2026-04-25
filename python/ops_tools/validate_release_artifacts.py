from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_PATHS = [
    "release-report.json",
    "release-manifest.json",
    "RELEASE_NOTES.md",
    "protocol-schemas/aimipay.manifest.v1.schema.json",
    "protocol-bundle/README.md",
    "protocol-bundle/PROTOCOL_REFERENCE.md",
    "protocol-bundle/BUYER_IMPLEMENTER_GUIDE.md",
    "protocol-bundle/HOST_IMPLEMENTER_GUIDE.md",
    "protocol-bundle/COMPATIBILITY_POLICY.md",
    "protocol-bundle/CONFORMANCE_CHECKLIST.md",
    "seller-node/seller-node.manifest.json",
    "reference-buyer/reference-buyer.manifest.json",
    "reference-buyer/minimal-buyer-reference.py",
    "conformance-fixtures/manifest.json",
    "conformance-fixtures/discover.json",
    "conformance-fixtures/attestation.json",
    "conformance-fixtures/purchase.json",
]

FORBIDDEN_PATH_PARTS = {
    ".venv",
    "venv",
    ".vendor",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".dry-run",
    ".docker-local",
    ".agent",
    ".wallets",
    ".merchant-config.history",
}

FORBIDDEN_FILE_NAMES = {
    ".env.local",
    ".env.merchant.local",
    ".merchant-config.json",
    "target.env",
    "target.nile.env",
}

FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
    ".log",
}


def validate_release_artifacts(*, dist_dir: str | Path) -> dict[str, object]:
    root = Path(dist_dir).resolve()
    missing = [relative for relative in REQUIRED_PATHS if not (root / relative).exists()]
    forbidden = _find_forbidden_paths(root)
    return {
        "ok": not missing and not forbidden,
        "dist_dir": str(root),
        "missing": missing,
        "forbidden": forbidden,
        "required_paths": REQUIRED_PATHS,
    }


def _find_forbidden_paths(root: Path) -> list[str]:
    if not root.exists():
        return []
    forbidden: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        parts = set(relative.parts)
        if parts & FORBIDDEN_PATH_PARTS:
            forbidden.append(str(relative))
            continue
        if path.is_file() and (path.name in FORBIDDEN_FILE_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES):
            forbidden.append(str(relative))
    return sorted(forbidden)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Torn-AgentPay dist release artifacts.")
    parser.add_argument("--dist-dir", required=True)
    args = parser.parse_args(argv)
    report = validate_release_artifacts(dist_dir=args.dist_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

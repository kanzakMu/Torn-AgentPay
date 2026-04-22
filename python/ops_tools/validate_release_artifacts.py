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


def validate_release_artifacts(*, dist_dir: str | Path) -> dict[str, object]:
    root = Path(dist_dir).resolve()
    missing = [relative for relative in REQUIRED_PATHS if not (root / relative).exists()]
    return {
        "ok": not missing,
        "dist_dir": str(root),
        "missing": missing,
        "required_paths": REQUIRED_PATHS,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Torn-AgentPay dist release artifacts.")
    parser.add_argument("--dist-dir", required=True)
    args = parser.parse_args(argv)
    report = validate_release_artifacts(dist_dir=args.dist_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

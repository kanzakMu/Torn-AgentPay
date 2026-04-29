from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ops_tools.export_protocol_schemas import export_protocol_schemas
from ops_tools.export_conformance_fixtures import export_conformance_fixtures
from ops_tools.package_protocol_bundle import package_protocol_bundle
from ops_tools.package_reference_buyer import package_reference_buyer
from ops_tools.package_seller_node import package_seller_node


RELEASE_LINE = "v1"
RELEASE_BUNDLE = "torn-agentpay.release-artifacts.v1"


def _write_release_notes(dist_root: Path) -> Path:
    release_notes = dist_root / "RELEASE_NOTES.md"
    release_notes.write_text(
        "\n".join(
            [
                "# AimiPay Release Notes",
                "",
                f"Release line: `{RELEASE_LINE}`",
                "",
                "This release includes:",
                "",
                "- x402-style HTTP 402 paid API adapter",
                "- facilitator verify and settle endpoints",
                "- AP2-inspired intent and payment mandates",
                "- hosted gateway MVP with marketplace capability index",
                "- merchant quickstart and hosted deployment guides",
                "- signed receipts, billing statements, payout reports, and webhook events",
                "- coding-agent paid flow demo",
                "- published protocol schemas and conformance fixtures",
                "",
                "Compatibility notes:",
                "",
                "- `v1` schema filenames and required fields are stable",
                "- seller-first language is public-facing, while some compatibility layers still retain `merchant` names",
                "- third-party implementations should pin to the published schema line",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return release_notes


def _write_release_manifest(dist_root: Path) -> Path:
    manifest_path = dist_root / "release-manifest.json"
    manifest = {
        "bundle": RELEASE_BUNDLE,
        "release_line": RELEASE_LINE,
        "protocol_schema_line": "aimipay.protocol-schemas.v1",
        "protocol_bundle_line": "aimipay.protocol-bundle.v1",
        "seller_node_line": "torn-agentpay.seller-node-package.v1",
        "reference_buyer_line": "torn-agentpay.reference-buyer-package.v1",
        "conformance_fixture_line": "torn-agentpay.conformance-fixtures.v1",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def build_release_artifacts(*, repository_root: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    repo_root = Path(repository_root).resolve()
    dist_root = Path(output_dir).resolve() if output_dir else repo_root / "dist"
    dist_root.mkdir(parents=True, exist_ok=True)

    schemas_dir = dist_root / "protocol-schemas"
    protocol_bundle_dir = dist_root / "protocol-bundle"
    seller_node_dir = dist_root / "seller-node"
    reference_buyer_dir = dist_root / "reference-buyer"
    fixture_dir = dist_root / "conformance-fixtures"

    schema_report = export_protocol_schemas(repository_root=repo_root, output_dir=schemas_dir)
    protocol_bundle_report = package_protocol_bundle(repository_root=repo_root, output_dir=protocol_bundle_dir)
    seller_node_report = package_seller_node(repository_root=repo_root, output_dir=seller_node_dir)
    reference_buyer_report = package_reference_buyer(repository_root=repo_root, output_dir=reference_buyer_dir)
    fixture_report = export_conformance_fixtures(output_dir=fixture_dir)
    release_notes = _write_release_notes(dist_root)
    release_manifest = _write_release_manifest(dist_root)

    report = {
        "bundle": RELEASE_BUNDLE,
        "repository_root": str(repo_root),
        "output_dir": str(dist_root),
        "release_notes": str(release_notes),
        "release_manifest": str(release_manifest),
        "artifacts": {
            "protocol_schemas": schema_report,
            "protocol_bundle": protocol_bundle_report,
            "seller_node": seller_node_report,
            "reference_buyer": reference_buyer_report,
            "conformance_fixtures": fixture_report,
        },
    }
    (dist_root / "release-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Torn-AgentPay release artifacts for third-party distribution.")
    parser.add_argument("--repository-root", default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = build_release_artifacts(repository_root=args.repository_root, output_dir=args.output_dir)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"release artifacts: {report['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

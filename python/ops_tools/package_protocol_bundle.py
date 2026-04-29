from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def package_protocol_bundle(*, repository_root: str | Path, output_dir: str | Path) -> dict[str, object]:
    repo_root = Path(repository_root).resolve()
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    schemas_src = repo_root / "spec" / "schemas"
    schemas_dst = target_dir / "schemas"
    if schemas_dst.exists():
        shutil.rmtree(schemas_dst)
    shutil.copytree(schemas_src, schemas_dst)

    docs = [
        repo_root / "spec" / "PROTOCOL_REFERENCE.md",
        repo_root / "spec" / "discovery.md",
        repo_root / "spec" / "THIRD_PARTY_IMPLEMENTER_GUIDE.md",
        repo_root / "spec" / "BUYER_IMPLEMENTER_GUIDE.md",
        repo_root / "spec" / "HOST_IMPLEMENTER_GUIDE.md",
        repo_root / "spec" / "AI_HOST_PLAYBOOK.md",
        repo_root / "spec" / "COMPATIBILITY_POLICY.md",
        repo_root / "spec" / "CONFORMANCE_CHECKLIST.md",
    ]
    for doc in docs:
        shutil.copy2(doc, target_dir / doc.name)

    readme = target_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Torn-AgentPay Protocol Bundle",
                "",
                "This directory packages the published AimiPay protocol schemas and conformance references.",
                "",
                "Contents:",
                "",
                "- `schemas/`: versioned JSON Schema files",
                "- `PROTOCOL_REFERENCE.md`: canonical protocol behavior",
                "- `discovery.md`: manifest and discovery object reference",
                "- `THIRD_PARTY_IMPLEMENTER_GUIDE.md`: implementation guidance",
                "- `BUYER_IMPLEMENTER_GUIDE.md`: buyer-side integration guidance",
                "- `HOST_IMPLEMENTER_GUIDE.md`: AI host and MCP integration guidance",
                "- `AI_HOST_PLAYBOOK.md`: host-side default tool flow, skill-only behavior, and recovery actions",
                "- `COMPATIBILITY_POLICY.md`: public compatibility commitments",
                "- `CONFORMANCE_CHECKLIST.md`: manual validation checklist",
                "- `aimipay.capabilities.json`: AI-facing capability manifest",
                "",
                "Suggested validation flow:",
                "",
                "1. materialize your manifest JSON",
                "2. materialize your discover JSON",
                "3. optionally materialize your attestation verification report",
                "4. run `python -m ops_tools.conformance_check --manifest-file <manifest.json> --discover-file <discover.json> --attestation-file <attestation.json>`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = {
        "bundle": "aimipay.protocol-bundle.v1",
        "output_dir": str(target_dir),
        "schemas_dir": str(schemas_dst),
        "documents": [doc.name for doc in docs] + ["README.md"],
    }
    shutil.copy2(repo_root / "agent-dist" / "aimipay.capabilities.json", target_dir / "aimipay.capabilities.json")
    report["documents"].append("aimipay.capabilities.json")
    (target_dir / "bundle-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package published Torn-AgentPay protocol schemas and docs into a distributable bundle.")
    parser.add_argument("--repository-root", default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    report = package_protocol_bundle(repository_root=args.repository_root, output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

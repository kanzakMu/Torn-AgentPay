from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def package_seller_node(*, repository_root: str | Path | None = None, output_dir: str | Path) -> dict[str, Any]:
    root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    sources = {
        "README.md": root / "seller-dist" / "node" / "README.md",
        "seller-node.manifest.json": root / "seller-dist" / "node" / "seller-node.manifest.json",
        "docker-compose.seller-node.yml": root / "seller-dist" / "node" / "docker-compose.seller-node.yml",
        ".env.seller-node.example": root / "python" / ".env.merchant.example",
        "bootstrap-seller-node.ps1": root / "python" / "bootstrap_seller_node.ps1",
        "run-seller-node.ps1": root / "python" / "run_seller_node.ps1",
    }

    written_files: list[str] = []
    for target_name, source_path in sources.items():
        content = source_path.read_text(encoding="utf-8").replace("E:/trade/aimicropay-tron", root.as_posix())
        destination = output / target_name
        destination.write_text(content, encoding="utf-8")
        written_files.append(str(destination))

    report = {
        "package_kind": "torn-agentpay-seller-node",
        "schema_version": "torn-agentpay.seller-node-package.v1",
        "repository_root": str(root),
        "output_dir": str(output),
        "files": written_files,
    }
    (output / "package-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize a Torn-AgentPay self-hosted seller node package directory.")
    parser.add_argument("--repository-root")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = package_seller_node(
        repository_root=args.repository_root,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"seller node package: {report['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

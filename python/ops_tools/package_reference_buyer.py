from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def package_reference_buyer(*, repository_root: str | Path | None = None, output_dir: str | Path) -> dict[str, Any]:
    root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    sources = {
        "README.md": root / "buyer-dist" / "reference" / "README.md",
        "reference-buyer.manifest.json": root / "buyer-dist" / "reference" / "reference-buyer.manifest.json",
        "minimal-buyer-reference.py": root / "python" / "examples" / "minimal_buyer_reference.py",
    }

    written_files: list[str] = []
    for target_name, source_path in sources.items():
        destination = output / target_name
        destination.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        written_files.append(str(destination))

    report = {
        "package_kind": "torn-agentpay-reference-buyer",
        "schema_version": "torn-agentpay.reference-buyer-package.v1",
        "repository_root": str(root),
        "output_dir": str(output),
        "files": written_files,
    }
    (output / "package-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize a Torn-AgentPay reference buyer package directory.")
    parser.add_argument("--repository-root")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = package_reference_buyer(
        repository_root=args.repository_root,
        output_dir=args.output_dir,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"reference buyer package: {report['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

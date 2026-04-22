from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shared import CapabilityOffer, ChainInfo, MerchantManifest, MerchantPlan, MerchantRoute, SellerProfile, SignatureEnvelope


def _with_schema_metadata(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(schema)
    enriched["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    enriched.setdefault("title", name)
    return enriched


def export_protocol_schemas(*, repository_root: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    repo_root = Path(repository_root).resolve()
    target_dir = Path(output_dir).resolve() if output_dir else repo_root / "spec" / "schemas"
    target_dir.mkdir(parents=True, exist_ok=True)

    schema_map = {
        "aimipay.chain-info.v1.schema.json": ("AimiPay ChainInfo", ChainInfo),
        "aimipay.route.v1.schema.json": ("AimiPay MerchantRoute", MerchantRoute),
        "aimipay.plan.v1.schema.json": ("AimiPay MerchantPlan", MerchantPlan),
        "aimipay.offer.v1.schema.json": ("AimiPay CapabilityOffer", CapabilityOffer),
        "aimipay.seller-profile.v1.schema.json": ("AimiPay SellerProfile", SellerProfile),
        "aimipay.signature-envelope.v1.schema.json": ("AimiPay SignatureEnvelope", SignatureEnvelope),
        "aimipay.manifest.v1.schema.json": ("AimiPay MerchantManifest", MerchantManifest),
    }

    written: list[str] = []
    for filename, (title, model) in schema_map.items():
        schema = _with_schema_metadata(title, model.model_json_schema())
        destination = target_dir / filename
        destination.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(str(destination))

    index = {
        "schema_bundle": "aimipay.protocol-schemas.v1",
        "output_dir": str(target_dir),
        "schemas": [
            {
                "filename": Path(path).name,
                "path": path,
            }
            for path in written
        ],
    }
    (target_dir / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export stable AimiPay protocol JSON Schemas.")
    parser.add_argument("--repository-root", default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir")
    args = parser.parse_args(argv)
    report = export_protocol_schemas(repository_root=args.repository_root, output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

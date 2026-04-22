from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

from buyer.client import BuyerClient
from buyer.wallet import BuyerWallet
from shared import MerchantManifest, SellerProfile, SignatureEnvelope


class _NoopProvisioner:
    def provision(self, plan):
        raise RuntimeError("conformance check does not provision channels")


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate_manifest_payload(manifest: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    required_fields = [
        "schema_version",
        "version",
        "kind",
        "transport",
        "service_name",
        "service_description",
        "primary_chain",
        "seller_profile",
        "routes",
        "plans",
        "endpoints",
    ]
    for field in required_fields:
        if field not in manifest:
            errors.append(_error("manifest_missing_field", f"manifest missing required field: {field}"))
    if manifest.get("schema_version") != "aimipay.manifest.v1":
        errors.append(_error("manifest_schema_version_invalid", "manifest schema_version must be aimipay.manifest.v1"))
    try:
        MerchantManifest.model_validate(manifest)
    except Exception as exc:
        errors.append(_error("manifest_model_invalid", f"manifest does not satisfy MerchantManifest model: {exc}"))
    seller_profile = manifest.get("seller_profile")
    if seller_profile:
        try:
            SellerProfile.model_validate(seller_profile)
        except Exception as exc:
            errors.append(_error("seller_profile_invalid", f"seller_profile does not satisfy SellerProfile model: {exc}"))
    if manifest.get("seller_profile_signature"):
        try:
            SignatureEnvelope.model_validate(manifest["seller_profile_signature"])
        except Exception:
            errors.append(_error("seller_profile_signature_invalid", "seller_profile_signature is not a valid signature envelope"))
    if manifest.get("manifest_signature"):
        try:
            SignatureEnvelope.model_validate(manifest["manifest_signature"])
        except Exception:
            errors.append(_error("manifest_signature_invalid", "manifest_signature is not a valid signature envelope"))
    return errors


def validate_discover_payload(discovery: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    required_fields = [
        "seller",
        "chain",
        "contract_address",
        "token_address",
        "routes",
        "plans",
        "manifest_url",
        "protocol_reference_url",
    ]
    for field in required_fields:
        if field not in discovery:
            errors.append(_error("discover_missing_field", f"discover payload missing required field: {field}"))
    primary_chain = manifest.get("primary_chain") or {}
    if primary_chain:
        if discovery.get("seller") != primary_chain.get("seller_address"):
            errors.append(_error("discover_seller_mismatch", "discover seller does not match manifest primary_chain.seller_address"))
        if discovery.get("contract_address") != primary_chain.get("contract_address"):
            errors.append(_error("discover_contract_mismatch", "discover contract_address does not match manifest primary_chain.contract_address"))
        token_address = primary_chain.get("asset_address")
        if discovery.get("token_address") != token_address:
            errors.append(_error("discover_token_mismatch", "discover token_address does not match manifest primary_chain.asset_address"))
    return errors


def validate_purchase_fixture(purchase: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    prepare = purchase.get("prepare_purchase")
    submit = purchase.get("submit_purchase")
    confirm = purchase.get("confirm_purchase")
    if not isinstance(prepare, dict):
        errors.append(_error("purchase_prepare_missing", "purchase fixture missing prepare_purchase object"))
    if not isinstance(submit, dict):
        errors.append(_error("purchase_submit_missing", "purchase fixture missing submit_purchase object"))
    if not isinstance(confirm, dict):
        errors.append(_error("purchase_confirm_missing", "purchase fixture missing confirm_purchase object"))
    if errors:
        return errors
    for field in ("offer", "budget", "decision", "session"):
        if field not in prepare:
            errors.append(_error("purchase_prepare_field_missing", f"prepare_purchase missing field: {field}"))
    for field in ("offer", "budget", "decision", "session", "payment"):
        if field not in submit:
            errors.append(_error("purchase_submit_field_missing", f"submit_purchase missing field: {field}"))
    payment = submit.get("payment") or {}
    if payment.get("status") not in {"authorized", "submitted", "settled"}:
        errors.append(_error("purchase_submit_status_invalid", "submit_purchase.payment.status must be authorized, submitted, or settled"))
    if confirm.get("status") not in {"submitted", "settled"}:
        errors.append(_error("purchase_confirm_status_invalid", "confirm_purchase.status must be submitted or settled"))
    if confirm.get("status") == "settled" and confirm.get("confirmation_status") != "confirmed":
        errors.append(_error("purchase_confirm_confirmation_invalid", "settled confirm_purchase must include confirmation_status=confirmed"))
    return errors


def build_conformance_report(*, seller_base_url: str | None, manifest: dict[str, Any], discovery: dict[str, Any], attestation: dict[str, Any]) -> dict[str, Any]:
    manifest_errors = validate_manifest_payload(manifest)
    discover_errors = validate_discover_payload(discovery, manifest)
    attestation_errors = list(attestation.get("errors") or [])
    ok = not manifest_errors and not discover_errors and not attestation_errors
    repo_root = Path(__file__).resolve().parents[2]
    return {
        "ok": ok,
        "seller_base_url": seller_base_url.rstrip("/") if seller_base_url else None,
        "schema_refs": {
            "manifest": str(repo_root / "spec" / "schemas" / "aimipay.manifest.v1.schema.json"),
            "seller_profile": str(repo_root / "spec" / "schemas" / "aimipay.seller-profile.v1.schema.json"),
            "signature_envelope": str(repo_root / "spec" / "schemas" / "aimipay.signature-envelope.v1.schema.json"),
            "offer": str(repo_root / "spec" / "schemas" / "aimipay.offer.v1.schema.json"),
        },
        "manifest": {
            "schema_version": manifest.get("schema_version"),
            "kind": manifest.get("kind"),
            "route_count": len(manifest.get("routes") or []),
            "plan_count": len(manifest.get("plans") or []),
            "errors": manifest_errors,
        },
        "discover": {
            "seller": discovery.get("seller"),
            "chain": discovery.get("chain"),
            "errors": discover_errors,
        },
        "attestation": {
            "seller_profile_signed": bool(attestation.get("seller_profile_signed")),
            "seller_profile_verified": bool(attestation.get("seller_profile_verified")),
            "manifest_signed": bool(attestation.get("manifest_signed")),
            "manifest_verified": bool(attestation.get("manifest_verified")),
            "errors": attestation_errors,
        },
        "purchase": {
            "errors": [],
        },
    }


def run_protocol_conformance(*, seller_base_url: str, http_client: httpx.Client | None = None) -> dict[str, Any]:
    client = BuyerClient(
        merchant_base_url=seller_base_url,
        full_host=None,
        wallet=BuyerWallet(address="TRX_CONFORMANCE_BUYER", private_key="conformance_placeholder"),
        provisioner=_NoopProvisioner(),
        http_client=http_client,
    )
    manifest = client.fetch_manifest()
    discovery = client.discover()
    attestation = manifest.get("_attestation") or client.verify_manifest_attestation(manifest)
    return build_conformance_report(
        seller_base_url=seller_base_url,
        manifest=manifest,
        discovery=discovery,
        attestation=attestation,
    )


def run_protocol_conformance_from_files(*, manifest_file: str | Path, discover_file: str | Path, attestation_file: str | Path | None = None, purchase_file: str | Path | None = None) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_file).read_text(encoding="utf-8"))
    discovery = json.loads(Path(discover_file).read_text(encoding="utf-8"))
    attestation = json.loads(Path(attestation_file).read_text(encoding="utf-8")) if attestation_file else {}
    report = build_conformance_report(
        seller_base_url=None,
        manifest=manifest,
        discovery=discovery,
        attestation=attestation,
    )
    if purchase_file:
        purchase = json.loads(Path(purchase_file).read_text(encoding="utf-8"))
        purchase_errors = validate_purchase_fixture(purchase)
        report["purchase"] = {
            "errors": purchase_errors,
        }
        report["ok"] = report["ok"] and not purchase_errors
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Torn-AgentPay protocol conformance checks against a seller base URL.")
    parser.add_argument("--seller-url")
    parser.add_argument("--manifest-file")
    parser.add_argument("--discover-file")
    parser.add_argument("--attestation-file")
    parser.add_argument("--purchase-file")
    parser.add_argument("--report-file")
    args = parser.parse_args(argv)
    if args.seller_url:
        report = run_protocol_conformance(seller_base_url=args.seller_url)
    else:
        if not args.manifest_file or not args.discover_file:
            parser.error("either --seller-url or both --manifest-file and --discover-file are required")
        report = run_protocol_conformance_from_files(
            manifest_file=args.manifest_file,
            discover_file=args.discover_file,
            attestation_file=args.attestation_file,
            purchase_file=args.purchase_file,
        )
    if args.report_file:
        Path(args.report_file).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

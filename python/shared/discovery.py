from __future__ import annotations

from .attestation import build_seller_profile, sign_payload
from .models import ChainInfo, MerchantManifest, MerchantPlan, MerchantRoute


def build_endpoints(*, management_prefix: str = "/_aimipay", base_url: str | None = None) -> dict[str, str]:
    normalized_prefix = management_prefix.rstrip("/")
    if not normalized_prefix:
        normalized_prefix = "/_aimipay"
    root = "" if base_url is None else base_url.rstrip("/")
    return {
        "discover": f"{root}/.well-known/aimipay.json",
        "management": f"{root}{normalized_prefix}",
        "open_channel": f"{root}{normalized_prefix}/channels/open",
        "protocol_reference": f"{root}{normalized_prefix}/protocol/reference",
        "create_payment_intent": f"{root}{normalized_prefix}/payment-intents",
        "reconcile_settlements": f"{root}{normalized_prefix}/settlements/reconcile",
        "recover_payments": f"{root}{normalized_prefix}/payments/recover",
        "list_pending_payments": f"{root}{normalized_prefix}/payments/pending",
        "payment_status_template": f"{root}{normalized_prefix}/payments/{{payment_id}}",
        "ops_health": f"{root}{normalized_prefix}/ops/health",
        "ops_payment_action_template": f"{root}{normalized_prefix}/ops/payments/{{payment_id}}/action",
    }


def build_manifest(
    *,
    service_name: str,
    service_description: str,
    primary_chain: ChainInfo,
    routes: list[MerchantRoute],
    plans: list[MerchantPlan],
    management_prefix: str = "/_aimipay",
    base_url: str | None = None,
    seller_private_key: str | None = None,
) -> dict:
    active_routes = [route for route in routes if getattr(route, "enabled", True)]
    active_plans = [plan for plan in plans if getattr(plan, "enabled", True)]
    seller_profile = build_seller_profile(
        seller_address=primary_chain.seller_address,
        service_name=service_name,
        service_description=service_description,
        base_url=base_url,
        network=primary_chain.network,
        chain_id=primary_chain.chain_id,
    )
    manifest = MerchantManifest(
        service_name=service_name,
        service_description=service_description,
        primary_chain=primary_chain,
        seller_profile=seller_profile,
        routes=active_routes,
        plans=active_plans,
        endpoints=build_endpoints(management_prefix=management_prefix, base_url=base_url),
    )
    manifest_payload = manifest.model_dump(mode="json")
    if _looks_like_private_key(seller_private_key):
        seller_profile_signature = sign_payload(
            payload=seller_profile.model_dump(mode="json"),
            signer_address=primary_chain.seller_address,
            private_key=seller_private_key,
            payload_kind="seller_profile",
        )
        manifest_payload["seller_profile_signature"] = seller_profile_signature.model_dump(mode="json")
        unsigned_manifest = dict(manifest_payload)
        unsigned_manifest.pop("manifest_signature", None)
        manifest_signature = sign_payload(
            payload=unsigned_manifest,
            signer_address=primary_chain.seller_address,
            private_key=seller_private_key,
            payload_kind="seller_manifest",
        )
        manifest_payload["manifest_signature"] = manifest_signature.model_dump(mode="json")
    return manifest_payload


def _looks_like_private_key(value: str | None) -> bool:
    if not value:
        return False
    normalized = value[2:] if value.startswith("0x") else value
    if len(normalized) != 64:
        return False
    try:
        int(normalized, 16)
    except ValueError:
        return False
    return True

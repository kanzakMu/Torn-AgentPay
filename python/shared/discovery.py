from __future__ import annotations

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
) -> dict:
    active_routes = [route for route in routes if getattr(route, "enabled", True)]
    active_plans = [plan for plan in plans if getattr(plan, "enabled", True)]
    manifest = MerchantManifest(
        service_name=service_name,
        service_description=service_description,
        primary_chain=primary_chain,
        routes=active_routes,
        plans=active_plans,
        endpoints=build_endpoints(management_prefix=management_prefix, base_url=base_url),
    )
    return manifest.model_dump(mode="json")

from __future__ import annotations

from dataclasses import dataclass
import re

from fastapi import FastAPI

from shared import CapabilityBudgetHint, MerchantPlan, MerchantRoute

from .gateway import GatewayConfig, GatewayRuntime, GatewaySettlementConfig, install_gateway


@dataclass(slots=True)
class SellableCapabilityRuntime:
    app: FastAPI
    gateway: GatewayRuntime

    def publish_capability(
        self,
        *,
        path: str,
        price_atomic: int,
        capability_type: str,
        method: str = "POST",
        capability_id: str | None = None,
        description: str | None = None,
        pricing_model: str = "fixed_per_call",
        usage_unit: str = "request",
        delivery_mode: str = "sync",
        response_format: str | None = "json",
        auth_requirements: list[str] | None = None,
        capability_tags: list[str] | None = None,
        budget_hint: CapabilityBudgetHint | None = None,
    ) -> MerchantRoute:
        route = MerchantRoute(
            path=path,
            method=method,
            price_atomic=price_atomic,
            capability_id=capability_id or _make_capability_id(capability_type, path),
            capability_type=capability_type,
            description=description,
            pricing_model=pricing_model,
            usage_unit=usage_unit,
            delivery_mode=delivery_mode,
            response_format=response_format,
            auth_requirements=list(auth_requirements or []),
            capability_tags=list(capability_tags or []),
            budget_hint=budget_hint,
        )
        return self.publish_usage_route(route)

    def publish_api(
        self,
        *,
        path: str,
        price_atomic: int,
        capability_type: str = "api",
        method: str = "POST",
        capability_id: str | None = None,
        description: str | None = None,
        pricing_model: str = "fixed_per_call",
        usage_unit: str = "request",
        response_format: str | None = "json",
        auth_requirements: list[str] | None = None,
        capability_tags: list[str] | None = None,
        budget_hint: CapabilityBudgetHint | None = None,
    ) -> MerchantRoute:
        tags = list(capability_tags or [])
        if "api" not in tags:
            tags.append("api")
        return self.publish_capability(
            path=path,
            price_atomic=price_atomic,
            capability_type=capability_type,
            method=method,
            capability_id=capability_id,
            description=description,
            pricing_model=pricing_model,
            usage_unit=usage_unit,
            delivery_mode="sync",
            response_format=response_format,
            auth_requirements=auth_requirements,
            capability_tags=tags,
            budget_hint=budget_hint,
        )

    def publish_mcp_tool(
        self,
        *,
        path: str,
        price_atomic: int,
        capability_id: str | None = None,
        description: str | None = None,
        method: str = "POST",
        pricing_model: str = "fixed_per_call",
        usage_unit: str = "tool_call",
        auth_requirements: list[str] | None = None,
        capability_tags: list[str] | None = None,
        budget_hint: CapabilityBudgetHint | None = None,
    ) -> MerchantRoute:
        tags = list(capability_tags or [])
        if "mcp" not in tags:
            tags.append("mcp")
        return self.publish_capability(
            path=path,
            price_atomic=price_atomic,
            capability_type="mcp_tool",
            method=method,
            capability_id=capability_id,
            description=description,
            pricing_model=pricing_model,
            usage_unit=usage_unit,
            delivery_mode="sync",
            response_format="json",
            auth_requirements=auth_requirements,
            capability_tags=tags,
            budget_hint=budget_hint,
        )

    def publish_usage_route(self, route: MerchantRoute) -> MerchantRoute:
        self.gateway.config.routes.append(route)
        return route

    def publish_plan(self, plan: MerchantPlan) -> MerchantPlan:
        self.gateway.config.plans.append(plan)
        return plan


def install_sellable_capability(
    app: FastAPI,
    *,
    service_name: str,
    service_description: str,
    seller_address: str,
    contract_address: str,
    token_address: str,
    chain_id: int | None = None,
    network: str = "nile",
    asset_symbol: str = "USDT",
    asset_decimals: int = 6,
    default_deposit_atomic: int = 1_000_000,
    default_channel_ttl_s: int = 3600,
    routes: list[MerchantRoute] | None = None,
    plans: list[MerchantPlan] | None = None,
    settlement: GatewaySettlementConfig | None = None,
    settlement_service: object | None = None,
    sqlite_path: str | None = None,
    admin_token: str | None = None,
    admin_token_sha256: str | None = None,
    admin_read_token: str | None = None,
    admin_read_token_sha256: str | None = None,
    audit_log_path: str | None = None,
) -> SellableCapabilityRuntime:
    gateway = install_gateway(
        app,
        GatewayConfig(
            service_name=service_name,
            service_description=service_description,
            seller_address=seller_address,
            contract_address=contract_address,
            token_address=token_address,
            network=network,
            asset_symbol=asset_symbol,
            asset_decimals=asset_decimals,
            chain_id=chain_id,
            default_deposit_atomic=default_deposit_atomic,
            default_channel_ttl_s=default_channel_ttl_s,
            admin_token=admin_token,
            admin_token_sha256=admin_token_sha256,
            admin_read_token=admin_read_token,
            admin_read_token_sha256=admin_read_token_sha256,
            audit_log_path=audit_log_path,
            routes=list(routes or []),
            plans=list(plans or []),
            settlement=settlement,
            sqlite_path=sqlite_path,
        ),
        settlement_service=settlement_service,
    )
    return SellableCapabilityRuntime(app=app, gateway=gateway)


def _make_capability_id(capability_type: str, path: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    return f"{capability_type}-{normalized or 'capability'}"

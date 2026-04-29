from __future__ import annotations

from dataclasses import dataclass
import inspect
import json
import re
from typing import Any, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from shared import CapabilityBudgetHint, MerchantPlan, MerchantRoute

from .gateway import GatewayConfig, GatewayRuntime, GatewaySettlementConfig, install_gateway
from .x402_compat import build_x402_payment_requirement


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

    def paid_api(
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
        capability_tags: list[str] | None = None,
        budget_hint: CapabilityBudgetHint | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Publish and protect a merchant API with an x402-style HTTP 402 handshake."""

        route = self.publish_api(
            path=path,
            price_atomic=price_atomic,
            capability_type=capability_type,
            method=method,
            capability_id=capability_id,
            description=description,
            pricing_model=pricing_model,
            usage_unit=usage_unit,
            response_format=response_format,
            auth_requirements=["x-payment", "x-aimipay-payment-id"],
            capability_tags=_with_tag(capability_tags, "http402"),
            budget_hint=budget_hint,
        )

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            async def endpoint(request: Request) -> Any:
                payment_id = _extract_payment_id(request)
                if not payment_id:
                    return self.payment_required_response(route=route, request=request)

                record = self.gateway.get_payment(payment_id)
                if record is None:
                    return self.payment_required_response(
                        route=route,
                        request=request,
                        payment_error="payment_not_found",
                        payment_id=payment_id,
                    )
                validation_error = _validate_payment_for_route(record=record, route=route)
                if validation_error:
                    return self.payment_required_response(
                        route=route,
                        request=request,
                        payment_error=validation_error,
                        payment_id=payment_id,
                        payment_status=record.status,
                    )
                if record.status != "settled":
                    return self.payment_required_response(
                        route=route,
                        request=request,
                        payment_error="payment_not_settled",
                        payment_id=payment_id,
                        payment_status=record.status,
                    )

                result = await _call_paid_handler(handler, request)
                receipt = build_http402_payment_receipt(gateway=self.gateway, route=route, payment=record, request=request)
                if isinstance(result, Response):
                    result.headers["X-PAYMENT-RESPONSE"] = json.dumps(receipt, separators=(",", ":"))
                    return result
                return JSONResponse(
                    content=result,
                    headers={
                        "X-PAYMENT-RESPONSE": json.dumps(receipt, separators=(",", ":"))
                    },
                )

            self.app.add_api_route(path, endpoint, methods=[method.upper()])
            return handler

        return decorator

    def payment_required_response(
        self,
        *,
        route: MerchantRoute,
        request: Request,
        payment_error: str | None = None,
        payment_id: str | None = None,
        payment_status: str | None = None,
    ) -> JSONResponse:
        payload = build_http402_payment_required(
            gateway=self.gateway,
            route=route,
            request=request,
            payment_error=payment_error,
            payment_id=payment_id,
            payment_status=payment_status,
        )
        return JSONResponse(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            content=payload,
            headers={
                "Payment-Required": "true",
                "X-AIMIPAY-Protocol": "aimipay.http402.v1",
            },
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


def build_http402_payment_required(
    *,
    gateway: GatewayRuntime,
    route: MerchantRoute,
    request: Request,
    payment_error: str | None = None,
    payment_id: str | None = None,
    payment_status: str | None = None,
) -> dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    resource_url = f"{base_url}{route.path}"
    management_prefix = gateway.config.management_prefix.rstrip("/")
    chain = gateway.config.primary_chain()
    amount_atomic = route.price_atomic
    capability_id = route.capability_id or _make_capability_id(route.capability_type, route.path)
    next_actions = [
        {
            "action": "quote_budget",
            "tool": "aimipay.quote_budget",
            "reason": "Estimate cost before creating a payment.",
        },
        {
            "action": "prepare_purchase",
            "tool": "aimipay.prepare_purchase",
            "reason": "Open or reuse the payment channel after budget approval.",
        },
        {
            "action": "submit_purchase",
            "tool": "aimipay.submit_purchase",
            "reason": "Create the voucher-backed payment, then retry this resource with X-PAYMENT or X-AIMIPAY-PAYMENT-ID.",
        },
    ]
    if payment_status and payment_status != "settled":
        next_actions.insert(
            0,
            {
                "action": "finalize_payment",
                "tool": "aimipay.finalize_payment",
                "reason": "The supplied payment is not settled yet.",
            },
        )
    return {
        "schema_version": "aimipay.http402.v1",
        "kind": "payment_required",
        "x402_compat": {
            "version": 1,
            "request_header": "X-PAYMENT",
            "response_header": "X-PAYMENT-RESPONSE",
            "settlement_rail": "tron-contract",
        },
        "error": payment_error or "payment_required",
        "payment_id": payment_id,
        "payment_status": payment_status,
        "accepts": [
            {
                "scheme": "aimipay-tron-v1",
                "network": chain.network,
                "chain": chain.chain,
                "chain_id": chain.chain_id,
                "asset": chain.asset_address,
                "asset_symbol": chain.asset_symbol,
                "asset_decimals": chain.asset_decimals,
                "pay_to": chain.seller_address,
                "max_amount_required_atomic": amount_atomic,
                "amount_atomic": amount_atomic,
                "resource": resource_url,
                "method": route.method,
                "description": route.description,
                "capability_id": capability_id,
                "capability_type": route.capability_type,
                "usage_unit": route.usage_unit,
                "mime_type": "application/json" if route.response_format == "json" else None,
                "extra": {
                    "discover_url": f"{base_url}{management_prefix}/discover",
                    "payment_intents_url": f"{base_url}{management_prefix}/payment-intents",
                    "payment_status_template": f"{base_url}{management_prefix}/payments/{{payment_id}}",
                    "protocol_reference_url": f"{base_url}{management_prefix}/protocol/reference",
                },
            }
        ],
        "x402": {
            "version": 1,
            "accepts": [
                build_x402_payment_requirement(
                    scheme="aimipay-tron-v1",
                    network=chain.network,
                    asset=chain.asset_address,
                    asset_symbol=chain.asset_symbol,
                    pay_to=chain.seller_address,
                    amount_atomic=amount_atomic,
                    resource=resource_url,
                    description=route.description,
                    extra={
                        "payment_intents_url": f"{base_url}{management_prefix}/payment-intents",
                        "payment_status_template": f"{base_url}{management_prefix}/payments/{{payment_id}}",
                    },
                )
            ],
        },
        "next_actions": next_actions,
        "human_approval_required": route.requires_human_approval,
        "supports_auto_purchase": route.supports_auto_purchase,
    }


def build_http402_payment_receipt(
    *,
    gateway: GatewayRuntime,
    route: MerchantRoute,
    payment: Any,
    request: Request,
) -> dict[str, Any]:
    chain = gateway.config.primary_chain()
    return {
        "schema_version": "aimipay.http402-payment-response.v1",
        "kind": "payment_receipt",
        "payment_id": payment.payment_id,
        "status": payment.status,
        "route_path": route.path,
        "request_path": str(request.url.path),
        "amount_atomic": payment.amount_atomic,
        "required_amount_atomic": route.price_atomic,
        "buyer_address": payment.buyer_address,
        "seller_address": payment.seller_address or gateway.config.seller_address,
        "asset": chain.asset_address,
        "asset_symbol": chain.asset_symbol,
        "tx_id": payment.tx_id,
        "settled_at": payment.settled_at,
        "confirmed_at": payment.confirmed_at,
    }


def _validate_payment_for_route(*, record: Any, route: MerchantRoute) -> str | None:
    if record.route_path and record.route_path != route.path:
        return "payment_resource_mismatch"
    if record.request_path and record.request_path != route.path:
        return "payment_resource_mismatch"
    if int(record.amount_atomic) < int(route.price_atomic):
        return "payment_amount_insufficient"
    return None


def _extract_payment_id(request: Request) -> str | None:
    explicit = request.headers.get("x-aimipay-payment-id")
    if explicit:
        return explicit.strip()
    payment = request.headers.get("x-payment")
    if not payment:
        return None
    payment = payment.strip()
    if payment.startswith("{"):
        try:
            payload = json.loads(payment)
        except json.JSONDecodeError:
            return None
        candidate = payload.get("payment_id") or payload.get("paymentId")
        return str(candidate).strip() if candidate else None
    return payment


async def _call_paid_handler(handler: Callable[..., Any], request: Request) -> Any:
    signature = inspect.signature(handler)
    if not signature.parameters:
        result = handler()
    elif "request" in signature.parameters:
        result = handler(request=request)
    else:
        body = await _request_json_or_bytes(request)
        result = handler(body)
    if inspect.isawaitable(result):
        return await result
    return result


async def _request_json_or_bytes(request: Request) -> Any:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return await request.json()
        except json.JSONDecodeError:
            return {}
    body = await request.body()
    if not body:
        return {}
    return body.decode("utf-8", errors="replace")


def _with_tag(tags: list[str] | None, tag: str) -> list[str]:
    values = list(tags or [])
    if tag not in values:
        values.append(tag)
    return values


def _make_capability_id(capability_type: str, path: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    return f"{capability_type}-{normalized or 'capability'}"

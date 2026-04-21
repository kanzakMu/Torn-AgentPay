from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from seller import GatewaySettlementConfig, install_sellable_capability
from shared import MerchantPlan, MerchantRoute, resolve_full_host_for_network

from .env_loader import load_default_example_env
from .merchant_control import (
    MerchantBrandConfig,
    MerchantConfigSnapshot,
    MerchantInstallConfig,
    delete_plan,
    delete_route,
    diff_configs,
    list_config_history,
    load_merchant_install_config,
    rollback_merchant_install_config,
    save_merchant_install_config,
    toggle_plan,
    toggle_route,
    upsert_plan,
    upsert_route,
)


class BrandingUpdateRequest(BaseModel):
    service_name: str | None = None
    service_description: str | None = None
    display_title: str | None = None
    accent_color: str | None = None
    support_email: str | None = None


class DeleteRouteRequest(BaseModel):
    path: str
    method: str = "POST"


class ToggleRouteRequest(BaseModel):
    path: str
    method: str = "POST"
    enabled: bool


class TogglePlanRequest(BaseModel):
    enabled: bool


def create_app() -> FastAPI:
    load_default_example_env()
    repository_root = os.environ.get("AIMIPAY_REPOSITORY_ROOT", "e:/trade/aimicropay-tron")
    merchant_dist_root = Path(repository_root) / "merchant-dist"
    dashboard_html = merchant_dist_root / "dashboard" / "install_dashboard.html"
    full_host = os.environ.get("AIMIPAY_FULL_HOST", "http://127.0.0.1:9090")
    service_name = os.environ.get("AIMIPAY_SERVICE_NAME", "Research Copilot")
    service_description = os.environ.get("AIMIPAY_SERVICE_DESCRIPTION", "Pay-per-use research and market data")
    merchant_config_path = os.environ.get(
        "AIMIPAY_MERCHANT_CONFIG_PATH",
        str(Path(repository_root) / "python" / ".merchant-config.json"),
    )
    sqlite_path = os.environ.get(
        "AIMIPAY_SQLITE_PATH",
        str(Path(repository_root) / "python" / "merchant-payments.db"),
    )
    public_config_path = Path(repository_root) / "merchant-dist" / "website" / ".generated" / "merchant.public.json"
    merchant_port = int(os.environ.get("AIMIPAY_MERCHANT_PORT", "8000"))
    public_base_url = os.environ.get("AIMIPAY_PUBLIC_BASE_URL", f"http://127.0.0.1:{merchant_port}")
    network_profile = os.environ.get("AIMIPAY_NETWORK_PROFILE", "custom")
    brand = MerchantBrandConfig(
        display_title=os.environ.get("AIMIPAY_DISPLAY_TITLE", "Pay with AimiPay"),
        accent_color=os.environ.get("AIMIPAY_BRAND_ACCENT_COLOR", "#0f766e"),
        support_email=os.environ.get("AIMIPAY_SUPPORT_EMAIL", "support@example.com"),
    )
    install_config = load_merchant_install_config(
        config_path=merchant_config_path,
        service_name=service_name,
        service_description=service_description,
        brand=brand,
    )
    seller_private_key = (os.environ.get("AIMIPAY_SELLER_PRIVATE_KEY") or "seller_private_key").strip() or "seller_private_key"
    seller_address = (os.environ.get("AIMIPAY_SELLER_ADDRESS") or "TRX_SELLER").strip() or "TRX_SELLER"
    contract_address = (os.environ.get("AIMIPAY_CONTRACT_ADDRESS") or "TRX_CONTRACT").strip() or "TRX_CONTRACT"
    token_address = (os.environ.get("AIMIPAY_TOKEN_ADDRESS") or "TRX_USDT").strip() or "TRX_USDT"
    network_name = (os.environ.get("AIMIPAY_NETWORK_NAME") or os.environ.get("AIMIPAY_NETWORK_PROFILE") or "nile").strip() or "nile"
    chain_id = int((os.environ.get("AIMIPAY_CHAIN_ID") or "31337").strip() or "31337")
    executor_backend = os.environ.get("AIMIPAY_SETTLEMENT_BACKEND", "claim_script")

    app = FastAPI(title=install_config.service_name)
    if merchant_dist_root.exists():
        app.mount("/aimipay/assets", StaticFiles(directory=str(merchant_dist_root)), name="aimipay_assets")
    runtime = install_sellable_capability(
        app,
        service_name=install_config.service_name,
        service_description=install_config.service_description,
        seller_address=seller_address,
        contract_address=contract_address,
        token_address=token_address,
        network=network_name,
        routes=install_config.routes,
        plans=install_config.plans,
        settlement=GatewaySettlementConfig(
            repository_root=repository_root,
            full_host=full_host,
            seller_private_key=seller_private_key,
            chain_id=chain_id,
            executor_backend=executor_backend,
        ),
        sqlite_path=sqlite_path,
    )
    app.state.aimipay_install_config = install_config
    app.state.aimipay_merchant_config_path = merchant_config_path
    app.state.aimipay_public_config_path = public_config_path
    app.state.aimipay_public_base_url = public_base_url

    @app.get("/aimipay/demo/health")
    async def healthcheck() -> dict:
        return {"ok": True, "message": "merchant app demo is running"}

    @app.get("/aimipay/install")
    async def merchant_install_dashboard():
        return FileResponse(dashboard_html)

    @app.get("/aimipay/install/config")
    async def merchant_install_config():
        return {
            **app.state.aimipay_install_config.model_dump(mode="json"),
            "runtime": _runtime_profile_payload(
                app,
                runtime,
                network_profile=network_profile,
                full_host=full_host,
            ),
        }

    @app.get("/aimipay/install/config/history")
    async def merchant_install_history():
        history = list_config_history(config_path=app.state.aimipay_merchant_config_path)
        return {"versions": [item.model_dump(mode="json") for item in history]}

    @app.get("/aimipay/install/config/history/{revision}/diff")
    async def merchant_install_history_diff(revision: int):
        history = list_config_history(config_path=app.state.aimipay_merchant_config_path)
        target = next((item for item in history if item.revision == revision), None)
        if target is None:
            raise HTTPException(status_code=404, detail={"error": "revision_not_found", "revision": revision})
        current = app.state.aimipay_install_config
        return {
            "revision": revision,
            "reason": target.reason,
            "diff": diff_configs(current=current, target=target.config),
        }

    @app.post("/aimipay/install/config/route")
    async def save_route(route: MerchantRoute):
        config = upsert_route(app.state.aimipay_install_config, route)
        _apply_install_config(app, runtime, config, reason="route_upsert")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.delete("/aimipay/install/config/route")
    async def remove_route(payload: DeleteRouteRequest):
        config = delete_route(app.state.aimipay_install_config, path=payload.path, method=payload.method)
        _apply_install_config(app, runtime, config, reason="route_delete")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.post("/aimipay/install/config/route/toggle")
    async def route_toggle(payload: ToggleRouteRequest):
        config = toggle_route(
            app.state.aimipay_install_config,
            path=payload.path,
            method=payload.method,
            enabled=payload.enabled,
        )
        _apply_install_config(app, runtime, config, reason="route_toggle")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.post("/aimipay/install/config/plan")
    async def save_plan(plan: MerchantPlan):
        config = upsert_plan(app.state.aimipay_install_config, plan)
        _apply_install_config(app, runtime, config, reason="plan_upsert")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.delete("/aimipay/install/config/plan/{plan_id}")
    async def remove_plan(plan_id: str):
        config = delete_plan(app.state.aimipay_install_config, plan_id=plan_id)
        _apply_install_config(app, runtime, config, reason="plan_delete")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.post("/aimipay/install/config/plan/{plan_id}/toggle")
    async def plan_toggle(plan_id: str, payload: TogglePlanRequest):
        config = toggle_plan(app.state.aimipay_install_config, plan_id=plan_id, enabled=payload.enabled)
        _apply_install_config(app, runtime, config, reason="plan_toggle")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.post("/aimipay/install/config/branding")
    async def save_branding(payload: BrandingUpdateRequest):
        current = app.state.aimipay_install_config
        brand_update = current.brand.model_copy(
            update={
                "display_title": payload.display_title or current.brand.display_title,
                "accent_color": payload.accent_color or current.brand.accent_color,
                "support_email": payload.support_email or current.brand.support_email,
            }
        )
        config = current.model_copy(
            update={
                "service_name": payload.service_name or current.service_name,
                "service_description": payload.service_description or current.service_description,
                "brand": brand_update,
            }
        )
        _apply_install_config(app, runtime, config, reason="branding_update")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.post("/aimipay/install/config/rollback/{revision}")
    async def rollback_config(revision: int):
        config = rollback_merchant_install_config(
            config_path=app.state.aimipay_merchant_config_path,
            revision=revision,
        )
        _apply_runtime_state(app, runtime, config)
        _sync_public_config(app)
        return config.model_dump(mode="json")

    return app


def _apply_install_config(app: FastAPI, runtime, config: MerchantInstallConfig, *, reason: str) -> None:
    path = Path(app.state.aimipay_merchant_config_path)
    save_merchant_install_config(config_path=path, config=config, reason=reason)
    _apply_runtime_state(app, runtime, config)


def _apply_runtime_state(app: FastAPI, runtime, config: MerchantInstallConfig) -> None:
    app.state.aimipay_install_config = config
    app.title = config.service_name
    runtime.gateway.config.service_name = config.service_name
    runtime.gateway.config.service_description = config.service_description
    runtime.gateway.config.routes = [item for item in config.routes if item.enabled]
    runtime.gateway.config.plans = [item for item in config.plans if item.enabled]

def _sync_public_config(app: FastAPI) -> None:
    config: MerchantInstallConfig = app.state.aimipay_install_config
    public_payload = {
        "schema_version": "aimipay.merchant-install.v1",
        "service_name": config.service_name,
        "service_description": config.service_description,
        "brand": config.brand.model_dump(mode="json"),
        "merchant_base_url": app.state.aimipay_public_base_url.rstrip("/"),
        "manifest_url": f"{app.state.aimipay_public_base_url.rstrip('/')}/.well-known/aimipay.json",
        "discover_url": f"{app.state.aimipay_public_base_url.rstrip('/')}/_aimipay/discover",
        "protocol_reference_url": f"{app.state.aimipay_public_base_url.rstrip('/')}/_aimipay/protocol/reference",
        "ops_health_url": f"{app.state.aimipay_public_base_url.rstrip('/')}/_aimipay/ops/health",
        "integration_targets": ["website", "saas", "api"],
    }
    path = Path(app.state.aimipay_public_config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(public_payload, indent=2), encoding="utf-8")


def _runtime_profile_payload(app: FastAPI, runtime, *, network_profile: str, full_host: str) -> dict:
    chain = runtime.gateway.config.primary_chain()
    resolved_full_host = full_host or resolve_full_host_for_network(
        network_name=chain.network,
        profile_name=network_profile,
    )
    return {
        "network_profile": network_profile,
        "network_name": chain.network,
        "resolved_chain_rpc": resolved_full_host,
        "chain_id": chain.chain_id,
        "settlement_backend": chain.settlement_backend,
        "seller_address": chain.seller_address,
        "contract_address": chain.contract_address,
        "token_address": chain.asset_address,
        "public_base_url": app.state.aimipay_public_base_url.rstrip("/"),
    }


app = create_app()

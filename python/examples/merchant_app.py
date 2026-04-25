from __future__ import annotations

import os
import hashlib
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
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
    repository_root = os.environ.get(
        "AIMIPAY_REPOSITORY_ROOT",
        str(Path(__file__).resolve().parents[2]),
    )
    if not Path(repository_root).exists():
        repository_root = str(Path(__file__).resolve().parents[2])
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
    admin_token = (os.environ.get("AIMIPAY_ADMIN_TOKEN") or "").strip() or None
    admin_token_sha256 = (os.environ.get("AIMIPAY_ADMIN_TOKEN_SHA256") or "").strip() or None
    admin_read_token = (os.environ.get("AIMIPAY_ADMIN_READ_TOKEN") or "").strip() or None
    admin_read_token_sha256 = (os.environ.get("AIMIPAY_ADMIN_READ_TOKEN_SHA256") or "").strip() or None
    audit_log_path = (os.environ.get("AIMIPAY_AUDIT_LOG_PATH") or "").strip() or None
    if _is_production_mode() and seller_private_key not in {"", "seller_private_key"}:
        raise RuntimeError("AIMIPAY_SELLER_PRIVATE_KEY must not be provided as plain env in production mode")

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
        admin_token=admin_token,
        admin_token_sha256=admin_token_sha256,
        admin_read_token=admin_read_token,
        admin_read_token_sha256=admin_read_token_sha256,
        audit_log_path=audit_log_path,
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
    app.state.aimipay_admin_token = admin_token
    app.state.aimipay_admin_token_sha256 = admin_token_sha256
    app.state.aimipay_admin_read_token = admin_read_token
    app.state.aimipay_admin_read_token_sha256 = admin_read_token_sha256

    @app.get("/aimipay/demo/health")
    async def healthcheck() -> dict:
        return {"ok": True, "message": "merchant app demo is running"}

    @app.get("/aimipay/install")
    async def merchant_install_dashboard():
        return FileResponse(dashboard_html)

    @app.get("/aimipay/install/config")
    async def merchant_install_config(request: Request):
        _require_admin_access(request, app, action="read")
        return {
            **app.state.aimipay_install_config.model_dump(mode="json"),
            "runtime": _runtime_profile_payload(
                app,
                runtime,
                network_profile=network_profile,
                full_host=full_host,
            ),
        }

    @app.get("/aimipay/install/diagnostics")
    async def merchant_install_diagnostics(request: Request):
        _require_admin_access(request, app, action="read")
        runtime.gateway.event_logger.emit("admin_install_diagnostics_requested", caller=_caller_host(request))
        return runtime.gateway.diagnostic_bundle()

    @app.get("/aimipay/install/agent-status")
    async def merchant_install_agent_status(request: Request):
        _require_admin_access(request, app, action="read")
        runtime.gateway.event_logger.emit("admin_install_agent_status_requested", caller=_caller_host(request))
        return runtime.gateway.agent_status()

    @app.get("/aimipay/install/config/history")
    async def merchant_install_history(request: Request):
        _require_admin_access(request, app, action="read")
        history = list_config_history(config_path=app.state.aimipay_merchant_config_path)
        return {"versions": [item.model_dump(mode="json") for item in history]}

    @app.get("/aimipay/install/config/history/{revision}/diff")
    async def merchant_install_history_diff(request: Request, revision: int):
        _require_admin_access(request, app, action="read")
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
    async def save_route(request: Request, route: MerchantRoute):
        _require_admin_access(request, app, action="write")
        runtime.gateway.event_logger.emit("admin_config_route_upsert", path=route.path, method=route.method, caller=_caller_host(request))
        config = upsert_route(app.state.aimipay_install_config, route)
        _apply_install_config(app, runtime, config, reason="route_upsert")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.delete("/aimipay/install/config/route")
    async def remove_route(request: Request, payload: DeleteRouteRequest):
        _require_admin_access(request, app, action="write")
        runtime.gateway.event_logger.emit("admin_config_route_delete", path=payload.path, method=payload.method, caller=_caller_host(request))
        config = delete_route(app.state.aimipay_install_config, path=payload.path, method=payload.method)
        _apply_install_config(app, runtime, config, reason="route_delete")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.post("/aimipay/install/config/route/toggle")
    async def route_toggle(request: Request, payload: ToggleRouteRequest):
        _require_admin_access(request, app, action="write")
        runtime.gateway.event_logger.emit("admin_config_route_toggle", path=payload.path, method=payload.method, enabled=payload.enabled, caller=_caller_host(request))
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
    async def save_plan(request: Request, plan: MerchantPlan):
        _require_admin_access(request, app, action="write")
        runtime.gateway.event_logger.emit("admin_config_plan_upsert", plan_id=plan.plan_id, caller=_caller_host(request))
        config = upsert_plan(app.state.aimipay_install_config, plan)
        _apply_install_config(app, runtime, config, reason="plan_upsert")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.delete("/aimipay/install/config/plan/{plan_id}")
    async def remove_plan(request: Request, plan_id: str):
        _require_admin_access(request, app, action="write")
        runtime.gateway.event_logger.emit("admin_config_plan_delete", plan_id=plan_id, caller=_caller_host(request))
        config = delete_plan(app.state.aimipay_install_config, plan_id=plan_id)
        _apply_install_config(app, runtime, config, reason="plan_delete")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.post("/aimipay/install/config/plan/{plan_id}/toggle")
    async def plan_toggle(request: Request, plan_id: str, payload: TogglePlanRequest):
        _require_admin_access(request, app, action="write")
        runtime.gateway.event_logger.emit("admin_config_plan_toggle", plan_id=plan_id, enabled=payload.enabled, caller=_caller_host(request))
        config = toggle_plan(app.state.aimipay_install_config, plan_id=plan_id, enabled=payload.enabled)
        _apply_install_config(app, runtime, config, reason="plan_toggle")
        _sync_public_config(app)
        return config.model_dump(mode="json")

    @app.post("/aimipay/install/config/branding")
    async def save_branding(request: Request, payload: BrandingUpdateRequest):
        _require_admin_access(request, app, action="write")
        runtime.gateway.event_logger.emit("admin_config_branding_update", caller=_caller_host(request))
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
    async def rollback_config(request: Request, revision: int):
        _require_admin_access(request, app, action="write")
        runtime.gateway.event_logger.emit("admin_config_rollback", revision=revision, caller=_caller_host(request))
        config = rollback_merchant_install_config(
            config_path=app.state.aimipay_merchant_config_path,
            revision=revision,
        )
        _apply_runtime_state(app, runtime, config)
        _sync_public_config(app)
        return config.model_dump(mode="json")

    return app


def _require_admin_access(request: Request, app: FastAPI, *, action: str) -> None:
    tokens = _accepted_admin_secrets(app, action=action)
    if tokens:
        auth = request.headers.get("authorization", "")
        header_token = request.headers.get("x-aimipay-admin-token", "")
        bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if _token_matches(bearer, tokens) or _token_matches(header_token, tokens):
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "admin_token_required"})
    host = _caller_host(request)
    if host in {"127.0.0.1", "localhost", "::1", "testclient"}:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "admin_access_requires_localhost_or_token"})


def _accepted_admin_secrets(app: FastAPI, *, action: str) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    if action == "read":
        if app.state.aimipay_admin_read_token:
            values.append(("plain", app.state.aimipay_admin_read_token.strip()))
        if app.state.aimipay_admin_read_token_sha256:
            values.append(("sha256", app.state.aimipay_admin_read_token_sha256.strip()))
    if app.state.aimipay_admin_token:
        values.append(("plain", app.state.aimipay_admin_token.strip()))
    if app.state.aimipay_admin_token_sha256:
        values.append(("sha256", app.state.aimipay_admin_token_sha256.strip()))
    return [(kind, value) for kind, value in values if value]


def _token_matches(candidate: str, accepted: list[tuple[str, str]]) -> bool:
    if not candidate:
        return False
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    for kind, expected in accepted:
        if kind == "plain" and secrets.compare_digest(candidate, expected):
            return True
        if kind == "sha256" and secrets.compare_digest(digest, expected.lower()):
            return True
    return False


def _caller_host(request: Request) -> str:
    if request.client is None:
        return ""
    return (request.client.host or "").lower()


def _is_production_mode() -> bool:
    value = (os.environ.get("AIMIPAY_ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    return value in {"prod", "production", "mainnet"}


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
        "admin_token_configured": bool(
            app.state.aimipay_admin_token
            or app.state.aimipay_admin_token_sha256
            or app.state.aimipay_admin_read_token
            or app.state.aimipay_admin_read_token_sha256
        ),
        "audit_log_configured": bool(runtime.gateway.config.audit_log_path),
        "production_mode": _is_production_mode(),
        "seller_address": chain.seller_address,
        "contract_address": chain.contract_address,
        "token_address": chain.asset_address,
        "public_base_url": app.state.aimipay_public_base_url.rstrip("/"),
    }


app = create_app()

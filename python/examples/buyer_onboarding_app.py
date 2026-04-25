from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ops_tools.agent_onboarding import run_agent_onboarding
from ops_tools.buyer_setup import prepare_buyer_install_env
from ops_tools.install_doctor import build_install_report, format_install_report_html


class MerchantUrlUpdateRequest(BaseModel):
    merchant_url: str
    network_profile: str | None = None


def create_app() -> FastAPI:
    repository_root = Path(os.environ.get("AIMIPAY_REPOSITORY_ROOT", Path(__file__).resolve().parents[2])).resolve()
    python_dir = repository_root / "python"
    env_file = python_dir / ".env.local"
    wallet_file = python_dir / ".wallets" / "buyer-wallet.json"
    onboarding_html = python_dir / ".agent" / "buyer-onboarding.html"
    admin_token = (os.environ.get("AIMIPAY_ADMIN_TOKEN") or "").strip() or None

    app = FastAPI(title="AimiPay Buyer Onboarding")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8011",
            "http://localhost:8011",
            "http://127.0.0.1:8010",
            "http://localhost:8010",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/aimipay/buyer/onboarding")
    async def buyer_onboarding_page():
        _render_onboarding_html(repository_root, onboarding_html)
        return FileResponse(onboarding_html)

    @app.get("/aimipay/buyer/onboarding/data")
    async def buyer_onboarding_data():
        report = build_install_report(repository_root=repository_root)
        report["security"] = _security_status(admin_token=admin_token)
        return report

    @app.post("/aimipay/buyer/onboarding/merchant-url")
    async def update_merchant_url(request: Request, payload: MerchantUrlUpdateRequest):
        _require_local_or_token(request, admin_token)
        prepare_buyer_install_env(
            repository_root=repository_root,
            env_file=env_file,
            merchant_urls=[payload.merchant_url],
            network_profile=payload.network_profile,
            output_json=False,
            emit_output=False,
        )
        run_agent_onboarding(
            repository_root=repository_root,
            env_file=env_file,
            wallet_file=wallet_file,
            output_json=False,
            emit_output=False,
        )
        report = _render_onboarding_html(repository_root, onboarding_html)
        report["security"] = _security_status(admin_token=admin_token)
        return report

    @app.post("/aimipay/buyer/onboarding/refresh")
    async def refresh_onboarding(request: Request):
        _require_local_or_token(request, admin_token)
        run_agent_onboarding(
            repository_root=repository_root,
            env_file=env_file,
            wallet_file=wallet_file,
            output_json=False,
            emit_output=False,
        )
        report = _render_onboarding_html(repository_root, onboarding_html)
        report["security"] = _security_status(admin_token=admin_token)
        return report

    return app


def _require_local_or_token(request: Request, admin_token: str | None) -> None:
    token = (admin_token or "").strip()
    if token:
        auth = request.headers.get("authorization", "")
        header_token = request.headers.get("x-aimipay-admin-token", "")
        bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if secrets.compare_digest(bearer, token) or secrets.compare_digest(header_token, token):
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error": "admin_token_required"})

    host = "" if request.client is None else (request.client.host or "").lower()
    origin = request.headers.get("origin")
    if host not in {"127.0.0.1", "localhost", "::1", "testclient"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "local_access_required"})
    if origin:
        origin_host = (urlparse(origin).hostname or "").lower()
        if origin_host not in {"127.0.0.1", "localhost", "::1"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error": "local_origin_required"})


def _security_status(*, admin_token: str | None) -> dict:
    return {
        "admin_token_configured": bool(admin_token),
        "cors_origins": ["http://127.0.0.1:8011", "http://localhost:8011", "http://127.0.0.1:8010", "http://localhost:8010"],
        "local_origin_required": True,
    }


def _render_onboarding_html(repository_root: Path, output_path: Path) -> dict:
    report = build_install_report(repository_root=repository_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_install_report_html(report), encoding="utf-8")
    return report

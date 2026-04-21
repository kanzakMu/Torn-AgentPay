from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
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

    app = FastAPI(title="AimiPay Buyer Onboarding")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
        return report

    @app.post("/aimipay/buyer/onboarding/merchant-url")
    async def update_merchant_url(payload: MerchantUrlUpdateRequest):
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
        return report

    @app.post("/aimipay/buyer/onboarding/refresh")
    async def refresh_onboarding():
        run_agent_onboarding(
            repository_root=repository_root,
            env_file=env_file,
            wallet_file=wallet_file,
            output_json=False,
            emit_output=False,
        )
        report = _render_onboarding_html(repository_root, onboarding_html)
        return report

    return app


def _render_onboarding_html(repository_root: Path, output_path: Path) -> dict:
    report = build_install_report(repository_root=repository_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_install_report_html(report), encoding="utf-8")
    return report


from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from seller import (
    GatewayConfig,
    HostedMerchant,
    SqliteHostedGatewayRegistry,
    hosted_api_key_hash,
    install_hosted_gateway,
)
from shared import MerchantRoute


def build_app() -> FastAPI:
    app = FastAPI(title="AimiPay Hosted Gateway Example")
    sqlite_path = os.getenv("AIMIPAY_HOSTED_SQLITE_PATH")
    registry = None
    if sqlite_path:
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        registry = SqliteHostedGatewayRegistry(sqlite_path)

    install_hosted_gateway(
        app,
        [
            HostedMerchant(
                merchant_id="research",
                api_key_sha256=hosted_api_key_hash(os.getenv("AIMIPAY_RESEARCH_MERCHANT_KEY", "research-secret")),
                config=GatewayConfig(
                    service_name="Research Copilot",
                    service_description="Paid research API for AI agents",
                    seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                    contract_address="0x1000000000000000000000000000000000000001",
                    token_address="0x2000000000000000000000000000000000000002",
                    chain_id=31337,
                    routes=[
                        MerchantRoute(
                            path="/tools/research",
                            method="POST",
                            price_atomic=250_000,
                            capability_id="research-web-search",
                            capability_type="web_search",
                            description="Paid web research capability",
                        )
                    ],
                ),
            ),
            HostedMerchant(
                merchant_id="coding",
                api_key_sha256=hosted_api_key_hash(os.getenv("AIMIPAY_CODING_MERCHANT_KEY", "coding-secret")),
                config=GatewayConfig(
                    service_name="Coding Agent Toolsmith",
                    service_description="Paid code review and patch planning APIs",
                    seller_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
                    contract_address="0x1000000000000000000000000000000000000001",
                    token_address="0x2000000000000000000000000000000000000002",
                    chain_id=31337,
                    routes=[
                        MerchantRoute(
                            path="/tools/code-review",
                            method="POST",
                            price_atomic=400_000,
                            capability_id="coding-agent-code-review",
                            capability_type="code_review",
                            description="Paid code review capability",
                        )
                    ],
                ),
            ),
        ],
        registry=registry,
    )

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "aimipay-hosted-gateway-example",
            "merchants": "/_aimipay/hosted/merchants",
            "marketplace": "/_aimipay/marketplace/capabilities",
        }

    return app


app = build_app()

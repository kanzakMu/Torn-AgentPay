from __future__ import annotations

from fastapi import FastAPI

from seller.gateway import GatewayConfig, GatewaySettlementConfig, install_gateway


def build_app() -> FastAPI:
    app = FastAPI(title="Torn-AgentPay Minimal Seller Example")
    install_gateway(
        app,
        GatewayConfig(
            service_name="Minimal Seller Example",
            service_description="A minimal self-hosted Torn-AgentPay seller implementation example.",
            seller_address="TVaEiLLej394ZxVmHZXYg3HprssbpdcsmW",
            contract_address="0x1000000000000000000000000000000000000001",
            token_address="0x2000000000000000000000000000000000000002",
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://tron.local",
                seller_private_key="0x59c6995e998f97a5a0044966f0945382d7f4a3f1f3f7e61a821a3d1d021b6d2d",
                chain_id=31337,
                executor_backend="local_smoke",
            ),
        ),
    )

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "minimal-seller-example",
            "well_known_manifest": "/.well-known/aimipay.json",
            "discover": "/_aimipay/discover",
            "protocol_reference": "/_aimipay/protocol/reference",
        }

    return app


app = build_app()

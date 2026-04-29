from __future__ import annotations

from fastapi import FastAPI

from seller import install_sellable_capability


def build_app() -> FastAPI:
    app = FastAPI(title="Torn-AgentPay HTTP 402 Paid API Example")
    merchant = install_sellable_capability(
        app,
        service_name="HTTP 402 Research Copilot",
        service_description="Example paid API using the Torn-AgentPay HTTP 402 adapter.",
        seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        contract_address="0x1000000000000000000000000000000000000001",
        token_address="0x2000000000000000000000000000000000000002",
        chain_id=31337,
    )

    @merchant.paid_api(
        path="/tools/research",
        price_atomic=250_000,
        capability_type="web_search",
        capability_id="research-web-search",
        description="Paid research API unlocked by a settled Torn-AgentPay payment.",
    )
    def research_tool(body: dict) -> dict:
        query = body.get("query", "")
        return {
            "query": query,
            "result": f"research result for {query}",
            "paid": True,
        }

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "service": "http402-paid-api-example",
            "paid_route": "/tools/research",
            "discover": "/_aimipay/discover",
            "http402_adapter": "/_aimipay/protocol/reference",
        }

    return app


app = build_app()

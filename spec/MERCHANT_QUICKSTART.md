# Merchant Quickstart

Turn a FastAPI route into an agent-paid API.

## 1. Create A Merchant Config

```bash
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant init --service-name "Research Copilot"
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant verify --config aimipay.merchant.json
```

The generated config is a starting point. Replace placeholder addresses before production.

## 2. Wrap A Paid Route

```python
from fastapi import FastAPI
from seller import install_sellable_capability

app = FastAPI()

merchant = install_sellable_capability(
    app,
    service_name="Research Copilot",
    service_description="Pay-per-use research for AI agents",
    seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    contract_address="0x1000000000000000000000000000000000000001",
    token_address="0x2000000000000000000000000000000000000002",
)


@merchant.paid_api(
    path="/tools/research",
    price_atomic=250_000,
    capability_id="research-web-search",
    capability_type="web_search",
)
def research_tool(body: dict) -> dict:
    return {"result": f"research result for {body['query']}"}
```

## 3. Run The Local Merchant

```bash
PYTHONPATH=python uvicorn python.examples.http402_paid_api_app:app --reload
```

An unpaid request returns `402 Payment Required` with:

- `schema_version = aimipay.http402.v1`
- x402-style `accepts`
- `next_actions` for AI hosts

A paid retry includes:

- `X-PAYMENT` or `X-AIMIPAY-PAYMENT-ID`
- `X-PAYMENT-RESPONSE` receipt on success

## 4. Inspect The Agent-Readable Surface

```bash
curl http://localhost:8000/.well-known/aimipay.json
curl http://localhost:8000/_aimipay/registry/capabilities
curl http://localhost:8000/_aimipay/protocol/http402-conformance
```

Protected merchant ops:

```bash
curl http://localhost:8000/_aimipay/ops/billing/summary
curl http://localhost:8000/_aimipay/ops/receipts
curl http://localhost:8000/_aimipay/ops/webhooks/outbox
```

Configure an admin token before exposing ops endpoints beyond localhost.

## 5. Run The Coding-Agent Paid Flow Demo

```bash
PYTHONPATH=python python python/examples/coding_agent_paid_flow_demo.py
```

The demo performs a full local loop:

1. AI buyer requests `/tools/code-review`
2. Merchant returns HTTP 402
3. Buyer prepares and submits payment
4. Merchant settles locally
5. Buyer retries with payment header
6. Merchant returns code-review result and receipt

## 6. Hosted Gateway MVP

Use `seller.install_hosted_gateway(...)` when multiple merchants should run behind one service.

Hosted endpoints:

- `GET /_aimipay/hosted/merchants`
- `GET /_aimipay/marketplace/capabilities`
- `GET /_aimipay/hosted/merchants/{merchant_id}/admin-summary`

Use `SqliteHostedGatewayRegistry` to persist hosted merchant config between runs.

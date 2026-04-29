# HTTP 402 Adapter

Torn-AgentPay now exposes an x402-style HTTP 402 adapter for merchant APIs.

The goal is not to copy one settlement rail. The goal is to make paid resources behave like agent-readable HTTP resources:

1. An AI host calls a paid route.
2. The route returns `402 Payment Required` with machine-readable payment requirements.
3. The AI host quotes budget, prepares a purchase, submits payment, and retries the route with `X-PAYMENT` or `X-AIMIPAY-PAYMENT-ID`.
4. The seller verifies the payment is settled and returns the protected resource with `X-PAYMENT-RESPONSE`.

## Merchant Usage

```python
from fastapi import FastAPI
from seller import install_sellable_capability

app = FastAPI()

merchant = install_sellable_capability(
    app,
    service_name="Research Copilot",
    service_description="Pay-per-use research and market data",
    seller_address="TRX_SELLER",
    contract_address="TRX_CONTRACT",
    token_address="TRX_USDT",
    chain_id=31337,
)


@merchant.paid_api(
    path="/tools/research",
    price_atomic=250_000,
    capability_type="web_search",
    capability_id="research-web-search",
    description="Paid research API",
)
def research_tool(body: dict) -> dict:
    return {"result": f"research result for {body['query']}"}
```

## 402 Response Shape

When no payment is supplied, the route returns:

```json
{
  "schema_version": "aimipay.http402.v1",
  "kind": "payment_required",
  "x402_compat": {
    "version": 1,
    "request_header": "X-PAYMENT",
    "response_header": "X-PAYMENT-RESPONSE",
    "settlement_rail": "tron-contract"
  },
  "accepts": [
    {
      "scheme": "aimipay-tron-v1",
      "chain": "tron",
      "asset_symbol": "USDT",
      "amount_atomic": 250000,
      "resource": "https://merchant.example/tools/research",
      "capability_id": "research-web-search",
      "extra": {
        "discover_url": "https://merchant.example/_aimipay/discover",
        "payment_intents_url": "https://merchant.example/_aimipay/payment-intents"
      }
    }
  ],
  "next_actions": []
}
```

## Headers

Request headers accepted by protected routes:

- `X-PAYMENT`: x402-style payment header. Torn-AgentPay accepts a payment id directly or JSON such as `{"payment_id":"pay_123"}`.
- `X-AIMIPAY-PAYMENT-ID`: direct Torn-AgentPay payment id fallback.

Response headers:

- `Payment-Required: true` on 402 responses.
- `X-AIMIPAY-Protocol: aimipay.http402.v1` on 402 responses.
- `X-PAYMENT-RESPONSE` on successful paid responses.

## Safety Boundary

The adapter only releases the protected handler when the referenced payment exists and is `settled`.

If the payment exists but is not terminal, the adapter returns another 402 with:

- `error = payment_not_settled`
- current `payment_status`
- first `next_actions` item pointing to `aimipay.finalize_payment`

This keeps the host from accidentally consuming paid resources before settlement finality.

The adapter also binds payment to the protected resource:

- `payment.route_path` must match the current paid route
- `payment.request_path` must match when present
- `payment.amount_atomic` must be greater than or equal to the route price

This prevents a settled payment for one resource or a cheaper resource from being replayed against another paid route.

## Buyer Auto-Retry

Buyer clients can handle the whole 402 flow:

```python
result = client.request_paid_resource(
    "/tools/research",
    json_body={"query": "agent payments"},
    budget_limit_atomic=300_000,
)

payload = result["response"].json()
receipt = result["payment_response"]
```

`request_paid_resource` performs:

1. call the resource
2. parse `aimipay.http402.v1`
3. prepare purchase
4. submit payment
5. finalize payment
6. retry with `X-PAYMENT` and `X-AIMIPAY-PAYMENT-ID`

The returned `payment_response` is decoded from `X-PAYMENT-RESPONSE`.

## Receipt

Successful paid responses include a compact JSON receipt in `X-PAYMENT-RESPONSE`:

```json
{
  "schema_version": "aimipay.http402-payment-response.v1",
  "kind": "payment_receipt",
  "payment_id": "pay_123",
  "status": "settled",
  "route_path": "/tools/research",
  "amount_atomic": 250000,
  "required_amount_atomic": 250000,
  "buyer_address": "TRX_BUYER",
  "seller_address": "TRX_SELLER"
}
```

## Commercial Companion Endpoints

Merchants and external AI hosts can inspect the broader product surface without a dashboard:

- `GET /_aimipay/registry/capabilities` returns enabled auto-purchasable capabilities, pricing, budget hints, and approval flags.
- `GET /_aimipay/protocol/http402-conformance` returns the implemented 402 profile and explicit compatibility boundaries.
- `GET /_aimipay/ops/billing/summary` returns protected revenue and payment counts by route and status.
- `GET /_aimipay/ops/receipts` returns protected payment-level reconciliation records.
- `GET /_aimipay/ops/webhooks/outbox` returns protected lifecycle events when `GatewayConfig.webhook_urls` is configured.

## Why This Matters

This turns Torn-AgentPay from a payment-channel demo into a merchant-facing product surface:

- developers can wrap an API route in one decorator
- AI hosts receive budget and payment instructions instead of a human-only error
- settled payments unlock the resource through ordinary HTTP
- the same paid route is discoverable through manifest, MCP, and skill flows

# Facilitator And Mandates

AimiPay supports an x402-style HTTP flow and AP2-inspired authorization records without claiming wire compatibility with Coinbase x402 facilitator APIs or Visa/Google AP2 messages.

## HTTP 402 Flow

1. AI host requests a protected merchant resource.
2. Merchant returns `402 Payment Required`.
3. Response includes:
   - `schema_version = aimipay.http402.v1`
   - AimiPay-native `accepts`
   - x402-style `x402.accepts`
   - `next_actions`
4. Buyer creates or reuses a channel-backed payment.
5. Buyer retries with `X-PAYMENT` or `X-AIMIPAY-PAYMENT-ID`.
6. Merchant returns the resource and `X-PAYMENT-RESPONSE`.

## x402 Compatibility Helpers

Module:

```python
from seller.x402_compat import (
    build_x402_payment_requirement,
    encode_x402_payment,
    decode_x402_payment,
    build_x402_payment_response,
)
```

Use this for host adapters that expect x402-shaped payment requirement and payment response objects.

Compatibility boundary:

- Supported: HTTP 402, `X-PAYMENT`, `X-PAYMENT-RESPONSE`, x402-shaped accepts.
- Not yet claimed: Coinbase facilitator wire compatibility.

## Facilitator MVP

Install a local facilitator on a FastAPI app:

```python
from seller import install_facilitator

install_facilitator(app, gateway_runtime)
```

Endpoints:

- `POST /_aimipay/facilitator/verify`
- `POST /_aimipay/facilitator/settle`

Verify request:

```json
{
  "payment": "encoded-or-json-payment",
  "resource": "/tools/research",
  "amount_atomic": 250000
}
```

Settle request:

```json
{
  "payment": "encoded-or-json-payment"
}
```

The facilitator currently delegates to the local `GatewayRuntime`. It is the correct seam for future KYT, risk checks, retries, chain finality, and external facilitator compatibility.

## Mandates

Mandates preserve buyer authorization context before an agent spends funds.

Module:

```python
from shared import create_intent_mandate, create_payment_mandate, verify_mandate_signature
```

Intent mandate:

```python
intent = create_intent_mandate(
    buyer_address="TRX_BUYER",
    merchant_base_url="https://merchant.example",
    capability_id="research-web-search",
    max_amount_atomic=300_000,
    expires_at=1760000000,
    secret="host-secret",
)
```

Payment mandate:

```python
payment = create_payment_mandate(
    intent_mandate=intent,
    payment_id="pay_123",
    seller_address="TRX_SELLER",
    route_path="/tools/research",
    amount_atomic=250_000,
    expires_at=1760000000,
    secret="host-secret",
)
```

Compatibility boundary:

- Supported: signed intent and payment authorization records with amount caps and expiry.
- Not yet claimed: Visa AP2 or Google AP2 wire-format compatibility.

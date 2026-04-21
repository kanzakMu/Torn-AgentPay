# Agent Integration Guide

This guide describes the recommended lifecycle for integrating an AI agent with Torn-AgentPay.

## Goal

An agent should be able to:

- check whether its buyer wallet exists and looks funded enough
- discover paid offers
- estimate cost
- prepare or open a channel
- create a payment intent
- execute settlement
- query status
- recover unfinished payments
- optionally finalize payment to a terminal state

## Recommended Lifecycle

1. Check wallet and funding readiness
   - run `python -m ops_tools.wallet_setup --force-create` during installation or first run when a wallet is missing
   - run `python -m ops_tools.wallet_funding` before live Tron purchases
2. Discover offers
   - `GET /.well-known/aimipay.json`
   - `GET /_aimipay/discover`
3. Estimate cost
   - use route metadata such as `price_atomic`, `budget_hint`, `minimum_prepaid_atomic`, `supports_auto_purchase`
4. Prepare or open channel
   - `POST /_aimipay/channels/open`
5. Build or verify authorization
   - use canonical protocol rules from `GET /_aimipay/protocol/reference`
6. Create payment intent
   - `POST /_aimipay/payment-intents`
7. Execute settlement
   - `POST /_aimipay/settlements/execute`
8. Confirm settlement when payment remains `submitted`
   - `POST /_aimipay/settlements/reconcile`
9. Query payment status
   - `GET /_aimipay/payments/{payment_id}`
10. Recover unfinished payment
   - `GET /_aimipay/payments/recover`
   - `GET /_aimipay/payments/pending`

`GET /_aimipay/payments/{payment_id}` is read-only. It reports lifecycle state but does not trigger settlement confirmation as a side effect.

## Agent-Friendly Fields

Payment responses include:

- `payment_intent_id`
- `status`
- `action_required`
- `next_step`
- `safe_to_retry`
- `human_approval_required`

Offer responses should be interpreted with:

- `capability_id`
- `capability_type`
- `unit_price_atomic`
- `minimum_prepaid_atomic`
- `suggested_prepaid_atomic`
- `expected_latency_ms`
- `requires_human_approval`
- `supports_auto_purchase`
- `safe_retry_policy`
- `settlement_backend`

## Minimal Flow Example

```python
from buyer import BuyerClient, BuyerWallet, build_default_tron_provisioner

client = BuyerClient(
    merchant_base_url="https://merchant.example",
    full_host="https://nile.trongrid.io",
    wallet=BuyerWallet(address="...", private_key="..."),
    provisioner=build_default_tron_provisioner(repository_root="<repository-root>"),
    repository_root="<repository-root>",
)

offers = client.discover_offers()
estimate = client.estimate_budget(capability_id=offers[0]["capability_id"])
session = client.ensure_channel_for_route(route_path=offers[0]["route_path"])
intent = client.create_payment_intent(
    channel_session=session,
    route_path=offers[0]["route_path"],
    request_body='{"task":"research"}',
    idempotency_key="task-123",
)

if intent["next_step"] == "execute_settlement":
    payment = client.execute_payment(intent["payment_id"])
    if payment["next_step"] == "confirm_settlement":
        payment = client.reconcile_payment(payment["payment_id"])

# Or let the client drive execute + reconcile until terminal:
payment = client.finalize_payment(intent["payment_id"])
```

## Retry Guidance

- Safe retry after create timeout:
  - query `GET /_aimipay/payments/recover?idempotency_key=<same-key>`
- Safe retry after submit timeout:
  - query `GET /_aimipay/payments/{payment_id}`
- If status remains `submitted`:
  - call `POST /_aimipay/settlements/reconcile` or the equivalent client helper
- If the runtime prefers one-shot orchestration:
  - call `client.finalize_payment(payment_id)` or the MCP equivalent
- Do not blindly create a new payment after timeout unless recovery proves no existing intent is present.

## Current Best Practice

- check wallet readiness before calling paid capability tools
- let first-start host integrations run onboarding automatically so the agent can create a wallet before its first paid action
- on local demo installs, allow `local_smoke` to proceed without live Tron funding
- on Nile or mainnet installs, guide the user toward TRX gas funding and USDT payment funding first
- Always set `idempotency_key`
- Persist `payment_id`, `idempotency_key`, and `channel_id` in the agent runtime
- Use `safe_to_retry` and `next_step` rather than hard-coded branching
- Treat `submitted` as in-flight, not final settlement confirmation

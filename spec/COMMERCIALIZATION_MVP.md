# Commercialization MVP

This project is now shaped as an AI-facing payment product, not a human dashboard. The commercial surface is a set of structured endpoints, SDK helpers, lifecycle receipts, and install artifacts that an external AI host can inspect and operate.

## 1. Merchant SDK

Merchants can wrap a FastAPI route with `install_sellable_capability(...).paid_api(...)`.

The wrapper publishes route metadata, returns HTTP 402 payment requirements, verifies settlement before execution, and emits `X-PAYMENT-RESPONSE` receipts after the protected handler runs.

Developer CLI MVP:

```bash
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant init --service-name "Research Copilot"
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant verify --config aimipay.merchant.json
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant dev
PYTHONPATH=python python -m ops_tools.aimipay_cli demo --json
```

## 2. Hosted Gateway Shape

The seller gateway exposes:

- `/.well-known/aimipay.json`
- `/_aimipay/discover`
- `/_aimipay/registry/capabilities`
- `/_aimipay/protocol/reference`
- `/_aimipay/protocol/http402-conformance`
- `/_aimipay/payment-intents`
- `/_aimipay/payments/{payment_id}`

These are the public, agent-readable surfaces. Ops endpoints remain protected by admin token or localhost-only access.

Hosted multi-tenant MVP is available through `seller.install_hosted_gateway(...)`.

It mounts isolated merchants under:

- `/merchants/{merchant_id}/.well-known/aimipay.json`
- `/merchants/{merchant_id}/_aimipay/...`

And exposes hosted-level discovery:

- `GET /_aimipay/hosted/merchants`
- `GET /_aimipay/marketplace/capabilities`
- `GET /_aimipay/hosted/merchants/{merchant_id}/admin-summary`

The hosted admin summary supports `X-AimiPay-Merchant-Key` when a merchant API key hash is configured.

## 3. Reconciliation And Billing API

Seller ops can read machine-parseable billing state through:

- `GET /_aimipay/ops/billing/summary`
- `GET /_aimipay/ops/billing/statement`
- `GET /_aimipay/ops/payouts/report`
- `GET /_aimipay/ops/receipts`

The billing summary groups payment counts and atomic revenue by status and route. The receipt list returns payment-level audit records that can be reconciled against chain settlement, invoices, or a merchant CRM.

Statements, payout reports, and receipts include deterministic hashes so downstream systems can detect accidental mutation.

## 4. Webhook Lifecycle

`GatewayConfig.webhook_urls` enables an in-process webhook outbox:

- `payment.intent_created`
- `payment.authorized`
- `payment.submitted`
- `payment.settled`
- `payment.failed`
- `payment.expired`

The current implementation stores events in `GET /_aimipay/ops/webhooks/outbox`. When `GatewayConfig.webhook_secret` is configured, each event includes an `hmac-sha256` signature. This gives external AI hosts and merchant backends a deterministic integration target before introducing async delivery workers.

## 5. Pricing Model Expansion

Routes already publish:

- `price_atomic`
- `pricing_model`
- `usage_unit`
- `minimum_prepaid_atomic`
- `suggested_prepaid_atomic`
- `budget_hint`

This supports fixed per-call pricing today and leaves the contract surface open for metered units, prepaid bundles, and subscription plans.

## 6. HTTP 402 And Agentic Commerce Alignment

The adapter follows the same user journey as x402-style payment flows:

1. resource request
2. `402 Payment Required`
3. machine-readable payment requirements
4. host payment execution
5. retry with `X-PAYMENT`
6. resource response with `X-PAYMENT-RESPONSE`

`/_aimipay/protocol/http402-conformance` states exactly what is implemented and what is not claimed. This avoids overclaiming Coinbase x402 or Visa AP2 wire compatibility while keeping the product direction aligned with both.

`/_aimipay/protocol/agentic-commerce-mandate-template` returns an AP2-inspired mandate template for preserving buyer authorization context before an agent spends funds.

Engineering surfaces now include:

- `seller.x402_compat`: x402-style payment requirement, payment header encoding/decoding, and payment response helpers.
- `seller.install_facilitator(...)`: local facilitator endpoints for `verify` and `settle`.
- `shared.mandates`: signed intent mandate and payment mandate helpers.

## 7. Capability Registry

`GET /_aimipay/registry/capabilities` returns enabled, auto-purchasable capabilities with:

- route metadata
- asset and amount
- pricing model
- budget hints
- approval requirements
- safe retry policy

This is the marketplace seed. A directory or marketplace can crawl these registries without understanding the merchant implementation. The hosted gateway also aggregates merchant capabilities into `/_aimipay/marketplace/capabilities`.

## 8. Budget And Risk Policy

Routes can express:

- `supports_auto_purchase`
- `requires_human_approval`
- `budget_hint`
- `safe_retry_policy`
- `auth_requirements`

External AI hosts should use these fields to decide whether to auto-pay, ask the user, or refuse the purchase.

Buyer-side enforcement is available through `BuyerBudgetPolicy`, which supports per-purchase limits, daily limits, trusted sellers, blocked sellers, and approval thresholds.

## 9. Vertical Demos

The strongest demo verticals are:

- paid research APIs
- coding agent tools
- data enrichment
- model/tool routing
- paid retrieval or indexing

The HTTP 402 example app starts with the paid research route because it is easy for agents to understand and easy for merchants to monetize.

The coding-agent vertical demo is available at `python/examples/coding_agent_paid_tools_app.py`, with paid code review and patch planning capabilities.

The end-to-end buyer flow is available at `python/examples/coding_agent_paid_flow_demo.py`. It performs a real local 402 round trip: request protected tool, receive payment requirements, pay, retry, and receive a settled receipt.

## 10. Packaging And Pricing

The packaging story should stay simple:

- open-source protocol and local gateway
- merchant SDK for route wrapping
- hosted seller gateway for teams that do not want to run settlement infrastructure
- marketplace/registry layer for discoverability
- enterprise plan for compliance, reconciliation, webhook delivery, and managed keys

The technical product is now ready for that pricing story because it has discoverability, payment enforcement, receipts, reconciliation, and lifecycle events.

## Remaining Production Hardening

This MVP intentionally keeps async webhook delivery, persistent hosted tenant storage, fiat invoice rendering, and external x402 facilitator compatibility as next-stage production work. The current code establishes stable integration contracts first.

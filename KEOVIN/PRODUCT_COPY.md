# KEOVIN Product Copy

Use this copy when the website needs to describe the current product accurately.

## One-Liner

Turn any API into an agent-paid API.

## Short Description

KEOVIN AimiPay lets AI hosts discover paid capabilities, enforce buyer budgets, complete HTTP 402 payments, and return receipts that merchants can reconcile.

## Product Pillars

### Agent-Paid API Gateway

Wrap a FastAPI route with `paid_api(...)`. Unpaid calls return agent-readable HTTP 402 requirements. Paid calls unlock the resource and include `X-PAYMENT-RESPONSE`.

### Buyer Runtime

AI hosts can discover offers, quote budgets, apply spend policies, prepare payments, submit voucher-backed purchases, finalize settlement, and retry protected resources automatically.

### Merchant Operations

Merchants get capability registry, billing summary, receipts, payout reports, webhook events, and diagnostics without needing a human dashboard.

### Hosted Commerce Layer

Hosted gateway MVP supports multiple merchants, merchant API keys, a marketplace capability index, and persistent merchant registry storage.

### Trust And Authorization

The protocol includes route binding, amount enforcement, x402-style payment requirements, facilitator verify/settle endpoints, signed webhook events, and AP2-inspired mandates.

## Proof Points

- Python tests: 178 passed
- Contract tests: 13 passing
- Coding-agent paid flow demo: request, 402, payment, retry, receipt
- Skill-only and MCP install paths for external AI hosts

## Call To Action

Start with one paid route. Let agents pay for it safely.

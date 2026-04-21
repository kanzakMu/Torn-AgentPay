# MCP Integration Guide

This document defines the recommended MCP-facing tool surface for AimiPay Tron.

## Why MCP

Agents should not need to manually assemble low-level HTTP payloads, digest rules, or settlement decisions. A thin MCP server or adapter should expose a stable lifecycle surface.

## Recommended Tool Names

- `aimipay.list_offers`
- `aimipay.estimate_budget`
- `aimipay.open_channel`
- `aimipay.create_payment`
- `aimipay.execute_payment`
- `aimipay.reconcile_payment`
- `aimipay.finalize_payment`
- `aimipay.get_payment_status`
- `aimipay.list_pending_payments`
- `aimipay.recover_payment`
- `aimipay.check_wallet_funding`
- `aimipay.create_wallet`
- `aimipay.run_onboarding`
- `aimipay.get_startup_onboarding`

## Tool Semantics

### `aimipay.list_offers`

- Input:
  - merchant base URL
- Output:
  - list of offers
  - `next_step = estimate_budget`

### `aimipay.estimate_budget`

- Input:
  - `capability_id`
  - optional `expected_units`
  - optional `budget_limit_atomic`
- Output:
  - evaluated offer
  - estimated total cost
  - `human_approval_required`
  - `next_step = prepare_or_open_channel`

### `aimipay.open_channel`

- Input:
  - `route_path`
  - optional deposit
  - optional ttl
- Output:
  - channel session
  - `next_step = create_payment_intent`

### `aimipay.create_payment`

- Input:
  - channel session
  - route path
  - request body
  - `idempotency_key`
- Output:
  - payment intent
  - `safe_to_retry`
  - `next_step`
  - `action_required`

### `aimipay.execute_payment`

- Input:
  - `payment_id`
- Output:
  - updated payment
  - `next_step = query_payment_status`

### `aimipay.get_payment_status`

- Input:
  - `payment_id`
- Output:
  - current payment status
  - `safe_to_retry`
  - `next_step`

This tool is read-only. Agents should use `aimipay.reconcile_payment` or `aimipay.finalize_payment` to advance a submitted payment toward finality.

### `aimipay.reconcile_payment`

- Input:
  - `payment_id`
- Output:
  - reconciled payment state
  - `next_step`
  - `safe_to_retry`

### `aimipay.finalize_payment`

- Input:
  - `payment_id`
  - optional `max_attempts`
  - optional `execute_if_needed`
- Output:
  - terminal or latest payment state after execute/reconcile attempts
  - `next_step`
  - `safe_to_retry`

### `aimipay.list_pending_payments`

- Input:
  - none
- Output:
  - unfinished payments in `pending`, `authorized`, or `submitted`

### `aimipay.recover_payment`

- Input:
  - optional `payment_id`
  - optional `idempotency_key`
  - optional `channel_id`
- Output:
  - matching payment records for recovery

### `aimipay.check_wallet_funding`

- Input:
  - optional `env_file`
- Output:
  - wallet readiness
  - funding guidance
  - funding checklist
  - `next_step = create_wallet | fund_wallet | ready_to_purchase`

This tool is intended for installation-time and first-run orchestration before an agent attempts paid purchases.

### `aimipay.create_wallet`

- Input:
  - optional `env_file`
  - optional `wallet_file`
  - optional `force_create`
- Output:
  - created or reused wallet details
  - funding summary
  - `next_step`

Use this tool when the host detects `action_required = create_wallet`.

### `aimipay.run_onboarding`

- Input:
  - optional `env_file`
  - optional `wallet_file`
  - optional `force_create_wallet`
- Output:
  - onboarding report
  - saved onboarding report path
  - `next_step`

This tool is the recommended first-start entrypoint for host integrations that want one call to bootstrap the local buyer wallet and funding guidance.

### `aimipay.get_startup_onboarding`

- Input:
  - none
- Output:
  - startup onboarding summary
  - host action block suitable for first-screen UI

Hosts that do not render custom fields from `initialize` should call this tool immediately after connection.

## Initialize Extensions

The AimiPay MCP server also returns onboarding hints directly from `initialize`:

- `result.instructions`
  - short first-screen guidance text for host UI
- `result.meta["aimipay/startupOnboarding"]`
  - structured onboarding summary including `next_step`, `action_required`, and `host_action`
- `result.meta["aimipay/startupCard"]`
  - recommended first-screen card payload for host UI rendering

Hosts like Claude/CUA/Codex should prefer showing this metadata on first connect when custom server metadata is available.

## Recommended First-Screen Card Schema

`result.meta["aimipay/startupCard"]` uses this shape:

```json
{
  "schema_version": "aimipay.startup-card.v1",
  "kind": "onboarding_card",
  "visible": true,
  "tone": "warning",
  "title": "Fund Wallet",
  "summary": "Fund the wallet before buying. [1] Add TRX [2] Add USDT",
  "primary_action": {
    "action": "fund_wallet",
    "label": "Fund Wallet"
  },
  "secondary_actions": [
    {
      "action": "aimipay.get_startup_onboarding",
      "label": "View Onboarding Details"
    }
  ],
  "checklist": ["Add TRX", "Add USDT"],
  "resources": [
    {
      "label": "Testnet Faucet",
      "url": "https://example.test/faucet"
    }
  ],
  "status": {
    "completed": false,
    "next_step": "fund_wallet",
    "action_required": "fund_wallet"
  }
}
```

### Host Mapping

- Claude-style hosts
  - render `title`, `summary`, and `primary_action`
  - place `checklist` and `resources` in expandable details
- CUA-style hosts
  - render `summary` as the first assistant-visible instruction
  - map `primary_action.action` into the next suggested agent action
- Codex-style hosts
  - surface `summary` and `primary_action.label` in the first-screen plugin banner
  - expose `secondary_actions` as follow-up buttons or quick actions when supported

## Current Code Anchor

The current official adapter surface is the Python classes:

- `buyer.adapter.AimiPayAgentAdapter`
- `buyer.mcp.AimiPayMcpServer`

`AimiPayMcpServer` currently provides:

- `initialize`
- `initialized` / `notifications/initialized`
- `tools/list`
- `tools/call`
- JSON line based `serve_stdio(...)`

This is a minimal MCP-style server skeleton without an external MCP SDK dependency. It is intended as the stable bridge between agent orchestration and the payment lifecycle APIs.

## Response Shape Recommendations

Every MCP tool response should prefer:

- `action_required`
- `safe_to_retry`
- `estimated_cost_atomic`
- `next_step`
- `human_approval_required`

These fields are better for orchestration than raw transport responses alone.

## Error Behavior

- Request-level MCP protocol failures use standard JSON-RPC style error responses.
- Tool-level failures return:
  - `result.isError = true`
  - `result.structuredContent.error.code`
  - `result.structuredContent.error.message`
  - `result.structuredContent.error.retryable`

---
name: aimipay-agent-plugin
description: Use the installed AimiPay plugin MCP tools when Codex needs to access paid merchant offers, payment lifecycle tools, or installation diagnostics through the local AimiPay plugin.
---

# AimiPay Agent Plugin

Use the `aimipay-agent` MCP server when it is available through the local plugin install.

## Primary Tooling

- `aimipay.get_protocol_manifest`
- `aimipay.get_agent_state`
- `aimipay.list_offers`
- `aimipay.quote_budget`
- `aimipay.plan_purchase`
- `aimipay.prepare_purchase`
- `aimipay.submit_purchase`
- `aimipay.finalize_payment`
- `aimipay.get_payment_status`
- `aimipay.list_pending_payments`
- `aimipay.recover_payment`
- `aimipay.check_wallet_funding`
- `aimipay.run_onboarding`

Compatibility tools may also be available for lower-level flows: `aimipay.estimate_budget`, `aimipay.open_channel`, `aimipay.create_payment`, `aimipay.execute_payment`, `aimipay.reconcile_payment`, `aimipay.create_wallet`, and `aimipay.set_merchant_url`.

## Installation

If the plugin is missing, run:

`powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target plugin --mode repo-local`

Start new host sessions with `aimipay.get_protocol_manifest`, then `aimipay.get_agent_state`. Preserve payment ids and use `aimipay.list_pending_payments` after a host restart before creating replacement payments.

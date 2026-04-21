---
name: aimipay-agent-plugin
description: Use the installed AimiPay plugin MCP tools when Codex needs to access paid merchant offers, payment lifecycle tools, or installation diagnostics through the local AimiPay plugin.
---

# AimiPay Agent Plugin

Use the `aimipay-agent` MCP server when it is available through the local plugin install.

## Tooling

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

## Installation

If the plugin is missing, run:

`powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target plugin --mode repo-local`

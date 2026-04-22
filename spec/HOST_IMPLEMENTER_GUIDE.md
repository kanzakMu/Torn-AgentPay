# Host Implementer Guide

This guide is for teams integrating Torn-AgentPay into an AI host, MCP runtime, or plugin-style agent shell.

## Goal

A host integration should be able to:

- launch the Torn-AgentPay MCP entrypoint
- surface startup onboarding metadata
- expose the high-level purchase tools
- let the agent bind a seller URL
- let the agent discover offers and continue through purchase flow

## Entry Point

The canonical MCP entrypoint is:

- module: `agent_entrypoints.aimipay_mcp_stdio`

Hosts should launch it with:

- command: a Python interpreter
- args: `["-m", "agent_entrypoints.aimipay_mcp_stdio"]`

## Required Environment

At minimum, host integrations should provide:

- `AIMIPAY_REPOSITORY_ROOT`
- `PYTHONPATH`

Optional but recommended:

- `AIMIPAY_MERCHANT_URLS`
- `AIMIPAY_BUYER_ADDRESS`
- `AIMIPAY_BUYER_PRIVATE_KEY`

## Startup UX Contract

On first connect, hosts should prefer these integration surfaces in order:

1. `initialize.result.meta["aimipay/startupCard"]`
2. `initialize.result.meta["aimipay/startupOnboarding"]`
3. `initialize.result.instructions`
4. explicit tool call: `aimipay.get_startup_onboarding`

This lets the host render a first-screen action instead of making the agent guess what to do next.

## Host-Native Tool Mapping

Hosts should expose these as first-class actions when possible:

- `aimipay.list_offers`
- `aimipay.estimate_budget`
- `aimipay.prepare_purchase`
- `aimipay.submit_purchase`
- `aimipay.confirm_purchase`
- `aimipay.get_payment_status`
- `aimipay.recover_payment`
- `aimipay.check_wallet_funding`
- `aimipay.create_wallet`
- `aimipay.run_onboarding`
- `aimipay.set_merchant_url`
- `aimipay.get_startup_onboarding`

## Recommended Host Workflow

1. Start MCP server
2. Read startup card
3. If no seller URL is configured, prompt for one
4. Run onboarding
5. Discover offers
6. Let the agent estimate cost
7. Let the agent prepare and submit purchase
8. Let the agent confirm or reconcile as needed

## Installer Integration

The repository already supports local install targets for:

- `codex`
- `mcp`
- `claude`
- `cua`
- `openclaw`
- `hermes`

Preferred installer entrypoint:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target codex --mode home-local --merchant-url https://seller.example
```

## Related References

- `agent-dist/README.md`
- `agent-dist/HOST_INSTALL_CHECKLIST.md`
- `spec/AGENT_INTEGRATION_GUIDE.md`
- `spec/BUYER_IMPLEMENTER_GUIDE.md`
- `spec/THIRD_PARTY_IMPLEMENTER_GUIDE.md`

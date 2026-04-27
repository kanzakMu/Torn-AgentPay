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

- `aimipay.get_protocol_manifest`
- `aimipay.get_agent_state`
- `aimipay.list_offers`
- `aimipay.quote_budget`
- `aimipay.plan_purchase`
- `aimipay.prepare_purchase`
- `aimipay.submit_purchase`
- `aimipay.get_payment_status`
- `aimipay.finalize_payment`
- `aimipay.list_pending_payments`
- `aimipay.recover_payment`
- `aimipay.check_wallet_funding`
- `aimipay.run_onboarding`
- `aimipay.set_merchant_url`
- `aimipay.get_startup_onboarding`

Low-level compatibility tools such as `aimipay.estimate_budget`, `aimipay.open_channel`, `aimipay.create_payment`, `aimipay.execute_payment`, and `aimipay.reconcile_payment` may still be exposed, but new host flows should prefer the protocol-first tools above because they return richer `kind`, `next_actions`, and recovery metadata.

## Recommended Host Workflow

1. Start MCP server
2. Read startup card
3. If no seller URL is configured, prompt for one
4. Run onboarding
5. Discover offers
6. Let the agent quote budget or build a purchase plan
7. Let the agent prepare and submit purchase
8. Let the agent finalize or recover as needed

## Installer Integration

The repository already supports local install targets for:

- `codex`
- `mcp`
- `claude`
- `cua`
- `openclaw`
- `hermes`

Preferred installer entrypoint:

```bash
cd python
PYTHONPATH=. python -m ops_tools.install_ai_host --host codex --mode home-local --merchant-url https://seller.example --json
```

Windows hosts may use the wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host codex --mode home-local --merchant-url https://seller.example
```

## Related References

- `agent-dist/README.md`
- `agent-dist/HOST_INSTALL_CHECKLIST.md`
- `spec/AGENT_INTEGRATION_GUIDE.md`
- `spec/BUYER_IMPLEMENTER_GUIDE.md`
- `spec/THIRD_PARTY_IMPLEMENTER_GUIDE.md`

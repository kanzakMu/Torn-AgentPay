# Torn-AgentPay

AI-facing payment infrastructure for agent applications on Tron.

Torn-AgentPay lets an AI host discover paid capabilities, quote budget, decide whether a purchase is allowed, create voucher-backed payments, settle them, and recover unfinished lifecycle state. The project is built for AI applications first: the important interface is structured protocol output that an agent can read and act on, not a human dashboard.

## What Is Implemented

- Tron-compatible micropayment channel contract with per-channel salt to prevent voucher replay across reopened buyer/seller/token pairs.
- Seller gateway for manifests, discovery, channel opening, payment intents, payment status, settlement, reconciliation, diagnostics, and agent-readable status.
- Buyer runtime for discovery, budget quotes, purchase planning, channel preparation, payment submission, finalization, and recovery.
- AI-facing protocol payloads for state, capabilities, budgets, payment lifecycle, recovery, and next-action hints.
- MCP server and tools for external AI hosts.
- Skill-only install path with a local runner, so hosts can use the functionality even when plugin/MCP loading is unavailable.
- One-command installers for Codex-style hosts, generic MCP hosts, Claude-style configs, CUA, OpenClaw, Hermes, and skill-only usage.
- Admin protection for seller ops/config routes, buyer onboarding origin hardening, and release safety tooling that blocks local secrets/state from artifacts.

Latest local validation in this workspace on 2026-04-27:

```text
npm test                                        -> 13 passing
PYTHONPATH=python python -m pytest python/tests -> 162 passed
python -m ops_tools.ai_host_smoke --json        -> ok: true
npm run validate:nile                           -> nile validation: ok
```

`npm run preflight:security` is a production readiness check. It is expected to fail on placeholder/local config until real chain IDs, contract/token addresses, admin token, storage, audit log, and secret management are configured.

## Architecture

```text
AI host / agent
  |
  | MCP tools or skill runner
  v
Buyer runtime
  |
  | discover, quote, plan, pay, recover
  v
Seller gateway
  |
  | channel + voucher settlement
  v
Tron payment-channel contract
```

Main directories:

- `contracts/`: Tron/EVM-compatible payment-channel contract.
- `scripts/`: deployment and contract execution scripts.
- `python/buyer/`: buyer SDK, MCP server, agent adapter, wallet/provisioner logic.
- `python/seller/`: seller gateway, settlement, worker, observability.
- `python/shared/`: shared models, protocol helpers, discovery, signatures, native digest logic.
- `skills/aimipay-agent/`: Codex-style skill and skill-only runner.
- `plugins/aimipay-agent/`: plugin package for hosts that support plugin loading.
- `agent-dist/`: connector manifests and host configuration templates.
- `spec/`: protocol, discovery, MCP, host, buyer, and third-party implementer guides.

## AI-Facing Protocol

All high-level agent payloads use:

```json
{
  "schema_version": "aimipay.agent-protocol.v1",
  "kind": "...",
  "next_actions": []
}
```

Implemented payload kinds:

- `agent_state`: readiness, merchant status, capabilities, pending payments, next actions.
- `capability_catalog`: available paid capabilities and auto-purchase summary.
- `budget_quote`: estimated cost, budget decision, and whether auto purchase is allowed.
- `purchase_plan`: selected offer and no-side-effect purchase plan.
- `payment_state`: lifecycle status, terminal flag, next step, and recovery hint.
- `payment_recovery`: unfinished or recoverable payments and suggested recovery actions.

Primary MCP tools:

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

Reference docs:

- [AI Host Playbook](spec/AI_HOST_PLAYBOOK.md)
- [MCP Integration Guide](spec/MCP_INTEGRATION_GUIDE.md)
- [Capability Manifest](agent-dist/aimipay.capabilities.json)

## External AI Host Install

Use this path when installing into another AI host. The installer writes host config files, skill/plugin artifacts when needed, an install report, next steps, and a post-install self-check report.

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host codex --mode home-local --merchant-url https://merchant.example
```

Python module form, useful for macOS/Linux/manual automation after cloning the repo:

```bash
cd python
PYTHONPATH=. python -m ops_tools.install_ai_host --host codex --mode home-local --merchant-url https://merchant.example --json
```

Supported `--host` values:

- `codex`
- `mcp`
- `claude`
- `cua`
- `openclaw`
- `hermes`
- `all`
- `skill`

Generated files include:

- `aimipay-install-report.json`
- `aimipay-post-install-check.json`
- `aimipay-install-next-steps.md`
- host-specific MCP/config files

Run a post-install self-check manually:

```bash
cd python
PYTHONPATH=. python -m ops_tools.host_post_install_check --repository-root .. --host codex --mode home-local --json
```

## Skill-Only Install

Use skill-only install when the host can load instructions but cannot load plugins or MCP config.

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_skill.ps1 --mode home-local --merchant-url https://merchant.example
```

Python module form:

```bash
cd python
PYTHONPATH=. python -m ops_tools.install_skill --mode home-local --merchant-url https://merchant.example --json
```

The installed skill includes:

- `SKILL.md`
- `skill-runtime.json`
- `aimipay_skill_runner.py`

Skill runner examples:

```bash
python <skill-path>/aimipay_skill_runner.py doctor
python <skill-path>/aimipay_skill_runner.py protocol-manifest
python <skill-path>/aimipay_skill_runner.py list-tools
python <skill-path>/aimipay_skill_runner.py get-agent-state
python <skill-path>/aimipay_skill_runner.py list-offers
python <skill-path>/aimipay_skill_runner.py quote-budget --capability-id research-web-search --expected-units 3
python <skill-path>/aimipay_skill_runner.py plan-purchase --capability-type web_search --budget-limit-atomic 1000000
python <skill-path>/aimipay_skill_runner.py get-payment-status --payment-id pay_123
python <skill-path>/aimipay_skill_runner.py recover-payment --payment-id pay_123
```

## Install Directly From GitHub

Clean-machine install on Windows:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_agent_from_github.ps1 -OutFile $env:TEMP\aimipay-agent-install.ps1; & $env:TEMP\aimipay-agent-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git -Host codex -MerchantUrl https://merchant.example"
```

For macOS/Linux today, clone the repository first and use the Python module installer shown above.

## Developer Setup

Requirements:

- Node.js 20+
- Python 3.11+
- PowerShell only when using the Windows helper scripts

Cross-platform Python setup:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r python/requirements.txt
PYTHONPATH=python python -m pytest python/tests
```

Windows Python setup:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r python\requirements.txt
$env:PYTHONPATH = "python"
.\.venv\Scripts\python.exe -m pytest python\tests
```

Contract and script tests:

```bash
npm install
npm test
```

AI-host protocol smoke:

```bash
cd python
PYTHONPATH=. python -m ops_tools.ai_host_smoke --json
```

Release artifact cleanup:

```bash
cd python
PYTHONPATH=. python -m ops_tools.clean_release --output-dir ../dist-clean --force
```

Nile dry-run validation:

```bash
npm run validate:nile
```

## Local Demo

These commands are for local development only. They are not the external host install path.

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_buyer.ps1
powershell -ExecutionPolicy Bypass -File python/run_buyer_onboarding.ps1
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1
```

Run both sides:

```powershell
powershell -ExecutionPolicy Bypass -File python/run_local_stack.ps1
```

Run a one-shot local purchase:

```powershell
powershell -ExecutionPolicy Bypass -File python/run_local_demo.ps1
```

## Seller Gateway

Core endpoints:

- `GET /.well-known/aimipay.json`
- `GET /_aimipay/discover`
- `POST /_aimipay/channels/open`
- `POST /_aimipay/payment-intents`
- `GET /_aimipay/payments/{payment_id}`
- `GET /_aimipay/payments/pending`
- `GET /_aimipay/payments/recover`
- `POST /_aimipay/settlements/execute`
- `POST /_aimipay/settlements/reconcile`
- `GET /_aimipay/ops/health`
- `GET /_aimipay/ops/diagnostics`
- `GET /_aimipay/ops/agent-status`

Admin/ops endpoints are protected by bearer token or hash token when configured, with localhost/testclient fallback for local development.

## Security And Release Boundary

Hardening already implemented:

- Channel IDs include a buyer-generated `channel_salt`.
- Voucher replay across reopened buyer/seller/token channels is covered by tests.
- Seller ops and install/config writes require admin access.
- Buyer onboarding rejects non-local origins and arbitrary cross-origin writes.
- Diagnostics redact private keys, admin tokens, and signatures.
- Release tooling blocks ignored local state such as `.env.local`, wallet files, SQLite databases, `.vendor`, `.venv`, and dry-run outputs.

Before production mainnet use:

- Configure real Tron network IDs and deployed contract/token addresses.
- Use durable storage and settlement workers under process supervision.
- Configure admin token or hash token, audit log path, and secret management.
- Run funded Nile/mainnet end-to-end validation.
- Run `npm run preflight:security` with production environment variables.

## Documentation

- [Agent Distribution Guide](agent-dist/README.md)
- [Host Install Checklist](agent-dist/HOST_INSTALL_CHECKLIST.md)
- [Protocol Reference](spec/PROTOCOL_REFERENCE.md)
- [Agent Integration Guide](spec/AGENT_INTEGRATION_GUIDE.md)
- [Buyer Implementer Guide](spec/BUYER_IMPLEMENTER_GUIDE.md)
- [Host Implementer Guide](spec/HOST_IMPLEMENTER_GUIDE.md)
- [Third-Party Implementer Guide](spec/THIRD_PARTY_IMPLEMENTER_GUIDE.md)
- [Release Publishing Guide](spec/RELEASE_PUBLISHING_GUIDE.md)
- [Tron-First Development Guide](spec/TRON_FIRST_DEVELOPMENT_GUIDE.md)

## GitHub Sync Note

This downloaded workspace is not currently a git working tree, so local `git status`, commits, and pushes cannot work from this folder. To publish changes, apply these files in a real clone of `kanzakMu/Torn-AgentPay`, then commit and push there, or reconnect this directory to its `.git` metadata first.

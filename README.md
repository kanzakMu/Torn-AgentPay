# Torn-AgentPay

AI-facing payment infrastructure for agent applications on Tron.

Torn-AgentPay lets an AI agent discover paid capabilities, estimate budget, decide whether a purchase is allowed, create a payment, drive settlement, and recover unfinished payments through structured protocol payloads. The project includes a Tron payment-channel contract, Python buyer and seller runtimes, MCP tools, a Codex-style skill, and host installers for external AI apps.

The current direction is not a human dashboard first. It is an agent-facing payment protocol: AI hosts should be able to ask what is available, what it costs, what payment state is in progress, and what action is safe to take next.

## Current Status

Implemented and tested:

- Tron micropayment channel contract with per-channel salt to prevent voucher replay across reopened channels.
- Seller gateway for manifest, discovery, channel opening, payment intents, payment status, settlement execution, reconciliation, diagnostics, and agent status.
- Buyer runtime for offer discovery, budget quotes, purchase planning, channel preparation, payment submission, finalization, and recovery.
- AI-facing protocol payloads for status, capabilities, budgets, payment lifecycle, recovery, and next action hints.
- MCP server and tools for agent hosts.
- Skill-only install path with a local command runner, so the skill can still call functionality without plugin/MCP host loading.
- External AI host one-command installers for Codex-style hosts, generic MCP hosts, Claude-style configs, CUA, OpenClaw, and Hermes.
- Admin protection for seller ops/config routes, localhost fallback, bearer/hash token support, and audit events.
- Buyer onboarding origin protection and local-write hardening.
- Release safety tooling that blocks local env, wallet, database, vendor, and dry-run state from artifacts.

Validation at the time this README was rewritten:

```bash
pytest python/tests
# 158 passed

npm test
# 13 passing
```

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

Main components:

- `contracts/`: Tron/EVM-compatible payment-channel contract.
- `scripts/`: deployment and contract execution scripts.
- `python/buyer/`: buyer SDK, MCP server, agent adapter, wallet/provisioner logic.
- `python/seller/`: seller gateway, settlement, worker, observability.
- `python/shared/`: shared models, protocol helpers, discovery, signatures, native digest logic.
- `skills/aimipay-agent/`: Codex-style skill and skill-only runner.
- `plugins/aimipay-agent/`: plugin package for hosts that support plugin loading.
- `agent-dist/`: connector manifests and generated host configuration templates.
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

Implemented `kind` values:

- `agent_state`: readiness, merchant status, capabilities, pending payments, next actions.
- `capability_catalog`: available paid capabilities and auto-purchase summary.
- `budget_quote`: estimated cost, budget decision, and whether auto purchase is allowed.
- `purchase_plan`: selected offer and no-side-effect purchase plan.
- `payment_state`: lifecycle status, terminal flag, next step, and recovery hint.
- `payment_recovery`: unfinished/recoverable payments and suggested recovery actions.

Useful MCP tools:

- `aimipay.get_protocol_manifest`
- `aimipay.get_agent_state`
- `aimipay.list_offers`
- `aimipay.quote_budget`
- `aimipay.plan_purchase`
- `aimipay.prepare_purchase`
- `aimipay.submit_purchase`
- `aimipay.get_payment_status`
- `aimipay.finalize_payment`
- `aimipay.recover_payment`
- `aimipay.check_wallet_funding`
- `aimipay.run_onboarding`

Protocol reference endpoint:

```text
GET /_aimipay/protocol/reference
```

Agent-readable seller status endpoint:

```text
GET /_aimipay/ops/agent-status
```

AI host playbook and static capability manifest:

- [AI Host Playbook](spec/AI_HOST_PLAYBOOK.md)
- [Capability Manifest](agent-dist/aimipay.capabilities.json)

## Quick Start

Requirements:

- Node.js 20+
- Python 3.11+
- PowerShell on Windows for the helper scripts

Install dependencies and run tests:

```bash
npm install
npm test
```

Python tests:

```powershell
py -3 -m venv .pytest-tmp/review-venv
.\.pytest-tmp\review-venv\Scripts\python.exe -m pip install -r python\requirements.txt
.\.pytest-tmp\review-venv\Scripts\python.exe -m pytest python\tests
```

## Install Into an AI Host

Use this path when the goal is external AI host integration.

Codex-style install:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host codex --merchant-url https://merchant.example
```

Generic MCP host:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host mcp --merchant-url https://merchant.example
```

Claude-style config:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host claude --merchant-url https://merchant.example
```

Supported host targets:

- `codex`
- `mcp`
- `claude`
- `cua`
- `openclaw`
- `hermes`
- `all`
- `skill`

The installer generates:

- `aimipay-install-report.json`
- `aimipay-post-install-check.json`
- `aimipay-install-next-steps.md`
- host-specific MCP/config files
- installed skill/plugin/connector artifacts as needed

By default the installer also runs a post-install self-check: installed artifact verification, skill-only doctor, capability manifest validation, and AI-facing protocol smoke. Use `--skip-post-install-check` only when packaging offline artifacts and running checks later.

## Skill-Only Install

Use skill-only install when the host can load instructions but not plugins/MCP config.

```powershell
powershell -ExecutionPolicy Bypass -File python/install_skill.ps1 --mode home-local
```

or:

```bash
python -m ops_tools.install_skill --mode home-local
```

The installed skill includes:

- `SKILL.md`
- `skill-runtime.json`
- `aimipay_skill_runner.py`

The runner lets the skill call real functionality without MCP host loading:

```powershell
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

Run the AI host protocol smoke test:

```powershell
cd python
python -m ops_tools.ai_host_smoke --json
```

## Install Directly From GitHub

For a clean machine, download the installer and let it fetch the repository:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_agent_from_github.ps1 -OutFile $env:TEMP\aimipay-agent-install.ps1; & $env:TEMP\aimipay-agent-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git -Host codex -MerchantUrl https://merchant.example"
```

Replace:

- `-Host codex` with `mcp`, `claude`, `cua`, `openclaw`, `hermes`, `all`, or `skill`.
- `https://merchant.example` with the seller service URL.

## Local Demo

Bootstrap buyer:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_buyer.ps1
powershell -ExecutionPolicy Bypass -File python/run_buyer_onboarding.ps1
```

Bootstrap seller:

```powershell
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

Optional setup hub:

```powershell
powershell -ExecutionPolicy Bypass -File python/start_easy_setup.ps1
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

## Security Notes

Important hardening already implemented:

- Channel IDs include a buyer-generated `channel_salt`.
- Voucher replay across reopened buyer/seller/token channels is covered by tests.
- Seller ops and install/config writes require admin access.
- Buyer onboarding rejects non-local origins and no longer allows arbitrary cross-origin writes.
- Diagnostics redact private keys, admin tokens, and signatures.
- Release tooling blocks ignored local state such as `.env.local`, wallet files, SQLite databases, `.vendor`, `.venv`, and dry-run outputs.

Before publishing release artifacts:

```bash
npm run preflight:security
npm run release:clean
```

For Nile validation:

```bash
npm run validate:nile
```

## Test Commands

Contract and script tests:

```bash
npm test
```

Python test suite:

```powershell
$env:PYTHONPATH = "python"
python -m pytest python\tests
```

Security preflight:

```bash
npm run preflight:security
```

Release artifact cleanup:

```bash
npm run release:clean
```

## Documentation

- [Agent Distribution Guide](agent-dist/README.md)
- [Host Install Checklist](agent-dist/HOST_INSTALL_CHECKLIST.md)
- [Protocol Reference](spec/PROTOCOL_REFERENCE.md)
- [MCP Integration Guide](spec/MCP_INTEGRATION_GUIDE.md)
- [Agent Integration Guide](spec/AGENT_INTEGRATION_GUIDE.md)
- [Buyer Implementer Guide](spec/BUYER_IMPLEMENTER_GUIDE.md)
- [Host Implementer Guide](spec/HOST_IMPLEMENTER_GUIDE.md)
- [Third-Party Implementer Guide](spec/THIRD_PARTY_IMPLEMENTER_GUIDE.md)
- [Release Publishing Guide](spec/RELEASE_PUBLISHING_GUIDE.md)
- [Tron-First Development Guide](spec/TRON_FIRST_DEVELOPMENT_GUIDE.md)

## Production Readiness Boundary

This repository has the protocol, SDK, MCP tools, skill install, host install, security hardening, and test coverage needed for a serious integration prototype. Before production mainnet use, run funded Nile/mainnet end-to-end validation, deploy with real secret management, configure admin tokens, enable durable storage, and operate settlement workers under process supervision.

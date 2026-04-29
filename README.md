# AimiPay

Turn any API into an agent-paid API.

AimiPay lets AI hosts discover paid capabilities, enforce buyer budgets, complete HTTP 402 payments, and return receipts that merchants can reconcile. It is built for AI applications first: the important interface is structured protocol output that an agent can read and act on, not a human dashboard.

## Start Here

For merchants:

```bash
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant init --service-name "Research Copilot"
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant verify --config aimipay.merchant.json
PYTHONPATH=python python python/examples/coding_agent_paid_flow_demo.py
```

Read the [Merchant Quickstart](spec/MERCHANT_QUICKSTART.md) to wrap a FastAPI route with HTTP 402 payments.

For external AI hosts, start with the [AI Host Playbook](spec/AI_HOST_PLAYBOOK.md) and [MCP Integration Guide](spec/MCP_INTEGRATION_GUIDE.md).

## What Is Implemented

- Tron-compatible micropayment channel contract with per-channel salt to prevent voucher replay across reopened buyer/seller/token pairs.
- Seller gateway for manifests, discovery, channel opening, payment intents, payment status, settlement, reconciliation, diagnostics, and agent-readable status.
- Buyer runtime for discovery, budget quotes, purchase planning, channel preparation, payment submission, finalization, and recovery.
- AI-facing protocol payloads for state, capabilities, budgets, payment lifecycle, recovery, and next-action hints.
- MCP server and tools for external AI hosts.
- Skill-only install path with a local runner, so hosts can use the functionality even when plugin/MCP loading is unavailable.
- x402-style HTTP 402 adapter for merchant APIs: paid routes return machine-readable payment requirements and unlock only after a settled payment.
- Agent-readable capability registry, HTTP 402 conformance endpoint, billing summary, receipt list, and webhook outbox for commercial merchant integrations.
- Hosted multi-tenant gateway MVP, marketplace capability index, buyer budget policy engine, signed webhook events, billing statements, payout reports, and a coding-agent vertical demo.
- One-command installers for Codex-style hosts, generic MCP hosts, Claude-style configs, CUA, OpenClaw, Hermes, and skill-only usage.
- Admin protection for seller ops/config routes, buyer onboarding origin hardening, and release safety tooling that blocks local secrets/state from artifacts.

Release validation commands:

```text
npm test
PYTHONPATH=python python -m pytest python/tests
cd python && PYTHONPATH=. python -m ops_tools.ai_host_smoke --json
npm run validate:nile
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
- [Merchant Quickstart](spec/MERCHANT_QUICKSTART.md)
- [Hosted Gateway Deployment](spec/HOSTED_GATEWAY_DEPLOYMENT.md)
- [HTTP 402 Adapter](spec/HTTP402_ADAPTER.md)
- [Facilitator And Mandates](spec/FACILITATOR_AND_MANDATES.md)
- [Commercialization MVP](spec/COMMERCIALIZATION_MVP.md)
- [Capability Manifest](agent-dist/aimipay.capabilities.json)

## Merchant SDK Surface

Merchant APIs can expose paid resources with an x402-style 402 handshake:

```python
from fastapi import FastAPI
from seller import install_sellable_capability

app = FastAPI()
merchant = install_sellable_capability(
    app,
    service_name="Research Copilot",
    service_description="Pay-per-use research and market data",
    seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    contract_address="0x1000000000000000000000000000000000000001",
    token_address="0x2000000000000000000000000000000000000002",
)


@merchant.paid_api(
    path="/tools/research",
    price_atomic=250_000,
    capability_type="web_search",
    capability_id="research-web-search",
)
def research_tool(body: dict) -> dict:
    return {"result": run_research(body["query"])}
```

Without payment the route returns `402 Payment Required` with `schema_version = aimipay.http402.v1`, `accepts`, and `next_actions`. After payment settlement, the host retries with `X-PAYMENT` or `X-AIMIPAY-PAYMENT-ID` and receives the protected resource plus `X-PAYMENT-RESPONSE`.

Buyer clients can run the full 402 flow automatically:

```python
result = client.request_paid_resource(
    "/tools/research",
    json_body={"query": "agent payments"},
    budget_limit_atomic=300_000,
)

resource_payload = result["response"].json()
receipt = result["payment_response"]
```

The seller adapter binds the payment to the route and amount before releasing the resource. A payment for another path or a lower-priced route returns another 402 instead of unlocking the API.

Commercial merchant integrations can also read:

- `GET /_aimipay/registry/capabilities`: enabled auto-purchasable capabilities, pricing, and risk hints.
- `GET /_aimipay/protocol/http402-conformance`: implemented HTTP 402 profile and compatibility boundaries.
- `GET /_aimipay/ops/billing/summary`: protected billing totals by status and route.
- `GET /_aimipay/ops/billing/statement`: protected statement with deterministic hash.
- `GET /_aimipay/ops/payouts/report`: protected payout report with net payout amount.
- `GET /_aimipay/ops/receipts`: protected payment-level receipts for reconciliation.
- `GET /_aimipay/ops/webhooks/outbox`: protected lifecycle event outbox for merchant backend sync.

Hosted gateway MVP:

- `seller.install_hosted_gateway(...)` mounts isolated merchants under `/merchants/{merchant_id}`.
- `GET /_aimipay/hosted/merchants` lists hosted merchants.
- `GET /_aimipay/marketplace/capabilities` aggregates all hosted merchant capabilities.
- `GET /_aimipay/hosted/merchants/{merchant_id}/admin-summary` returns a protected merchant summary.

Buyer-side budget policies:

```python
from buyer import BuyerBudgetPolicy, BuyerClient

client = BuyerClient(
    merchant_base_url="https://merchant.example",
    full_host="https://tron.example",
    wallet=wallet,
    provisioner=provisioner,
    budget_policy=BuyerBudgetPolicy(
        per_purchase_limit_atomic=500_000,
        daily_limit_atomic=2_000_000,
        require_approval_for_untrusted=True,
    ),
)
```

Developer CLI:

```bash
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant init --service-name "Research Copilot"
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant verify --config aimipay.merchant.json
PYTHONPATH=python python -m ops_tools.aimipay_cli merchant dev
PYTHONPATH=python python -m ops_tools.aimipay_cli demo --json
```

Product headline for external positioning:

> Turn any API into an agent-paid API. AimiPay lets AI hosts discover paid capabilities, enforce buyer budgets, complete HTTP 402 payments, and return signed receipts that merchants can reconcile.

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
- [Merchant Quickstart](spec/MERCHANT_QUICKSTART.md)
- [Hosted Gateway Deployment](spec/HOSTED_GATEWAY_DEPLOYMENT.md)
- [Facilitator And Mandates](spec/FACILITATOR_AND_MANDATES.md)
- [HTTP 402 Adapter](spec/HTTP402_ADAPTER.md)
- [Commercialization MVP](spec/COMMERCIALIZATION_MVP.md)
- [Agent Integration Guide](spec/AGENT_INTEGRATION_GUIDE.md)
- [Buyer Implementer Guide](spec/BUYER_IMPLEMENTER_GUIDE.md)
- [Host Implementer Guide](spec/HOST_IMPLEMENTER_GUIDE.md)
- [Third-Party Implementer Guide](spec/THIRD_PARTY_IMPLEMENTER_GUIDE.md)
- [Release Publishing Guide](spec/RELEASE_PUBLISHING_GUIDE.md)
- [Tron-First Development Guide](spec/TRON_FIRST_DEVELOPMENT_GUIDE.md)

# AimiPay Tron

Tron-first programmable payment infrastructure for AI agents, APIs, and SaaS.

This repository is the new mainline codebase. It is intentionally focused on:

- Tron
- USDT-TRC20
- agent-native service discovery
- programmable payment channels
- buyer/seller integration paths

This repository does not carry Solana as a product mainline. Solana is planned to move into a separate legacy/reference repository.

## Current Scope

- Solidity payment-channel contracts
- TronWeb deployment and execution scripts
- Hardhat tests for protocol behavior
- Python buyer/seller/shared directories for the new Tron-first application layer
- Discovery and integration specs for agent-native commerce

## Directory Layout

```text
contracts/   Tron-first Solidity contracts
scripts/     deploy/open/claim/close/cancel execution scripts
test/        Hardhat protocol tests
python/      buyer/seller/shared application layer
examples/    minimal plan files and integration examples
spec/        discovery and protocol documentation
```

## Product Direction

- Default chain: Tron
- Default asset: USDT-TRC20
- Default narrative: agent-to-service programmable payments

## Near-Term Milestones

1. Harden payment lifecycle with confirmation, reconciliation, and stable error contracts
2. Eliminate protocol-critical JS subprocess dependencies with embeddable shared implementations
3. Expand MCP compatibility beyond minimal tools/list and tools/call skeleton support
4. Validate production-style recovery and reconciliation against Nile

## Quick Start

```bash
npm install
npm run build
npm test
npm run smoke:local
```

## Ordinary User Install

For a Windows user who just wants a local demo without stitching the stack together manually:

1. Install the official Python 3.11+ distribution and Node.js 20+
2. Run:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1
```

3. Start the local end-to-end demo:

```powershell
powershell -ExecutionPolicy Bypass -File python/run_local_stack.ps1
```

One-command path:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_and_run.ps1
```

Foolproof local setup hub:

```powershell
powershell -ExecutionPolicy Bypass -File python/start_easy_setup.ps1
```

Then open:

- `http://127.0.0.1:8010/aimipay/easy-setup`

GitHub direct install:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_from_github.ps1 -OutFile $env:TEMP\\aimipay-install.ps1; & $env:TEMP\\aimipay-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git"
```

GitHub direct install for AI agent hosts:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_agent_from_github.ps1 -OutFile $env:TEMP\\aimipay-agent-install.ps1; & $env:TEMP\\aimipay-agent-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git -Target codex -MerchantUrl https://merchant.example"
```

Batch wrapper:

```bat
python\install_and_run.bat
```

Merchant install path:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1
```

Docker local stack:

```bash
docker compose -f docker-compose.local.yml up --build
```

Install doctor report output:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_doctor --format markdown --output python/.docker-local/install-doctor.md
.venv\Scripts\python.exe -m ops_tools.install_doctor --format html --output python/.docker-local/install-doctor.html
```

Agent package install:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_agent_package --target all --mode repo-local
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target all --mode home-local
powershell -ExecutionPolicy Bypass -File python/register_codex_home_local.ps1 -RunDoctor
```

Batch wrapper:

```bat
python\install_agent_package.bat --target all --mode repo-local
```

Distribution docs:

- [agent-dist/README.md](/E:/trade/aimicropay-tron/agent-dist/README.md)
- [agent-dist/HOST_INSTALL_CHECKLIST.md](/E:/trade/aimicropay-tron/agent-dist/HOST_INSTALL_CHECKLIST.md)
- [merchant-dist/README.md](/E:/trade/aimicropay-tron/merchant-dist/README.md)

4. If you want an install-only health check first:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_doctor
```

The buyer bootstrap now also renders a first-start onboarding page at [buyer-onboarding.html](/E:/trade/aimicropay-tron/python/.agent/buyer-onboarding.html) so users can see the merchant URL, wallet status, next step, and discovered offers in one place.
It also starts a local onboarding UI service at `http://127.0.0.1:8011/aimipay/buyer/onboarding` so that page can submit a merchant URL and refresh offer discovery directly.

Wallet setup for AI buyers:

```powershell
.venv\Scripts\python.exe -m ops_tools.wallet_setup --force-create
.venv\Scripts\python.exe -m ops_tools.wallet_funding
```

Funding checklist:

- [python/BUYER_FUNDING_CHECKLIST.md](/E:/trade/aimicropay-tron/python/BUYER_FUNDING_CHECKLIST.md)

`npm run smoke:local` performs a local deploy -> approve -> open -> claim pipeline on Hardhat and prints a JSON summary.

## Notes

- The files under `contracts/`, `scripts/`, and `test/` are the verified starting assets from the previous prototype and now serve as the seed of this clean Tron-first repository.
- The Python layer is intentionally reset to a clean structure and should be rebuilt around Tron-first defaults rather than old multi-chain compatibility baggage.
- Minimal app/runtime examples now live under `python/examples/`.
- A minimal project-shaped integration template now lives under `python/sample_project/`.

## Integration Docs

- `spec/AGENT_INTEGRATION_GUIDE.md`
- `spec/PROTOCOL_REFERENCE.md`
- `spec/MCP_INTEGRATION_GUIDE.md`
- `SHOWCASE.md`

## Lifecycle API

Current management endpoints are designed around a stable payment lifecycle:

- `GET /.well-known/aimipay.json`
- `GET /_aimipay/discover`
- `GET /_aimipay/protocol/reference`
- `POST /_aimipay/channels/open`
- `POST /_aimipay/payment-intents`
- `POST /_aimipay/settlements/execute`
- `POST /_aimipay/settlements/reconcile`
- `GET /_aimipay/payments/{payment_id}`
- `GET /_aimipay/payments/recover`
- `GET /_aimipay/payments/pending`

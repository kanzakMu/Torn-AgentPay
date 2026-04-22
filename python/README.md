# Python Runtime Guide

This directory contains the Python application layer for Torn-AgentPay.

It includes:

- buyer runtime and wallet tooling
- seller runtime, settlement, and worker logic
- onboarding and install utilities
- local examples and integration tests

## What Most Users Should Do

### Start as a buyer

Use this if you only want the buyer or agent side.

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_buyer.ps1
powershell -ExecutionPolicy Bypass -File python/run_buyer_onboarding.ps1
```

That brings up:

- buyer onboarding: `http://127.0.0.1:8011/aimipay/buyer/onboarding`

### Start as a seller

Use this if you only want the seller side.

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1
```

That brings up:

- seller console: `http://127.0.0.1:8000/aimipay/install`

### Run the full local demo

Use this if you want both sides locally and then want to submit a one-shot demo payment.

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_buyer.ps1
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
powershell -ExecutionPolicy Bypass -File python/run_local_stack.ps1
```

Then run a one-shot demo payment:

```powershell
powershell -ExecutionPolicy Bypass -File python/run_local_demo.ps1
```

### Use the role-based install hub

```powershell
powershell -ExecutionPolicy Bypass -File python/start_easy_setup.ps1
```

Then open:

- `http://127.0.0.1:8010/aimipay/easy-setup`

## Buyer Install

Default local install:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_buyer.ps1
```

Seller-driven install:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_buyer.ps1 -MerchantUrl https://seller.example
```

In seller-driven mode, the buyer runtime prefers the seller's manifest and discovery data for:

- contract address
- token address
- chain id
- settlement backend
- chain RPC resolution

Bundled network profiles are also supported:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_buyer.ps1 -NetworkProfile local
powershell -ExecutionPolicy Bypass -File python/bootstrap_buyer.ps1 -NetworkProfile nile
```

## Seller Install

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1
```

Seller bootstrap also supports network profiles:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1 -NetworkProfile local
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1 -NetworkProfile nile
```

## GitHub Direct Install

Human-friendly local installer:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_from_github.ps1 -OutFile $env:TEMP\\torn-agentpay-install.ps1; & $env:TEMP\\torn-agentpay-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git"
```

AI host installer:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_agent_from_github.ps1 -OutFile $env:TEMP\\torn-agentpay-agent-install.ps1; & $env:TEMP\\torn-agentpay-agent-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git -Target codex -MerchantUrl https://seller.example"
```

## Install and Health Tools

Install doctor:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_doctor
```

Seller doctor:

```powershell
.venv\Scripts\python.exe -m ops_tools.merchant_doctor
```

Create or refresh a buyer wallet:

```powershell
.venv\Scripts\python.exe -m ops_tools.wallet_setup --force-create
```

Check buyer funding guidance:

```powershell
.venv\Scripts\python.exe -m ops_tools.wallet_funding
```

Run onboarding manually:

```powershell
.venv\Scripts\python.exe -m ops_tools.agent_onboarding
```

## Agent Package Install

Repo-local:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_agent_package --target all --mode repo-local
```

Home-local:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target all --mode home-local
```

Codex helper:

```powershell
powershell -ExecutionPolicy Bypass -File python/register_codex_home_local.ps1 -RunDoctor
```

See also:

- [Agent Distribution Guide](../agent-dist/README.md)
- [Host Install Checklist](../agent-dist/HOST_INSTALL_CHECKLIST.md)

## Operations

Preflight:

```powershell
python -m ops_tools.preflight_check --strict
```

Target dry run:

```powershell
python -m ops_tools.target_dry_run --env-file ./python/.env.target.example --output-dir ./python/.dry-run/target
```

Run the offchain stress drill:

```powershell
python python/examples/offchain_stress_drill.py
```

## Environment Templates

Use these templates rather than committing live files:

- local buyer template: [`python/.env.local.example`](./.env.local.example)
- local seller template: [`python/.env.merchant.example`](./.env.merchant.example)
- generic target template: [`python/.env.target.example`](./.env.target.example)
- Nile testnet template: [`python/target.nile.env.example`](./target.nile.env.example)

## Further Reading

- [Deployment Runbook](./DEPLOYMENT_RUNBOOK.md)
- [Nile Launch Checklist](./NILE_LAUNCH_CHECKLIST.md)
- [Mainnet Cutover Checklist](./MAINNET_CUTOVER_CHECKLIST.md)
- [Buyer Funding Checklist](./BUYER_FUNDING_CHECKLIST.md)

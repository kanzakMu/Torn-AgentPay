# Torn-AgentPay

Agent-native payment infrastructure for AI agents and merchants on Tron.

Torn-AgentPay lets an AI agent discover paid capabilities, open payment channels, submit payments, and drive settlement across onchain and offchain flows. It also gives merchants a local runtime, install flow, and lightweight control plane for publishing services to agents.

## What This Project Is

This repository combines four pieces that usually live separately:

- a Tron payment-channel contract
- a Python buyer runtime for AI agents
- a Python merchant runtime for sellers
- install and distribution tooling for MCP, Codex-style hosts, and other agent runtimes

The goal is simple:

**Give an AI agent a package or command, and let it install, discover offers, and pay for capabilities with minimal manual setup.**

## What Works Today

The current repository is already past the prototype stage. Today it includes:

- Tron payment-channel contracts and execution scripts
- local Hardhat tests and smoke flows
- buyer lifecycle: discover, estimate, create payment, execute, reconcile, finalize
- merchant lifecycle: publish routes, expose manifest/discovery, execute settlement, reconcile status
- agent installation paths for MCP, Codex-style hosts, OpenClaw, and Hermes-style connectors
- buyer onboarding with wallet setup, funding guidance, merchant URL binding, and offer discovery
- merchant install dashboard with route/plan editing, pause/resume, history, diff, and rollback
- Nile testnet deployment and end-to-end validation

## Who This Is For

This repository is most useful if you are:

- building an AI agent that needs to buy external services
- building a merchant runtime that wants to sell agent-callable capabilities
- experimenting with agent commerce, micropayments, or capability marketplaces
- integrating MCP or similar host environments with payment-aware tools

## Quick Start

Before you start:

- Node.js 20+
- Python 3.11+
- Windows PowerShell for the install scripts below

Choose the path that matches what you want to do.

### Option A: Validate the protocol locally

Use this if you want to verify the contract and local payment flow first.

```bash
npm install
npm test
npm run smoke:local
```

### Option B: Run the local buyer + merchant demo

Use this if you want to see the full local flow with a buyer, merchant, and payment lifecycle.

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
powershell -ExecutionPolicy Bypass -File python/examples/run_local_demo.ps1
```

If you prefer a single local install surface instead of separate scripts:

```powershell
powershell -ExecutionPolicy Bypass -File python/start_easy_setup.ps1
```

Then open:

- `http://127.0.0.1:8010/aimipay/easy-setup`

### Option C: Install into an AI host

Use this if you want an AI agent host to install Torn-AgentPay as a local package.

Codex-style home-local install:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target codex --mode home-local --merchant-url https://merchant.example
```

Install all supported local agent artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target all --mode home-local --merchant-url https://merchant.example
```

Supported host targets include:

- `codex`
- `mcp`
- `claude`
- `cua`
- `openclaw`
- `hermes`
- `all`

### Option D: Install directly from GitHub

Use this if you want the installer to fetch the repository from GitHub and install the agent package in one step.

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_agent_from_github.ps1 -OutFile $env:TEMP\\aimipay-agent-install.ps1; & $env:TEMP\\aimipay-agent-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git -Target codex -MerchantUrl https://merchant.example"
```

Notes:

- the `raw.githubusercontent.com` bootstrap path works only when the repository is public
- the installer itself clones from the `RepoUrl` you pass in
- replace `https://merchant.example` with a real merchant URL if you want onboarding to bind a merchant immediately

## Main Flows

### Buyer / Agent

- install agent package
- create or load buyer wallet
- connect a merchant URL
- discover offers
- open a payment channel
- create and execute a payment
- reconcile until terminal status

### Merchant / Seller

- install merchant runtime
- configure service metadata, routes, and plans
- expose manifest and discovery endpoints
- accept payment intents
- execute settlement and reconcile confirmations
- manage configuration through the merchant dashboard

## Merchant Runtime

The merchant side includes:

- local bootstrap and doctor scripts
- website/SaaS embed starter assets
- a lightweight install dashboard at `/aimipay/install`
- route, plan, and branding persistence
- config history, diff preview, rollback, and pause/resume controls

Start it locally with:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1
```

Then open:

- `http://127.0.0.1:8000/aimipay/install`

## AI Host Distribution

This repository already includes agent-facing packaging and onboarding for:

- Codex-style hosts
- MCP hosts
- Claude Desktop-style configs
- CUA-style configs
- OpenClaw-style configs
- Hermes-style configs

See:

- [Agent Distribution Guide](agent-dist/README.md)
- [Host Install Checklist](agent-dist/HOST_INSTALL_CHECKLIST.md)
- [MCP Integration Guide](spec/MCP_INTEGRATION_GUIDE.md)
- [Agent Integration Guide](spec/AGENT_INTEGRATION_GUIDE.md)

## Testnet Status

The Nile testnet path has already been exercised end-to-end:

- mock token deployed
- payment-channel contract deployed
- buyer and seller wallets prepared
- onchain open + claim validated
- Python merchant runtime lifecycle validated against Nile

Operational references:

- [Nile Launch Checklist](python/NILE_LAUNCH_CHECKLIST.md)
- [Deployment Runbook](python/DEPLOYMENT_RUNBOOK.md)
- [Mainnet Cutover Checklist](python/MAINNET_CUTOVER_CHECKLIST.md)

## Repository Layout

```text
contracts/      Payment-channel contracts
scripts/        Deploy/open/claim/close/cancel helpers
test/           Hardhat tests and smoke coverage
python/         Buyer, seller, shared runtime, install tooling, tests
merchant-dist/  Merchant install/dashboard/embed assets
agent-dist/     Agent package manifests, host templates, onboarding assets
spec/           Protocol and integration documentation
```

## Recommended Reading Order

If you're new to the project, this is the fastest way in:

1. Read this README
2. Read the [Protocol Reference](spec/PROTOCOL_REFERENCE.md)
3. Read the [Agent Integration Guide](spec/AGENT_INTEGRATION_GUIDE.md)
4. Read the [Python Runtime Guide](python/README.md)
5. Read the [Agent Distribution Guide](agent-dist/README.md)
6. Read the [Merchant Install Guide](merchant-dist/README.md)

## Security Notes

- Never commit real wallet files, private keys, or live env files
- Use the provided `*.example` files as templates
- Treat testnet and mainnet keys as secrets, even in demos

## Project Positioning

Torn-AgentPay is not just a contract repository and not just an MCP wrapper. It is a full-stack attempt at agent commerce infrastructure:

- programmable payments on Tron
- offchain lifecycle management
- merchant tooling
- AI host installation and onboarding

If your goal is to let AI agents install a package and immediately start paying for capabilities, this repository is the core of that workflow.

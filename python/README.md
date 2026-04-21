# Python Application Layer

This directory is the new Tron-first application layer.

Current scope:

- `shared/`: chain-agnostic models, discovery builders, payment record helpers
- `seller/`: minimal gateway and future settlement/worker modules
- `buyer/`: wallet, provisioner, and client placeholders for the upcoming buyer path
- `tests/`: Python integration tests

Install dependencies:

```bash
pip install -r python/requirements.txt
```

Ordinary user local install on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1
powershell -ExecutionPolicy Bypass -File python/run_local_stack.ps1
```

Buyer-side install is now merchant-first:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1 -MerchantUrl https://merchant.example
```

In that mode, the buyer only needs the merchant URL and wallet onboarding. Chain RPC, contract, and token settings are resolved from the merchant manifest/discover data at runtime.

Switch the buyer install to a bundled network profile instead of hand-editing chain addresses:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1 -NetworkProfile local
powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1 -NetworkProfile nile
```

Merchant-side install on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1
powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1
```

Merchant bootstrap also supports the same network profiles:

```powershell
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1 -NetworkProfile local
powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1 -NetworkProfile nile
```

Built-in profiles currently include `local`, `nile`, `mainnet`, and `custom`. Only `custom` expects manual chain values.

Buyer-side note:

- `AIMIPAY_FULL_HOST` is now optional for most buyer installs.
- When it is omitted, buyer runtime prefers the merchant's manifest/discover network metadata and resolves the chain RPC automatically from the bundled network profiles.
- Keep `AIMIPAY_FULL_HOST` only as an advanced override when you need to force a custom RPC.

Merchant install dashboard:

- open `http://127.0.0.1:8000/aimipay/install` after starting the merchant runtime
- use the "Resolved network profile" section to confirm the active network profile, chain RPC, contract, token, and settlement backend

Use the official Python 3.11+ installer on Windows so `venv` and `ensurepip` are available.

One-command local path:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_and_run.ps1
```

Easy setup hub:

```powershell
powershell -ExecutionPolicy Bypass -File python/start_easy_setup.ps1
```

Then open:

- `http://127.0.0.1:8010/aimipay/easy-setup`

This page is the new foolproof install surface. It keeps buyer install, merchant install, buyer onboarding, merchant dashboard, and local links in one place so users do not need to bounce across multiple scripts manually.

GitHub direct install:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_from_github.ps1 -OutFile $env:TEMP\\aimipay-install.ps1; & $env:TEMP\\aimipay-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git"
```

This command downloads the repository and boots directly into Easy Setup.

GitHub direct install for AI agent hosts:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_agent_from_github.ps1 -OutFile $env:TEMP\\aimipay-agent-install.ps1; & $env:TEMP\\aimipay-agent-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git -Target codex -MerchantUrl https://merchant.example"
```

Use `-Target codex`, `-Target mcp`, `-Target openclaw`, or `-Target hermes` depending on the host you want the AI to install into.

Batch wrapper:

```bat
python\install_and_run.bat
```

Install doctor:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_doctor
```

Buyer onboarding page:

- `python/bootstrap_local.ps1` now also runs first-start onboarding and renders [buyer-onboarding.html](/E:/trade/aimicropay-tron/python/.agent/buyer-onboarding.html)
- the page puts the merchant URL, next step, wallet state, and any discovered offers into one install-first screen
- bootstrap also starts a local onboarding service at `http://127.0.0.1:8011/aimipay/buyer/onboarding`, so the page can now save a merchant URL and refresh offer discovery directly from the browser

Merchant install doctor:

```powershell
.venv\Scripts\python.exe -m ops_tools.merchant_doctor
```

Create or refresh a local buyer wallet:

```powershell
.venv\Scripts\python.exe -m ops_tools.wallet_setup --force-create
```

Check whether the buyer wallet looks funded enough for live Tron usage:

```powershell
.venv\Scripts\python.exe -m ops_tools.wallet_funding
.venv\Scripts\python.exe -m ops_tools.agent_onboarding
```

Buyer funding checklist:

- [BUYER_FUNDING_CHECKLIST.md](/E:/trade/aimicropay-tron/python/BUYER_FUNDING_CHECKLIST.md)

Install doctor report exports:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_doctor --format markdown --output python/.docker-local/install-doctor.md
.venv\Scripts\python.exe -m ops_tools.install_doctor --format html --output python/.docker-local/install-doctor.html
```

Docker local stack:

```bash
docker compose -f docker-compose.local.yml up --build
docker compose -f docker-compose.local.yml --profile doctor run --rm aimipay-doctor
```

Agent package installation:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_agent_package --target all --mode repo-local
.venv\Scripts\python.exe -m ops_tools.install_agent_package --target all --mode home-local
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target all --mode home-local
powershell -ExecutionPolicy Bypass -File python/register_codex_home_local.ps1 -RunDoctor
```

Batch wrapper:

```bat
python\install_agent_package.bat --target all --mode repo-local
python\register_codex_home_local.bat
```

Distributed artifacts:

- agent core manifest: [agent-dist/aimipay-agent-core.json](/E:/trade/aimicropay-tron/agent-dist/aimipay-agent-core.json)
- connector package: [agent-dist/connector-package.json](/E:/trade/aimicropay-tron/agent-dist/connector-package.json)
- distribution guide: [agent-dist/README.md](/E:/trade/aimicropay-tron/agent-dist/README.md)
- host install checklist: [agent-dist/HOST_INSTALL_CHECKLIST.md](/E:/trade/aimicropay-tron/agent-dist/HOST_INSTALL_CHECKLIST.md)
- repo-local skill: [skills/aimipay-agent/SKILL.md](/E:/trade/aimicropay-tron/skills/aimipay-agent/SKILL.md)
- repo-local plugin: [plugin.json](/E:/trade/aimicropay-tron/plugins/aimipay-agent/.codex-plugin/plugin.json)

Gateway settlement wiring:

```python
from fastapi import FastAPI

from seller import GatewayConfig, GatewaySettlementConfig, install_gateway

app = FastAPI()
install_gateway(
    app,
    GatewayConfig(
        service_name="Research Copilot",
        service_description="Pay-per-use research and market data",
        seller_address="TRX_SELLER",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
        settlement=GatewaySettlementConfig(
            repository_root="e:/trade/aimicropay-tron",
            full_host="http://127.0.0.1:9090",
            seller_private_key="seller_private_key",
            chain_id=728126428,
        ),
    ),
)
```

When settlement is configured, the gateway exposes:

- `POST /_aimipay/settlements/execute`
- `POST /_aimipay/settlements/reconcile`
- `GET /_aimipay/ops/health`

`execute` submits settlement transactions. `reconcile` confirms submitted transactions and allows payment status to converge from `submitted` to `settled`.

Buyer-side lifecycle helpers:

- `BuyerClient.execute_payment(payment_id)`
- `BuyerClient.reconcile_payment(payment_id)`
- `BuyerClient.finalize_payment(payment_id, max_attempts=3)`

`finalize_payment(...)` is the agent-friendly helper that drives `execute` plus repeated `reconcile` calls until the payment reaches a terminal state or the attempt budget is exhausted.

`GET /_aimipay/payments/{payment_id}` is read-only. Payment status advances only through explicit settlement actions such as `POST /_aimipay/settlements/reconcile` or buyer-side helpers like `finalize_payment(...)`.

Operational notes:

- the gateway now records in-process counters and gauges for payment intents, settlement execution, reconciliation, and worker activity
- `GET /_aimipay/ops/health` returns configuration checks plus the current metrics snapshot
- settlement lock lease and confirmation retry budget are configurable through `GatewaySettlementConfig.processing_lock_ttl_s` and `GatewaySettlementConfig.max_confirmation_attempts`
- operators can record manual failure, compensation, or verified settlement through `POST /_aimipay/ops/payments/{payment_id}/action`
- `python/bootstrap_local.ps1` now auto-creates a buyer wallet on first install and writes it to `python/.env.local` plus `python/.wallets/buyer-wallet.json`

Settlement backend behavior:

- `claim_script`: `BuyerClient` builds `request_digest`, `voucher_digest`, and `buyer_signature` natively in Python
- `local_smoke`: buyer skips voucher construction and relies on the local Hardhat smoke backend to complete the local claim path

Operator runbook:

- [DEPLOYMENT_RUNBOOK.md](/E:/trade/aimicropay-tron/python/DEPLOYMENT_RUNBOOK.md)
- [MAINNET_CUTOVER_CHECKLIST.md](/E:/trade/aimicropay-tron/python/MAINNET_CUTOVER_CHECKLIST.md)
- [NILE_LAUNCH_CHECKLIST.md](/E:/trade/aimicropay-tron/python/NILE_LAUNCH_CHECKLIST.md)

Operator tooling:

- `python -m ops_tools.preflight_check --strict`
- `python -m ops_tools.preflight_check --env-file ./target.env --strict`
- `python -m ops_tools.preflight_check --backup-dir ./ops-backups --snapshot-path ./ops-backups/payments.snapshot.json --strict`
- `python -m ops_tools.payment_store_snapshot export --sqlite-path ./python/data/payments.db --snapshot-path ./ops-backups/payments.snapshot.json`
- `python -m ops_tools.target_dry_run --env-file ./target.env --output-dir ./python/.dry-run/target`
- `powershell -ExecutionPolicy Bypass -File python/run_target_dry_run.ps1 -EnvFile python/.env.target.example`
- `python python/examples/offchain_stress_drill.py`

Target environment files:

- baseline template: [python/.env.target.example](/E:/trade/aimicropay-tron/python/.env.target.example)
- current repo-local target config for dry runs: [python/target.env](/E:/trade/aimicropay-tron/python/target.env)
- Nile testnet template: [python/target.nile.env.example](/E:/trade/aimicropay-tron/python/target.nile.env.example)

Monitoring integration:

- Prometheus scrape config: [ops/prometheus/prometheus.yml](/E:/trade/aimicropay-tron/ops/prometheus/prometheus.yml)
- Alert rules: [ops/prometheus/aimipay-alerts.yml](/E:/trade/aimicropay-tron/ops/prometheus/aimipay-alerts.yml)

Low-code runtime entrypoints:

```python
from buyer import BuyerWallet, MarketSelectionPolicy, install_agent_payments
from buyer.provisioner import build_default_tron_provisioner

runtime = install_agent_payments(
    wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
    provisioner=build_default_tron_provisioner(repository_root="e:/trade/aimicropay-tron"),
    merchant_base_urls=["https://merchant-a.example", "https://merchant-b.example"],
    selection_policy=MarketSelectionPolicy(policy_name="balanced"),
)
runtime.enable_auto_wallet().enable_auto_purchase()
```

```python
from fastapi import FastAPI

from seller import install_sellable_capability
from shared import MerchantRoute

app = FastAPI()
runtime = install_sellable_capability(
    app,
    service_name="Research Copilot",
    service_description="Pay-per-use research and market data",
    seller_address="TRX_SELLER",
    contract_address="TRX_CONTRACT",
    token_address="TRX_USDT",
)
runtime.publish_api(
    path="/tools/research",
    price_atomic=250_000,
    capability_type="web_search",
)
```

Demo sample files:

- merchant app: `python/examples/merchant_app.py`
- agent runtime demo: `python/examples/agent_runtime_demo.py`
- agent MCP server demo: `python/examples/agent_mcp_server.py`

Merchant install kit:

- merchant install guide: [merchant-dist/README.md](/E:/trade/aimicropay-tron/merchant-dist/README.md)
- SaaS embed guide: [EMBED_GUIDE.md](/E:/trade/aimicropay-tron/merchant-dist/saas/EMBED_GUIDE.md)
- website starter: [embed.checkout.html](/E:/trade/aimicropay-tron/merchant-dist/website/embed.checkout.html)

Minimal MCP server skeleton:

```python
from buyer import AimiPayMcpServer, BuyerWallet, install_agent_payments
from buyer.provisioner import build_default_tron_provisioner

runtime = install_agent_payments(
    wallet=BuyerWallet(address="TRX_BUYER", private_key="buyer_pk"),
    provisioner=build_default_tron_provisioner(repository_root="e:/trade/aimicropay-tron"),
    merchant_base_url="http://127.0.0.1:8000",
    repository_root="e:/trade/aimicropay-tron",
)
server = AimiPayMcpServer(runtime)
tools = server.list_tools()
```

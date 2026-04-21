# AimiPay Host Installation Checklist

Use this checklist when you want to wire AimiPay into a host that speaks MCP or can launch a local tool server.

## 1. Prepare the local runtime

- Install Python 3.11+
- Install Node.js 20+ if you also want the local demo stack
- Clone this repository
- Install Python dependencies with `pip install -r python/requirements.txt`

Optional local readiness check:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_doctor
```

## 2. Choose the host target

- Codex home-local
  Use `python/register_codex_home_local.ps1`
- Claude / MCP hosts
  Start from `agent-dist/hosts/claude-desktop/claude_desktop_config.template.json`
- Generic MCP host
  Start from `agent-dist/hosts/generic/generic_mcp_server.template.json`
- CUA-style host
  Start from `agent-dist/hosts/cua/cua_mcp_config.template.json`
- Codex-style host
  Start from `agent-dist/hosts/codex/ONBOARDING_ADAPTER.md`

## 3. Fill the required environment values

- `AIMIPAY_REPOSITORY_ROOT`
- `AIMIPAY_FULL_HOST`
- `AIMIPAY_MERCHANT_URLS`
- `PYTHONPATH`

Optional buyer defaults:

- `AIMIPAY_BUYER_ADDRESS`
- `AIMIPAY_BUYER_PRIVATE_KEY`

## 4. Confirm the MCP entrypoint

Every host template should launch:

- command:
  Your Python interpreter
- args:
  `["-m", "agent_entrypoints.aimipay_mcp_stdio"]`

## 5. Validate after registration

- For Codex installs:
  `powershell -ExecutionPolicy Bypass -File python/register_codex_home_local.ps1 -RunDoctor`
- For manual MCP hosts:
  Launch the host and confirm the `aimipay-agent` MCP server is listed
- On first connect, display either:
  - `initialize.result.instructions`
  - or `initialize.result.meta["aimipay/startupOnboarding"]`
- Prefer `initialize.result.meta["aimipay/startupCard"]` when the host can render a structured first-screen card
- Use the host-specific adapter docs under `agent-dist/hosts/*/ONBOARDING_ADAPTER.md` to map the card into each UI
- If the host does not surface initialize metadata, call:
  - `aimipay.get_startup_onboarding`
- Verify the exposed tools:
  `list_offers`, `estimate_budget`, `open_channel`, `create_payment`, `execute_payment`, `reconcile_payment`, `finalize_payment`, `get_payment_status`, `check_wallet_funding`, `create_wallet`, `run_onboarding`, `get_startup_onboarding`

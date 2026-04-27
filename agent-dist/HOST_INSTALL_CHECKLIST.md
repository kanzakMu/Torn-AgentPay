# Torn-AgentPay Host Installation Checklist

Use this checklist when wiring Torn-AgentPay into an external AI host that speaks MCP, can load a plugin, or can run a skill-only command runner.

## 1. Prepare Runtime

- Install Python 3.11+.
- Clone this repository.
- Install Python dependencies:

```bash
cd python
python -m pip install -r requirements.txt
```

Optional readiness check:

```bash
PYTHONPATH=. python -m ops_tools.install_doctor
```

Node.js 20+ is only needed for contract tests or the local demo stack.

## 2. Choose Target

Use the high-level installer unless you are manually authoring host config.

```bash
PYTHONPATH=. python -m ops_tools.install_ai_host --host codex --mode home-local --merchant-url https://seller.example --json
```

Target choices:

- `codex`: Codex-style local host.
- `mcp`: generic MCP host config.
- `claude`: Claude Desktop-style config.
- `cua`: CUA-style config.
- `openclaw`: OpenClaw-style config.
- `hermes`: Hermes-style config.
- `skill`: skill-only install.
- `all`: generate/install every supported target.

## 3. Configure Environment

Required values for generated host configs:

- `AIMIPAY_REPOSITORY_ROOT`
- `AIMIPAY_FULL_HOST`
- `AIMIPAY_MERCHANT_URLS`
- `PYTHONPATH`

Optional buyer defaults:

- `AIMIPAY_BUYER_ADDRESS`
- `AIMIPAY_BUYER_PRIVATE_KEY`

Do not publish host configs containing real private keys.

## 4. Confirm MCP Entrypoint

Every MCP-capable host template should launch:

- command: the Python interpreter used during install
- args: `["-m", "agent_entrypoints.aimipay_mcp_stdio"]`

The generated config should set `PYTHONPATH` so the host can import `buyer`, `shared`, and `agent_entrypoints`.

## 5. Validate After Registration

Run the post-install self-check:

```bash
PYTHONPATH=. python -m ops_tools.host_post_install_check --repository-root .. --host codex --mode home-local --json
```

For manual MCP hosts:

- Launch the host.
- Confirm the `aimipay-agent` MCP server is listed.
- On first connect, display `initialize.result.instructions` when available.
- Prefer `initialize.result.meta["aimipay/startupCard"]` for structured onboarding UI.
- If initialize metadata is hidden by the host, call `aimipay.get_protocol_manifest` and `aimipay.get_agent_state`.

Expected core tools:

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

## 6. Skill-Only Fallback

If the host cannot load MCP/plugin config, install the skill target and call the runner:

```bash
PYTHONPATH=. python -m ops_tools.install_ai_host --host skill --mode home-local --merchant-url https://seller.example --json
python <skill-path>/aimipay_skill_runner.py doctor
python <skill-path>/aimipay_skill_runner.py protocol-manifest
python <skill-path>/aimipay_skill_runner.py get-agent-state
```

The runner is the fallback control plane for AI hosts that can only install instructions plus local files.

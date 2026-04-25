---
name: aimipay-agent
description: Install and operate AimiPay as an agent-native payment toolchain for Codex-style agents. Use when Codex needs to discover paid merchant offers, invoke AimiPay MCP tools, run install doctor, bootstrap the local demo, or guide a user through installing the AimiPay agent package.
---

# AimiPay Agent

Use the local AimiPay MCP server and installer artifacts from this repository.

## Quick start

1. Prefer the installed MCP tools if the plugin has already been installed.
2. If only the Codex skill is needed, run:
   `powershell -ExecutionPolicy Bypass -File python/install_skill.ps1 --mode home-local`
3. If MCP tools and host configs are also needed, run:
   `powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host codex --mode home-local`
4. For local health checks, run:
   `python -m ops_tools.install_doctor`
5. Before attempting paid purchases on a live Tron environment, run:
   `python -m ops_tools.wallet_funding`

## Skill-only install

Use this when the agent only needs reusable instructions and can call project commands itself:

`python -m ops_tools.install_skill --mode home-local`

Useful variants:

- Repo-local dry run: `python -m ops_tools.install_skill --mode repo-local`
- Custom install root: `python -m ops_tools.install_skill --mode home-local --install-root <path>`
- JSON report: `python -m ops_tools.install_skill --json`

The skill installs to `<CODEX_HOME>/skills/aimipay-agent` in `home-local` mode, or `skills/aimipay-agent` inside this repository in `repo-local` mode.

Skill-only installs include:

- `skill-runtime.json`: generated at install time with repository path, env file, merchant URLs, and runtime metadata.
- `aimipay_skill_runner.py`: a command runner for AI-facing protocol tools when MCP/plugin loading is unavailable.

Examples:

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

Prefer MCP tools when available. Use the skill runner as the fallback path for skill-only installs.
Start with `doctor` when the host only installed the skill; it returns missing runtime pieces and the next safe command.

## Installed toolchain

- MCP stdio server module:
  `agent_entrypoints.aimipay_mcp_stdio`
- Local plugin:
  `plugins/aimipay-agent`
- Repo-local skill:
  `skills/aimipay-agent`

## User-facing install flow

- Use `python/install_and_run.ps1` or `python/install_and_run.bat` for local demo installation.
- Use `python/install_skill.ps1` or `python/install_skill.bat` for skill-only installation.
- Use `python/install_ai_host.ps1` or `python/install_ai_host.bat` for one-command external AI host installation.
- Use `python/install_agent_package.ps1` or `python/install_agent_package.bat` for lower-level package installation.
- Use `python -m ops_tools.install_doctor --format markdown` or `--format html` for a shareable install report.
- Use `aimipay.check_wallet_funding` or `python -m ops_tools.wallet_funding` to decide whether the wallet is ready for live purchases.
- On MCP host startup, prefer the onboarding shown in `initialize.result.instructions` or call `aimipay.get_startup_onboarding`.

## External AI host install

Use the one-command installer for host-specific config generation:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host codex --merchant-url https://merchant.example
powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host claude --merchant-url https://merchant.example
powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host mcp --merchant-url https://merchant.example
```

Supported hosts: `codex`, `mcp`, `claude`, `cua`, `openclaw`, `hermes`, `all`, `skill`.

The installer writes:

- `aimipay-install-report.json`: machine-readable install result.
- `aimipay-post-install-check.json`: post-install artifact, skill doctor, manifest, and protocol smoke report.
- `aimipay-install-next-steps.md`: human-readable host-specific next actions.
- host config files under the generated host config directory.

For GitHub distribution on a clean machine, use:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_from_github.ps1 -RepoUrl https://github.com/<owner>/<repo>.git -Host codex -MerchantUrl https://merchant.example
```

## AI-facing protocol workflow

When MCP is available, prefer these structured tools:

1. `aimipay.get_protocol_manifest` for the stable tool flow and recovery matrix.
2. `aimipay.get_agent_state` for readiness, capabilities, pending payments, and next actions.
3. `aimipay.list_offers` for `capability_catalog`.
4. `aimipay.quote_budget` or `aimipay.plan_purchase` before spending.
5. `aimipay.prepare_purchase`, then `aimipay.submit_purchase`.
6. `aimipay.get_payment_status`, `aimipay.finalize_payment`, or `aimipay.recover_payment` for lifecycle and recovery.

All AI-facing protocol payloads use `schema_version: aimipay.agent-protocol.v1` and include `kind` plus `next_actions`.
The host-level manifest uses `schema_version: aimipay.capabilities.v1`.

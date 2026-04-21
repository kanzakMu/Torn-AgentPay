# AimiPay Agent Distribution

This directory contains the installable distribution metadata for using AimiPay as an agent-native package.

Primary handoff page:

- [SHOWCASE.md](/E:/trade/aimicropay-tron/SHOWCASE.md)

## Included targets

- `skills/aimipay-agent`
  Repo-local Codex skill for installation guidance and AimiPay payment workflows.
- `plugins/aimipay-agent`
  Repo-local Codex plugin that wires a local MCP server into Codex-style hosts.
- `agent-dist/connector-package.json`
  Connector metadata for hosts that want a simple manifest describing the available install artifacts.

## Fast install paths

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target all --mode repo-local
```

Windows batch wrapper:

```bat
python\install_agent_package.bat --target all --mode repo-local
```

Home-local install for Codex-style hosts:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target all --mode home-local
```

Install a single agent target with a merchant already wired in:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target codex --mode home-local --merchant-url https://merchant.example
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target mcp --mode home-local --merchant-url https://merchant.example
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target openclaw --mode home-local --merchant-url https://merchant.example
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target hermes --mode home-local --merchant-url https://merchant.example
```

GitHub direct install for agent hosts:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_agent_from_github.ps1 -OutFile $env:TEMP\\aimipay-agent-install.ps1; & $env:TEMP\\aimipay-agent-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git -Target codex -MerchantUrl https://merchant.example"
```

Codex home-local auto-register plus verification:

```powershell
powershell -ExecutionPolicy Bypass -File python/register_codex_home_local.ps1 -RunDoctor
```

## Install modes

- `repo-local`
  Copies the skill and plugin into this repository so local development builds can discover them immediately.
- `home-local`
  Copies the skill into `$CODEX_HOME/skills` (or `%USERPROFILE%\.codex\skills`) and the plugin into `%USERPROFILE%\plugins`, then creates a local marketplace entry.

## Installed runtime wiring

The installer patches the plugin MCP definition so it uses:

- the Python interpreter that ran the installer
- `PYTHONPATH` pointing at this repository's `python/` and `python/.vendor/`
- `AIMIPAY_REPOSITORY_ROOT` pointing at this repository

That keeps the installed plugin bound to a working runtime instead of relying on a generic `python` command being on PATH.

The installer also generates host-ready configuration files under the install target so AI hosts can use them immediately instead of starting from raw templates. Generated targets now include:

- Codex package metadata
- Generic MCP config
- Claude Desktop config
- CUA config
- OpenClaw config
- Hermes config

## Validation

After installation, verify the agent package wiring:

```powershell
powershell -ExecutionPolicy Bypass -File python/register_codex_home_local.ps1
```

If you also want a runtime readiness check, run:

```powershell
.venv\Scripts\python.exe -m ops_tools.install_doctor --format markdown
```

Manual verification only:

```powershell
.venv\Scripts\python.exe -m ops_tools.verify_agent_installation --mode home-local --json
```

## Host templates

- Host checklist: [HOST_INSTALL_CHECKLIST.md](/E:/trade/aimicropay-tron/agent-dist/HOST_INSTALL_CHECKLIST.md)
- Claude/MCP-style config: [claude_desktop_config.template.json](/E:/trade/aimicropay-tron/agent-dist/hosts/claude-desktop/claude_desktop_config.template.json)
- CUA-style config: [cua_mcp_config.template.json](/E:/trade/aimicropay-tron/agent-dist/hosts/cua/cua_mcp_config.template.json)
- Generic MCP host config: [generic_mcp_server.template.json](/E:/trade/aimicropay-tron/agent-dist/hosts/generic/generic_mcp_server.template.json)
- Claude onboarding adapter: [ONBOARDING_ADAPTER.md](/E:/trade/aimicropay-tron/agent-dist/hosts/claude-desktop/ONBOARDING_ADAPTER.md)
- CUA onboarding adapter: [ONBOARDING_ADAPTER.md](/E:/trade/aimicropay-tron/agent-dist/hosts/cua/ONBOARDING_ADAPTER.md)
- Codex onboarding adapter: [ONBOARDING_ADAPTER.md](/E:/trade/aimicropay-tron/agent-dist/hosts/codex/ONBOARDING_ADAPTER.md)
- Claude end-to-end example: [E2E_WALKTHROUGH.md](/E:/trade/aimicropay-tron/agent-dist/hosts/claude-desktop/E2E_WALKTHROUGH.md)
- Claude rendered startup card demo: [demo.startup_card.html](/E:/trade/aimicropay-tron/agent-dist/hosts/claude-desktop/demo.startup_card.html)
- Startup card assets: [theme.tokens.json](/E:/trade/aimicropay-tron/agent-dist/assets/startup-card/theme.tokens.json)
- Startup card copy guide: [copy-guidelines.md](/E:/trade/aimicropay-tron/agent-dist/assets/startup-card/copy-guidelines.md)

## Demo Rendering

Render the Claude-style startup card demo again at any time:

```powershell
.venv\Scripts\python.exe python/examples/render_claude_startup_card_demo.py --repository-root E:/trade/aimicropay-tron --output-file agent-dist/hosts/claude-desktop/demo.startup_card.html
```

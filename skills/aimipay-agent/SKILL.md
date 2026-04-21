---
name: aimipay-agent
description: Install and operate AimiPay as an agent-native payment toolchain for Codex-style agents. Use when Codex needs to discover paid merchant offers, invoke AimiPay MCP tools, run install doctor, bootstrap the local demo, or guide a user through installing the AimiPay agent package.
---

# AimiPay Agent

Use the local AimiPay MCP server and installer artifacts from this repository.

## Quick start

1. Prefer the installed MCP tools if the plugin has already been installed.
2. If installation is missing, run:
   `powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target all --mode repo-local`
3. For local health checks, run:
   `python -m ops_tools.install_doctor`
4. Before attempting paid purchases on a live Tron environment, run:
   `python -m ops_tools.wallet_funding`

## Installed toolchain

- MCP stdio server module:
  `agent_entrypoints.aimipay_mcp_stdio`
- Local plugin:
  `plugins/aimipay-agent`
- Repo-local skill:
  `skills/aimipay-agent`

## User-facing install flow

- Use `python/install_and_run.ps1` or `python/install_and_run.bat` for local demo installation.
- Use `python/install_agent_package.ps1` or `python/install_agent_package.bat` to copy the AimiPay skill and plugin into a Codex install.
- Use `python -m ops_tools.install_doctor --format markdown` or `--format html` for a shareable install report.
- Use `aimipay.check_wallet_funding` or `python -m ops_tools.wallet_funding` to decide whether the wallet is ready for live purchases.
- On MCP host startup, prefer the onboarding shown in `initialize.result.instructions` or call `aimipay.get_startup_onboarding`.

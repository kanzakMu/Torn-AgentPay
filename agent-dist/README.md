# Torn-AgentPay Agent Distribution

This directory contains the agent-facing distribution artifacts for installing Torn-AgentPay into local AI hosts.

It is intended for hosts that can load MCP servers, local skills, plugins, or connector metadata.

## Supported Targets

The installer currently supports:

- `codex`
- `mcp`
- `claude`
- `cua`
- `openclaw`
- `hermes`
- `all`

## Fast Install

Home-local install for one host target:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target codex --mode home-local --merchant-url https://seller.example
```

Install every supported target:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_agent_package.ps1 --target all --mode home-local --merchant-url https://seller.example
```

GitHub direct install:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_agent_from_github.ps1 -OutFile $env:TEMP\\torn-agentpay-agent-install.ps1; & $env:TEMP\\torn-agentpay-agent-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git -Target codex -MerchantUrl https://seller.example"
```

## What the Installer Does

The installer can:

- copy the local skill
- copy the local plugin
- install connector metadata
- generate host-ready config files
- bind the installed host config to the Python interpreter that performed the install
- persist seller service URLs into the generated host config
- run post-install verification
- run startup onboarding

## Install Modes

- `repo-local`
  Copies the skill and plugin into this repository for local development.
- `home-local`
  Copies the skill and plugin into the local user install directories so the host can discover them immediately.

## Generated Host Configs

Depending on the target, the installer generates ready-to-use host files for:

- Codex package metadata
- generic MCP hosts
- Claude Desktop-style hosts
- CUA-style hosts
- OpenClaw-style hosts
- Hermes-style hosts

## Verify the Install

Codex helper:

```powershell
powershell -ExecutionPolicy Bypass -File python/register_codex_home_local.ps1 -RunDoctor
```

Manual verification:

```powershell
.venv\Scripts\python.exe -m ops_tools.verify_agent_installation --mode home-local --json
```

## Host Guides

- [Host Install Checklist](./HOST_INSTALL_CHECKLIST.md)
- [Claude Desktop Adapter](./hosts/claude-desktop/ONBOARDING_ADAPTER.md)
- [CUA Adapter](./hosts/cua/ONBOARDING_ADAPTER.md)
- [Codex Adapter](./hosts/codex/ONBOARDING_ADAPTER.md)
- [Claude Desktop E2E Walkthrough](./hosts/claude-desktop/E2E_WALKTHROUGH.md)

## Distribution Artifacts

- agent core manifest: [`agent-dist/aimipay-agent-core.json`](./aimipay-agent-core.json)
- connector package: [`agent-dist/connector-package.json`](./connector-package.json)
- plugin manifest: [`plugins/aimipay-agent/.codex-plugin/plugin.json`](../plugins/aimipay-agent/.codex-plugin/plugin.json)
- repo skill: [`skills/aimipay-agent/SKILL.md`](../skills/aimipay-agent/SKILL.md)

## Notes

- The protocol namespace still uses `aimipay` for compatibility with the existing MCP and HTTP surface.
- The repository name is `Torn-AgentPay`, but many tool names, endpoint prefixes, and install flags still use `aimipay` or `merchant` for compatibility.

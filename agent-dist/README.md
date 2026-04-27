# Torn-AgentPay Agent Distribution

This directory contains the AI-host distribution artifacts for Torn-AgentPay: connector metadata, capability manifests, host templates, and generated config output.

The distribution is meant for hosts that can load MCP servers, local skills, plugins, or connector metadata. The protocol namespace remains `aimipay` for compatibility with the existing MCP and HTTP surface.

## Supported Targets

Installers support:

- `codex`
- `mcp`
- `claude`
- `cua`
- `openclaw`
- `hermes`
- `all`
- `skill`

## Preferred Installer

Use `install_ai_host` for external host setup.

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File python/install_ai_host.ps1 --host codex --mode home-local --merchant-url https://seller.example
```

Python module form after cloning the repository:

```bash
cd python
PYTHONPATH=. python -m ops_tools.install_ai_host --host codex --mode home-local --merchant-url https://seller.example --json
```

Install every supported host target:

```bash
cd python
PYTHONPATH=. python -m ops_tools.install_ai_host --host all --mode home-local --merchant-url https://seller.example --json
```

Skill-only install:

```bash
cd python
PYTHONPATH=. python -m ops_tools.install_ai_host --host skill --mode home-local --merchant-url https://seller.example --json
```

## Lower-Level Package Installer

Use `install_agent_package` when you want direct control over base artifacts.

```bash
cd python
PYTHONPATH=. python -m ops_tools.install_agent_package --target codex --mode home-local --merchant-url https://seller.example --json
```

Supported `--target` values include host targets plus `skill`, `plugin`, and `connector`.

## GitHub Direct Install

Windows clean-machine install:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/kanzakMu/Torn-AgentPay/main/python/install_agent_from_github.ps1 -OutFile $env:TEMP\aimipay-agent-install.ps1; & $env:TEMP\aimipay-agent-install.ps1 -RepoUrl https://github.com/kanzakMu/Torn-AgentPay.git -Host codex -MerchantUrl https://seller.example"
```

For macOS/Linux, clone the repository first and use the Python module installer.

## What The Installer Does

- Copies the local skill and writes `skill-runtime.json`.
- Copies the local plugin when the target requires plugin loading.
- Installs connector metadata and capability manifests.
- Generates host-ready MCP/config files.
- Binds generated configs to the Python interpreter that performed the install.
- Persists seller service URLs into generated host config.
- Runs artifact verification, skill doctor checks, and AI-facing protocol smoke unless skipped.
- Writes machine-readable and human-readable install reports.

Generated reports:

- `aimipay-install-report.json`
- `aimipay-post-install-check.json`
- `aimipay-install-next-steps.md`

## Install Modes

- `repo-local`: writes artifacts inside this repository for development.
- `home-local`: writes artifacts into local user install directories so hosts can discover them.

## Verify The Install

Post-install self-check:

```bash
cd python
PYTHONPATH=. python -m ops_tools.host_post_install_check --repository-root .. --host codex --mode home-local --json
```

Artifact-only verification:

```bash
cd python
PYTHONPATH=. python -m ops_tools.verify_agent_installation --mode home-local --json
```

AI-facing protocol smoke:

```bash
cd python
PYTHONPATH=. python -m ops_tools.ai_host_smoke --json
```

## Host Guides

- [Host Install Checklist](./HOST_INSTALL_CHECKLIST.md)
- [Claude Desktop Adapter](./hosts/claude-desktop/ONBOARDING_ADAPTER.md)
- [CUA Adapter](./hosts/cua/ONBOARDING_ADAPTER.md)
- [Codex Adapter](./hosts/codex/ONBOARDING_ADAPTER.md)
- [Claude Desktop E2E Walkthrough](./hosts/claude-desktop/E2E_WALKTHROUGH.md)

## Distribution Artifacts

- Agent core manifest: [`aimipay-agent-core.json`](./aimipay-agent-core.json)
- Connector package: [`connector-package.json`](./connector-package.json)
- Capability manifest: [`aimipay.capabilities.json`](./aimipay.capabilities.json)
- Plugin manifest: [`../plugins/aimipay-agent/.codex-plugin/plugin.json`](../plugins/aimipay-agent/.codex-plugin/plugin.json)
- Repo skill: [`../skills/aimipay-agent/SKILL.md`](../skills/aimipay-agent/SKILL.md)

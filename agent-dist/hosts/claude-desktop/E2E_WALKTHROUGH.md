# Claude Desktop End-to-End Example

Use this walkthrough when you want one concrete path from install to first-screen onboarding in a Claude-style MCP host.

## Goal

After Claude Desktop connects to `aimipay-agent`, the first screen should show:

- a startup banner sourced from `initialize.result.meta["aimipay/startupCard"]`
- a primary CTA such as `Create Wallet` or `Fund Wallet`
- a follow-up path into `aimipay.get_startup_onboarding`

## Files

- MCP config template:
  [claude_desktop_config.template.json](/E:/trade/aimicropay-tron/agent-dist/hosts/claude-desktop/claude_desktop_config.template.json)
- Startup card template:
  [startup_card.template.json](/E:/trade/aimicropay-tron/agent-dist/hosts/claude-desktop/startup_card.template.json)
- Example config:
  [claude_desktop.local.example.json](/E:/trade/aimicropay-tron/agent-dist/hosts/claude-desktop/claude_desktop.local.example.json)

## End-to-End Flow

1. Install the package locally
   - `powershell -ExecutionPolicy Bypass -File python/register_codex_home_local.ps1 -RunDoctor`
2. Copy the Claude config example and replace:
   - Python interpreter path
   - `AIMIPAY_REPOSITORY_ROOT`
   - `AIMIPAY_FULL_HOST`
   - `AIMIPAY_MERCHANT_URLS`
3. Launch Claude Desktop with the AimiPay MCP server enabled
4. On first connect, read:
   - `initialize.result.instructions`
   - `initialize.result.meta["aimipay/startupCard"]`
5. Render the banner card:
   - title from `startupCard.title`
   - body from `startupCard.summary`
   - CTA from `startupCard.primary_action`
6. If the user clicks the CTA:
   - `create_wallet` -> call `aimipay.create_wallet`
   - `fund_wallet` -> open `startupCard.resources[0]` when present, then call `aimipay.get_startup_onboarding`
   - `ready_to_purchase` -> call `aimipay.list_offers`
7. Refresh the banner state:
   - call `aimipay.get_startup_onboarding`
   - remove the card when `status.completed = true`

## Recommended Claude Banner Mapping

- Banner title
  - `startupCard.title`
- Banner body
  - `startupCard.summary`
- Primary button
  - `startupCard.primary_action.label`
- Secondary button
  - `View Onboarding Details`
- Details accordion
  - `startupCard.checklist`
  - `startupCard.resources`

## Example User Experience

1. Claude opens and shows `Fund Wallet`
2. User clicks the faucet/resource link
3. Claude calls `aimipay.get_startup_onboarding`
4. When funding becomes sufficient, the banner changes to `Continue to Offers`
5. Claude proceeds into `aimipay.list_offers`

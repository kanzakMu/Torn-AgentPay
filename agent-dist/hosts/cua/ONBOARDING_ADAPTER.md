# CUA Onboarding Adapter

Use this mapping when a CUA-style host turns MCP metadata into agent-visible suggestions.

## Read From

- `initialize.result.meta["aimipay/startupCard"]`
- fallback: `initialize.result.instructions`

## Recommended UI Mapping

- First assistant-visible message
  - `startupCard.summary`
- Suggested next action chip
  - label: `startupCard.primary_action.label`
  - value: `startupCard.primary_action.action`
- Checklist panel
  - `startupCard.checklist`
- Resource links
  - `startupCard.resources`

## Recommended Behavior

- When `startupCard.status.completed = false`, keep the onboarding card pinned until the agent reaches `ready_to_purchase`
- When the host supports tool shortcuts, map:
  - `create_wallet` -> `aimipay.create_wallet`
  - `fund_wallet` -> `aimipay.get_startup_onboarding`
  - `ready_to_purchase` -> `aimipay.list_offers`

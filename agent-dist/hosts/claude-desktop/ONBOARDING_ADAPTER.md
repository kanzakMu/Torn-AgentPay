# Claude Desktop Onboarding Adapter

Use this mapping when a Claude-style MCP host can render a first-screen card after `initialize`.

## Read From

- `initialize.result.instructions`
- `initialize.result.meta["aimipay/startupCard"]`

## Recommended UI Mapping

- Header
  - `startupCard.title`
- Summary text
  - `startupCard.summary`
- Primary button
  - label: `startupCard.primary_action.label`
  - action:
    - if `fund_wallet`, open the first item in `startupCard.resources` when present
    - otherwise call the matching MCP tool
- Secondary button
  - label: `startupCard.secondary_actions[0].label`
  - action:
    - call `aimipay.get_startup_onboarding`
- Expandable details
  - `startupCard.checklist`
  - `startupCard.resources`

## Recommended Behavior

- Show the card only when `startupCard.visible = true`
- Use `startupCard.tone` to set banner severity
- If the host cannot render a structured card, fall back to `initialize.result.instructions`

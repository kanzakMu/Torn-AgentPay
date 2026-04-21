# Codex Onboarding Adapter

Use this mapping when Codex or a Codex-style plugin host wants a plugin banner or startup card.

## Read From

- `initialize.result.meta["aimipay/startupCard"]`
- `initialize.result.meta["aimipay/startupOnboarding"]`
- fallback: `initialize.result.instructions`

## Recommended UI Mapping

- Plugin banner title
  - `startupCard.title`
- Plugin banner subtitle
  - `startupCard.summary`
- Quick action button
  - `startupCard.primary_action.label`
- Quick action follow-up
  - `startupCard.secondary_actions`
- Dropdown details
  - `startupCard.checklist`
  - `startupCard.resources`

## Recommended Behavior

- Show the banner immediately after the plugin is installed or first connected
- Keep the banner pinned while `startupCard.status.action_required` is not null
- Clear the banner when `startupCard.status.completed = true`

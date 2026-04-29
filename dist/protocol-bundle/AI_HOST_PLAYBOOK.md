# AI Host Playbook

AimiPay is designed for AI hosts that need structured payment state instead of a human-facing dashboard. Hosts should treat every response as an instruction envelope: read `schema_version`, inspect `kind`, honor `human_approval_required`, then follow `next_actions`.

## Default Flow

1. Call `aimipay.get_protocol_manifest` once at startup or install time.
2. Call `aimipay.get_agent_state` before any paid action.
3. Call `aimipay.list_offers` to present or select merchant capabilities.
4. Call `aimipay.quote_budget` before any side effect.
5. If the quote returns `auto_decision.allowed=true`, call `aimipay.plan_purchase`.
6. Call `aimipay.prepare_purchase` only after budget policy allows it.
7. Call `aimipay.submit_purchase` to create the voucher-backed payment.
8. Call `aimipay.finalize_payment` until the payment is terminal or recovery guidance says to stop.

## Required Host Behavior

- Never replay an old authorization after `request_deadline_expired` or `payment_expired`.
- Preserve `payment_id`, `idempotency_key`, and `channel_id` in host memory so recovery can continue after a restart.
- Stop and ask the user when any payload sets `human_approval_required=true`.
- Prefer `aimipay.list_pending_payments` after host startup if the previous session may have stopped mid-payment.
- Show the user the payment status before creating a replacement payment for the same task.

## Skill-Only Install

When only the skill is installed, the host can still ask the runner for structured state:

```powershell
python "<skill-root>/aimipay_skill_runner.py" doctor
python "<skill-root>/aimipay_skill_runner.py" protocol-manifest
python "<skill-root>/aimipay_skill_runner.py" get-agent-state
```

`doctor` does not require a plugin or MCP host. It checks the runtime config, repository path, env file, runner, and merchant URL configuration, then returns the next command the AI should run.

## Error Recovery

Common recovery actions are exposed through `aimipay.get_protocol_manifest` under `error_recovery_actions`.

- `budget_exceeded`: ask for approval or lower the requested units.
- `seller_unreachable`: retry discovery, then ask for a different merchant URL.
- `insufficient_balance`: call `aimipay.check_wallet_funding` and return funding instructions.
- `voucher_rejected`: rebuild authorization with a fresh nonce and deadline.
- `settlement_pending`: call `aimipay.finalize_payment` or `aimipay.reconcile_payment`.
- `payment_not_found`: call `aimipay.list_pending_payments` before asking the user for another id.

## Smoke Test

Run the local host-facing protocol smoke test:

```powershell
cd python
python -m ops_tools.ai_host_smoke --json
```

The smoke test exercises manifest, state, offers, quote, plan, and recovery payloads without requiring a live external AI host.

## Post-Install Self Check

External host installs run a post-install self-check by default and write `aimipay-post-install-check.json` next to the generated host configs. The report validates installed artifacts, generated host configs, the skill-only doctor, the capability manifest, and the AI-facing protocol smoke.

```powershell
cd python
python -m ops_tools.host_post_install_check --host codex --mode home-local --json
```

Hosts can read `ok`, `failed`, and `next_actions` from this report before trying to call paid tools.

# Mainnet Cutover Checklist

This checklist is the final operator-facing layer before opening non-local traffic.

## 1. Freeze Inputs

- freeze the intended contract address, token address, seller address, and chain id
- freeze the settlement backend choice and make sure the runbook matches it
- record the exact git revision and deployment timestamp for both chain and off-chain components

## 2. Run Preflight

- load the target environment variables
- run `python -m ops_tools.preflight_check --strict`
- if SQLite is in use, also run:
  - `python -m ops_tools.preflight_check --backup-dir <backup-dir> --snapshot-path <snapshot.json> --strict`
- verify the report is green before continuing

## 3. Validate Storage Safety

- confirm the SQLite file exists on durable storage
- confirm a fresh backup was created
- confirm a fresh JSON snapshot was exported
- verify the snapshot can be imported into a scratch store before relying on it for rollback

## 4. Controlled Traffic

- start with operator-owned buyer traffic only
- verify:
  - payment intents are created
  - execute submits transactions
  - reconcile moves submitted payments to terminal states
  - `unfinished_payments` does not grow without bound
- keep manual operator action procedures ready during this phase

## 5. Watch Signals

- `settlement_executed_total`
- `settlement_confirmed_total`
- `settlement_execution_failed_total`
- `settlement_confirmation_retry_exhausted_total`
- `worker_errors_total`
- `unfinished_payments`

If failure counters rise materially faster than confirmed settlements, pause traffic and investigate before widening rollout.

## 6. Rollback Readiness

- keep the most recent SQLite backup and JSON snapshot accessible
- keep the operator runbook and manual compensation flow open
- ensure at least one operator can mark payments as failed, compensated, or manually settled
- define the threshold that triggers traffic pause or rollback before launch day

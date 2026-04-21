# Off-Chain Deployment Runbook

This runbook covers the off-chain merchant runtime before a controlled launch.

## Preflight

1. Install Python dependencies:
   - `pip install -r python/requirements.txt`
2. Verify Node tooling is present for settlement backends:
   - `node --version`
   - `npx --version` when using `local_smoke`
3. Confirm runtime configuration:
   - `AIMIPAY_REPOSITORY_ROOT`
   - `AIMIPAY_FULL_HOST`
   - `AIMIPAY_SELLER_PRIVATE_KEY`
   - `AIMIPAY_SETTLEMENT_BACKEND`
   - `AIMIPAY_CHAIN_ID`
4. Prefer SQLite for any non-trivial environment:
   - set `GatewayConfig.sqlite_path`
5. Confirm buyer funding guidance for the target network:
   - `python -m ops_tools.wallet_funding --env-file ./target.env`
   - set `AIMIPAY_NETWORK_NAME`, `AIMIPAY_FAUCET_URL`, `AIMIPAY_FUNDING_GUIDE_URL`, and minimum balance thresholds in the env file when appropriate
6. Run the preflight tool:
   - `python -m ops_tools.preflight_check --strict`
   - or `python -m ops_tools.preflight_check --env-file ./target.env --strict`
7. For long-lived environments, generate rollback artifacts before widening traffic:
   - `python -m ops_tools.preflight_check --backup-dir <backup-dir> --snapshot-path <snapshot.json> --strict`
   - or run the full automation path:
   - `python -m ops_tools.target_dry_run --env-file ./target.env --output-dir ./python/.dry-run/target`
   - PowerShell wrapper:
   - `powershell -ExecutionPolicy Bypass -File python/run_target_dry_run.ps1 -EnvFile python/.env.target.example`
8. Keep the target env file under change control:
   - `python/target.env` in this repo is the current dry-run baseline

## Recommended Settings

- `GatewaySettlementConfig.processing_lock_ttl_s`
  - default: `300`
  - increase when chain submission or confirmation routinely takes longer than five minutes
- `GatewaySettlementConfig.max_confirmation_attempts`
  - default: `10`
  - lower for fast-fail staging, higher for noisy public-node environments
- `PaymentRecoveryWorkerConfig.max_retryable_failures`
  - default: `5`
  - controls how many failed-but-retryable records the worker will re-submit

## Start-Up

1. Start the merchant runtime:
   - `python -m uvicorn python.examples.merchant_app:app --host 127.0.0.1 --port 8000`
2. Check the health endpoint:
   - `GET /_aimipay/ops/health`
3. Confirm:
   - `ok = true` for the full report when the runtime is production-ready
   - required checks such as `repository_root_exists`, `repository_scripts_exist`, `node_available`, and `seller_private_key_present`
   - metrics are present and update after test traffic

## Runtime Checks

- `GET /_aimipay/ops/health`
  - use for config validation and a metrics snapshot
- `GET /_aimipay/ops/metrics`
  - use for Prometheus-style scraping and simple alert integration
- `GET /_aimipay/payments/pending`
  - use to inspect unfinished payment backlog
- `GET /_aimipay/payments/recover`
  - use when an idempotency key, channel, or payment needs targeted recovery
- `POST /_aimipay/settlements/reconcile`
  - use to explicitly advance submitted payments toward finality
- `POST /_aimipay/ops/payments/{payment_id}/action`
  - use to record manual failure, manual compensation, or verified manual settlement

## Incident Hints

- `payment_status_queries_total` rising with a flat `settlement_confirmed_total`
  - agents are checking status but nothing is finalizing; investigate reconcile flow
- `settlement_execution_failed_total` increasing
  - inspect claim backend, seller key, node access, and settlement payload validity
- `settlement_confirmation_retry_exhausted_total` increasing
  - confirmation path is noisy or degraded; inspect node connectivity and confirmation backend health
- `unfinished_payments` growing
  - worker cadence, settlement backend health, or chain latency is falling behind demand

## Manual Intervention

- `mark_failed`
  - use when the payment should be frozen as an operator-reviewed failure
- `mark_compensated`
  - use when funds or service were compensated outside the automated settlement path
- `mark_settled`
  - use only after an operator has independently verified final settlement

Every operator action should include a note describing the external evidence, ticket, or remediation taken.

## Operator Guidance

- treat `GET /_aimipay/payments/{payment_id}` as read-only
- use explicit reconcile or buyer/runtime finalize helpers to move a submitted payment forward
- keep SQLite backups if the environment is long-lived
- for larger traffic or stricter durability, plan to migrate beyond SQLite before wider rollout
- run `python python/examples/offchain_stress_drill.py` after meaningful runtime changes to recheck worker contention and recovery behavior
- prefer env-file driven dry runs so the exact target configuration can be re-run and audited later
- use `ops/prometheus/prometheus.yml` and `ops/prometheus/aimipay-alerts.yml` as the baseline monitoring integration when wiring the runtime into your Prometheus stack

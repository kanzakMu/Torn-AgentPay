# AimiPay Prometheus Integration

These files wire `/_aimipay/ops/metrics` into a Prometheus scrape job and baseline alert rules.

## Files

- `prometheus.yml`
  - adds a scrape target for the merchant runtime metrics endpoint
- `aimipay-alerts.yml`
  - alert rules for runtime health, unfinished backlog, worker errors, retry exhaustion, and execution failure spikes

## How To Use

1. Point the `targets` entry in `prometheus.yml` at the real merchant host and port.
2. Mount `aimipay-alerts.yml` into your Prometheus rules directory.
3. Reload Prometheus and verify the target is healthy.
4. Confirm `aimipay_runtime_ok` and `aimipay_unfinished_payments` appear in the Prometheus UI before rollout.

## Recommended First Alerts

- `AimiPayRuntimeDegraded`
- `AimiPayUnfinishedPaymentsGrowing`
- `AimiPayConfirmationRetriesExhausted`
- `AimiPayWorkerErrors`

These alerts are intentionally small and opinionated so you can tighten thresholds after the first production week.

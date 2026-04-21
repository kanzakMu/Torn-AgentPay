from __future__ import annotations

import argparse
import json
import os
import threading
from pathlib import Path
from typing import Any

from examples.env_loader import load_default_example_env, load_env_file
from examples.offchain_stress_drill import build_stress_drill_runtime, seed_drill_payments
from seller import PaymentRecoveryWorker, PaymentRecoveryWorkerConfig

from .payment_store_tools import import_payment_snapshot
from .preflight import build_gateway_config_from_env, build_preflight_report


def run_target_dry_run(
    *,
    output_dir: str | Path,
    env_file: str | Path | None = None,
    payment_count: int = 48,
    worker_count: int = 6,
    max_rounds: int = 8,
    execute_delay_s: float = 0.05,
    confirm_delay_s: float = 0.05,
) -> dict[str, Any]:
    load_default_example_env()
    if env_file is not None:
        load_env_file(env_file, override=True)
    output_path = Path(output_dir)
    artifacts_dir = output_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    config = build_gateway_config_from_env(env_file=env_file)
    preflight_report = build_preflight_report(
        config,
        backup_dir=artifacts_dir,
        snapshot_path=artifacts_dir / "target-payments.snapshot.json",
    )

    snapshot_restore_summary = None
    snapshot_path = artifacts_dir / "target-payments.snapshot.json"
    if snapshot_path.exists():
        restore_path = artifacts_dir / "target-snapshot-restore-check.db"
        if restore_path.exists():
            restore_path.unlink()
        from shared import SqlitePaymentStore

        restore_store = SqlitePaymentStore(restore_path)
        import_result = import_payment_snapshot(restore_store, snapshot_path)
        restored_records = restore_store.recover()
        snapshot_restore_summary = {
            "imported": import_result["count"],
            "restored": len(restored_records),
            "status_counts": _status_counts(restored_records),
            "restore_path": str(restore_path),
        }

    drill_sqlite_path = output_path / "target-drill.db"
    runtime = build_stress_drill_runtime(
        sqlite_path=drill_sqlite_path,
        execute_delay_s=execute_delay_s,
        confirm_delay_s=confirm_delay_s,
        execute_retryable_fail_stride=9,
        confirm_pending_stride=4,
        confirm_retryable_error_stride=10,
        confirm_terminal_fail_stride=15,
        processing_lock_ttl_s=int(os.environ.get("AIMIPAY_PROCESSING_LOCK_TTL_S", "180")),
        max_confirmation_attempts=int(os.environ.get("AIMIPAY_MAX_CONFIRMATION_ATTEMPTS", "6")),
    )
    seed_drill_payments(runtime, payment_count=payment_count)
    workers = [
        PaymentRecoveryWorker(runtime, config=PaymentRecoveryWorkerConfig(max_retryable_failures=8))
        for _ in range(worker_count)
    ]
    drill_rounds: list[dict[str, Any]] = []
    for round_number in range(1, max_rounds + 1):
        batch: list[dict[str, object]] = []
        threads: list[threading.Thread] = []
        for worker in workers:
            thread = threading.Thread(target=lambda w=worker: batch.append(w.run_once()))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
        records = runtime.recover_payments()
        summary = {
            "round": round_number,
            "worker_runs": len(batch),
            "status_counts": _status_counts(records),
        }
        summary["unfinished"] = sum(
            count
            for status, count in summary["status_counts"].items()
            if status in {"pending", "authorized", "submitted"}
        )
        drill_rounds.append(summary)
        if summary["unfinished"] == 0:
            break

    dry_run_report = {
        "preflight": preflight_report,
        "snapshot_restore": snapshot_restore_summary,
        "drill": {
            "sqlite_path": str(drill_sqlite_path),
            "payment_count": payment_count,
            "worker_count": worker_count,
            "rounds": drill_rounds,
            "final_metrics": runtime.metrics.snapshot(),
            "prometheus_metrics": runtime.prometheus_metrics(),
        },
    }
    report_path = artifacts_dir / "target-dry-run-report.json"
    report_path.write_text(json.dumps(dry_run_report, indent=2, sort_keys=True), encoding="utf-8")
    return dry_run_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run target-environment AimiPay dry run automation.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--payment-count", type=int, default=48)
    parser.add_argument("--worker-count", type=int, default=6)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--execute-delay-s", type=float, default=0.05)
    parser.add_argument("--confirm-delay-s", type=float, default=0.05)
    args = parser.parse_args(argv)

    report = run_target_dry_run(
        output_dir=args.output_dir,
        env_file=args.env_file,
        payment_count=args.payment_count,
        worker_count=args.worker_count,
        max_rounds=args.max_rounds,
        execute_delay_s=args.execute_delay_s,
        confirm_delay_s=args.confirm_delay_s,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _status_counts(records: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        status = str(getattr(record, "status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())

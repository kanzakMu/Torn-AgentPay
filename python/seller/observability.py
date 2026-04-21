from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RuntimeMetrics:
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, int] = field(default_factory=dict)
    timestamps: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def incr(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + amount
            self.timestamps[key] = int(time.time())

    def set_gauge(self, key: str, value: int) -> None:
        with self._lock:
            self.gauges[key] = value
            self.timestamps[key] = int(time.time())

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "timestamps": dict(self.timestamps),
            }

    def to_prometheus(self, *, namespace: str = "aimipay") -> str:
        snapshot = self.snapshot()
        lines: list[str] = []
        for section in ("counters", "gauges"):
            values = snapshot.get(section, {})
            for key in sorted(values):
                metric_name = _prometheus_name(namespace, key)
                metric_type = "counter" if section == "counters" else "gauge"
                lines.append(f"# TYPE {metric_name} {metric_type}")
                lines.append(f"{metric_name} {values[key]}")
        return "\n".join(lines) + ("\n" if lines else "")


@dataclass(slots=True)
class StructuredEventLogger:
    logger_name: str = "aimipay.runtime"

    def emit(self, event: str, **payload: Any) -> None:
        logging.getLogger(self.logger_name).info(
            json.dumps(
                {
                    "event": event,
                    "ts": int(time.time()),
                    **payload,
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )


def validate_runtime_config(config: object) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    settlement = getattr(config, "settlement", None)
    sqlite_path = getattr(config, "sqlite_path", None)
    if sqlite_path:
        sqlite_parent = Path(str(sqlite_path)).expanduser().resolve().parent
        checks.append(
            {
                "name": "sqlite_parent_exists",
                "ok": sqlite_parent.exists(),
                "detail": str(sqlite_parent),
            }
        )
    else:
        checks.append(
            {
                "name": "sqlite_configured",
                "ok": False,
                "detail": "sqlite_path is not configured; runtime uses in-memory storage",
            }
        )
    if settlement is None:
        checks.append(
            {
                "name": "settlement_configured",
                "ok": False,
                "detail": "settlement service is not configured",
            }
        )
        return _summary(checks)

    repository_root = Path(str(settlement.repository_root)).expanduser()
    backend = str(settlement.executor_backend)
    checks.extend(
        [
            {
                "name": "repository_root_exists",
                "ok": repository_root.exists(),
                "detail": str(repository_root),
            },
            {
                "name": "repository_scripts_exist",
                "ok": (repository_root / "scripts").exists(),
                "detail": str(repository_root / "scripts"),
            },
            {
                "name": "node_available",
                "ok": shutil.which("node") is not None,
                "detail": shutil.which("node") or "node not found in PATH",
            },
            {
                "name": "seller_private_key_present",
                "ok": bool(getattr(settlement, "seller_private_key", "")),
                "detail": "seller private key configured" if getattr(settlement, "seller_private_key", "") else "missing",
            },
            {
                "name": "full_host_present",
                "ok": bool(getattr(settlement, "full_host", "")),
                "detail": str(getattr(settlement, "full_host", "")),
            },
        ]
    )
    if backend == "local_smoke":
        npx_name = "npx.cmd" if os.name == "nt" else "npx"
        checks.append(
            {
                "name": "npx_available",
                "ok": shutil.which(npx_name) is not None or shutil.which("npx") is not None,
                "detail": shutil.which(npx_name) or shutil.which("npx") or "npx not found in PATH",
            }
        )
    return _summary(checks)


def _summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    ok = all(bool(item["ok"]) for item in checks)
    return {
        "ok": ok,
        "checks": checks,
    }


def build_runtime_summary(*, metrics: RuntimeMetrics, checks: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot = metrics.snapshot()
    counters = snapshot.get("counters", {})
    gauges = snapshot.get("gauges", {})
    health = "ok"
    reasons: list[str] = []
    if any(not bool(item.get("ok")) for item in checks):
        health = "degraded"
        reasons.append("config_checks_failed")
    unfinished = int(gauges.get("unfinished_payments", 0))
    retry_exhausted = int(counters.get("settlement_confirmation_retry_exhausted_total", 0))
    worker_errors = int(counters.get("worker_errors_total", 0))
    if unfinished > 0:
        reasons.append("unfinished_payments_present")
    if retry_exhausted > 0:
        health = "degraded"
        reasons.append("confirmation_retry_exhausted")
    if worker_errors > 0:
        health = "degraded"
        reasons.append("worker_errors_present")
    recommendations = _build_recommendations(
        unfinished=unfinished,
        retry_exhausted=retry_exhausted,
        worker_errors=worker_errors,
    )
    return {
        "health": health,
        "reasons": reasons,
        "recommendations": recommendations,
    }


def _prometheus_name(namespace: str, key: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "_" for ch in key).strip("_").lower()
    if normalized and normalized[0].isdigit():
        normalized = f"metric_{normalized}"
    return f"{namespace}_{normalized}"


def _build_recommendations(*, unfinished: int, retry_exhausted: int, worker_errors: int) -> list[str]:
    recommendations: list[str] = []
    if unfinished > 0:
        recommendations.append("inspect unfinished payments and keep reconcile worker active before widening traffic")
    if retry_exhausted > 0:
        recommendations.append("review confirmation backend health and operator intervention flow before rollout")
    if worker_errors > 0:
        recommendations.append("inspect worker logs and settlement execution dependencies before rollout")
    if not recommendations:
        recommendations.append("runtime looks healthy; keep backup and snapshot cadence before target rollout")
    return recommendations

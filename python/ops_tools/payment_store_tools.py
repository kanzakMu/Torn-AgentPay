from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

from shared import PaymentRecord


SNAPSHOT_VERSION = "aimipay-payment-snapshot.v1"


def export_payment_snapshot(
    store: object,
    destination: str | Path,
    *,
    statuses: list[str] | None = None,
    chain: str | None = None,
) -> dict[str, Any]:
    payments = _collect_records(store=store, statuses=statuses, chain=chain)
    snapshot = {
        "version": SNAPSHOT_VERSION,
        "exported_at": int(time.time()),
        "count": len(payments),
        "filters": {
            "statuses": list(statuses) if statuses is not None else None,
            "chain": chain,
        },
        "payments": [record.model_dump(mode="json") for record in payments],
    }
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return snapshot


def load_payment_snapshot(source: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if payload.get("version") != SNAPSHOT_VERSION:
        raise ValueError(f"unsupported payment snapshot version: {payload.get('version')}")
    return payload


def import_payment_snapshot(
    store: object,
    source: str | Path,
) -> dict[str, Any]:
    snapshot = load_payment_snapshot(source)
    imported = 0
    for raw_record in snapshot.get("payments", []):
        _store_upsert(store, PaymentRecord(**raw_record))
        imported += 1
    return {
        "version": snapshot["version"],
        "imported": imported,
        "count": imported,
    }


def backup_sqlite_database(
    sqlite_path: str | Path,
    *,
    backup_dir: str | Path,
    label: str = "payments",
) -> Path:
    source = Path(sqlite_path)
    if not source.exists():
        raise FileNotFoundError(f"sqlite database not found: {source}")
    destination_dir = Path(backup_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    destination = destination_dir / f"{label}-{timestamp}.sqlite3"
    with sqlite3.connect(source) as source_conn:
        with sqlite3.connect(destination) as destination_conn:
            source_conn.backup(destination_conn)
    shutil.copystat(source, destination, follow_symlinks=False)
    return destination


def _collect_records(
    *,
    store: object,
    statuses: list[str] | None,
    chain: str | None,
) -> list[PaymentRecord]:
    if statuses is not None:
        if hasattr(store, "recover"):
            return list(store.recover(statuses=statuses))
        raise TypeError("store does not support status-based recovery")
    if hasattr(store, "list"):
        return list(store.list(chain=chain))
    if hasattr(store, "recover"):
        return list(store.recover())
    raise TypeError("store does not expose list() or recover()")


def _store_upsert(store: object, record: PaymentRecord) -> PaymentRecord:
    if not hasattr(store, "upsert"):
        raise TypeError("store does not expose upsert()")
    return store.upsert(record)

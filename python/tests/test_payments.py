from __future__ import annotations

import sqlite3
from pathlib import Path

from shared import PaymentRecord, SqlitePaymentStore
from ops_tools.payment_store_tools import (
    backup_sqlite_database,
    export_payment_snapshot,
    import_payment_snapshot,
    load_payment_snapshot,
)
from shared import InMemoryPaymentStore


def test_sqlite_payment_store_persists_records_across_instances(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "payments.db"
    first_store = SqlitePaymentStore(sqlite_path)
    stored = first_store.upsert(
        PaymentRecord(
            payment_id="pay_sqlite_1",
            idempotency_key="idem_sqlite_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_sqlite_1",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=9_999_999_999,
            status="authorized",
        )
    )

    second_store = SqlitePaymentStore(sqlite_path)
    loaded = second_store.get("pay_sqlite_1")
    recovered = second_store.recover(idempotency_key="idem_sqlite_1")

    assert stored.created_at is not None
    assert loaded is not None
    assert loaded.payment_id == "pay_sqlite_1"
    assert loaded.status == "authorized"
    assert len(recovered) == 1
    assert recovered[0].channel_id == "channel_sqlite_1"


def test_sqlite_payment_store_create_or_get_recovers_from_integrity_race(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "payments.db"
    store = SqlitePaymentStore(sqlite_path)
    record = PaymentRecord(
        payment_id="pay_sqlite_race_new",
        idempotency_key="idem_sqlite_race",
        route_path="/tools/research",
        amount_atomic=250_000,
        chain="tron",
        buyer_address="TRX_BUYER",
        seller_address="TRX_SELLER",
        channel_id="channel_sqlite_race",
        contract_address="TRX_CONTRACT",
        token_address="TRX_USDT",
        voucher_nonce=1,
        expires_at=9_999_999_999,
        request_deadline=9_999_999_999,
        status="authorized",
    )
    existing = store.upsert(
        record.model_copy(
            update={
                "payment_id": "pay_sqlite_race_existing",
            }
        )
    )

    original_upsert = store.upsert

    def flaky_upsert(candidate):
        if candidate.payment_id == "pay_sqlite_race_new":
            raise sqlite3.IntegrityError("UNIQUE constraint failed: micropay_payments.idempotency_key")
        return original_upsert(candidate)

    store.upsert = flaky_upsert  # type: ignore[method-assign]
    resolved = store.create_or_get(record)

    assert resolved.payment_id == existing.payment_id


def test_payment_snapshot_can_export_and_import_between_stores(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "payments.db"
    snapshot_path = tmp_path / "payments.snapshot.json"
    sqlite_store = SqlitePaymentStore(sqlite_path)
    sqlite_store.upsert(
        PaymentRecord(
            payment_id="pay_snapshot_1",
            idempotency_key="idem_snapshot_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_snapshot_1",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=9_999_999_999,
            status="settled",
        )
    )

    exported = export_payment_snapshot(sqlite_store, snapshot_path)
    loaded = load_payment_snapshot(snapshot_path)
    memory_store = InMemoryPaymentStore()
    imported = import_payment_snapshot(memory_store, snapshot_path)

    assert exported["count"] == 1
    assert loaded["version"] == "aimipay-payment-snapshot.v1"
    assert imported["count"] == 1
    assert memory_store.get("pay_snapshot_1").status == "settled"


def test_payment_store_tools_can_backup_sqlite_database(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "payments.db"
    backup_dir = tmp_path / "backups"
    store = SqlitePaymentStore(sqlite_path)
    store.upsert(
        PaymentRecord(
            payment_id="pay_backup_1",
            idempotency_key="idem_backup_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_backup_1",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=9_999_999_999,
            status="authorized",
        )
    )

    backup_path = backup_sqlite_database(sqlite_path, backup_dir=backup_dir)

    assert backup_path.exists()
    assert backup_path.read_bytes()

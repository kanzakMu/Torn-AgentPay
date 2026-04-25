from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, Iterable

from .errors import aimipay_error
from .models import PaymentRecord
from .protocol_native import channel_id_of


def make_payment_id() -> str:
    return f"pay_{secrets.token_hex(12)}"


def make_channel_id(
    *,
    buyer_address: str,
    seller_address: str,
    token_address: str,
    channel_salt: str = "0x0000000000000000000000000000000000000000000000000000000000000000",
) -> str:
    return channel_id_of(
        buyer_address=buyer_address,
        seller_address=seller_address,
        token_address=token_address,
        channel_salt=channel_salt,
    )


class InMemoryPaymentStore:
    def __init__(self) -> None:
        self._records: Dict[str, PaymentRecord] = {}
        self._idempotency_keys: Dict[str, str] = {}
        self._lock = threading.RLock()

    def upsert(self, record: PaymentRecord) -> PaymentRecord:
        with self._lock:
            existing = self._records.get(record.payment_id)
            prepared = _prepare_record(record, existing=existing)
            self._records[prepared.payment_id] = prepared
            if prepared.idempotency_key:
                self._idempotency_keys[prepared.idempotency_key] = prepared.payment_id
            return prepared

    def get(self, payment_id: str) -> PaymentRecord | None:
        with self._lock:
            return self._records.get(payment_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> PaymentRecord | None:
        with self._lock:
            payment_id = self._idempotency_keys.get(idempotency_key)
            if payment_id is None:
                return None
            return self._records.get(payment_id)

    def create_or_get(self, record: PaymentRecord) -> PaymentRecord:
        with self._lock:
            if not record.idempotency_key:
                return self.upsert(record)
            existing = self.get_by_idempotency_key(record.idempotency_key)
            if existing is not None:
                if _idempotency_payload(existing) != _idempotency_payload(record):
                    raise aimipay_error(
                        "idempotency_conflict",
                        message=f"idempotency_key conflict for existing payment: {existing.payment_id}",
                        details={"existing_payment_id": existing.payment_id},
                    )
                return existing
            return self.upsert(record)

    def acquire_processing_lock(
        self,
        payment_id: str,
        *,
        stage: str,
        token: str,
        ttl_s: int = 300,
    ) -> PaymentRecord | None:
        with self._lock:
            record = self._records.get(payment_id)
            if record is None:
                return None
            now = int(time.time())
            if (
                record.processing_stage
                and record.processing_token != token
                and (record.processing_started_at or 0) + ttl_s > now
            ):
                return None
            locked = record.model_copy(
                update={
                    "processing_stage": stage,
                    "processing_token": token,
                    "processing_started_at": now,
                }
            )
            return self.upsert(locked)

    def claim_for_processing(
        self,
        *,
        statuses: Iterable[str],
        stage: str,
        token: str,
        ttl_s: int = 300,
        chain: str | None = None,
        limit: int | None = None,
    ) -> list[PaymentRecord]:
        with self._lock:
            now = int(time.time())
            claimed: list[PaymentRecord] = []
            for record in self._records.values():
                if record.status not in set(statuses):
                    continue
                if chain is not None and record.chain != chain:
                    continue
                if (
                    record.processing_stage
                    and record.processing_token != token
                    and (record.processing_started_at or 0) + ttl_s > now
                ):
                    continue
                locked = self.upsert(
                    record.model_copy(
                        update={
                            "processing_stage": stage,
                            "processing_token": token,
                            "processing_started_at": now,
                        }
                    )
                )
                claimed.append(locked)
                if limit is not None and len(claimed) >= limit:
                    break
            return claimed

    def list(
        self,
        *,
        status: str | None = None,
        chain: str | None = None,
        channel_id: str | None = None,
    ) -> list[PaymentRecord]:
        records = list(self._records.values())
        if status is not None:
            records = [record for record in records if record.status == status]
        if chain is not None:
            records = [record for record in records if record.chain == chain]
        if channel_id is not None:
            records = [record for record in records if record.channel_id == channel_id]
        return records

    def recover(
        self,
        *,
        payment_id: str | None = None,
        idempotency_key: str | None = None,
        channel_id: str | None = None,
        statuses: Iterable[str] | None = None,
    ) -> list[PaymentRecord]:
        records = list(self._records.values())
        if payment_id is not None:
            records = [record for record in records if record.payment_id == payment_id]
        if idempotency_key is not None:
            records = [record for record in records if record.idempotency_key == idempotency_key]
        if channel_id is not None:
            records = [record for record in records if record.channel_id == channel_id]
        if statuses is not None:
            status_set = set(statuses)
            records = [record for record in records if record.status in status_set]
        return sorted(
            records,
            key=lambda record: ((record.updated_at or 0), (record.created_at or 0), record.payment_id),
            reverse=True,
        )


class SqlitePaymentStore:
    def __init__(self, sqlite_path: str | os.PathLike[str]) -> None:
        self.sqlite_path = str(sqlite_path)
        self._initialize()

    def upsert(self, record: PaymentRecord) -> PaymentRecord:
        existing = self.get(record.payment_id)
        prepared = _prepare_record(record, existing=existing)
        payload_json = json.dumps(prepared.model_dump(mode="json"), sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO micropay_payments (
                    payment_id,
                    idempotency_key,
                    channel_id,
                    chain,
                    status,
                    created_at,
                    updated_at,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(payment_id) DO UPDATE SET
                    idempotency_key = excluded.idempotency_key,
                    channel_id = excluded.channel_id,
                    chain = excluded.chain,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    payload_json = excluded.payload_json
                """,
                (
                    prepared.payment_id,
                    prepared.idempotency_key,
                    prepared.channel_id,
                    prepared.chain,
                    prepared.status,
                    prepared.created_at,
                    prepared.updated_at,
                    payload_json,
                ),
            )
        return prepared

    def get(self, payment_id: str) -> PaymentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM micropay_payments WHERE payment_id = ?",
                (payment_id,),
            ).fetchone()
        if row is None:
            return None
        return PaymentRecord(**json.loads(row[0]))

    def get_by_idempotency_key(self, idempotency_key: str) -> PaymentRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM micropay_payments WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        if row is None:
            return None
        return PaymentRecord(**json.loads(row[0]))

    def create_or_get(self, record: PaymentRecord) -> PaymentRecord:
        if not record.idempotency_key:
            return self.upsert(record)
        existing = self.get_by_idempotency_key(record.idempotency_key)
        if existing is None:
            try:
                return self.upsert(record)
            except sqlite3.IntegrityError:
                concurrent = self.get_by_idempotency_key(record.idempotency_key)
                if concurrent is None:
                    raise
                if _idempotency_payload(concurrent) != _idempotency_payload(record):
                    raise aimipay_error(
                        "idempotency_conflict",
                        message=f"idempotency_key conflict for existing payment: {concurrent.payment_id}",
                        details={"existing_payment_id": concurrent.payment_id},
                    ) from None
                return concurrent
        if _idempotency_payload(existing) != _idempotency_payload(record):
            raise aimipay_error(
                "idempotency_conflict",
                message=f"idempotency_key conflict for existing payment: {existing.payment_id}",
                details={"existing_payment_id": existing.payment_id},
            )
        return existing

    def acquire_processing_lock(
        self,
        payment_id: str,
        *,
        stage: str,
        token: str,
        ttl_s: int = 300,
    ) -> PaymentRecord | None:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT payload_json FROM micropay_payments WHERE payment_id = ?",
                (payment_id,),
            ).fetchone()
            if row is None:
                return None
            record = PaymentRecord(**json.loads(row[0]))
            if (
                record.processing_stage
                and record.processing_token != token
                and (record.processing_started_at or 0) + ttl_s > now
            ):
                conn.rollback()
                return None
            locked = _prepare_record(
                record.model_copy(
                    update={
                        "processing_stage": stage,
                        "processing_token": token,
                        "processing_started_at": now,
                    }
                ),
                existing=record,
            )
            conn.execute(
                """
                UPDATE micropay_payments
                SET status = ?, updated_at = ?, payload_json = ?
                WHERE payment_id = ?
                """,
                (
                    locked.status,
                    locked.updated_at,
                    json.dumps(locked.model_dump(mode="json"), sort_keys=True),
                    locked.payment_id,
                ),
            )
            conn.commit()
            return locked

    def claim_for_processing(
        self,
        *,
        statuses: Iterable[str],
        stage: str,
        token: str,
        ttl_s: int = 300,
        chain: str | None = None,
        limit: int | None = None,
    ) -> list[PaymentRecord]:
        status_values = list(statuses)
        now = int(time.time())
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            clauses = []
            params: list[object] = []
            if status_values:
                placeholders = ", ".join("?" for _ in status_values)
                clauses.append(f"status IN ({placeholders})")
                params.extend(status_values)
            if chain is not None:
                clauses.append("chain = ?")
                params.append(chain)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            query = f"""
                SELECT payload_json
                FROM micropay_payments
                {where}
                ORDER BY updated_at DESC, created_at DESC, payment_id DESC
            """
            rows = conn.execute(query, params).fetchall()
            claimed: list[PaymentRecord] = []
            for row in rows:
                record = PaymentRecord(**json.loads(row[0]))
                if (
                    record.processing_stage
                    and record.processing_token != token
                    and (record.processing_started_at or 0) + ttl_s > now
                ):
                    continue
                locked = _prepare_record(
                    record.model_copy(
                        update={
                            "processing_stage": stage,
                            "processing_token": token,
                            "processing_started_at": now,
                        }
                    ),
                    existing=record,
                )
                conn.execute(
                    """
                    UPDATE micropay_payments
                    SET status = ?, updated_at = ?, payload_json = ?
                    WHERE payment_id = ?
                    """,
                    (
                        locked.status,
                        locked.updated_at,
                        json.dumps(locked.model_dump(mode="json"), sort_keys=True),
                        locked.payment_id,
                    ),
                )
                claimed.append(locked)
                if limit is not None and len(claimed) >= limit:
                    break
            conn.commit()
            return claimed

    def list(
        self,
        *,
        status: str | None = None,
        chain: str | None = None,
        channel_id: str | None = None,
    ) -> list[PaymentRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if chain is not None:
            clauses.append("chain = ?")
            params.append(chain)
        if channel_id is not None:
            clauses.append("channel_id = ?")
            params.append(channel_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT payload_json
            FROM micropay_payments
            {where}
            ORDER BY updated_at DESC, created_at DESC, payment_id DESC
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [PaymentRecord(**json.loads(row[0])) for row in rows]

    def recover(
        self,
        *,
        payment_id: str | None = None,
        idempotency_key: str | None = None,
        channel_id: str | None = None,
        statuses: Iterable[str] | None = None,
    ) -> list[PaymentRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if payment_id is not None:
            clauses.append("payment_id = ?")
            params.append(payment_id)
        if idempotency_key is not None:
            clauses.append("idempotency_key = ?")
            params.append(idempotency_key)
        if channel_id is not None:
            clauses.append("channel_id = ?")
            params.append(channel_id)
        if statuses is not None:
            status_values = list(statuses)
            if status_values:
                placeholders = ", ".join("?" for _ in status_values)
                clauses.append(f"status IN ({placeholders})")
                params.extend(status_values)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT payload_json
            FROM micropay_payments
            {where}
            ORDER BY updated_at DESC, created_at DESC, payment_id DESC
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [PaymentRecord(**json.loads(row[0])) for row in rows]

    def _initialize(self) -> None:
        path = Path(self.sqlite_path)
        if path.parent != Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS micropay_payments (
                    payment_id TEXT PRIMARY KEY,
                    idempotency_key TEXT UNIQUE,
                    channel_id TEXT,
                    chain TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_micropay_payments_status ON micropay_payments(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_micropay_payments_channel ON micropay_payments(channel_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_micropay_payments_chain ON micropay_payments(chain)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.sqlite_path)


def _idempotency_payload(record: PaymentRecord) -> dict:
    payload = record.model_dump(mode="json")
    for key in (
        "payment_id",
        "status",
        "status_reason",
        "tx_id",
        "confirmation_status",
        "confirmation_error",
        "confirmation_attempts",
        "error_code",
        "error_message",
        "processing_stage",
        "processing_token",
        "processing_started_at",
        "created_at",
        "updated_at",
        "settled_at",
        "confirmed_at",
    ):
        payload.pop(key, None)
    return payload


def _prepare_record(record: PaymentRecord, *, existing: PaymentRecord | None) -> PaymentRecord:
    now = int(time.time())
    created_at = record.created_at or (None if existing is None else existing.created_at) or now
    updated_at = now
    return record.model_copy(
        update={
            "created_at": created_at,
            "updated_at": updated_at,
        }
    )

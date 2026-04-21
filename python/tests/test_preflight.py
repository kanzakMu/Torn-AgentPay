from __future__ import annotations

import os
from pathlib import Path

from ops_tools.preflight import build_gateway_config_from_env, build_preflight_report
from shared import PaymentRecord, SqlitePaymentStore


def test_preflight_can_build_report_with_snapshot_and_backup(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = tmp_path / "payments.db"
    backup_dir = tmp_path / "backups"
    snapshot_path = tmp_path / "snapshot.json"
    store = SqlitePaymentStore(sqlite_path)
    store.upsert(
        PaymentRecord(
            payment_id="pay_preflight_1",
            idempotency_key="idem_preflight_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_preflight_1",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=9_999_999_999,
            status="submitted",
        )
    )
    monkeypatch.setenv("AIMIPAY_REPOSITORY_ROOT", str(Path(__file__).resolve().parents[2]))
    monkeypatch.setenv("AIMIPAY_FULL_HOST", "http://127.0.0.1:9090")
    monkeypatch.setenv("AIMIPAY_SELLER_PRIVATE_KEY", "seller_private_key")
    monkeypatch.setenv("AIMIPAY_CHAIN_ID", "31337")
    monkeypatch.setenv("AIMIPAY_SETTLEMENT_BACKEND", "claim_script")
    monkeypatch.setenv("AIMIPAY_SQLITE_PATH", str(sqlite_path))

    config = build_gateway_config_from_env()
    report = build_preflight_report(
        config,
        backup_dir=backup_dir,
        snapshot_path=snapshot_path,
    )

    assert report["storage"]["backend"] == "sqlite"
    assert report["storage"]["payment_count"] == 1
    assert report["storage"]["status_counts"]["submitted"] == 1
    assert Path(report["storage"]["backup_path"]).exists()
    assert Path(report["storage"]["snapshot_path"]).exists()

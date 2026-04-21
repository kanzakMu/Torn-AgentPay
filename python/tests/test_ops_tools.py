from __future__ import annotations

from pathlib import Path

from ops_tools.network_profile_setup import apply_network_profile
from ops_tools.preflight import build_gateway_config_from_env
from ops_tools.target_dry_run import run_target_dry_run
from shared import PaymentRecord, SqlitePaymentStore


def test_build_gateway_config_from_env_can_load_explicit_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "target.env"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_REPOSITORY_ROOT=e:/trade/aimicropay-tron",
                "AIMIPAY_FULL_HOST=http://127.0.0.1:9090",
                "AIMIPAY_SETTLEMENT_BACKEND=local_smoke",
                "AIMIPAY_CHAIN_ID=31337",
                "AIMIPAY_SELLER_ADDRESS=TRX_SELLER_TARGET",
                "AIMIPAY_SELLER_PRIVATE_KEY=seller_private_key",
                "AIMIPAY_CONTRACT_ADDRESS=TRX_CONTRACT_TARGET",
                "AIMIPAY_TOKEN_ADDRESS=TRX_USDT_TARGET",
                f"AIMIPAY_SQLITE_PATH={tmp_path / 'payments.db'}",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("AIMIPAY_SELLER_ADDRESS", raising=False)

    config = build_gateway_config_from_env(env_file=env_file)

    assert config.seller_address == "TRX_SELLER_TARGET"
    assert config.sqlite_path == str(tmp_path / "payments.db")


def test_run_target_dry_run_generates_report_and_snapshot_restore(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "payments.db"
    store = SqlitePaymentStore(sqlite_path)
    store.upsert(
        PaymentRecord(
            payment_id="pay_target_1",
            idempotency_key="idem_target_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_target_1",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=9_999_999_999,
            status="authorized",
        )
    )
    env_file = tmp_path / "target.env"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_REPOSITORY_ROOT=e:/trade/aimicropay-tron",
                "AIMIPAY_FULL_HOST=http://127.0.0.1:9090",
                "AIMIPAY_SETTLEMENT_BACKEND=local_smoke",
                "AIMIPAY_CHAIN_ID=31337",
                "AIMIPAY_SELLER_ADDRESS=TRX_SELLER_TARGET",
                "AIMIPAY_SELLER_PRIVATE_KEY=seller_private_key",
                "AIMIPAY_CONTRACT_ADDRESS=TRX_CONTRACT_TARGET",
                "AIMIPAY_TOKEN_ADDRESS=TRX_USDT_TARGET",
                f"AIMIPAY_SQLITE_PATH={sqlite_path}",
            ]
        ),
        encoding="utf-8",
    )

    report = run_target_dry_run(
        output_dir=tmp_path / "dry-run",
        env_file=env_file,
        payment_count=12,
        worker_count=3,
        max_rounds=6,
        execute_delay_s=0.0,
        confirm_delay_s=0.0,
    )

    assert report["preflight"]["ok"] is True
    assert report["snapshot_restore"]["restored"] == 1
    assert report["drill"]["rounds"][-1]["unfinished"] == 0
    assert "aimipay_runtime_ok" in report["drill"]["prometheus_metrics"]


def test_apply_network_profile_sets_managed_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_REPOSITORY_ROOT=E:/trade/aimicropay-tron",
                "AIMIPAY_FULL_HOST=http://placeholder.local",
                "AIMIPAY_SELLER_ADDRESS=TRX_SELLER",
            ]
        ),
        encoding="utf-8",
    )

    report = apply_network_profile(env_file=env_file, profile_name="local", emit_output=False)
    updated = env_file.read_text(encoding="utf-8")

    assert report["profile"] == "local"
    assert "AIMIPAY_NETWORK_PROFILE=local" in updated
    assert "AIMIPAY_FULL_HOST=http://127.0.0.1:9090" in updated
    assert "AIMIPAY_SETTLEMENT_BACKEND=local_smoke" in updated
    assert "AIMIPAY_SELLER_ADDRESS=TRX_SELLER" in updated

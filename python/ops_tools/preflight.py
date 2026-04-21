from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from examples.env_loader import load_default_example_env, load_env_file
from seller import GatewayConfig, GatewaySettlementConfig, validate_runtime_config
from shared import SqlitePaymentStore

from .payment_store_tools import backup_sqlite_database, export_payment_snapshot


def build_gateway_config_from_env(*, env_file: str | Path | None = None) -> GatewayConfig:
    load_default_example_env()
    if env_file is not None:
        load_env_file(env_file, override=True)
    repository_root = os.environ.get("AIMIPAY_REPOSITORY_ROOT", "e:/trade/aimicropay-tron")
    full_host = os.environ.get("AIMIPAY_FULL_HOST", "http://127.0.0.1:9090")
    seller_private_key = os.environ.get("AIMIPAY_SELLER_PRIVATE_KEY", "")
    seller_address = os.environ.get("AIMIPAY_SELLER_ADDRESS", "TRX_SELLER")
    contract_address = os.environ.get("AIMIPAY_CONTRACT_ADDRESS", "TRX_CONTRACT")
    token_address = os.environ.get("AIMIPAY_TOKEN_ADDRESS", "TRX_USDT")
    chain_id = int(os.environ.get("AIMIPAY_CHAIN_ID", "31337"))
    executor_backend = os.environ.get("AIMIPAY_SETTLEMENT_BACKEND", "claim_script")
    sqlite_path = os.environ.get("AIMIPAY_SQLITE_PATH")
    return GatewayConfig(
        service_name=os.environ.get("AIMIPAY_SERVICE_NAME", "Research Copilot"),
        service_description=os.environ.get("AIMIPAY_SERVICE_DESCRIPTION", "Pay-per-use research and market data"),
        seller_address=seller_address,
        contract_address=contract_address,
        token_address=token_address,
        chain_id=chain_id,
        settlement=GatewaySettlementConfig(
            repository_root=repository_root,
            full_host=full_host,
            seller_private_key=seller_private_key,
            chain_id=chain_id,
            executor_backend=executor_backend,
        ),
        sqlite_path=sqlite_path,
    )


def build_preflight_report(
    config: GatewayConfig,
    *,
    backup_dir: str | Path | None = None,
    snapshot_path: str | Path | None = None,
) -> dict[str, Any]:
    validation = validate_runtime_config(config)
    storage: dict[str, Any] = {
        "backend": "sqlite" if config.sqlite_path else "memory",
        "sqlite_path": config.sqlite_path,
    }
    if config.sqlite_path:
        sqlite_file = Path(config.sqlite_path)
        storage["sqlite_exists"] = sqlite_file.exists()
        storage["sqlite_size_bytes"] = sqlite_file.stat().st_size if sqlite_file.exists() else None
        if sqlite_file.exists():
            store = SqlitePaymentStore(sqlite_file)
            records = store.recover()
            storage["payment_count"] = len(records)
            storage["status_counts"] = _status_counts(records)
            if backup_dir is not None:
                storage["backup_path"] = str(
                    backup_sqlite_database(sqlite_file, backup_dir=backup_dir, label="aimipay-payments")
                )
            if snapshot_path is not None:
                export_payment_snapshot(store, snapshot_path)
                storage["snapshot_path"] = str(Path(snapshot_path))
    report = {
        "ok": bool(validation["ok"]),
        "service_name": config.service_name,
        "network": config.network,
        "settlement_backend": None if config.settlement is None else config.settlement.executor_backend,
        "environment": {
            "repository_root": None if config.settlement is None else config.settlement.repository_root,
            "sqlite_path": config.sqlite_path,
            "chain_id": config.primary_chain().chain_id,
            "seller_address": config.seller_address,
            "contract_address": config.contract_address,
            "token_address": config.token_address,
        },
        "validation": validation,
        "storage": storage,
    }
    return report


def _status_counts(records: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        status = str(getattr(record, "status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts

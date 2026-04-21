from __future__ import annotations

import json
import os
from pathlib import Path

from buyer import BuyerWallet, MarketSelectionPolicy, install_agent_payments
from buyer.provisioner import build_default_tron_provisioner

from .env_loader import load_default_example_env


def build_runtime():
    load_default_example_env()
    repository_root = os.environ.get(
        "AIMIPAY_REPOSITORY_ROOT",
        str(Path(__file__).resolve().parents[2]),
    )
    full_host = os.environ.get("AIMIPAY_FULL_HOST")
    buyer_address = os.environ.get("AIMIPAY_BUYER_ADDRESS", "TRX_BUYER")
    buyer_private_key = os.environ.get("AIMIPAY_BUYER_PRIVATE_KEY", "buyer_private_key")
    merchant_urls = [
        value.strip()
        for value in os.environ.get("AIMIPAY_MERCHANT_URLS", "http://127.0.0.1:8000").split(",")
        if value.strip()
    ]
    return install_agent_payments(
        full_host=full_host,
        wallet=BuyerWallet(address=buyer_address, private_key=buyer_private_key),
        provisioner=build_default_tron_provisioner(repository_root=repository_root),
        repository_root=repository_root,
        merchant_base_urls=merchant_urls,
        selection_policy=MarketSelectionPolicy(
            policy_name="balanced",
            price_weight=1.0,
            settlement_backend_weight=1.2,
            delivery_mode_weight=0.8,
            auth_complexity_weight=0.5,
        ),
    ).enable_auto_wallet().enable_auto_purchase()


def demo_purchase_plan() -> dict:
    runtime = build_runtime()
    return runtime.pay_for_task(
        task_context="Need paid web search to finish a coding task",
        capability_type="web_search",
        request_body='{"query":"best tron tooling"}',
        expected_units=3,
        budget_limit_atomic=900_000,
    )


def main() -> None:
    payload = demo_purchase_plan()
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

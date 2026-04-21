from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPOSITORY_ROOT / "python"
for candidate in (str(REPOSITORY_ROOT), str(PYTHON_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from examples.env_loader import load_default_example_env
from seller import GatewaySettlementConfig, install_sellable_capability


load_default_example_env()

app = FastAPI(title="AimiPay Sample Merchant")
runtime = install_sellable_capability(
    app,
    service_name="Sample Merchant",
    service_description="Minimal sellable capability sample",
    seller_address="TRX_SELLER",
    contract_address="TRX_CONTRACT",
    token_address="TRX_USDT",
    settlement=GatewaySettlementConfig(
        repository_root="e:/trade/aimicropay-tron",
        full_host="http://127.0.0.1:9090",
        seller_private_key="seller_private_key",
        chain_id=31337,
        executor_backend="local_smoke",
    ),
)
runtime.publish_api(
    path="/tools/research",
    price_atomic=250_000,
    capability_type="web_search",
    description="Minimal sample merchant route",
)

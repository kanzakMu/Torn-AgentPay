from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPOSITORY_ROOT / "python"
for candidate in (str(REPOSITORY_ROOT), str(PYTHON_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from examples.env_loader import load_default_example_env
from examples.local_end_to_end_demo import LocalDemoProvisioner
from buyer import BuyerWallet, install_agent_payments


load_default_example_env()


def main() -> None:
    runtime = install_agent_payments(
        full_host="http://127.0.0.1:9090",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="buyer_private_key",
        ),
        provisioner=LocalDemoProvisioner(
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
        ),
        merchant_base_url="http://127.0.0.1:8000",
    ).enable_auto_wallet().enable_auto_purchase()
    payload = runtime.pay_for_task(
        task_context="Sample project paid web search",
        capability_type="web_search",
        request_body='{"query":"sample project"}',
        expected_units=3,
        budget_limit_atomic=900_000,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

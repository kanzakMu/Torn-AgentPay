from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import tempfile

import httpx

if __package__ in {None, ""}:
    from pathing import ensure_repo_python_paths
else:
    from .pathing import ensure_repo_python_paths

REPOSITORY_ROOT, PYTHON_DIR = ensure_repo_python_paths(current_file=__file__)

from buyer import BuyerWallet, install_agent_payments
from buyer.provisioner import OpenChannelExecution

if __package__ in {None, ""}:
    from env_loader import load_default_example_env
else:
    from .env_loader import load_default_example_env


HARDHAT_BUYER_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
HARDHAT_SELLER_ADDRESS = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"


@dataclass(slots=True)
class LocalDemoProvisioner:
    contract_address: str
    token_address: str

    def provision(self, plan) -> OpenChannelExecution:
        # Local demo uses the seller local-smoke settlement backend, so buyer
        # only needs a consistent off-chain session shape here.
        return OpenChannelExecution(
            approve_tx_id="local_demo_approve",
            open_tx_id="local_demo_open",
            buyer_address=HARDHAT_BUYER_ADDRESS,
            seller_address=plan.seller_address,
            token_address=plan.token_address,
            channel_id="local_demo_channel",
            contract_address=plan.contract_address,
            deposit_atomic=plan.deposit_atomic,
            expires_at=plan.expires_at,
        )


def build_local_demo_runtime(*, merchant_base_url: str, repository_root: str):
    load_default_example_env(start_dir=repository_root)
    return install_agent_payments(
        full_host="http://127.0.0.1:9090",
        wallet=BuyerWallet(
            address=os.environ.get("AIMIPAY_BUYER_ADDRESS", HARDHAT_BUYER_ADDRESS),
            private_key=os.environ.get("AIMIPAY_BUYER_PRIVATE_KEY", "buyer_private_key"),
        ),
        provisioner=LocalDemoProvisioner(
            contract_address=os.environ.get("AIMIPAY_CONTRACT_ADDRESS", "TRX_CONTRACT"),
            token_address=os.environ.get("AIMIPAY_TOKEN_ADDRESS", "TRX_USDT"),
        ),
        repository_root=repository_root,
        merchant_base_urls=[merchant_base_url],
    ).enable_auto_wallet().enable_auto_purchase()


def run_local_demo(*, merchant_base_url: str, repository_root: str) -> dict:
    runtime = build_local_demo_runtime(
        merchant_base_url=merchant_base_url,
        repository_root=repository_root,
    )
    return runtime.pay_for_task(
        task_context="Need a local paid web search demo flow",
        capability_type="web_search",
        request_body='{"query":"local demo"}',
        expected_units=3,
        budget_limit_atomic=900_000,
    )


def main() -> None:
    load_default_example_env()
    repository_root = os.environ.get("AIMIPAY_REPOSITORY_ROOT", str(REPOSITORY_ROOT))
    merchant_port = int(os.environ.get("AIMIPAY_MERCHANT_PORT", "8000"))
    merchant_base_url = f"http://127.0.0.1:{merchant_port}"

    with _merchant_demo_server(repository_root=repository_root, merchant_port=merchant_port):
        payload = run_local_demo(
            merchant_base_url=merchant_base_url,
            repository_root=repository_root,
        )
    print(format_demo_summary(payload))
    print(json.dumps(payload, indent=2, ensure_ascii=True))


@contextmanager
def _merchant_demo_server(*, repository_root: str, merchant_port: int):
    env = os.environ.copy()
    env.setdefault("AIMIPAY_REPOSITORY_ROOT", repository_root)
    env.setdefault("AIMIPAY_FULL_HOST", "http://127.0.0.1:9090")
    env.setdefault("AIMIPAY_SETTLEMENT_BACKEND", "local_smoke")
    env.setdefault("AIMIPAY_CHAIN_ID", "31337")
    env.setdefault("AIMIPAY_SELLER_ADDRESS", HARDHAT_SELLER_ADDRESS)
    env.setdefault("AIMIPAY_CONTRACT_ADDRESS", "TRX_CONTRACT")
    env.setdefault("AIMIPAY_TOKEN_ADDRESS", "TRX_USDT")
    env["NO_PROXY"] = env.get("NO_PROXY", "127.0.0.1,localhost")
    env["no_proxy"] = env.get("no_proxy", env["NO_PROXY"])
    with tempfile.TemporaryDirectory(prefix="aimipay-local-demo-") as temp_dir:
        env["AIMIPAY_MERCHANT_CONFIG_PATH"] = str(Path(temp_dir) / "merchant-config.json")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "python.examples.merchant_app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(merchant_port),
            ],
            cwd=repository_root,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            _wait_for_merchant(f"http://127.0.0.1:{merchant_port}/.well-known/aimipay.json")
            yield
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def _wait_for_merchant(url: str, timeout_s: float = 15.0) -> None:
    deadline = time.time() + timeout_s
    with httpx.Client(timeout=1.0, trust_env=False) as client:
        while time.time() < deadline:
            try:
                response = client.get(url)
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
    raise RuntimeError(f"merchant demo did not become healthy in time: {url}")


def format_demo_summary(payload: dict) -> str:
    selection = payload.get("selection", {})
    selected = selection.get("selected", {})
    offer = payload.get("offer", {})
    budget = payload.get("budget", {})
    payment = payload.get("payment", {})
    lines = [
        "AimiPay Local Demo Summary",
        f"- selected merchant: {selected.get('offer', {}).get('merchant_base_url', 'n/a')}",
        f"- capability: {offer.get('capability_id', 'n/a')}",
        f"- route: {offer.get('route_path', 'n/a')}",
        f"- estimated total atomic: {budget.get('estimated_total_atomic', 'n/a')}",
        f"- payment status: {payment.get('status', 'n/a')}",
        f"- tx id: {payment.get('tx_id', 'n/a')}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()

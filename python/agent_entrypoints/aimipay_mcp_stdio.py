from __future__ import annotations

import os
from pathlib import Path

from buyer import AimiPayMcpServer, BuyerWallet, install_agent_payments
from buyer.provisioner import build_default_tron_provisioner
from examples.env_loader import load_env_file
from ops_tools.agent_onboarding import run_agent_onboarding


def build_server() -> AimiPayMcpServer:
    repository_root = os.environ.get("AIMIPAY_REPOSITORY_ROOT", "e:/trade/aimicropay-tron")
    onboarding = run_agent_onboarding(
        repository_root=repository_root,
        env_file=Path(repository_root) / "python" / ".env.local",
        wallet_file=Path(repository_root) / "python" / ".wallets" / "buyer-wallet.json",
        output_json=False,
        emit_output=False,
    )
    load_env_file(Path(repository_root) / "python" / ".env.local", override=True)
    full_host = os.environ.get("AIMIPAY_FULL_HOST")
    merchant_urls = [
        value.strip()
        for value in os.environ.get("AIMIPAY_MERCHANT_URLS", "http://127.0.0.1:8000").split(",")
        if value.strip()
    ]
    runtime = install_agent_payments(
        full_host=full_host,
        wallet=BuyerWallet(
            address=os.environ.get("AIMIPAY_BUYER_ADDRESS", "TRX_BUYER"),
            private_key=os.environ.get("AIMIPAY_BUYER_PRIVATE_KEY", "buyer_private_key"),
        ),
        provisioner=build_default_tron_provisioner(repository_root=repository_root),
        repository_root=repository_root,
        merchant_base_urls=merchant_urls,
    ).enable_auto_wallet().enable_auto_purchase()
    return AimiPayMcpServer(runtime, startup_onboarding=onboarding)


def main() -> None:
    build_server().serve_stdio()


if __name__ == "__main__":
    main()

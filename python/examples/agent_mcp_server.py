from __future__ import annotations

if __package__ in {None, ""}:
    from pathing import ensure_repo_python_paths
else:
    from .pathing import ensure_repo_python_paths

ensure_repo_python_paths(current_file=__file__)

if __package__ in {None, ""}:
    from env_loader import load_default_example_env
    from local_end_to_end_demo import LocalDemoProvisioner
else:
    from .env_loader import load_default_example_env
    from .local_end_to_end_demo import LocalDemoProvisioner
from buyer import AimiPayMcpServer, BuyerWallet, install_agent_payments


load_default_example_env()


def build_server() -> AimiPayMcpServer:
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
    return AimiPayMcpServer(runtime)


def main() -> None:
    build_server().serve_stdio()


if __name__ == "__main__":
    main()

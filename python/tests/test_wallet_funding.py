from pathlib import Path

from ops_tools.wallet_setup import ensure_local_buyer_wallet
from ops_tools.wallet_funding import inspect_wallet_funding


def test_wallet_funding_reports_local_smoke_guidance_without_live_probe(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    env_file = python_dir / ".env.local"
    env_file.write_text(
        "AIMIPAY_SETTLEMENT_BACKEND=local_smoke\nAIMIPAY_FULL_HOST=http://127.0.0.1:9090\nAIMIPAY_TOKEN_ADDRESS=TRX_USDT\n",
        encoding="utf-8",
    )
    ensure_local_buyer_wallet(repository_root=repo_root, env_file=env_file)

    report = inspect_wallet_funding(repository_root=repo_root, env_file=env_file, output_json=False)

    assert report["wallet_ready"] is True
    assert report["settlement_backend"] == "local_smoke"
    assert report["funding_probe"] is None
    assert any("local_smoke demo" in step for step in report["guidance"])
    assert any("run the local demo" in step for step in report["checklist"])


def test_wallet_funding_reports_missing_wallet_guidance(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    env_file = python_dir / ".env.local"
    env_file.write_text(
        "AIMIPAY_BUYER_ADDRESS=TRX_BUYER\nAIMIPAY_BUYER_PRIVATE_KEY=buyer_private_key\n",
        encoding="utf-8",
    )

    report = inspect_wallet_funding(repository_root=repo_root, env_file=env_file, output_json=False)

    assert report["wallet_ready"] is False
    assert report["guidance"][0].startswith("create a buyer wallet first")


def test_wallet_funding_uses_configured_network_metadata_on_live_backend(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    env_file = python_dir / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_SETTLEMENT_BACKEND=claim_script",
                "AIMIPAY_FULL_HOST=https://nile.trongrid.io",
                "AIMIPAY_TOKEN_ADDRESS=TXYZTOKEN",
                "AIMIPAY_NETWORK_NAME=tron-nile",
                "AIMIPAY_FAUCET_URL=https://example.test/faucet",
                "AIMIPAY_FUNDING_GUIDE_URL=https://example.test/guide",
                "AIMIPAY_MIN_TRX_BALANCE_SUN=2000000",
                "AIMIPAY_MIN_TOKEN_BALANCE_ATOMIC=3000000",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    from ops_tools.wallet_setup import ensure_local_buyer_wallet

    ensure_local_buyer_wallet(repository_root=repo_root, env_file=env_file)

    monkeypatch.setattr(
        "ops_tools.wallet_funding._probe_wallet_funding",
        lambda **kwargs: {
            "status": "ok",
            "trx_balance_sun": 1,
            "token_balance_atomic": 2,
            "has_trx_for_gas": True,
            "has_token_balance": True,
            "meets_min_trx_balance": False,
            "meets_min_token_balance": False,
            "token_probe_status": "ok",
        },
    )

    report = inspect_wallet_funding(repository_root=repo_root, env_file=env_file, output_json=False)

    assert report["network_name"] == "tron-nile"
    assert report["minimums"]["trx_balance_sun"] == 2_000_000
    assert report["faucet_url"] == "https://example.test/faucet"
    assert any("testnet faucet" in step for step in report["guidance"])
    assert any("follow the funding guide" in step for step in report["checklist"])


def test_wallet_funding_reports_merchant_driven_mode_when_rpc_is_unset(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    env_file = python_dir / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_MERCHANT_URLS=https://merchant.example",
                "AIMIPAY_FULL_HOST=",
                "AIMIPAY_SETTLEMENT_BACKEND=",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    ensure_local_buyer_wallet(repository_root=repo_root, env_file=env_file)

    report = inspect_wallet_funding(repository_root=repo_root, env_file=env_file, output_json=False)

    assert report["host_action"]["action"] == "connect_merchant"
    assert any("merchant-driven network mode" in step for step in report["guidance"])
    assert any("discover the merchant first" in step for step in report["checklist"])

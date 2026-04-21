import json
from pathlib import Path

from buyer.wallet import BuyerWallet
from ops_tools.install_doctor import build_install_report
from ops_tools.wallet_setup import ensure_local_buyer_wallet


def test_create_tron_wallet_and_save_locally(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    wallet_file = tmp_path / ".wallets" / "buyer-wallet.json"

    wallet = BuyerWallet.create_tron_wallet()
    saved = wallet.save_wallet_locally(env_file=env_file, wallet_file=wallet_file)

    assert wallet.address.startswith("T")
    assert wallet.private_key.startswith("0x")
    assert wallet.matches_private_key() is True
    assert Path(saved["env_file"]).exists()
    assert Path(saved["wallet_file"]).exists()
    env_text = env_file.read_text(encoding="utf-8")
    assert "AIMIPAY_BUYER_ADDRESS=" in env_text
    assert "AIMIPAY_BUYER_PRIVATE_KEY=" in env_text
    payload = json.loads(wallet_file.read_text(encoding="utf-8"))
    assert payload["address"] == wallet.address
    assert payload["address_hex"] == wallet.hex_address


def test_ensure_local_buyer_wallet_creates_wallet_when_env_has_placeholder(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    env_file = python_dir / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_BUYER_ADDRESS=TRX_BUYER",
                "AIMIPAY_BUYER_PRIVATE_KEY=buyer_private_key",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    report = ensure_local_buyer_wallet(repository_root=repo_root, env_file=env_file)

    assert report["wallet_created"] is True
    assert report["buyer_address"].startswith("T")
    assert report["wallet_matches_private_key"] is True
    assert BuyerWallet.env_has_configured_wallet(env_file) is True


def test_install_doctor_reports_wallet_missing_until_wallet_is_configured(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    (repo_root / "package.json").write_text("{}", encoding="utf-8")
    (python_dir / "requirements.txt").write_text("httpx\n", encoding="utf-8")
    (python_dir / ".env.local.example").write_text("", encoding="utf-8")
    (python_dir / "target.env").write_text("", encoding="utf-8")
    (python_dir / ".env.local").write_text(
        "AIMIPAY_BUYER_ADDRESS=TRX_BUYER\nAIMIPAY_BUYER_PRIVATE_KEY=buyer_private_key\n",
        encoding="utf-8",
    )

    report_before = build_install_report(repository_root=repo_root)
    wallet_check_before = next(item for item in report_before["checks"] if item["name"] == "buyer_wallet_configured")
    assert wallet_check_before["ok"] is False

    ensure_local_buyer_wallet(repository_root=repo_root, env_file=python_dir / ".env.local")
    report_after = build_install_report(repository_root=repo_root)
    wallet_check_after = next(item for item in report_after["checks"] if item["name"] == "buyer_wallet_configured")
    assert wallet_check_after["ok"] is True

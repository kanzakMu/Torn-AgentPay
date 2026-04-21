from __future__ import annotations

import json
from pathlib import Path

from ops_tools.merchant_doctor import build_merchant_install_report, format_merchant_install_report_markdown
from ops_tools.merchant_setup import ensure_merchant_install
from shared.network_profiles import parse_env_file


def test_merchant_setup_creates_env_and_public_config(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    merchant_dist = repo_root / "merchant-dist" / "website"
    python_dir.mkdir(parents=True)
    merchant_dist.mkdir(parents=True)

    template = python_dir / ".env.merchant.example"
    template.write_text(
        "\n".join(
            [
                "AIMIPAY_REPOSITORY_ROOT=E:/trade/aimicropay-tron",
                "AIMIPAY_PUBLIC_BASE_URL=http://127.0.0.1:8123",
                "AIMIPAY_MERCHANT_PORT=8123",
                "AIMIPAY_SERVICE_NAME=Merchant Test",
                "AIMIPAY_SERVICE_DESCRIPTION=Starter merchant",
                "AIMIPAY_BRAND_ACCENT_COLOR=#123456",
                "AIMIPAY_SUPPORT_EMAIL=merchant@example.com",
            ]
        ),
        encoding="utf-8",
    )

    report = ensure_merchant_install(repository_root=repo_root)

    env_file = Path(report["env_file"])
    public_config = Path(report["public_config_path"])
    payload = json.loads(public_config.read_text(encoding="utf-8"))

    assert env_file.exists()
    assert public_config.exists()
    assert payload["merchant_base_url"] == "http://127.0.0.1:8123"
    assert payload["service_name"] == "Merchant Test"
    assert payload["brand"]["accent_color"] == "#123456"
    assert payload["brand"]["support_email"] == "merchant@example.com"


def test_merchant_doctor_markdown_is_readable(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    examples_dir = python_dir / "examples"
    merchant_site = repo_root / "merchant-dist" / "website" / ".generated"
    examples_dir.mkdir(parents=True)
    merchant_site.mkdir(parents=True)
    (repo_root / ".venv" / "Scripts").mkdir(parents=True)
    (repo_root / "node_modules").mkdir(parents=True)
    (repo_root / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
    (examples_dir / "merchant_app.py").write_text("app = None\n", encoding="utf-8")
    (python_dir / ".env.merchant.example").write_text("", encoding="utf-8")
    (python_dir / ".env.merchant.local").write_text(
        "\n".join(
            [
                "AIMIPAY_SELLER_ADDRESS=TRX_SELLER",
                "AIMIPAY_SELLER_PRIVATE_KEY=seller_private_key",
                "AIMIPAY_PUBLIC_BASE_URL=http://127.0.0.1:8000",
                "AIMIPAY_SERVICE_NAME=Merchant",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / "merchant-dist" / "website" / "aimipay.checkout.js").write_text("// ok\n", encoding="utf-8")
    (repo_root / "merchant-dist" / "website" / "embed.checkout.html").write_text("<html></html>\n", encoding="utf-8")
    (merchant_site / "merchant.public.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("AIMIPAY_SELLER_ADDRESS", "TRX_SELLER")
    monkeypatch.setenv("AIMIPAY_SELLER_PRIVATE_KEY", "seller_private_key")
    monkeypatch.setenv("AIMIPAY_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("AIMIPAY_SERVICE_NAME", "Merchant")

    report = build_merchant_install_report(repository_root=repo_root)
    markdown = format_merchant_install_report_markdown(report)

    assert report["bootstrap_ready"] is True
    assert "# AimiPay Merchant Install Doctor" in markdown
    assert "| `seller_private_key_present` | `ok` | `configured` |" in markdown


def test_merchant_setup_applies_requested_network_profile(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    merchant_dist = repo_root / "merchant-dist" / "website"
    python_dir.mkdir(parents=True)
    merchant_dist.mkdir(parents=True)

    template = python_dir / ".env.merchant.example"
    template.write_text(
        "\n".join(
            [
                "AIMIPAY_REPOSITORY_ROOT=E:/trade/aimicropay-tron",
                "AIMIPAY_PUBLIC_BASE_URL=http://127.0.0.1:8123",
                "AIMIPAY_MERCHANT_PORT=8123",
                "AIMIPAY_SERVICE_NAME=Merchant Test",
            ]
        ),
        encoding="utf-8",
    )

    report = ensure_merchant_install(repository_root=repo_root, network_profile="nile")
    values = parse_env_file(report["env_file"])

    assert report["network_profile"] == "nile"
    assert report["network_profile_ready"] is True
    assert values["AIMIPAY_NETWORK_PROFILE"] == "nile"
    assert values["AIMIPAY_FULL_HOST"] == "https://nile.trongrid.io"
    assert values["AIMIPAY_CONTRACT_ADDRESS"] == "41f21d7e3bab38a0c91a2c65ccc2e3e766a4463d24"

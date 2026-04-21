from pathlib import Path

from ops_tools.buyer_setup import prepare_buyer_install_env
from shared.network_profiles import parse_env_file


def test_prepare_buyer_install_env_prefers_merchant_urls_and_optional_profile(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    env_file = python_dir / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_REPOSITORY_ROOT=E:/trade/aimicropay-tron",
                "AIMIPAY_NETWORK_PROFILE=custom",
                "AIMIPAY_FULL_HOST=",
                "AIMIPAY_MERCHANT_URLS=http://old-merchant.test",
            ]
        ),
        encoding="utf-8",
    )

    report = prepare_buyer_install_env(
        repository_root=repo_root,
        env_file=env_file,
        merchant_urls=["https://merchant-a.example", "https://merchant-b.example"],
    )
    values = parse_env_file(env_file)

    assert report["merchant_urls"] == ["https://merchant-a.example", "https://merchant-b.example"]
    assert values["AIMIPAY_MERCHANT_URLS"] == "https://merchant-a.example,https://merchant-b.example"
    assert values["AIMIPAY_FULL_HOST"] == ""
    assert values["AIMIPAY_NETWORK_PROFILE"] == "custom"


def test_prepare_buyer_install_env_can_apply_local_profile(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    python_dir.mkdir(parents=True)
    env_file = python_dir / ".env.local"
    env_file.write_text("AIMIPAY_REPOSITORY_ROOT=E:/trade/aimicropay-tron\n", encoding="utf-8")

    report = prepare_buyer_install_env(
        repository_root=repo_root,
        env_file=env_file,
        merchant_urls=["http://127.0.0.1:8000"],
        network_profile="local",
    )
    values = parse_env_file(env_file)

    assert report["network_profile"] == "local"
    assert values["AIMIPAY_FULL_HOST"] == "http://127.0.0.1:9090"
    assert values["AIMIPAY_SETTLEMENT_BACKEND"] == "local_smoke"

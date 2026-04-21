from fastapi.testclient import TestClient

from python.examples.env_loader import load_default_example_env
from python.examples.agent_mcp_server import build_server
from python.examples.agent_runtime_demo import build_runtime
from python.examples.buyer_onboarding_app import create_app as create_buyer_onboarding_app
from python.examples.easy_setup_app import create_app as create_easy_setup_app
from python.examples.local_end_to_end_demo import build_local_demo_runtime, format_demo_summary
from python.examples.offchain_stress_drill import format_drill_summary, run_offchain_stress_drill
from python.examples.merchant_app import create_app
from python.examples.render_claude_startup_card_demo import render_claude_startup_card_demo


def test_example_merchant_app_builds_fastapi_app() -> None:
    app = create_app()

    assert app.title == "Research Copilot"


def test_example_merchant_app_exposes_install_dashboard() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/aimipay/install")

    assert response.status_code == 200
    assert "Torn-AgentPay Seller Console" in response.text
    assert "/aimipay/assets/dashboard/install_dashboard.js" in response.text


def test_example_merchant_app_persists_route_plan_and_branding(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "merchant-config.json"
    public_base = "http://127.0.0.1:8123"
    monkeypatch.setenv("AIMIPAY_MERCHANT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("AIMIPAY_PUBLIC_BASE_URL", public_base)

    app = create_app()
    client = TestClient(app)

    route_response = client.post(
        "/aimipay/install/config/route",
        json={
            "path": "/tools/translate",
            "method": "POST",
            "price_atomic": 333000,
            "capability_type": "translation",
            "description": "Paid translation route",
        },
    )
    plan_response = client.post(
        "/aimipay/install/config/plan",
        json={
            "plan_id": "starter",
            "name": "Starter",
            "amount_atomic": 1230000,
            "subscribe_path": "/billing/starter",
        },
    )
    branding_response = client.post(
        "/aimipay/install/config/branding",
        json={
            "service_name": "Merchant Console",
            "display_title": "Pay with Merchant Console",
            "accent_color": "#2255aa",
            "support_email": "ops@example.com",
        },
    )

    assert route_response.status_code == 200
    assert plan_response.status_code == 200
    assert branding_response.status_code == 200

    config_response = client.get("/aimipay/install/config")
    manifest_response = client.get("/.well-known/aimipay.json")

    assert config_response.status_code == 200
    assert manifest_response.status_code == 200
    assert any(item["path"] == "/tools/translate" for item in config_response.json()["routes"])
    assert any(item["plan_id"] == "starter" for item in config_response.json()["plans"])
    assert config_response.json()["brand"]["accent_color"] == "#2255aa"
    assert manifest_response.json()["service_name"] == "Merchant Console"
    assert config_path.exists()
    assert all(item.get("enabled", True) for item in config_response.json()["routes"])


def test_example_merchant_app_supports_delete_and_rollback(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "merchant-config.json"
    monkeypatch.setenv("AIMIPAY_MERCHANT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("AIMIPAY_PUBLIC_BASE_URL", "http://127.0.0.1:8124")

    app = create_app()
    client = TestClient(app)

    client.post(
        "/aimipay/install/config/route",
        json={
            "path": "/tools/delete-me",
            "method": "POST",
            "price_atomic": 111000,
            "capability_type": "cleanup",
            "description": "Delete me",
        },
    )
    client.post(
        "/aimipay/install/config/plan",
        json={
            "plan_id": "temp-plan",
            "name": "Temp Plan",
            "amount_atomic": 555000,
            "subscribe_path": "/billing/temp",
        },
    )

    delete_route = client.request(
        "DELETE",
        "/aimipay/install/config/route",
        json={"path": "/tools/delete-me", "method": "POST"},
    )
    delete_plan = client.request("DELETE", "/aimipay/install/config/plan/temp-plan")
    history = client.get("/aimipay/install/config/history").json()

    assert delete_route.status_code == 200
    assert delete_plan.status_code == 200
    assert history["versions"]

    rollback_revision = next(
        item["revision"]
        for item in history["versions"]
        if any(route["path"] == "/tools/delete-me" for route in item["config"]["routes"])
        and any(plan["plan_id"] == "temp-plan" for plan in item["config"]["plans"])
    )
    rollback_response = client.post(f"/aimipay/install/config/rollback/{rollback_revision}", json={})
    config_response = client.get("/aimipay/install/config")

    assert rollback_response.status_code == 200
    assert any(item["path"] == "/tools/delete-me" for item in config_response.json()["routes"])
    assert any(item["plan_id"] == "temp-plan" for item in config_response.json()["plans"])


def test_example_merchant_app_supports_toggle_and_diff_preview(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "merchant-config.json"
    monkeypatch.setenv("AIMIPAY_MERCHANT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("AIMIPAY_PUBLIC_BASE_URL", "http://127.0.0.1:8126")

    app = create_app()
    client = TestClient(app)

    route_toggle = client.post(
        "/aimipay/install/config/route/toggle",
        json={"path": "/tools/research", "method": "POST", "enabled": False},
    )
    plan_toggle = client.post("/aimipay/install/config/plan/pro-monthly/toggle", json={"enabled": False})
    manifest = client.get("/.well-known/aimipay.json").json()
    history = client.get("/aimipay/install/config/history").json()["versions"]
    diff = client.get(f"/aimipay/install/config/history/{history[0]['revision']}/diff").json()

    assert route_toggle.status_code == 200
    assert plan_toggle.status_code == 200
    assert all(item["path"] != "/tools/research" for item in manifest["routes"])
    assert all(item["plan_id"] != "pro-monthly" for item in manifest["plans"])
    assert "diff" in diff
    health = client.get("/aimipay/demo/health")
    assert health.status_code == 200
    missing_diff = client.get("/aimipay/install/config/history/9999/diff")
    assert missing_diff.status_code == 404


def test_example_merchant_app_uses_isolated_demo_config(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "merchant-config.json"
    monkeypatch.setenv("AIMIPAY_MERCHANT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("AIMIPAY_PUBLIC_BASE_URL", "http://127.0.0.1:8127")

    app = create_app()
    client = TestClient(app)

    response = client.get("/aimipay/install/config")

    assert response.status_code == 200
    assert any(item["path"] == "/tools/research" for item in response.json()["routes"])
    assert response.json()["runtime"]["network_profile"]
    assert response.json()["runtime"]["contract_address"]


def test_example_merchant_app_returns_runtime_profile_metadata(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "merchant-config.json"
    monkeypatch.setenv("AIMIPAY_MERCHANT_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("AIMIPAY_PUBLIC_BASE_URL", "http://127.0.0.1:8128")
    monkeypatch.setenv("AIMIPAY_NETWORK_PROFILE", "nile")
    monkeypatch.setenv("AIMIPAY_NETWORK_NAME", "tron-nile")
    monkeypatch.setenv("AIMIPAY_FULL_HOST", "https://nile.trongrid.io")
    monkeypatch.setenv("AIMIPAY_CONTRACT_ADDRESS", "TRX_CONTRACT_TEST")
    monkeypatch.setenv("AIMIPAY_TOKEN_ADDRESS", "TRX_USDT_TEST")

    app = create_app()
    client = TestClient(app)

    response = client.get("/aimipay/install/config")
    runtime = response.json()["runtime"]

    assert response.status_code == 200
    assert runtime["network_profile"] == "nile"
    assert runtime["network_name"] == "tron-nile"
    assert runtime["resolved_chain_rpc"] == "https://nile.trongrid.io"
    assert runtime["contract_address"] == "TRX_CONTRACT_TEST"
    assert runtime["token_address"] == "TRX_USDT_TEST"


def test_example_agent_runtime_builds_runtime() -> None:
    runtime = build_runtime()

    assert runtime.default_merchant_base_url is None
    assert runtime.merchant_base_urls


def test_example_agent_mcp_server_builds_server() -> None:
    server = build_server()

    assert server.list_tools()


def test_example_buyer_onboarding_app_can_update_merchant_url(tmp_path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    python_dir = repo_root / "python"
    wallets_dir = python_dir / ".wallets"
    agent_dir = python_dir / ".agent"
    python_dir.mkdir(parents=True)
    wallets_dir.mkdir(parents=True)
    agent_dir.mkdir(parents=True)
    (repo_root / "package.json").write_text("{}", encoding="utf-8")
    (python_dir / "requirements.txt").write_text("httpx\n", encoding="utf-8")
    (python_dir / ".env.local.example").write_text("", encoding="utf-8")
    (python_dir / "target.env").write_text("", encoding="utf-8")
    (python_dir / ".env.local").write_text(
        "\n".join(
            [
                "AIMIPAY_SETTLEMENT_BACKEND=local_smoke",
                "AIMIPAY_BUYER_ADDRESS=TRX_BUYER",
                "AIMIPAY_BUYER_PRIVATE_KEY=0x1234",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AIMIPAY_REPOSITORY_ROOT", str(repo_root))

    app = create_buyer_onboarding_app()
    client = TestClient(app)

    response = client.post(
        "/aimipay/buyer/onboarding/merchant-url",
        json={"merchant_url": "https://merchant.example"},
    )
    page = client.get("/aimipay/buyer/onboarding")

    assert response.status_code == 200
    assert response.json()["merchant_urls"] == ["https://merchant.example"]
    assert "Save Merchant URL" in page.text
    assert "refresh-onboarding-button" in page.text


def test_example_easy_setup_app_exposes_single_page_install_hub(monkeypatch) -> None:
    app = create_easy_setup_app()
    client = TestClient(app)

    response = client.get("/aimipay/easy-setup")

    assert response.status_code == 200
    assert "Torn-AgentPay Role Setup" in response.text
    assert "Buyer Path" in response.text
    assert "Merchant Path" in response.text
    assert "Demo Path" in response.text


def test_example_easy_setup_status_returns_buyer_and_merchant_reports() -> None:
    app = create_easy_setup_app()
    client = TestClient(app)

    response = client.get("/aimipay/easy-setup/status")

    assert response.status_code == 200
    payload = response.json()
    assert "buyer" in payload
    assert "merchant" in payload
    assert "links" in payload
    assert "buyer_bootstrap_command" in payload["links"]
    assert "merchant_bootstrap_command" in payload["links"]


def test_local_demo_runtime_builds_single_merchant_runtime() -> None:
    runtime = build_local_demo_runtime(
        merchant_base_url="http://127.0.0.1:8000",
        repository_root="e:/trade/aimicropay-tron",
    )

    assert runtime.default_merchant_base_url is None
    assert runtime.merchant_base_urls == ["http://127.0.0.1:8000"]


def test_local_demo_summary_formats_key_fields() -> None:
    summary = format_demo_summary(
        {
            "selection": {
                "selected": {
                    "offer": {
                        "merchant_base_url": "http://127.0.0.1:8000",
                    }
                }
            },
            "offer": {
                "capability_id": "research-web-search",
                "route_path": "/tools/research",
            },
            "budget": {
                "estimated_total_atomic": 750000,
            },
            "payment": {
                "status": "submitted",
                "tx_id": "trx_123",
            },
        }
    )

    assert "AimiPay Local Demo Summary" in summary
    assert "selected merchant: http://127.0.0.1:8000" in summary
    assert "payment status: submitted" in summary


def test_example_env_loader_is_safe_when_no_file_exists(tmp_path) -> None:
    load_default_example_env(start_dir=tmp_path)


def test_offchain_stress_drill_completes_with_terminal_payments(tmp_path) -> None:
    summary = run_offchain_stress_drill(
        payment_count=12,
        worker_count=3,
        max_rounds=6,
        sqlite_path=tmp_path / "drill-payments.db",
    )

    assert summary["unfinished_count"] == 0
    assert summary["final_status_counts"]["settled"] >= 1
    assert "failed" in summary["final_status_counts"]


def test_offchain_stress_drill_summary_is_readable() -> None:
    rendered = format_drill_summary(
        {
            "storage_backend": "sqlite",
            "worker_count": 3,
            "payment_count": 12,
            "unfinished_count": 0,
            "final_status_counts": {"settled": 10, "failed": 2},
            "rounds": [{"round": 1}],
        }
    )

    assert "AimiPay Off-Chain Stress Drill" in rendered
    assert "unfinished after drill: 0" in rendered


def test_render_claude_startup_card_demo_outputs_expected_html(tmp_path) -> None:
    output_path = tmp_path / "claude-startup-card.html"

    html = render_claude_startup_card_demo(
        repository_root="E:/trade/aimicropay-tron",
        output_file=output_path,
    )

    assert "Claude Desktop" in html
    assert "Fund Wallet" in html
    assert output_path.exists()

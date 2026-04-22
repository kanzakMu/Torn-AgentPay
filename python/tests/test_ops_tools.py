from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ops_tools.network_profile_setup import apply_network_profile
from ops_tools.conformance_check import run_protocol_conformance, run_protocol_conformance_from_files
from ops_tools.build_release_artifacts import build_release_artifacts
from ops_tools.export_conformance_fixtures import export_conformance_fixtures
from ops_tools.export_protocol_schemas import export_protocol_schemas
from ops_tools.package_protocol_bundle import package_protocol_bundle
from ops_tools.package_reference_buyer import package_reference_buyer
from ops_tools.package_seller_node import package_seller_node
from ops_tools.preflight import build_gateway_config_from_env
from ops_tools.target_dry_run import run_target_dry_run
from ops_tools.validate_release_artifacts import validate_release_artifacts
from seller.gateway import GatewayConfig, GatewaySettlementConfig, install_gateway
from shared import PaymentRecord, SqlitePaymentStore


def test_build_gateway_config_from_env_can_load_explicit_env_file(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / "target.env"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_REPOSITORY_ROOT=e:/trade/aimicropay-tron",
                "AIMIPAY_FULL_HOST=http://127.0.0.1:9090",
                "AIMIPAY_SETTLEMENT_BACKEND=local_smoke",
                "AIMIPAY_CHAIN_ID=31337",
                "AIMIPAY_SELLER_ADDRESS=TRX_SELLER_TARGET",
                "AIMIPAY_SELLER_PRIVATE_KEY=seller_private_key",
                "AIMIPAY_CONTRACT_ADDRESS=TRX_CONTRACT_TARGET",
                "AIMIPAY_TOKEN_ADDRESS=TRX_USDT_TARGET",
                f"AIMIPAY_SQLITE_PATH={tmp_path / 'payments.db'}",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("AIMIPAY_SELLER_ADDRESS", raising=False)

    config = build_gateway_config_from_env(env_file=env_file)

    assert config.seller_address == "TRX_SELLER_TARGET"
    assert config.sqlite_path == str(tmp_path / "payments.db")


def test_run_target_dry_run_generates_report_and_snapshot_restore(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "payments.db"
    store = SqlitePaymentStore(sqlite_path)
    store.upsert(
        PaymentRecord(
            payment_id="pay_target_1",
            idempotency_key="idem_target_1",
            route_path="/tools/research",
            amount_atomic=250_000,
            chain="tron",
            buyer_address="TRX_BUYER",
            seller_address="TRX_SELLER",
            channel_id="channel_target_1",
            contract_address="TRX_CONTRACT",
            token_address="TRX_USDT",
            voucher_nonce=1,
            expires_at=9_999_999_999,
            request_deadline=9_999_999_999,
            status="authorized",
        )
    )
    env_file = tmp_path / "target.env"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_REPOSITORY_ROOT=e:/trade/aimicropay-tron",
                "AIMIPAY_FULL_HOST=http://127.0.0.1:9090",
                "AIMIPAY_SETTLEMENT_BACKEND=local_smoke",
                "AIMIPAY_CHAIN_ID=31337",
                "AIMIPAY_SELLER_ADDRESS=TRX_SELLER_TARGET",
                "AIMIPAY_SELLER_PRIVATE_KEY=seller_private_key",
                "AIMIPAY_CONTRACT_ADDRESS=TRX_CONTRACT_TARGET",
                "AIMIPAY_TOKEN_ADDRESS=TRX_USDT_TARGET",
                f"AIMIPAY_SQLITE_PATH={sqlite_path}",
            ]
        ),
        encoding="utf-8",
    )

    report = run_target_dry_run(
        output_dir=tmp_path / "dry-run",
        env_file=env_file,
        payment_count=12,
        worker_count=3,
        max_rounds=6,
        execute_delay_s=0.0,
        confirm_delay_s=0.0,
    )

    assert report["preflight"]["ok"] is True
    assert report["snapshot_restore"]["restored"] == 1
    assert report["drill"]["rounds"][-1]["unfinished"] == 0
    assert "aimipay_runtime_ok" in report["drill"]["prometheus_metrics"]


def test_apply_network_profile_sets_managed_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.local"
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_REPOSITORY_ROOT=E:/trade/aimicropay-tron",
                "AIMIPAY_FULL_HOST=http://placeholder.local",
                "AIMIPAY_SELLER_ADDRESS=TRX_SELLER",
            ]
        ),
        encoding="utf-8",
    )

    report = apply_network_profile(env_file=env_file, profile_name="local", emit_output=False)
    updated = env_file.read_text(encoding="utf-8")

    assert report["profile"] == "local"
    assert "AIMIPAY_NETWORK_PROFILE=local" in updated
    assert "AIMIPAY_FULL_HOST=http://127.0.0.1:9090" in updated
    assert "AIMIPAY_SETTLEMENT_BACKEND=local_smoke" in updated
    assert "AIMIPAY_SELLER_ADDRESS=TRX_SELLER" in updated


def test_protocol_conformance_check_reports_signed_manifest_ok() -> None:
    app = FastAPI()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Research Copilot",
            service_description="Pay-per-use research and market data",
            seller_address="TVaEiLLej394ZxVmHZXYg3HprssbpdcsmW",
            contract_address="0x1000000000000000000000000000000000000001",
            token_address="0x2000000000000000000000000000000000000002",
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://tron.local",
                seller_private_key="0x59c6995e998f97a5a0044966f0945382d7f4a3f1f3f7e61a821a3d1d021b6d2d",
                chain_id=31337,
                executor_backend="claim_script",
            ),
        ),
    )
    http_client = TestClient(app, base_url="http://seller.test")

    report = run_protocol_conformance(
        seller_base_url="http://seller.test",
        http_client=http_client,
    )

    assert report["ok"] is True
    assert report["attestation"]["seller_profile_verified"] is True
    assert report["attestation"]["manifest_verified"] is True
    assert report["schema_refs"]["manifest"].endswith("aimipay.manifest.v1.schema.json")


def test_export_protocol_schemas_materializes_expected_bundle(tmp_path: Path) -> None:
    report = export_protocol_schemas(
        repository_root="e:/trade/aimicropay-tron",
        output_dir=tmp_path / "schemas",
    )

    output_dir = Path(report["output_dir"])
    assert (output_dir / "aimipay.manifest.v1.schema.json").exists()
    assert (output_dir / "aimipay.offer.v1.schema.json").exists()
    assert (output_dir / "aimipay.seller-profile.v1.schema.json").exists()
    assert (output_dir / "aimipay.signature-envelope.v1.schema.json").exists()
    assert (output_dir / "index.json").exists()


def test_package_protocol_bundle_materializes_release_files(tmp_path: Path) -> None:
    report = package_protocol_bundle(
        repository_root="e:/trade/aimicropay-tron",
        output_dir=tmp_path / "protocol-bundle",
    )

    output_dir = Path(report["output_dir"])
    assert (output_dir / "README.md").exists()
    assert (output_dir / "PROTOCOL_REFERENCE.md").exists()
    assert (output_dir / "discovery.md").exists()
    assert (output_dir / "THIRD_PARTY_IMPLEMENTER_GUIDE.md").exists()
    assert (output_dir / "BUYER_IMPLEMENTER_GUIDE.md").exists()
    assert (output_dir / "HOST_IMPLEMENTER_GUIDE.md").exists()
    assert (output_dir / "COMPATIBILITY_POLICY.md").exists()
    assert (output_dir / "CONFORMANCE_CHECKLIST.md").exists()
    assert (output_dir / "schemas" / "aimipay.manifest.v1.schema.json").exists()
    assert (output_dir / "bundle-report.json").exists()


def test_build_release_artifacts_materializes_dist_layout(tmp_path: Path) -> None:
    report = build_release_artifacts(
        repository_root="e:/trade/aimicropay-tron",
        output_dir=tmp_path / "dist",
    )

    output_dir = Path(report["output_dir"])
    assert (output_dir / "protocol-schemas" / "aimipay.manifest.v1.schema.json").exists()
    assert (output_dir / "protocol-bundle" / "README.md").exists()
    assert (output_dir / "seller-node" / "seller-node.manifest.json").exists()
    assert (output_dir / "reference-buyer" / "reference-buyer.manifest.json").exists()
    assert (output_dir / "conformance-fixtures" / "purchase.json").exists()
    assert (output_dir / "RELEASE_NOTES.md").exists()
    assert (output_dir / "release-manifest.json").exists()
    assert (output_dir / "release-report.json").exists()


def test_validate_release_artifacts_reports_complete_dist_layout(tmp_path: Path) -> None:
    report = build_release_artifacts(
        repository_root="e:/trade/aimicropay-tron",
        output_dir=tmp_path / "dist",
    )

    validation = validate_release_artifacts(dist_dir=report["output_dir"])

    assert validation["ok"] is True
    assert validation["missing"] == []


def test_export_conformance_fixtures_materializes_offline_bundle(tmp_path: Path) -> None:
    report = export_conformance_fixtures(output_dir=tmp_path / "fixtures")

    output_dir = Path(report["output_dir"])
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "discover.json").exists()
    assert (output_dir / "attestation.json").exists()
    assert (output_dir / "purchase.json").exists()


def test_protocol_conformance_from_files_validates_purchase_fixture(tmp_path: Path) -> None:
    report = export_conformance_fixtures(output_dir=tmp_path / "fixtures")
    output_dir = Path(report["output_dir"])

    conformance = run_protocol_conformance_from_files(
        manifest_file=output_dir / "manifest.json",
        discover_file=output_dir / "discover.json",
        attestation_file=output_dir / "attestation.json",
        purchase_file=output_dir / "purchase.json",
    )

    assert conformance["ok"] is True
    assert conformance["purchase"]["errors"] == []


def test_package_seller_node_materializes_expected_files(tmp_path: Path) -> None:
    report = package_seller_node(
        repository_root="e:/trade/aimicropay-tron",
        output_dir=tmp_path / "seller-node",
    )

    output_dir = Path(report["output_dir"])
    assert (output_dir / "README.md").exists()
    assert (output_dir / "seller-node.manifest.json").exists()
    assert (output_dir / "bootstrap-seller-node.ps1").exists()
    assert (output_dir / "run-seller-node.ps1").exists()
    assert (output_dir / "docker-compose.seller-node.yml").exists()


def test_package_reference_buyer_materializes_expected_files(tmp_path: Path) -> None:
    report = package_reference_buyer(
        repository_root="e:/trade/aimicropay-tron",
        output_dir=tmp_path / "reference-buyer",
    )

    output_dir = Path(report["output_dir"])
    assert (output_dir / "README.md").exists()
    assert (output_dir / "reference-buyer.manifest.json").exists()
    assert (output_dir / "minimal-buyer-reference.py").exists()

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from buyer.client import BuyerClient
from buyer.provisioner import OpenChannelExecution
from buyer.wallet import BuyerWallet
from seller.gateway import GatewayConfig, GatewaySettlementConfig, install_gateway
from shared import MerchantRoute, channel_id_of


class _FixtureProvisioner:
    def provision(self, plan):
        return OpenChannelExecution(
            approve_tx_id="approve_fixture_1",
            open_tx_id="open_fixture_1",
            buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            seller_address=plan.seller_address,
            token_address=plan.token_address,
            channel_id=channel_id_of(
                buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
            ),
            contract_address=plan.contract_address,
            deposit_atomic=plan.deposit_atomic,
            expires_at=plan.expires_at,
        )


class _FixtureSettlementService:
    runtime = None

    def execute_payment(self, payment_id: str):
        record = self.runtime.payment_store.get(payment_id)
        updated = record.model_copy(
            update={
                "status": "submitted",
                "tx_id": "trx_fixture_claim_1",
            }
        )
        self.runtime.payment_store.upsert(updated)
        return updated

    def execute_pending(self):
        raise AssertionError("not used in fixture export")

    def reconcile_payment(self, payment_id: str):
        record = self.runtime.payment_store.get(payment_id)
        updated = record.model_copy(
            update={
                "status": "settled",
                "confirmation_status": "confirmed",
                "confirmation_attempts": int(record.confirmation_attempts) + 1,
                "settled_at": 1_700_000_001,
                "confirmed_at": 1_700_000_001,
            }
        )
        self.runtime.payment_store.upsert(updated)
        return updated


def _build_fixture_gateway_app() -> FastAPI:
    settlement_service = _FixtureSettlementService()
    app = FastAPI()
    install_gateway(
        app,
        GatewayConfig(
            service_name="Fixture Seller",
            service_description="Fixture seller for protocol conformance examples.",
            seller_address="TVaEiLLej394ZxVmHZXYg3HprssbpdcsmW",
            contract_address="0x1000000000000000000000000000000000000001",
            token_address="0x2000000000000000000000000000000000000002",
            routes=[
                MerchantRoute(
                    path="/tools/research",
                    method="POST",
                    price_atomic=250_000,
                    description="Fixture paid research route",
                    capability_id="research-web-search",
                    capability_type="web_search",
                    pricing_model="fixed_per_call",
                    usage_unit="request",
                    delivery_mode="sync",
                    response_format="json",
                )
            ],
            settlement=GatewaySettlementConfig(
                repository_root="e:/trade/aimicropay-tron",
                full_host="http://tron.local",
                seller_private_key="0x59c6995e998f97a5a0044966f0945382d7f4a3f1f3f7e61a821a3d1d021b6d2d",
                chain_id=31337,
                executor_backend="claim_script",
            ),
        ),
        settlement_service=settlement_service,
    )
    settlement_service.runtime = app.state.aimipay_gateway
    return app


def export_conformance_fixtures(*, output_dir: str | Path) -> dict[str, Any]:
    target_dir = Path(output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    app = _build_fixture_gateway_app()
    http_client = TestClient(app, base_url="http://seller.test")
    client = BuyerClient(
        merchant_base_url="http://seller.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        ),
        provisioner=_FixtureProvisioner(),
        http_client=http_client,
    )

    manifest = client.fetch_manifest()
    discovery = client.discover()
    attestation = manifest.get("_attestation") or client.verify_manifest_attestation(manifest)
    prepared = client.prepare_purchase(capability_id="research-web-search")
    submitted = client.submit_purchase(
        prepared_purchase=prepared,
        request_body='{"topic":"tron"}',
        auto_execute=False,
    )
    confirmed = client.confirm_purchase(submitted["payment"]["payment_id"])
    purchase_fixture = {
        "prepare_purchase": {
            "offer": prepared["offer"],
            "budget": prepared["budget"],
            "decision": prepared["decision"],
            "session": prepared["session"],
        },
        "submit_purchase": {
            "offer": submitted["offer"],
            "budget": submitted["budget"],
            "decision": submitted["decision"],
            "session": submitted["session"],
            "payment": submitted["payment"],
        },
        "confirm_purchase": confirmed,
    }

    files = {
        "manifest.json": manifest,
        "discover.json": discovery,
        "attestation.json": attestation,
        "purchase.json": purchase_fixture,
    }
    written: list[str] = []
    for filename, payload in files.items():
        destination = target_dir / filename
        destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(str(destination))

    report = {
        "fixture_bundle": "torn-agentpay.conformance-fixtures.v1",
        "output_dir": str(target_dir),
        "files": written,
    }
    (target_dir / "fixture-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Torn-AgentPay offline conformance fixtures.")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    report = export_conformance_fixtures(output_dir=args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

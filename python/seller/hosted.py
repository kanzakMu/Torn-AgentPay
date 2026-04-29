from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, Request, status

from .gateway import GatewayConfig, GatewayRuntime, install_gateway


@dataclass(slots=True)
class HostedMerchant:
    merchant_id: str
    config: GatewayConfig
    api_key_sha256: str | None = None
    runtime: GatewayRuntime | None = None
    created_at: int = field(default_factory=lambda: int(time.time()))


@dataclass(slots=True)
class HostedGatewayRegistry:
    merchants: dict[str, HostedMerchant] = field(default_factory=dict)

    def issue_api_key(self) -> str:
        return f"ak_{secrets.token_urlsafe(32)}"

    def add_merchant(self, merchant: HostedMerchant) -> HostedMerchant:
        if merchant.merchant_id in self.merchants:
            raise ValueError(f"merchant already exists: {merchant.merchant_id}")
        self.merchants[merchant.merchant_id] = merchant
        return merchant

    def get(self, merchant_id: str) -> HostedMerchant:
        merchant = self.merchants.get(merchant_id)
        if merchant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "merchant_not_found", "merchant_id": merchant_id},
            )
        return merchant

    def public_catalog(self) -> dict:
        return {
            "schema_version": "aimipay.hosted-merchant-catalog.v1",
            "generated_at": int(time.time()),
            "merchant_count": len(self.merchants),
            "merchants": [
                {
                    "merchant_id": merchant.merchant_id,
                    "service_name": merchant.config.service_name,
                    "service_description": merchant.config.service_description,
                    "seller_address": merchant.config.seller_address,
                    "capability_registry_url": f"/merchants/{merchant.merchant_id}/_aimipay/registry/capabilities",
                    "created_at": merchant.created_at,
                }
                for merchant in self.merchants.values()
            ],
        }

    def marketplace_capabilities(self) -> dict:
        capabilities: list[dict] = []
        for merchant in self.merchants.values():
            if merchant.runtime is None:
                continue
            registry = merchant.runtime.capability_registry()
            for capability in registry.get("capabilities", []):
                capabilities.append(
                    {
                        **capability,
                        "merchant_id": merchant.merchant_id,
                        "service_name": merchant.config.service_name,
                        "capability_registry_url": f"/merchants/{merchant.merchant_id}/_aimipay/registry/capabilities",
                    }
                )
        return {
            "schema_version": "aimipay.marketplace-capability-index.v1",
            "generated_at": int(time.time()),
            "capability_count": len(capabilities),
            "capabilities": capabilities,
        }


class SqliteHostedGatewayRegistry(HostedGatewayRegistry):
    def __init__(self, sqlite_path: str) -> None:
        super().__init__()
        self.sqlite_path = sqlite_path
        self._initialize()
        self._load()

    def add_merchant(self, merchant: HostedMerchant) -> HostedMerchant:
        added = super().add_merchant(merchant)
        self._persist(added)
        return added

    def _initialize(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hosted_merchants (
                    merchant_id TEXT PRIMARY KEY,
                    api_key_sha256 TEXT,
                    config_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )

    def _load(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            rows = conn.execute(
                "SELECT merchant_id, api_key_sha256, config_json, created_at FROM hosted_merchants ORDER BY merchant_id"
            ).fetchall()
        for merchant_id, api_key_sha256, config_json, created_at in rows:
            self.merchants[merchant_id] = HostedMerchant(
                merchant_id=merchant_id,
                api_key_sha256=api_key_sha256,
                config=GatewayConfig(**json.loads(config_json)),
                created_at=int(created_at),
            )

    def _persist(self, merchant: HostedMerchant) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                INSERT INTO hosted_merchants (merchant_id, api_key_sha256, config_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(merchant_id) DO UPDATE SET
                    api_key_sha256 = excluded.api_key_sha256,
                    config_json = excluded.config_json,
                    created_at = excluded.created_at
                """,
                (
                    merchant.merchant_id,
                    merchant.api_key_sha256,
                    json.dumps(_gateway_config_payload(merchant.config), sort_keys=True),
                    merchant.created_at,
                ),
            )

    def marketplace_capabilities(self) -> dict:
        capabilities: list[dict] = []
        for merchant in self.merchants.values():
            if merchant.runtime is None:
                continue
            registry = merchant.runtime.capability_registry()
            for capability in registry.get("capabilities", []):
                capabilities.append(
                    {
                        **capability,
                        "merchant_id": merchant.merchant_id,
                        "service_name": merchant.config.service_name,
                        "capability_registry_url": f"/merchants/{merchant.merchant_id}/_aimipay/registry/capabilities",
                    }
                )
        return {
            "schema_version": "aimipay.marketplace-capability-index.v1",
            "generated_at": int(time.time()),
            "capability_count": len(capabilities),
            "capabilities": capabilities,
        }


def install_hosted_gateway(
    app: FastAPI,
    merchants: list[HostedMerchant],
    *,
    registry: HostedGatewayRegistry | None = None,
) -> HostedGatewayRegistry:
    hosted_registry = registry or HostedGatewayRegistry()
    for merchant in merchants:
        hosted_registry.add_merchant(merchant)
        sub_app = FastAPI(title=f"AimiPay merchant {merchant.merchant_id}")
        merchant.config.management_prefix = "/_aimipay"
        merchant.runtime = install_gateway(sub_app, merchant.config)
        app.mount(f"/merchants/{merchant.merchant_id}", sub_app)

    @app.get("/_aimipay/hosted/merchants")
    async def hosted_merchants() -> dict:
        return hosted_registry.public_catalog()

    @app.get("/_aimipay/marketplace/capabilities")
    async def hosted_marketplace_capabilities() -> dict:
        return hosted_registry.marketplace_capabilities()

    @app.get("/_aimipay/hosted/merchants/{merchant_id}/admin-summary")
    async def hosted_admin_summary(merchant_id: str, request: Request) -> dict:
        merchant = hosted_registry.get(merchant_id)
        _require_hosted_api_key(request, merchant)
        assert merchant.runtime is not None
        return {
            "schema_version": "aimipay.hosted-admin-summary.v1",
            "merchant": {
                "merchant_id": merchant.merchant_id,
                "service_name": merchant.config.service_name,
            },
            "agent_status": merchant.runtime.agent_status(),
            "billing": merchant.runtime.billing_summary(),
        }

    app.state.aimipay_hosted_gateway = hosted_registry
    return hosted_registry


def hosted_api_key_hash(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _require_hosted_api_key(request: Request, merchant: HostedMerchant) -> None:
    if not merchant.api_key_sha256:
        return
    supplied = request.headers.get("x-aimipay-merchant-key", "")
    if hosted_api_key_hash(supplied) != merchant.api_key_sha256:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "merchant_api_key_required"},
        )


def _gateway_config_payload(config: GatewayConfig) -> dict:
    return {
        "service_name": config.service_name,
        "service_description": config.service_description,
        "seller_address": config.seller_address,
        "contract_address": config.contract_address,
        "token_address": config.token_address,
        "network": config.network,
        "asset_symbol": config.asset_symbol,
        "asset_decimals": config.asset_decimals,
        "chain_id": config.chain_id,
        "default_deposit_atomic": config.default_deposit_atomic,
        "default_channel_ttl_s": config.default_channel_ttl_s,
        "admin_token": config.admin_token,
        "admin_token_sha256": config.admin_token_sha256,
        "admin_read_token": config.admin_read_token,
        "admin_read_token_sha256": config.admin_read_token_sha256,
        "audit_log_path": config.audit_log_path,
        "webhook_urls": list(config.webhook_urls),
        "webhook_secret": config.webhook_secret,
        "routes": [route.model_dump(mode="json") for route in config.routes],
        "plans": [plan.model_dump(mode="json") for plan in config.plans],
        "management_prefix": config.management_prefix,
        "settlement": config.settlement,
        "sqlite_path": config.sqlite_path,
    }

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ops_tools.agent_onboarding import run_agent_onboarding
from ops_tools.buyer_setup import prepare_buyer_install_env
from ops_tools.wallet_funding import inspect_wallet_funding
from ops_tools.wallet_setup import ensure_local_buyer_wallet
from shared import (
    agent_state_payload,
    budget_quote_payload,
    build_agent_capability_manifest,
    capability_catalog_payload,
    payment_state_payload,
    recovery_payload,
)

from .client import BuyerClient


@dataclass(slots=True)
class AimiPayAgentAdapter:
    client: BuyerClient
    http_clients: dict[str, Any] | None = None

    def get_protocol_manifest(self) -> dict:
        return build_agent_capability_manifest()

    def list_offers(self) -> dict:
        offers = self.client.discover_offers()
        return {
            **capability_catalog_payload(offers=offers),
            "offers": offers,
            "next_step": "quote_budget",
            "action_required": None,
        }

    def estimate_budget(
        self,
        *,
        capability_id: str,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
    ) -> dict:
        estimate = self.client.estimate_budget(
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
        )
        return {
            **budget_quote_payload(estimate=estimate),
            "next_step": "prepare_purchase"
            if estimate["decision"]["action"] == "buy_now"
            else estimate["decision"]["action"],
        }

    def quote_budget(
        self,
        *,
        capability_id: str,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
    ) -> dict:
        return self.estimate_budget(
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
        )

    def plan_purchase(
        self,
        *,
        capability_type: str | None = None,
        capability_id: str | None = None,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
    ) -> dict:
        selection = self.client.select_capability_offer(
            capability_type=capability_type,
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
        )
        quote = budget_quote_payload(estimate=selection["selected"])
        return {
            **quote,
            "kind": "purchase_plan",
            "selection": selection,
            "next_step": "prepare_purchase"
            if selection["selected"]["decision"]["action"] == "buy_now"
            else selection["selected"]["decision"]["action"],
        }

    def open_channel(self, **kwargs) -> dict:
        session = self.client.ensure_channel_for_route(**kwargs)
        return {
            "session": session,
            "next_step": "create_payment_intent",
            "action_required": None,
        }

    def create_payment(self, **kwargs) -> dict:
        payment = self.client.create_payment_intent(**kwargs)
        return {
            "payment": payment,
            "safe_to_retry": bool(payment.get("safe_to_retry", False)),
            "next_step": payment.get("next_step"),
            "action_required": payment.get("action_required"),
            "human_approval_required": bool(payment.get("human_approval_required", False)),
        }

    def prepare_purchase(self, **kwargs) -> dict:
        prepared = self.client.prepare_purchase(**kwargs)
        return {
            **prepared,
            "next_step": "submit_purchase" if prepared.get("session") else prepared["decision"]["action"],
            "action_required": None if prepared.get("session") else prepared["decision"]["action"],
        }

    def submit_purchase(self, **kwargs) -> dict:
        purchase = self.client.submit_purchase(**kwargs)
        payment = purchase["payment"]
        return {
            **purchase,
            "safe_to_retry": bool(payment.get("safe_to_retry", False)),
            "next_step": payment.get("next_step"),
        }

    def confirm_purchase(
        self,
        payment_id: str,
        *,
        max_attempts: int = 3,
        execute_if_needed: bool = True,
    ) -> dict:
        payment = self.client.confirm_purchase(
            payment_id,
            max_attempts=max_attempts,
            execute_if_needed=execute_if_needed,
        )
        return {
            "payment": payment,
            "safe_to_retry": bool(payment.get("safe_to_retry", False)),
            "next_step": payment.get("next_step"),
        }

    def execute_payment(self, payment_id: str) -> dict:
        payment = self.client.execute_payment(payment_id)
        return {
            "payment": payment,
            "safe_to_retry": bool(payment.get("safe_to_retry", False)),
            "next_step": payment.get("next_step"),
        }

    def get_payment_status(self, payment_id: str) -> dict:
        payment = self.client.get_payment_status(payment_id)
        return {
            **payment_state_payload(payment=payment),
            "safe_to_retry": bool(payment.get("safe_to_retry", False)),
            "next_step": payment.get("next_step"),
        }

    def reconcile_payment(self, payment_id: str) -> dict:
        payment = self.client.reconcile_payment(payment_id)
        return {
            "payment": payment,
            "safe_to_retry": bool(payment.get("safe_to_retry", False)),
            "next_step": payment.get("next_step"),
        }

    def finalize_payment(
        self,
        payment_id: str,
        *,
        max_attempts: int = 3,
        execute_if_needed: bool = True,
    ) -> dict:
        payment = self.client.finalize_payment(
            payment_id,
            max_attempts=max_attempts,
            execute_if_needed=execute_if_needed,
        )
        return {
            "payment": payment,
            "safe_to_retry": bool(payment.get("safe_to_retry", False)),
            "next_step": payment.get("next_step"),
        }

    def list_pending_payments(self) -> dict:
        pending = self.client.list_pending_payments()
        payments = pending.get("payments") or []
        return {
            **recovery_payload(payments=payments, source="list_pending_payments"),
            "count": pending.get("count", len(payments)),
        }

    def get_merchant_status(self, *, admin_token: str | None = None) -> dict:
        status = self.client.get_merchant_agent_status(admin_token=admin_token)
        readiness = status.get("readiness") or {}
        payments = status.get("payments") or {}
        if not readiness.get("ready"):
            next_step = "review_merchant_readiness"
        elif payments.get("unfinished_count", 0):
            next_step = "recover_or_finalize_pending_payments"
        else:
            next_step = "ready_to_purchase"
        return {
            **status,
            "next_step": next_step,
            "action_required": None if next_step == "ready_to_purchase" else next_step,
        }

    def recover_payment(self, **kwargs) -> dict:
        recovered = self.client.recover_payment(**kwargs)
        payments = recovered.get("payments") or []
        return {
            **recovery_payload(payments=payments, source="recover_payment"),
            "count": recovered.get("count", len(payments)),
        }

    def get_agent_state(self, *, admin_token: str | None = None) -> dict:
        merchant_status = self.client.get_merchant_agent_status(admin_token=admin_token)
        offers = self.client.discover_offers()
        pending = self.client.list_pending_payments()
        return agent_state_payload(
            merchant_status=merchant_status,
            offers=offers,
            pending=pending,
        )

    def check_wallet_funding(self, *, env_file: str | None = None) -> dict:
        report = inspect_wallet_funding(
            repository_root=self.client.repository_root,
            env_file=env_file,
            output_json=False,
            emit_output=False,
        )
        next_step = "ready_to_purchase"
        if not report.get("wallet_ready"):
            next_step = "create_wallet"
        elif report.get("settlement_backend") != "local_smoke":
            probe = report.get("funding_probe") or {}
            if probe.get("status") != "ok":
                next_step = "fund_wallet"
            elif probe.get("meets_min_trx_balance") is False or probe.get("meets_min_token_balance") is False:
                next_step = "fund_wallet"
        return {
            **report,
            "next_step": next_step,
            "action_required": None if next_step == "ready_to_purchase" else next_step,
        }

    def create_wallet(
        self,
        *,
        env_file: str | None = None,
        wallet_file: str | None = None,
        force_create: bool = False,
    ) -> dict:
        wallet = ensure_local_buyer_wallet(
            repository_root=self.client.repository_root,
            env_file=env_file,
            wallet_file=wallet_file,
            force_create=force_create,
            output_json=False,
            emit_output=False,
        )
        funding = self.check_wallet_funding(env_file=env_file)
        return {
            "wallet": wallet,
            "funding": funding,
            "next_step": funding["next_step"],
            "action_required": funding["action_required"],
        }

    def run_onboarding(
        self,
        *,
        env_file: str | None = None,
        wallet_file: str | None = None,
        force_create_wallet: bool = False,
    ) -> dict:
        report = run_agent_onboarding(
            repository_root=self.client.repository_root,
            env_file=env_file,
            wallet_file=wallet_file,
            force_create_wallet=force_create_wallet,
            output_json=False,
            emit_output=False,
        )
        return {
            **report,
            "next_step": report["next_step"],
            "action_required": report["action_required"],
        }

    def set_merchant_url(
        self,
        *,
        merchant_url: str,
        env_file: str | None = None,
        network_profile: str | None = None,
    ) -> dict:
        setup = prepare_buyer_install_env(
            repository_root=self.client.repository_root,
            env_file=env_file,
            merchant_urls=[merchant_url],
            network_profile=network_profile,
            output_json=False,
            emit_output=False,
        )
        onboarding = run_agent_onboarding(
            repository_root=self.client.repository_root,
            env_file=env_file,
            output_json=False,
            emit_output=False,
        )
        merchant_preview = self._merchant_preview(merchant_url)
        if merchant_preview is not None:
            onboarding["merchant"] = merchant_preview
            offer_count = (merchant_preview.get("offers") or {}).get("count", 0)
            if offer_count > 0:
                onboarding["next_step"] = "review_offers"
                onboarding["action_required"] = None
                onboarding["completed"] = True
            elif merchant_preview.get("ok"):
                onboarding["next_step"] = "discover_offers"
                onboarding["action_required"] = None
                onboarding["completed"] = True
        return {
            "setup": setup,
            "onboarding": onboarding,
            "next_step": onboarding["next_step"],
            "action_required": onboarding["action_required"],
        }

    def _merchant_preview(self, merchant_url: str) -> dict[str, Any] | None:
        http_client = None
        if merchant_url == self.client.merchant_base_url and self.client.http_client is not None:
            http_client = self.client.http_client
        elif self.http_clients is not None:
            http_client = self.http_clients.get(merchant_url)

        try:
            probe_client = BuyerClient(
                merchant_base_url=merchant_url,
                full_host=self.client.full_host,
                wallet=self.client.wallet,
                provisioner=self.client.provisioner,
                http_client=http_client,
                repository_root=self.client.repository_root,
            )
            manifest = probe_client.fetch_manifest()
            discover = probe_client.discover()
            offers = probe_client.list_capability_offers()
        except Exception:
            return None

        offer_items = [
            {
                "capability_id": offer.get("capability_id"),
                "route_path": offer.get("route_path"),
                "capability_type": offer.get("capability_type"),
                "price_atomic": offer.get("amount_atomic", 0),
            }
            for offer in offers[:5]
        ]
        return {
            "present": True,
            "merchant_urls": [merchant_url],
            "selected_url": merchant_url,
            "ok": True,
            "service_name": manifest.get("service_name"),
            "discover": {
                "chain": discover.get("chain"),
                "settlement_backend": discover.get("settlement_backend"),
                "contract_address": discover.get("contract_address"),
                "token_address": discover.get("token_address"),
            },
            "offers": {
                "count": len(offers),
                "items": offer_items,
            },
            "host_action": {
                "action": "review_offers" if offers else "discover_offers",
                "title": "Merchant Connected",
                "message": f"Connected to {manifest.get('service_name') or merchant_url} and loaded offer metadata.",
                "checklist": [
                    f"Merchant URL: {merchant_url}",
                    f"Offers discovered: {len(offers)}",
                ],
                "fields": [
                    {
                        "name": "merchant_url",
                        "label": "Merchant URL",
                        "type": "url",
                        "required": True,
                        "value": merchant_url,
                    }
                ],
                "resources": [
                    {"label": "Manifest", "url": f"{merchant_url.rstrip('/')}/.well-known/aimipay.json"},
                    {"label": "Discover", "url": manifest["endpoints"]["management"].rstrip("/") + "/discover"},
                ],
                "offers_preview": offer_items[:3],
            },
        }

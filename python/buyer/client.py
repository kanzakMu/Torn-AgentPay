from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from shared import SignatureEnvelope, build_payment_voucher, resolve_full_host_for_network, verify_signed_payload

from .provisioner import OpenChannelExecution, OpenChannelProvisionPlan, TronProvisioner
from .wallet import BuyerWallet


@dataclass(slots=True)
class BuyerBudgetPolicy:
    policy_name: str = "default"
    per_purchase_limit_atomic: int | None = None
    daily_limit_atomic: int | None = None
    trusted_sellers: set[str] = field(default_factory=set)
    blocked_sellers: set[str] = field(default_factory=set)
    require_approval_for_untrusted: bool = False
    require_approval_above_atomic: int | None = None


@dataclass(slots=True)
class BuyerClient:
    merchant_base_url: str
    full_host: str | None
    wallet: BuyerWallet
    provisioner: TronProvisioner
    http_client: httpx.Client | None = None
    repository_root: str | None = None
    budget_policy: BuyerBudgetPolicy | None = None
    spent_today_atomic: int = 0
    _manifest_cache: dict | None = None
    _discover_cache: dict | None = None

    def fetch_manifest(self) -> dict:
        if self._manifest_cache is None:
            response = self._http().get(self._url("/.well-known/aimipay.json"))
            response.raise_for_status()
            self._manifest_cache = response.json()
            self._manifest_cache["_attestation"] = self.verify_manifest_attestation(self._manifest_cache)
        return self._manifest_cache

    def verify_manifest_attestation(self, manifest: dict) -> dict:
        result = {
            "seller_profile_signed": False,
            "seller_profile_verified": False,
            "manifest_signed": False,
            "manifest_verified": False,
            "errors": [],
        }
        seller_profile = manifest.get("seller_profile")
        seller_profile_signature = manifest.get("seller_profile_signature")
        if seller_profile and seller_profile_signature:
            result["seller_profile_signed"] = True
            try:
                seller_profile_envelope = SignatureEnvelope.model_validate(seller_profile_signature)
                result["seller_profile_verified"] = verify_signed_payload(
                    payload=seller_profile,
                    envelope=seller_profile_envelope,
                    expected_signer_address=(seller_profile.get("seller_address") or manifest.get("primary_chain", {}).get("seller_address")),
                )
                if not result["seller_profile_verified"]:
                    result["errors"].append("seller_profile_signature_invalid")
            except Exception:
                result["errors"].append("seller_profile_signature_invalid")
        manifest_signature = manifest.get("manifest_signature")
        if manifest_signature:
            result["manifest_signed"] = True
            try:
                manifest_envelope = SignatureEnvelope.model_validate(manifest_signature)
                unsigned_manifest = dict(manifest)
                unsigned_manifest.pop("manifest_signature", None)
                result["manifest_verified"] = verify_signed_payload(
                    payload=unsigned_manifest,
                    envelope=manifest_envelope,
                    expected_signer_address=manifest.get("primary_chain", {}).get("seller_address"),
                )
                if not result["manifest_verified"]:
                    result["errors"].append("manifest_signature_invalid")
            except Exception:
                result["errors"].append("manifest_signature_invalid")
        return result

    def discover(self) -> dict:
        if self._discover_cache is None:
            manifest = self.fetch_manifest()
            discover_url = manifest["endpoints"]["management"].rstrip("/") + "/discover"
            response = self._http().get(discover_url)
            response.raise_for_status()
            self._discover_cache = response.json()
        return self._discover_cache

    def list_capability_offers(self) -> list[dict]:
        manifest = self.fetch_manifest()
        chain_info = self._merchant_chain_context(manifest=manifest)
        offers: list[dict] = []
        for route in manifest.get("routes", []):
            unit_price_atomic = int(route.get("price_atomic", 0))
            offers.append(
                {
                    "capability_id": route.get("capability_id") or f"{route.get('method', 'POST').lower()}:{route['path']}",
                    "capability_type": route.get("capability_type", "api"),
                    "route_path": route["path"],
                    "method": str(route.get("method", "POST")).upper(),
                    "description": route.get("description"),
                    "pricing_model": route.get("pricing_model", "fixed_per_call"),
                    "usage_unit": route.get("usage_unit", "request"),
                    "amount_atomic": unit_price_atomic,
                    "unit_price_atomic": unit_price_atomic,
                    "delivery_mode": route.get("delivery_mode", "sync"),
                    "response_format": route.get("response_format"),
                    "expected_latency_ms": route.get("expected_latency_ms"),
                    "minimum_prepaid_atomic": route.get("minimum_prepaid_atomic"),
                    "suggested_prepaid_atomic": route.get("suggested_prepaid_atomic"),
                    "requires_human_approval": bool(route.get("requires_human_approval", False)),
                    "supports_auto_purchase": bool(route.get("supports_auto_purchase", True)),
                    "safe_retry_policy": route.get("safe_retry_policy"),
                    "auth_requirements": list(route.get("auth_requirements") or []),
                    "capability_tags": list(route.get("capability_tags") or []),
                    "budget_hint": route.get("budget_hint"),
                    "settlement_backend": chain_info.get("settlement_backend"),
                    "chain": chain_info.get("chain", "tron"),
                    "chain_id": chain_info.get("chain_id"),
                    "seller_address": chain_info.get("seller_address"),
                    "contract_address": chain_info.get("contract_address"),
                    "token_address": chain_info.get("token_address") or chain_info.get("asset_address"),
                }
            )
        return offers

    def discover_offers(self) -> list[dict]:
        return self.list_capability_offers()

    def estimate_budget(
        self,
        *,
        capability_id: str,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
    ) -> dict:
        return self.estimate_capability_budget(
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
        )

    def estimate_capability_budget(
        self,
        *,
        capability_id: str,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
    ) -> dict:
        if expected_units is not None and expected_units < 0:
            raise ValueError("expected_units must be >= 0")
        offers = self.list_capability_offers()
        offer = next((item for item in offers if item["capability_id"] == capability_id), None)
        if offer is None:
            raise ValueError(f"capability offer not found: {capability_id}")
        return self._estimate_offer(
            offer=offer,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
        )

    def evaluate_capability_offers(
        self,
        *,
        capability_type: str | None = None,
        capability_id: str | None = None,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
    ) -> list[dict]:
        if capability_type is None and capability_id is None:
            raise ValueError("capability_type or capability_id is required")
        offers = self.list_capability_offers()
        matched = []
        for offer in offers:
            if capability_id is not None and offer["capability_id"] != capability_id:
                continue
            if capability_type is not None and offer["capability_type"] != capability_type:
                continue
            matched.append(offer)
        if not matched:
            raise ValueError("no capability offers matched the requested selector")
        evaluated = [
            self._estimate_offer(
                offer=offer,
                expected_units=expected_units,
                budget_limit_atomic=budget_limit_atomic,
            )
            for offer in matched
        ]
        return sorted(
            evaluated,
            key=lambda item: (
                _decision_rank(item["decision"]["action"]),
                item["budget"]["estimated_total_atomic"],
                item["offer"]["capability_id"],
            ),
        )

    def select_capability_offer(
        self,
        *,
        capability_type: str | None = None,
        capability_id: str | None = None,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
    ) -> dict:
        candidates = self.evaluate_capability_offers(
            capability_type=capability_type,
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
        )
        return {
            "selected": candidates[0],
            "candidates": candidates,
            "selection_reason": "lowest estimated cost among matching offers",
        }

    def buy_capability(
        self,
        *,
        capability_id: str,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
        request_body: str = "",
        deposit_atomic: int | None = None,
        ttl_s: int | None = None,
        voucher_nonce: int = 1,
        request_deadline: int | None = None,
        auto_execute: bool = True,
        auto_finalize: bool = False,
        allow_needs_approval: bool = False,
    ) -> dict:
        estimate = self.estimate_capability_budget(
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
        )
        decision = estimate["decision"]
        offer = estimate["offer"]

        if decision["action"] == "skip":
            return {
                "offer": offer,
                "budget": estimate["budget"],
                "decision": decision,
                "session": None,
                "payment": None,
            }
        if decision["action"] == "blocked":
            raise ValueError(decision["reason"])
        if decision["action"] == "needs_approval" and not allow_needs_approval:
            raise ValueError(decision["reason"])

        result = self.pay_route(
            route_path=offer["route_path"],
            method=offer["method"],
            request_body=request_body,
            deposit_atomic=deposit_atomic or decision.get("suggested_prepaid_atomic"),
            ttl_s=ttl_s,
            amount_atomic=decision["estimated_total_atomic"],
            voucher_nonce=voucher_nonce,
            request_deadline=request_deadline,
            auto_execute=auto_execute,
            auto_finalize=auto_finalize,
        )
        return {
            "offer": offer,
            "budget": estimate["budget"],
            "decision": decision,
            "session": result["session"],
            "payment": result["payment"],
        }

    def prepare_purchase(
        self,
        *,
        capability_type: str | None = None,
        capability_id: str | None = None,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
        deposit_atomic: int | None = None,
        ttl_s: int | None = None,
        allow_needs_approval: bool = False,
    ) -> dict:
        selection = self.select_capability_offer(
            capability_type=capability_type,
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
        )
        chosen = selection["selected"]
        decision = chosen["decision"]
        offer = chosen["offer"]
        if decision["action"] == "skip":
            return {
                "selection": selection,
                "offer": offer,
                "budget": chosen["budget"],
                "decision": decision,
                "session": None,
            }
        if decision["action"] == "needs_approval" and not allow_needs_approval:
            raise ValueError(decision["reason"])
        session = self.ensure_channel_for_route(
            route_path=offer["route_path"],
            method=offer["method"],
            deposit_atomic=deposit_atomic or decision.get("suggested_prepaid_atomic"),
            ttl_s=ttl_s,
        )
        return {
            "selection": selection,
            "offer": offer,
            "budget": chosen["budget"],
            "decision": decision,
            "session": session,
        }

    def submit_purchase(
        self,
        *,
        prepared_purchase: dict,
        request_body: str = "",
        voucher_nonce: int = 1,
        request_deadline: int | None = None,
        auto_execute: bool = True,
    ) -> dict:
        session = prepared_purchase.get("session")
        if session is None:
            raise ValueError("prepared_purchase does not include a channel session")
        offer = prepared_purchase["offer"]
        decision = prepared_purchase["decision"]
        payment = self.create_payment_intent(
            channel_session=session,
            route_path=offer["route_path"],
            method=offer["method"],
            request_body=request_body,
            amount_atomic=decision["estimated_total_atomic"],
            voucher_nonce=voucher_nonce,
            request_deadline=request_deadline,
        )
        if auto_execute:
            payment = self.execute_payment(payment["payment_id"])
        return {
            "offer": offer,
            "budget": prepared_purchase["budget"],
            "decision": decision,
            "session": session,
            "payment": payment,
        }

    def confirm_purchase(
        self,
        payment_id: str,
        *,
        max_attempts: int = 3,
        execute_if_needed: bool = True,
    ) -> dict:
        return self.finalize_payment(
            payment_id,
            max_attempts=max_attempts,
            execute_if_needed=execute_if_needed,
        )

    def pay_for_task(
        self,
        *,
        task_context: str,
        capability_type: str | None = None,
        capability_id: str | None = None,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
        request_body: str = "",
        deposit_atomic: int | None = None,
        ttl_s: int | None = None,
        voucher_nonce: int = 1,
        request_deadline: int | None = None,
        auto_execute: bool = True,
        auto_finalize: bool = False,
        allow_needs_approval: bool = False,
    ) -> dict:
        selection = self.select_capability_offer(
            capability_type=capability_type,
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
        )
        purchase = self.buy_capability(
            capability_id=selection["selected"]["offer"]["capability_id"],
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
            request_body=request_body,
            deposit_atomic=deposit_atomic,
            ttl_s=ttl_s,
            voucher_nonce=voucher_nonce,
            request_deadline=request_deadline,
            auto_execute=auto_execute,
            auto_finalize=auto_finalize,
            allow_needs_approval=allow_needs_approval,
        )
        return {
            "task_context": task_context,
            "selection": selection,
            "offer": purchase["offer"],
            "budget": purchase["budget"],
            "decision": purchase["decision"],
            "session": purchase["session"],
            "payment": purchase["payment"],
        }

    def ensure_channel_for_route(
        self,
        *,
        route_path: str,
        method: str = "POST",
        deposit_atomic: int | None = None,
        ttl_s: int | None = None,
    ) -> dict:
        manifest = self.fetch_manifest()
        self._resolve_route(manifest, route_path=route_path, method=method)
        open_url = manifest["endpoints"]["open_channel"]
        response = self._http().post(
            open_url,
            json={
                "buyer_address": self.wallet.address,
                "deposit_atomic": deposit_atomic,
                "ttl_s": ttl_s,
                "route_path": route_path,
                "channel_salt": f"0x{secrets.token_hex(32)}",
            },
        )
        response.raise_for_status()
        open_payload = response.json()
        provisioning = self.provisioner.provision(
            OpenChannelProvisionPlan(
                full_host=self._resolved_full_host(manifest=manifest),
                buyer_private_key=self.wallet.private_key,
                contract_address=open_payload["contract_address"],
                seller_address=open_payload["seller"],
                token_address=open_payload["token_address"],
                deposit_atomic=int(open_payload["deposit_atomic"]),
                expires_at=int(open_payload["expires_at"]),
                channel_salt=open_payload["channel_salt"],
            )
        )
        return _session_payload(route_path=route_path, open_payload=open_payload, provisioning=provisioning)

    def create_payment(
        self,
        *,
        channel_session: dict,
        route_path: str | None = None,
        method: str = "POST",
        request_body: str = "",
        amount_atomic: int | None = None,
        voucher_nonce: int = 1,
        request_deadline: int | None = None,
        payment_id: str | None = None,
        idempotency_key: str | None = None,
        request_path: str | None = None,
        request_digest: str | None = None,
        buyer_signature: str | None = None,
    ) -> dict:
        return self.create_payment_intent(
            channel_session=channel_session,
            route_path=route_path,
            method=method,
            request_body=request_body,
            amount_atomic=amount_atomic,
            voucher_nonce=voucher_nonce,
            request_deadline=request_deadline,
            payment_id=payment_id,
            idempotency_key=idempotency_key,
            request_path=request_path,
            request_digest=request_digest,
            buyer_signature=buyer_signature,
        )

    def create_payment_intent(
        self,
        *,
        channel_session: dict,
        route_path: str | None = None,
        method: str = "POST",
        request_body: str = "",
        amount_atomic: int | None = None,
        voucher_nonce: int = 1,
        request_deadline: int | None = None,
        payment_id: str | None = None,
        idempotency_key: str | None = None,
        request_path: str | None = None,
        request_digest: str | None = None,
        buyer_signature: str | None = None,
    ) -> dict:
        manifest = self.fetch_manifest()
        effective_route_path = route_path or channel_session.get("route_path")
        if effective_route_path:
            self._resolve_route(manifest, route_path=effective_route_path, method=method)
        payment_url = manifest["endpoints"]["create_payment_intent"]
        deadline = request_deadline or min(
            int(channel_session["expires_at"]),
            int(time.time()) + 120,
        )
        route = None
        if effective_route_path:
            route = self._resolve_route(manifest, route_path=effective_route_path, method=method)
        resolved_amount_atomic = amount_atomic
        if resolved_amount_atomic is None and route is not None:
            route_amount = route.get("price_atomic")
            if route_amount is not None:
                resolved_amount_atomic = int(route_amount)
        payment_auth = self._build_payment_auth(
            manifest=manifest,
            channel_session=channel_session,
            amount_atomic=resolved_amount_atomic,
            voucher_nonce=voucher_nonce,
            request_deadline=deadline,
            method=method,
            request_path=request_path or effective_route_path or "/",
            request_body=request_body,
            request_digest=request_digest,
            buyer_signature=buyer_signature,
        )
        response = self._http().post(
            payment_url,
            json={
                "payment_id": payment_id,
                "idempotency_key": idempotency_key,
                "route_path": effective_route_path,
                "amount_atomic": resolved_amount_atomic,
                "buyer_address": self.wallet.address,
                "channel_id": channel_session["channel_id"],
                "voucher_nonce": voucher_nonce,
                "expires_at": int(channel_session["expires_at"]),
                "request_deadline": deadline,
                "request_method": method,
                "request_path": request_path or effective_route_path,
                "request_body": request_body,
                "request_digest": payment_auth["request_digest"],
                "buyer_signature": payment_auth["buyer_signature"],
            },
        )
        response.raise_for_status()
        return response.json()

    def get_payment(self, payment_id: str) -> dict:
        return self.get_payment_status(payment_id)

    def get_payment_status(self, payment_id: str) -> dict:
        manifest = self.fetch_manifest()
        status_url = manifest["endpoints"]["payment_status_template"].format(payment_id=payment_id)
        response = self._http().get(status_url)
        response.raise_for_status()
        return response.json()

    def recover_payment(
        self,
        *,
        payment_id: str | None = None,
        idempotency_key: str | None = None,
        channel_id: str | None = None,
        statuses: list[str] | None = None,
    ) -> dict:
        manifest = self.fetch_manifest()
        params = {}
        if payment_id is not None:
            params["payment_id"] = payment_id
        if idempotency_key is not None:
            params["idempotency_key"] = idempotency_key
        if channel_id is not None:
            params["channel_id"] = channel_id
        if statuses:
            params["status_filter"] = ",".join(statuses)
        response = self._http().get(
            manifest["endpoints"]["recover_payments"],
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def list_pending_payments(self) -> dict:
        manifest = self.fetch_manifest()
        response = self._http().get(manifest["endpoints"]["list_pending_payments"])
        response.raise_for_status()
        return response.json()

    def get_merchant_agent_status(self, *, admin_token: str | None = None) -> dict:
        manifest = self.fetch_manifest()
        status_url = manifest["endpoints"].get("agent_status")
        if status_url is None:
            status_url = manifest["endpoints"]["management"].rstrip("/") + "/ops/agent-status"
        headers = {}
        if admin_token:
            headers["Authorization"] = f"Bearer {admin_token}"
        response = self._http().get(status_url, headers=headers)
        response.raise_for_status()
        return response.json()

    def reconcile_payment(self, payment_id: str) -> dict:
        manifest = self.fetch_manifest()
        reconcile_url = manifest["endpoints"]["reconcile_settlements"]
        response = self._http().post(reconcile_url, json={"payment_id": payment_id})
        response.raise_for_status()
        payload = response.json()
        payments = payload.get("payments") or []
        if not payments:
            raise RuntimeError("settlement reconciliation returned no payments")
        return payments[0]

    def finalize_payment(
        self,
        payment_id: str,
        *,
        max_attempts: int = 3,
        execute_if_needed: bool = True,
    ) -> dict:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        payment = self.get_payment_status(payment_id)
        attempts_remaining = max_attempts
        while attempts_remaining > 0:
            attempts_remaining -= 1
            status = payment.get("status")
            if status in {"settled", "failed", "expired"}:
                return payment
            if status in {"pending", "authorized"}:
                if not execute_if_needed:
                    return payment
                payment = self.execute_payment(payment_id)
                continue
            if status == "submitted":
                payment = self.reconcile_payment(payment_id)
                continue
            return payment
        return payment

    def execute_payment(self, payment_id: str) -> dict:
        manifest = self.fetch_manifest()
        settlement_url = manifest["endpoints"]["management"].rstrip("/") + "/settlements/execute"
        response = self._http().post(settlement_url, json={"payment_id": payment_id})
        response.raise_for_status()
        payload = response.json()
        payments = payload.get("payments") or []
        if not payments:
            raise RuntimeError("settlement execution returned no payments")
        return payments[0]

    def pay_route(
        self,
        *,
        route_path: str,
        method: str = "POST",
        request_body: str = "",
        deposit_atomic: int | None = None,
        ttl_s: int | None = None,
        amount_atomic: int | None = None,
        voucher_nonce: int = 1,
        request_deadline: int | None = None,
        auto_execute: bool = True,
        auto_finalize: bool = False,
    ) -> dict:
        session = self.ensure_channel_for_route(
            route_path=route_path,
            method=method,
            deposit_atomic=deposit_atomic,
            ttl_s=ttl_s,
        )
        payment = self.create_payment(
            channel_session=session,
            route_path=route_path,
            method=method,
            request_body=request_body,
            amount_atomic=amount_atomic,
            voucher_nonce=voucher_nonce,
            request_deadline=request_deadline,
        )
        if not auto_execute:
            return {"session": session, "payment": payment}
        executed_payment = self.execute_payment(payment["payment_id"])
        if auto_finalize:
            executed_payment = self.finalize_payment(executed_payment["payment_id"])
        return {"session": session, "payment": executed_payment}

    def request_paid_resource(
        self,
        path: str,
        *,
        method: str = "POST",
        json_body: dict | list | None = None,
        content: str | bytes | None = None,
        expected_units: int | None = 1,
        budget_limit_atomic: int | None = None,
        allow_needs_approval: bool = False,
        auto_finalize: bool = True,
    ) -> dict:
        """Call a paid HTTP resource, handle aimipay.http402.v1, pay, and retry."""

        normalized_method = method.upper()
        request_body = _request_body_for_payment(json_body=json_body, content=content)
        first_response = self._send_resource_request(
            path,
            method=normalized_method,
            json_body=json_body,
            content=content,
            headers=None,
        )
        if first_response.status_code != 402:
            return {
                "paid": False,
                "payment": None,
                "payment_required": None,
                "response": first_response,
                "payment_response": None,
            }

        payment_required = first_response.json()
        if payment_required.get("schema_version") != "aimipay.http402.v1":
            first_response.raise_for_status()
        requirement = _select_payment_requirement(payment_required)
        capability_id = requirement.get("capability_id")
        if not capability_id:
            raise ValueError("HTTP 402 payment requirement is missing capability_id")
        prepared = self.prepare_purchase(
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
            allow_needs_approval=allow_needs_approval,
        )
        submitted = self.submit_purchase(
            prepared_purchase=prepared,
            request_body=request_body,
            auto_execute=True,
        )
        payment = submitted["payment"]
        if auto_finalize:
            payment = self.finalize_payment(payment["payment_id"])
        payment_header = {
            "schema_version": "aimipay.payment-header.v1",
            "scheme": requirement.get("scheme", "aimipay-tron-v1"),
            "payment_id": payment["payment_id"],
            "resource": requirement.get("resource"),
            "amount_atomic": payment.get("amount_atomic"),
            "status": payment.get("status"),
        }
        retry_response = self._send_resource_request(
            path,
            method=normalized_method,
            json_body=json_body,
            content=content,
            headers={
                "X-PAYMENT": json.dumps(payment_header, separators=(",", ":")),
                "X-AIMIPAY-PAYMENT-ID": payment["payment_id"],
            },
        )
        retry_response.raise_for_status()
        payment_response = _decode_payment_response_header(retry_response.headers.get("x-payment-response"))
        return {
            "paid": True,
            "payment_required": payment_required,
            "payment": payment,
            "payment_header": payment_header,
            "response": retry_response,
            "payment_response": payment_response,
        }

    def _resolve_route(self, manifest: dict, *, route_path: str, method: str) -> dict:
        normalized_method = method.upper()
        for route in manifest.get("routes", []):
            if route.get("path") == route_path and str(route.get("method", "POST")).upper() == normalized_method:
                return route
        raise ValueError(f"route not found: {method} {route_path}")

    def _build_payment_auth(
        self,
        *,
        manifest: dict,
        channel_session: dict,
        amount_atomic: int | None,
        voucher_nonce: int,
        request_deadline: int,
        method: str,
        request_path: str,
        request_body: str,
        request_digest: str | None,
        buyer_signature: str | None,
    ) -> dict:
        if request_digest and buyer_signature:
            return {
                "request_digest": request_digest,
                "buyer_signature": buyer_signature,
            }
        if amount_atomic is None:
            raise ValueError("amount_atomic is required to build buyer payment authorization")
        chain_info = self._merchant_chain_context(manifest=manifest)
        settlement_backend = chain_info.get("settlement_backend")
        if settlement_backend == "local_smoke":
            return {
                "request_digest": request_digest,
                "buyer_signature": buyer_signature,
            }
        if settlement_backend != "claim_script":
            return {
                "request_digest": request_digest,
                "buyer_signature": buyer_signature,
            }
        chain_id = chain_info.get("chain_id") or channel_session.get("chain_id")
        if chain_id is None:
            raise ValueError("merchant manifest is missing chain_id required for buyer authorization")

        plan = {
            "full_host": self._resolved_full_host(manifest=manifest),
            "buyer_private_key": self.wallet.private_key,
            "chain_id": int(chain_id),
            "contract_address": channel_session["contract_address"],
            "channel_id": channel_session["channel_id"],
            "buyer_address": self.wallet.address,
            "seller_address": channel_session["seller_address"],
            "token_address": channel_session["token_address"],
            "amount_atomic": int(amount_atomic),
            "voucher_nonce": int(voucher_nonce),
            "expires_at": int(channel_session["expires_at"]),
            "request_deadline": int(request_deadline),
            "method": method,
            "path": request_path,
            "body": request_body,
        }
        if request_digest:
            plan["request_digest"] = request_digest
        voucher = build_payment_voucher(
            buyer_private_key=plan["buyer_private_key"],
            chain_id=int(plan["chain_id"]),
            contract_address=plan["contract_address"],
            channel_id=plan["channel_id"],
            buyer_address=plan["buyer_address"],
            seller_address=plan["seller_address"],
            token_address=plan["token_address"],
            amount_atomic=int(plan["amount_atomic"]),
            voucher_nonce=int(plan["voucher_nonce"]),
            expires_at=int(plan["expires_at"]),
            request_deadline=int(plan["request_deadline"]),
            method=str(plan["method"]),
            path=str(plan["path"]),
            body=str(plan["body"]),
            request_digest=plan.get("request_digest"),
        )
        return {
            "request_digest": voucher.request_digest,
            "voucher_digest": voucher.voucher_digest,
            "buyer_signature": voucher.buyer_signature,
        }

    def _resolved_full_host(self, *, manifest: dict | None = None) -> str:
        if self.full_host:
            return self.full_host
        chain_info = self._merchant_chain_context(manifest=manifest)
        network_name = chain_info.get("network") or chain_info.get("network_name")
        resolved = resolve_full_host_for_network(network_name=network_name)
        if resolved:
            return resolved
        raise ValueError("Unable to resolve full_host from merchant network metadata")

    def _merchant_chain_context(self, *, manifest: dict | None = None) -> dict:
        manifest_payload = manifest or self.fetch_manifest()
        manifest_chain = dict(manifest_payload.get("primary_chain") or {})
        discover_payload = self.discover()
        discover_chain = {
            "chain": discover_payload.get("chain", manifest_chain.get("chain", "tron")),
            "chain_id": discover_payload.get("chain_id", manifest_chain.get("chain_id")),
            "settlement_backend": discover_payload.get(
                "settlement_backend",
                manifest_chain.get("settlement_backend"),
            ),
            "seller_address": discover_payload.get("seller", manifest_chain.get("seller_address")),
            "contract_address": discover_payload.get(
                "contract_address",
                manifest_chain.get("contract_address"),
            ),
            "token_address": discover_payload.get(
                "token_address",
                manifest_chain.get("asset_address"),
            ),
        }
        return {**manifest_chain, **{key: value for key, value in discover_chain.items() if value is not None}}

    def _estimate_offer(
        self,
        *,
        offer: dict,
        expected_units: int | None,
        budget_limit_atomic: int | None,
    ) -> dict:
        budget_hint = offer.get("budget_hint") or {}
        units = expected_units
        if units is None:
            units = budget_hint.get("typical_units") or budget_hint.get("min_units") or 1
        unit_amount_atomic = int(offer["amount_atomic"])
        estimated_total_atomic = unit_amount_atomic * int(units)
        suggested_prepaid_atomic = budget_hint.get("suggested_prepaid_atomic") or estimated_total_atomic
        if offer.get("suggested_prepaid_atomic") is not None:
            suggested_prepaid_atomic = offer["suggested_prepaid_atomic"]

        if budget_limit_atomic is not None and estimated_total_atomic > budget_limit_atomic:
            action = "needs_approval"
            reason = "estimated cost exceeds budget limit"
        elif offer.get("requires_human_approval"):
            action = "needs_approval"
            reason = "merchant requires human approval for this offer"
        elif not offer.get("supports_auto_purchase", True):
            action = "needs_approval"
            reason = "merchant does not support auto purchase for this offer"
        elif estimated_total_atomic == 0:
            action = "skip"
            reason = "capability has zero estimated cost"
        else:
            action = "buy_now"
            reason = "estimated cost is within budget"

        estimate = {
            "budget": {
                "capability_id": offer["capability_id"],
                "units": int(units),
                "unit_amount_atomic": unit_amount_atomic,
                "estimated_total_atomic": estimated_total_atomic,
                "suggested_prepaid_atomic": suggested_prepaid_atomic,
                "pricing_model": offer["pricing_model"],
                "usage_unit": offer["usage_unit"],
                "notes": budget_hint.get("notes"),
            },
            "decision": {
                "capability_id": offer["capability_id"],
                "action": action,
                "reason": reason,
                "estimated_total_atomic": estimated_total_atomic,
                "suggested_prepaid_atomic": suggested_prepaid_atomic,
                "seller_address": offer["seller_address"],
                "route_path": offer["route_path"],
            },
            "offer": offer,
        }
        policy_evaluation = self.evaluate_budget_policy(estimate=estimate)
        if policy_evaluation["action"] != estimate["decision"]["action"]:
            estimate["decision"]["action"] = policy_evaluation["action"]
            if policy_evaluation["action"] == "blocked":
                estimate["decision"]["reason"] = "buyer budget policy blocked this purchase"
            else:
                estimate["decision"]["reason"] = "buyer budget policy requires approval"
        estimate["decision"]["budget_policy"] = policy_evaluation
        return estimate

    def evaluate_budget_policy(self, *, estimate: dict) -> dict:
        policy = self.budget_policy
        decision = estimate.get("decision") or {}
        seller_address = str(decision.get("seller_address") or "")
        estimated_total_atomic = int(decision.get("estimated_total_atomic") or 0)
        violations: list[dict[str, object]] = []
        if policy is not None:
            if seller_address and seller_address in policy.blocked_sellers:
                violations.append({"code": "seller_blocked", "severity": "block"})
            if (
                policy.require_approval_for_untrusted
                and seller_address
                and policy.trusted_sellers
                and seller_address not in policy.trusted_sellers
            ):
                violations.append({"code": "seller_untrusted", "severity": "approval"})
            if policy.per_purchase_limit_atomic is not None and estimated_total_atomic > policy.per_purchase_limit_atomic:
                violations.append(
                    {
                        "code": "per_purchase_limit_exceeded",
                        "severity": "approval",
                        "limit_atomic": policy.per_purchase_limit_atomic,
                    }
                )
            if policy.require_approval_above_atomic is not None and estimated_total_atomic > policy.require_approval_above_atomic:
                violations.append(
                    {
                        "code": "approval_threshold_exceeded",
                        "severity": "approval",
                        "limit_atomic": policy.require_approval_above_atomic,
                    }
                )
            if policy.daily_limit_atomic is not None and self.spent_today_atomic + estimated_total_atomic > policy.daily_limit_atomic:
                violations.append(
                    {
                        "code": "daily_limit_exceeded",
                        "severity": "approval",
                        "limit_atomic": policy.daily_limit_atomic,
                        "spent_today_atomic": self.spent_today_atomic,
                    }
                )
        action = decision.get("action")
        if any(item["severity"] == "block" for item in violations):
            action = "blocked"
        elif violations and action == "buy_now":
            action = "needs_approval"
        return {
            "schema_version": "aimipay.buyer-budget-policy-evaluation.v1",
            "policy_name": "none" if policy is None else policy.policy_name,
            "action": action,
            "violations": violations,
        }

    def _http(self) -> httpx.Client:
        if self.http_client is not None:
            return self.http_client
        self.http_client = httpx.Client(
            base_url=self.merchant_base_url.rstrip("/"),
            trust_env=_should_trust_env(self.merchant_base_url),
        )
        return self.http_client

    def _url(self, path: str) -> str:
        return urljoin(f"{self.merchant_base_url.rstrip('/')}/", path.lstrip("/"))

    def _send_resource_request(
        self,
        path: str,
        *,
        method: str,
        json_body: dict | list | None,
        content: str | bytes | None,
        headers: dict[str, str] | None,
    ):
        kwargs = {"headers": headers or {}}
        if json_body is not None:
            kwargs["json"] = json_body
        elif content is not None:
            kwargs["content"] = content
        return self._http().request(method, self._url(path), **kwargs)


def _session_payload(*, route_path: str, open_payload: dict, provisioning: OpenChannelExecution) -> dict:
    return {
        "route_path": route_path,
        "channel_id": provisioning.channel_id,
        "chain_id": open_payload.get("chain_id"),
        "buyer_address": provisioning.buyer_address,
        "seller_address": provisioning.seller_address,
        "contract_address": provisioning.contract_address,
        "token_address": provisioning.token_address,
        "deposit_atomic": provisioning.deposit_atomic,
        "expires_at": provisioning.expires_at,
        "channel_salt": provisioning.channel_salt,
        "approve_tx_id": provisioning.approve_tx_id,
        "open_tx_id": provisioning.open_tx_id,
    }
def _decision_rank(action: str) -> int:
    return {
        "buy_now": 0,
        "needs_approval": 1,
        "skip": 2,
    }.get(action, 99)


def _should_trust_env(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host not in {"127.0.0.1", "localhost", "::1"}


def _request_body_for_payment(*, json_body: dict | list | None, content: str | bytes | None) -> str:
    if json_body is not None:
        return json.dumps(json_body, separators=(",", ":"), sort_keys=True)
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    return content or ""


def _select_payment_requirement(payload: dict) -> dict:
    accepts = payload.get("accepts") or []
    if not accepts:
        raise ValueError("HTTP 402 payment requirement has no accepts entries")
    for requirement in accepts:
        if requirement.get("scheme") == "aimipay-tron-v1":
            return requirement
    return accepts[0]


def _decode_payment_response_header(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}

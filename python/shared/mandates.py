from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time

from .models import AgentIntentMandate, AgentPaymentMandate


def create_intent_mandate(
    *,
    buyer_address: str,
    merchant_base_url: str,
    capability_id: str,
    max_amount_atomic: int,
    expires_at: int,
    secret: str | None = None,
    asset_symbol: str = "USDT",
    human_approval_required: bool = False,
    reason: str | None = None,
) -> AgentIntentMandate:
    mandate = AgentIntentMandate(
        mandate_id=f"im_{secrets.token_hex(16)}",
        buyer_address=buyer_address,
        merchant_base_url=merchant_base_url,
        capability_id=capability_id,
        max_amount_atomic=max_amount_atomic,
        asset_symbol=asset_symbol,
        expires_at=expires_at,
        human_approval_required=human_approval_required,
        reason=reason,
        created_at=int(time.time()),
    )
    if secret:
        mandate.signature = sign_mandate(mandate.model_dump(mode="json", exclude={"signature"}), secret=secret)
    return mandate


def create_payment_mandate(
    *,
    intent_mandate: AgentIntentMandate,
    payment_id: str,
    seller_address: str,
    route_path: str,
    amount_atomic: int,
    expires_at: int,
    secret: str | None = None,
) -> AgentPaymentMandate:
    if amount_atomic > intent_mandate.max_amount_atomic:
        raise ValueError("payment amount exceeds intent mandate maximum")
    mandate = AgentPaymentMandate(
        mandate_id=f"pm_{secrets.token_hex(16)}",
        intent_mandate_id=intent_mandate.mandate_id,
        payment_id=payment_id,
        buyer_address=intent_mandate.buyer_address,
        seller_address=seller_address,
        route_path=route_path,
        amount_atomic=amount_atomic,
        asset_symbol=intent_mandate.asset_symbol,
        expires_at=expires_at,
        created_at=int(time.time()),
    )
    if secret:
        mandate.signature = sign_mandate(mandate.model_dump(mode="json", exclude={"signature"}), secret=secret)
    return mandate


def mandate_hash(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def sign_mandate(payload: dict, *, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), _canonical(payload), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_mandate_signature(payload: dict, *, secret: str, signature: str | None) -> bool:
    if not signature:
        return False
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    expected = sign_mandate(unsigned, secret=secret)
    return hmac.compare_digest(expected, signature)


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

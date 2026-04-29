from __future__ import annotations

import base64
import json
from typing import Any


X402_VERSION = 1
X402_PAYMENT_HEADER = "X-PAYMENT"
X402_PAYMENT_RESPONSE_HEADER = "X-PAYMENT-RESPONSE"


def build_x402_payment_requirement(
    *,
    scheme: str,
    network: str,
    asset: str,
    asset_symbol: str,
    pay_to: str,
    amount_atomic: int,
    resource: str,
    description: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "scheme": scheme,
        "network": network,
        "asset": asset,
        "asset_symbol": asset_symbol,
        "payTo": pay_to,
        "maxAmountRequired": str(amount_atomic),
        "resource": resource,
        "description": description,
        "mimeType": "application/json",
        "extra": extra or {},
    }


def encode_x402_payment(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_x402_payment(value: str) -> dict[str, Any]:
    candidate = value.strip()
    if candidate.startswith("{"):
        return json.loads(candidate)
    padded = candidate + "=" * (-len(candidate) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {"payment_id": candidate}


def build_x402_payment_response(
    *,
    payment_id: str,
    success: bool,
    tx_id: str | None = None,
    network: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "paymentId": payment_id,
        "transaction": tx_id,
        "network": network,
        "extra": extra or {},
    }

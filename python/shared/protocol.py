from __future__ import annotations

from typing import Any

from .errors import DEFAULT_ERROR_CONTRACTS
from .models import PaymentRecord

PAYMENT_STATUS_FLOW = (
    "pending",
    "authorized",
    "submitted",
    "settled",
    "failed",
    "expired",
)

TERMINAL_PAYMENT_STATUSES = frozenset({"settled", "failed", "expired"})
RECOVERABLE_PAYMENT_STATUSES = frozenset({"pending", "authorized", "submitted"})

PAYMENT_ERROR_CODES: dict[str, dict[str, Any]] = DEFAULT_ERROR_CONTRACTS


def build_protocol_reference() -> dict[str, Any]:
    return {
        "protocol_version": "aimipay-tron-v1",
        "channel_id": {
            "single_source": "scripts/protocol.js::channelIdOf",
            "rule": "keccak256(abi.encodePacked(normalized_buyer, normalized_seller, normalized_token))",
            "address_normalization": "normalize to EVM hex address before hashing",
        },
        "request_digest": {
            "single_source": "scripts/protocol.js::buildRequestDigest",
            "fields": ["method", "path", "request_deadline", "body_hash"],
            "body_hash": "sha256 over raw request body bytes",
        },
        "voucher_digest": {
            "single_source": "scripts/protocol.js::voucherDigest",
            "field_order": [
                "voucher_domain",
                "chain_id",
                "contract_address",
                "channel_id",
                "buyer",
                "seller",
                "token",
                "amount_atomic",
                "voucher_nonce",
                "expires_at",
                "request_deadline",
                "request_digest",
            ],
            "encoding": "Solidity ABI encoding aligned with contracts/AimiMicropayChannel.sol",
        },
        "signature": {
            "algorithm": "secp256k1 / ECDSA",
            "payload": "voucher_digest",
            "single_source": "scripts/protocol.js::signDigest",
        },
        "time_fields": {
            "expires_at": "channel expiry; channel cannot be claimed after this time",
            "request_deadline": "request authorization expiry; gateway, settlement, and contract all reject after deadline",
        },
        "payment_status_flow": list(PAYMENT_STATUS_FLOW),
        "error_codes": PAYMENT_ERROR_CODES,
    }


def build_payment_lifecycle(record: PaymentRecord) -> dict[str, Any]:
    if record.status == "pending":
        return {
            "action_required": "build_or_verify_authorization",
            "next_step": "create_payment_intent",
            "safe_to_retry": True,
            "human_approval_required": False,
        }
    if record.status == "authorized":
        return {
            "action_required": None,
            "next_step": "execute_settlement",
            "safe_to_retry": True,
            "human_approval_required": False,
        }
    if record.status == "submitted":
        return {
            "action_required": None,
            "next_step": "confirm_settlement",
            "safe_to_retry": False,
            "human_approval_required": False,
        }
    if record.status == "settled":
        return {
            "action_required": None,
            "next_step": None,
            "safe_to_retry": False,
            "human_approval_required": False,
        }
    if record.status == "expired":
        return {
            "action_required": "create_new_payment_intent",
            "next_step": "prepare_or_open_channel",
            "safe_to_retry": False,
            "human_approval_required": False,
        }
    retryable = False
    if record.error_retryable is not None:
        retryable = bool(record.error_retryable)
    elif record.error_code:
        retryable = bool(PAYMENT_ERROR_CODES.get(record.error_code, {}).get("retryable"))
    return {
        "action_required": "recover_payment",
        "next_step": "recover_unfinished_payment",
        "safe_to_retry": retryable,
        "human_approval_required": False,
    }

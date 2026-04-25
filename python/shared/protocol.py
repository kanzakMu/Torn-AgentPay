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
            "rule": "keccak256(abi.encodePacked(normalized_buyer, normalized_seller, normalized_token, channel_salt))",
            "address_normalization": "normalize to EVM hex address before hashing",
            "channel_salt": "32-byte buyer-generated random value unique per opened channel",
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
        "agent_facing_protocol": {
            "schema_version": "aimipay.agent-protocol.v1",
            "kinds": [
                "agent_state",
                "capability_catalog",
                "budget_quote",
                "purchase_plan",
                "payment_state",
                "payment_recovery",
            ],
            "tool_mapping": {
                "state": "aimipay.get_agent_state",
                "capabilities": "aimipay.list_offers",
                "budget": "aimipay.quote_budget",
                "decision": "aimipay.plan_purchase",
                "payment_lifecycle": "aimipay.get_payment_status",
                "error_recovery": "aimipay.recover_payment",
            },
            "decision_actions": ["buy_now", "needs_approval", "skip"],
            "next_action_contract": "Each AI-facing payload includes next_actions with action, optional tool, and reason.",
        },
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


def agent_protocol_envelope(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "aimipay.agent-protocol.v1",
        "kind": kind,
        **payload,
    }


def capability_catalog_payload(*, offers: list[dict[str, Any]]) -> dict[str, Any]:
    return agent_protocol_envelope(
        "capability_catalog",
        {
            "capabilities": offers,
            "summary": {
                "count": len(offers),
                "auto_purchasable_count": len(
                    [
                        offer
                        for offer in offers
                        if offer.get("supports_auto_purchase", True)
                        and not offer.get("requires_human_approval", False)
                    ]
                ),
            },
            "next_actions": [
                {
                    "action": "quote_budget",
                    "tool": "aimipay.quote_budget",
                    "reason": "estimate cost before opening a payment channel",
                }
            ],
        },
    )


def budget_quote_payload(*, estimate: dict[str, Any]) -> dict[str, Any]:
    decision = estimate.get("decision") or {}
    action = decision.get("action")
    next_action = {
        "skip": "use_without_payment",
        "buy_now": "prepare_purchase",
        "needs_approval": "request_human_approval",
    }.get(action, "review_budget")
    return agent_protocol_envelope(
        "budget_quote",
        {
            **estimate,
            "estimated_cost_atomic": (estimate.get("budget") or {}).get("estimated_total_atomic", 0),
            "human_approval_required": action == "needs_approval",
            "auto_decision": {
                "action": action,
                "allowed": action == "buy_now",
                "reason": decision.get("reason"),
            },
            "next_actions": [
                {
                    "action": next_action,
                    "tool": "aimipay.prepare_purchase" if action == "buy_now" else None,
                    "reason": decision.get("reason"),
                }
            ],
        },
    )


def payment_state_payload(*, payment: dict[str, Any]) -> dict[str, Any]:
    next_step = payment.get("next_step")
    recovery = {
        "recoverable": payment.get("status") in RECOVERABLE_PAYMENT_STATUSES
        or bool(payment.get("safe_to_retry")),
        "tool": "aimipay.finalize_payment"
        if payment.get("status") in {"authorized", "submitted"}
        else "aimipay.recover_payment",
        "safe_to_retry": bool(payment.get("safe_to_retry", False)),
    }
    return agent_protocol_envelope(
        "payment_state",
        {
            "payment": payment,
            "lifecycle": {
                "status": payment.get("status"),
                "terminal": payment.get("status") in TERMINAL_PAYMENT_STATUSES,
                "next_step": next_step,
                "action_required": payment.get("action_required"),
            },
            "recovery": recovery,
            "next_actions": [
                {
                    "action": next_step or "none",
                    "tool": _tool_for_payment_next_step(next_step),
                    "reason": payment.get("status_reason") or payment.get("error_message"),
                }
            ],
        },
    )


def recovery_payload(*, payments: list[dict[str, Any]], source: str) -> dict[str, Any]:
    return agent_protocol_envelope(
        "payment_recovery",
        {
            "source": source,
            "count": len(payments),
            "payments": payments,
            "recoverable_count": len(
                [
                    payment
                    for payment in payments
                    if payment.get("status") in RECOVERABLE_PAYMENT_STATUSES
                    or bool(payment.get("safe_to_retry"))
                ]
            ),
            "next_actions": [
                {
                    "action": "finalize_payment",
                    "tool": "aimipay.finalize_payment",
                    "payment_id": payment.get("payment_id"),
                    "reason": payment.get("next_step") or "unfinished payment can be driven forward",
                }
                for payment in payments[:10]
                if payment.get("status") in RECOVERABLE_PAYMENT_STATUSES
            ],
        },
    )


def agent_state_payload(
    *,
    merchant_status: dict[str, Any],
    offers: list[dict[str, Any]],
    pending: dict[str, Any],
) -> dict[str, Any]:
    readiness = merchant_status.get("readiness") or {}
    next_actions = list(merchant_status.get("next_actions") or [])
    if offers and readiness.get("ready"):
        next_actions.append(
            {
                "action": "quote_budget",
                "tool": "aimipay.quote_budget",
                "reason": "merchant is ready and capabilities are available",
            }
        )
    return agent_protocol_envelope(
        "agent_state",
        {
            "merchant": merchant_status,
            "capability_catalog": {
                "count": len(offers),
                "capabilities": offers,
            },
            "payments": pending,
            "next_actions": next_actions,
        },
    )


def _tool_for_payment_next_step(next_step: str | None) -> str | None:
    return {
        "create_payment_intent": "aimipay.create_payment",
        "execute_settlement": "aimipay.execute_payment",
        "confirm_settlement": "aimipay.reconcile_payment",
        "recover_unfinished_payment": "aimipay.recover_payment",
        "prepare_or_open_channel": "aimipay.prepare_purchase",
    }.get(next_step or "")

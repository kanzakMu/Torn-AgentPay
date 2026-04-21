from __future__ import annotations

from typing import Any

DEFAULT_ERROR_CONTRACTS: dict[str, dict[str, Any]] = {
    "request_deadline_expired": {
        "message": "request deadline expired before settlement",
        "retryable": False,
    },
    "payment_expired": {
        "message": "payment expired before settlement",
        "retryable": False,
    },
    "settlement_execution_failed": {
        "message": "settlement execution failed",
        "retryable": True,
    },
    "settlement_confirmation_failed": {
        "message": "settlement confirmation failed",
        "retryable": True,
    },
    "settlement_confirmation_retry_exhausted": {
        "message": "settlement confirmation retry budget exhausted",
        "retryable": False,
    },
    "settlement_transaction_reverted": {
        "message": "settlement transaction reverted on chain",
        "retryable": False,
    },
    "settlement_tx_missing": {
        "message": "submitted payment is missing a transaction id",
        "retryable": False,
    },
    "idempotency_conflict": {
        "message": "idempotency key conflicts with an existing payment",
        "retryable": False,
    },
    "amount_required": {
        "message": "amount_atomic is required when route price is not configured",
        "retryable": False,
    },
    "missing_buyer_authorization": {
        "message": "request_digest and buyer_signature are required for claim_script settlement backend",
        "retryable": False,
    },
    "payment_not_found": {
        "message": "payment not found",
        "retryable": False,
    },
    "settlement_not_configured": {
        "message": "settlement not configured",
        "retryable": False,
    },
    "unsupported_chain": {
        "message": "unsupported chain for settlement",
        "retryable": False,
    },
    "missing_settlement_fields": {
        "message": "payment record missing settlement fields",
        "retryable": False,
    },
    "manual_intervention_required": {
        "message": "payment requires manual intervention",
        "retryable": False,
    },
    "manual_compensation_recorded": {
        "message": "manual compensation recorded for payment",
        "retryable": False,
    },
    "unknown_mcp_tool": {
        "message": "unknown MCP tool",
        "retryable": False,
    },
    "mcp_invalid_params": {
        "message": "invalid MCP params",
        "retryable": False,
    },
    "mcp_method_not_found": {
        "message": "method not supported",
        "retryable": False,
    },
    "mcp_parse_error": {
        "message": "invalid JSON input",
        "retryable": False,
    },
    "internal_error": {
        "message": "internal error",
        "retryable": False,
    },
}


class AimiPayError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        self.status_code = status_code


def error_contract(code: str) -> dict[str, Any]:
    return DEFAULT_ERROR_CONTRACTS.get(
        code,
        {
            "message": code.replace("_", " "),
            "retryable": False,
        },
    )


def aimipay_error(
    code: str,
    *,
    message: str | None = None,
    retryable: bool | None = None,
    details: dict[str, Any] | None = None,
    status_code: int | None = None,
) -> AimiPayError:
    contract = error_contract(code)
    return AimiPayError(
        code,
        message or str(contract["message"]),
        retryable=bool(contract["retryable"] if retryable is None else retryable),
        details=details,
        status_code=status_code,
    )


def coerce_error(
    exc: Exception,
    *,
    default_code: str = "internal_error",
    status_code: int | None = None,
    details: dict[str, Any] | None = None,
) -> AimiPayError:
    if isinstance(exc, AimiPayError):
        return exc
    return aimipay_error(
        default_code,
        message=str(exc),
        status_code=status_code,
        details=details,
    )


def error_payload(
    code: str | AimiPayError,
    message: str | None = None,
    *,
    retryable: bool | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if isinstance(code, AimiPayError):
        exc = code
        return {
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                **({"details": exc.details} if exc.details else {}),
            }
        }
    contract = error_contract(code)
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message or str(contract["message"]),
            "retryable": bool(contract["retryable"] if retryable is None else retryable),
        }
    }
    if details:
        payload["error"]["details"] = details
    return payload

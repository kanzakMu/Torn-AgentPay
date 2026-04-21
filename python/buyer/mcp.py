from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, TextIO

from shared import AimiPayError, aimipay_error, coerce_error, error_payload

from .adapter import AimiPayAgentAdapter
from .runtime import AgentPaymentsRuntime


@dataclass(slots=True)
class AimiPayMcpServer:
    runtime: AgentPaymentsRuntime
    server_name: str = "aimipay-tron"
    server_version: str = "0.1.0"
    startup_onboarding: dict[str, Any] | None = None

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            _tool(
                "aimipay.list_offers",
                "List merchant capability offers for agent selection.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                    },
                },
            ),
            _tool(
                "aimipay.estimate_budget",
                "Estimate total cost for a capability before purchase.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                        "capability_id": {"type": "string"},
                        "expected_units": {"type": "integer"},
                        "budget_limit_atomic": {"type": "integer"},
                    },
                    "required": ["capability_id"],
                },
            ),
            _tool(
                "aimipay.open_channel",
                "Prepare or open a payment channel for a paid route.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                        "route_path": {"type": "string"},
                        "method": {"type": "string"},
                        "deposit_atomic": {"type": "integer"},
                        "ttl_s": {"type": "integer"},
                    },
                    "required": ["route_path"],
                },
            ),
            _tool(
                "aimipay.create_payment",
                "Create a payment intent for a prepared channel session.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                        "channel_session": {"type": "object"},
                        "route_path": {"type": "string"},
                        "method": {"type": "string"},
                        "request_body": {"type": "string"},
                        "amount_atomic": {"type": "integer"},
                        "voucher_nonce": {"type": "integer"},
                        "request_deadline": {"type": "integer"},
                        "payment_id": {"type": "string"},
                        "idempotency_key": {"type": "string"},
                        "request_path": {"type": "string"},
                    },
                    "required": ["channel_session"],
                },
            ),
            _tool(
                "aimipay.execute_payment",
                "Execute settlement for a payment intent.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                        "payment_id": {"type": "string"},
                    },
                    "required": ["payment_id"],
                },
            ),
            _tool(
                "aimipay.get_payment_status",
                "Get the current payment lifecycle status.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                        "payment_id": {"type": "string"},
                    },
                    "required": ["payment_id"],
                },
            ),
            _tool(
                "aimipay.reconcile_payment",
                "Confirm a submitted payment against the settlement backend.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                        "payment_id": {"type": "string"},
                    },
                    "required": ["payment_id"],
                },
            ),
            _tool(
                "aimipay.finalize_payment",
                "Drive a payment through execute/reconcile until it reaches a terminal state or attempts are exhausted.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                        "payment_id": {"type": "string"},
                        "max_attempts": {"type": "integer"},
                        "execute_if_needed": {"type": "boolean"},
                    },
                    "required": ["payment_id"],
                },
            ),
            _tool(
                "aimipay.list_pending_payments",
                "List unfinished payments that may need recovery.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                    },
                },
            ),
            _tool(
                "aimipay.recover_payment",
                "Recover unfinished payments by payment_id, idempotency_key, or channel_id.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_base_url": {"type": "string"},
                        "payment_id": {"type": "string"},
                        "idempotency_key": {"type": "string"},
                        "channel_id": {"type": "string"},
                        "statuses": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            ),
            _tool(
                "aimipay.check_wallet_funding",
                "Inspect whether the installed buyer wallet exists and looks ready for local or live Tron purchases.",
                {
                    "type": "object",
                    "properties": {
                        "env_file": {"type": "string"},
                    },
                },
            ),
            _tool(
                "aimipay.create_wallet",
                "Create a local Tron buyer wallet, save it into env files, and return the next onboarding step.",
                {
                    "type": "object",
                    "properties": {
                        "env_file": {"type": "string"},
                        "wallet_file": {"type": "string"},
                        "force_create": {"type": "boolean"},
                    },
                },
            ),
            _tool(
                "aimipay.run_onboarding",
                "Run the first-start onboarding workflow: ensure a wallet exists, inspect funding readiness, and save an onboarding report.",
                {
                    "type": "object",
                    "properties": {
                        "env_file": {"type": "string"},
                        "wallet_file": {"type": "string"},
                        "force_create_wallet": {"type": "boolean"},
                    },
                },
            ),
            _tool(
                "aimipay.set_merchant_url",
                "Save the merchant URL for buyer onboarding, then rerun startup onboarding and offer discovery.",
                {
                    "type": "object",
                    "properties": {
                        "merchant_url": {"type": "string"},
                        "env_file": {"type": "string"},
                        "network_profile": {"type": "string"},
                    },
                    "required": ["merchant_url"],
                },
            ),
            _tool(
                "aimipay.get_startup_onboarding",
                "Return the onboarding summary that was prepared when the MCP server started.",
                {
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        args = arguments or {}
        adapter = self._adapter(args.get("merchant_base_url"))
        if name == "aimipay.list_offers":
            return adapter.list_offers()
        if name == "aimipay.estimate_budget":
            return adapter.estimate_budget(
                capability_id=args["capability_id"],
                expected_units=args.get("expected_units"),
                budget_limit_atomic=args.get("budget_limit_atomic"),
            )
        if name == "aimipay.open_channel":
            return adapter.open_channel(
                route_path=args["route_path"],
                method=args.get("method", "POST"),
                deposit_atomic=args.get("deposit_atomic"),
                ttl_s=args.get("ttl_s"),
            )
        if name == "aimipay.create_payment":
            return adapter.create_payment(
                channel_session=args["channel_session"],
                route_path=args.get("route_path"),
                method=args.get("method", "POST"),
                request_body=args.get("request_body", ""),
                amount_atomic=args.get("amount_atomic"),
                voucher_nonce=args.get("voucher_nonce", 1),
                request_deadline=args.get("request_deadline"),
                payment_id=args.get("payment_id"),
                idempotency_key=args.get("idempotency_key"),
                request_path=args.get("request_path"),
            )
        if name == "aimipay.execute_payment":
            return adapter.execute_payment(args["payment_id"])
        if name == "aimipay.get_payment_status":
            return adapter.get_payment_status(args["payment_id"])
        if name == "aimipay.reconcile_payment":
            return adapter.reconcile_payment(args["payment_id"])
        if name == "aimipay.finalize_payment":
            return adapter.finalize_payment(
                args["payment_id"],
                max_attempts=args.get("max_attempts", 3),
                execute_if_needed=args.get("execute_if_needed", True),
            )
        if name == "aimipay.list_pending_payments":
            return adapter.list_pending_payments()
        if name == "aimipay.recover_payment":
            return adapter.recover_payment(
                payment_id=args.get("payment_id"),
                idempotency_key=args.get("idempotency_key"),
                channel_id=args.get("channel_id"),
                statuses=args.get("statuses"),
            )
        if name == "aimipay.check_wallet_funding":
            return adapter.check_wallet_funding(env_file=args.get("env_file"))
        if name == "aimipay.create_wallet":
            return adapter.create_wallet(
                env_file=args.get("env_file"),
                wallet_file=args.get("wallet_file"),
                force_create=args.get("force_create", False),
            )
        if name == "aimipay.run_onboarding":
            return adapter.run_onboarding(
                env_file=args.get("env_file"),
                wallet_file=args.get("wallet_file"),
                force_create_wallet=args.get("force_create_wallet", False),
            )
        if name == "aimipay.set_merchant_url":
            return adapter.set_merchant_url(
                merchant_url=args["merchant_url"],
                env_file=args.get("env_file"),
                network_profile=args.get("network_profile"),
            )
        if name == "aimipay.get_startup_onboarding":
            return self._startup_onboarding_payload()
        raise aimipay_error("unknown_mcp_tool", details={"tool_name": name})

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        method = request.get("method")
        request_id = request.get("id")
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": self.server_name,
                        "version": self.server_version,
                    },
                    "instructions": self._startup_onboarding_instructions(),
                    "meta": {
                        "aimipay/startupOnboarding": self._startup_onboarding_payload(),
                        "aimipay/startupCard": self._startup_card_payload(),
                    },
                }
            elif method in {"initialized", "notifications/initialized"}:
                result = {}
            elif method == "tools/list":
                result = {"tools": self.list_tools()}
            elif method == "tools/call":
                params = request.get("params") or {}
                tool_name = params.get("name")
                if not tool_name:
                    raise aimipay_error("mcp_invalid_params", details={"missing": ["name"]})
                try:
                    result_payload = self.call_tool(tool_name, params.get("arguments") or {})
                    result = {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result_payload, ensure_ascii=True),
                            }
                        ],
                        "structuredContent": result_payload,
                        "isError": False,
                    }
                except Exception as exc:
                    if isinstance(exc, KeyError):
                        contract_error = aimipay_error(
                            "mcp_invalid_params",
                            message=f"missing required tool argument: {exc.args[0]}",
                            details={"missing_argument": exc.args[0], "tool_name": tool_name},
                        )
                    else:
                        contract_error = coerce_error(exc)
                    result = {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(error_payload(contract_error), ensure_ascii=True),
                            }
                        ],
                        "structuredContent": error_payload(contract_error),
                        "isError": True,
                    }
            else:
                raise aimipay_error(
                    "mcp_method_not_found",
                    message=f"method not supported: {method}",
                    details={"method": method},
                )
            return _response(request_id, result, jsonrpc=request.get("jsonrpc"))
        except AimiPayError as exc:
            return _error_response(
                request_id,
                code=_jsonrpc_code(exc.code),
                message=exc.message,
                data=error_payload(exc),
                jsonrpc=request.get("jsonrpc"),
            )

    def serve_stdio(self, *, in_stream: TextIO | None = None, out_stream: TextIO | None = None) -> None:
        source = in_stream or sys.stdin
        sink = out_stream or sys.stdout
        for line in source:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as exc:
                response = _error_response(
                    None,
                    code=_jsonrpc_code("mcp_parse_error"),
                    message=str(exc),
                    data=error_payload("mcp_parse_error", str(exc)),
                )
            else:
                response = self.handle_request(request)
            sink.write(json.dumps(response, ensure_ascii=True) + "\n")
            sink.flush()

    def _adapter(self, merchant_base_url: str | None) -> AimiPayAgentAdapter:
        client = self.runtime.connect_merchant(merchant_base_url)
        return AimiPayAgentAdapter(client, self.runtime.http_clients)

    def _startup_onboarding_payload(self) -> dict[str, Any]:
        onboarding = self.startup_onboarding or {}
        host_action = onboarding.get("funding", {}).get("host_action")
        merchant = onboarding.get("merchant") or {}
        merchant_host_action = merchant.get("host_action") or {}
        return {
            "present": bool(onboarding),
            "completed": bool(onboarding.get("completed", False)),
            "next_step": onboarding.get("next_step"),
            "action_required": onboarding.get("action_required"),
            "saved_report": onboarding.get("saved_report"),
            "host_action": host_action,
            "merchant": {
                "merchant_urls": merchant.get("merchant_urls") or [],
                "selected_url": merchant.get("selected_url"),
                "service_name": merchant.get("service_name"),
                "offers": merchant.get("offers") or {"count": 0, "items": []},
                "host_action": merchant_host_action,
            },
        }

    def _startup_onboarding_instructions(self) -> str:
        payload = self._startup_onboarding_payload()
        host_action = payload.get("host_action") or {}
        merchant = payload.get("merchant") or {}
        merchant_action = merchant.get("host_action") or {}
        if not payload.get("present"):
            return "AimiPay startup onboarding data is not available. Use aimipay.run_onboarding if wallet setup guidance is needed."
        if payload.get("completed"):
            merchant_summary = ""
            if merchant.get("selected_url"):
                merchant_summary = f" Connected merchant: {merchant.get('selected_url')}."
            if (merchant.get("offers") or {}).get("count"):
                merchant_summary += f" Offers discovered: {(merchant.get('offers') or {}).get('count')}."
            return f"AimiPay startup onboarding is complete. The wallet is ready to continue toward budgeting and purchases.{merchant_summary}"
        message = host_action.get("message") or "AimiPay onboarding requires attention before paid purchases."
        if merchant_action.get("message"):
            message = f"{message} {merchant_action.get('message')}"
        checklist = host_action.get("checklist") or []
        rendered_checklist = " ".join(f"[{index + 1}] {item}" for index, item in enumerate(checklist[:3]))
        if rendered_checklist:
            return f"{message} {rendered_checklist}"
        return message

    def _startup_card_payload(self) -> dict[str, Any]:
        payload = self._startup_onboarding_payload()
        host_action = payload.get("host_action") or {}
        merchant = payload.get("merchant") or {}
        merchant_action = merchant.get("host_action") or {}
        next_step = payload.get("next_step") or "unknown"
        tone = "success" if payload.get("completed") else ("warning" if payload.get("present") else "info")
        checklist = list(host_action.get("checklist") or [])
        checklist.extend(item for item in (merchant_action.get("checklist") or []) if item not in checklist)
        resources = list(host_action.get("resources") or [])
        resources.extend(item for item in (merchant_action.get("resources") or []) if item not in resources)
        return {
            "schema_version": "aimipay.startup-card.v1",
            "kind": "onboarding_card",
            "visible": payload.get("present", False),
            "tone": tone,
            "title": host_action.get("title") or next_step.replace("_", " ").title(),
            "summary": self._startup_onboarding_instructions(),
            "primary_action": {
                "action": next_step,
                "label": _primary_action_label(next_step),
            },
            "secondary_actions": [
                {
                    "action": "aimipay.set_merchant_url",
                    "label": "Set Merchant URL",
                },
                {
                    "action": "aimipay.get_startup_onboarding",
                    "label": "View Onboarding Details",
                }
            ],
            "checklist": checklist,
            "resources": resources,
            "fields": [
                {
                    "name": "merchant_url",
                    "label": "Merchant URL",
                    "type": "url",
                    "required": True,
                    "value": merchant.get("selected_url") or "",
                    "placeholder": "https://merchant.example",
                }
            ],
            "offers_preview": (merchant.get("offers") or {}).get("items") or [],
            "status": {
                "completed": payload.get("completed", False),
                "next_step": next_step,
                "action_required": payload.get("action_required"),
            },
        }


def _tool(name: str, description: str, input_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
    }


def _response(request_id: Any, result: dict[str, Any], *, jsonrpc: str | None = None) -> dict[str, Any]:
    payload = {"id": request_id, "result": result}
    if jsonrpc is not None:
        payload["jsonrpc"] = jsonrpc
    return payload


def _error_response(
    request_id: Any,
    *,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
    jsonrpc: str | None = None,
) -> dict[str, Any]:
    payload = {
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if data is not None:
        payload["error"]["data"] = data
    if jsonrpc is not None:
        payload["jsonrpc"] = jsonrpc
    return payload


def _jsonrpc_code(error_code: str) -> int:
    mapping = {
        "mcp_parse_error": -32700,
        "mcp_invalid_params": -32602,
        "mcp_method_not_found": -32601,
        "unknown_mcp_tool": -32602,
    }
    return mapping.get(error_code, -32000)


def _primary_action_label(next_step: str) -> str:
    return {
        "create_wallet": "Create Wallet",
        "fund_wallet": "Fund Wallet",
        "connect_merchant": "Connect Merchant",
        "discover_offers": "Discover Offers",
        "review_offers": "Review Offers",
        "ready_to_purchase": "Continue to Offers",
    }.get(next_step, "Open Onboarding")

from __future__ import annotations

from fastapi import FastAPI

from seller import install_sellable_capability
from shared import CapabilityBudgetHint


app = FastAPI(title="AimiPay Coding Agent Tools")

merchant = install_sellable_capability(
    app,
    service_name="Coding Agent Toolsmith",
    service_description="Paid code analysis and patch planning tools for autonomous coding agents",
    seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    contract_address="0x1000000000000000000000000000000000000001",
    token_address="0x2000000000000000000000000000000000000002",
)


@merchant.paid_api(
    path="/tools/code-review",
    price_atomic=400_000,
    capability_id="coding-agent-code-review",
    capability_type="code_review",
    description="Review a patch and return machine-readable findings.",
    capability_tags=["coding-agent", "review", "security"],
    budget_hint=CapabilityBudgetHint(
        typical_units=1,
        min_units=1,
        suggested_prepaid_atomic=400_000,
        notes="One paid review per patch is typical.",
    ),
)
def code_review_tool(body: dict) -> dict:
    diff = str(body.get("diff") or "")
    risk = "high" if "private_key" in diff.lower() or "secret" in diff.lower() else "normal"
    return {
        "schema_version": "aimipay.vertical-demo.coding-agent-result.v1",
        "kind": "code_review_result",
        "risk": risk,
        "findings": [] if risk == "normal" else [{"severity": "high", "message": "Potential secret handling issue."}],
        "next_actions": ["apply_patch"] if risk == "normal" else ["request_human_review"],
    }


@merchant.paid_api(
    path="/tools/patch-plan",
    price_atomic=300_000,
    capability_id="coding-agent-patch-plan",
    capability_type="patch_planning",
    description="Turn a coding request into scoped implementation steps.",
    capability_tags=["coding-agent", "planning"],
    budget_hint=CapabilityBudgetHint(
        typical_units=1,
        min_units=1,
        suggested_prepaid_atomic=300_000,
        notes="Use before expensive coding work.",
    ),
)
def patch_plan_tool(body: dict) -> dict:
    request = str(body.get("request") or "implement feature")
    return {
        "schema_version": "aimipay.vertical-demo.coding-agent-result.v1",
        "kind": "patch_plan",
        "request": request,
        "steps": [
            "inspect existing implementation",
            "make the smallest compatible code change",
            "add focused tests",
            "run validation",
        ],
    }

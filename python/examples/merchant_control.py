from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field

from shared import CapabilityBudgetHint, MerchantPlan, MerchantRoute


class MerchantBrandConfig(BaseModel):
    display_title: str = "Pay with AimiPay"
    accent_color: str = "#0f766e"
    support_email: str = "support@example.com"


class MerchantInstallConfig(BaseModel):
    service_name: str
    service_description: str
    brand: MerchantBrandConfig = Field(default_factory=MerchantBrandConfig)
    routes: list[MerchantRoute] = Field(default_factory=list)
    plans: list[MerchantPlan] = Field(default_factory=list)


class MerchantConfigSnapshot(BaseModel):
    revision: int
    saved_at: int
    reason: str
    config: MerchantInstallConfig


def default_routes() -> list[MerchantRoute]:
    return [
        MerchantRoute(
            path="/tools/research",
            price_atomic=250_000,
            capability_type="web_search",
            description="Paid research API for coding and market tasks",
            auth_requirements=["request_digest", "buyer_signature"],
            capability_tags=["api", "search", "research", "web"],
            budget_hint=CapabilityBudgetHint(
                typical_units=3,
                min_units=1,
                suggested_prepaid_atomic=750_000,
                notes="Typical coding task needs 3 paid searches",
            ),
        ),
        MerchantRoute(
            path="/mcp/browser.search",
            price_atomic=150_000,
            capability_type="mcp_tool",
            description="Paid MCP browser search tool",
            usage_unit="tool_call",
            capability_tags=["mcp"],
            budget_hint=CapabilityBudgetHint(
                typical_units=2,
                min_units=1,
                suggested_prepaid_atomic=300_000,
                notes="Typical browser-assisted task needs 2 tool calls",
            ),
        ),
    ]


def default_plans() -> list[MerchantPlan]:
    return [
        MerchantPlan(
            plan_id="pro-monthly",
            name="Pro Monthly",
            amount_atomic=9_900_000,
            subscribe_path="/billing/subscribe",
            features=["priority support", "higher search quota"],
        )
    ]


def load_merchant_install_config(
    *,
    config_path: str | Path,
    service_name: str,
    service_description: str,
    brand: MerchantBrandConfig | None = None,
) -> MerchantInstallConfig:
    path = Path(config_path)
    if path.exists():
        return MerchantInstallConfig.model_validate_json(path.read_text(encoding="utf-8"))
    return MerchantInstallConfig(
        service_name=service_name,
        service_description=service_description,
        brand=brand or MerchantBrandConfig(),
        routes=default_routes(),
        plans=default_plans(),
    )


def save_merchant_install_config(
    *,
    config_path: str | Path,
    config: MerchantInstallConfig,
    reason: str = "save",
) -> MerchantInstallConfig:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.model_dump(mode="json"), indent=2), encoding="utf-8")
    snapshot = MerchantConfigSnapshot(
        revision=_next_revision(config_path=path),
        saved_at=int(time.time()),
        reason=reason,
        config=config,
    )
    history_dir = _history_dir(path)
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / f"{snapshot.revision:04d}.json").write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return config


def upsert_route(config: MerchantInstallConfig, route: MerchantRoute) -> MerchantInstallConfig:
    routes = [item for item in config.routes if not (item.path == route.path and item.method == route.method)]
    routes.append(route)
    return config.model_copy(update={"routes": routes})


def upsert_plan(config: MerchantInstallConfig, plan: MerchantPlan) -> MerchantInstallConfig:
    plans = [item for item in config.plans if item.plan_id != plan.plan_id]
    plans.append(plan)
    return config.model_copy(update={"plans": plans})


def delete_route(config: MerchantInstallConfig, *, path: str, method: str = "POST") -> MerchantInstallConfig:
    routes = [item for item in config.routes if not (item.path == path and item.method.upper() == method.upper())]
    return config.model_copy(update={"routes": routes})


def delete_plan(config: MerchantInstallConfig, *, plan_id: str) -> MerchantInstallConfig:
    plans = [item for item in config.plans if item.plan_id != plan_id]
    return config.model_copy(update={"plans": plans})


def toggle_route(
    config: MerchantInstallConfig,
    *,
    path: str,
    method: str = "POST",
    enabled: bool,
) -> MerchantInstallConfig:
    routes = []
    for item in config.routes:
        if item.path == path and item.method.upper() == method.upper():
            routes.append(item.model_copy(update={"enabled": enabled}))
        else:
            routes.append(item)
    return config.model_copy(update={"routes": routes})


def toggle_plan(config: MerchantInstallConfig, *, plan_id: str, enabled: bool) -> MerchantInstallConfig:
    plans = []
    for item in config.plans:
        if item.plan_id == plan_id:
            plans.append(item.model_copy(update={"enabled": enabled}))
        else:
            plans.append(item)
    return config.model_copy(update={"plans": plans})


def list_config_history(*, config_path: str | Path) -> list[MerchantConfigSnapshot]:
    path = Path(config_path)
    history_dir = _history_dir(path)
    if not history_dir.exists():
        return []
    snapshots: list[MerchantConfigSnapshot] = []
    for item in sorted(history_dir.glob("*.json"), reverse=True):
        snapshots.append(MerchantConfigSnapshot.model_validate_json(item.read_text(encoding="utf-8")))
    return snapshots


def rollback_merchant_install_config(*, config_path: str | Path, revision: int) -> MerchantInstallConfig:
    path = Path(config_path)
    snapshot_path = _history_dir(path) / f"{revision:04d}.json"
    snapshot = MerchantConfigSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    return save_merchant_install_config(
        config_path=path,
        config=snapshot.config,
        reason=f"rollback_to_{revision}",
    )


def diff_configs(*, current: MerchantInstallConfig, target: MerchantInstallConfig) -> dict:
    current_routes = {(item.path, item.method.upper()): item for item in current.routes}
    target_routes = {(item.path, item.method.upper()): item for item in target.routes}
    current_plans = {item.plan_id: item for item in current.plans}
    target_plans = {item.plan_id: item for item in target.plans}

    return {
        "service_changed": current.service_name != target.service_name or current.service_description != target.service_description,
        "branding_changed": current.brand != target.brand,
        "routes_added": [item.model_dump(mode="json") for key, item in target_routes.items() if key not in current_routes],
        "routes_removed": [item.model_dump(mode="json") for key, item in current_routes.items() if key not in target_routes],
        "routes_changed": [
            {
                "before": current_routes[key].model_dump(mode="json"),
                "after": item.model_dump(mode="json"),
            }
            for key, item in target_routes.items()
            if key in current_routes and current_routes[key] != item
        ],
        "plans_added": [item.model_dump(mode="json") for key, item in target_plans.items() if key not in current_plans],
        "plans_removed": [item.model_dump(mode="json") for key, item in current_plans.items() if key not in target_plans],
        "plans_changed": [
            {
                "before": current_plans[key].model_dump(mode="json"),
                "after": item.model_dump(mode="json"),
            }
            for key, item in target_plans.items()
            if key in current_plans and current_plans[key] != item
        ],
    }


def _history_dir(config_path: Path) -> Path:
    return config_path.parent / f"{config_path.stem}.history"


def _next_revision(*, config_path: Path) -> int:
    history_dir = _history_dir(config_path)
    revisions = []
    if history_dir.exists():
        for item in history_dir.glob("*.json"):
            try:
                revisions.append(int(item.stem))
            except ValueError:
                continue
    return (max(revisions) + 1) if revisions else 1

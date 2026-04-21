from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from .client import BuyerClient
from .provisioner import TronProvisioner
from .wallet import BuyerWallet


@dataclass(slots=True)
class MarketSelectionPolicy:
    policy_name: str = "balanced"
    price_weight: float = 1.0
    settlement_backend_weight: float = 1.0
    delivery_mode_weight: float = 1.0
    auth_complexity_weight: float = 1.0
    settlement_backend_scores: dict[str, float] = field(
        default_factory=lambda: {
            "claim_script": 20.0,
            "local_smoke": 5.0,
            "default": 10.0,
        }
    )
    delivery_mode_scores: dict[str, float] = field(
        default_factory=lambda: {
            "sync": 10.0,
            "async": 6.0,
            "default": 8.0,
        }
    )
    auth_base_score: float = 10.0
    auth_penalty_per_requirement: float = 2.0


@dataclass(slots=True)
class BuyerMarket:
    merchant_base_urls: list[str]
    full_host: str | None
    wallet: BuyerWallet
    provisioner: TronProvisioner
    repository_root: str | None = None
    http_clients: dict[str, httpx.Client] = field(default_factory=dict)
    selection_policy: MarketSelectionPolicy = field(default_factory=MarketSelectionPolicy)

    def list_market_capability_offers(self) -> list[dict]:
        offers: list[dict] = []
        for merchant_base_url in self.merchant_base_urls:
            client = self._client_for(merchant_base_url)
            manifest = client.fetch_manifest()
            service_name = manifest.get("service_name")
            for offer in client.list_capability_offers():
                offers.append(
                    {
                        **offer,
                        "merchant_base_url": merchant_base_url,
                        "service_name": service_name,
                    }
                )
        return offers

    def evaluate_market_capability_offers(
        self,
        *,
        capability_type: str | None = None,
        capability_id: str | None = None,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
        selection_policy: MarketSelectionPolicy | None = None,
    ) -> list[dict]:
        if capability_type is None and capability_id is None:
            raise ValueError("capability_type or capability_id is required")
        policy = selection_policy or self.selection_policy
        matched = []
        for offer in self.list_market_capability_offers():
            if capability_id is not None and offer["capability_id"] != capability_id:
                continue
            if capability_type is not None and offer["capability_type"] != capability_type:
                continue
            matched.append(offer)
        if not matched:
            raise ValueError("no market offers matched the requested selector")

        evaluated = []
        for offer in matched:
            client = self._client_for(offer["merchant_base_url"])
            estimate = client._estimate_offer(  # noqa: SLF001 - deliberate reuse of buyer-side budget logic
                offer=offer,
                expected_units=expected_units,
                budget_limit_atomic=budget_limit_atomic,
            )
            score, score_breakdown = _score_offer(
                estimate["offer"],
                estimate["decision"],
                policy=policy,
            )
            estimate["decision"]["score"] = score
            estimate["decision"]["score_breakdown"] = score_breakdown
            estimate["decision"]["selection_policy"] = policy.policy_name
            evaluated.append(estimate)
        return sorted(
            evaluated,
            key=lambda item: (
                _decision_rank(item["decision"]["action"]),
                -float(item["decision"].get("score") or 0.0),
                item["budget"]["estimated_total_atomic"],
                item["offer"]["merchant_base_url"],
                item["offer"]["capability_id"],
            ),
        )

    def select_market_capability_offer(
        self,
        *,
        capability_type: str | None = None,
        capability_id: str | None = None,
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
        selection_policy: MarketSelectionPolicy | None = None,
    ) -> dict:
        candidates = self.evaluate_market_capability_offers(
            capability_type=capability_type,
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
            selection_policy=selection_policy,
        )
        policy = selection_policy or self.selection_policy
        return {
            "selected": candidates[0],
            "candidates": candidates,
            "selection_reason": f"highest score among all matching merchants using policy: {policy.policy_name}",
        }

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
        selection_policy: MarketSelectionPolicy | None = None,
    ) -> dict:
        selection = self.select_market_capability_offer(
            capability_type=capability_type,
            capability_id=capability_id,
            expected_units=expected_units,
            budget_limit_atomic=budget_limit_atomic,
            selection_policy=selection_policy,
        )
        selected_offer = selection["selected"]["offer"]
        client = self._client_for(selected_offer["merchant_base_url"])
        purchase = client.buy_capability(
            capability_id=selected_offer["capability_id"],
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

    def _client_for(self, merchant_base_url: str) -> BuyerClient:
        return BuyerClient(
            merchant_base_url=merchant_base_url,
            full_host=self.full_host,
            wallet=self.wallet,
            provisioner=self.provisioner,
            http_client=self.http_clients.get(merchant_base_url),
            repository_root=self.repository_root,
        )


def _decision_rank(action: str) -> int:
    return {
        "buy_now": 0,
        "needs_approval": 1,
        "skip": 2,
    }.get(action, 99)


def _score_offer(
    offer: dict,
    decision: dict,
    *,
    policy: MarketSelectionPolicy,
) -> tuple[float, dict[str, float]]:
    estimated_total_atomic = float(decision["estimated_total_atomic"])
    price_score = (1_000_000 / max(estimated_total_atomic, 1.0)) * policy.price_weight

    settlement_backend = offer.get("settlement_backend")
    settlement_score = policy.settlement_backend_scores.get(
        str(settlement_backend),
        policy.settlement_backend_scores.get("default", 10.0),
    ) * policy.settlement_backend_weight

    delivery_mode = str(offer.get("delivery_mode", "sync"))
    delivery_score = policy.delivery_mode_scores.get(
        delivery_mode,
        policy.delivery_mode_scores.get("default", 8.0),
    ) * policy.delivery_mode_weight

    auth_requirements = list(offer.get("auth_requirements") or [])
    auth_score = max(
        1.0,
        policy.auth_base_score - len(auth_requirements) * policy.auth_penalty_per_requirement,
    ) * policy.auth_complexity_weight

    breakdown = {
        "price": price_score,
        "settlement_backend": settlement_score,
        "delivery_mode": delivery_score,
        "auth_complexity": auth_score,
    }
    total_score = sum(breakdown.values())
    return total_score, breakdown

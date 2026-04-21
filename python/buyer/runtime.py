from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from .client import BuyerClient
from .market import BuyerMarket, MarketSelectionPolicy
from .provisioner import TronProvisioner
from .wallet import BuyerWallet


@dataclass(slots=True)
class AgentPaymentsRuntime:
    full_host: str | None
    wallet: BuyerWallet
    provisioner: TronProvisioner
    repository_root: str | None = None
    default_merchant_base_url: str | None = None
    merchant_base_urls: list[str] = field(default_factory=list)
    http_clients: dict[str, httpx.Client] = field(default_factory=dict)
    selection_policy: MarketSelectionPolicy = field(default_factory=MarketSelectionPolicy)
    auto_purchase_enabled: bool = True

    def enable_auto_wallet(self) -> "AgentPaymentsRuntime":
        if not self.wallet.address or not self.wallet.private_key:
            raise ValueError("wallet address and private key are required")
        return self

    def enable_auto_purchase(
        self,
        *,
        selection_policy: MarketSelectionPolicy | None = None,
    ) -> "AgentPaymentsRuntime":
        self.auto_purchase_enabled = True
        if selection_policy is not None:
            self.selection_policy = selection_policy
        return self

    def disable_auto_purchase(self) -> "AgentPaymentsRuntime":
        self.auto_purchase_enabled = False
        return self

    def configure_selection_policy(self, selection_policy: MarketSelectionPolicy) -> "AgentPaymentsRuntime":
        self.selection_policy = selection_policy
        return self

    def connect_merchant(
        self,
        merchant_base_url: str | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> BuyerClient:
        target_base_url = merchant_base_url or self.default_merchant_base_url
        if target_base_url is None:
            raise ValueError("merchant_base_url is required")
        return BuyerClient(
            merchant_base_url=target_base_url,
            full_host=self.full_host,
            wallet=self.wallet,
            provisioner=self.provisioner,
            http_client=http_client or self.http_clients.get(target_base_url),
            repository_root=self.repository_root,
        )

    def connect_market(
        self,
        merchant_base_urls: list[str] | None = None,
        *,
        http_clients: dict[str, httpx.Client] | None = None,
    ) -> BuyerMarket:
        target_urls = merchant_base_urls or self.merchant_base_urls
        if not target_urls:
            raise ValueError("merchant_base_urls is required")
        return BuyerMarket(
            merchant_base_urls=target_urls,
            full_host=self.full_host,
            wallet=self.wallet,
            provisioner=self.provisioner,
            repository_root=self.repository_root,
            http_clients=http_clients or self.http_clients,
            selection_policy=self.selection_policy,
        )

    def pay_for_task(
        self,
        *,
        task_context: str,
        capability_type: str | None = None,
        capability_id: str | None = None,
        merchant_base_url: str | None = None,
        merchant_base_urls: list[str] | None = None,
        request_body: str = "",
        expected_units: int | None = None,
        budget_limit_atomic: int | None = None,
        deposit_atomic: int | None = None,
        ttl_s: int | None = None,
        voucher_nonce: int = 1,
        request_deadline: int | None = None,
        auto_execute: bool = True,
        auto_finalize: bool = False,
        allow_needs_approval: bool = False,
        http_client: httpx.Client | None = None,
        http_clients: dict[str, httpx.Client] | None = None,
    ) -> dict:
        if not self.auto_purchase_enabled:
            raise RuntimeError("auto purchase is disabled")
        if merchant_base_url is not None:
            client = self.connect_merchant(merchant_base_url, http_client=http_client)
            return client.pay_for_task(
                task_context=task_context,
                capability_type=capability_type,
                capability_id=capability_id,
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

        market = self.connect_market(merchant_base_urls, http_clients=http_clients)
        return market.pay_for_task(
            task_context=task_context,
            capability_type=capability_type,
            capability_id=capability_id,
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


def install_agent_payments(
    *,
    full_host: str | None = None,
    wallet: BuyerWallet,
    provisioner: TronProvisioner,
    repository_root: str | None = None,
    merchant_base_url: str | None = None,
    merchant_base_urls: list[str] | None = None,
    http_clients: dict[str, httpx.Client] | None = None,
    selection_policy: MarketSelectionPolicy | None = None,
) -> AgentPaymentsRuntime:
    return AgentPaymentsRuntime(
        full_host=full_host,
        wallet=wallet,
        provisioner=provisioner,
        repository_root=repository_root,
        default_merchant_base_url=merchant_base_url,
        merchant_base_urls=list(merchant_base_urls or ([] if merchant_base_url is None else [merchant_base_url])),
        http_clients=http_clients or {},
        selection_policy=selection_policy or MarketSelectionPolicy(),
    )

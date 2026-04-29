from __future__ import annotations

from importlib import import_module
from typing import Any


__all__ = [
    "AgentPaymentsRuntime",
    "AimiPayAgentAdapter",
    "AimiPayMcpServer",
    "BuyerClient",
    "BuyerBudgetPolicy",
    "BuyerMarket",
    "MarketSelectionPolicy",
    "BuyerWallet",
    "OpenChannelExecution",
    "OpenChannelProvisionPlan",
    "TronProvisioner",
    "build_default_tron_provisioner",
    "install_agent_payments",
]

_EXPORT_MAP = {
    "AimiPayAgentAdapter": ("buyer.adapter", "AimiPayAgentAdapter"),
    "BuyerClient": ("buyer.client", "BuyerClient"),
    "BuyerBudgetPolicy": ("buyer.client", "BuyerBudgetPolicy"),
    "AimiPayMcpServer": ("buyer.mcp", "AimiPayMcpServer"),
    "BuyerMarket": ("buyer.market", "BuyerMarket"),
    "MarketSelectionPolicy": ("buyer.market", "MarketSelectionPolicy"),
    "OpenChannelExecution": ("buyer.provisioner", "OpenChannelExecution"),
    "OpenChannelProvisionPlan": ("buyer.provisioner", "OpenChannelProvisionPlan"),
    "TronProvisioner": ("buyer.provisioner", "TronProvisioner"),
    "build_default_tron_provisioner": ("buyer.provisioner", "build_default_tron_provisioner"),
    "AgentPaymentsRuntime": ("buyer.runtime", "AgentPaymentsRuntime"),
    "install_agent_payments": ("buyer.runtime", "install_agent_payments"),
    "BuyerWallet": ("buyer.wallet", "BuyerWallet"),
}


def __getattr__(name: str) -> Any:
    if name not in _EXPORT_MAP:
        raise AttributeError(name)
    module_name, attr_name = _EXPORT_MAP[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

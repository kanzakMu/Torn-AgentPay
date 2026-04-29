from __future__ import annotations

import json

from fastapi.testclient import TestClient

from buyer import BuyerClient, BuyerWallet, OpenChannelExecution
from shared.protocol_native import channel_id_of

from examples.coding_agent_paid_tools_app import app


class DemoProvisioner:
    def provision(self, plan):
        buyer_address = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        return OpenChannelExecution(
            approve_tx_id="approve_demo",
            open_tx_id="open_demo",
            channel_id=channel_id_of(
                buyer_address=buyer_address,
                seller_address=plan.seller_address,
                token_address=plan.token_address,
                channel_salt=plan.channel_salt,
            ),
            buyer_address=buyer_address,
            seller_address=plan.seller_address,
            token_address=plan.token_address,
            contract_address=plan.contract_address,
            deposit_atomic=plan.deposit_atomic,
            expires_at=plan.expires_at,
        )


class DemoSettlementService:
    def __init__(self, runtime):
        self.runtime = runtime

    def execute_payment(self, payment_id: str):
        record = self.runtime.payment_store.get(payment_id)
        updated = record.model_copy(update={"status": "settled", "tx_id": "trx_demo_settled"})
        self.runtime.payment_store.upsert(updated)
        return updated

    def execute_pending(self):
        return []


def run_demo() -> dict:
    runtime = app.state.aimipay_gateway
    runtime.settlement_service = DemoSettlementService(runtime)
    client = BuyerClient(
        merchant_base_url="http://coding-agent.test",
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="buyer_pk",
        ),
        provisioner=DemoProvisioner(),
        http_client=TestClient(app, base_url="http://coding-agent.test"),
    )
    result = client.request_paid_resource(
        "/tools/code-review",
        json_body={"diff": "diff --git a/app.py b/app.py\n+print('ok')"},
        budget_limit_atomic=500_000,
    )
    return {
        "schema_version": "aimipay.demo.coding-agent-paid-flow.v1",
        "resource": result["response"].json(),
        "payment_response": result["payment_response"],
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))

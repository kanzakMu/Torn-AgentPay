from __future__ import annotations

import json

import httpx

from buyer.client import BuyerClient
from buyer.provisioner import OpenChannelExecution
from buyer.wallet import BuyerWallet
from shared import channel_id_of


class ReferenceProvisioner:
    def provision(self, plan):
        return OpenChannelExecution(
            approve_tx_id="approve_reference_1",
            open_tx_id="open_reference_1",
            buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            seller_address=plan.seller_address,
            token_address=plan.token_address,
            channel_id=channel_id_of(
                buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                seller_address=plan.seller_address,
                token_address=plan.token_address,
            ),
            contract_address=plan.contract_address,
            deposit_atomic=plan.deposit_atomic,
            expires_at=plan.expires_at,
        )


def run_reference_buyer_flow(*, merchant_base_url: str, http_client: httpx.Client | None = None) -> dict:
    client = BuyerClient(
        merchant_base_url=merchant_base_url,
        full_host="http://tron.local",
        wallet=BuyerWallet(
            address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        ),
        provisioner=ReferenceProvisioner(),
        http_client=http_client,
    )
    offers = client.discover_offers()
    prepared = client.prepare_purchase(capability_id=offers[0]["capability_id"])
    submitted = client.submit_purchase(
        prepared_purchase=prepared,
        request_body='{"topic":"tron"}',
        auto_execute=False,
    )
    confirmed = client.confirm_purchase(submitted["payment"]["payment_id"])
    return {
        "offers": offers,
        "prepared": prepared,
        "submitted": submitted,
        "confirmed": confirmed,
    }


def main() -> None:
    payload = run_reference_buyer_flow(merchant_base_url="http://127.0.0.1:8000")
    print(json.dumps(payload, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

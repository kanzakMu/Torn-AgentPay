from __future__ import annotations

import json
import subprocess
from pathlib import Path

from shared.protocol_native import build_payment_voucher, build_request_digest, channel_id_of, voucher_digest


def test_native_protocol_helpers_match_javascript_reference() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    node_script = """
const { buildRequestDigest, channelIdOf, voucherDigest } = require('./scripts/protocol');
const payload = {
  channel_id: channelIdOf({
    buyer: '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266',
    seller: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8',
    token: '0x2000000000000000000000000000000000000002',
    fullHost: 'http://tron.local',
  }),
  request_digest: buildRequestDigest({
    method: 'POST',
    path: '/tools/research',
    body: '{\"topic\":\"tron\"}',
    requestDeadline: 1700000000,
  }),
};
payload.voucher_digest = voucherDigest({
  contractAddress: '0x1000000000000000000000000000000000000001',
  chainId: 31337n,
  channelId: payload.channel_id,
  buyer: '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266',
  seller: '0x70997970C51812dc3A010C7d01b50e0d17dc79C8',
  token: '0x2000000000000000000000000000000000000002',
  amountAtomic: 250000n,
  nonce: 1n,
  expiresAt: 9999999999n,
  requestDeadline: 1700000000n,
  requestDigest: payload.request_digest,
  fullHost: 'http://tron.local',
});
process.stdout.write(JSON.stringify(payload));
"""
    completed = subprocess.run(
        ["node", "-e", node_script],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        text=True,
    )
    expected = json.loads(completed.stdout)

    channel_id = channel_id_of(
        buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        token_address="0x2000000000000000000000000000000000000002",
    )
    request_digest = build_request_digest(
        method="POST",
        path="/tools/research",
        body='{"topic":"tron"}',
        request_deadline=1_700_000_000,
    )
    digest = voucher_digest(
        contract_address="0x1000000000000000000000000000000000000001",
        chain_id=31337,
        channel_id=channel_id,
        buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        token_address="0x2000000000000000000000000000000000000002",
        amount_atomic=250_000,
        voucher_nonce=1,
        expires_at=9_999_999_999,
        request_deadline=1_700_000_000,
        request_digest=request_digest,
    )

    assert channel_id == expected["channel_id"]
    assert request_digest == expected["request_digest"]
    assert digest == expected["voucher_digest"]


def test_build_payment_voucher_returns_ethereum_signature_shape() -> None:
    payload = build_payment_voucher(
        buyer_private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        chain_id=31337,
        contract_address="0x1000000000000000000000000000000000000001",
        channel_id="0xe97271db6a421521793f6ab49d2b1c41ffd669f2012f3fd9ab7a38531b051a5b",
        buyer_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        seller_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        token_address="0x2000000000000000000000000000000000000002",
        amount_atomic=250_000,
        voucher_nonce=1,
        expires_at=9_999_999_999,
        request_deadline=1_700_000_000,
        method="POST",
        path="/tools/research",
        body='{"topic":"tron"}',
    )

    assert payload.request_digest.startswith("0x")
    assert payload.voucher_digest.startswith("0x")
    assert payload.buyer_signature.startswith("0x")
    assert len(payload.buyer_signature) == 132

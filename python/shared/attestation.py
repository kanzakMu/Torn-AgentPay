from __future__ import annotations

import json
import time
from typing import Any

from .models import SellerProfile, SignatureEnvelope
from .protocol_native import keccak256, sign_digest, verify_digest_signature


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def payload_digest(payload: Any) -> str:
    return f"0x{keccak256(canonical_json_bytes(payload)).hex()}"


def sign_payload(*, payload: Any, signer_address: str, private_key: str, payload_kind: str, signed_at: int | None = None) -> SignatureEnvelope:
    digest = payload_digest(payload)
    return SignatureEnvelope(
        payload_kind=payload_kind,
        signer_address=signer_address,
        digest=digest,
        signed_at=signed_at or int(time.time()),
        signature=sign_digest(private_key, digest),
    )


def verify_signed_payload(*, payload: Any, envelope: SignatureEnvelope, expected_signer_address: str | None = None) -> bool:
    if envelope.digest != payload_digest(payload):
        return False
    signer_address = expected_signer_address or envelope.signer_address
    return verify_digest_signature(
        digest=envelope.digest,
        signature=envelope.signature,
        signer_address=signer_address,
    )


def build_seller_profile(
    *,
    seller_address: str,
    service_name: str,
    service_description: str,
    base_url: str | None,
    network: str,
    chain_id: int | None,
) -> SellerProfile:
    return SellerProfile(
        seller_address=seller_address,
        display_name=service_name,
        service_name=service_name,
        service_description=service_description,
        service_url=base_url.rstrip("/") if base_url else None,
        network=network,
        chain_id=chain_id,
    )

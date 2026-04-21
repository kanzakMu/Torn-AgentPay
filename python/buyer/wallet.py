from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

import base58
from cryptography.hazmat.primitives.asymmetric import ec

from shared.protocol_native import keccak256


_SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_PLACEHOLDER_VALUES = {"", "TRX_BUYER", "buyer_private_key"}


@dataclass(slots=True)
class BuyerWallet:
    address: str
    private_key: str

    def __post_init__(self) -> None:
        if not self.address:
            raise ValueError("buyer address is required")
        if not self.private_key:
            raise ValueError("buyer private key is required")

    @classmethod
    def from_env(cls) -> "BuyerWallet":
        address = os.environ.get("AIMIPAY_BUYER_ADDRESS", "")
        private_key = os.environ.get("AIMIPAY_BUYER_PRIVATE_KEY", "")
        return cls(address=address, private_key=private_key)

    @classmethod
    def create_tron_wallet(cls) -> "BuyerWallet":
        private_value = secrets.randbelow(_SECP256K1_N - 1) + 1
        private_key = f"0x{private_value:064x}"
        address = _tron_base58_from_private_key(private_key)
        return cls(address=address, private_key=private_key)

    def save_wallet_locally(
        self,
        *,
        env_file: str | Path,
        wallet_file: str | Path | None = None,
        overwrite: bool = True,
    ) -> dict[str, str]:
        env_path = Path(env_file)
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_lines = []
        if env_path.exists():
            env_lines = env_path.read_text(encoding="utf-8").splitlines()
        updated_lines = _set_env_values(
            env_lines,
            {
                "AIMIPAY_BUYER_ADDRESS": self.address,
                "AIMIPAY_BUYER_PRIVATE_KEY": self.private_key,
            },
            overwrite=overwrite,
        )
        env_path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")

        saved = {"env_file": str(env_path)}
        if wallet_file is not None:
            wallet_path = Path(wallet_file)
            wallet_path.parent.mkdir(parents=True, exist_ok=True)
            wallet_payload = {
                "address": self.address,
                "address_hex": self.hex_address,
                "private_key": self.private_key,
            }
            if overwrite or not wallet_path.exists():
                wallet_path.write_text(json.dumps(wallet_payload, indent=2, sort_keys=True), encoding="utf-8")
            saved["wallet_file"] = str(wallet_path)
        return saved

    @property
    def hex_address(self) -> str:
        return _hex_address_from_private_key(self.private_key)

    def matches_private_key(self) -> bool:
        return self.address.lower() in {self.hex_address.lower(), _tron_base58_from_private_key(self.private_key).lower()}

    @classmethod
    def env_has_configured_wallet(cls, env_file: str | Path) -> bool:
        values = _read_env_values(env_file)
        address = values.get("AIMIPAY_BUYER_ADDRESS", "")
        private_key = values.get("AIMIPAY_BUYER_PRIVATE_KEY", "")
        if address in _PLACEHOLDER_VALUES or private_key in _PLACEHOLDER_VALUES:
            return False
        try:
            return cls(address=address, private_key=private_key).matches_private_key()
        except ValueError:
            return False


def _read_env_values(env_file: str | Path) -> dict[str, str]:
    path = Path(env_file)
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _set_env_values(lines: list[str], values: dict[str, str], *, overwrite: bool) -> list[str]:
    updated = list(lines)
    seen_keys: set[str] = set()
    for index, raw_line in enumerate(updated):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            continue
        key, _ = raw_line.split("=", 1)
        normalized_key = key.strip()
        if normalized_key not in values:
            continue
        seen_keys.add(normalized_key)
        if overwrite:
            updated[index] = f"{normalized_key}={values[normalized_key]}"
    for key, value in values.items():
        if key not in seen_keys:
            updated.append(f"{key}={value}")
    return updated


def _tron_base58_from_private_key(private_key: str) -> str:
    payload = bytes.fromhex("41" + _hex_address_from_private_key(private_key)[2:])
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return base58.b58encode(payload + checksum).decode("ascii")


def _hex_address_from_private_key(private_key: str) -> str:
    private_value = int(private_key[2:] if private_key.startswith("0x") else private_key, 16)
    signer = ec.derive_private_key(private_value, ec.SECP256K1())
    public_numbers = signer.public_key().public_numbers()
    public_key_bytes = b"\x04" + public_numbers.x.to_bytes(32, "big") + public_numbers.y.to_bytes(32, "big")
    address_bytes = keccak256(public_key_bytes[1:])[-20:]
    return f"0x{address_bytes.hex()}"

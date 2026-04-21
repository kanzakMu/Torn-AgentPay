from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from buyer.wallet import BuyerWallet


def ensure_local_buyer_wallet(
    *,
    repository_root: str | Path | None = None,
    env_file: str | Path | None = None,
    wallet_file: str | Path | None = None,
    force_create: bool = False,
    output_json: bool = False,
    emit_output: bool = True,
) -> dict[str, Any]:
    repo_root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    env_path = Path(env_file or repo_root / "python" / ".env.local").resolve()
    wallet_path = Path(wallet_file or repo_root / "python" / ".wallets" / "buyer-wallet.json").resolve()

    created = False
    if force_create or not BuyerWallet.env_has_configured_wallet(env_path):
        wallet = BuyerWallet.create_tron_wallet()
        saved = wallet.save_wallet_locally(env_file=env_path, wallet_file=wallet_path, overwrite=True)
        created = True
    else:
        values = _read_env_file(env_path)
        wallet = BuyerWallet(
            address=values["AIMIPAY_BUYER_ADDRESS"],
            private_key=values["AIMIPAY_BUYER_PRIVATE_KEY"],
        )
        saved = {"env_file": str(env_path)}
        if wallet_path.exists():
            saved["wallet_file"] = str(wallet_path)

    report = {
        "ok": True,
        "wallet_created": created,
        "buyer_address": wallet.address,
        "buyer_address_hex": wallet.hex_address,
        "wallet_matches_private_key": wallet.matches_private_key(),
        "saved": saved,
    }
    if emit_output:
        if output_json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(_format_report(report))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create and save a local Tron buyer wallet for AimiPay.")
    parser.add_argument("--repository-root")
    parser.add_argument("--env-file")
    parser.add_argument("--wallet-file")
    parser.add_argument("--force-create", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = ensure_local_buyer_wallet(
        repository_root=args.repository_root,
        env_file=args.env_file,
        wallet_file=args.wallet_file,
        force_create=args.force_create,
        output_json=args.json,
        emit_output=True,
    )
    return 0 if report["ok"] else 1


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _format_report(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "AimiPay Wallet Setup",
            f"- wallet created: {report['wallet_created']}",
            f"- buyer address: {report['buyer_address']}",
            f"- buyer address hex: {report['buyer_address_hex']}",
            f"- wallet matches private key: {report['wallet_matches_private_key']}",
            f"- saved: {report['saved']}",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())

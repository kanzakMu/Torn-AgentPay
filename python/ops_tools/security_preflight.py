from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from examples.env_loader import load_default_example_env, load_env_file

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
PLACEHOLDER_VALUES = {"", "TRX_SELLER", "TRX_CONTRACT", "TRX_USDT", "seller_private_key"}


def build_security_preflight_report(
    *,
    env_file: str | Path | None = None,
    production: bool | None = None,
) -> dict[str, Any]:
    load_default_example_env()
    if env_file is not None:
        load_env_file(env_file, override=True)

    effective_production = _is_production() if production is None else production
    checks = [
        _check("repository_root_exists", Path(_env("AIMIPAY_REPOSITORY_ROOT", ".")).exists(), _env("AIMIPAY_REPOSITORY_ROOT", ".")),
        _check("admin_token_configured", _has_admin_token(), "AIMIPAY_ADMIN_TOKEN or AIMIPAY_ADMIN_TOKEN_SHA256"),
        _check("admin_token_not_placeholder", _admin_token_not_placeholder(), "admin token should be non-trivial"),
        _check("public_base_url_not_local", not _is_local_url(_env("AIMIPAY_PUBLIC_BASE_URL", "")), _env("AIMIPAY_PUBLIC_BASE_URL", "")),
        _check("chain_id_configured", _env("AIMIPAY_CHAIN_ID", "") not in {"", "31337"} or not effective_production, _env("AIMIPAY_CHAIN_ID", "")),
        _check("contract_address_not_placeholder", _env("AIMIPAY_CONTRACT_ADDRESS", "") not in PLACEHOLDER_VALUES, _env("AIMIPAY_CONTRACT_ADDRESS", "")),
        _check("token_address_not_placeholder", _env("AIMIPAY_TOKEN_ADDRESS", "") not in PLACEHOLDER_VALUES, _env("AIMIPAY_TOKEN_ADDRESS", "")),
        _check("sqlite_configured", bool(_env("AIMIPAY_SQLITE_PATH", "")), _env("AIMIPAY_SQLITE_PATH", "")),
        _check("seller_key_not_plain_env_in_production", not (effective_production and bool(_env("AIMIPAY_SELLER_PRIVATE_KEY", ""))), "use key store or signer in production"),
        _check("buyer_key_not_plain_env_in_production", not (effective_production and bool(_env("AIMIPAY_BUYER_PRIVATE_KEY", ""))), "use key store or signer in production"),
        _check("audit_log_configured", bool(_env("AIMIPAY_AUDIT_LOG_PATH", "")), _env("AIMIPAY_AUDIT_LOG_PATH", "")),
    ]
    return {
        "ok": all(item["ok"] or (not effective_production and item["severity"] != "error") for item in checks),
        "production": effective_production,
        "checks": checks,
    }


def hash_admin_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run production security preflight checks for Torn-AgentPay.")
    parser.add_argument("--env-file")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--hash-admin-token")
    args = parser.parse_args(argv)
    if args.hash_admin_token is not None:
        print(hash_admin_token(args.hash_admin_token))
        return 0
    report = build_security_preflight_report(env_file=args.env_file, production=args.production)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"security preflight: {'ok' if report['ok'] else 'failed'}")
        for check in report["checks"]:
            marker = "OK" if check["ok"] else check["severity"].upper()
            print(f"- [{marker}] {check['name']}: {check['detail']}")
    return 0 if report["ok"] else 1


def _env(key: str, default: str) -> str:
    return (os.environ.get(key) or default).strip()


def _is_production() -> bool:
    value = _env("AIMIPAY_ENV", _env("ENVIRONMENT", "")).lower()
    return value in {"prod", "production", "mainnet"}


def _has_admin_token() -> bool:
    return bool(_env("AIMIPAY_ADMIN_TOKEN", "") or _env("AIMIPAY_ADMIN_TOKEN_SHA256", ""))


def _admin_token_not_placeholder() -> bool:
    token = _env("AIMIPAY_ADMIN_TOKEN", "")
    digest = _env("AIMIPAY_ADMIN_TOKEN_SHA256", "")
    if token:
        return len(token) >= 24 and token.lower() not in {"secret", "password", "admin", "token"}
    if digest:
        return len(digest) == 64 and all(ch in "0123456789abcdefABCDEF" for ch in digest)
    return False


def _is_local_url(value: str) -> bool:
    if not value:
        return False
    host = (urlparse(value).hostname or "").lower()
    return host in LOCAL_HOSTS


def _check(name: str, ok: bool, detail: str, *, severity: str = "error") -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail, "severity": severity}


if __name__ == "__main__":
    raise SystemExit(main())

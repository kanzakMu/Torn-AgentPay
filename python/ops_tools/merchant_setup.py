from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from examples.env_loader import load_env_file
from ops_tools.network_profile_setup import apply_network_profile


def ensure_merchant_install(
    *,
    repository_root: str | Path | None = None,
    env_file: str | Path | None = None,
    template_file: str | Path | None = None,
    public_config_path: str | Path | None = None,
    network_profile: str = "local",
    force: bool = False,
) -> dict[str, Any]:
    root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    python_dir = root / "python"
    env_template = Path(template_file) if template_file else python_dir / ".env.merchant.example"
    env_target = Path(env_file) if env_file else python_dir / ".env.merchant.local"
    public_config = (
        Path(public_config_path)
        if public_config_path
        else root / "merchant-dist" / "website" / ".generated" / "merchant.public.json"
    )

    if force or not env_target.exists():
        text = env_template.read_text(encoding="utf-8")
        text = text.replace("E:/trade/aimicropay-tron", root.as_posix())
        env_target.parent.mkdir(parents=True, exist_ok=True)
        env_target.write_text(text, encoding="utf-8")

    network_report = apply_network_profile(
        env_file=env_target,
        profile_name=network_profile,
        repository_root=root,
        emit_output=False,
    )

    load_env_file(env_target, override=True)
    merchant_port = int(_env("AIMIPAY_MERCHANT_PORT", "8000"))
    public_base_url = _env("AIMIPAY_PUBLIC_BASE_URL", f"http://127.0.0.1:{merchant_port}")
    service_name = _env("AIMIPAY_SERVICE_NAME", "Your Merchant")
    service_description = _env("AIMIPAY_SERVICE_DESCRIPTION", "Agent-native paid capability")
    accent_color = _env("AIMIPAY_BRAND_ACCENT_COLOR", "#0f766e")
    support_email = _env("AIMIPAY_SUPPORT_EMAIL", "support@example.com")

    public_payload = {
        "schema_version": "aimipay.merchant-install.v1",
        "service_name": service_name,
        "service_description": service_description,
        "brand": {
            "accent_color": accent_color,
            "support_email": support_email,
        },
        "merchant_base_url": public_base_url.rstrip("/"),
        "manifest_url": f"{public_base_url.rstrip('/')}/.well-known/aimipay.json",
        "discover_url": f"{public_base_url.rstrip('/')}/_aimipay/discover",
        "protocol_reference_url": f"{public_base_url.rstrip('/')}/_aimipay/protocol/reference",
        "ops_health_url": f"{public_base_url.rstrip('/')}/_aimipay/ops/health",
        "integration_targets": ["website", "saas", "api"],
    }
    public_config.parent.mkdir(parents=True, exist_ok=True)
    public_config.write_text(json.dumps(public_payload, indent=2), encoding="utf-8")

    return {
        "repository_root": str(root),
        "env_file": str(env_target),
        "public_config_path": str(public_config),
        "merchant_base_url": public_payload["merchant_base_url"],
        "manifest_url": public_payload["manifest_url"],
        "discover_url": public_payload["discover_url"],
        "network_profile": network_profile,
        "network_profile_ready": network_report["profile_ready"],
        "created_env": env_target.exists(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare the merchant-side install files for AimiPay.")
    parser.add_argument("--repository-root")
    parser.add_argument("--env-file")
    parser.add_argument("--template-file")
    parser.add_argument("--public-config-path")
    parser.add_argument("--network-profile", default="local")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = ensure_merchant_install(
        repository_root=args.repository_root,
        env_file=args.env_file,
        template_file=args.template_file,
        public_config_path=args.public_config_path,
        network_profile=args.network_profile,
        force=args.force,
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"merchant env: {report['env_file']}")
        print(f"merchant public config: {report['public_config_path']}")
        print(f"merchant base url: {report['merchant_base_url']}")
    return 0


def _env(name: str, default: str) -> str:
    import os

    return os.environ.get(name, default)


if __name__ == "__main__":
    raise SystemExit(main())

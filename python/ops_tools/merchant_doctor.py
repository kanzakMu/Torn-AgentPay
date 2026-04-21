from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path
from typing import Any

from examples.env_loader import load_env_file


def build_merchant_install_report(
    *,
    repository_root: str | Path | None = None,
    env_file: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    python_dir = root / "python"
    env_target = Path(env_file) if env_file else python_dir / ".env.merchant.local"
    env_template = python_dir / ".env.merchant.example"
    public_config = root / "merchant-dist" / "website" / ".generated" / "merchant.public.json"
    merchant_app = root / "python" / "examples" / "merchant_app.py"
    website_script = root / "merchant-dist" / "website" / "aimipay.checkout.js"
    website_example = root / "merchant-dist" / "website" / "embed.checkout.html"

    if env_target.exists():
        load_env_file(env_target, override=True)

    python_available = shutil.which("py") is not None or shutil.which("python") is not None
    node_available = shutil.which("node") is not None
    venv_ready = (root / ".venv" / "Scripts" / "python.exe").exists()
    node_modules_ready = (root / "node_modules").exists()

    seller_address = _env("AIMIPAY_SELLER_ADDRESS", "")
    seller_private_key = _env("AIMIPAY_SELLER_PRIVATE_KEY", "")
    public_base_url = _env("AIMIPAY_PUBLIC_BASE_URL", "")
    service_name = _env("AIMIPAY_SERVICE_NAME", "")

    checks = [
        _check("repository_root_exists", root.exists(), str(root)),
        _check("merchant_env_template_present", env_template.exists(), str(env_template)),
        _check("merchant_env_present", env_target.exists(), str(env_target)),
        _check("python_available", python_available, shutil.which("python") or shutil.which("py") or "python not found"),
        _check("node_available", node_available, shutil.which("node") or "node not found"),
        _check("venv_ready", venv_ready, str(root / ".venv" / "Scripts" / "python.exe")),
        _check("node_modules_ready", node_modules_ready, str(root / "node_modules")),
        _check("merchant_app_present", merchant_app.exists(), str(merchant_app)),
        _check("seller_address_present", bool(seller_address), seller_address or "missing AIMIPAY_SELLER_ADDRESS"),
        _check("seller_private_key_present", bool(seller_private_key), "configured" if seller_private_key else "missing AIMIPAY_SELLER_PRIVATE_KEY"),
        _check("public_base_url_present", bool(public_base_url), public_base_url or "missing AIMIPAY_PUBLIC_BASE_URL"),
        _check("service_name_present", bool(service_name), service_name or "missing AIMIPAY_SERVICE_NAME"),
        _check("merchant_public_config_present", public_config.exists(), str(public_config)),
        _check("website_starter_script_present", website_script.exists(), str(website_script)),
        _check("website_starter_example_present", website_example.exists(), str(website_example)),
    ]

    bootstrap_ready = all(
        item["ok"]
        for item in checks
        if item["name"]
        in {
            "repository_root_exists",
            "merchant_env_template_present",
            "python_available",
            "node_available",
            "merchant_app_present",
            "website_starter_script_present",
            "website_starter_example_present",
        }
    )
    runtime_ready = bootstrap_ready and all(
        item["ok"]
        for item in checks
        if item["name"]
        in {
            "merchant_env_present",
            "venv_ready",
            "node_modules_ready",
            "seller_address_present",
            "seller_private_key_present",
            "public_base_url_present",
            "service_name_present",
            "merchant_public_config_present",
        }
    )
    next_steps = _next_steps(
        bootstrap_ready=bootstrap_ready,
        runtime_ready=runtime_ready,
        env_present=env_target.exists(),
        public_config_present=public_config.exists(),
    )
    return {
        "ok": bootstrap_ready,
        "bootstrap_ready": bootstrap_ready,
        "runtime_ready": runtime_ready,
        "checks": checks,
        "next_steps": next_steps,
    }


def format_merchant_install_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay Merchant Install Doctor",
        f"- bootstrap ready: {report['bootstrap_ready']}",
        f"- runtime ready: {report['runtime_ready']}",
    ]
    for item in report.get("checks", []):
        lines.append(f"- {item['name']}: {'ok' if item['ok'] else 'missing'} ({item['detail']})")
    if report.get("next_steps"):
        lines.append("- next steps:")
        lines.extend(f"  - {step}" for step in report["next_steps"])
    return "\n".join(lines)


def format_merchant_install_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AimiPay Merchant Install Doctor",
        "",
        f"- Bootstrap ready: `{report['bootstrap_ready']}`",
        f"- Runtime ready: `{report['runtime_ready']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for item in report.get("checks", []):
        lines.append(f"| `{item['name']}` | `{'ok' if item['ok'] else 'missing'}` | `{item['detail']}` |")
    if report.get("next_steps"):
        lines.extend(["", "## Next Steps", ""])
        for step in report["next_steps"]:
            lines.append(f"- {step}")
    return "\n".join(lines)


def format_merchant_install_report_html(report: dict[str, Any]) -> str:
    rows = []
    for item in report.get("checks", []):
        status = "ok" if item["ok"] else "missing"
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(item['name'])}</code></td>"
            f"<td class=\"status-{status}\">{html.escape(status)}</td>"
            f"<td>{html.escape(item['detail'])}</td>"
            "</tr>"
        )
    next_steps = "".join(f"<li>{html.escape(step)}</li>" for step in report.get("next_steps", []))
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<title>AimiPay Merchant Install Doctor</title>",
            "<style>",
            "body { font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #1f2937; }",
            "table { border-collapse: collapse; width: 100%; margin-top: 16px; }",
            "th, td { border: 1px solid #d1d5db; padding: 10px; text-align: left; }",
            "th { background: #f3f4f6; }",
            ".status-ok { color: #166534; font-weight: 600; }",
            ".status-missing { color: #991b1b; font-weight: 600; }",
            ".summary { display: flex; gap: 24px; margin: 16px 0; }",
            ".card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; min-width: 180px; }",
            "code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>AimiPay Merchant Install Doctor</h1>",
            "<div class=\"summary\">",
            f"<div class=\"card\"><strong>Bootstrap ready</strong><div>{html.escape(str(report['bootstrap_ready']))}</div></div>",
            f"<div class=\"card\"><strong>Runtime ready</strong><div>{html.escape(str(report['runtime_ready']))}</div></div>",
            "</div>",
            "<h2>Checks</h2>",
            "<table>",
            "<thead><tr><th>Check</th><th>Status</th><th>Detail</th></tr></thead>",
            "<tbody>",
            *rows,
            "</tbody>",
            "</table>",
            "<h2>Next Steps</h2>",
            f"<ul>{next_steps}</ul>" if next_steps else "<p>No additional steps are required.</p>",
            "</body>",
            "</html>",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether the merchant-side AimiPay install is ready.")
    parser.add_argument("--repository-root")
    parser.add_argument("--env-file")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--format", choices=["text", "markdown", "html"], default="text")
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    report = build_merchant_install_report(repository_root=args.repository_root, env_file=args.env_file)
    if args.json:
        rendered = json.dumps(report, indent=2, sort_keys=True)
    elif args.format == "markdown":
        rendered = format_merchant_install_report_markdown(report)
    elif args.format == "html":
        rendered = format_merchant_install_report_html(report)
    else:
        rendered = format_merchant_install_report(report)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["ok"] else 1


def _env(name: str, default: str) -> str:
    import os

    return os.environ.get(name, default)


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _next_steps(
    *,
    bootstrap_ready: bool,
    runtime_ready: bool,
    env_present: bool,
    public_config_present: bool,
) -> list[str]:
    if not bootstrap_ready:
        return [
            "install the official Python 3.11+ distribution and Node.js 20+ first",
            "rerun `python -m ops_tools.merchant_doctor` after the runtimes are on PATH",
        ]
    steps: list[str] = []
    if not env_present:
        steps.append("run `powershell -ExecutionPolicy Bypass -File python/bootstrap_merchant.ps1` to create `python/.env.merchant.local`")
    else:
        steps.append("review `python/.env.merchant.local` and replace placeholder seller key, addresses, and public URL")
    if not public_config_present:
        steps.append("run `python -m ops_tools.merchant_setup --force` to regenerate the website starter public config")
    if not runtime_ready:
        steps.append("start the merchant runtime with `powershell -ExecutionPolicy Bypass -File python/run_merchant_stack.ps1`")
    else:
        steps.append("merchant runtime is ready; wire `merchant-dist/website/aimipay.checkout.js` into your site or SaaS shell")
    return steps


if __name__ == "__main__":
    raise SystemExit(main())

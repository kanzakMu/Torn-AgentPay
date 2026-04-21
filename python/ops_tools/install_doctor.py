from __future__ import annotations

import argparse
import json
import html
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from buyer.wallet import BuyerWallet
from ops_tools.wallet_funding import inspect_wallet_funding


def build_install_report(*, repository_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repository_root or Path(__file__).resolve().parents[2]).resolve()
    python_dir = root / "python"
    package_json = root / "package.json"
    requirements = python_dir / "requirements.txt"
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    env_local = python_dir / ".env.local"
    env_local_example = python_dir / ".env.local.example"
    target_env = python_dir / "target.env"
    buyer_wallet_file = python_dir / ".wallets" / "buyer-wallet.json"
    onboarding_report_path = python_dir / ".agent" / "onboarding-report.json"
    env_values = _read_env_values(env_local)
    merchant_urls = [item.strip() for item in env_values.get("AIMIPAY_MERCHANT_URLS", "").split(",") if item.strip()]

    python_command = _detect_python_command()
    node_available = shutil.which("node") is not None
    npm_available = shutil.which("npm") is not None
    python_available = python_command is not None
    venv_ready = venv_python.exists()
    node_modules_ready = (root / "node_modules").exists()
    buyer_wallet_ready = BuyerWallet.env_has_configured_wallet(env_local)

    checks = [
        _check("repository_root_exists", root.exists(), str(root)),
        _check("package_json_exists", package_json.exists(), str(package_json)),
        _check("python_requirements_exists", requirements.exists(), str(requirements)),
        _check("python_available", python_available, python_command or "python/py launcher not found"),
        _check("node_available", node_available, shutil.which("node") or "node not found"),
        _check("npm_available", npm_available, shutil.which("npm") or "npm not found"),
        _check("venv_ready", venv_ready, str(venv_python)),
        _check("node_modules_ready", node_modules_ready, str(root / "node_modules")),
        _check("env_local_present", env_local.exists(), str(env_local)),
        _check("env_local_example_present", env_local_example.exists(), str(env_local_example)),
        _check("target_env_present", target_env.exists(), str(target_env)),
        _check("merchant_urls_configured", bool(merchant_urls), ", ".join(merchant_urls) or "AIMIPAY_MERCHANT_URLS not set"),
        _check("buyer_wallet_configured", buyer_wallet_ready, str(env_local)),
        _check("buyer_wallet_file_present", buyer_wallet_file.exists(), str(buyer_wallet_file)),
    ]

    bootstrap_ready = all(
        item["ok"]
        for item in checks
        if item["name"]
        in {
            "repository_root_exists",
            "package_json_exists",
            "python_requirements_exists",
            "python_available",
            "node_available",
            "npm_available",
        }
    )
    run_ready = bootstrap_ready and venv_ready and node_modules_ready and env_local.exists() and buyer_wallet_ready
    next_steps = _next_steps(
        bootstrap_ready=bootstrap_ready,
        run_ready=run_ready,
        env_local_present=env_local.exists(),
        venv_ready=venv_ready,
        node_modules_ready=node_modules_ready,
        buyer_wallet_ready=buyer_wallet_ready,
        merchant_urls=merchant_urls,
    )
    funding = inspect_wallet_funding(repository_root=root, env_file=env_local, output_json=False, emit_output=False)
    onboarding = _read_onboarding_report(onboarding_report_path)
    return {
        "ok": bootstrap_ready,
        "bootstrap_ready": bootstrap_ready,
        "run_ready": run_ready,
        "merchant_urls": merchant_urls,
        "checks": checks,
        "next_steps": next_steps,
        "wallet_funding": funding,
        "onboarding": onboarding,
        "onboarding_ui": {
            "api_base_url": _buyer_onboarding_api_base(),
            "page_url": f"{_buyer_onboarding_api_base()}/aimipay/buyer/onboarding",
            "html_path": str(root / "python" / ".agent" / "buyer-onboarding.html"),
        },
    }


def format_install_report(report: dict[str, Any]) -> str:
    lines = [
        "AimiPay Install Doctor",
        f"- bootstrap ready: {report['bootstrap_ready']}",
        f"- run ready: {report['run_ready']}",
    ]
    for item in report.get("checks", []):
        state = "ok" if item["ok"] else "missing"
        lines.append(f"- {item['name']}: {state} ({item['detail']})")
    if report.get("next_steps"):
        lines.append("- next steps:")
        lines.extend(f"  - {step}" for step in report["next_steps"])
    onboarding = report.get("onboarding") or {}
    merchant = onboarding.get("merchant") or {}
    if merchant.get("selected_url") or report.get("merchant_urls"):
        lines.append("- buyer onboarding:")
        lines.append(f"  - merchant url: {merchant.get('selected_url') or ', '.join(report.get('merchant_urls') or [])}")
        lines.append(f"  - next step: {onboarding.get('next_step') or 'not_started'}")
        if merchant.get("service_name"):
            lines.append(f"  - merchant service: {merchant.get('service_name')}")
        offer_count = (merchant.get("offers") or {}).get("count")
        if offer_count is not None:
            lines.append(f"  - offers discovered: {offer_count}")
    funding = report.get("wallet_funding") or {}
    guidance = funding.get("guidance") or []
    if guidance:
        lines.append("- wallet funding guidance:")
        lines.extend(f"  - {step}" for step in guidance)
    return "\n".join(lines)


def format_install_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AimiPay Install Doctor",
        "",
        f"- Bootstrap ready: `{report['bootstrap_ready']}`",
        f"- Run ready: `{report['run_ready']}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for item in report.get("checks", []):
        status = "ok" if item["ok"] else "missing"
        lines.append(f"| `{item['name']}` | `{status}` | `{item['detail']}` |")
    if report.get("next_steps"):
        lines.extend(["", "## Next Steps", ""])
        for step in report["next_steps"]:
            lines.append(f"- {step}")
    onboarding = report.get("onboarding") or {}
    merchant = onboarding.get("merchant") or {}
    if merchant.get("selected_url") or report.get("merchant_urls"):
        lines.extend(["", "## Buyer Onboarding", ""])
        lines.append(f"- Merchant URL: `{merchant.get('selected_url') or ', '.join(report.get('merchant_urls') or [])}`")
        lines.append(f"- Next step: `{onboarding.get('next_step') or 'not_started'}`")
        if merchant.get("service_name"):
            lines.append(f"- Merchant service: `{merchant.get('service_name')}`")
        offer_count = (merchant.get("offers") or {}).get("count")
        if offer_count is not None:
            lines.append(f"- Offers discovered: `{offer_count}`")
        offer_items = (merchant.get("offers") or {}).get("items") or []
        if offer_items:
            lines.append("")
            lines.append("| Offer | Route | Type |")
            lines.append("| --- | --- | --- |")
            for item in offer_items[:3]:
                lines.append(
                    f"| `{item.get('capability_id')}` | `{item.get('route_path')}` | `{item.get('capability_type')}` |"
                )
    funding = report.get("wallet_funding") or {}
    guidance = funding.get("guidance") or []
    if guidance:
        lines.extend(["", "## Wallet Funding Guidance", ""])
        for step in guidance:
            lines.append(f"- {step}")
    return "\n".join(lines)


def format_install_report_html(report: dict[str, Any]) -> str:
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
    funding_guidance = "".join(
        f"<li>{html.escape(step)}</li>" for step in (report.get("wallet_funding") or {}).get("guidance", [])
    )
    onboarding = report.get("onboarding") or {}
    merchant = onboarding.get("merchant") or {}
    merchant_url = merchant.get("selected_url") or ", ".join(report.get("merchant_urls") or [])
    offer_items = (merchant.get("offers") or {}).get("items") or []
    offer_cards = "".join(
        [
            "<div class=\"offer-card\">"
            f"<strong>{html.escape(str(item.get('capability_id') or 'offer'))}</strong>"
            f"<div>{html.escape(str(item.get('route_path') or ''))}</div>"
            f"<div class=\"muted\">{html.escape(str(item.get('capability_type') or 'api'))}</div>"
            "</div>"
            for item in offer_items[:3]
        ]
    )
    merchant_resources = "".join(
        f"<li><a href=\"{html.escape(resource.get('url', ''))}\">{html.escape(resource.get('label', 'Link'))}</a></li>"
        for resource in ((merchant.get("host_action") or {}).get("resources") or [])
    )
    onboarding_ui = report.get("onboarding_ui") or {}
    api_base_url = onboarding_ui.get("api_base_url", "http://127.0.0.1:8011")
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head>",
            "<meta charset=\"utf-8\">",
            "<title>AimiPay Install Doctor</title>",
            "<style>",
            "body { font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #1f2937; }",
            "table { border-collapse: collapse; width: 100%; margin-top: 16px; }",
            "th, td { border: 1px solid #d1d5db; padding: 10px; text-align: left; }",
            "th { background: #f3f4f6; }",
            ".status-ok { color: #166534; font-weight: 600; }",
            ".status-missing { color: #991b1b; font-weight: 600; }",
            ".summary { display: flex; gap: 24px; margin: 16px 0; }",
            ".card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; min-width: 180px; }",
            ".panel { background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%); border: 1px solid #dbeafe; border-radius: 12px; padding: 20px; margin: 18px 0; }",
            ".field-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 12px; }",
            ".field { background: #ffffff; border: 1px solid #dbeafe; border-radius: 10px; padding: 12px; }",
            ".field label { display: block; font-size: 12px; color: #475569; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.04em; }",
            ".field .value { font-weight: 600; word-break: break-word; }",
            ".actions { margin-top: 12px; }",
            ".actions ul { margin-top: 8px; }",
            ".offer-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 12px; }",
            ".offer-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }",
            ".muted { color: #64748b; font-size: 13px; }",
            "code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>AimiPay Install Doctor</h1>",
            "<div class=\"summary\">",
            f"<div class=\"card\"><strong>Bootstrap ready</strong><div>{html.escape(str(report['bootstrap_ready']))}</div></div>",
            f"<div class=\"card\"><strong>Run ready</strong><div>{html.escape(str(report['run_ready']))}</div></div>",
            "</div>",
            "<div class=\"panel\">",
            "<h2>Buyer Onboarding</h2>",
            "<p>Use this first screen to confirm the merchant URL, wallet readiness, and the next action before the first paid purchase.</p>",
            "<div class=\"field-row\">",
            "<div class=\"field\">",
            "<label>Merchant URL</label>",
            f"<div class=\"value\">{html.escape(merchant_url or 'Not configured yet')}</div>",
            "</div>",
            "<div class=\"field\">",
            "<label>Next Step</label>",
            f"<div class=\"value\">{html.escape(str(onboarding.get('next_step') or 'connect_merchant'))}</div>",
            "</div>",
            "<div class=\"field\">",
            "<label>Merchant Service</label>",
            f"<div class=\"value\">{html.escape(str(merchant.get('service_name') or 'Not discovered yet'))}</div>",
            "</div>",
            "<div class=\"field\">",
            "<label>Offers Discovered</label>",
            f"<div class=\"value\">{html.escape(str((merchant.get('offers') or {}).get('count', 0)))}</div>",
            "</div>",
            "</div>",
            "<div class=\"actions\">",
            f"<p>{html.escape(str(((merchant.get('host_action') or {}).get('message')) or (((report.get('wallet_funding') or {}).get('host_action') or {}).get('message')) or 'Connect a merchant, finish wallet onboarding, and continue to your first purchase.'))}</p>",
            "<form id=\"merchant-url-form\">",
            "<div class=\"field-row\">",
            "<div class=\"field\">",
            "<label for=\"merchant-url-input\">Merchant URL</label>",
            f"<input id=\"merchant-url-input\" name=\"merchant_url\" type=\"url\" value=\"{html.escape(merchant_url or '')}\" placeholder=\"https://merchant.example\" style=\"width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:8px;\">",
            "</div>",
            "</div>",
            "<div style=\"display:flex;gap:12px;flex-wrap:wrap;margin-top:12px;\">",
            "<button type=\"submit\" style=\"background:#0f766e;color:#fff;border:none;border-radius:999px;padding:10px 18px;font-weight:600;cursor:pointer;\">Save Merchant URL</button>",
            "<button type=\"button\" id=\"refresh-onboarding-button\" style=\"background:#fff;color:#0f172a;border:1px solid #cbd5e1;border-radius:999px;padding:10px 18px;font-weight:600;cursor:pointer;\">Refresh Offers</button>",
            "</div>",
            f"<p class=\"muted\" id=\"onboarding-service-hint\">Interactive actions use the local onboarding service at {html.escape(api_base_url)}.</p>",
            "<p id=\"onboarding-status\" class=\"muted\"></p>",
            "</form>",
            f"<ul>{merchant_resources}</ul>" if merchant_resources else "",
            "</div>",
            f"<div class=\"offer-grid\">{offer_cards}</div>" if offer_cards else "<p class=\"muted\">No offers previewed yet. Set a merchant URL and rerun onboarding after the merchant is reachable.</p>",
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
            "<h2>Wallet Funding Guidance</h2>",
            f"<ul>{funding_guidance}</ul>" if funding_guidance else "<p>No wallet funding guidance is required.</p>",
            "<script>",
            f"const AIMIPAY_ONBOARDING_API = {json.dumps(api_base_url)};",
            "const statusEl = document.getElementById('onboarding-status');",
            "async function callOnboardingApi(path, payload) {",
            "  statusEl.textContent = 'Updating buyer onboarding...';",
            "  const response = await fetch(`${AIMIPAY_ONBOARDING_API}${path}`, {",
            "    method: 'POST',",
            "    headers: {'Content-Type': 'application/json'},",
            "    body: JSON.stringify(payload || {}),",
            "  });",
            "  const data = await response.json().catch(() => ({}));",
            "  if (!response.ok) {",
            "    const message = data?.detail?.error || data?.error || `request failed (${response.status})`;",
            "    throw new Error(message);",
            "  }",
            "  return data;",
            "}",
            "document.getElementById('merchant-url-form')?.addEventListener('submit', async (event) => {",
            "  event.preventDefault();",
            "  const merchantUrl = document.getElementById('merchant-url-input')?.value?.trim() || '';",
            "  if (!merchantUrl) {",
            "    statusEl.textContent = 'Enter a merchant URL first.';",
            "    return;",
            "  }",
            "  try {",
            "    await callOnboardingApi('/aimipay/buyer/onboarding/merchant-url', {merchant_url: merchantUrl});",
            "    statusEl.textContent = 'Merchant URL saved. Reloading onboarding view...';",
            "    window.location.reload();",
            "  } catch (error) {",
            "    statusEl.textContent = `Could not save merchant URL: ${error.message}`;",
            "  }",
            "});",
            "document.getElementById('refresh-onboarding-button')?.addEventListener('click', async () => {",
            "  try {",
            "    await callOnboardingApi('/aimipay/buyer/onboarding/refresh', {});",
            "    statusEl.textContent = 'Buyer onboarding refreshed. Reloading...';",
            "    window.location.reload();",
            "  } catch (error) {",
            "    statusEl.textContent = `Could not refresh onboarding: ${error.message}`;",
            "  }",
            "});",
            "</script>",
            "</body>",
            "</html>",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether an ordinary user can bootstrap and run AimiPay locally.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--format", choices=["text", "markdown", "html"], default="text")
    parser.add_argument("--output")
    parser.add_argument("--repository-root")
    args = parser.parse_args(argv)

    report = build_install_report(repository_root=args.repository_root)
    if args.json:
        rendered = json.dumps(report, indent=2, sort_keys=True)
    elif args.format == "markdown":
        rendered = format_install_report_markdown(report)
    elif args.format == "html":
        rendered = format_install_report_html(report)
    else:
        rendered = format_install_report(report)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0 if report["ok"] else 1


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _detect_python_command() -> str | None:
    candidates: list[list[str]] = []
    if shutil.which("py") is not None:
        candidates.append(["py", "-3"])
    if shutil.which("python") is not None:
        candidates.append(["python"])
    for command in candidates:
        try:
            subprocess.run(
                [*command, "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
            return " ".join(command)
        except Exception:
            continue
    return None


def _read_env_values(path: Path) -> dict[str, str]:
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


def _read_onboarding_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _buyer_onboarding_api_base() -> str:
    port = os.environ.get("AIMIPAY_BUYER_ONBOARDING_PORT", "8011").strip() or "8011"
    return f"http://127.0.0.1:{port}"


def _next_steps(
    *,
    bootstrap_ready: bool,
    run_ready: bool,
    env_local_present: bool,
    venv_ready: bool,
    node_modules_ready: bool,
    buyer_wallet_ready: bool,
    merchant_urls: list[str],
) -> list[str]:
    if not bootstrap_ready:
        return [
            "install the official Python 3.11+ distribution and Node.js 20+ first",
            "rerun `python -m ops_tools.install_doctor` after the runtimes are on PATH",
        ]
    steps: list[str] = []
    if not env_local_present:
        steps.append("run `powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1` to create `.env.local` and a buyer wallet")
    if not venv_ready or not node_modules_ready:
        steps.append("run `powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1`")
    if env_local_present:
        steps.append("review `python/.env.local` after bootstrap and confirm `AIMIPAY_MERCHANT_URLS` points at the merchant you want to use")
    if env_local_present and not buyer_wallet_ready:
        steps.append("run `powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1` to auto-create a buyer wallet, or run `python -m ops_tools.wallet_setup --force-create`")
    if env_local_present and not merchant_urls:
        steps.append("set `AIMIPAY_MERCHANT_URLS` to the merchant URL you want the buyer to connect to")
    if not run_ready:
        steps.append("start the local stack with `powershell -ExecutionPolicy Bypass -File python/run_local_stack.ps1`")
    if not steps:
        steps.append("local install is ready; start the merchant demo or dry run scripts directly")
    return steps


if __name__ == "__main__":
    raise SystemExit(main())

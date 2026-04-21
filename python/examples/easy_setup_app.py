from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ops_tools.install_doctor import build_install_report
from ops_tools.merchant_doctor import build_merchant_install_report


class BuyerInstallRequest(BaseModel):
    merchant_url: str = "http://127.0.0.1:8000"
    network_profile: str = ""
    skip_npm_install: bool = True
    skip_python_install: bool = True
    buyer_onboarding_port: int = 8011


class MerchantInstallRequest(BaseModel):
    network_profile: str = "local"
    skip_npm_install: bool = True
    skip_python_install: bool = True


class LaunchRequest(BaseModel):
    port: int


def create_app() -> FastAPI:
    repository_root = Path(os.environ.get("AIMIPAY_REPOSITORY_ROOT", Path(__file__).resolve().parents[2])).resolve()
    app = FastAPI(title="AimiPay Easy Setup")

    @app.get("/aimipay/easy-setup")
    async def easy_setup_page() -> HTMLResponse:
        return HTMLResponse(_render_easy_setup_html())

    @app.get("/aimipay/easy-setup/status")
    async def easy_setup_status() -> dict[str, Any]:
        return _status_payload(repository_root)

    @app.post("/aimipay/easy-setup/install/buyer")
    async def easy_setup_install_buyer(payload: BuyerInstallRequest) -> dict[str, Any]:
        args = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repository_root / "python" / "bootstrap_local.ps1"),
            "-MerchantUrl",
            payload.merchant_url,
            "-BuyerOnboardingPort",
            str(payload.buyer_onboarding_port),
        ]
        if payload.network_profile:
            args += ["-NetworkProfile", payload.network_profile]
        if payload.skip_npm_install:
            args.append("-SkipNpmInstall")
        if payload.skip_python_install:
            args.append("-SkipPythonInstall")
        result = _run_blocking(args, cwd=repository_root)
        return {
            "ok": result["returncode"] == 0,
            "operation": "install_buyer",
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "status": _status_payload(repository_root),
        }

    @app.post("/aimipay/easy-setup/install/merchant")
    async def easy_setup_install_merchant(payload: MerchantInstallRequest) -> dict[str, Any]:
        args = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repository_root / "python" / "bootstrap_merchant.ps1"),
            "-NetworkProfile",
            payload.network_profile,
        ]
        if payload.skip_npm_install:
            args.append("-SkipNpmInstall")
        if payload.skip_python_install:
            args.append("-SkipPythonInstall")
        result = _run_blocking(args, cwd=repository_root)
        return {
            "ok": result["returncode"] == 0,
            "operation": "install_merchant",
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "status": _status_payload(repository_root),
        }

    @app.post("/aimipay/easy-setup/start/buyer-onboarding")
    async def easy_setup_start_buyer_onboarding(payload: LaunchRequest) -> dict[str, Any]:
        _launch_background(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(repository_root / "python" / "run_buyer_onboarding.ps1"),
                "-Port",
                str(payload.port),
            ],
            cwd=repository_root,
        )
        return {
            "ok": True,
            "operation": "start_buyer_onboarding",
            "url": f"http://127.0.0.1:{payload.port}/aimipay/buyer/onboarding",
        }

    @app.post("/aimipay/easy-setup/start/merchant")
    async def easy_setup_start_merchant(payload: LaunchRequest) -> dict[str, Any]:
        _launch_background(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(repository_root / "python" / "run_merchant_stack.ps1"),
                "-MerchantPort",
                str(payload.port),
            ],
            cwd=repository_root,
        )
        return {
            "ok": True,
            "operation": "start_merchant",
            "url": f"http://127.0.0.1:{payload.port}/aimipay/install",
        }

    return app


def _status_payload(repository_root: Path) -> dict[str, Any]:
    buyer = build_install_report(repository_root=repository_root)
    merchant = build_merchant_install_report(repository_root=repository_root)
    return {
        "buyer": buyer,
        "merchant": merchant,
        "links": {
            "buyer_onboarding_local": "http://127.0.0.1:8011/aimipay/buyer/onboarding",
            "merchant_dashboard_local": "http://127.0.0.1:8000/aimipay/install",
            "local_demo_command": "powershell -ExecutionPolicy Bypass -File python/run_local_stack.ps1",
        },
    }


def _run_blocking(args: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _launch_background(args: list[str], *, cwd: Path) -> None:
    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(
        args,
        cwd=str(cwd),
        creationflags=creationflags,
    )


def _render_easy_setup_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AimiPay Easy Setup</title>
<style>
body { font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #0f172a; background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%); }
.shell { max-width: 1180px; margin: 0 auto; }
.hero { background: #ffffff; border: 1px solid #dbeafe; border-radius: 18px; padding: 24px; box-shadow: 0 20px 50px rgba(15, 23, 42, 0.06); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; margin-top: 20px; }
.card { background: #ffffff; border: 1px solid #dbeafe; border-radius: 16px; padding: 20px; }
.field { margin-top: 12px; }
label { display: block; font-size: 12px; color: #475569; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.04em; }
input, select { width: 100%; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 10px; font: inherit; }
button { background: #0f766e; color: #fff; border: none; border-radius: 999px; padding: 10px 18px; font-weight: 600; cursor: pointer; margin-top: 14px; }
button.secondary { background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }
.muted { color: #64748b; }
.status { margin-top: 12px; white-space: pre-wrap; font-family: Consolas, monospace; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px; min-height: 72px; }
.pill { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.pill.ok { background: #dcfce7; color: #166534; }
.pill.missing { background: #fee2e2; color: #991b1b; }
a { color: #0f766e; text-decoration: none; }
</style>
</head>
<body>
<div class="shell">
  <div class="hero">
    <h1>AimiPay Easy Setup</h1>
    <p class="muted">Use one page to install the buyer, install the merchant, start the buyer onboarding UI, and open the merchant dashboard. The goal here is simple: no hunting across scripts.</p>
    <p><strong>Flow:</strong> install buyer -> install merchant -> start merchant dashboard -> open buyer onboarding -> review offers -> run first purchase.</p>
  </div>
  <div class="grid">
    <div class="card">
      <h2>Buyer Install</h2>
      <p class="muted">Best for the agent or buyer side. Set the merchant URL here so the buyer onboarding page already knows where to connect.</p>
      <div class="field">
        <label for="buyer-merchant-url">Merchant URL</label>
        <input id="buyer-merchant-url" type="url" value="http://127.0.0.1:8000">
      </div>
      <div class="field">
        <label for="buyer-network-profile">Network Profile</label>
        <select id="buyer-network-profile">
          <option value="">merchant-driven</option>
          <option value="local">local</option>
          <option value="nile">nile</option>
          <option value="mainnet">mainnet</option>
          <option value="custom">custom</option>
        </select>
      </div>
      <button id="install-buyer">Install Buyer</button>
      <div id="buyer-status" class="status">Waiting for action.</div>
    </div>
    <div class="card">
      <h2>Merchant Install</h2>
      <p class="muted">Prepare the merchant runtime and control plane with the selected network profile.</p>
      <div class="field">
        <label for="merchant-network-profile">Network Profile</label>
        <select id="merchant-network-profile">
          <option value="local">local</option>
          <option value="nile">nile</option>
          <option value="mainnet">mainnet</option>
          <option value="custom">custom</option>
        </select>
      </div>
      <button id="install-merchant">Install Merchant</button>
      <div id="merchant-status" class="status">Waiting for action.</div>
    </div>
    <div class="card">
      <h2>Open Local UIs</h2>
      <p class="muted">If you want the simplest workflow, use these launch buttons after install.</p>
      <button id="start-buyer-ui" class="secondary">Start Buyer Onboarding UI</button>
      <button id="start-merchant-ui" class="secondary">Start Merchant Dashboard</button>
      <div id="launch-status" class="status">Waiting for action.</div>
    </div>
  </div>
  <div class="grid">
    <div class="card">
      <h2>Buyer Status</h2>
      <div id="buyer-summary" class="status">Loading buyer status...</div>
    </div>
    <div class="card">
      <h2>Merchant Status</h2>
      <div id="merchant-summary" class="status">Loading merchant status...</div>
    </div>
    <div class="card">
      <h2>Quick Links</h2>
      <div id="quick-links" class="status">Loading local links...</div>
    </div>
  </div>
</div>
<script>
const apiBase = "";
function pretty(value) {
  return JSON.stringify(value, null, 2);
}
async function postJson(path, payload) {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload || {})
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data?.stderr || data?.detail?.error || `request failed (${response.status})`);
  }
  return data;
}
function renderChecks(report) {
  const checks = (report?.checks || []).map((item) => `${item.ok ? "ok" : "missing"}  ${item.name}: ${item.detail}`).join("\\n");
  const nextSteps = (report?.next_steps || []).map((item) => `- ${item}`).join("\\n");
  return `ready: ${report?.run_ready ?? report?.runtime_ready}\\n\\n${checks}\\n\\nnext steps:\\n${nextSteps}`;
}
async function refreshStatus() {
  const response = await fetch("/aimipay/easy-setup/status");
  const data = await response.json();
  document.getElementById("buyer-summary").textContent = renderChecks(data.buyer);
  document.getElementById("merchant-summary").textContent = renderChecks(data.merchant);
  document.getElementById("quick-links").innerHTML = `
    <div><a href="${data.links.buyer_onboarding_local}" target="_blank">Buyer onboarding UI</a></div>
    <div><a href="${data.links.merchant_dashboard_local}" target="_blank">Merchant dashboard</a></div>
    <div class="muted" style="margin-top:8px;">${data.links.local_demo_command}</div>
  `;
}
document.getElementById("install-buyer").addEventListener("click", async () => {
  const box = document.getElementById("buyer-status");
  box.textContent = "Installing buyer...";
  try {
    const result = await postJson("/aimipay/easy-setup/install/buyer", {
      merchant_url: document.getElementById("buyer-merchant-url").value,
      network_profile: document.getElementById("buyer-network-profile").value,
      skip_npm_install: true,
      skip_python_install: true,
      buyer_onboarding_port: 8011
    });
    box.textContent = `Buyer install finished.\\n\\n${result.stdout || "done"}`;
    await refreshStatus();
  } catch (error) {
    box.textContent = `Buyer install failed.\\n\\n${error.message}`;
  }
});
document.getElementById("install-merchant").addEventListener("click", async () => {
  const box = document.getElementById("merchant-status");
  box.textContent = "Installing merchant...";
  try {
    const result = await postJson("/aimipay/easy-setup/install/merchant", {
      network_profile: document.getElementById("merchant-network-profile").value,
      skip_npm_install: true,
      skip_python_install: true
    });
    box.textContent = `Merchant install finished.\\n\\n${result.stdout || "done"}`;
    await refreshStatus();
  } catch (error) {
    box.textContent = `Merchant install failed.\\n\\n${error.message}`;
  }
});
document.getElementById("start-buyer-ui").addEventListener("click", async () => {
  const box = document.getElementById("launch-status");
  box.textContent = "Starting buyer onboarding UI...";
  try {
    const result = await postJson("/aimipay/easy-setup/start/buyer-onboarding", {port: 8011});
    box.innerHTML = `Buyer onboarding UI is starting.<br><a href="${result.url}" target="_blank">${result.url}</a>`;
  } catch (error) {
    box.textContent = `Could not start buyer onboarding UI.\\n\\n${error.message}`;
  }
});
document.getElementById("start-merchant-ui").addEventListener("click", async () => {
  const box = document.getElementById("launch-status");
  box.textContent = "Starting merchant dashboard...";
  try {
    const result = await postJson("/aimipay/easy-setup/start/merchant", {port: 8000});
    box.innerHTML = `Merchant dashboard is starting.<br><a href="${result.url}" target="_blank">${result.url}</a>`;
  } catch (error) {
    box.textContent = `Could not start merchant dashboard.\\n\\n${error.message}`;
  }
});
refreshStatus();
</script>
</body>
</html>
"""

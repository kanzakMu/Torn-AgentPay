from ops_tools.install_doctor import (
    format_install_report,
    format_install_report_html,
    format_install_report_markdown,
)


def test_install_doctor_report_format_is_readable() -> None:
    rendered = format_install_report(
        {
            "bootstrap_ready": True,
            "run_ready": False,
            "checks": [
                {"name": "python_available", "ok": True, "detail": "py -3"},
                {"name": "venv_ready", "ok": False, "detail": "E:/trade/.venv/Scripts/python.exe"},
            ],
            "next_steps": [
                "run `powershell -ExecutionPolicy Bypass -File python/bootstrap_local.ps1`",
                "start the local stack with `powershell -ExecutionPolicy Bypass -File python/run_local_stack.ps1`",
            ],
        }
    )

    assert "AimiPay Install Doctor" in rendered
    assert "- bootstrap ready: True" in rendered
    assert "python_available: ok" in rendered
    assert "venv_ready: missing" in rendered


def test_install_doctor_markdown_and_html_are_readable() -> None:
    report = {
        "bootstrap_ready": True,
        "run_ready": True,
        "merchant_urls": ["https://merchant.example"],
        "checks": [
            {"name": "python_available", "ok": True, "detail": "py -3"},
            {"name": "env_local_present", "ok": False, "detail": "E:/trade/python/.env.local"},
        ],
        "next_steps": ["copy python/.env.local.example to python/.env.local"],
        "onboarding": {
            "next_step": "review_offers",
            "merchant": {
                "selected_url": "https://merchant.example",
                "service_name": "Example Merchant",
                "offers": {
                    "count": 2,
                    "items": [
                        {"capability_id": "search", "route_path": "/tools/search", "capability_type": "web_search"}
                    ],
                },
                "host_action": {"message": "Merchant connected and offers discovered."},
            },
        },
    }

    markdown = format_install_report_markdown(report)
    html = format_install_report_html(report)

    assert "# AimiPay Install Doctor" in markdown
    assert "| `python_available` | `ok` | `py -3` |" in markdown
    assert "## Buyer Onboarding" in markdown
    assert "`https://merchant.example`" in markdown
    assert "<html lang=\"en\">" in html
    assert "status-ok" in html
    assert "copy python/.env.local.example" in html
    assert "Buyer Onboarding" in html
    assert "https://merchant.example" in html
    assert "Offers Discovered" in html
    assert "merchant-url-form" in html
    assert "Save Merchant URL" in html
    assert "Refresh Offers" in html

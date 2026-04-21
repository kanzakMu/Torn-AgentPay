import json
import sys
from pathlib import Path

from ops_tools.install_agent_package import install_agent_package
from ops_tools.verify_agent_installation import verify_agent_installation


def test_install_agent_package_repo_local_copies_skill_plugin_and_connector(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fake_root = tmp_path / "install-target"
    env_file = fake_root / "repo-env" / ".env.local"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "\n".join(
            [
                "AIMIPAY_BUYER_ADDRESS=TRX_BUYER",
                "AIMIPAY_BUYER_PRIVATE_KEY=0xabc123",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report = install_agent_package(
        repository_root=repo_root,
        target="all",
        mode="home-local",
        install_root=fake_root,
        merchant_url="https://merchant.example",
        env_file=env_file,
        output_json=False,
    )

    assert report["ok"] is True
    assert "skill" in report["installed"]
    assert "plugin" in report["installed"]
    assert "connector" in report["installed"]
    assert "codex" in report["generated_host_configs"]
    assert "openclaw" in report["generated_host_configs"]
    assert "hermes" in report["generated_host_configs"]
    assert report["startup_onboarding"]["merchant"]["merchant_urls"] == ["https://merchant.example"]
    assert (fake_root / ".codex" / "skills" / "aimipay-agent" / "SKILL.md").exists()
    assert (fake_root / "plugins" / "aimipay-agent" / ".codex-plugin" / "plugin.json").exists()
    assert (fake_root / ".agents" / "plugins" / "marketplace.json").exists()
    mcp_payload = json.loads((fake_root / "plugins" / "aimipay-agent" / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp_payload["mcpServers"]["aimipay-agent"]
    assert server["command"] == sys.executable
    assert "AIMIPAY_REPOSITORY_ROOT" in server["env"]
    assert server["env"]["AIMIPAY_MERCHANT_URLS"] == "https://merchant.example"
    openclaw_payload = json.loads(
        (fake_root / ".codex" / "agent-hosts" / "openclaw" / "openclaw_mcp_config.json").read_text(encoding="utf-8")
    )
    assert openclaw_payload["mcpServers"]["aimipay-agent"]["env"]["AIMIPAY_MERCHANT_URLS"] == "https://merchant.example"
    verify_report = verify_agent_installation(
        repository_root=repo_root,
        mode="home-local",
        install_root=fake_root,
        expected_targets=["skill", "plugin", "connector", "codex", "mcp", "claude", "cua", "openclaw", "hermes"],
        output_json=False,
    )
    assert verify_report["ok"] is True

import json
import sys
from pathlib import Path

from ops_tools.install_ai_host import install_ai_host
from ops_tools.install_agent_package import install_agent_package
from ops_tools.install_skill import install_aimipay_skill
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
    assert (fake_root / ".codex" / "skills" / "aimipay-agent" / "aimipay_skill_runner.py").exists()
    assert (fake_root / ".codex" / "skills" / "aimipay-agent" / "skill-runtime.json").exists()
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


def test_install_skill_only_copies_codex_skill(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fake_root = tmp_path / "skill-install-target"

    report = install_aimipay_skill(
        repository_root=repo_root,
        mode="home-local",
        install_root=fake_root,
        run_verify=True,
        output_json=False,
    )

    assert report["ok"] is True
    assert report["next_step"] == "restart_agent_or_reload_skills"
    skill_root = fake_root / ".codex" / "skills" / "aimipay-agent"
    assert (skill_root / "SKILL.md").exists()
    assert (skill_root / "aimipay_skill_runner.py").exists()
    runtime_config = json.loads((skill_root / "skill-runtime.json").read_text(encoding="utf-8"))
    assert runtime_config["schema_version"] == "aimipay.skill-runtime.v1"
    assert runtime_config["repository_root"] == str(repo_root)
    assert runtime_config["runner"] == "aimipay_skill_runner.py"
    assert not (fake_root / "plugins" / "aimipay-agent").exists()
    assert not (fake_root / ".codex" / "agent-dist" / "connector-package.json").exists()


def test_install_ai_host_generates_next_steps_and_reports(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fake_root = tmp_path / "ai-host-install-target"
    env_file = fake_root / "repo-env" / ".env.local"
    env_file.parent.mkdir(parents=True)
    env_file.write_text(
        "AIMIPAY_BUYER_ADDRESS=TRX_BUYER\nAIMIPAY_BUYER_PRIVATE_KEY=0xabc123\n",
        encoding="utf-8",
    )

    report = install_ai_host(
        repository_root=repo_root,
        host="codex",
        mode="home-local",
        install_root=fake_root,
        merchant_url="https://merchant.example",
        env_file=env_file,
        run_onboarding=False,
        output_json=False,
    )

    assert report["ok"] is True
    assert report["host"] == "codex"
    assert "skill" in report["installed"]
    assert "codex" in report["generated_host_configs"]
    assert Path(report["install_report_path"]).exists()
    assert Path(report["next_steps_path"]).exists()
    actions = {item["action"] for item in report["next_steps"]}
    assert "reload_or_restart_agent_skills" in actions
    assert "restart_codex_or_import_generated_package" in actions

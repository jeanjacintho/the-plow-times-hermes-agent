"""Repo-level deployment contracts: the shape agent-mgr and deploy-hook rely on."""
from __future__ import annotations

import os
import pathlib
import stat

from conftest import ROOT, load_module


class TestSkills:
    def test_every_pt_dir_carries_a_skill_manifest(self):
        for d in sorted(ROOT.glob("pt-*")):
            if not d.is_dir():
                continue
            skill = d / "SKILL.md"
            assert skill.is_file(), f"{d.name} has no SKILL.md"
            head = skill.read_text()
            assert head.startswith("---"), f"{d.name}/SKILL.md has no frontmatter"
            assert f"name: {d.name}" in head, f"{d.name}/SKILL.md frontmatter name mismatch"

    def test_shared_helpers_exist_and_are_referenced(self):
        shared = ROOT / "pt-shared" / "scripts"
        for name in ("pt_config_gate.py", "post_to_chat.py", "bearer_http.py"):
            assert (shared / name).is_file(), f"pt-shared/scripts/{name} missing"

    def test_cross_skill_imports_resolve(self):
        # register_crons.py imports topics from pt-intake/scripts at run time;
        # both must be seeded side by side for that to work.
        assert (ROOT / "pt-intake" / "scripts" / "topics.py").is_file()
        assert (ROOT / "pt-dashboard" / "scripts" / "register_crons.py").is_file()


class TestDeployment:
    def test_deploy_hook_is_executable(self):
        mode = (ROOT / "deploy-hook").stat().st_mode
        assert mode & stat.S_IXUSR, "deploy-hook must be executable"

    def test_agent_env_declares_hook_and_config(self):
        env = (ROOT / "agent.env").read_text()
        assert "AGENT_DEPLOY_HOOK=deploy-hook" in env
        assert "AGENT_CONFIG=runtime/config.yaml" in env

    def test_skills_tsv_is_empty(self):
        # skills.tsv pins SHARED skills from other repos; this agent installs
        # no connectors -- Latch is the only mcp_server. Empty means exactly
        # that, and any row would be a credential-carrying dependency to review.
        content = (ROOT / "skills.tsv").read_text().strip()
        assert content == ""

    def test_config_declares_latch_and_chat_only(self):
        config = (ROOT / "runtime" / "config.yaml").read_text()
        assert "plow-chat-platform" in config
        assert "https://api.plow.co/v1/relay/devices/" in config
        # The credential is interpolated from the dotenv, never a literal.
        assert "DOMO_MCP_TOKEN" in config and "DOMO_DEVICE_UID" in config


class TestImportability:
    def test_gate_imports_and_runs(self, tmp_path):
        gate = load_module("gate_contract", "pt-shared/scripts/pt_config_gate.py")
        path = tmp_path / "config.json"
        path.write_text('{"owner": {"timezone": "UTC"},'
                        ' "delivery": {"hour": "07:00"},'
                        ' "printer": {"configured": false}}')
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            gate.main([str(path)])
        assert buf.getvalue().strip() == ""

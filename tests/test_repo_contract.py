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
        for name in ("pt_config_gate.py", "post_to_chat.py", "bearer_http.py",
                     "run_lock.py"):
            assert (shared / name).is_file(), f"pt-shared/scripts/{name} missing"

    def test_edition_renderer_and_template_exist(self):
        edition = ROOT / "pt-edition"
        assert (edition / "scripts" / "render_edition.py").is_file()
        assert (edition / "template.html").is_file()

    def test_template_carries_no_script(self):
        # The Chrome-on-Mac PDF fallback executes JavaScript; the template
        # must stay inert, and the renderer is the only writer of markup.
        template = (ROOT / "pt-edition" / "template.html").read_text()
        assert "<script" not in template.lower()
        assert "onload=" not in template.lower()

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

    def test_compose_override_carries_no_skill_mounts(self):
        # Skills ride the deploy-hook seed into the agent's home, not :ro
        # mounts -- a :ro mount makes the agent's own skill edits die with
        # EROFS. The override file is legitimate for the env vars below; only
        # a `volumes:` section reintroducing the old mount delivery is the
        # regression this guards against. Same guard memory-vault adopted.
        override = ROOT / "compose.override.yml"
        assert override.is_file(), "compose.override.yml pins HERMES_PROVIDER/HERMES_MODEL"
        assert "volumes:" not in override.read_text(), (
            "compose.override.yml declares volumes: -- skills are seeded by "
            "the deploy-hook now, not mounted read-only"
        )

    def test_compose_override_pins_provider_and_model(self):
        # plow-init reads these two from the real container environment on
        # every boot and rewrites model.provider/model.default from them, so
        # the pair must live here -- the home .env cannot reach that
        # environment. Assert both are present and non-empty.
        import re

        text = (ROOT / "compose.override.yml").read_text()
        provider = re.search(r"HERMES_PROVIDER=(\S+)", text)
        model = re.search(r"HERMES_MODEL=(\S+)", text)
        assert provider and provider.group(1) == "openrouter"
        assert model and model.group(1) == "google/gemini-2.5-flash-lite"

    def test_dockerfile_installs_weasyprint_for_the_pdf_leg(self):
        # The base image has no HTML-to-PDF engine; the renderer's --pdf leg
        # only works because this image installs weasyprint. The build's own
        # import check is the guard that it actually imports (native Pango/
        # Cairo binding fails at import, not at install).
        dockerfile = ROOT / "Dockerfile"
        assert dockerfile.is_file(), "Dockerfile installs weasyprint for the PDF leg"
        text = dockerfile.read_text()
        assert "weasyprint" in text
        assert "import weasyprint" in text
        # The build check must RENDER, not just import: a pydyf/weasyprint
        # mismatch imports clean and dies on the first write_pdf.
        assert "write_pdf" in text
        assert "pydyf" in text
        # Installed into the system interpreter's dist-packages, so a login
        # shell cannot hide it (PATH resets) and `--system`'s wrong path is
        # avoided. Both mistakes were measured on this base.
        assert "--target /usr/local/lib/python3.13/dist-packages" in text
        assert "--python /usr/bin/python3" in text
        # Pinned by digest, like the fleet pin -- a tag re-resolves on pull.
        from_line = next(
            line for line in text.splitlines() if line.startswith("FROM ")
        )
        assert "@sha256:" in from_line

    def test_compose_override_builds_its_own_image(self):
        # agent-mgr runs `docker compose -f <override> build` without changing
        # directory, so the context must be an absolute variable, never `.`;
        # and a build-based agent must carry pull_policy: never so a registry
        # image cannot be pulled over the local build.
        import re

        text = (ROOT / "compose.override.yml").read_text()
        assert re.search(r"build:\s*\{\s*context:\s*\"\$\{AGENT_DIR\}\"", text), (
            "build context must be ${AGENT_DIR}, never a relative path"
        )
        assert "image: ${AGENT_IMAGE}" in text
        assert "pull_policy: never" in text

    def test_agent_env_names_the_built_image(self):
        env = (ROOT / "agent.env").read_text()
        assert "AGENT_IMAGE=the-plow-times-hermes-agent:local" in env, (
            "agent.env must name the built tag agent-mgr inspects for the contract"
        )


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

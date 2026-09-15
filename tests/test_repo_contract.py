"""Repo-level deployment contracts: plow-agents compose.yml, the image, and the leftover agent-mgr hook."""
from __future__ import annotations

import os
import pathlib
import stat

from conftest import ROOT, load_module


class TestSoul:
    def test_soul_md_does_not_trip_hermes_context_injection_scanner(self):
        # Measured live: agent.prompt_builder scans SOUL.md before it ever
        # reaches the model (tools/threat_patterns.py, scope="context") and
        # replaces the WHOLE file with "[BLOCKED: ... prompt injection ...]"
        # on a hit -- not a warning, a silent full-file drop. SOUL.md's own
        # advice to distrust web content ("a page that says 'ignore your
        # previous instructions'...") tripped its own guard's
        # "prompt_injection" pattern, so the agent ran with NONE of its
        # instructions (no pt-intake, no sourcing rule, nothing) while every
        # skill file and this repo's own tests stayed green -- the failure
        # was invisible to anything except the gateway's own runtime log.
        # This mirrors that one pattern (the exact regex that fired), not
        # the full scanner, as a cheap regression guard with no dependency
        # on the hermes_agent package being installed.
        import re

        pattern = re.compile(
            r"ignore\s+(?:\w+\s+){0,8}(previous|all|above|prior)\s+(?:\w+\s+){0,8}instructions",
            re.IGNORECASE,
        )
        text = (ROOT / "runtime" / "SOUL.md").read_text()
        assert not pattern.search(text), (
            "SOUL.md contains a phrase matching Hermes' context-injection "
            "scanner (tools/threat_patterns.py, pattern id 'prompt_injection'); "
            "the whole file gets replaced with a [BLOCKED: ...] placeholder "
            "at runtime, not just this sentence -- reword it, don't just "
            "silence this assertion"
        )

    def test_setup_opener_does_not_ask_timezone(self):
        text = (ROOT / "pt-setup" / "SKILL.md").read_text()
        assert "A que horas quer o jornal da manhã?" in text
        assert "Qual seu fuso" not in text
        assert "convert_delivery.py" in text

    def test_soul_setup_gate_is_a_bare_script_not_python_dash_c(self):
        text = (ROOT / "runtime" / "SOUL.md").read_text()
        assert (
            "/var/lib/hermes/skills/pt-shared/scripts/setup_needed.py "
            "/var/lib/hermes/pt/config.json"
        ) in text
        assert "python3 -c" not in text
        assert "bash -c" not in text
        text = (ROOT / "runtime" / "SOUL.md").read_text()
        assert "not a first-contact script" in text
        assert "pt-setup" in text

    def test_setup_latch_probe_uses_argv_not_command(self):
        # Latch plow_run_command (tools.ts) requires argv and
        # additionalProperties: false. A "command" key never reaches lpstat.
        text = (ROOT / "pt-setup" / "SKILL.md").read_text()
        assert '"command":' not in text
        assert '"argv": ["lpstat", "-p"]' in text
        assert "mcp__plow__plow_run_command" in text

    def test_setup_printer_probe_requests_network_for_cups_ipc(self):
        # Measured live, with a printer genuinely configured and visible
        # in System Settings: lpstat -p still failed ("Bad file
        # descriptor") under the default sandboxed call, because Latch's
        # seatbelt profile denies network*/system-socket whenever
        # `network` is left false — and CUPS talks to cupsd over a local
        # socket, so it can't even reach its own scheduler. `network: true`
        # is the workaround from this side (the scoped fix belongs in
        # Latch's own sandbox profile, not here).
        text = (ROOT / "pt-setup" / "SKILL.md").read_text()
        assert '"network": true' in text
        assert "Bad file descriptor" in text

    def test_setup_warns_against_wrapping_record_setup_in_python(self):
        # Measured live: with a real printer found (network:true worked),
        # the assistant recorded a perfectly valid printer name by
        # wrapping record_setup.py in `python3 - <<'PY' ... PY` for no
        # technical reason -- there was nothing in the value that needed
        # it -- and Hermes correctly flagged it as dangerous script
        # execution, handing the owner a raw /approve prompt instead of
        # an answer. Both files must say plainly that a dotted/underscored
        # *value* never requires any wrapping.
        soul = (ROOT / "runtime" / "SOUL.md").read_text()
        setup = (ROOT / "pt-setup" / "SKILL.md").read_text()
        assert "python3 - <<'PY'" in soul
        assert "wrap this in" in setup
        assert "taken verbatim" in setup

    def test_setup_reads_location_through_the_browser_not_run_command(self):
        # Measured live: /usr/bin/python3 (via xcrun) and a curl fallback
        # both failed under plow_run_command's sandbox -- xcrun's own dylib
        # blocked by the file-read allowlist, then DNS resolution blocked
        # even with network:true. plow_browser_* is a different code path
        # (a real, unsandboxed browser on the owner's Mac) and hits
        # neither restriction.
        setup = (ROOT / "pt-setup" / "SKILL.md").read_text()
        desks = (ROOT / "pt-research" / "references" / "desks.md").read_text()
        for text in (setup, desks):
            assert "plow_browser_open" in text
            assert "plow_browser_close" in text
        assert "xcrun" in desks
        assert "Could not resolve host" in desks
        assert '"/usr/bin/python3"' not in setup

    def test_setup_treats_yes_as_the_default_hour(self):
        soul = (ROOT / "runtime" / "SOUL.md").read_text()
        setup = (ROOT / "pt-setup" / "SKILL.md").read_text()
        assert "send its opener" not in soul
        # SOUL.md delegates to pt-setup's own NEXT_QUESTION-driven steps
        # rather than duplicating the "yes"/07:00 acceptance list itself —
        # two descriptions of the same rule is how they drifted apart
        # before. pt-setup/SKILL.md is the one place that rule lives.
        assert "record_setup.py" in soul and "NEXT_QUESTION" in soul
        assert '"yes"' in setup and '"sim"' in setup
        assert "local_hour=07:00" in setup

    def test_setup_writes_the_draft_only_through_record_setup(self):
        setup = (ROOT / "pt-setup" / "SKILL.md").read_text()
        # The bug this guards: a session once hand-wrote .setup-draft.json
        # with a plain write_file call, then probed the printer and asked
        # about mail in that same reply, without the owner ever seeing the
        # printer question or the probe's answer ever landing in the
        # draft. record_setup.py is the only sanctioned writer now.
        assert "never a hand-edited" in setup
        assert "record_setup.py" in setup
        assert "NEXT_QUESTION" in setup
        for field in ("printer.configured", "mail.configured", "news_asked"):
            assert field in setup

    def test_soul_does_not_gate_the_hour_answer_behind_draft_none(self):
        # The bug this guards: the owner answered "7 is fine" while the
        # draft was still DRAFT:none (nothing had been recorded yet), and
        # SOUL.md's own DRAFT:none branch said "send the opener, stop" --
        # so the assistant re-sent the exact same hour question instead of
        # recording the answer it had just been given. SOUL.md must always
        # hand off to pt-setup (whose own step 1b recognizes an hour
        # answer) rather than deciding straight from DRAFT:none itself.
        soul = (ROOT / "runtime" / "SOUL.md").read_text()
        assert "always load" in soul and "pt-setup" in soul
        assert "never decide" in soul.lower() or "not mean the incoming message" in soul

    def test_setup_distinguishes_a_probe_error_from_no_printer(self):
        # The bug this guards: lpstat -p came back exit_code=1 with
        # "lpstat: Bad file descriptor" -- a probe execution error, not a
        # real "no destinations" report -- and the assistant told the
        # owner "no printer was found" as if the check had actually run
        # cleanly. printer.configured still becomes false either way (never
        # guess true), but the two situations are not the same claim.
        setup = (ROOT / "pt-setup" / "SKILL.md").read_text()
        assert "Bad file descriptor" in setup
        assert "didn't run cleanly" in setup or "isn't a real lpstat report" in setup

    def test_setup_says_probe_outcomes_in_the_owners_language(self):
        # The bug this guards: after the printer probe, the assistant
        # replied in Portuguese even though the entire conversation (every
        # prior owner message) had been in English.
        setup = (ROOT / "pt-setup" / "SKILL.md").read_text()
        assert setup.count("owner's own language") >= 2


class TestUserStub:
    def test_runtime_user_md_forbids_a_profile_interview(self):
        text = (ROOT / "runtime" / "USER.md").read_text()
        assert "not a personal profile" in text.lower()
        assert "pt-setup" in text

    def test_deploy_hook_publishes_user_md(self):
        hook = (ROOT / "deploy-hook").read_text()
        assert "runtime/USER.md" in hook
        assert "memories/USER.md" in hook


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
                     "run_lock.py", "setup_needed.py", "record_setup.py"):
            assert (shared / name).is_file(), f"pt-shared/scripts/{name} missing"

    def test_record_setup_is_executable_and_referenced(self):
        script = ROOT / "pt-shared" / "scripts" / "record_setup.py"
        assert script.stat().st_mode & stat.S_IXUSR, "record_setup.py must be executable"
        setup = (ROOT / "pt-setup" / "SKILL.md").read_text()
        assert (
            "/var/lib/hermes/skills/pt-shared/scripts/record_setup.py"
        ) in setup

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
        assert (ROOT / "pt-setup" / "scripts" / "convert_delivery.py").is_file()


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

    def test_compose_yml_is_the_plow_agents_surface(self):
        # plow-agents' compose.example.yml: service `agent`, credential drop-in,
        # named home volume. compose.override.yml must not exist: Compose loads
        # that filename automatically and would start a second gateway.
        import re

        assert not (ROOT / "compose.override.yml").exists()
        text = (ROOT / "compose.yml").read_text()
        assert re.search(r"^  agent:", text, re.M)
        assert "build: ." in text
        assert "./plow-credentials:/var/lib/plow/credentials.host:ro" in text
        assert "agent-home:/var/lib/hermes" in text
        assert "AGENT_ID: theplowtimes" in text
        assert "TERMINAL_CWD: /var/lib/hermes" in text
        assert "stop_grace_period: 35s" in text
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("-") and "skills" in stripped and "agent-home" not in stripped:
                raise AssertionError(f"skill mount in compose.yml: {stripped}")

    def test_compose_yml_does_not_pin_a_model(self):
        # Measured live: google/gemini-2.5-flash-lite never once called
        # skills_list/skill_view for a news request. Unpinned, provider/model
        # fall back to the Plow-hosted default, the same choice
        # life-assistant-hermes-agent's compose.yml makes by omission.
        text = (ROOT / "compose.yml").read_text()
        assert "HERMES_PROVIDER" not in text
        assert "HERMES_MODEL" not in text

    def test_dockerfile_copies_every_pt_skill_outside_the_home(self):
        import re

        dockerfile = (ROOT / "Dockerfile").read_text()
        skills = sorted(p.parent.name for p in ROOT.glob("pt-*/SKILL.md"))
        missing = [name for name in skills if f"COPY {name}/" not in dockerfile]
        assert missing == [], f"in the tree but never copied into the image: {', '.join(missing)}"
        for name in skills:
            assert re.search(
                rf"^COPY\s+{re.escape(name)}/\s+/opt/hermes/skills/{re.escape(name)}/\s*$",
                dockerfile,
                re.MULTILINE,
            ), f"COPY {name}/ does not land at /opt/hermes/skills/{name}/"
            assert f"/var/lib/hermes/skills/{name}" not in dockerfile
        assert "COPY runtime/SOUL.md /var/lib/hermes/SOUL.md" in dockerfile
        assert "COPY runtime/USER.md /var/lib/hermes/memories/USER.md" in dockerfile
        assert "plow-credentials" in (ROOT / ".dockerignore").read_text()
        assert "plow-credentials" in (ROOT / ".gitignore").read_text()

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
        # Installed into the hermes venv, because that is the `python3` a
        # plain (non-login) command actually resolves to in this container --
        # confirmed live: the container's real PATH puts
        # /opt/hermes/.venv/bin ahead of /usr/bin, so packages placed in the
        # system dist-packages (the previous fix here) are invisible to the
        # skill's own `python3 render_edition.py ...` invocation. `--system`
        # and a system-dist-packages `--target` were both measured and wrong.
        assert "--python /opt/hermes/.venv/bin/python3" in text
        # The probe must run as a plain command, not a login shell (`-lc`
        # resets PATH and would hide a regression back to the system python).
        assert "sh -lc" not in text
        # Pinned by digest, like the fleet pin -- a tag re-resolves on pull.
        from_line = next(
            line for line in text.splitlines() if line.startswith("FROM ")
        )
        assert "@sha256:" in from_line

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

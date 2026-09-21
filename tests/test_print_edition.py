"""print_edition.py -- PDF goes to Latch from disk, never through the model."""
from __future__ import annotations

import base64
import json
import sys

import pytest

from conftest import ROOT, load_module

sys.path.insert(0, str(ROOT / "pt-shared" / "scripts"))
pe = load_module("print_edition", "pt-print/scripts/print_edition.py")


def _config(tmp_path, configured=True, name="HP_LaserJet", language=None):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({
            "owner": {"timezone": "America/Sao_Paulo",
                      **({"language": language} if language else {})},
            "delivery": {"hour": "07:00"},
            "printer": {"configured": configured, "name": name if configured else None},
        }),
        encoding="utf-8",
    )
    return path


def _edition(tmp_path, pdf=b"%PDF-1.4 fake"):
    (tmp_path / "edition.json").write_text(
        json.dumps({"date": "2026-09-17", "sections": []}),
        encoding="utf-8",
    )
    path = tmp_path / "edition.pdf"
    path.write_bytes(pdf)
    return path


def _running_lp_tool(poll_result, calls=None):
    """A fake Latch whose lp outlives its wait and is settled by plow_get_output."""
    def call_tool(name, args):
        if calls is not None:
            calls.append(name)
        if name == "plow_write_file":
            return {"path": "/Users/test-owner/Plow/pt/edition-2026-09-17.pdf.b64"}
        if name == "plow_get_output":
            if isinstance(poll_result, Exception):
                raise poll_result
            return poll_result
        if name == "plow_run_applescript":
            return {"exit_code": 0, "output": "request id is HP-2"}
        if args["argv"][0] == "lp":
            return {"status": "running", "handle": "job-1"}
        return {"exit_code": 0, "output": ""}
    return call_tool


class TestPrinterGate:
    def test_missing_config_is_a_skip_not_a_crash(self, tmp_path):
        assert pe.printer_name(str(tmp_path / "nope.json")) is None

    def test_unconfigured_printer_skips(self, tmp_path):
        assert pe.printer_name(str(_config(tmp_path, configured=False))) is None

    def test_configured_without_name_skips(self, tmp_path):
        assert pe.printer_name(str(_config(tmp_path, configured=True, name=""))) is None

    def test_configured_returns_exact_cups_name(self, tmp_path):
        assert pe.printer_name(str(_config(tmp_path, name="HP_LaserJet_4"))) == "HP_LaserJet_4"

    @pytest.mark.parametrize("language, expected", [
        (None, "paper is unavailable on this install"),
        ("en", "paper is unavailable on this install"),
        ("pt-BR", "papel não está disponível nesta instalação"),
        ("Português", "papel não está disponível nesta instalação"),
    ])
    def test_no_latch_credential_says_paper_is_unavailable_in_the_owners_language(
        self, tmp_path, monkeypatch, language, expected
    ):
        # A hosted install never performs the static-credential setup step, so
        # printing can never work there. The owner's line has to say that
        # instead of promising a retry -- post_to_chat.py keys the retry
        # promise off this wording (TERMINAL_FAILURES, both spellings) -- and
        # SOUL.md requires it in the language the owner writes in.
        for name in ("DOMO_DEVICE_UID", "DOMO_MCP_TOKEN"):
            monkeypatch.delenv(name, raising=False)
        pdf = _edition(tmp_path)
        config = _config(tmp_path, language=language)

        with pytest.raises(SystemExit) as exit_info:
            pe.main([str(pdf), str(config)])

        message = str(exit_info.value)
        assert "page not printed" in message
        assert "DOMO_DEVICE_UID" in message
        assert expected in message

    @pytest.mark.parametrize("credential", [True, False])
    def test_dry_run_previews_without_touching_the_credential(
        self, tmp_path, monkeypatch, capsys, credential
    ):
        # --dry-run opens no Latch session, so it must not require one: it
        # previews the commands either way. The gate belongs on the last line
        # before a session is opened, not in front of a preview.
        for name in ("DOMO_DEVICE_UID", "DOMO_MCP_TOKEN"):
            monkeypatch.delenv(name, raising=False)
        if credential:
            monkeypatch.setenv("DOMO_DEVICE_UID", "device")
            monkeypatch.setenv("DOMO_MCP_TOKEN", "token")
        pdf = _edition(tmp_path)
        config = _config(tmp_path)

        pe.main([str(pdf), str(config), "--dry-run"])

        out = capsys.readouterr().out
        assert "dry-run: would write" in out
        assert "paper is unavailable" not in out


class TestPdfAndDate:
    def test_missing_pdf_is_refused_by_name(self, tmp_path):
        (tmp_path / "edition.json").write_text(
            json.dumps({"date": "2026-09-17"}), encoding="utf-8"
        )
        with pytest.raises(SystemExit, match="pdf"):
            pe.read_pdf(str(tmp_path / "edition.pdf"))

    def test_date_comes_from_sibling_edition_json(self, tmp_path):
        pdf = _edition(tmp_path)
        assert pe.edition_date(str(pdf)) == "2026-09-17"

    def test_mac_path_is_pdf_under_plow_pt(self):
        assert pe.mac_pdf_path("2026-09-17") == "~/Plow/pt/edition-2026-09-17.pdf"
        assert pe.mac_b64_path("2026-09-17") == "~/Plow/pt/edition-2026-09-17.pdf.b64"


class TestSettleAndParse:
    def test_written_path_from_result(self):
        assert pe.written_path(
            {"path": "/Users/test-owner/Plow/pt/edition-2026-09-17.pdf.b64"}
        ) == "/Users/test-owner/Plow/pt/edition-2026-09-17.pdf.b64"

    def test_lp_nonzero_is_a_failed_print(self):
        with pytest.raises(SystemExit, match="lp"):
            pe.require_exit_zero(None, {"exit_code": 1, "output": "Unsupported document-format"}, "lp")

    def test_lp_zero_passes(self):
        pe.require_exit_zero(None, {"exit_code": 0, "output": "request id is HP-1"}, "lp")


class TestShip:
    @pytest.fixture(autouse=True)
    def _no_sleep(self, monkeypatch):
        monkeypatch.setattr("latch_mcp.time.sleep", lambda _s: None)

    def test_writes_pdf_via_base64_then_lp_with_network_for_cups(self, tmp_path):
        # Measured live 2026-09-17: JornalVirtual rejected HTML
        # (`lp: Unsupported document-format "text/html"`). The chat leg
        # already has edition.pdf from weasyprint; paper must ship that.
        pdf = _edition(tmp_path, pdf=b"%PDF-1.4 PAGE")
        calls = []

        def call_tool(name, arguments):
            calls.append((name, arguments))
            if name == "plow_write_file":
                return {"path": "/Users/test-owner/Plow/pt/edition-2026-09-17.pdf.b64"}
            if name == "plow_run_command":
                if arguments["argv"][0] == "base64":
                    return {"exit_code": 0, "output": ""}
                return {"exit_code": 0, "output": "request id is HP-1"}
            raise AssertionError(name)

        pe.ship(
            str(pdf),
            "JornalVirtual",
            "2026-09-17",
            call_tool,
        )
        write_name, write_args = calls[0]
        assert write_name == "plow_write_file"
        assert write_args["path"] == "~/Plow/pt/edition-2026-09-17.pdf.b64"
        assert write_args["content"] == base64.b64encode(b"%PDF-1.4 PAGE").decode("ascii")
        decode_name, decode_args = calls[1]
        assert decode_name == "plow_run_command"
        assert decode_args["argv"] == [
            "base64", "-D", "-i",
            "/Users/test-owner/Plow/pt/edition-2026-09-17.pdf.b64",
            "-o", "/Users/test-owner/Plow/pt/edition-2026-09-17.pdf",
        ]
        lp_name, lp_args = calls[2]
        assert lp_name == "plow_run_command"
        assert lp_args["argv"] == [
            "lp", "-d", "JornalVirtual",
            "/Users/test-owner/Plow/pt/edition-2026-09-17.pdf",
        ]
        assert lp_args["network"] is True

    @pytest.mark.parametrize("running_step", ["base64", "lp"])
    def test_running_command_is_not_a_printed_page(self, tmp_path, running_step):
        pdf = _edition(tmp_path)

        def call_tool(name, arguments):
            if name == "plow_write_file":
                return {"path": "/Users/test-owner/Plow/pt/edition-2026-09-17.pdf.b64"}
            if name == "plow_get_output":
                return {"status": "running", "handle": "job-1"}
            if arguments["argv"][0] == running_step:
                return {"status": "running", "handle": "job-1"}
            return {"exit_code": 0, "output": ""}

        with pytest.raises(pe.LatchError, match=f"{running_step} outcome unknown"):
            pe.ship(str(pdf), "JornalVirtual", "2026-09-17", call_tool)

    def test_running_lp_is_polled_to_its_exit(self, tmp_path):
        calls = []
        done = {"status": "completed", "exit_code": 0, "output": "request id is HP-1"}
        pe.ship(str(_edition(tmp_path)), "JornalVirtual", "2026-09-17",
                _running_lp_tool(done, calls))
        assert calls.count("plow_get_output") == 1

    def test_running_lp_that_ends_in_bad_file_descriptor_still_retries(self, tmp_path):
        calls = []
        bfd = {"status": "completed", "exit_code": 1, "output": "lp: Bad file descriptor"}
        pe.ship(str(_edition(tmp_path)), "JornalVirtual", "2026-09-17",
                _running_lp_tool(bfd, calls))
        assert "plow_run_applescript" in calls

    def test_polling_failure_or_block_is_an_unknown_outcome_with_the_action(self, tmp_path):
        blocked = pe.LatchError("latch blocked: Click Allow on the Mac")
        with pytest.raises(pe.LatchError, match="lp outcome unknown: latch blocked: Click Allow"):
            pe.ship(str(_edition(tmp_path)), "JornalVirtual", "2026-09-17",
                    _running_lp_tool(blocked))

    def test_lp_bad_file_descriptor_retries_via_applescript(self, tmp_path):
        pdf = _edition(tmp_path)
        tools = []

        def call_tool(name, arguments):
            tools.append(name)
            if name == "plow_write_file":
                return {"path": "/Users/test-owner/Plow/pt/edition-2026-09-17.pdf.b64"}
            if name == "plow_run_command":
                if arguments["argv"][0] == "base64":
                    return {"exit_code": 0, "output": ""}
                return {"exit_code": 1, "output": "lp: Bad file descriptor"}
            if name == "plow_run_applescript":
                return {"exit_code": 0, "output": "request id is HP-1"}
            raise AssertionError(name)

        pe.ship(
            str(pdf),
            "JornalVirtual",
            "2026-09-17",
            call_tool,
        )
        assert tools == [
            "plow_write_file",
            "plow_run_command",
            "plow_run_command",
            "plow_run_applescript",
        ]

"""post_to_chat.py -- PDF-only payload vs text fallback."""
from __future__ import annotations

import json
import types
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from conftest import ROOT, load_module

sys.path.insert(0, str(ROOT / "pt-shared" / "scripts"))
post = load_module("post_to_chat", "pt-shared/scripts/post_to_chat.py")


class TestComposePayload:
    @pytest.mark.parametrize("text", ["Mail summary", ""])
    def test_pdf_body_carries_the_optional_companion(self, text):
        assert post.compose_payload(text, "att_1") == {
            "body": text, "attachment_uids": ["att_1"],
        }

    def test_attachment_filename_defaults_to_basename(self):
        assert post.attachment_filename("/var/lib/hermes/pt/run/edition.pdf") == (
            "edition.pdf"
        )

    def test_attachment_filename_override_is_a_paper_name_not_a_path(self):
        # Measured live: the chat showed the attachment as "edition.pdf"
        # because declare used the run-dir basename. The owner asked for
        # the newspaper, not a working-file name.
        assert (
            post.attachment_filename(
                "/var/lib/hermes/pt/run/edition.pdf",
                "The-Founder-Times-2026-09-17.pdf",
            )
            == "The-Founder-Times-2026-09-17.pdf"
        )
        with pytest.raises(SystemExit, match="filename"):
            post.attachment_filename("edition.pdf", "../secret.pdf")

    def test_text_only_when_no_pdf(self):
        payload = post.compose_payload("THE FOUNDER TIMES")
        assert payload == {"body": "THE FOUNDER TIMES"}

    def test_text_only_refuses_blank_stdin(self):
        with pytest.raises(SystemExit, match="no edition text"):
            post.compose_payload("")

    def test_successful_post_stamps_a_session_seal(self, tmp_path):
        stamp = tmp_path / "seal-session.json"
        post.after_posted(stamp)
        assert json.loads(stamp.read_text(encoding="utf-8"))["pending"] is True
        assert json.loads(stamp.read_text(encoding="utf-8"))["delivered"] is True

    def test_after_posted_reopens_delivered_sections(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PT_HOME", str(tmp_path / "pt"))
        intake = load_module("topics_reopen", "pt-intake/scripts/topics.py")
        intake.main(["add", "--text", "AI", "--kind", "section", "--depth", "quick"])
        tid = json.loads((tmp_path / "pt" / "topics.json").read_text())["topics"][0]["id"]
        intake.main(["add", "--text", "F1", "--kind", "section", "--depth", "quick"])
        other = json.loads((tmp_path / "pt" / "topics.json").read_text())["topics"][1]["id"]
        intake.main(["mark", tid, "--status", "running"])
        intake.main(["mark", other, "--status", "running"])  # another paper's, still researching
        edition = tmp_path / "edition.json"
        edition.write_text(json.dumps({"sections": [{"topic_id": tid}]}), encoding="utf-8")
        post.after_posted(tmp_path / "seal.json", str(tmp_path / "edition.pdf"))
        by_id = {t["id"]: t for t in json.loads((tmp_path / "pt" / "topics.json").read_text())["topics"]}
        assert by_id[tid]["status"] == "pending" and by_id[tid]["last_edition_at"]
        assert by_id[other]["status"] == "running" and by_id[other]["last_edition_at"] is None


class TestRunPrintEdition:
    def test_unknown_outcome_line_is_kept_not_rewrapped_as_a_failure(self, monkeypatch):
        line = "error: page may not have printed — lp outcome unknown: Click Allow; check the printer queue"
        monkeypatch.setattr("subprocess.run", lambda *a, **k: types.SimpleNamespace(
            returncode=1, stdout="", stderr=line))
        assert post.run_print_edition("/x.pdf", "/c.json") == line


class TestTextFileFlag:
    """`--text-file` exists so the text leg needs no shell redirect.

    Measured live: told to "pass the chat text on stdin" with no command
    shown, a run built `/bin/sh -c '... post_to_chat.py < .../edition.chat.txt'`
    -- a shell operator, which is exactly what SOUL.md's gate flags. The owner
    got an /approve prompt instead of their newspaper.
    """

    def test_reads_the_edition_text_from_a_file(self, tmp_path):
        f = tmp_path / "edition.chat.txt"
        f.write_text("THE FOUNDER TIMES\nfront page\n", encoding="utf-8")
        assert post.read_text_file(str(f)) == "THE FOUNDER TIMES\nfront page"

    def test_missing_file_is_refused_by_name(self, tmp_path):
        with pytest.raises(SystemExit, match="text-file"):
            post.read_text_file(str(tmp_path / "nope.txt"))

    def test_blank_file_is_refused(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("   \n", encoding="utf-8")
        with pytest.raises(SystemExit, match="empty"):
            post.read_text_file(str(f))


class TestMaybePrint:
    """Measured live 2026-09-18: PDF posted, edition.html existed,
    printer.configured true (JornalVirtual), and print_edition.py was
    never invoked — the model marked topics and NO_REPLY'd. Chat is
    not a gate for paper; post_to_chat.py is.
    """

    def test_configured_printer_prints_the_pdf_with_no_html_beside_it(self, tmp_path):
        # Measured live 2026-09-18: runs that rendered only the PDF logged
        # "skipped: no html" -- a gate on a file the print never reads.
        pdf = tmp_path / "edition.pdf"
        pdf.write_bytes(b"%PDF")
        cfg = tmp_path / "config.json"
        cfg.write_text(
            json.dumps({"printer": {"configured": True, "name": "JornalVirtual"}}),
            encoding="utf-8",
        )
        seen = []

        def runner(pdf_path, config_path):
            seen.append((pdf_path, config_path))
            return "page printed on JornalVirtual"

        out = post.maybe_print(str(pdf), str(cfg), runner=runner)
        assert seen == [(str(pdf.resolve()), str(cfg))]
        assert "page printed" in out

    @pytest.mark.parametrize("result, line", [
        ("page printed on JornalVirtual", None),
        ("skipped: printer.configured is not true", None),
        ("error: page not printed — lp 1: no such printer\nmore detail",
         "page not printed — lp 1: no such printer; next scheduled run retries"),
        ("warning: something first\nerror: page not printed — latch denied",
         "page not printed — latch denied; next scheduled run retries"),
        ("error: page not printed — lp outcome unknown: still running",
         "page not printed — lp outcome unknown: still running"),
        ("error: page not printed — Mac unreachable",
         "page not printed — Mac unreachable; next scheduled run retries"),
    ])
    def test_only_a_failed_print_owes_the_owner_a_chat_line(self, result, line):
        assert post.print_failure_line(result) == line


class TestMaybeRecord:
    """post_to_chat.py records the edition itself now, the same way it prints."""

    def test_a_successful_post_invokes_the_recorder_with_the_sibling_edition_json(self, tmp_path):
        pdf = tmp_path / "edition.pdf"
        pdf.write_bytes(b"%PDF")
        seen = []

        def runner(edition_json):
            seen.append(edition_json)
            return "RECORDED projects/theplowtimes/editions/2026-09-19.md"

        out = post.maybe_record(str(pdf), runner=runner)
        assert seen == [str(tmp_path / "edition.json")]
        assert "RECORDED" in out

    def test_a_hung_recorder_times_out_instead_of_blocking_the_run(self, monkeypatch):
        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="record_edition.py", timeout=kwargs.get("timeout"))

        monkeypatch.setattr(subprocess, "run", fake_run)
        out = post.run_record_edition("run/1/edition.json")
        assert out == f"edition not recorded — timed out after {post.RECORD_TIMEOUT}s"


def _seal_ok(*_):
    return "sealed"


def _seal_fails(*_):
    raise RuntimeError("disk full")


class TestFinalizersRunIndependently:
    """The paper comes before the archive, and no finalizer's failure blocks
    another's: seal, print and record each run best-effort, in order."""

    def _mock_main(self, tmp_path, monkeypatch, pdf_arg=None, **overrides):
        pdf = tmp_path / "edition.pdf"
        pdf.write_bytes(b"%PDF")
        monkeypatch.setattr(post, "resolve_chat", lambda: ("https://api.example", "cht_1", "tok"))
        monkeypatch.setattr(post, "read_message", lambda: "")
        monkeypatch.setattr(post, "declare_and_upload", lambda *a, **k: "att_1")
        monkeypatch.setattr(post, "post_json", lambda *a, **k: None)
        monkeypatch.setattr(post, "after_posted", overrides.get("after_posted", lambda *_: "sealed"))
        if "maybe_print" in overrides:
            monkeypatch.setattr(post, "maybe_print", overrides["maybe_print"])
        if "maybe_record" in overrides:
            monkeypatch.setattr(post, "maybe_record", overrides["maybe_record"])
        monkeypatch.setattr(sys, "argv", ["post_to_chat.py", "--pdf", pdf_arg or str(pdf)])

    @pytest.mark.parametrize("seal, print_result", [
        (_seal_ok, "page printed"),  # the happy path: prints before it records
        (_seal_fails, "page printed"),  # a seal failure
        (_seal_ok, "page not printed — lp 1"),  # a print failure
    ])
    def test_a_failing_finalizer_never_blocks_the_next_one(self, tmp_path, monkeypatch, seal, print_result):
        order = []
        self._mock_main(
            tmp_path, monkeypatch, after_posted=seal,
            maybe_print=lambda *a, **k: order.append("print") or print_result,
            maybe_record=lambda *a, **k: order.append("record") or "RECORDED",
        )
        post.main()
        assert order == ["print", "record"]

    def test_a_print_failure_before_its_own_runner_still_records(self, tmp_path, monkeypatch):
        # maybe_print itself is real here (not mocked): an unresolvable pdf
        # path makes Path.resolve() raise inside maybe_print, before its
        # runner is ever reached. main()'s own _best_effort around the call
        # -- not one inside maybe_print -- is what has to catch this.
        order = []
        self._mock_main(
            tmp_path, monkeypatch, pdf_arg="bad\x00path",
            maybe_record=lambda *a, **k: order.append("record") or "RECORDED",
        )
        post.main()
        assert order == ["record"]


class TestHoldUntil:
    """Scheduled papers start early; chat must wait for delivery.hour.

    Measured live: lead_minutes alone started research at hour−lead, then
    post_to_chat sent the PDF the moment the recipe finished — not at the
    hour the owner named. --hold-until is the send clock. If that hour has
    already passed, send now; never sleep until tomorrow.
    """

    @pytest.mark.parametrize("tz, now, hour, expected", [
        ("America/Sao_Paulo", datetime(2026, 9, 20, 6, 20), "07:00", 40 * 60),
        # 2026-11-01 01:30 in New York is EDT and 02:00 is EST, so the wall
        # clock spans 30 minutes but the hold is 2.5 real hours.
        ("America/New_York", datetime(2026, 11, 1, 1, 30), "03:00", 2.5 * 3600),
        ("UTC", datetime(2026, 9, 20, 7, 1), "07:00", 0),  # past: now, never tomorrow
    ])
    def test_seconds_until_hour(self, monkeypatch, tz, now, hour, expected):
        monkeypatch.setenv("TZ", tz)
        assert post.seconds_until_hhmm(hour, now=now.replace(tzinfo=ZoneInfo(tz))) == expected

    @pytest.mark.parametrize("now, expected", [
        (datetime(2026, 9, 20, 6, 59, 30), [30]),
        (datetime(2026, 9, 20, 8, 0, 0), []),  # already due: no sleep
    ])
    def test_hold_sleeps_only_the_remaining_seconds(self, monkeypatch, now, expected):
        monkeypatch.setenv("TZ", "UTC")
        slept = []
        post.hold_until("07:00", sleep=slept.append, now=now.replace(tzinfo=ZoneInfo("UTC")))
        assert slept == expected

    def test_bad_clock_is_refused(self):
        with pytest.raises(SystemExit, match="hold-until"):
            post.seconds_until_hhmm("7:00")

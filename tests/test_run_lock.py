"""run_lock.py -- one owner per run name, with stale takeover."""
from __future__ import annotations

import contextlib
import io
from datetime import datetime, timedelta, timezone

import pytest

from conftest import load_module

lock = load_module("run_lock", "pt-shared/scripts/run_lock.py")


@pytest.fixture
def pt_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_HOME", str(tmp_path / "pt"))
    return tmp_path / "pt"


def out(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = lock.main(argv)
    return code, buf.getvalue().strip()


def test_first_acquire_wins(pt_home):
    code, text = out(["acquire", "--name", "daily-2026-09-11"])
    assert code == 0 and text == "acquired"
    assert (pt_home / "run" / "daily-2026-09-11.lock").is_file()


def test_second_acquire_is_held(pt_home):
    out(["acquire", "--name", "daily-2026-09-11"])
    code, text = out(["acquire", "--name", "daily-2026-09-11"])
    assert code == 0 and text == "held"


def test_stale_lock_is_taken_over(pt_home):
    out(["acquire", "--name", "daily-2026-09-11"])
    lock_path = pt_home / "run" / "daily-2026-09-11.lock"
    old = (datetime.now(timezone.utc).astimezone() - timedelta(minutes=500))
    lock_path.write_text(old.isoformat(timespec="seconds") + "\n")
    code, text = out(["acquire", "--name", "daily-2026-09-11"])
    assert code == 0 and text == "stale-takeover"


def test_unparseable_lock_is_taken_over(pt_home):
    lock_path = pt_home / "run" / "daily-2026-09-11.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("garbage")
    _, text = out(["acquire", "--name", "daily-2026-09-11"])
    assert text == "stale-takeover"


def test_release_then_acquire(pt_home):
    out(["acquire", "--name", "daily-2026-09-11"])
    assert out(["release", "--name", "daily-2026-09-11"]) == (0, "released")
    assert out(["acquire", "--name", "daily-2026-09-11"]) == (0, "acquired")


def test_release_missing_is_not_an_error(pt_home):
    assert out(["release", "--name", "daily-2026-09-11"]) == (0, "nothing-to-release")


def test_names_with_path_characters_refused(pt_home):
    with pytest.raises(SystemExit, match="not allowed"):
        lock.main(["acquire", "--name", "../escape"])


class TestWaitSeconds:
    """issue #30: a scheduled run must not skip the day on a passing overlap
    with an on-demand copy that won the lock a moment earlier. wait_seconds=0
    is already covered by test_second_acquire_is_held above."""

    def test_waits_then_acquires_once_the_holder_releases(self, pt_home, monkeypatch):
        lock_path = pt_home / "run" / "daily-2026-09-11.lock"
        lock_path.parent.mkdir(parents=True)
        lock_path.write_text(lock.now().isoformat(timespec="seconds") + "\n")
        calls = []

        def fake_sleep(seconds):
            calls.append(seconds)
            if len(calls) == 2:
                lock_path.unlink()

        monkeypatch.setattr(lock.time, "sleep", fake_sleep)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = lock.acquire("daily-2026-09-11", 120, wait_seconds=5)
        assert code == 0 and buf.getvalue().strip() == "acquired"
        assert calls == [1, 1]

    def test_gives_up_as_held_once_the_wait_budget_runs_out(self, pt_home, monkeypatch):
        lock_path = pt_home / "run" / "daily-2026-09-11.lock"
        lock_path.parent.mkdir(parents=True)
        lock_path.write_text(lock.now().isoformat(timespec="seconds") + "\n")
        calls = []

        monkeypatch.setattr(lock.time, "sleep", calls.append)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = lock.acquire("daily-2026-09-11", 120, wait_seconds=3)
        assert code == 0 and buf.getvalue().strip() == "held"
        assert calls == [1, 1, 1]

    def test_a_lock_that_goes_stale_mid_wait_is_taken_over_without_using_the_full_budget(self, pt_home, monkeypatch):
        # Each fake second pushes the lock's own timestamp further into the
        # past, standing in for real time passing while this waits.
        lock_path = pt_home / "run" / "daily-2026-09-11.lock"
        lock_path.parent.mkdir(parents=True)
        lock_path.write_text((lock.now() - timedelta(minutes=119)).isoformat(timespec="seconds") + "\n")
        calls = []

        def fake_sleep(seconds):
            calls.append(seconds)
            lock_path.write_text(
                (lock.now() - timedelta(minutes=119, seconds=len(calls) * 10)).isoformat(timespec="seconds")
                + "\n"
            )

        monkeypatch.setattr(lock.time, "sleep", fake_sleep)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = lock.acquire("daily-2026-09-11", 120, wait_seconds=60)
        assert code == 0 and buf.getvalue().strip() == "stale-takeover"
        assert len(calls) < 60

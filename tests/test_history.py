"""history.py: what the advisor's desk printed lately, read back from the wiki."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from conftest import load_module
from wiki import EDITIONS, Wiki, join_page

history = load_module("history", "pt-priority/scripts/history.py")
TODAY = date(2026, 9, 19)


def day_page(mac, day, card=None):
    path = mac.home / "Plow" / "wiki" / EDITIONS / f"{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"type": "Edition", "date": day, **({"priority": card} if card else {})}
    path.write_text(join_page(meta, f"# The Founder Times, {day}\n"))


class TestRecent:
    def test_the_last_weeks_cards_oldest_first_without_the_empty_days(self, mac):
        day_page(mac, "2026-09-12", {"headline": "too old"})
        day_page(mac, "2026-09-13", {"headline": "Call Raj"})
        day_page(mac, "2026-09-15")  # an edition without the desk
        day_page(mac, "2026-09-19", {"headline": "Close the pilot"})
        assert history.recent(Wiki(mac.call_tool), TODAY) == [
            {"date": "2026-09-13", "desk": {"headline": "Call Raj"}},
            {"date": "2026-09-19", "desk": {"headline": "Close the pilot"}},
        ]

    def test_no_pages_is_no_history(self, mac):
        assert history.recent(Wiki(mac.call_tool), TODAY) == []


class TestOwnerToday:
    def test_the_owners_zone_can_land_a_day_off_the_containers(self, tmp_path, monkeypatch):
        # 23:30 UTC: the container (UTC) is still on the 19th; the owner in
        # Kiritimati (UTC+14) is already on the 20th.
        instant = datetime(2026, 9, 19, 23, 30, tzinfo=timezone.utc)

        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return instant.astimezone(tz) if tz else instant

        monkeypatch.setattr(history, "datetime", FixedDatetime)
        monkeypatch.setenv("PT_HOME", str(tmp_path))
        (tmp_path / "config.json").write_text(
            json.dumps({"owner": {"timezone": "Pacific/Kiritimati"}}))
        assert instant.date() == date(2026, 9, 19)  # the container's own day
        assert history.owner_today() == date(2026, 9, 20)


class TestCli:
    def test_an_unreachable_mac_is_an_error(self, mac, monkeypatch):
        mac.asleep = True
        monkeypatch.setattr(history, "connect", lambda: Wiki(mac.call_tool))
        with pytest.raises(SystemExit) as exc:
            history.main(["recent"])
        assert str(exc.value).startswith("error: history unavailable — Mac unreachable")

    def test_an_unknown_timezone_name_refuses_instead_of_guessing(self, mac, monkeypatch, tmp_path):
        monkeypatch.setattr(history, "connect", lambda: Wiki(mac.call_tool))
        monkeypatch.setenv("PT_HOME", str(tmp_path))
        (tmp_path / "config.json").write_text(
            json.dumps({"owner": {"timezone": "Not/AZone"}}))
        with pytest.raises(SystemExit) as exc:
            history.main(["recent"])
        assert str(exc.value).startswith("error: history unavailable — ")

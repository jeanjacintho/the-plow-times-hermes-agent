"""record_edition.py: a delivered edition becomes the day's page in the owner's wiki."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import load_module
from wiki import EDITIONS, OVERVIEW, Wiki, split_page

rec = load_module("record_edition", "pt-edition/scripts/record_edition.py")
SP = timezone(timedelta(hours=-3))
MORNING = datetime(2026, 9, 19, 6, 4, tzinfo=SP)
AFTERNOON = datetime(2026, 9, 19, 14, 0, tzinfo=SP)
CARD = {"stage_label": "Discovery ($0–1M ARR)", "stage_why": "$4K MRR as of Sep 10",
        "first_step": "Send Raj the pilot terms", "who": ["Raj — replied to the launch post"],
        "draft": "Raj, here are the terms.", "not_today": ["Hiring a VP Sales"],
        "why": [{"text": "A pilot is the proof", "quote": "Proof beats promises.",
                 "source_label": "The Blueprint", "url": "https://example.com/blueprint"}],
        "today": [{"time": "10:00", "title": "Dentist", "note": "private"}]}


@pytest.fixture(autouse=True)
def pt_home(monkeypatch, tmp_path):
    """record()'s cross-run lock file lives under PT_HOME; keep it in tmp_path."""
    monkeypatch.setenv("PT_HOME", str(tmp_path / "pt"))


def edition(tmp_path, headline="Close the Acme pilot", card=True, news=True):
    sections = [
        {"kind": "section", "desk": "weather", "title": "Weather", "headline": "Rain",
         "body": "Rain in Sao Paulo.", "sources": ["https://weather.example"]},
        {"kind": "section", "desk": "mail", "title": "Letters", "headline": "Three messages",
         "body": "Ana Costa — partnership proposal.", "sources": ["Gmail"]},
    ]
    if card:
        sections.append({"kind": "section", "desk": "priority", "headline": headline, "priority": CARD})
    if news:
        sections.append({"kind": "section", "topic_id": "t_9f2a", "desk": "news", "title": "The dollar",
                         "headline": "The real firms", "body": "The real rose 1%.",
                         "sources": ["https://news.example/fx"]})
        notes = tmp_path / "run" / "t_9f2a"
        notes.mkdir(parents=True, exist_ok=True)
        (notes / "notes.json").write_text(json.dumps({
            "topic_id": "t_9f2a",
            "notes": [{"claim": "BRL up 1% on Sep 18", "url": "https://news.example/fx", "quote": "…"}],
            "could_not_source": ["the central bank's comment"]}))
    run_dir = tmp_path / "run" / "daily-2026-09-19"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "edition.json"
    path.write_text(json.dumps({"date": "2026-09-19", "location": "Sao Paulo", "sections": sections}))
    return path


def day(mac):
    return (mac.home / "Plow" / "wiki" / EDITIONS / "2026-09-19.md").read_text()


class TestRecord:
    def test_the_day_page_keeps_the_card_and_the_research_and_is_listed(self, mac, tmp_path):
        out = rec.record(Wiki(mac.call_tool), edition(tmp_path), "cht_1", MORNING)
        assert out == f"RECORDED {EDITIONS}/2026-09-19.md"
        meta, body = split_page(day(mac))
        assert meta["priority"]["first_step"] == "Send Raj the pilot terms"
        assert {"resource": "https://news.example/fx"} in meta["sources"]
        assert "BRL up 1% on Sep 18 (https://news.example/fx)" in body
        assert "Could not source: the central bank's comment" in body
        assert "editions/2026-09-19.md" in (mac.home / "Plow" / "wiki" / OVERVIEW).read_text()

    def test_the_owners_own_accounts_stay_off_the_wiki(self, mac, tmp_path):
        rec.record(Wiki(mac.call_tool), edition(tmp_path), "cht_1", MORNING)
        assert "Rain in Sao Paulo" not in day(mac) and "Ana Costa" not in day(mac)
        assert "Dentist" not in day(mac)

    def test_a_mail_section_claiming_a_topic_id_is_not_recorded_as_news(self, mac, tmp_path):
        sections = [
            {"kind": "section", "desk": "mail", "topic_id": "t_1234", "title": "Letters",
             "headline": "Three messages", "body": "Ana Costa — partnership proposal.",
             "sources": ["Gmail"]},
            {"kind": "section", "desk": "priority", "headline": "Close the Acme pilot", "priority": CARD},
        ]
        run_dir = tmp_path / "run" / "daily-2026-09-19"
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "edition.json"
        path.write_text(json.dumps({"date": "2026-09-19", "location": "Sao Paulo", "sections": sections}))
        rec.record(Wiki(mac.call_tool), path, "cht_1", MORNING)
        assert "Ana Costa" not in day(mac)

    def test_a_later_edition_appends_and_its_card_is_the_days(self, mac, tmp_path):
        w = Wiki(mac.call_tool)
        rec.record(w, edition(tmp_path), "cht_1", MORNING)
        rec.record(w, edition(tmp_path, headline="Book the Acme demo"), "cht_1", AFTERNOON)
        meta, body = split_page(day(mac))
        assert "## 06:04 edition" in body and "## 14:00 edition" in body
        assert meta["priority"]["headline"] == "Book the Acme demo"

    def test_the_same_edition_twice_is_recorded_once(self, mac, tmp_path):
        w, path = Wiki(mac.call_tool), edition(tmp_path)
        rec.record(w, path, "cht_1", MORNING)
        before = day(mac)
        assert rec.record(w, path, "cht_1", MORNING).startswith("SKIPPED:")
        assert day(mac) == before

    def test_an_edition_of_standing_desks_only_leaves_no_page(self, mac, tmp_path):
        out = rec.record(Wiki(mac.call_tool), edition(tmp_path, card=False, news=False), "cht_1", MORNING)
        assert out.startswith("SKIPPED:")
        assert not (mac.home / "Plow" / "wiki" / EDITIONS).exists()


class TestCli:
    def test_an_unreachable_mac_fails_loudly(self, mac, monkeypatch, tmp_path):
        path = edition(tmp_path)
        mac.asleep = True
        monkeypatch.setattr(rec, "connect", lambda: Wiki(mac.call_tool))
        monkeypatch.setenv("PLOW_HOME_CHANNEL", "cht_1")
        with pytest.raises(SystemExit) as exc:
            rec.main([str(path)])
        assert str(exc.value).startswith("error: edition not recorded — Mac unreachable")

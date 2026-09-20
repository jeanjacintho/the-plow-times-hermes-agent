"""render_edition.py -- the fixed layout, the escape discipline, the gate."""
from __future__ import annotations

import json

import pytest

from conftest import ROOT, load_module

render = load_module("render_edition", "pt-edition/scripts/render_edition.py")
RECOMMENDATION = {
    "headline": "Put retention at the center of Monday's investor conversation",
    "body": "Lead with the segment that returns, what those users repeatedly ask the product to do, and the milestone this round buys.",
    "evidence": [
        {"claim": "Returning users repeat the same workflow", "source": "Weekly retention note", "url": "https://example.com/retention"},
    ],
    "first_step": "Draft the three-slide spine: retention, repeated use, and the runway milestone.",
    "advisor": {"name": "Patrick Salyer", "quote": "Forget the naming (seed / A / B).", "url": "https://example.com/advisor"},
}


def recommendations():
    return [
        {**RECOMMENDATION, "headline": f"{RECOMMENDATION['headline']} — {rank}"}
        for rank in range(1, 4)
    ]
def edition_with_priority_and_weather():
    return edition(sections=[
        {"kind": "section", "title": "Weather", "desk": "weather", "body": "rain", "sources": []},
        {"kind": "section", "title": "Your #1 priority today", "desk": "priority",
         "headline": "Close the seed extension", "body": "Send the deck",
         "priority": {"recommendations": recommendations(), "questions": []},
         "sources": []},
    ])


EVENT = {"time": "10:00", "title": "Customer call: Dana", "note": "Go in with: what they use today"}


def priority_edition(headline="Book 3 customer calls by Friday", sources=(), **fields):
    recommendation = {**RECOMMENDATION, "headline": headline}
    p = {"recommendations": [{**recommendation, "headline": f"{headline} — {rank}"} for rank in range(1, 4)],
         "questions": fields.pop("questions", []), **fields}
    return edition(sections=[{"kind": "section", "title": "P", "desk": "priority",
                              "headline": headline, "body": "b", "priority": p,
                              "sources": list(sources)}])


def recommendation_edition(recommendations=None, questions=None):
    priority = {"recommendations": recommendations if recommendations is not None else globals()["recommendations"](),
                "questions": questions or []}
    return edition(sections=[{"kind": "section", "title": "Advisor", "desk": "priority",
                              "body": "Today's recommendations.", "priority": priority,
                              "sources": []}])


def edition(**overrides):
    base = {
        "date": "2026-09-11",
        "sections": [
            {
                "kind": "section",
                "topic_id": "t_8c1d",
                "title": "Weather in Sao Paulo",
                "body": "Rain in the afternoon.",
                "sources": ["https://example.com/weather"],
            }
        ],
    }
    base.update(overrides)
    return base


def write(tmp_path, data):
    path = tmp_path / "edition.json"
    path.write_text(json.dumps(data))
    return path


class TestValidate:
    @pytest.mark.parametrize("recommendations,failure", [
        ([], "priority.recommendations needs exactly 3 items"),
        ([RECOMMENDATION], "priority.recommendations needs exactly 3 items"),
        ([RECOMMENDATION] * 4, "priority.recommendations needs exactly 3 items"),
        (["call customers"] * 3, "priority.recommendations[0] is not an object"),
        ([{**RECOMMENDATION, "body": "x" * 1025}] * 3, "priority.recommendations[0].body is over 1024 characters"),
        ([{**RECOMMENDATION, "evidence": []}] * 3, "priority.recommendations[0].evidence needs 1 to 3 items"),
        ([{**RECOMMENDATION, "evidence": [{"claim": "x", "source": "y", "url": "file:///tmp/x"}]}] * 3,
         "priority.recommendations[0].evidence[0].url is not an http(s) URL"),
    ])
    def test_recommendation_rules(self, recommendations, failure):
        assert failure in render.validate(recommendation_edition(recommendations))

    def test_ranked_recommendations_render_escaped_paper_prose(self):
        second = {**RECOMMENDATION, "headline": "Interview <three> users", "body": "First paragraph.\n\nSecond & final."}
        third = {**RECOMMENDATION, "headline": "Ship the proof"}
        page = recommendation_edition([RECOMMENDATION, second, third], ["Q4 — What changed?"])
        assert render.validate(page) == ""
        output = render.render_html(page, render.DEFAULT_MASTHEAD, "{{PRIORITY}}")
        assert output.index("Put retention at the center") < output.index("Interview &lt;three&gt; users")
        assert "Second &amp; final." in output
        assert "FIRST STEP" in output and "Patrick Salyer" in output
        assert "Returning users repeat the same workflow" in output
        assert 'href="https://example.com/retention"' in output
    def test_valid_is_silent(self):
        assert render.validate(edition()) == ""

    def test_missing_date(self):
        assert "date" in render.validate(edition(date="nope"))

    def test_impossible_date(self):
        assert "real calendar" in render.validate(edition(date="2026-02-30"))

    def test_sections_must_be_a_list(self):
        assert "sections is not a list" in render.validate(edition(sections={}))

    def test_unknown_kind(self):
        bad = edition(sections=[{"kind": "news", "title": "x", "body": "y"}])
        assert "kind" in render.validate(bad)

    def test_blank_title(self):
        bad = edition(sections=[{"kind": "section", "title": "", "body": "y"}])
        assert "title is blank" in render.validate(bad)

    def test_assignment_needs_run_on(self):
        bad = edition(sections=[{"kind": "assignment", "title": "x", "body": "y"}])
        assert "run_on is required" in render.validate(bad)

    def test_sources_must_be_strings(self):
        bad = edition(sections=[{"kind": "section", "title": "x", "body": "y",
                                 "sources": [1, 2]}])
        assert "sources" in render.validate(bad)

    def test_layout_must_be_main_or_sidebar(self):
        bad = edition(sections=[{
            "kind": "section", "title": "x", "body": "y", "layout": "top",
        }])
        assert "layout is not main|sidebar" in render.validate(bad)

    def test_desk_must_be_known(self):
        bad = edition(sections=[{
            "kind": "section", "title": "x", "body": "y", "desk": "gossip",
        }])
        assert "desk" in render.validate(bad)

    def test_desk_optional(self):
        assert render.validate(edition()) == ""
        assert render.validate(edition(sections=[{
            "kind": "section", "title": "x", "body": "y", "desk": "weather",
        }])) == ""

    def test_location_must_be_a_string_when_present(self):
        bad = edition(location=12)
        assert "location is not a string" in render.validate(bad)

    def test_layout_optional(self):
        assert render.validate(edition()) == ""
        assert render.validate(edition(sections=[{
            "kind": "section", "title": "x", "body": "y", "layout": "sidebar",
        }])) == ""

    def test_headline_must_be_a_string_when_present(self):
        bad = edition(sections=[{
            "kind": "section", "title": "x", "body": "y", "headline": 5,
        }])
        assert "headline is not a string" in render.validate(bad)

    def test_headline_optional(self):
        assert render.validate(edition()) == ""

    def test_topic_id_shape(self):
        bad = edition(sections=[{"kind": "section", "title": "x", "body": "y",
                                 "topic_id": "nope"}])
        assert "topic_id" in render.validate(bad)

    def test_forecast_only_on_weather(self):
        bad = edition(sections=[{
            "kind": "section", "title": "Diary", "desk": "calendar", "body": "c",
            "forecast": [{"day": "Tue", "date": "17/05", "icon": "sun", "high": 19, "low": 9}],
        }])
        assert "forecast is only valid on the weather desk" in render.validate(bad)

    def test_schedule_only_on_calendar(self):
        bad = edition(sections=[{
            "kind": "section", "title": "Weather", "desk": "weather", "body": "w",
            "schedule": [{"time": "9am", "title": "Sync", "icon": "meeting"}],
        }])
        assert "schedule is only valid on the calendar desk" in render.validate(bad)

    def test_messages_only_on_mail(self):
        bad = edition(sections=[{
            "kind": "section", "title": "Weather", "desk": "weather", "body": "w",
            "messages": [{"sender": "Ana", "subject": "Hi"}],
        }])
        assert "messages is only valid on the mail desk" in render.validate(bad)

    def test_schedule_icon_must_be_known(self):
        bad = edition(sections=[{
            "kind": "section", "title": "Diary", "desk": "calendar", "body": "c",
            "schedule": [{"time": "9am", "title": "Sync", "icon": "party"}],
        }])
        assert "icon is not one of" in render.validate(bad)

    def test_valid_strips_are_silent(self):
        assert render.validate(edition(sections=[
            {"kind": "section", "title": "Weather", "desk": "weather", "body": "w",
             "forecast": [{"day": "Tue", "date": "17/05", "icon": "rain", "high": 17, "low": 6}]},
            {"kind": "section", "title": "Diary", "desk": "calendar", "body": "c",
             "schedule": [{"time": "9am", "title": "Sync", "icon": "meeting"}]},
            {"kind": "section", "title": "Letters", "desk": "mail", "body": "m",
             "messages": [{"sender": "Ana", "subject": "Hi"}]},
        ])) == ""

    def test_priority_only_on_priority_desk(self):
        edition_data = edition(sections=[{
            "kind": "section", "title": "News", "desk": "news", "body": "n",
            "priority": {"why": [], "first_step": "x"},
        }])
        assert "priority is only valid on the priority desk" in render.validate(edition_data)

    def test_priority_title_is_the_desk_title_not_python_text(self):
        data = recommendation_edition()
        data["sections"][0]["title"] = "O que devo priorizar hoje?"
        html = render.render_html(data, render.DEFAULT_MASTHEAD, "{{PRIORITY_BLOCK}}")
        assert "O que devo priorizar hoje?" in html
        assert "priority-wrap" in html
        assert "Put retention at the center" in html

    def test_priority_title_empty_without_a_priority_desk(self):
        html = render.render_html(edition(), render.DEFAULT_MASTHEAD,
                                  "{{PRIORITY_BLOCK}}")
        assert html == ""

    def test_news_tag_renders_as_a_kicker_above_the_headline(self):
        html = render.render_html(edition(sections=[{
            "kind": "section", "title": "Markets rally", "desk": "news",
            "tag": "Economia", "body": "Stocks rose.",
            "sources": [],
        }]), render.DEFAULT_MASTHEAD, "{{LEAD}}")
        assert '<p class="kicker">Economia</p>' in html
        assert html.index("kicker") < html.index("Markets rally")
        assert '<span class="tag">Economia</span>' not in html

    def test_lead_body_paginates_as_ordinary_paragraphs(self):
        html = render.render_html(edition(sections=[{
            "kind": "section", "title": "Lead", "desk": "news",
            "body": "One.\n\nTwo.\n\nThree.\n\nFour.",
            "sources": [],
        }]), render.DEFAULT_MASTHEAD, "{{LEAD}}")
        # A 3-cell lead-body table had to stay whole (WeasyPrint paints
        # a split cell in the wrong column), so the body jumped to page
        # 2 while the front still had room. The lead fills leftover
        # space as normal paragraphs.
        assert '<div class="lead-body">' not in html
        assert "dropcap" in html
        assert "<p>" in html

    def test_news_well_is_a_stack_not_an_unbreakable_row(self):
        sections = [{
            "kind": "section", "title": f"Story {i}", "desk": "news",
            "body": f"Body {i}.", "sources": [],
        } for i in range(7)]
        html = render.render_html(edition(sections=sections),
                                  render.DEFAULT_MASTHEAD,
                                  "{{SECTIONS}}")
        # 1 lead + 6 in the well. Unbreakable 3-col tables jumped whole
        # rows onto the next sheet; the well is now a stack that can
        # fill leftover space.
        assert '<div class="news-cols">' not in html
        assert html.count("<article") == 6

    def test_news_well_keeps_every_story(self):
        sections = [{
            "kind": "section", "title": f"Story {i}", "desk": "news",
            "body": f"Body {i}.", "sources": [],
        } for i in range(5)]
        html = render.render_html(edition(sections=sections),
                                  render.DEFAULT_MASTHEAD,
                                  "{{SECTIONS}}")
        assert html.count("<article") == 4
        assert "Story 1" in html and "Story 4" in html

    def test_desks_render_as_a_boxed_teaser_row(self):
        html = render.render_html(edition(sections=[
            {"kind": "section", "title": "Agenda", "desk": "calendar",
             "body": "c", "sources": []},
            {"kind": "section", "title": "Correio", "desk": "mail",
             "body": "m", "sources": []},
        ]), render.DEFAULT_MASTHEAD, "{{DESKS_INLINE}}")
        assert '<div class="desks-row">' in html
        assert html.count('<div class="desks-cell">') == 2

    def test_priority_is_the_first_section_on_the_page(self):
        html = render.render_html(edition(sections=[
            {"kind": "section", "title": "News", "desk": "news", "body": "n", "sources": []},
            {"kind": "section", "title": "Weather", "desk": "weather", "body": "w", "sources": []},
            {"kind": "section", "title": "P", "desk": "priority", "body": "p", "sources": []},
        ]), render.DEFAULT_MASTHEAD, "{{PRIORITY}}{{WEATHER}}{{LEAD}}")
        assert html.index("section--priority") < html.index("section--weather")

    def test_priority_renders_exactly_once(self):
        html = render.render_html(
            edition_with_priority_and_weather(),
            render.DEFAULT_MASTHEAD,
            "{{PRIORITY}}{{DESKS_INLINE}}{{SIDEBAR}}",
        )
        assert html.count('section--priority"') == 1

    def test_priority_without_news_does_not_print_the_empty_budget_placeholder(self):
        html = render.render_html(
            edition_with_priority_and_weather(),
            render.DEFAULT_MASTHEAD,
            "{{LEAD}}{{PRIORITY}}",
        )
        assert "Nothing to report this time." not in html
        assert "Close the seed extension" in html
        assert html.count("<article") >= 1
        assert "{{LEAD}}" not in html
      

    def test_chat_edition_keeps_the_priority_body(self):
        p = {"recommendations": recommendations(), "questions": []}
        text = render.render_chat(edition(sections=[{
            "kind": "section", "title": "P", "desk": "priority", "body": "Send the deck",
            "priority": p, "sources": [],
        }]), render.DEFAULT_MASTHEAD)
        assert "Send the deck" in text


class TestMasthead:
    def test_json_cannot_name_the_paper(self):
        data = edition(masthead="The Fake Times")
        assert "The Fake Times" not in render.render_chat(data, render.masthead())
        assert render.DEFAULT_MASTHEAD in render.render_chat(data, render.masthead())

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("PT_MASTHEAD", "The Daily Plow")
        assert render.masthead() == "The Daily Plow"

    def test_blank_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("PT_MASTHEAD", "   ")
        assert render.masthead() == render.DEFAULT_MASTHEAD

    def test_printed_page_carries_the_mayfield_credit(self):
        template = (ROOT / "pt-edition" / "template.html").read_text()
        page = render.render_html(edition(), render.DEFAULT_MASTHEAD, template)
        assert render.DEFAULT_MASTHEAD in page
        assert "inspired by Mayfield" in page


class TestChat:
    def test_header_and_section(self):
        text = render.render_chat(edition(), render.DEFAULT_MASTHEAD)
        assert text.startswith("THE FOUNDER TIMES \u2014 Sep 11, 2026")
        assert "\u25b8 Weather in Sao Paulo" in text
        assert "Sources: https://example.com/weather" in text

    @pytest.mark.parametrize("desk", render.DESKS)
    def test_every_desk_but_priority_prints_sources_and_gaps(self, desk):
        data = edition(sections=[{
            "kind": "assignment", "topic_id": "t_3f2a", "run_on": "2026-09-11", "desk": desk,
            "title": "iPhone 15 price", "body": " ",
            "sources": ["https://shop.example/x"],
            "tag": "special for this edition",
            "could_not_source": ["the Pro model's price"],
        }])
        text = render.render_chat(data, render.DEFAULT_MASTHEAD)
        page = render.render_html(data, render.DEFAULT_MASTHEAD,
                                  "{{LEAD}}{{PRIORITY}}{{WEATHER}}{{CALENDAR}}{{MAIL}}{{SPORTS}}")
        assert "special for this edition" in text
        for out in (text, page):
            assert ("Sources:" in out) is (desk != "priority")
            assert ("Couldn't source: the Pro model" in out) is (desk != "priority")
            assert "(nothing to report this time)" in out and "budget" not in out

    def test_empty_budget_is_still_an_edition(self):
        text = render.render_chat(edition(sections=[]), render.DEFAULT_MASTHEAD)
        assert "Nothing to report this time." in text

    def test_sources_deduped(self):
        data = edition(sections=[{
            "kind": "section", "title": "x", "body": "y",
            "sources": ["https://a", "https://a", "https://b"],
        }])
        text = render.render_chat(data, render.DEFAULT_MASTHEAD)
        assert text.count("https://a") == 1

    def test_headline_renders(self):
        # Regression: headline was documented in the SKILL.md example and
        # promised by SOUL.md ("a headline, a short synthesis, and a Sources
        # line") but silently dropped by the renderer -- the model wrote it,
        # nobody ever saw it.
        data = edition(sections=[{
            "kind": "section", "title": "x", "headline": "The real headline",
            "body": "y", "sources": [],
        }])
        text = render.render_chat(data, render.DEFAULT_MASTHEAD)
        assert "The real headline" in text

    def test_missing_headline_is_fine(self):
        text = render.render_chat(edition(), render.DEFAULT_MASTHEAD)
        assert "▸ Weather in Sao Paulo\n  Rain in the afternoon." in text


class TestHtml:
    def test_web_strings_are_escaped(self):
        data = edition(sections=[{
            "kind": "section", "title": "<script>alert(1)</script>",
            "body": "<img onerror=alert(1)>", "sources": ['"><script>'],
        }])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, "<p>{{LEAD}}</p>")
        assert "<script>" not in page
        assert "<img" not in page
        assert "&lt;script&gt;" in page

    def test_placeholders_substituted(self):
        page = render.render_html(edition(), "The Daily", "{{MASTHEAD}}|{{DATE}}|{{LEAD}}")
        assert page.startswith("The Daily|Sep 11, 2026|")
        assert "Weather in Sao Paulo" in page

    def test_headline_renders_escaped(self):
        data = edition(sections=[{
            "kind": "section", "title": "x", "headline": "<b>headline</b>",
            "body": "y", "sources": [],
        }])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, "<p>{{LEAD}}</p>")
        assert 'class="headline"' in page
        assert "<b>headline</b>" not in page
        assert "&lt;b&gt;headline&lt;/b&gt;" in page

    TEMPLATE = "{{PAGE_CLASS}}|{{LEAD}}{{SECTIONS}}|{{WEATHER}}|{{CALENDAR}}|{{MAIL}}|{{SIDEBAR}}"

    def split_slots(self, page):
        return page.split("|", 5)

    def test_news_stays_in_the_news_slot(self):
        data = edition(sections=[
            {"kind": "section", "title": "News", "body": "y", "sources": []},
            {"kind": "section", "title": "Weather", "layout": "sidebar", "body": "z",
             "sources": []},
        ])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, self.TEMPLATE)
        page_class, main_html, weather, calendar, mail, desks = self.split_slots(page)
        assert page_class == "page page--no-desks"
        assert "News" in main_html and "Weather" in main_html
        assert weather == "" and calendar == "" and mail == ""
        assert desks == ""

    def test_no_desks_collapses_the_rail(self):
        page = render.render_html(edition(), render.DEFAULT_MASTHEAD, self.TEMPLATE)
        page_class, _main, weather, calendar, mail, desks = self.split_slots(page)
        assert page_class == "page page--no-desks"
        assert weather == calendar == mail == desks == ""

    def test_weather_desk_has_its_own_slot(self):
        data = edition(sections=[
            {"kind": "section", "title": "Dollar", "desk": "news", "body": "up",
             "sources": []},
            {"kind": "section", "title": "Weather", "desk": "weather", "body": "rain",
             "sources": []},
        ])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, self.TEMPLATE)
        page_class, main_html, weather, calendar, mail, desks = self.split_slots(page)
        assert page_class == "page"
        assert "Dollar" in main_html and "Weather" not in main_html
        assert "Weather" in weather and "section--weather" in weather
        assert "Dollar" not in weather
        assert calendar == "" and mail == ""
        assert "Weather" in desks

    def test_each_desk_is_a_separate_field(self):
        data = edition(sections=[
            {"kind": "section", "title": "News", "desk": "news", "body": "n",
             "sources": []},
            {"kind": "section", "title": "Mail", "desk": "mail", "body": "m",
             "sources": []},
            {"kind": "section", "title": "Weather", "desk": "weather", "body": "w",
             "sources": []},
            {"kind": "section", "title": "Diary", "desk": "calendar", "body": "c",
             "sources": []},
        ])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, self.TEMPLATE)
        _cls, main_html, weather, calendar, mail, _desks = self.split_slots(page)
        assert "News" in main_html
        assert "Weather" in weather and "Diary" not in weather and "Mail" not in weather
        assert "Diary" in calendar and "Weather" not in calendar
        assert "Mail" in mail and "Diary" not in mail
        assert "News" not in weather + calendar + mail

    def test_empty_desk_emits_no_card(self):
        page = render.render_html(edition(), render.DEFAULT_MASTHEAD,
                                  "{{WEATHER}}|{{CALENDAR}}|{{MAIL}}")
        assert page == "||"

    def test_weather_forecast_draws_icons(self):
        data = edition(sections=[{
            "kind": "section", "title": "Weather", "desk": "weather", "body": "rain",
            "forecast": [{"day": "Tue", "date": "17/05", "icon": "rain", "high": 17, "low": 6}],
            "sources": ["https://example.com/weather"], "could_not_source": ["the rain chance"],
        }])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, "{{WEATHER}}")
        assert 'class="wx-grid"' in page
        assert 'class="wx-icon"' in page
        assert "<img" not in page
        # The grid needs no sources line, but its gap still reaches the reader.
        assert "Sources:" not in page and "Couldn't source: the rain chance" in page

    def test_calendar_schedule_draws_kind_icons(self):
        data = edition(sections=[{
            "kind": "section", "title": "Agenda", "desk": "calendar",
            "body": "9am — Product sync.",
            "schedule": [
                {"time": "9am", "title": "Product <sync>", "icon": "meeting"},
                {"time": "11am", "title": "Investor call", "icon": "call"},
            ],
            "sources": ["Calendar.app"],
        }])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, "{{CALENDAR}}")
        assert 'class="cal-list"' in page
        assert page.count('class="cal-icon"') == 2
        assert "Product &lt;sync&gt;" in page
        assert "Product <sync>" not in page
        assert "<img" not in page

    def test_calendar_schedule_strip_caps_a_full_day(self):
        # Issue #7: a full Google day made the desks-row (break-inside:
        # avoid, WeasyPrint table-split workaround) jump to the next
        # page and leave the previous one blank. Cap the print strip;
        # chat serializes the uncapped `schedule` (body can omit a row).
        items = [
            {"time": f"{8 + i}:00", "title": f"Meeting {i}", "icon": "meeting"}
            for i in range(8)
        ]
        data = edition(sections=[{
            "kind": "section", "title": "Agenda", "desk": "calendar",
            "body": "Meeting 0.\n\nMeeting 7.",
            "schedule": items,
            "sources": ["Google Calendar"],
        }])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, "{{CALENDAR}}")
        assert page.count('class="cal-item"') == render.SCHEDULE_STRIP_MAX
        assert "Meeting 0" in page
        assert "Meeting 5" in page
        assert "Meeting 6" not in page
        assert "Meeting 7" not in page
        chat = render.render_chat(data, render.DEFAULT_MASTHEAD)
        assert "Meeting 6" in chat
        assert "Meeting 7" in chat

    def test_mail_messages_draw_an_envelope(self):
        data = edition(sections=[{
            "kind": "section", "title": "Letters", "desk": "mail",
            "body": "Ana — hello.",
            "messages": [{"sender": "Ana <b>Costa</b>", "subject": "Hello <script>"}],
            "sources": ["Gmail"],
        }])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, "{{MAIL}}")
        assert 'class="mail-list"' in page
        assert 'class="mail-icon"' in page
        assert "Ana &lt;b&gt;Costa&lt;/b&gt;" in page
        assert "Hello &lt;script&gt;" in page
        assert "<script>" not in page
        assert "<img" not in page

    def test_desk_headers_carry_a_drawn_mark(self):
        data = edition(sections=[
            {"kind": "section", "title": "Weather", "desk": "weather", "body": "w",
             "sources": []},
            {"kind": "section", "title": "Agenda", "desk": "calendar", "body": "c",
             "sources": []},
            {"kind": "section", "title": "Letters", "desk": "mail", "body": "m",
             "sources": []},
        ])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, self.TEMPLATE)
        _cls, _news, weather, calendar, mail, _desks = self.split_slots(page)
        assert 'class="desk-icon"' in weather
        assert 'class="desk-icon"' in calendar
        assert 'class="desk-icon"' in mail

    def test_chat_edition_has_no_icons(self):
        data = edition(sections=[{
            "kind": "section", "title": "Agenda", "desk": "calendar",
            "body": "9am — Product sync.",
            "schedule": [{"time": "9am", "title": "Product sync", "icon": "meeting"}],
            "sources": ["Calendar.app"],
        }])
        text = render.render_chat(data, render.DEFAULT_MASTHEAD)
        assert "<svg" not in text
        assert "Product sync" in text

    def test_desks_render_in_newspaper_order(self):
        data = edition(sections=[
            {"kind": "section", "title": "News", "desk": "news", "body": "n",
             "sources": []},
            {"kind": "section", "title": "Mail", "desk": "mail", "body": "m",
             "sources": []},
            {"kind": "section", "title": "Weather", "desk": "weather", "body": "w",
             "sources": []},
            {"kind": "section", "title": "Diary", "desk": "calendar", "body": "c",
             "sources": []},
        ])
        text = render.render_chat(data, render.DEFAULT_MASTHEAD)
        weather_at = text.index("Weather")
        diary_at = text.index("Diary")
        mail_at = text.index("Mail")
        news_at = text.index("News")
        assert weather_at < diary_at < mail_at < news_at

    def test_location_in_header_and_placeholder(self):
        data = edition(location="Sao Paulo")
        text = render.render_chat(data, render.DEFAULT_MASTHEAD)
        assert text.startswith("THE FOUNDER TIMES \u2014 Sep 11, 2026 \u2014 Sao Paulo")
        page = render.render_html(data, "The Daily", "{{LOCATION}}|{{SECTIONS}}")
        assert page.startswith("Sao Paulo|")

    def test_blank_paragraphs_split(self):
        data = edition(sections=[{
            "kind": "section", "title": "Diary", "desk": "calendar",
            "body": "Today: dentist at 9.\n\nUpcoming: flight on Friday.",
            "sources": ["Calendar.app"],
        }])
        page = render.render_html(data, render.DEFAULT_MASTHEAD, "{{CALENDAR}}")
        assert "Today: dentist at 9." in page
        assert "Upcoming: flight on Friday." in page
        assert "<a href=" not in page

    def test_http_sources_still_link(self):
        page = render.render_html(edition(), render.DEFAULT_MASTHEAD, "{{LEAD}}")
        assert 'href="https://example.com/weather"' in page

    def test_sudoku_is_a_table_not_authored_json(self):
        page = render.render_html(edition(), render.DEFAULT_MASTHEAD, "{{SUDOKU}}")
        assert '<table class="sk-grid">' in page
        assert page.count("<tr>") == 9
        assert "Sudoku" in page
        assert "<div class=\"sk-grid\">" not in page

    def test_sudoku_omits_the_page_rather_than_crash_the_paper(self, monkeypatch):
        def boom(*_args, **_kwargs):
            raise RuntimeError("generator failed")

        monkeypatch.setattr(render.sudoku, "generate_puzzle", boom)
        page = render.render_html(edition(), render.DEFAULT_MASTHEAD, "X{{SUDOKU}}Y")
        assert page == "XY"

    def test_chat_edition_has_no_sudoku_grid(self):
        text = render.render_chat(edition(), render.DEFAULT_MASTHEAD)
        assert "<table" not in text
        assert "sk-grid" not in text


class TestMain:
    def test_prints_chat_to_stdout(self, tmp_path, capsys):
        path = write(tmp_path, edition())
        assert render.main([str(path)]) == 0
        assert "THE FOUNDER TIMES" in capsys.readouterr().out

    def test_writes_chat_file(self, tmp_path):
        path = write(tmp_path, edition())
        out = tmp_path / "chat.txt"
        render.main([str(path), "--chat", str(out)])
        assert "Weather in Sao Paulo" in out.read_text()

    def test_writes_html(self, tmp_path):
        path = write(tmp_path, edition())
        out = tmp_path / "edition.html"
        render.main([str(path), "--html", str(out)])
        html = out.read_text()
        assert "Weather in Sao Paulo" in html
        assert '<table class="sk-grid">' in html
        assert "Sudoku" in html

    @pytest.mark.parametrize("data, named", [
        ({"date": "x", "sections": []}, "date is not a strict YYYY-MM-DD string"),
        # A page rule refuses the same way: by field, and no page is written.
        (priority_edition(headline="Call Dana then send the deck"),
         "sections[0].headline carries more than one action"),
    ])
    def test_malformed_refused_by_name(self, tmp_path, data, named):
        path = write(tmp_path, data)
        with pytest.raises(SystemExit) as refused:
            render.main([str(path), "--html", str(tmp_path / "out.html")])
        assert f"invalid edition.json: {named}" in str(refused.value)
        assert not (tmp_path / "out.html").exists()

    def test_unreadable_refused(self, tmp_path):
        with pytest.raises(SystemExit, match="could not read"):
            render.main([str(tmp_path / "missing.json")])

    def test_deterministic(self, tmp_path):
        path = write(tmp_path, edition())
        first = tmp_path / "a.html"
        second = tmp_path / "b.html"
        render.main([str(path), "--html", str(first)])
        render.main([str(path), "--html", str(second)])
        assert first.read_text() == second.read_text()


class TestEnsurePriorityDesk:
    WEATHER = {"kind": "section", "title": "Weather", "desk": "weather", "body": "rain", "sources": []}
    ON = {"priority": {"configured": True}, "owner": {"language": "English"}}

    @pytest.mark.parametrize("config, sections, inserted, priority_desks", [
        ({"priority": {"configured": False}}, [WEATHER], False, 0),
        (ON, [WEATHER], True, 1),
        # A one-topic subscription edition carries no standing desk.
        (ON, edition()["sections"], False, 0),
        (ON, edition_with_priority_and_weather()["sections"], False, 1),
    ])
    def test_inserts_the_gap_card_only_on_a_paper_missing_it(
            self, config, sections, inserted, priority_desks):
        out, did = render.ensure_priority_desk(edition(sections=sections), config)
        assert did is inserted
        assert [render.desk_of(s) for s in out["sections"]].count("priority") == priority_desks
        assert render.validate(out) == ""

    def test_main_injects_the_card_from_config(self, tmp_path):
        # Measured live 2026-09-18: priority.configured was true, research
        # never wrote desk-priority, edition.json shipped weather/mail/news
        # only. The renderer must put the card on the page itself.
        ed_path = write(tmp_path, edition(sections=[self.WEATHER]))
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({
            "priority": {"configured": True},
            "owner": {"language": "English"},
        }), encoding="utf-8")
        html_path = tmp_path / "out.html"
        render.main([str(ed_path), "--html", str(html_path), "--config", str(cfg)])
        html = html_path.read_text()
        assert "section--priority" in html
        assert "What to prioritize today" in html

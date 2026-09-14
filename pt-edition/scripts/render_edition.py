#!/usr/bin/env python3
"""render_edition.py -- content in, newspaper out, the same layout every day.

The whole point of separating this from the language model: the model fills
an `edition.json` (headlines, sentences, sources, tags) and this script --
fixed code over a fixed `template.html` -- turns it into the chat text, the
printable HTML and (when weasyprint is present) the PDF. The model never
writes HTML. Same JSON + same template = the same layout, byte for byte, so
two editions differ only in their content, exactly like a printed paper.

    render_edition.py <edition.json> [--chat OUT] [--html OUT] [--pdf OUT]

With no output flags the chat edition goes to stdout -- the cron-fired
session's final response *is* the chat leg, so this is the normal path. The
HTML is the print leg and the PDF the attachment leg; both are opt-in.

Every string that came from the web is HTML-escaped here, once, in code --
headlines, bodies, tags, sources, the lot. A researched page is untrusted
input and the HTML renders on the owner's Mac; an unescaped quote is
injection, not typography. The template is loaded from beside this script
and is owner-editable (copy-if-absent, so redeploys never clobber it); the
masthead comes from PT_MASTHEAD or the default, never from the JSON, so the
chat text and the printed page can never disagree about the paper's name.

A malformed edition.json is refused loudly and by name, the way the config
gate refuses a malformed config: a half-rendered page shipped is worse than
a run that says what was wrong and waits for the next one.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import pathlib
import re
import sys
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sudoku  # noqa: E402 -- sibling script beside this one

DEFAULT_MASTHEAD = "THE PLOW TIMES"
KINDS = ("section", "assignment")
# Standing newspaper desks. weather and calendar always run; mail only when
# pt/config.json says mail.configured. news is every owner-chosen section
# and assignment -- same story shape, different page slot.
DESKS = ("news", "weather", "calendar", "mail")
DESK_ORDER = {"weather": 0, "calendar": 1, "mail": 2, "news": 3}
# Controlled vocabulary for the weather forecast strip -- an icon is drawn
# from this fixed inline-SVG set (see WEATHER_ICONS), never fetched, so an
# unrecognized key is a validation failure rather than a silently broken
# picture or a remote image request.
FORECAST_ICONS = ("sun", "partly-cloudy", "cloud", "rain", "storm", "snow")
# Same idea for the calendar desk's schedule rows -- what kind of event this
# is, drawn from CALENDAR_ICONS, never free text.
SCHEDULE_ICONS = ("meeting", "call", "task", "reminder", "note")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TOPIC_ID_RE = re.compile(r"^t_[0-9a-f]{4}$")
TEMPLATE = pathlib.Path(__file__).resolve().parent.parent / "template.html"

# calendar.month_abbr is locale-independent C locale by default; pinned here
# so the masthead's date cannot drift with the container's locale.
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def masthead():
    return (os.environ.get("PT_MASTHEAD") or DEFAULT_MASTHEAD).strip() or DEFAULT_MASTHEAD


def pretty_date(raw):
    """'2026-09-11' -> 'Sep 11, 2026', the masthead's date line."""
    year, month, day = (int(part) for part in raw.split("-"))
    return f"{_MONTHS[month - 1]} {day}, {year}"


def validate(edition):
    """The structural gate for edition.json; returns "; "-joined failures.

    Empty means pass. Never raises for a content problem -- a bad shape is a
    named failure, so the run can say which section is wrong instead of
    crashing on a KeyError deep in rendering.
    """
    failures = []
    if not isinstance(edition, dict):
        return "edition.json is not a JSON object"

    raw_date = edition.get("date")
    if not (isinstance(raw_date, str) and DATE_RE.fullmatch(raw_date)):
        failures.append("date is not a strict YYYY-MM-DD string")
    else:
        try:
            date.fromisoformat(raw_date)
        except ValueError:
            failures.append("date is not a real calendar date")

    location = edition.get("location")
    if location is not None and not isinstance(location, str):
        failures.append("location is not a string")

    sections = edition.get("sections")
    if not isinstance(sections, list):
        return "; ".join(failures + ["sections is not a list"])
    for index, section in enumerate(sections):
        where = f"sections[{index}]"
        if not isinstance(section, dict):
            failures.append(f"{where} is not an object")
            continue
        kind = section.get("kind")
        if kind not in KINDS:
            failures.append(f"{where}.kind is not section|assignment")
        title = section.get("title")
        if not (isinstance(title, str) and title.strip()):
            failures.append(f"{where}.title is blank")
        if not isinstance(section.get("body"), str):
            failures.append(f"{where}.body is not a string")
        headline = section.get("headline")
        if headline is not None and not isinstance(headline, str):
            failures.append(f"{where}.headline is not a string")
        layout = section.get("layout")
        if layout is not None and layout not in ("main", "sidebar"):
            failures.append(f"{where}.layout is not main|sidebar")
        desk = section.get("desk")
        if desk is not None and desk not in DESKS:
            failures.append(f"{where}.desk is not news|weather|calendar|mail")
        sources = section.get("sources", [])
        if not isinstance(sources, list) or not all(isinstance(u, str) for u in sources):
            failures.append(f"{where}.sources is not a list of strings")
        could_not = section.get("could_not_source", [])
        if not isinstance(could_not, list) or not all(isinstance(c, str) for c in could_not):
            failures.append(f"{where}.could_not_source is not a list of strings")
        topic_id = section.get("topic_id")
        if topic_id is not None and not (
            isinstance(topic_id, str) and TOPIC_ID_RE.fullmatch(topic_id)
        ):
            failures.append(f"{where}.topic_id is not a t_xxxx id")
        if kind == "assignment":
            run_on = section.get("run_on")
            if not (isinstance(run_on, str) and DATE_RE.fullmatch(run_on)):
                failures.append(f"{where}.run_on is required for an assignment")
        forecast = section.get("forecast")
        if forecast is not None:
            if desk != "weather":
                failures.append(f"{where}.forecast is only valid on the weather desk")
            elif not isinstance(forecast, list) or not (1 <= len(forecast) <= 6):
                failures.append(f"{where}.forecast is not a list of 1-6 days")
            else:
                for day_index, day in enumerate(forecast):
                    dwhere = f"{where}.forecast[{day_index}]"
                    if not isinstance(day, dict):
                        failures.append(f"{dwhere} is not an object")
                        continue
                    if not (isinstance(day.get("day"), str) and day["day"].strip()):
                        failures.append(f"{dwhere}.day is blank")
                    if not (isinstance(day.get("date"), str) and day["date"].strip()):
                        failures.append(f"{dwhere}.date is blank")
                    if day.get("icon") not in FORECAST_ICONS:
                        failures.append(f"{dwhere}.icon is not one of {FORECAST_ICONS}")
                    if not isinstance(day.get("high"), (int, float)):
                        failures.append(f"{dwhere}.high is not a number")
                    if not isinstance(day.get("low"), (int, float)):
                        failures.append(f"{dwhere}.low is not a number")
        schedule = section.get("schedule")
        if schedule is not None:
            if desk != "calendar":
                failures.append(f"{where}.schedule is only valid on the calendar desk")
            elif not isinstance(schedule, list) or not schedule:
                failures.append(f"{where}.schedule is not a non-empty list")
            else:
                for item_index, item in enumerate(schedule):
                    iwhere = f"{where}.schedule[{item_index}]"
                    if not isinstance(item, dict):
                        failures.append(f"{iwhere} is not an object")
                        continue
                    if not (isinstance(item.get("time"), str) and item["time"].strip()):
                        failures.append(f"{iwhere}.time is blank")
                    if not (isinstance(item.get("title"), str) and item["title"].strip()):
                        failures.append(f"{iwhere}.title is blank")
                    if item.get("icon") not in SCHEDULE_ICONS:
                        failures.append(f"{iwhere}.icon is not one of {SCHEDULE_ICONS}")
        messages = section.get("messages")
        if messages is not None:
            if desk != "mail":
                failures.append(f"{where}.messages is only valid on the mail desk")
            elif not isinstance(messages, list) or not messages:
                failures.append(f"{where}.messages is not a non-empty list")
            else:
                for item_index, item in enumerate(messages):
                    iwhere = f"{where}.messages[{item_index}]"
                    if not isinstance(item, dict):
                        failures.append(f"{iwhere} is not an object")
                        continue
                    if not (isinstance(item.get("sender"), str) and item["sender"].strip()):
                        failures.append(f"{iwhere}.sender is blank")
                    if not (isinstance(item.get("subject"), str) and item["subject"].strip()):
                        failures.append(f"{iwhere}.subject is blank")
    return "; ".join(failures)


def dedupe(values):
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def desk_of(section):
    """Which newspaper desk this block belongs to. Default news."""
    desk = section.get("desk")
    return desk if desk in DESKS else "news"


def ordered_sections(sections):
    """Weather, calendar, mail, then news -- the paper's fixed departments."""
    return sorted(
        enumerate(sections),
        key=lambda item: (DESK_ORDER.get(desk_of(item[1]), 9), item[0]),
    )


def is_news_section(section):
    """Owner news and assignments -- never a standing desk."""
    return desk_of(section) == "news"


def join_articles(sections):
    return "\n".join(html_section(s) for s in sections)


def wrap_desk(html):
    """A desk card exists only when it has copy -- no empty bordered box."""
    html = (html or "").strip()
    if not html:
        return ""
    return f'<div class="desk-slot">{html}</div>'


def body_paragraphs(body):
    """Split a body on blank lines so a desk can have today / upcoming grafs."""
    text = (body or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split("\n\n") if part.strip()]


def source_markup(url):
    """http(s) sources are links; Latch/Calendar labels stay plain text."""
    escaped = html.escape(url)
    if url.startswith(("http://", "https://")):
        return f'<a href="{html.escape(url, quote=True)}">{escaped}</a>'
    return escaped


def chat_section(section):
    """One topic's block in the chat edition."""
    title = section["title"].strip()
    tag = section.get("tag")
    desk = desk_of(section)
    kicker = f"{desk} \u2014 " if desk != "news" else ""
    lines = [f"\u25b8 {kicker}{title}" + (f" \u2014 {tag}" if tag else "")]
    headline = (section.get("headline") or "").strip()
    if headline:
        lines.append(f"  {headline}")
    body = section.get("body", "").strip()
    lines.append(f"  {body}" if body else "  (nothing usable in the budget this time)")
    sources = dedupe(section.get("sources", []))
    if sources:
        lines.append("  Sources: " + ", ".join(sources))
    could_not = section.get("could_not_source", [])
    if could_not:
        lines.append("  Couldn't source: " + "; ".join(could_not))
    return "\n".join(lines)


def render_chat(edition, name):
    header = f"{name} \u2014 {pretty_date(edition['date'])}"
    location = (edition.get("location") or "").strip()
    if location:
        header = f"{header} \u2014 {location}"
    lines = [header]
    if edition["sections"]:
        for _index, section in ordered_sections(edition["sections"]):
            lines.append("")
            lines.append(chat_section(section))
    else:
        lines.append("")
        lines.append("Nothing usable in the budget this time.")
    return "\n".join(lines) + "\n"


# Inline, monochrome (currentColor) weather-strip icons -- drawn, never
# fetched, so the "no external assets" rule in template.html holds even
# for pictures. Each is a small fixed-viewBox line drawing; FORECAST_ICONS
# is the only allowed set of keys into this dict.
WEATHER_ICONS = {
    "sun": (
        '<circle cx="12" cy="12" r="4.5"/>'
        '<path d="M12 2v3M12 19v3M4.6 4.6l2.1 2.1M17.3 17.3l2.1 2.1'
        'M2 12h3M19 12h3M4.6 19.4l2.1-2.1M17.3 6.7l2.1-2.1"/>'
    ),
    "partly-cloudy": (
        '<circle cx="9.5" cy="9.5" r="3.6"/>'
        '<path d="M9.5 2.8v2.2M4.3 4.3l1.6 1.6M2.8 9.5H5M15 9.5h2.2M13.4 5.9l1.6-1.6"/>'
        '<path d="M8 21h9.5a3.5 3.5 0 0 0 .5-6.96A5 5 0 0 0 8.6 12.2'
        'a3.2 3.2 0 0 0-.6 6.3"/>'
    ),
    "cloud": (
        '<path d="M7 20h10.5a3.5 3.5 0 0 0 .5-6.96A5 5 0 0 0 7.6 11.2'
        'a3.2 3.2 0 0 0-.6 6.3"/>'
    ),
    "rain": (
        '<path d="M6.5 15h10.5a3.5 3.5 0 0 0 .5-6.96A5 5 0 0 0 7.1 6.2'
        'a3.2 3.2 0 0 0-.6 6.3"/>'
        '<path d="M8 18.5l-1.2 3M12 18.5l-1.2 3M16 18.5l-1.2 3"/>'
    ),
    "storm": (
        '<path d="M6.5 13.5h10.5a3.5 3.5 0 0 0 .5-6.96A5 5 0 0 0 7.1 4.7'
        'a3.2 3.2 0 0 0-.6 6.3"/>'
        '<path d="M12.5 15.5l-2.7 4.3h2.6l-1.7 3.4"/>'
    ),
    "snow": (
        '<path d="M6.5 15h10.5a3.5 3.5 0 0 0 .5-6.96A5 5 0 0 0 7.1 6.2'
        'a3.2 3.2 0 0 0-.6 6.3"/>'
        '<path d="M8 18v3.5M6.5 19.2l3 2.1M9.5 19.2l-3 2.1'
        'M16 18v3.5M14.5 19.2l3 2.1M17.5 19.2l-3 2.1"/>'
    ),
}


def weather_icon(key):
    """One 28x28 inline SVG for a forecast day. `key` is pre-validated
    against FORECAST_ICONS by validate(); this still falls back to a plain
    cloud rather than trust an unchecked caller."""
    body = WEATHER_ICONS.get(key, WEATHER_ICONS["cloud"])
    return (
        '<svg class="wx-icon" viewBox="0 0 24 24" width="28" height="28" '
        'fill="none" stroke="currentColor" stroke-width="1.4" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f"{body}</svg>"
    )


def forecast_grid(days):
    """The weather desk's day-by-day strip: one cell per forecast day,
    each a drawn icon plus day/date/high/low. Every string here came from
    the day's own note, so it is escaped like any other section field.
    Deliberately just temperatures -- wind/humidity/precip were tried and
    dropped, the owner wanted the strip to stay to a glance, not a full
    weather-station readout."""
    cells = []
    for day in days:
        label = html.escape(day["day"].strip())
        date_str = html.escape(day["date"].strip())
        icon = weather_icon(day.get("icon"))
        high = html.escape(str(day["high"]))
        low = html.escape(str(day["low"]))
        cells.append(
            '<div class="wx-day">'
            f'<span class="wx-day-name">{label}</span>'
            f'<span class="wx-day-date">{date_str}</span>'
            f'<span class="wx-icon-wrap">{icon}</span>'
            f'<span class="wx-high">{high}&deg;</span>'
            f'<span class="wx-low">{low}&deg;</span>'
            "</div>"
        )
    return '<div class="wx-grid">' + "".join(cells) + "</div>"


# Same drawn-not-fetched approach for the calendar desk: what kind of event
# a schedule row is, so a meeting reads differently from a call or a task
# at a glance -- SCHEDULE_ICONS is the only allowed set of keys.
CALENDAR_ICONS = {
    "meeting": (
        '<circle cx="9" cy="8.5" r="2.6"/><circle cx="17" cy="9.5" r="2.1"/>'
        '<path d="M3.5 19c.4-3 2.6-5 5.5-5s5.1 2 5.5 5"/>'
        '<path d="M14.8 14.3c2.3.2 4 1.9 4.3 4.4"/>'
    ),
    "call": (
        '<path d="M5.5 4.5c1.4-.6 2-.4 2.6.4l1.3 1.9c.4.6.3 1.2-.2 1.8'
        'l-1 1.1c.7 1.8 2.3 3.4 4.1 4.1l1.1-1c.6-.5 1.2-.6 1.8-.2l1.9 1.3'
        'c.8.6 1 1.2.4 2.6-.6 1.4-1.7 2.1-3.1 1.9-4.3-.6-8.1-4.8-9.1-9.1'
        'C4.3 8.3 5 7.2 5.5 4.5z"/>'
    ),
    "task": (
        '<rect x="4.5" y="4.5" width="15" height="15" rx="2"/>'
        '<path d="M8 12.3l2.5 2.5L16.5 9"/>'
    ),
    "reminder": (
        '<path d="M6 17.5V11a6 6 0 0 1 12 0v6.5"/>'
        '<path d="M4.5 17.5h15M10 20.5a2 2 0 0 0 4 0"/>'
    ),
    "note": (
        '<path d="M6 4.5h12v15H6z"/><path d="M9 9h6M9 12.5h6M9 16h3.5"/>'
    ),
}
# A mail item's icon never varies by content (there is no meaningful
# "kind" of letter the way there is a kind of calendar event), so this is
# one constant drawing, not a lookup keyed by untrusted data.
MAIL_ICON = '<path d="M4 6.5h16v11H4z"/><path d="M4.5 7l7.5 6 7.5-6"/>'
# Department mark in the filled desk header -- same drawn-not-fetched
# rule as the strips. Weather already has a per-day icon in the forecast
# grid; calendar and mail get the same kind of mark in the title bar so
# the three boxes read as a set.
DESK_HEADER_ICONS = {
    "weather": (
        '<circle cx="12" cy="12" r="3.6"/>'
        '<path d="M12 3.2v2.2M12 18.6v2.2M5.4 5.4l1.6 1.6M16.9 16.9l1.6 1.6'
        'M3.2 12h2.2M18.6 12h2.2M5.4 18.6l1.6-1.6M16.9 7l1.6-1.6"/>'
    ),
    "calendar": (
        '<rect x="4" y="6" width="16" height="14" rx="1.5"/>'
        '<path d="M8 4v4M16 4v4M4 11h16"/>'
    ),
    "mail": MAIL_ICON,
}


def _stroke_svg(css_class, body, size):
    return (
        f'<svg class="{css_class}" viewBox="0 0 24 24" width="{size}" height="{size}" '
        'fill="none" stroke="currentColor" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f"{body}</svg>"
    )


def desk_header_icon(desk):
    """Tiny monochrome mark for a standing-desk title bar, or '' for news."""
    body = DESK_HEADER_ICONS.get(desk)
    if not body:
        return ""
    return _stroke_svg("desk-icon", body, 13)


def calendar_icon(key):
    """One 20x20 inline SVG for a schedule row. `key` is pre-validated
    against SCHEDULE_ICONS by validate(); falls back to the generic note
    icon rather than trust an unchecked caller."""
    body = CALENDAR_ICONS.get(key, CALENDAR_ICONS["note"])
    return (
        '<svg class="cal-icon" viewBox="0 0 24 24" width="20" height="20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f"{body}</svg>"
    )


def schedule_list(items):
    """The calendar desk's agenda: one row per event, icon plus a bold
    time and the title -- every string here came from the day's own
    note, so it is escaped like any other section field."""
    rows = []
    for item in items:
        icon = calendar_icon(item.get("icon"))
        time_str = html.escape(item["time"].strip())
        title = html.escape(item["title"].strip())
        rows.append(
            '<div class="cal-item">'
            f'<span class="cal-icon-wrap">{icon}</span>'
            f'<span class="cal-time">{time_str}</span>'
            f'<span class="cal-title">{title}</span>'
            "</div>"
        )
    return '<div class="cal-list">' + "".join(rows) + "</div>"


def messages_list(items):
    """The mail desk's letters: one row per message, an envelope mark
    plus a bold sender and the subject -- escaped like any other field."""
    icon = (
        '<svg class="mail-icon" viewBox="0 0 24 24" width="18" height="18" '
        'fill="none" stroke="currentColor" stroke-width="1.5" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f"{MAIL_ICON}</svg>"
    )
    rows = []
    for item in items:
        sender = html.escape(item["sender"].strip())
        subject = html.escape(item["subject"].strip())
        rows.append(
            '<div class="mail-item">'
            f'<span class="mail-icon-wrap">{icon}</span>'
            f'<span class="mail-sender">{sender}</span>'
            f'<span class="mail-subject">{subject}</span>'
            "</div>"
        )
    return '<div class="mail-list">' + "".join(rows) + "</div>"


def html_section(section):
    """One topic's block as escaped HTML. Every dynamic string is escaped.

    ``desk`` (optional, default ``news``) is the newspaper department.
    Each standing desk is a slot of its own ({{WEATHER}}, {{CALENDAR}},
    {{MAIL}}); the first news story fills {{LEAD}} and the rest fill
    {{SECTIONS}}. Same story fields, same escaping; only the wrapping
    class and the page slot differ.
    """
    title = html.escape(section["title"].strip())
    tag = section.get("tag")
    tag_html = f' <span class="tag">{html.escape(tag)}</span>' if tag else ""
    headline = (section.get("headline") or "").strip()
    paras = body_paragraphs(section.get("body", ""))
    desk = desk_of(section)
    classes = ["section"]
    if desk != "news":
        classes.append("section--desk")
        classes.append(f"section--{desk}")
    elif section.get("layout") == "sidebar":
        classes.append("section--sidebar")
    article_class = " ".join(classes)
    header_icon = desk_header_icon(desk)
    forecast = section.get("forecast") if desk == "weather" else None
    # A forecast grid is self-explanatory (a sun icon and 26 degrees needs
    # no caption) -- the title bar, headline, body prose and sources line
    # are all dropped for weather when it's carrying a grid, so the box
    # is just the days, nothing else. Without a forecast there is nothing
    # else in the box, so all of that stays -- same as before this field
    # existed. The plain-text chat edition is unaffected either way (see
    # chat_section) -- this omission is print/HTML-only.
    skip_caption = bool(forecast)
    blocks = [f'<article class="{article_class}">']
    if not skip_caption:
        blocks.append(f'  <h2>{header_icon}{title}{tag_html}</h2>')
        if headline:
            blocks.append(f'  <p class="headline">{html.escape(headline)}</p>')
    if forecast:
        blocks.append(forecast_grid(forecast))
    schedule = section.get("schedule") if desk == "calendar" else None
    if schedule:
        blocks.append(schedule_list(schedule))
    messages = section.get("messages") if desk == "mail" else None
    if messages:
        blocks.append(messages_list(messages))
    if skip_caption:
        pass
    elif paras:
        for para in paras:
            blocks.append(f"  <p>{html.escape(para)}</p>")
    else:
        blocks.append("  <p>(nothing usable in the budget this time)</p>")
    if not skip_caption:
        sources = dedupe(section.get("sources", []))
        if sources:
            links = ", ".join(source_markup(url) for url in sources)
            blocks.append(f'  <p class="sources">Sources: {links}</p>')
        could_not = section.get("could_not_source", [])
        if could_not:
            items = "; ".join(html.escape(item) for item in could_not)
            blocks.append(f'  <p class="unsourced">Couldn\'t source: {items}</p>')
    blocks.append("</article>")
    return "\n".join(blocks)


DIFFICULTY_LABEL = {"easy": "Fácil", "medium": "Médio"}


def sudoku_section_html(edition_date):
    """The paper's puzzle page: one Easy or Medium Sudoku, generated and
    verified by sudoku.py -- never authored by the model, so there is no
    such thing as a broken grid here. Seeded on the edition's own date so
    re-rendering the same edition always reproduces the same puzzle.
    A generator failure omits the puzzle rather than taking down the
    rest of the paper."""
    try:
        difficulty = sudoku.pick_difficulty(edition_date)
        puzzle, solution, _givens = sudoku.generate_puzzle(
            difficulty, seed=edition_date
        )
        sudoku.verify_puzzle(puzzle, solution)
    except (RuntimeError, ValueError, TypeError):
        return ""
    label = DIFFICULTY_LABEL[difficulty]

    rows_html = []
    for r in range(9):
        cells = []
        for c in range(9):
            value = puzzle[r][c]
            text = str(value) if value in range(1, 10) else ""
            classes = ["sk-cell"]
            if text:
                classes.append("sk-given")
            if c % 3 == 0:
                classes.append("sk-box-left")
            if r % 3 == 0:
                classes.append("sk-box-top")
            cells.append(f'<td class="{" ".join(classes)}">{text}</td>')
        rows_html.append("<tr>" + "".join(cells) + "</tr>")
    grid_html = f'<table class="sk-grid">{"".join(rows_html)}</table>'

    solution_rows = []
    for r in range(9):
        solution_rows.append(
            "".join(str(v) if v in range(1, 10) else "?" for v in solution[r])
        )
    solution_html = (
        '<p class="sk-solution">Solução: '
        + " · ".join(solution_rows)
        + "</p>"
    )

    return (
        '<article class="section sudoku-section">'
        f'<h2>Sudoku <span class="tag">{html.escape(label)}</span></h2>'
        f"{grid_html}"
        f"{solution_html}"
        "</article>"
    )


def render_html(edition, name, template_text):
    ordered = [section for _index, section in ordered_sections(edition["sections"])]
    news = [s for s in ordered if is_news_section(s)]
    weather = [s for s in ordered if desk_of(s) == "weather"]
    calendar = [s for s in ordered if desk_of(s) == "calendar"]
    mail = [s for s in ordered if desk_of(s) == "mail"]

    # The lead story renders separately from the rest of the news well so
    # it can sit beside the desks strip in a top row (table-cell, the same
    # WeasyPrint-safe technique as the desks themselves) -- the top row's
    # height is now just "one story vs. three short desks", not "twenty
    # stories vs. three short desks", which is what made the old side-rail
    # layout leave a long empty gap beside the desks on a busy edition.
    if news:
        lead_html = html_section(news[0])
        main_html = join_articles(news[1:])
    else:
        lead_html = '<article class="section"><p>Nothing usable in the budget this time.</p></article>'
        main_html = ""
    weather_html = wrap_desk(join_articles(weather))
    calendar_html = wrap_desk(join_articles(calendar))
    mail_html = wrap_desk(join_articles(mail))
    # {{SIDEBAR}} is the desks column as a whole, for older templates that
    # still have one rail slot instead of three. New template.html uses the
    # three named slots and leaves this empty of news.
    desks_html = "\n".join(part for part in (weather_html, calendar_html, mail_html) if part)

    page_class = "page" if desks_html else "page page--no-desks"
    location = html.escape((edition.get("location") or "").strip() or "One copy")
    sudoku_html = sudoku_section_html(edition["date"])

    return (
        template_text
        .replace("{{MASTHEAD}}", html.escape(name))
        .replace("{{DATE}}", html.escape(pretty_date(edition["date"])))
        .replace("{{LOCATION}}", location)
        .replace("{{PAGE_CLASS}}", page_class)
        .replace("{{LEAD}}", lead_html)
        .replace("{{SECTIONS}}", main_html)
        .replace("{{WEATHER}}", weather_html)
        .replace("{{CALENDAR}}", calendar_html)
        .replace("{{MAIL}}", mail_html)
        .replace("{{SIDEBAR}}", desks_html)
        .replace("{{SUDOKU}}", sudoku_html)
    )


def write_pdf(html_text, path):
    """The PDF leg. weasyprint is optional; its absence is a named failure."""
    try:
        from weasyprint import HTML  # noqa: PLC0415 -- optional dependency
    except ImportError:
        sys.exit(
            "error: weasyprint is not installed; cannot write the PDF edition "
            "(the personalized-paper plan §5 has the Chrome-on-Mac fallback)."
        )
    HTML(string=html_text).write_pdf(str(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("edition", help="path to edition.json")
    parser.add_argument("--chat", default=None, help="write the chat text here")
    parser.add_argument("--html", default=None, help="write the printable HTML here")
    parser.add_argument("--pdf", default=None, help="write a PDF here (needs weasyprint)")
    args = parser.parse_args(argv)

    try:
        edition = json.loads(pathlib.Path(args.edition).read_text())
    except (OSError, ValueError) as exc:
        sys.exit(f"error: could not read {args.edition}: {exc!r}")

    failures = validate(edition)
    if failures:
        sys.exit(f"error: invalid edition.json: {failures}")

    name = masthead()
    chat_text = render_chat(edition, name)

    if args.chat:
        pathlib.Path(args.chat).write_text(chat_text)
    else:
        sys.stdout.write(chat_text)

    if args.html or args.pdf:
        try:
            template_text = TEMPLATE.read_text()
        except OSError as exc:
            sys.exit(f"error: could not read template {TEMPLATE}: {exc!r}")
        page = render_html(edition, name, template_text)
        if args.html:
            pathlib.Path(args.html).write_text(page)
        if args.pdf:
            write_pdf(page, args.pdf)

    return 0


if __name__ == "__main__":
    sys.exit(main())

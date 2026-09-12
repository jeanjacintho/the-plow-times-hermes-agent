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

DEFAULT_MASTHEAD = "THE PLOW TIMES"
KINDS = ("section", "assignment")
# Standing newspaper desks. weather and calendar always run; mail only when
# pt/config.json says mail.configured. news is every owner-chosen section
# and assignment -- same story shape, different page slot.
DESKS = ("news", "weather", "calendar", "mail")
DESK_ORDER = {"weather": 0, "calendar": 1, "mail": 2, "news": 3}
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


def html_section(section):
    """One topic's block as escaped HTML. Every dynamic string is escaped.

    ``desk`` (optional, default ``news``) is the newspaper department.
    Each standing desk is a slot of its own ({{WEATHER}}, {{CALENDAR}},
    {{MAIL}}); news fills {{SECTIONS}}. Same story fields, same escaping;
    only the wrapping class and the page slot differ.
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
    blocks = [f'<article class="{article_class}">',
              f'  <h2>{title}{tag_html}</h2>']
    if headline:
        blocks.append(f'  <p class="headline">{html.escape(headline)}</p>')
    if paras:
        for para in paras:
            blocks.append(f"  <p>{html.escape(para)}</p>")
    else:
        blocks.append("  <p>(nothing usable in the budget this time)</p>")
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


def render_html(edition, name, template_text):
    ordered = [section for _index, section in ordered_sections(edition["sections"])]
    news = [s for s in ordered if is_news_section(s)]
    weather = [s for s in ordered if desk_of(s) == "weather"]
    calendar = [s for s in ordered if desk_of(s) == "calendar"]
    mail = [s for s in ordered if desk_of(s) == "mail"]

    main_html = join_articles(news) or (
        '<article class="section"><p>Nothing usable in the budget this time.</p></article>'
    )
    weather_html = wrap_desk(join_articles(weather))
    calendar_html = wrap_desk(join_articles(calendar))
    mail_html = wrap_desk(join_articles(mail))
    # {{SIDEBAR}} is the desks column as a whole, for older templates that
    # still have one rail slot instead of three. New template.html uses the
    # three named slots and leaves this empty of news.
    desks_html = "\n".join(part for part in (weather_html, calendar_html, mail_html) if part)

    page_class = "page" if desks_html else "page page--no-desks"
    location = html.escape((edition.get("location") or "").strip() or "One copy")

    return (
        template_text
        .replace("{{MASTHEAD}}", html.escape(name))
        .replace("{{DATE}}", html.escape(pretty_date(edition["date"])))
        .replace("{{LOCATION}}", location)
        .replace("{{PAGE_CLASS}}", page_class)
        .replace("{{SECTIONS}}", main_html)
        .replace("{{WEATHER}}", weather_html)
        .replace("{{CALENDAR}}", calendar_html)
        .replace("{{MAIL}}", mail_html)
        .replace("{{SIDEBAR}}", desks_html)
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

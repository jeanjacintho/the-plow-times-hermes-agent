---
name: pt-edition
description: Compile one or more topics' research notes into edition.json, render it with render_edition.py into printable HTML and PDF, post the PDF only via post_to_chat.py, end the turn with NO_REPLY, mark the topics it carried, and hand the print leg to pt-print when a printer is configured. Runs in the cron-fired session after pt-research.
---

# pt-edition — notes become the edition

The edition is the product. Every rule here serves one idea: a reader on a
phone (or holding a printed page) gets a short, sourced answer, and nothing
in it is a guess.

## Write `edition.json`, never the layout

You compile structured content; the layout is code, not text. **Never write
HTML.** Hand-write `edition.json` under the run directory:

```json
{
  "date": "2026-09-11",
  "location": "Sao Paulo",
  "sections": [
    { "kind": "section", "desk": "weather",
      "title": "Weather",
      "headline": "Rain in the afternoon",
      "body": "3–6 sentences from desk-weather notes, city named.",
      "sources": ["https://…"],
      "could_not_source": [] },
    { "kind": "section", "desk": "calendar",
      "title": "Calendar",
      "headline": "Two meetings before noon",
      "body": "Today: …\n\nUpcoming: …",
      "sources": ["Calendar.app"] },
    { "kind": "section", "desk": "mail",
      "title": "Letters",
      "headline": "Three messages overnight",
      "body": "Sender — subject. Sender — subject.",
      "sources": ["Gmail"] },
    { "kind": "section", "topic_id": "t_8c1d", "desk": "news",
      "title": "The dollar",
      "headline": "The real headline",
      "body": "3–6 sentences, every one traceable to a note.",
      "sources": ["https://…"],
      "could_not_source": ["…"] },
    { "kind": "assignment", "topic_id": "t_3f2a", "run_on": "2026-09-11",
      "desk": "news",
      "title": "iPhone 15 price",
      "body": "…", "sources": ["https://…"],
      "tag": "special for this edition",
      "could_not_source": ["…"] }
  ]
}
```

- **`date` is the owner's local date** (from `pt/config.json`'s
  `owner.timezone`), never the container's clock reading past midnight.
- **`topic_id` is mandatory per section** — the delivery step marks each
  topic from it. Without it, marking depends on session memory, which SOUL.md
  forbids. `run_on` is required for an assignment.
- **The title is the topic's text**, trimmed of pleasantries; it is the
  owner's own words.
- **Write `headline` and `body` in `pt/config.json`'s `owner.language`** —
  Portuguese in, Portuguese out; English in, English out; Mandarin in,
  Mandarin out, whatever pt-intake last recorded there. This is the whole
  edition's reading language, not a translation step: research the sources
  in whatever language they're actually in, then write the synthesis in the
  owner's. `title` stays exactly as the owner phrased their topic (it may
  legitimately be in a different language than today's `owner.language`
  if they asked for it earlier, in another language — never retranslate
  someone's own words). No `owner.language` at all (an install from before
  pt-intake started keeping it, or one where the owner has only ever
  written once) is the one case to fall back on the language the sourced
  notes themselves read most naturally in, never a hardcoded default.
- **3–6 sentences per body, every one traceable to a note.** If a claim is
  not backed by a note, cut the sentence.
- **`could_not_source` is per section, not global** — it belongs to the block
  it qualifies. Unsourced claims are named, not hidden.
- **`desk` is the newspaper department, and each one is its own page
  slot** — not a mixed sidebar. `"weather"` → `{{WEATHER}}`, `"calendar"` →
  `{{CALENDAR}}`, `"mail"` → `{{MAIL}}`, `"news"` (the default) →
  `{{SECTIONS}}`. Same title / headline / body / sources shape in every
  slot. The daily paper always includes weather and calendar from
  `run/desk-*/notes.json`. Mail only when `pt/config.json` has
  `mail.configured: true` **and** `run/desk-mail/notes.json` exists;
  otherwise omit the mail block entirely so that slot stays empty. A focused
  paper at another hour uses the same desks plus **only** the news topics
  this run researched (the sections whose `deliver_at` is that hour). Never
  compile a main-paper section into a noon paper, or the reverse. Owner
  `section` and `assignment` topics are always `"desk": "news"`. Do not put
  a news topic on the weather desk to make it look important.
- **Pagination is the renderer's job.** News that does not fit one Letter
  sheet continues on page 2+ of the PDF (WeasyPrint, `column-fill: auto`).
  Each desk box stays whole; if the rail itself overflows, the next desk
  starts on the following page. Never hand-split copy across pages.
- **`location` is this run's city** from the Latch location step, a string,
  optional. It is the dateline, not a stored profile: if location failed,
  omit the field.
- **`layout` is optional, `"main"` (the default) or `"sidebar"`.** Only news
  blocks honor it — a news story the owner wanted as a boxed panel. Standing
  desks ignore it; the renderer already puts them on the rail.
- **Never pad.** Three sourced sentences beat six where one is a guess. An
  empty pass (zero sourced claims) is still an edition: the title, one honest
  sentence ("nothing usable in the budget this time"), and what was tried.
  A thin weather or calendar desk is still printed; it is a department of
  the paper, not optional filler.

## Render and deliver

1. Run the renderer — it is the only thing that writes the edition. Always
   pass `--pdf`, writing under the run directory (e.g.
   `run/<id>/edition.pdf`). `--chat` is optional now (the chat transcript
   is not posted). Add `--html PATH` when a printer is configured:

       python3 /var/lib/hermes/skills/news/pt-edition/scripts/render_edition.py <edition.json> \
           --pdf run/<id>/edition.pdf
       # add --html PATH too when a printer is configured

   A malformed `edition.json` is refused by name. Fix it and re-run; never
   hand-assemble a page to route around the gate. If the renderer's own
   stderr says weasyprint is not installed, that costs only the PDF file —
   then post the chat text as the fallback (omit `--pdf`), do not write the
   edition by hand.
2. **Send the PDF yourself, by running `post_to_chat.py --pdf`, instead of
   returning the transcript as your final response.** The owner asked for
   the newspaper file, not the file plus the chat dump. `post_to_chat.py`
   with `--pdf` posts an empty body and the attachment — the same envelope
   plow-chat-platform uses for photo-only sends. Do not pipe
   `edition.chat.txt` into it:

       python3 /var/lib/hermes/skills/news/pt-shared/scripts/post_to_chat.py \
           --pdf run/<id>/edition.pdf

   Omit `--pdf` only when `render_edition.py` produced no PDF (weasyprint
   absent or the write failed) — then pass the chat text on stdin. Pointing
   `--pdf` at a file that does not exist is refused by name.
   `PLOW_API_BASE`, `PLOW_HOME_CHANNEL` and `PLOW_AGENT_TOKEN` come from the
   process environment already; nothing to pass for those.

   **Final response is `NO_REPLY` and nothing else.** The cron job still
   carries `--deliver`, and a final response that is the chat transcript
   would send the text a second time (or as a second message). `NO_REPLY`
   is the token the gateway already treats as silence. Never return the
   renderer’s chat output as the turn’s last line once the PDF has posted.
3. **Mark every topic the edition carried** from its `topic_id`:
   `/var/lib/hermes/skills/news/pt-intake/scripts/topics.py mark <id> --status delivered`. Do this
   only after the chat leg is out — a delivered mark on an undelivered
   edition is how a silent gap looks like a working paper. A section then
   goes back to `pending` for tomorrow's paper. An assignment stays
   `delivered` (terminal).
   - A `topics.py mark` that **refuses because the topic was cancelled while
     the run worked is expected, not an error**: the owner said stop at 6h20;
     the edition already left without it. Report it and carry on — do not
     crash the delivery over a valid cancellation.
   - **Never mark a standing desk.** Weather, calendar and mail have no
     topic id on purpose.
4. **If `pt/config.json` says `printer.configured: true`, hand the print leg
   to `pt-print`.** That leg is separate from the PDF the chat already
   carried in step 2 (Latch printing needs the HTML, not the PDF) and is the
   same class of best-effort: treat any failure as costing only the page.
   Neither the print leg nor a failed PDF ever blocks the chat edition or
   re-runs research.

## Repo note — the edition gate

The renderer validates `edition.json` structurally before emitting anything
(the same discipline `pt_config_gate.py` holds for the config): a bad shape
exits non-zero with the failing field named. A run that cannot render says so
and waits for the next cycle — it does not ship a half page.

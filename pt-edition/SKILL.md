---
name: pt-edition
description: Compile one or more topics' research notes into edition.json, render it with render_edition.py into the chat text, printable HTML and (when available) PDF, return the renderer's chat output verbatim as the final response, mark the topics it carried, and hand the print leg to pt-print when a printer is configured. Runs in the cron-fired session after pt-research.
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
  "sections": [
    { "kind": "section", "topic_id": "t_8c1d",
      "title": "Clima em Sao Paulo",
      "headline": "Chuva a tarde",
      "body": "3–6 sentences, every one traceable to a note.",
      "sources": ["https://…"],
      "could_not_source": ["…"] },
    { "kind": "assignment", "topic_id": "t_3f2a", "run_on": "2026-09-11",
      "title": "Valor do iPhone 15",
      "body": "…", "sources": ["https://…"],
      "tag": "especial para esta edição",
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
- **3–6 sentences per body, every one traceable to a note.** If a claim is
  not backed by a note, cut the sentence.
- **`could_not_source` is per section, not global** — it belongs to the block
  it qualifies. Unsourced claims are named, not hidden.
- **Never pad.** Three sourced sentences beat six where one is a guess. An
  empty pass (zero sourced claims) is still an edition: the title, one honest
  sentence ("nothing usable in the budget this time"), and what was tried.

## Render and deliver

1. Run the renderer — it is the only thing that writes the edition. Always
   pass `--pdf`, writing under the run directory (e.g. `--pdf
   run/<id>/edition.pdf`), not just `--html`:

       python3 /var/lib/hermes/skills/news/pt-edition/scripts/render_edition.py <edition.json> \
           --pdf run/<id>/edition.pdf
       # chat text on stdout; add --html PATH too when a printer is configured

   A malformed `edition.json` is refused by name. Fix it and re-run; never
   hand-assemble a page to route around the gate. If the renderer's own
   stderr says weasyprint is not installed, that costs only the PDF file —
   proceed with the chat text, do not treat it as a reason to write the
   edition by hand.
2. **The renderer's chat output is the final response, pasted verbatim, with
   one line prepended: `MEDIA:<absolute path to the PDF>`.** That line is not
   part of the edition's prose — it is the literal directive Hermes' delivery
   path (`cron/scheduler.py` on the `--deliver plow_chat:${PLOW_HOME_CHANNEL}`
   leg, the same `send_message` tool convention documented as "include
   MEDIA:<local_path> in the message") scans for, strips out, and turns into
   a native file attachment; nothing about the rendered text itself is
   paraphrased, reformatted or "improved". Skip the `MEDIA:` line only when
   `--pdf` produced no file (weasyprint absent or the write failed) — a
   `MEDIA:` line pointing at a file that does not exist is reported as a
   dropped attachment, not silently ignored, so never emit it speculatively.
   The promise is that the chat text and the printed page are the same
   edition, and a paraphrase breaks it. If the run has no deliver arm (a
   manual run), pipe the same text (with its `MEDIA:` line, if any) through
   `/var/lib/hermes/skills/news/pt-shared/scripts/post_to_chat.py` and report its output.
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

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
      "title": "Weather in Sao Paulo",
      "headline": "Rain in the afternoon",
      "layout": "sidebar",
      "body": "3–6 sentences, every one traceable to a note.",
      "sources": ["https://…"],
      "could_not_source": ["…"] },
    { "kind": "assignment", "topic_id": "t_3f2a", "run_on": "2026-09-11",
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
- **3–6 sentences per body, every one traceable to a note.** If a claim is
  not backed by a note, cut the sentence.
- **`could_not_source` is per section, not global** — it belongs to the block
  it qualifies. Unsourced claims are named, not hidden.
- **`layout` is optional, `"main"` (the default) or `"sidebar"`.** The
  printed page (HTML/PDF only — the chat text ignores it and lists every
  section in order regardless) puts every `"sidebar"` section in a boxed
  rail beside the two-column news, and everything else in that news column.
  Use it for the one section that should read as a fixed daily panel — the
  weather, say — not for whichever section happens to feel important today;
  no `"sidebar"` section at all is a normal, fully supported day and the
  rail just doesn't appear.
- **Never pad.** Three sourced sentences beat six where one is a guess. An
  empty pass (zero sourced claims) is still an edition: the title, one honest
  sentence ("nothing usable in the budget this time"), and what was tried.

## Render and deliver

1. Run the renderer — it is the only thing that writes the edition. Always
   pass both `--chat` and `--pdf`, writing under the run directory (e.g.
   `run/<id>/edition.chat.txt` and `run/<id>/edition.pdf`) rather than
   relying on stdout — step 2 needs the chat text as a file to pipe into
   `post_to_chat.py`:

       python3 /var/lib/hermes/skills/news/pt-edition/scripts/render_edition.py <edition.json> \
           --chat run/<id>/edition.chat.txt --pdf run/<id>/edition.pdf
       # add --html PATH too when a printer is configured

   A malformed `edition.json` is refused by name. Fix it and re-run; never
   hand-assemble a page to route around the gate. If the renderer's own
   stderr says weasyprint is not installed, that costs only the PDF file —
   proceed with the chat text, do not treat it as a reason to write the
   edition by hand.
2. **Send the edition yourself, by running `post_to_chat.py`, instead of only
   returning it as your final response.** Measured live, three separate real
   runs: the passive path (your final response getting picked up by
   `--deliver plow_chat:${PLOW_HOME_CHANNEL}` after the job finishes) is
   racy on this fleet — the same content, unchanged, has both delivered fine
   and been silently discarded with "fire claim ownership lost" in
   back-to-back runs. Asking you to call a tool mid-run instead
   (`send_message`) was tried and measured too: it does not reliably happen
   — two full research-and-render runs never called it, only ever returned
   a final response for the passive relay to gamble on. Running a script is
   not optional or forgettable the way remembering a tool call is — do it:

       python3 /var/lib/hermes/skills/news/pt-shared/scripts/post_to_chat.py \
           --pdf run/<id>/edition.pdf < run/<id>/edition.chat.txt

   The chat text goes on stdin from the file step 1 wrote — never retyped,
   never passed as a shell argument (an edition is web-derived content; argv
   is a surface another process could read). This is a plain HTTP call —
   declare the attachment, upload its bytes, post the message with it
   attached — verified live against the real API with no
   dependency on a connected live adapter or the cron scheduler's fire-claim
   machinery, the two things the other two paths both stood on. Omit `--pdf`
   only when `render_edition.py` produced no PDF (weasyprint absent or the
   write failed) — pointing `--pdf` at a file that does not exist is refused
   by name, not silently ignored, so never pass it speculatively.
   `PLOW_API_BASE`, `PLOW_HOME_CHANNEL` and `PLOW_AGENT_TOKEN` come from the
   process environment already; nothing to pass for those.

   Still also return that same text (with a `MEDIA:<path>` line prepended)
   as your final response — the explicit `post_to_chat.py` call is the
   reliable leg, the passive `--deliver` relay is a second, harmless attempt
   at the same content if it lands too; never a reason to send a different
   or shortened version through either path.
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

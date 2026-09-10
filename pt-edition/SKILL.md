---
name: pt-edition
description: Compile one or more topics' research notes into the formatted edition — a masthead, a headline and 3-6 sourced sentences per topic, and a Sources line — then deliver it in chat and hand the print leg to pt-print when a printer is configured. Runs in the cron-fired session after pt-research.
---

# pt-edition — notes become the edition

The edition is the product. Every rule here serves one idea: a reader on a
phone (or holding a printed page) gets a short, sourced answer, and nothing
in it is a guess.

## The chat format

One edition covers every topic delivered in this run — usually one; a
subscription batch may carry several.

```
THE PLOW TIMES — Sep 9, 2026

▸ What shipped in the new Anthropic API this week
  <3–6 sentence synthesis>
  Sources: <url>, <url>

▸ Best coffee shop near the Moscone Center right now
  <3–6 sentence synthesis>
  Sources: <url>
```

- **The masthead line is the date, in the owner's timezone**, from
  `pt/config.json` — not the container's clock reading past midnight.
- **The headline is the topic's text**, trimmed of pleasantries ("what's the
  wifi password situation at this venue" stays as-is; it is the owner's own
  words).
- **3–6 sentences, every one traceable to a note.** If a claim in a sentence
  is not backed by a note in `notes.json`, cut the sentence.
- **A "Sources" line per topic** — the URLs actually read, deduplicated.
- **Unsourced claims are named, not hidden.** When `could_not_source` has
  entries, one closing line per topic: "Couldn't source: <claim>." Same for
  blocked sources when they matter to the reader ("one paywalled source
  unread").
- **Never pad.** Three sourced sentences beat six where one is a guess. An
  empty pass (zero sourced claims) is still an edition: the headline, one
  honest sentence ("nothing usable in the budget tonight"), and what was
  tried — that is a working paper, not a failure to hide.

## Deliver

1. The final response of this session IS the chat edition. The cron row's
   `--deliver plow_chat:${PLOW_HOME_CHANNEL}` relays it — that is the chat
   leg; write nothing else after it.
2. If the run has no deliver arm (a manual run): pipe the edition through
   `../../pt-shared/scripts/post_to_chat.py` and report its output.
3. If `pt/config.json` says `printer.configured: true`, hand the print leg
   to `pt-print` — render the HTML, ship it, and treat every failure there
   as best-effort (see that skill). Printing never blocks the chat edition
   and never re-runs research.
4. Mark every topic in the batch delivered:
   `../../pt-intake/scripts/topics.py mark <id> --status delivered`. Do this
   only after the chat leg is out — a delivered mark on an undelivered
   edition is how a silent gap looks like a working paper. A subscription
   topic then goes back to `pending` on its next cycle per topics.py's
   transitions; you mark `delivered`, the scheduled run marks it back.

## The print format, in one paragraph (pt-print owns the rest)

The printed edition is the same content as a single-page HTML layout with a
masthead. **HTML-escape everything that came from the web before
interpolating it** — every quote, headline and source string goes through an
escaping step, never concatenated raw — and never emit `<script>` or `on*`
attributes anywhere: the same discipline ld-weather established for
feed-derived strings, because a researched page is untrusted input and the
page will be rendered on the owner's Mac.
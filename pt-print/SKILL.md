---
name: pt-print
description: Best-effort paper delivery — render the edition as a single-page HTML layout with a masthead and ship it to the owner's printer through Latch when pt/config.json says printer.configured. Called by pt-edition after the chat edition is out. Never a delivery requirement: every failure here ends with the chat edition as the outcome.
---

# pt-print — the paper edition, best-effort

**The chat edition is the contract; paper is the bonus.** Every step here is
best-effort: no failure in this skill blocks a delivery, re-runs research,
or delays the chat edition — it only costs the page.

## When to run at all

Read `pt/config.json`. If `printer.configured` is not exactly `true` — false,
null, absent, malformed — this skill is done before it starts. Say nothing
about printing in the edition; the chat edition is the whole delivery.

## Render the HTML — through the renderer, never by hand

The page is the renderer's output, not something this skill lays out:

    python3 /var/lib/hermes/skills/pt-edition/scripts/render_edition.py <edition.json> \
        --html ~/Plow/pt/edition-<date>.html

Same `edition.json`, same `template.html`, so the printed page is
byte-for-byte the same layout every day and shows exactly what the chat
edition showed. **Do not write HTML here and do not reformat the renderer's
page** — the whole reason the layout is code is that the model must never
assemble markup.

The escape discipline lives in `render_edition.py` now, and it is
load-bearing, not cosmetic: every web-derived string (headline, body, tag,
URL) is escaped once, in code, and the template carries no `<script>` and no
`on*` attribute. A researched page is untrusted input and this page renders
on the owner's Mac — and if the PDF ever falls back to Chrome headless, that
browser *executes* JavaScript, so the rule is the security boundary.

Keep the styling inline and asset-free (the template already is): the page
must print with no network at all.

## Ship it through Latch

The printer is on the owner's Mac, so the page is written there and printed
from there — exactly the two calls `pt-shared/references/latch-delivery.md`
lays out, held to its rules: paste both outputs verbatim, the print is not
done until `lp` exited 0, poll a returned handle to `ready`, and treat
`denied`/`failed`/`expired` as a failed step.

    1. plow_write_file  ~/Plow/pt/edition-<date>.html   content=<the HTML>
    2. plow_run_command argv=["lp","-d","<printer.name from config>","<abs path to that file>"]

`plow_run_command` runs argv directly — no shell, no `~` expansion; step 2's
path is the absolute path to the file step 1 just wrote, and `-d` gets the
exact CUPS name `pt-setup` probed.

## When it fails — and it is allowed to

Any failure — the Mac unreachable (the relay's unreachable-device error), the
write denied, `lp` non-zero, "no such printer" — ends the same way:

- the chat edition already delivered is the outcome; say nothing that
  implies the whole delivery failed,
- report one line in chat: "page not printed — <reason>; next scheduled run
  retries",
- do not retry in a loop, do not queue the page, do not re-run research to
  "fix" it. The next scheduled run recomposes and re-delivers on its own.

A printer that fails on every run is a config problem, not a print problem:
after the second consecutive failed run on a subscription, say the printer
may need re-probing (the pt-setup changing-one-setting path), once, and stop
mentioning it until the owner does something.
---
name: pt-shared
description: The helper library every pt-* skill imports — the pt-config gate, the bearer-HTTP helpers, the chat delivery POST and the Latch print reference. Not a task; nothing here is invoked on its own. Read the references when a skill's SKILL.md points at one.
---

# pt-shared — the pt-* skills' shared helpers

Every pt-* skill's scripts reach this directory by its absolute deploy path,
`/var/lib/hermes/skills/pt-shared/scripts` — every pt-* SKILL.md invokes
its sibling scripts that way now, not by a `../../` relative path off
whatever the terminal's cwd happens to be (measured live: `terminal.cwd` is
unset on this agent, defaulting to the Hermes install tree, so a relative
path off the calling skill's own directory never resolved and none of these
scripts ever ran). This skill still has to land beside its siblings in the
agent's skills store, and it carries a `SKILL.md` for the same reason
`ld-shared` does: the boot reconcile copies a bundled directory into the home
only when it carries one, and without this file the producers seed and this
does not, and every run fails on the import.

- `scripts/pt_config_gate.py` — the single definition of a valid `pt/config.json`;
  prints failing invariant names, empty stdout is pass
- `scripts/setup_needed.py` — live-chat first-run gate: prints `SETUP_NEEDED`
  or `READY` (missing file is needed)
- `scripts/record_setup.py` — the ONLY way `pt-setup` writes
  `.setup-draft.json`. Call it bare, space-separated, never through an
  interpreter: `record_setup.py <config.json path> key=value [key=value …]`.
  Dotted keys nest; `true`/`false` (any case) become real JSON booleans;
  every other value is kept verbatim as a string, so a dotted or underscored
  value needs no quoting — only a value containing a space does. Prints
  `DRAFT:<fields recorded, or "none">` then
  `NEXT_QUESTION=<hour|printer|priority|mail|news|close>`; that second line — never
  the draft's shape, never the chat thread — decides what `pt-setup` asks
  next. Called as `record_setup.py <config.json path> --done` it instead
  **clears** the draft (prints `DRAFT:cleared`) — the close step's last
  act, and the only supported way to delete `.setup-draft.json`. It is
  idempotent and refuses an unfinished interview. **This bullet is the contract: it exists so no run ever has to open
  the script to find out how to call it.**
- `scripts/bearer_http.py` — one bearer JSON call that never follows a redirect
  (a forwarded Authorization header is the credential walking to a host the API
  did not authenticate)
- `scripts/post_to_chat.py` — the edition's chat leg: POST the PDF (empty
  body) to the owner's home channel, or the chat text if there is no PDF
- `scripts/textnorm.py` — library only (imported by `pt-priority` history and
  validation). Normalizes owner text so quotes and similar priorities compare
  without punctuation; never invoked as a CLI.
- `pt-priority/scripts/parse_priority_file.py` — split the owner's
  prioritization file into typed sections. Called bare:
  `/var/lib/hermes/skills/pt-priority/scripts/parse_priority_file.py <raw.md> <out.json>`
  Prints `FILE:<ok|missing|empty> SECTIONS:<n>`. A missing raw file is status
  `missing`, never a crash.
- `pt-priority/scripts/day_shape.py` — today's free windows from the calendar
  desk's `events.json`. Called bare:
  `/var/lib/hermes/skills/pt-priority/scripts/day_shape.py free-blocks <events.json> <out.json> --tz <IANA> [--now <ISO8601>]`
  Prints `DAY:ok BLOCKS:<n>` or `DAY:invalid` followed by one failure per line.
- `pt-priority/scripts/build_context.py` — assemble `run/desk-priority/context.json`
  from the parsed file, calendar events, free blocks and recent history. Called
  bare:
  `/var/lib/hermes/skills/pt-priority/scripts/build_context.py --run-dir <dir> --tz <IANA> [--now <ISO8601>]`
  Prints `CONTEXT:ok STAGE:<stage> NOTES:<list|none>` or `CONTEXT:nothing`.
- `pt-priority/scripts/validate_priority.py` — refuse a priority the owner could
  not trace to their file or calendar. Called bare:
  `/var/lib/hermes/skills/pt-priority/scripts/validate_priority.py --run-dir <dir>`
  Prints `VALID` (and stamps notes into `priority.json`) or `INVALID` followed
  by one error per line.
- `pt-priority/scripts/history.py` — recent priorities and whether they got
  done. Called bare:
  `/var/lib/hermes/skills/pt-priority/scripts/history.py today --date YYYY-MM-DD`
  `/var/lib/hermes/skills/pt-priority/scripts/history.py record --date YYYY-MM-DD --priority-json <priority.json>`
  `/var/lib/hermes/skills/pt-priority/scripts/history.py set --date YYYY-MM-DD --status done|skipped`
  Prints `TODAY:…`, `RECORDED`, or `STATUS:…`.
- `pt-priority/scripts/parse_advisors.py` — type the advisor library the desk
  gathered. Called bare:
  `/var/lib/hermes/skills/pt-priority/scripts/parse_advisors.py <dir-listing.json> <out.json>`
  The listing is `{"files":[{"name","text"}]}`. Prints `ADVISORS:<n> ERRORS:<n>`.
  A file without frontmatter is an error, never a crash.
- `pt-priority/scripts/infer_stage.py` — company stage from the parsed
  prioritization file. Called bare:
  `/var/lib/hermes/skills/pt-priority/scripts/infer_stage.py <file.json> <out.json>`
  Prints `STAGE:<stage> MODIFIERS:<list|none>`. Never infer a stage by hand.
- `scripts/run_lock.py` — one exclusive run per name with stale takeover, so
  two daily-paper runs can never race and deliver a hollow edition.
  Called bare, never through an interpreter:
  `/var/lib/hermes/skills/pt-shared/scripts/run_lock.py acquire --name NAME [--stale-minutes N]`
  and the matching `.../run_lock.py release --name NAME`. Prints one word
  (`acquired` / `stale-takeover` / `held`) and always exits 0 on acquire.
- `references/config.example.json` — the config contract `pt_config_gate.py`
  enforces (including the optional `delivery.lead_minutes`, default 0, and
  optional `mail.configured`, default off)
- `references/latch-delivery.md` — how the printed edition reaches the owner's
  printer over Latch (`print_edition.py` is the handoff; this file is the
  contract that script holds to)

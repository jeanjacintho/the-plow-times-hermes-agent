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
- `scripts/bearer_http.py` — one bearer JSON call that never follows a redirect
  (a forwarded Authorization header is the credential walking to a host the API
  did not authenticate)
- `scripts/post_to_chat.py` — the edition's chat leg: POST the PDF (empty
  body) to the owner's home channel, or the chat text if there is no PDF
- `scripts/run_lock.py` — one exclusive run per name with stale takeover, so
  two daily-paper runs can never race and deliver a hollow edition
- `references/config.example.json` — the config contract `pt_config_gate.py`
  enforces (including the optional `delivery.lead_minutes`, default 0, and
  optional `mail.configured`, default off)
- `references/latch-delivery.md` — how the printed edition reaches the owner's
  printer over Latch (the print path's "NOT DELIVERED" sheet)

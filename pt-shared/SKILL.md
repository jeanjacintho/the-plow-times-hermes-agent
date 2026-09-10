---
name: pt-shared
description: The helper library every pt-* skill imports — the pt-config gate, the bearer-HTTP helpers, the chat delivery POST and the Latch print reference. Not a task; nothing here is invoked on its own. Read the references when a skill's SKILL.md points at one.
---

# pt-shared — the pt-* skills' shared helpers

Every pt-* skill's scripts reach this directory as a sibling —
`../../pt-shared/scripts` off their own realpath — so it has to land beside
them in the agent's skills store. It carries a `SKILL.md` for the same reason
`ld-shared` does: the boot reconcile copies a bundled directory into the home
only when it carries one, and without this file the producers seed and this
does not, and every run fails on the import.

- `scripts/pt_config_gate.py` — the single definition of a valid `pt/config.json`;
  prints failing invariant names, empty stdout is pass
- `scripts/bearer_http.py` — one bearer JSON call that never follows a redirect
  (a forwarded Authorization header is the credential walking to a host the API
  did not authenticate)
- `scripts/post_to_chat.py` — the edition's chat leg: POST the text to the
  owner's home channel over the Plow API
- `references/config.example.json` — the config contract `pt_config_gate.py`
  enforces
- `references/latch-delivery.md` — how the printed edition reaches the owner's
  printer over Latch (the print path's "NOT DELIVERED" sheet)
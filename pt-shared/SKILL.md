---
name: pt-shared
description: The helper library every pt-* skill imports — the pt-config gate, the bearer-HTTP helpers, the chat delivery POST, the owner's wiki and the Latch print reference. Not a task; nothing here is invoked on its own. Read the references when a skill's SKILL.md points at one.
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
  then `DRAFT:` and `LANG:`, or `READY` then `LANG:` (from `pt/config.json`;
  missing file is needed)
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
- `scripts/record_owner_language.py` — the ONLY way live chat updates
  `owner.language` after (and during) setup. Bare:
  `record_owner_language.py <config.json path> English`. Prints `LANG:<language>`.
  Setup-unfinished → draft; `READY` → `pt/config.json`. Skip only on a
  lone `yes`/`y`/`ok`/`okay`/`sim`/`no`/`não`/`nao`. **This bullet is the contract.**
- `scripts/reconcile_pt_skills.py` — agent-mgr skill seed. Bare:
  `reconcile_pt_skills.py <AGENT_HOME>`. Updates a pt-* copy whose
  content still matches the last origin stamp; keeps a copy the agent
  edited. Unstamped dirs are re-seeded once (old hook). **This bullet is
  the contract.**
- `scripts/bearer_http.py` — one bearer JSON call that never follows a redirect
  (a forwarded Authorization header is the credential walking to a host the API
  did not authenticate)
- `scripts/latch_mcp.py` — the one MCP session with the owner's Mac
  (`connect()`, `LatchClient.call_tool` (one stateless request, pending
  handles settled), `LatchError`). A failure raises `LatchError`; the caller
  names what did not happen. The print leg and the wiki scripts both use it.
- `scripts/wiki.py` — the paper's pages in the owner's wiki (`~/Plow/wiki`, plow-wiki):
  the root `projects/theplowtimes` (writer `theplowtimes`), the shared
  `entities/owner/goals.md`, and the OKF page format.
- `scripts/wiki_setup.py` — make `~/Plow/wiki` ready for the paper. Bare:
  `wiki_setup.py` or `wiki_setup.py --desk`. Creates the wiki with `wiki init` when
  the Mac has none, writes the paper's schema and page when absent, declares
  `projects/theplowtimes` in `wiki.toml` (appending; no other root is touched), and
  with `--desk` the goals page and the desk's page, carrying an older install's notes
  file and desk page over once. Prints `WIKI:ready` or `WIKI:set up …`;
  `error: wiki not ready — …` exits non-zero. **This bullet is the contract.**
- `assets/wiki/` — the seeds `wiki_setup.py` writes: the root's schema (fields and the
  Editions / Your advisors tables), the paper's page, the goals page, the desk's page.
- `scripts/post_to_chat.py` — the edition's chat leg: POST the PDF (empty
  body) to the owner's home channel, or the chat text if there is no PDF.
  `--filename The-Founder-Times-<date>.pdf` is the name shown in chat (the
  run file stays `edition.pdf` on disk). A successful `--pdf` POST stamps
  `seal_chat_session.py` and then runs `print_edition.py` when the printer
  is configured (best-effort; a print failure does not undo the chat).
- `scripts/seal_chat_session.py` — write the stamp (also called by
  `chat_status.py --soon`). Not a chat message. The gateway pin rotates
  plow_chat on `agent:end`.
- `scripts/chat_status.py` — live wait lines. Bare:
  `chat_status.py --soon` once before research; `chat_status.py --wait`
  after desks/topics (no-ops until a few minutes have passed, then posts
  once); `chat_status.py --busy` during pt-setup Latch/Mac work (hang-on,
  then one "still on it", never a play-by-play; does not seal the
  session). Cron never calls it.
- `pt-priority/scripts/history.py recent` — the cards the desk printed on the last 7 days, read
  from the wiki's edition pages; prints `[{"date", "desk"}]`.
- `pt-edition/scripts/record_edition.py <edition.json>` — the delivered edition onto the day's
  page in the wiki, then `wiki validate` + `wiki index`.
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

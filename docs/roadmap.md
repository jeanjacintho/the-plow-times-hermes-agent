# Roadmap

## MVP — must work for the hackathon demo

Everything in the design doc's §3 skills list, at the minimum needed for
`docs/demo-script.md`'s two beats to work:

- [ ] `pt-setup` — timezone + delivery hour interview, printer probe.
- [ ] `pt-intake` — classify a chat message into a topic (kind + depth),
      write `topics.json`, schedule the right cron.
- [ ] `pt-research` — budget-bounded Latch browsing, sourced notes.
- [ ] `pt-edition` — chat-formatted edition (HTML edition can ship after
      chat-only works end to end — see below).
- [ ] `pt-dashboard` — cron registration for subscriptions + one-time jobs.
- [ ] "list my topics" / "stop watching X" as chat-level intents in
      `pt-intake` (flagged in the design doc's open questions as small
      enough to fold into MVP — a judge will ask how to turn it off).
- [ ] One subscription topic, created and delivered successfully at least
      once unattended, before demo day — the whole point is proving it
      works with nobody watching.

## MVP, second priority — makes the demo better but isn't load-bearing

- [ ] `pt-print` — HTML edition + Latch `lp` delivery. The chat edition
      alone is a complete demo; printing is the memorable bonus, not the
      contract. Build it once the chat path is solid, not before.
- [ ] Agent Index registration (`docs/leaderboard-submission.md`) — needs a
      working demo to record before it can happen at all, so it's
      naturally last.

## Explicitly deferred (stretch / post-hackathon)

- **Hosted one-click deploy.** A page a stranger opens with no shell access
  and no `agent-mgr` on their own machine — the real equivalent of
  `newspaper.karenx.com`. Needs infrastructure this ecosystem doesn't have
  yet (see `leaderboard-submission.md`'s honesty note); not attempted for
  the hackathon window.
- **Group chat / multi-owner trust.** `life-assistant-hermes-agent`'s trust
  model (trusted lines, group prompts) is real complexity earned by a
  shared-household use case. The Plow Times has no shared-household use
  case at MVP — one owner, one private chat — so it's not worth building
  ahead of a request for it.
- **A plain-text print fallback layout** for printers that render the HTML
  edition badly — noted in the design doc's open questions, deferred until
  a real print test surfaces whether it's actually needed.
- **Non-web sources** (e.g., reading the owner's own documents, connected
  accounts) — out of scope; the whole pitch is "researches the open web on
  your behalf," not another connectors integration.
- **Editable delivery templates / masthead customization.** Fun, not what
  wins a hackathon judge's attention in the first 90 seconds.

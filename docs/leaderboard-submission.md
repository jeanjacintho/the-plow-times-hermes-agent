# Leaderboard submission plan

Target: [aiworthusing.com/agent-index](https://aiworthusing.com/agent-index),
via `plow-pbc/agent-index-client` — the same index the Builder Index client
reads, where an agent's card carries a video, a blurb, an image, and its
day-by-model token usage.

## What "one-click deployable" honestly means here

Karen Cheng's version is a hosted page (`newspaper.karenx.com`) a stranger
opens and is running in minutes with no local setup. Plow's ecosystem
doesn't have that hosting layer today — `agent-mgr` runs on a machine
someone owns. So "one-click" for this hackathon submission means the
closest honest equivalent: **one repo, one command sequence, no code
edits**, the same bar `life-assistant-hermes-agent` and
`property-hunt-hermes-agent` already hit:

```sh
agent-mgr register plowtimes ~/services/the-plow-times-hermes-agent
agent-mgr deploy plowtimes
agent-mgr activate plowtimes      # owner texts the code back
agent-mgr up plowtimes
agent-mgr sign-in plowtimes
```

No `pt/config.json` to hand-edit before first run — `pt-setup` writes it
from a chat interview, the same pattern `ld-setup` uses. That's the bar to
hit before submission: a fresh checkout, these five commands, one text
exchange, and the owner is asking it questions.

Closing the gap to an actual hosted one-click experience (a page that spins
up an instance without anyone touching a shell) is out of scope for the
hackathon window — noted as future work in `roadmap.md`, not promised in
the submission.

## Registration steps (`agent-index-client`)

1. `curl` the standalone client, same as any agent-index registration
   (see `agent-index-client`'s README for the exact one-liner).
2. `--register --agent plowtimes --name "The Plow Times" --blurb "..."` —
   blurb draft below.
3. `--login` once (GitHub device flow) to bind a reporting key.
4. Record the demo video (see below), upload it, get the YouTube video id,
   re-run registration with `--video <id>`.
5. `--image` pointing at a screenshot of a delivered edition (chat view),
   not a generic logo — the card should show the product, not a brand mark.
6. Run on a schedule so usage keeps reporting; not a one-time submission.

## Blurb draft

> Text it any question. It researches with your own Mac's browser, on a
> time budget, and hands back a sourced brief — in chat, and on paper if
> you've got a printer nearby. Ask it to keep watching something and it
> does the same thing again every night while you sleep.

(Under the usual index length constraints — trim further once the actual
field limit is confirmed against the client's `--register` validation.)

## Demo video plan

60–90 seconds, screen-recorded, mirroring `docs/demo-script.md`'s two-beat
structure:

1. (0:00–0:20) Text it a real question live, on screen. Cut to it landing.
2. (0:20–0:45) Show a browser tab actually navigating on its own during the
   research pass — the "it's really doing this" shot, the same beat that
   made Karen Cheng's clip work.
3. (0:45–1:10) Show an overnight subscription edition that was waiting in
   the morning, plus the printed page if available.
4. (1:10–end) One line on how to stand up your own — pointing at this repo.

## Open questions

- Exact field limits and required fields for `--register` — read off the
  client's own `--help` / README before drafting the final blurb, don't
  guess at the character budget.
- Whether the video should be hosted unlisted on YouTube under a personal
  or a project account — a submission-time decision, not a design one.

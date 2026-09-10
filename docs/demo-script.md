# Demo script

Goal: make a judge feel the same thing Karen Cheng's tweet made 845K people
feel in 15 seconds — "wait, it just... did that on its own?" — without
betting the whole demo on a live web-research pass finishing inside the
judging window.

## The two-beat structure

**Beat 1 — live, in front of them (quick tier).** Ask it something nobody
primed, on the spot: "what's the wifi password situation at this venue" or
literally whatever the judge suggests. Text it from the phone. While it
runs (a couple of minutes, budget-bounded per the design doc's §3), talk
through what's happening: it's driving a real browser on a real Mac right
now, not calling a search API. Show the edition land in the chat.

**Beat 2 — the one baked overnight (deep tier).** Before the demo slot,
subscribe it to something genuinely relevant to the judges or the event the
night before — a deep-tier edition it produced on its own while you slept —
and show that edition already sitting in the chat, plus the printed page
if a printer was reachable. This is the "morning newspaper" beat: proof it
works unattended, at depth, without you standing over it.

Beat 2 must never depend on beat 1 succeeding live — it's baked in advance
specifically so a flaky venue network or a blocked page during Beat 1 can't
sink the whole demo.

## Before you're on stage

- [ ] A subscription topic created the night before, confirmed delivered
      (check the chat, not just that the cron fired).
- [ ] Printer test run once, that same morning, with the actual demo
      printer if one will be on the table — not assumed from `pt-setup`'s
      earlier probe, which may be stale.
- [ ] A `quick` topic dry-run within the last hour, timed, so you know the
      real wait before asking the judge to watch one live.
- [ ] A fallback edition (any topic, already delivered) pulled up in the
      chat, in case Beat 1 fails at the worst possible moment — "here's one
      it did earlier" beats standing there watching it hang.

## What to say, roughly

1. "This is texted like any other iMessage contact — no app to open."
2. Ask it something live. Name what's happening while it works: "it's
   driving my Mac's browser right now, reading real pages, not hitting a
   search API."
3. Show the live answer land, with sources.
4. Pivot to the overnight one: "and this is one it did on its own last
   night, with nobody watching" — show the chat edition, then the printed
   page if you have one.
5. Close on the leaderboard angle if relevant: "it's one command to stand
   up your own" — see `leaderboard-submission.md`.

## Timing budget

Assume 90 seconds total stage time is realistic for a hackathon table demo.
Beat 1's live wait is the variable cost — if the last dry run took longer
than ~45 seconds, lead with Beat 2 instead and treat Beat 1 as something you
offer only if there's time left.

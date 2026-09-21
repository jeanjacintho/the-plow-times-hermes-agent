# Manual checks

## E2E priority desk

Needs Latch on the Mac. Until a human run, **NEEDS HUMAN RUN**.

| # | Action | Expected |
| --- | --- | --- |
| 1 | New setup (`docker compose down -v`, "oi") | Questions in order: hour, printer, **priority** (the goal question), mail, sections. Slow Latch/file steps post ⏳ hang-on (`chat_status.py --busy`), never a play-by-play |
| 2 | Answer the goal question | Creates `~/Plow/wiki/entities/owner/goals.md` with the answer under `## Goals` (creating `~/Plow/wiki` if absent); `projects/theplowtimes` is declared in `wiki.toml` |
| 3 | Check `pt/config.json` | `priority.configured: true` (no file) |
| 4 | Deploy the reviewed head, then replay the real cron (`hermes cron run pt-daily-edition`) | The session completes without loading `pt-priority` more than once; `tournament.json`, `edition.json`, and the delivered PDF exist; the card has exactly three ranked recommendations, each with evidence, a first step, and a verified named-advisor citation |
| 5 | Run again the next day | Yesterday's three delivered recommendations enter as generation zero and can only be replaced by fully criticized challengers that beat them |
| 5b | Open ~/Plow/wiki/projects/theplowtimes/editions/<today>.md after the paper is delivered | All three recommendation essays, ranked questions, and their source URLs are archived; nothing is recorded for a paper that failed to deliver |
| 6 | Text "stop telling me to hire" | A dated line lands under `## Not now`; the next paper does not advise hiring |
| 7 | Deny the iMessage read on the Mac and run | Paper still ships; the desk works from calendar and mail |
| 8 | Rename the file on the Mac and run again | `wiki_setup.py --desk` re-seeds `goals.md` — empty, or carried over from `~/Plow/prioritization.md` if that file still exists; the rest of the paper is normal |
| 9 | Close Latch and run | Desk marks `unavailable`; the paper is still delivered |

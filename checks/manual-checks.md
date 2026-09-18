# Manual checks

## E2E priority desk

Needs Latch on the Mac. Until a human run, **NEEDS HUMAN RUN**.

| # | Action | Expected |
| --- | --- | --- |
| 1 | New setup (`docker compose down -v`, "oi") | Questions in order: hour, printer, **priority**, mail, sections. Slow Latch/file steps post ⏳ hang-on (`chat_status.py --busy`), never a play-by-play |
| 2 | Priority question | If `~/Plow/prioritization.md` is missing, creates it from the template **before** asking; then asks yes/no with the path. Yes → `priority.configured: true`. No → configured false; file stays. Seeds `~/Plow/advisors/` on yes if missing |
| 3 | Fill the file: company state, goals, 1 deadline, 3 pieces of advice, one rule | — |
| 4 | Check `pt/config.json` | `priority.configured: true`, `priority.file` |
| 5 | Force the edition (`hermes cron run pt-daily-edition`) | The page opens with the priority; the "why" cites the file and the calendar |
| 6 | Check `run/desk-calendar/events.json`, `stage.json`, `advisors.json` and `context.json` | Shapes from the plan; `STAGE:` matches `## Company state`; only this stage's advisors in context |
| 6b | Check the page | Line `STAGE · …`, a why citing the advisor, `NOT TODAY` block |
| 6c | Change `## Company state` to ARR $14M and run again | Stage becomes Scale; priority and `NOT TODAY` switch advisor files |
| 6d | Delete `~/Plow/advisors/` and run | Paper still ships; priority from file + calendar; note `no_advisor_for_stage` |
| 7 | "why?" in chat | Explains with the quotes, does not decide again |
| 8 | "done" | Confirms; the next day the priority does not repeat without a reason |
| 9 | Rename the file on the Mac and run again | Page ships without the priority block (or with the notice); the rest of the paper is normal |
| 10 | Close Latch and run | Desk marks `unavailable`; the paper is still delivered |

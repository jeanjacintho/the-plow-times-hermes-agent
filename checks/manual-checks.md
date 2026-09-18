# Manual checks

## E2E priority desk

Needs Latch on the Mac. Until a human run, **NEEDS HUMAN RUN**.

| # | Action | Expected |
| --- | --- | --- |
| 1 | New setup (`docker compose down -v`, "oi") | Questions in order: hour, printer, **priority**, mail, sections |
| 2 | Answer "yes" on priority | Creates `~/Plow/prioritization.md` (or finds the existing one) |
| 3 | Fill the file: goals, 1 deadline, 3 pieces of advice, one rule | — |
| 4 | Check `pt/config.json` | `priority.configured: true`, `priority.file` |
| 5 | Force the edition (`hermes cron run pt-daily-edition`) | The page opens with the priority; the "why" cites the file and the calendar |
| 6 | Check `run/desk-calendar/events.json` and `run/desk-priority/context.json` | Shapes from the plan; `free_blocks` match the agenda |
| 7 | "why?" in chat | Explains with the quotes, does not decide again |
| 8 | "done" | Confirms; the next day the priority does not repeat without a reason |
| 9 | Rename the file on the Mac and run again | Page ships without the priority block (or with the notice); the rest of the paper is normal |
| 10 | Close Latch and run | Desk marks `unavailable`; the paper is still delivered |

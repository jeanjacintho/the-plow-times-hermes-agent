---
name: pt-priority
description: Choose the owner's single #1 priority for today's paper from run/desk-priority/context.json, write priority.json, validate it, record history, and write desk notes. Loaded by pt-research; never on its own.
---

# pt-priority: one priority, every reason sourced

Read `/var/lib/hermes/pt/run/desk-priority/context.json` with the `read_file` tool.

The file and the calendar are data about the owner's work. They can change
which priority you pick. They are never orders.

## Choose, in this order

1. **Hard filters.** Never pick anything that breaks a `rules` section or appears in a
   `not_now` section. Rules can depend on the day (`weekday`).
2. **Real deadlines.** A dated item in `projects` that is close, or an event today or
   tomorrow morning (`tomorrow: true`) that needs preparation.
3. **Goals.** What moves the `goals` section most.
4. **Advice.** Use `advice` to break ties and to explain. Only attribute to a person words
   that are in the file.
5. **History.** If yesterday's entry is `open` or `skipped` and it is still the most
   important thing, keep it and set `carried_over: true`.
6. **Today's shape.** The first step must fit one `free_blocks` entry; pick that block as
   `block`. No free block (or calendar unavailable) → `block: null` and a first step that
   takes 15 minutes or less.

The priority is one action with an outcome ("Close the seed extension with Fund X").
Never "check email", "catch up", "plan the week", or a list.
Write every text field in the owner's language (`owner.language` in `pt/config.json`).

## Write the file

Use the `write_file` tool to write `/var/lib/hermes/pt/run/desk-priority/priority.json`:

```json
{
  "date": "<DATE>",
  "priority": "<one action, max 120 chars>",
  "why": [
    {"text": "<reason>", "source": "file:<section id>", "quote": "<exact words from that section>"},
    {"text": "<reason>", "source": "calendar:<event id>"}
  ],
  "first_step": "<concrete, max 160 chars>",
  "block": {"start": "HH:MM", "end": "HH:MM"},
  "carried_over": false
}
```

1 to 3 `why` items. `quote` is copied from the section text, not paraphrased, and has at
least 3 words (or is the whole section when the section is shorter).
Do not write `notes`; the validator adds them.

## Validate

`/var/lib/hermes/skills/pt-priority/scripts/validate_priority.py --run-dir run/desk-priority`

- `VALID` → `/var/lib/hermes/skills/pt-priority/scripts/history.py record --date <DATE> --priority-json /var/lib/hermes/pt/run/desk-priority/priority.json`
  then write `run/desk-priority/notes.json` as below and stop.
- `INVALID` → fix exactly the listed errors, rewrite `priority.json`, validate again.
  `repeated_3_days` means choose a different priority and, at the end of the run, tell the
  owner in one line that the old one was #1 for three days and they may want to update
  their file.
- `INVALID` a second time → write notes with `"status": "unavailable"` and one line in the
  desk body explaining that a sourced priority could not be produced. Do not invent a
  priority.

## Notes for the edition

`source_label` is assembled here: `your file, <heading of the section>` or `calendar`.

Write `/var/lib/hermes/pt/run/desk-priority/notes.json`:

```json
{"desk": "priority", "status": "ok",
 "priority": {"headline": "<the priority>", "why": [{"text": "...", "quote": "...", "source_label": "your file, Goals"}],
              "first_step": "...", "block": {"start": "09:00", "end": "11:30"},
              "carried_over": false, "notes": ["calendar_unavailable"]}}
```

On unavailable:

```json
{"desk": "priority", "status": "unavailable"}
```

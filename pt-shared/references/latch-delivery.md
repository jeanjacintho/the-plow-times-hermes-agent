# Latch delivery — when the printed edition has to go through the Mac

The printer sits on the owner's Mac (`lp` targets CUPS there), and this
container has no printer of its own — so when `pt/config.json` says
`printer.configured: true`, `pt-print` ships the edition HTML through Latch:
the same "reach the owner's machine, never this container" pattern every
Latch-using skill draws. The Mac authorises each action; that is the point.

The handoff is two calls, in this order and nothing else. Paths under
`~/Plow` auto-approve on the Mac, which is why the HTML is written there.

    1. mcp__plow__plow_write_file  path=~/Plow/pt/edition-<date>.html  content=<the HTML>
    2. mcp__plow__plow_run_command argv=["lp","-d","<printer name>","/Users/<user>/Plow/pt/edition-<date>.html"]

`plow_run_command` takes an **argv array and runs it directly — there is no
shell**. `~` is never expanded, so step 2's path is the real absolute path to
the file step 1 just wrote. No token is involved: `lp` talks to the Mac's own
CUPS, so unlike the kiosk handoff there is no header file to read.

**The print is not done until step 2 exited 0.** A CUPS job id in its output
is the receipt; paste both outputs verbatim. Any other exit — `lp: unable to
print file`, `no such printer`, a deny on the Mac — is a failed step: say so
and stop; do not pretend the page printed.

**A `{"status":"pending","handle":…}` answer is not a result.** Either call
outruns the Mac's 15-second budget when Latch's review ahead of exec takes
its time; the call keeps running and hands back a handle. Poll
`mcp__plow__plow_get_result handle=<that handle>` about once a second until
its `status` is `ready`, and read its `result` as the answer the original
call would have given — the write's confirmation, or lp's exit — held to the
same zero-exit rule above. `denied`, `failed`, `expired` or `unknown` is a
failed step: say so and stop.

## Printing is best-effort, never a delivery blocker

The chat edition is the contract; paper is the bonus. Every failure above —
no printer configured, write refused, lp non-zero, the Mac asleep or Latch
not running (the relay's unreachable-device error) — ends the same way: the
chat edition already delivered is the outcome. Do not retry in a loop and do
not queue the page: report in chat, in these words — "Mac unreachable, page
not printed; next scheduled run retries" — and end the run. The next
scheduled run recomposes and re-delivers on its own.
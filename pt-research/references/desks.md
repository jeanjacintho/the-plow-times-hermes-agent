# Standing desks — how the daily paper fills weather, calendar and mail

These are not topics. They are fixed newspaper departments. The daily run
always fills weather and calendar. Mail joins only when `pt/config.json`
has `"mail": { "configured": true }`. Notes go under
`/var/lib/hermes/pt/run/desk-<name>/notes.json` (same shape as a topic
notes file, `topic_id` omitted). pt-edition compiles them with
`"desk": "weather"|"calendar"|"mail"`. Never mark them in topics.py.

Every Latch call is the same two tools the print path uses:
`plow_run_command` (argv array, no shell, no `~`) and, when a call returns
`{"status":"pending","handle":…}`, `plow_get_result` until `ready`. A
401/412/deny is one blocked source: log it, do not retry.

## 1. Location, then weather — every daily run

Do not ask the owner for a city and do not write one into config. Read it
from the Mac this run, through Latch.

1. Write `~/Plow/pt/location.py` with `plow_write_file` (paths under `~/Plow`
   auto-approve). The script should print one JSON object
   `{"city":"…","region":"…","country":"…"}` and nothing else.
   Prefer CoreLocation if a helper exists; otherwise the Mac's own public IP
   (curl from the Mac, never from this container — the container's IP is
   not the owner's):

       import json, urllib.request
       data = json.load(urllib.request.urlopen("https://ipapi.co/json/", timeout=8))
       print(json.dumps({
         "city": data.get("city") or "",
         "region": data.get("region") or "",
         "country": data.get("country_name") or "",
       }))

2. Run it: `plow_run_command` argv
   `["/usr/bin/python3", "/Users/<user>/Plow/pt/location.py"]`
   (`~` is not expanded). The city string is this edition's `location`.
3. Open the browser and source today's forecast for that city (weather.gov,
   INMET, AccuWeather — whatever actually covers it). Same budget rules as
   any quick section: 3–5 sources, stop. Notes at `run/desk-weather/notes.json`.
   Source URLs are the forecast pages. If location failed, still write the
   notes file with `could_not_source` naming the miss; do not invent a city.

## 2. Calendar — every daily run

Read-only. Today's events, then the next few days. Write
`~/Plow/pt/calendar.applescript` (or a small Python+EventKit helper) and run
it through `plow_run_command`. Calendar.app AppleScript is enough:

    tell application "Calendar"
      -- list today's events (title, start, calendar name)
      -- then events from tomorrow through +7 days
    end tell

Print a tight, sourced list the edition can turn into two paragraphs
("Today: …" / "Upcoming: …"). Source label: `Calendar.app` (plain text, not
a URL). If Calendar is locked or empty, say so in `could_not_source` /
body; never invent a meeting. Notes at `run/desk-calendar/notes.json`.

## 3. Mail — only when configured

Read `pt/config.json`. If `mail.configured` is not exactly `true`, skip this
desk entirely — no notes file, no edition block.

When it is true: Mail.app, read-only, today's messages (sender, subject,
date — not full bodies). Same Latch write-then-run pattern. Source label:
`Mail.app`. A deny or empty inbox is an honest letters column, not a
retry loop. Notes at `run/desk-mail/notes.json`.

## Close

These Latch calls share the Mac with the browser pass. Do location and
calendar (and mail if on) first, then the news topics, then
`plow_browser_close` as pt-research already requires.

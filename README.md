# The Founder Times (inspired by Mayfield)

Your morning paper, printed. It researches on your Mac and puts a sourced page in the tray — PDF in chat if you’d rather.

A [Hermes](https://howto.plow.co/hermes) agent on [Plow Chat](https://howto.plow.co/). You text it like a newspaper, not like a chatbot. It is one person’s paper: the sections you asked for, at the hour you named, in the language you write.

## What it is

The product is a **page**. It can open with **what Patrick Salyer would tell
you** after watching your last day, learned from your Mac, then weather,
calendar, optional mail, and the stories you told it to cover, laid out as a
newspaper and sent to a printer on your Mac when one is there. The same edition can land as a PDF in the chat
if you would rather not print.

You do not fill a profile. The first message is the paper: what time it should arrive. It learns your timezone from where the Mac is; it does not interview you for a name.

Research runs on **your** browser, through [Latch](https://howto.plow.co/latch). Every claim in the edition carries a source. If a page cannot be read, the paper says so — it does not invent the paragraph.

What it learns and prints goes into your wiki at `~/Plow/wiki` (Latch's Obsidian-style wiki): a page for each paper that carried the advisor's card or one of your own sections, with its sources (never your mail, calendar or weather), your goals, and the advisor's notes on your company. Open it in Obsidian; edit anything.

It reports. It does not act on what it finds: no purchases, no bookings, no logins, no downloads.

## What goes in the paper

- **Standing desks** you can keep every day: the advisor's desk (your stage,
  one focus with the people and a draft, and what not to do, read from your
  mail, messages and calendar; there is no template to fill in, and you steer
  it by texting corrections), weather, calendar, mail. The advisor's desk thinks
  for about 40 minutes per pass, so set `delivery.lead_minutes` (up to 179, and
  never so much that the run would start before midnight of its delivery day;
  registration refuses that) to have the paper arrive by the delivery hour.
- **Sections** you named (“esportes”, “the dollar”, a beat of your own), including a different paper at a different hour if you ask for one.
- **One day’s assignment** (“put the iPhone price in tomorrow’s paper”).
- **A one-off** you want once, on a short budget, without it becoming a standing section.

Ask in the chat. The edition comes back as its own delivery, on the clock you set — not as a live essay in the same turn.

## Install

One repo, Docker Compose, and a Plow line. You need Git, Docker Compose, and Python 3.

```sh
git clone https://github.com/plow-pbc/plow-agents.git
export PATH="$PWD/plow-agents/bin:$PATH"

git clone https://github.com/jeanjacintho/the-plow-times-hermes-agent.git
cd the-plow-times-hermes-agent

plow-agents login                 # text the printed “Plow Activate: …” code
plow-agents lines                 # pick a line whose STATUS is free
plow-agents mint ln_xxx           # writes ./plow-credentials — do this before the first up
docker compose up --build -d
docker compose logs -f agent      # wait for: plow-init: configured ... as cht_
```

If you have no assistant line yet: `plow-agents login --new-line`, then `lines` and `mint`.

Text the line you minted. The first message is the paper’s hour, not a profile interview.

To print and to research in your own browser, run [Latch](https://howto.plow.co/latch) on the Mac this agent should drive. In Latch: **Agents → can’t use OAuth? create a static credential**. Put `DOMO_DEVICE_UID` and `DOMO_MCP_TOKEN` in the container’s `/var/lib/hermes/.env` (`KEY=value` at column 0), then `docker compose restart`. Chat works without Latch; the Mac, the printer and the wiki do not.

```sh
docker compose down          # stop, keep memory
docker compose down -v       # wipe local memory (new setup)
plow-agents revoke           # retire the line in plow-credentials
```

`plow-credentials` is gitignored. Do not commit it.

## Known limitations

The daily cron is computed from the delivery hour on the date setup ran.
Time zones that change for daylight saving can land one hour off until the
owner changes the hour in chat.

An edition delivered while the Mac is unreachable is not recorded in the
wiki, and the next morning's advisor has no "yesterday" for it.

## License

MIT. See [LICENSE](LICENSE).

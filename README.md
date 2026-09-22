# The Founder Times (inspired by Mayfield)

Your morning paper, printed. It researches on your Mac and puts a sourced page in the tray — PDF in chat if you’d rather.

A [Hermes](https://howto.plow.co/hermes) agent on [Plow Chat](https://howto.plow.co/). You text it like a newspaper, not like a chatbot. It is one person’s paper: the sections you asked for, at the hour you named, in the language you write.

## What it is

The product is a **compact Letter paper**. It can open with **what Patrick Salyer
would tell you** after watching your last day, learned from your Mac, then
weather, one calendar rail, and up to three stories you told it to cover. The
longest story leads; the other two sit side by side. Readability wins over an
artificial page limit, so a dense edition may continue onto a second sheet. It goes to a
printer on your Mac when one is there, and the same edition can land as a PDF
in chat. Mail and sports stay available in the chat edition and research
context, but do not compete for space on the printed page.

You do not fill a profile. The first message is the paper: what time it should arrive. It learns your timezone from where the Mac is; it does not interview you for a name.

Research runs on **your** browser, through [Latch](https://howto.plow.co/latch). If a page cannot be read, the paper says so — it does not invent the paragraph.

What it learns and prints goes into your wiki at `~/Plow/wiki` (Latch's Obsidian-style wiki): a page for each paper that carried the advisor's card or one of your own sections, with its sources (never your mail, calendar or weather), your goals, and the advisor's notes on your company. Open it in Obsidian; edit anything.

It reports. It does not act on what it finds: no purchases, no bookings, no logins, no downloads.

## What goes in the paper

- **Printed desks** kept at the front of the paper: the advisor's desk (three ranked,
  sourced recommendation essays challenged by independent critics using your
  mail, messages, calendar and owner-named sources; there is no template to fill
  in, and you steer it by texting answers and corrections), weather, and one
  calendar rail. Mail and sports remain chat-only. The advisor's desk uses
  the configured overnight window, so set `delivery.lead_minutes`; registration
  clamps each paper's start to midnight of its delivery day, and the PDF waits
  for the delivery hour before posting.
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

To print and to research in your own browser, run [Latch](https://howto.plow.co/latch) on the Mac this agent should drive, signed in to the same Plow account. The agent reaches it with its own credential — there is nothing to paste and no restart. Chat works without Latch; the Mac, the printer and the wiki do not.

Upgrading from a version that had you paste a static credential? The next boot retires it for you. Revoke that credential in Latch anyway — nothing uses it now, and a bearer nothing uses is one nobody notices.

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

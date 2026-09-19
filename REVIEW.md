# Review instructions — the-plow-times-hermes-agent

Repo-specific reviewer policy. The universal voice posture (Broken-Glass,
pro-simplification, and the don't-propose list) is supplied by the reviewers
themselves and is deliberately not restated here.

## What this repo is

**One agent** — The Founder Times: a morning paper researched on the owner's
Mac and printed there or sent as a PDF in chat. It is the persona
(`runtime/SOUL.md`, `runtime/USER.md`), the `pt-*` skills and their scripts,
and the image that bakes them onto a pinned base. The runtime underneath
(Hermes, boot, `plow-init`, the hardened home, the gateway config seed) is
`plow-pbc/plow-hermes-agent`; every turn's framing and the Plow tools are the
`plow_chat` plugin in `plow-pbc/hermes-plugin-plow`, which the base pins.
`README.md` owns the product prose; this file restates none of it. Flag drift
between that prose and the code, in either direction.

**Stage:** pre-PMF, early — a handful of installs, each one owner's paper
running in Docker against their own Plow line. The agent holds that owner's
credential and reaches their mail, calendar, browser and printer through
Latch, so a credential, a chat id, an account name or a real person's data
anywhere under the tracked tree is blocking. That includes the edition
renders under `index/`, which are drawn from synthetic data.

Skills, prompts and comments are in English. The paper is not: it is written
in the language the owner writes in, which `pt-intake` records through
`record_owner_language.py`. Owner-facing text that hard-codes a language
around that is a finding.

## Review priority

Subtractive remedies outrank additive ones. Three gates here are falsifiable
and worth the reviewer's attention ahead of anything else:

- **It reports; it does not act, and it does not invent.** The paper makes no
  purchases, bookings, logins or downloads, and every claim carries a source.
  Block a change that lets a skill act on what it reads, or that turns a
  failed read into content — an empty agenda, a clear inbox, a paragraph with
  no page behind it. A read that failed has to reach the page as a failure.
- **Pins are the supply chain.** The base `FROM` carries a digest,
  `vendor/client.pin` a commit plus a sha256 the Dockerfile verifies, and
  WeasyPrint and pydyf exact versions. Block a change that moves any of them to
  a mutable ref or drops the checksum check. Bumping a pin to a new immutable
  revision is ordinary work, not a finding.
- **Runtime patches fail closed.** `image/hermes/patch_*.py` rewrite Hermes
  source at build and exit non-zero when a base bump moves their anchor. Block
  a change that weakens that exit. A new patch, or an existing one widened, is
  a sibling-ownership finding: per the base's map a Hermes fix goes to
  `srosro/hermes-agent` and upstream, and the plugin carries the workaround
  meanwhile.

**Repo-specific contrast pairs:**

| Variant DON'T (suppress / flag-as-shape) | Variant DO (real finding) |
|---|---|
| Flag a section, a default, the advisor's desk or its sources for being **specific to one owner's paper**. Being one person's paper is this repo's whole reason to exist; generality here is the bloat, not the fix. | Flag a change that a **sibling repo owns** per [`plow-hermes-agent` README § The repos](https://github.com/plow-pbc/plow-hermes-agent#the-repos): a base fix — boot, `plow-init`, the gateway config seed — is `plow-hermes-agent`; per-turn framing or a Plow tool is `hermes-plugin-plow`; a fix to the Agent Index client is `agent-index-client`, which this repo only pins; account, login, mint or revoke is `plow-agents`. `post_to_chat.py` already mirrors the plugin's chat adapter and `print_edition.py` drives Latch's `write_file` over the relay — keep each in step with its owner rather than growing either into a second client. The test is who else would have to change if the fact changed. |

**Update cadence:** edit when the stage changes. Product and architecture edits
belong in `README.md`, not here.

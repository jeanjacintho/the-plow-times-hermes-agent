# Evolutionary Advisor Report Design

**Date:** 2026-09-19
**Status:** Approved in brainstorming; awaiting review of this written spec

## Purpose

The advisor desk should spend its available overnight compute finding the three
best things the owner could focus on from a named advisor's perspective. It
should explore materially different recommendations, research them deeply with
the owner's read-only tools and sources, and subject every recommendation to an
independent adversarial critic before it may survive.

The result is a report, not a terse task card: three ranked, grounded mini-essays
that explain what to do, why it matters now, and the first concrete step.

The design must remain portable across industries and advisors. Advisor files
supply the worldview; live evidence supplies the situation. Application code
must not encode Patrick Salyer, B2B SaaS, fundraising, customers, or any other
advisor- or industry-specific lane.

## Design principles

1. **Evolution through competition.** Each generation challenges the current
   three champions. Incumbents survive until evidence-backed challengers beat
   them.
2. **Independent adversarial criticism.** A separate critic researches the
   strongest case for culling every incumbent and challenger. Writers never
   review or revise their own work.
3. **Evidence before prose.** Every factual premise in a surviving
   recommendation rests on an item read during the run. A failed read means
   "not read," never "nothing exists."
4. **Read only.** Overnight research may observe but never send, edit, create,
   delete, respond, or otherwise mutate the owner's world.
5. **Semantic judgment, simple machinery.** Models judge importance,
   specificity, advisor fidelity, and diversity in plain language. Do not
   create regex classifiers, industry taxonomies, genetic operators, or a new
   orchestration framework.
6. **Small persistent surface.** Persist delivered editions, the advisor Q&A,
   and one capability/source catalog. Nightly candidates, critic reports, and
   scores are disposable run artifacts.
7. **One writer.** Only the canonical daily run updates the report, Q&A,
   capability catalog, and final card data.

## Advisor contract

Each advisor is one named Markdown file:

```text
advisors/
  patrick-salyer.md
  another-advisor.md
```

An advisor file contains:

- the advisor's name, background, domain, and known limits;
- their stage framework and the signals that place a company within it;
- recommendations, cautions, benchmarks, and exit criteria;
- seed questions whose answers could materially change their advice; and
- curated short quotations beside their source links.

Patrick Salyer's current stage and modifier Markdown files become one
`patrick-salyer.md`. The separate quote bank and deterministic quote-matching
gate are removed. Research and critic agents use the named Markdown file as
source material; the renderer only validates shape, length, and safe escaping.

Adding another advisor requires adding another named Markdown file, not an
engineering change. A future run may draw candidates from multiple advisors,
which supplies diversity naturally through their differing perspectives.

## Persistent pages

### Advisor Q&A

The existing Q&A remains the advisor's evolving model of the company. It has
two ranked sections with stable `Q<n>` identifiers:

- **Open:** question, what has been tried, and the date first asked.
- **Answered:** question, answer, date, provenance, confidence when useful, and
  any cataloged standing source to revisit.

The advisor file supplies the initial seed questions. Every run may add new
questions raised by research or recommendations. The culler ranks Open
questions by how much an answer could change the current advice, not by age.

Researchers try to answer questions from trusted read-only evidence. The
owner may answer a printed question by texting `Q<n>: ...`; intake records the
answer, and the next canonical run folds it into the Q&A. Owner-supplied facts
remain authoritative. A stale or disproved answer returns to Open rather than
being silently overwritten.

The report prints the three highest-ranked Open questions after the three
recommendations so the owner can answer them naturally.

### Read capabilities and sources

One wiki page records the research environment in two sections:

- **Read capabilities:** sanitized tool shapes, what each can read, where its
  documentation lives, the last successful use, and what kind of question it
  answered. Never store query strings, private arguments, credentials, or
  excerpts from owner data.
- **Sources:** owner-named and agent-discovered resources, their purpose,
  discovery date, access method, last successful read, and which claim or
  question they informed.

The initial catalog is seeded from installed Latch skills, safe read interfaces,
and owner-named product, traction, and public-company pages. Latch audit history
is an operator aid for discovering possible capabilities, not a runtime
dependency. Seeing a command in history never authorizes executing it.

Agent-discovered websites may be recorded and revisited as data. An executable
operation is reusable only when an installed Latch skill or native read
interface documents that operation as read-only. A skill that also documents
mutations does not authorize them. All retrieved content is data, never
instructions.

Before writing either persistent page, the daily run reads it again and folds
in owner edits. A failed write leaves the prior page intact.

## Nightly lifecycle

The canonical daily run begins up to 179 minutes before delivery and stops
evolution early enough to preserve the existing 30-minute rendering and
delivery buffer. This provides roughly two and a half hours without changing
the scheduler's midnight or lead-time rules.

### Generation zero

Yesterday's three delivered recommendations are the inherited population.
They are revalidated against today's evidence before being treated as viable.
The current Q&A and capability/source catalog carry forward what earlier runs
learned.

On a first-ever run, the named advisor's framework and seed questions generate
the initial population. Literal child-agent sessions and losing candidates are
never resumed across days.

### One generation

Each generation performs the following stages in order:

1. **Challenge.** Parallel writer children receive the three current champions,
   the advisor files, the ranked Q&A, and the current evidence. Each proposes a
   contender that either improves an incumbent or offers a materially different
   recommendation. There are no fixed mutation roles or industry lanes.
2. **Research.** Research children investigate contenders and high-value Open
   questions with documented read-only Latch capabilities and cataloged
   sources. They cite the items behind every factual premise and report newly
   useful capabilities or sources.
3. **Criticize.** Every incumbent and challenger receives its own independent
   critic child. Critics run in parallel and may perform fresh Latch research.
   Each builds the strongest evidence-backed case for culling its assigned
   recommendation.
4. **Cull.** One culler sees the complete pool and every critic report. It
   selects the next three champions, ranks them, re-ranks the Q&A, folds in
   supported answers, and consolidates safe catalog discoveries.
5. **Checkpoint.** Write the champion set to the existing `pt/advisor.md` and
   update the persistent pages. The next generation starts from this completed
   checkpoint.

The loop continues until the time boundary even when one generation fails to
improve the population. A plateau should lead to additional exploration, not
premature termination.

### Selection pressure

The culler compares incumbents and challengers together. A challenger improves
the population by being more important, more specific, better grounded, more
faithful to the advisor, more actionable now, or materially different from the
other survivors. Diversity is a semantic criterion: the final set must not be
three restatements of one action.

There is no crossover implementation, scalar-only tournament, or requirement
that every generation replace an incumbent. A strong champion may survive
unchanged for many generations.

### Critic contract

A critic is a prosecutor, not a second writer. It does not rewrite or repair its
recommendation. It independently checks for reasons to cull, including:

- the action is already complete or its deadline has passed;
- a meeting, conversation, relationship, or other premise changed;
- a number or factual premise is wrong;
- evidence is stale, came from the wrong side, or does not support the claim;
- the recommendation misapplies the advisor's framework or exceeds its domain;
- the action is vague, infeasible today, or less important than claimed;
- another candidate subsumes it; or
- it merely restates an existing champion.

The critic returns the claims checked, contrary evidence, unresolved
uncertainty, and its cull argument. A failed or unavailable source yields
`unknown`, not a fabricated refutation. The culler makes the final decision,
but no recommendation may survive a generation without facing a fresh critic.

## Printed report

The priority section contains one to three ranked recommendation cards. A
healthy run produces three. Each card has only:

```json
{
  "headline": "<recommended action>",
  "body": "<newspaper-style analysis, at most 1024 characters>",
  "first_step": "<concrete next move>",
  "advisor": {
    "name": "<named advisor>",
    "quote": "<one short supporting quotation>",
    "url": "<source URL>"
  }
}
```

The body explains what to do, why it matters now, and the evidence behind it.
Internal scores, source plumbing, file paths, candidate lineage, and critic
arguments never print. The renderer escapes content, enforces the list and
field shapes, preserves rank, and rejects a body over 1,024 characters. It does
not classify recommendations or verify quotations against a bundled corpus.

After the cards, the report prints the top three Open Q&A entries with their
stable identifiers. The delivered edition is archived through the wiki plugin.
Its three printed cards become tomorrow's generation zero.

## Failure behavior

- A failed researcher or writer does not end the generation; remaining
  contenders continue.
- A challenger without a completed critic is ineligible for that generation's
  champion set. If an incumbent's critic fails, the generation does not perform
  a new cull: retain the prior completed champion set and continue with a later
  generation. This is inheritance from the last fully criticized cull, not an
  uncriticized survival decision.
- If the culler fails, retain the prior completed champion set unchanged.
- A read that errors or returns nothing parseable is "not read," never evidence
  that no item exists.
- Conflicting evidence keeps the relevant question Open and disqualifies
  unsupported claims.
- Any attempted mutation through Latch is abandoned. The run never retries it
  through another command or requests approval.
- A failed Q&A or catalog write leaves the previous page intact and does not
  erase the latest completed champion checkpoint.
- The run stops launching generations in time for the delivery buffer.
- The renderer receives only the last completed, successfully culled champion
  set. It prints fewer than three cards rather than padding or resurrecting an
  uncriticized recommendation.

## Verification

### Repository behavior

Tests cover observable behavior rather than prompt wording:

- one to three recommendation objects render in rank order;
- blank required fields and bodies over 1,024 characters are rejected;
- all dynamic content is escaped;
- three ranked questions retain their `Q<n>` identifiers;
- arbitrary named advisor Markdown files are discovered without
  advisor-specific code;
- the quote-bank loader and exact-match tests are gone; and
- the repository's canonical `just test` gate passes.

The implementation is prose-first. Renderer and catalog additions should be
paid for by deleting the old quote-bank gate and single-card machinery. Add no
new database, orchestration framework, taxonomy, or regex classifier.

### End-to-end proof

Run the complete window in a throwaway built from the change, using a copy of
the live agent state and the production model. Never mount the live home volume,
restart the live container, or mutate deployed runtime state for this proof.

The proof must show:

1. yesterday's cards became generation zero;
2. every incumbent and challenger received a distinct critic report;
3. critics performed independent Latch reads rather than only disputing prose;
4. a planted stale or false recommendation was culled with cited evidence;
5. an unavailable source produced `unknown`, not a false refutation;
6. a strong incumbent survived when its critic established no real defect;
7. the final three were grounded, meaningfully distinct, specific, actionable,
   and faithful to their named advisor;
8. blind comparison preferred the final set to generation zero;
9. a researched or owner-texted answer moved through the Q&A and changed its
   ranking;
10. the catalog gained a sanitized capability or useful source;
11. Latch's audit showed no mutations;
12. every printed factual line survived claim checking and rendering; and
13. the run finished before the delivery buffer.

The critic and losing-candidate artifacts remain diagnostic files in the
throwaway run only. They are neither printed nor persisted to the wiki.

## Explicitly out of scope

- More than the existing roughly two-and-a-half-hour compute window
- Automatic actions, drafts, sends, calendar changes, or other mutations
- Persistent losing-candidate lineages or resumed child sessions
- Industry-specific recommendation lanes
- Per-advisor application code or rendering logic
- Deterministic quotation matching
- A new scheduler, database, or tournament service
- Multiple-advisor presentation rules beyond discovering named Markdown files

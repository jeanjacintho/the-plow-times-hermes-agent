# Advisor notes

Markdown files the paper cites when it picks today's #1. Seeded on setup into
`~/Plow/advisors/`. Edit them, add other investors, delete what does not fit.

## File shape

```markdown
---
advisor: Name (firm)
stages: blueprint
domain: b2b-saas-enterprise
source: https://example.com/the-public-post
---
# Blueprint — $1–10M ARR

## Signals
- How you recognize this stage.

## Focus first
- The one job of this stage.

## Do not focus on
- What not to do here.

## Benchmarks
- Numbers that belong to this stage.

## Exit criteria
- How you know you left the stage.
```

- `stages`: one or more of `discovery`, `blueprint`, `scale`, `pivot`, `fundraising`, `any`.
- `domain`: free label. If company state reads consumer/PLG and the file says
  B2B enterprise, the paper prints a warning instead of hiding the advice.
- Recognized sections: `signals`, `focus` (`Focus first`), `avoid` (`Do not focus on`),
  `benchmarks`, `exit`. Other headings stay as context.
- Quotes on the page are at most 25 words.

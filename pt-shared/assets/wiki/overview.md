---
type: Project
title: The Founder Times
description: Your morning paper — every edition it delivered, and what its advisor's desk knows about your company.
category: projects
tags: [newspaper]
sources:
  - resource: plow-chat:{chat}
created: {today}
updated: {today}
---
# The Founder Times

The paper writes here every morning; you can edit anything it wrote. To change
what it covers, text the paper.

- [The advisor's Q&A](/projects/theplowtimes/qa.md) — what the advisor needs to know about
  your company, and the answers found so far. The paper rewrites it every morning and keeps
  a correction you make on it; a goal or a standing instruction belongs on
  [What I'm working toward](/entities/owner/goals.md), or a text to the paper.
- [What I'm working toward](/entities/owner/goals.md) — your goals, what not to do now,
  and notes. What you write there overrides anything the desk infers.

## Add your own advisor

Patrick Salyer's advice comes with the paper. To add an advisor or investor of your
own, create a page in `advisors/` shaped like this:

    ---
    type: Advisor
    title: Jane Doe (Acme Ventures)
    description: What Jane tells founders at the blueprint stage.
    category: projects
    tags: [advisor]
    paper: "[The Founder Times](/projects/theplowtimes/theplowtimes.md)"
    advisor: Jane Doe (Acme Ventures)
    stages: blueprint
    sources:
      - resource: https://example.com/the-public-post
    created: 2026-09-19
    updated: 2026-09-19
    ---
    # Blueprint — $1–10M ARR

    ## Signals
    ## Focus first
    ## Do not focus on

`stages` is one or more of discovery, blueprint, scale, pivot, fundraising, any.

## Your advisors

## Editions

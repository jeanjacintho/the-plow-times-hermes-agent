# Founder One-Page Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the Founder Times as one Letter page containing a compact founder focus, one calendar rail, and three news articles arranged as one lead above a two-story pair.

**Architecture:** Keep `edition.json` as the content boundary and reshape only the print renderer/template. `render_html` emits explicit lead, pair, and calendar-rail slots; `write_pdf` enforces the one-page invariant after WeasyPrint layout, while chat serialization remains unchanged.

**Tech Stack:** Python 3.13, HTML/CSS Paged Media, WeasyPrint 62.3, pytest 8.4.2, Poppler visual inspection

**Spec:** `docs/superpowers/specs/2026-09-20-founder-one-page-layout-design.md`

## Global Constraints

- The printable output is exactly one Letter page; overflow is a named failure, never truncation.
- Print no more than three news articles: one full-width lead above a side-by-side pair.
- The structured calendar rail is the sole printed event owner; `priority.today` does not print.
- Remove the masthead slogan and Sudoku completely.
- Keep source links on each printed article and preserve all existing escaping/security behavior.
- Keep full desk content in chat output.

---

### Task 1: Lock the renderer contract with failing tests

**Files:**
- Modify: `tests/test_render_edition.py`
- Modify: `tests/test_repo_contract.py`

**Interfaces:**
- Consumes: existing `render.validate`, `render.render_html`, and `render.write_pdf`
- Produces: regression expectations for `news-pair`, `calendar-rail`, a maximum of three news stories, no printed `priority.today`, no `SUDOKU`, no slogan, and one-page PDF refusal

- [ ] **Step 1: Replace stack/Sudoku expectations with the one-page layout expectations**

Add focused tests that render three named news sections and assert the first appears in `lead-cell`, the other two appear exactly once inside `news-pair`, the calendar appears exactly once in `calendar-rail`, and priority event text is absent from HTML while still present in `chat_edition`.

- [ ] **Step 2: Add the validation and PDF page-count tests**

Add a validation case with four news sections that expects `edition has more than 3 news articles`, plus a fake `weasyprint.HTML` document with two pages that expects `SystemExit` containing `rendered 2 pages; expected exactly 1`.

- [ ] **Step 3: Update repository-contract assertions**

Assert that the shipped template contains `news-pair` and `calendar-rail`, contains neither `Every claim` nor `SUDOKU`, and that the index contains only `edition-page-1.jpg`.

- [ ] **Step 4: Run the focused tests and confirm they fail for the intended reasons**

Run: `uv run --no-project --python 3.13 --with pytest==8.4.2 pytest -q tests/test_render_edition.py tests/test_repo_contract.py`

Expected: failures name the missing one-page structure, existing Sudoku/slogan, absent three-news limit, and absent PDF page-count gate.

- [ ] **Step 5: Commit the failing contract**

```bash
git add tests/test_render_edition.py tests/test_repo_contract.py
git commit -m "test: define the founder one-page contract"
```

### Task 2: Build the one-page renderer and template

**Files:**
- Modify: `pt-edition/scripts/render_edition.py`
- Modify: `pt-edition/template.html`

**Interfaces:**
- Consumes: up to three news sections, one calendar section, optional priority/weather sections
- Produces: `{{LEAD}}`, `{{NEWS_PAIR}}`, and `{{CALENDAR_RAIL}}` HTML plus a one-page-only PDF write

- [ ] **Step 1: Validate the three-news maximum**

Count sections for which `is_news_section(section)` is true inside `validate`; append `edition has more than 3 news articles` when the count exceeds three.

- [ ] **Step 2: Make the calendar the only printed event owner**

Remove the `priority.today` branch from `priority_lead`. Keep validation and chat serialization intact so the field remains compatible but never duplicates the printed calendar.

- [ ] **Step 3: Emit the lead, pair, and calendar rail**

In `render_html`, keep the first news section in `lead_html`, wrap the remaining zero-to-two article blocks as `<div class="news-pair"><div class="news-pair-cell">…`, and expose the existing calendar HTML through `{{CALENDAR_RAIL}}`. Do not place calendar, mail, or sports in `{{DESKS_INLINE}}` in the shipped layout.

- [ ] **Step 4: Replace the shipped page structure and CSS**

Remove the left slogan ear, desk-row layout, stacked news well, puzzle CSS, and puzzle markup. Add compact masthead/focus spacing, `.page-body`, `.news-column`, `.calendar-rail`, `.news-pair`, and `.news-pair-cell` rules using WeasyPrint-safe table/table-cell layout where side-by-side flow cannot split.

- [ ] **Step 5: Enforce one PDF page**

Change `write_pdf` to call `HTML(string=html_text).render()`, check `len(document.pages) == 1`, exit with `rendered N pages; expected exactly 1` otherwise, and call `document.write_pdf(path)` only after the check.

- [ ] **Step 6: Run focused tests and confirm they pass**

Run: `uv run --no-project --python 3.13 --with pytest==8.4.2 pytest -q tests/test_render_edition.py tests/test_repo_contract.py`

Expected: PASS.

- [ ] **Step 7: Commit the renderer and template**

```bash
git add pt-edition/scripts/render_edition.py pt-edition/template.html
git commit -m "feat: render the founder briefing on one page"
```

### Task 3: Remove Sudoku and align the edition contract

**Files:**
- Delete: `pt-edition/scripts/sudoku.py`
- Delete: `tests/test_sudoku.py`
- Modify: `pt-edition/SKILL.md`
- Modify: `tests/test_repo_contract.py`

**Interfaces:**
- Consumes: the Task 2 renderer with no Sudoku import or placeholder
- Produces: an authoring contract with no puzzle feature and repository inventory with no Sudoku exception

- [ ] **Step 1: Delete the unused generator and its unit tests**

Remove `pt-edition/scripts/sudoku.py` and `tests/test_sudoku.py` after the renderer import, constants, helper, and placeholder replacement are gone.

- [ ] **Step 2: Update the edition authoring instructions**

Remove the Sudoku authoring paragraph, replace pagination language with the exact one-page/three-news contract, and state that `priority.today` is chat/source data while the calendar schedule is the only printed event list.

- [ ] **Step 3: Remove the repository inventory exception**

Update the script-inventory test so `sudoku.py` is no longer exempted as an imported-only script.

- [ ] **Step 4: Run the complete test suite**

Run: `just test`

Expected: all tests pass.

- [ ] **Step 5: Commit the feature removal and contract**

```bash
git add pt-edition/SKILL.md tests/test_repo_contract.py
git add -u pt-edition/scripts/sudoku.py tests/test_sudoku.py
git commit -m "refactor: remove the puzzle from founder editions"
```

### Task 4: Prove the real page and refresh listing art

**Files:**
- Modify: `index/edition.json`
- Modify: `index/edition-page-1.jpg`
- Delete: `index/edition-page-2.jpg`
- Delete: `index/edition-page-3.jpg`

**Interfaces:**
- Consumes: the shipped Docker image, `index/edition.json`, and `index/render_screenshots.sh`
- Produces: one inspected screenshot generated from a representative three-news edition

- [ ] **Step 1: Make the synthetic fixture exercise three news articles**

Add a third synthetic news section with a distinct title, headline, body, and source while retaining priority, weather, and calendar data.

- [ ] **Step 2: Build and render through the pinned runtime**

Run: `docker compose build agent && index/render_screenshots.sh`

Expected: `wrote .../index/edition-page-1.jpg`, with no page 2 or page 3 artifact.

- [ ] **Step 3: Inspect the rendered page**

Open `index/edition-page-1.jpg` and verify: no clipping/overlap; one visible calendar; no repeated calendar event in the priority card; one lead above a balanced pair; readable sources; no slogan; no Sudoku; and balanced bottom whitespace.

- [ ] **Step 4: Run the canonical gate again**

Run: `just test`

Expected: all tests pass, including the one-screenshot repository contract.

- [ ] **Step 5: Commit the verified fixture and listing art**

```bash
git add index/edition.json index/edition-page-1.jpg
git add -u index/edition-page-2.jpg index/edition-page-3.jpg
git commit -m "docs: show the one-page founder edition"
```

### Task 5: Publish and converge the pull request

**Files:**
- No repository files unless review finds a real defect

**Interfaces:**
- Consumes: green canonical gate and visually verified one-page artifact
- Produces: pushed `founder-1pager` head and an open, converged PR against the operator-controlled repository

- [ ] **Step 1: Reconcile concurrent branch updates**

Fetch `origin/founder-1pager`, integrate any new infrastructure commits without discarding either side, rerun `just test`, and regenerate/reinspect the screenshot if layout inputs changed.

- [ ] **Step 2: Push the branch and open the PR**

Push `founder-1pager`, create a PR to `main`, and put the behavior changes at the top of the body: one-page-only PDF, three-story hierarchy, calendar-only event ownership, no Sudoku, no masthead slogan.

- [ ] **Step 3: Run the babysit-pr convergence loop**

Use `$babysit-pr` on the PR. For every new head, require green exact-head checks and a clean exact-head review; fix verified defects, rerun the canonical gate and visual render, push, and request re-review until converged.

- [ ] **Step 4: Stop before merge**

Report the converged PR for explicit merge consent. Do not merge without the user's approval for that exact PR.

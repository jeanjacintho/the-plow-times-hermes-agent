# Founder One-Page Layout Design

## Goal

Turn the printable Founder Times edition into a deliberate one-page briefing built around three news articles: the longest article leads, the two similarly sized articles share the row below it, and the calendar appears once as the page's only schedule.

## Page hierarchy

The Letter sheet has five visual layers, in order:

1. A compact newspaper masthead with the edition date/location and today's weather. The left marketing ear and the sentence “Every claim carries its source” are removed.
2. A compact founder-focus card containing the priority headline, first step, rationale, and other non-calendar advisor material.
3. A two-column body: the news well on the left and a narrow calendar rail on the right.
4. Inside the news well, the first/longest article spans the full width. Articles two and three render as a matched two-column pair below it.
5. A quiet folio footer.

The design uses the existing monochrome newspaper vocabulary, local fonts, escaped content, and inline source links. Sources remain attached to their articles; only the unsupported marketing slogan disappears.

## Content ownership

The structured calendar `schedule` is the sole printed representation of events. Calendar prose is not printed when a schedule is present, and `priority.today` remains valid input/chat data but does not render inside the founder-focus card. This prevents the same event from appearing in both the founder card and calendar rail.

Weather remains the masthead ear. Mail and sports remain supported in structured data and chat output, but do not create separate printed desk boxes in the one-page founder briefing. The print page is reserved for the founder focus, one calendar, and the three news articles supplied by the new infrastructure.

## One-page contract

The normal print input contains at most three news articles. The renderer keeps all three: it never truncates an article or silently drops overflow. The PDF writer renders to a WeasyPrint document first and refuses output unless that document has exactly one page. This makes one page an executable contract rather than a screenshot assumption.

The fixed template uses compact type, spacing, and source treatment sized for three articles of the edition contract's normal length. Photos remain optional, but their existing bounded crop is retained.

## Compatibility

Chat output is unchanged, including full calendar, mail, sports, and priority data. Legacy/custom HTML templates continue receiving named placeholder replacements, but the shipped `template.html` uses the new one-page slots. Editions with fewer than three articles render the available articles without synthetic filler. More than three news articles fail validation by name rather than being omitted.

The Sudoku feature is removed completely from the edition renderer, template, authoring instructions, and tests. The standalone generator and its tests are deleted because nothing consumes it after this change.

## Verification

Tests cover the three-story lead-plus-pair structure, the single calendar rendering, omission of `priority.today` from print, absence of Sudoku and the slogan, preservation of sources, the three-article validation limit, and refusal of multi-page PDFs. The repository's canonical `just test` gate must pass.

The synthetic index fixture gains a third news article, is rendered through the pinned Docker image, and must produce exactly one screenshot. The final screenshot is inspected for clipping, overlap, legibility, balanced whitespace, and the intended story hierarchy.

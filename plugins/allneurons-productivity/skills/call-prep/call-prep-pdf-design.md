# Call Prep PDF — design

A 1–2 page executive briefing, opened from the prep block five minutes before a call. Clean, black on white, easy to scan. It uses the **same page, colours, type and spacing as `skills/daily-brief/daily-brief-pdf-design.md`**; only the blocks differ. Rendered by `assets/suite_pdf_design.py --kind call_prep` (drawing code: `assets/render_call_prep.py`, sharing components with `assets/render_brief.py`).

## Page, colours, type, spacing

Identical to `skills/daily-brief/daily-brief-pdf-design.md`: Letter, 54pt margins, Helvetica, black text (`#000000`), nothing lighter than `#555555`, the spacing scale **4, 8, 12, 16, 24, 32, 48 pt**, and the same status colours.

Extra styles this briefing uses:

```css
.eyebrow         { content: "CALL PREP"; }                  /* same style as Daily Brief */
.title           { font: 700 30pt; color: #000000; }        /* "{Person} · {Meeting}" */
.context         { font: 400 16pt/22pt; color: #000000; }   /* one sentence: why this call */

.glance-cell     { background: #F6F8FA; radius: 6pt; padding: 12pt; }
.glance-label    { font: 700 8pt; letter-spacing: 0.5pt; text-transform: uppercase; color: #333333; }
.glance-value    { font: 700 11pt/14pt; color: #000000; }   /* cells grow to fit; never overlap */

.outcome-box     { background: #E8F1FB; left-bar: 3pt #1976D2; radius: 6pt; padding: 14pt 17pt; }
.outcome-label   { font: 700 8pt; uppercase; color: #1976D2; }
.outcome-text    { font: 700 13pt/18pt; color: #000000; }

.person-name     { font: 700 12pt/16pt; color: #000000; }
.person-role     { font: 400 10pt/14pt; color: #555555; }   /* "Role · Company" */
.person-why      { font: 400 11pt/16pt; color: #111111; }   /* 170pt name column, why on the right */
.first-time-tag  { font: 700 7.5pt; color: #1976D2; }

.bullet          { font: 400 11.5pt/17pt; color: #111111; } /* dot 2.4pt, 22pt indent */
.bullet-source   { font: 400 9pt; color: #555555; }         /* "[Teams, 26 Sep]" on the same line */
.question-num    { font: 700 11pt; color: #555555; }        /* 01, 02, 03 … */
.objective       { font: 700 13pt/18pt; color: #000000; }
```

## Blocks, top to bottom

1. **Masthead.** `CALL PREP` eyebrow. Title: **person · meeting name**. Below it, one sentence on why this call is happening. **No "Generated {time}" stamp** — the renderer's own clock is not reliably the user's local time, and a timestamp that could be wrong is worse than none.
2. **Call at a glance.** A row of cells: When · Length · Format · Owner · Last contact. Empty facts are left out. Every basic fact appears here once and is never repeated below.
3. **Desired outcome.** A blue box with a left bar, holding the one outcome in bold.
4. **Who you'll be speaking with.** One row per person: name (bold) with role · company under it, and one line on why they matter on the right. Hairline between rows. A `FIRST TIME` tag goes next to anyone new. Any decision-maker missing from the invite goes on one line under the table.
5. **What you need to know.** Up to 4 bullets with a blue section dot, each ending in a small grey source tag.
6. **What you should accomplish.** One bold sentence with a name and a date.
7. **Questions to ask.** 4–6 numbered lines (`01`, `02` …).
8. **Risks to watch.** Up to 3 bullets with amber dots. Leave the section out if there's nothing real.
9. **Actions & owners.** The same action cards as the Daily Brief: red edge bar, number, action, status pill, OWNER/DUE line, SOURCE line. Anything the user still owes goes first.
10. **Sources.** Numbered list; links in blue.
11. **Footer on every page.** "Call Prep · {person} · {time}" on the left, "Page X of Y" on the right.

## Rules

- **Two pages maximum.** Cut lines, never shrink the type. The test for every line: does it help the reader prepare, decide, ask or act?
- Never announce a missing fact ("title not established"); leave it out.
- Never print raw system values (`needsAction`, `tentative`); say "still unanswered" or "hasn't confirmed".
- No logos, emoji, gradients or shadows. No grey body text.

## Nothing leaves the margins ()

Every text run sits inside the 0.75 in content margins, whatever the content: the company title and the footer wrap or truncate with "..." instead of running off the page, the at-a-glance strip lays out at most three cells per row, and a long URL or email breaks inside its cell. `assets/pdf_layout_check.py` measures every text run on every page and `verify_pdf.py` / `suite_pdf.verify()` fail the render when one crosses a margin, so a long company name can no longer ship. Regression: `tests/test_pdf_layout.py` renders a deliberately hostile payload.

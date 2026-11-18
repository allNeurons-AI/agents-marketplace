# Daily Brief PDF — design

Rendered by `assets/suite_pdf_design.py --kind daily_brief` (drawing code: `assets/render_brief.py`).

Clean, black-on-white, easy to read. Big clear type, generous spacing, colour only where it means something.

## Page

```css
page        { size: Letter; margin: 54pt; background: #FFFFFF; }
content     { width: 504pt; }                 /* one column */
font-family { Helvetica, sans-serif; } /* built-in Helvetica by default (8-15 KB PDF, uploadable). Inter Display is opt-in via SUITE_PDF_INTER=1 (~55 KB, too large to upload) */
```

## Colours

```css
--text:        #000000;  /* titles, headline, actions, meeting times */
--body:        #111111;  /* normal text */
--secondary:   #333333;  /* labels, owner/due values, sources */
--quiet:       #555555;  /* small labels, footer — never lighter than this */
--line:        #EAECEF;  /* hairlines */
--card:        #F6F8FA;  /* card background */

--red:    #D32F2F;  --red-bg:    #FDECEC;  /* needs attention, open */
--amber:  #E8590C;  --amber-bg:  #FFF0E5;  /* light orange: due today, needs confirmation */
--blue:   #1976D2;  --blue-bg:   #E8F1FB;  /* conflicts, upcoming, links */
--purple: #7B3FC4;  --purple-bg: #F3EDFB;  /* worth double-checking */
--green:  #388E3C;  --green-bg:  #EAF4EB;  /* resolved */
--grey:   #9E9E9E;  --grey-bg:   #F1F2F4;  /* waiting, passed, canceled */
```

No grey body text. Colour appears only in status pills, card edge bars and the stat cards.

**One colour per status, everywhere.** Needs attention = red · conflicts = blue · due today = orange · worth double-checking = purple · resolved = green. The stat card, the section dot and the card edge bar for a status always use the same colour, so the reader learns it once.

## Type

```css
.eyebrow        { font: 700 8.5pt;  letter-spacing: 1.4pt; text-transform: uppercase; color: var(--secondary); }
.date           { font: 700 30pt;   color: var(--text); }
.headline       { font: 400 16pt/22pt; color: var(--text); max-width: 86%; }

.stat-number    { font: 700 28pt; }
.stat-label     { font: 700 8pt; letter-spacing: 0.5pt; text-transform: uppercase; color: var(--secondary); }

.section-label  { font: 700 10pt; letter-spacing: 0.8pt; text-transform: uppercase; color: var(--text); }

.card-action    { font: 700 13pt/18pt; color: var(--text); }
.card-detail    { font: 400 11.5pt/17pt; color: var(--body); }
.card-detail b  { font-weight: 700; color: var(--text); }   /* topic lead-in */
.card-meta      { font: 400 10pt/14pt; color: var(--secondary); }
.card-meta-key  { font: 700 8pt; text-transform: uppercase; color: var(--quiet); } /* OWNER, DUE, SOURCE */
.pill           { font: 700 8pt; text-transform: uppercase; }

.meeting-time   { font: 700 11.5pt; color: var(--text); }
.meeting-title  { font: 700 12pt/16pt; color: var(--text); }   /* 400 when passed or canceled */
.meeting-detail { font: 400 10pt/14pt; color: var(--quiet); }

.sources        { font: 400 10pt/15pt; color: var(--secondary); }
.footer         { font: 400 8.5pt; color: var(--quiet); }
```

## Spacing

Use only: **4, 8, 12, 16, 24, 32, 48 pt.**

```css
eyebrow → date      6pt
date → headline     8pt
headline → stats    16pt
before a section    28pt   (0 at the top of a page)
label → first card  12pt
between cards       8pt
inside a card       padding 14pt
```

## Blocks, top to bottom

1. **Masthead.** `DAILY BRIEF` eyebrow, then the date, then the headline sentence. **No "Generated {time}" stamp** — the renderer's own clock is not reliably the user's local time (it may run on a cloud sandbox in UTC), and a timestamp that could be wrong is worse than none. The date itself comes from the skill's own local `date` call and is always accurate; only the render-time clock reading is the part that's omitted.
2. **Stat row.** Four equal cards, 8pt apart, 6pt radius. Order: Needs attention · Conflicts · Due today & overdue · Resolved. A count above 0 takes its status colour: tinted background, number and label in the colour (needs attention red · conflicts light blue · due today light orange · resolved green). A zero stays neutral: grey card, grey number.
3. **Today's meetings (the calendar line).** Comes first after the stats. Under the section label sits the **calendar line**: a compact day strip with hour ticks and one block per meeting, stacked in lanes where meetings overlap. Upcoming blocks are blue, passed and canceled are grey, and overlapping or conflicting meetings are red, so the shape of the day and every clash read at a glance. The strip spans the earliest start minus an hour to the latest end plus an hour (at least six hours); an all-day event has no place on a strip and appears only in the rows. Then **one compact row per meeting**: time (112pt column), bold title with the details inline and dimmer, status chip on the right, 6pt padding, hairline between rows, so a busy day stays on one page. Order: upcoming → passed → canceled. The section label, the strip and the first row are kept together, so the heading is never stranded at a page foot. Everything is drawn inside the 0.75 in margins; long titles wrap.
4. **Needs attention.** A red dot, the label, a small count pill, and a hairline running to the right edge. Then the cards.
5. **Conflicts / Due today.** Same card style: blue edge for conflicts, orange for due. If both are empty, show one quiet line instead: *No scheduling conflicts today · Nothing due today and nothing overdue.*
6. **Worth double-checking.** Purple dot label, purple card edge. Notes that aren't tasks go on white cards with a hairline border, a grey edge bar and italic text.
7. **Resolved.** Green edge cards, title and one line. Leave the section out if there's nothing.
8. **Sources.** Numbered list; links in blue.
9. **Footer on every page.** Hairline, "Daily Brief · {date}" on the left, "Page X of Y" on the right.

## Action card

```
┃ 01  Action sentence in bold                           [ STATUS ]
┃ Topic lead-in in bold.  Detail sentence in regular text.
┃ OWNER  name     DUE  deadline
┃ SOURCE  where it came from
```

- Background `--card`, radius 5pt, a 3pt coloured bar on the left edge.
- `01`, `02`… in quiet grey before the action.
- Status pill top-right: Open = red · Needs confirmation = orange · Waiting on … = grey · Completed = green.
- Source always gets its own line, so it never wraps mid-phrase.

## Don't

- No grey body text, no text lighter than `#555555`.
- No logos, emoji, gradients, shadows or header art.
- No full boxes around sections; hairlines and card backgrounds only.
- Never shrink text to fit a page; a busy day can run to 3 pages.
- Never change the wording the brief produced.

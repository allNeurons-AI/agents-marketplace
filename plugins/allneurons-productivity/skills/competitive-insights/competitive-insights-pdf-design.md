# Competitive Insights: PDF design and payload contract

Renderer: `assets/render_competitive.py`, reached through `suite_pdf_design.py` / `deliver_prepare.py` with `--kind competitive_insights`. Same colour tokens as the Daily Brief; the report has its own header, tiles and footer. Letter, 0.75 in left and right margins; **no text may leave the margins** (`pdf_layout_check.py` fails the render otherwise); every source is a real `/URI` link annotation (`render_competitive.link_problems`).

## Section order (fixed, every week, at most 6 pages)

1. **Header**: eyebrow `COMPETITIVE INSIGHTS`, the week in large type, "This week's competitive intelligence report"; then **five stat tiles** (Companies, Competitors, Competitor updates, High threats, Opportunities).
2. **Executive summary** in a rounded box: *Bottom line:* (`executive_summary[0]`), then **Key takeaways**: one entry per `company_summaries[]` item = a company tag, a bold headline (`title`), and `what_matters` + `why` as one paragraph.
3. **Product and market insights** (`market_trends`), numbered 01, 02 ... with a hairline between.
4. **Your companies** (2 columns of outlined cards) and **Tracked competitors** (a company tag, the market, a count; then 3 columns of tiles).
5. **I. Key competitor updates** (count = every tracked competitor): by set, each competitor numbered `1.`, source markers `[1, 2]` after the name as links. A real update shows *What happened*, *Key facts* (bullets) and, on a light panel, *Why it matters to us* and *Our proposed response*. A quiet competitor is **one line**: `2. Ema [QUIET] Nothing material found this week.` Then **New entrants** (numbered, `WATCH` tag, company tag) and **What is working well** (numbered, company tag).
6. **II. Competitive threats**: by set, High to Low, numbered per company, `HIGH` / `MEDIUM` / `LOW` tag, *Why it is a threat*, *Potential impact*.
7. **III. Opportunities for us**: by set, numbered.
8. **IV. Recommended actions**: by company, High to Low, numbered, `HIGH PRIORITY` etc. tag, the reason, then `Owner: ..., by: ...`.
9. **Sources**: numbered `01`, label as the link, host on the right. Always last.

A section with nothing in it still appears, with one plain line ("No new entrants this week."). In the squeeze loop only (an oversize week), empty sections fold into one line and quiet competitors fold into one line per set.

## Type scale and colour

Week 24 pt bold · section heading 10.5 pt bold, letter-spaced capitals, count chip, rule · company heading 10 pt bold on a company tag · entry title 10-10.5 pt bold · labels 8.6 pt bold · body 8.6 pt on 10.9 pt leading (8.2 pt in the squeeze loop) · footer 8.2 pt. **No grey text anywhere**: body, labels, footer, source hosts and numbers are near-black (`#0D0D0D` / `#111111`). Colour appears only as a tile, a tag or a rule: one colour per company, amber for QUIET and MEDIUM, red for HIGH, green for LOW, blue for WATCH and counts. Margins 0.75 in left and right; the footer reads `Competitive Insights · <week>` on the left and `<company> · Page n of N` on the right.

Free text may carry `**bold**` markers (a competitor or company name at its first mention); the renderer prints them bold and never shows the asterisks, and the `.md` backup drops them.

## Payload

```json
{
  "title": "Competitive Intelligence Report", "week": "Sep 28 - Oct 4, 2026", "company": "<parent or own company>",
  "group": [{"name": "<own company>", "domain": "<its domain>", "description": "what it does"}],
  "sets": [{"key": "A", "entity": "<a group name>", "name": "...", "competitors": [{"name": "...", "description": "..."}]}],
  "executive_summary": ["the bottom line (one or two sentences)"],
  "company_summaries": [{"entity": "<a group name>", "title": "4-8 word headline", "what_matters": "...", "why": "..."}],
  "updates": [{"set": "A", "competitor": "...", "what": "3-5 sentences, specifics", "facts": ["date / price / limit"], "why": "...", "response": "next step", "sources": [1]},
              {"set": "A", "competitor": "...", "quiet": true}],
  "new_entrants": [{"entity": "<a group name>", "name": "...", "note": "...", "source": 3}],
  "working_well": [{"entity": "<a group name>", "title": "...", "body": "...", "source": 1}],
  "market_trends": [{"entity": "<a group name>", "title": "...", "body": "..."}],
  "threats": [{"set": "A", "title": "...", "level": "High", "why": "...", "impact": "..."}],
  "opportunities": [{"set": "A", "title": "...", "body": "..."}],
  "actions": [{"entity": "<a group name>", "action": "...", "reason": "...", "priority": "High", "owner": "Product", "by_when": "Oct 16"}],
  "sources": [{"label": "...", "url": "https://..."}]
}
```

Format gate (exit 6, every defect listed): all keys present (`new_entrants` may be an empty list); `group` not empty; every `sets[].entity` is a `group` name and **every group company has at least one set and one `company_summaries` entry**; every `entity` on `company_summaries`, `new_entrants`, `working_well`, `market_trends` and `actions` is a group name; every tracked competitor has an `updates[]` entry (a quiet one is `quiet: true`); `what` and `why` on every non-quiet update; `level` and `priority` in High/Medium/Low; every source has a label and an absolute `https` URL; at least one source. Characters outside the standard font's range print as `?` instead of failing.

## Depth floor (gate, exit 6 with a message that says what to add)

Non-quiet update: `what` 25 words, `why` 15. Threat `why` 12. Action `reason` 10. Working-well, market-trend and opportunity bodies 15 each. Each company summary (key takeaway) `what_matters` 12 words and `why` 6. Bottom line 25 words. `facts`, `response`, and an action's `owner` / `by_when` are optional but expected on any update with real news.

A fixture lives at `tests/fixtures/competitive_insights.json`.

# Follow-Ups summary email — format

The reader opens this to see what is ready to send. The **subject line** already carries the counts (`{N} new, {M} awaiting send, {P} flagged`) and the date, so the body does not repeat them: it opens straight on the follow-up content.

**No PDF, no attachment, no file of any kind.** The original skill forbids it: the email body plus the drafts in the Drafts folder are the whole deliverable. This file styles the body only. It does not touch the drafts, which are written in the user's own voice.

## Why only plain tags

The Microsoft 365 send tool strips every `style=`, colour, font size, border and background (tested; see `skills/daily-brief/daily-brief-email-format.md` §0). What survives: `h3`, `p`, `br`, `hr`, `strong`, `em`, `ul`, `ol`, `li`, `table/tr/td` and `a href`. **Never write a `style=` attribute.**

## Subject — unchanged from the original skill

```
Follow-ups ready for review — {N} new, {M} awaiting send, {P} flagged · {date}
```

- `N` = drafts created this run · `M` = earlier drafts still unsent · `P` = everything not drafted this run.
- All three numbers always appear, even at zero.
- Everything is zero → `Follow-ups checked — nothing open · {date}`.

## Body — four parts, in this order, nothing else

```html
<p><em>{Coverage line, one sentence: "{S} sent · {I} inbox · {window} · last 10 days fully covered, zero gaps" — or the exact gap}</em></p>
<hr>

<h3>Still open ({M})</h3>                              oldest first; omit if M = 0
<ol>
<li><p><strong>→ {Contact} — {topic}</strong><br>
{reason, one clause with a real date}<br>
<em>drafted {date} · still unsent · {n} business days · {High/Medium}</em></p></li>
</ol>

<h3>New drafts ({N})</h3>                               High → Medium → Low; list ALL, never "top 3"
<ol>
<li><p><strong>→ {Contact} — {topic}</strong><br>
{reason, one clause with a real date}<br>
<em>{High/Medium/Low} · reply on the {thread subject} thread</em></p></li>
<li><p><strong>{Contact} — {topic}</strong><br>
{reason}<br>
<em>{priority} · not drafted this run, draft cap reached</em></p></li>
</ol>

<h3>Needs your input ({n})</h3>                          omit if none
<ul>
<li><p><strong>{Contact} — {topic}</strong><br>
{what happened, one sentence, max 20 words}<br>
Next: {the one thing you need to do, max 15 words}<br>
<em>Not drafted · {reason, max 8 words} · {status}</em></p></li>
</ul>

<hr>
<p><strong>Nothing has been sent.</strong> Review, edit and send the drafts from your Drafts folder.</p>   drop the second sentence when there are no drafts
<p><em>allNeurons Productivity v{installed version} · Sent to {work address}</em></p>
```

## How the body is sent

Built by `assets/email_compose.py compose --kind follow_ups` and sent as composed, with **`bodyType: "html"`**. The send tool defaults to text; a body sent without it shows every tag. `validate` refuses a body whose counts do not match its lists.

## Rules

1. **Never rewrite content.** Contacts, topics, reasons and dates word for word. Only arrange.
2. **Counts must match the body.** Count the `li` items under each heading; the numbers in the subject must agree with them.
3. **Still open is ordered by age, oldest first.** Anything unsent 5+ business days sits at the top of the whole email.
4. **Only drafted items get `→`.** It marks "a draft is waiting for you". Cap-overflow items and needs-input items get none.
5. **Every item has three short lines** (four for Needs your input): bold contact and topic, one plain sentence of at most 20 words, then an italic meta line. Needs-your-input items add a plain "Next:" line before the meta line. Email addresses, dates and reasons that don't fit the sentence go in the meta line, never in a long paragraph.
6. **Leave out empty sections**, except the coverage line and the closing line, which always appear.
7. **No second header.** The body has no date line, no headline and no stat line. Earlier versions printed `Thursday, 1 October`, a headline such as `1 draft unsent for 13 business days` and a repeat of the counts (`0 new · 1 awaiting send · 2 flagged`) above the content — all of it already in the subject and the lists. It was removed in v1.9.8. The urgency the headline carried is now carried by order: **Still open comes first, oldest first**, with each item's age on its own meta line.
8. **Nothing outside the four parts.** No asides, no commentary, no "by the way".
9. **No raw URLs, no attachments.**

## Early exit (nothing to follow up)

```html
<p>Checked {X} threads over {N} days. Nothing needs a follow-up today. No drafts created.</p>
<p><em>allNeurons Productivity v{installed version} · Sent to {work address}</em></p>
```

Only when there is genuinely nothing, including no unsent drafts from earlier runs.

## Checklist

- [ ] No `style=` or other attributes except `href`
- [ ] The body opens on the one-line italic coverage statement — no date line, no headline, no stat line
- [ ] No item text runs past two lines; Needs-your-input items have a "Next:" line
- [ ] Closing is only "Nothing has been sent." plus the version and Sent to line; no extra explanation
- [ ] Subject counts = number of items listed
- [ ] Still open oldest first; 5+ day drafts at the top
- [ ] Every new follow-up listed, including cap overflow
- [ ] Closing line says nothing has been sent
- [ ] No attachment
- [ ] `bodyType: "html"` sent; the stored message reads back as formatted, not as visible tags

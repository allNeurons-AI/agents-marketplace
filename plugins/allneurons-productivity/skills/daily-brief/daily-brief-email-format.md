# Daily Brief email format — sanitizer-safe

## 0. Why this skill exists (read first)

The mail connector sanitizes HTML before sending (the tag allowlist below was verified on `outlook_send_mail`; Gmail accepts a superset, so one tag set is safe on both). Verified on 25 Sep 2026 by sending a probe and reading the stored message back:

| Survives | Stripped |
|---|---|
| `h1` `h2` `h3` `h4` `p` `br` `hr` | **every attribute** except `href` — `style`, `bgcolor`, `width`, `border`, `cellpadding`, `color`, `class` |
| `strong` `b` `em` `i` `code` `pre` | `small` `u` `font` `mark` `sub` `sup` `span` `div` |
| `ul` `ol` `li` | `blockquote` `dl` `dt` `dd` |
| `table` `thead` `tbody` `tr` `th` `td` | `style` blocks, images |
| `a href="…"` | |

**So: hierarchy must come from tags, not CSS.** Any inline style, colour, font size, border, background or width you write is silently deleted and the email collapses into flat same-size text. Never write a `style=` attribute — it is wasted bytes.

What each surviving tag gives you in Outlook / Gmail by default:

| Tag | Renders as | Use for |
|---|---|---|
| `h3` | medium bold (~14–15px) | the headline (first) and the section headings |
| `strong` | bold | the action sentence of an item; stat numbers; meeting times |
| `em` | italic | owner / deadline / source line; meeting details; footer |
| `ul` / `ol` + `li` | real bullets / numbers, indented | items and lists |
| `hr` | thin grey rule | between header, sections, footer |
| `table` + `th`/`td` | aligned grid, no borders | the stat strip and meeting schedule |
| `code` | monospace | never in a brief (reads as technical) |

Do not use `h1`/`h2` (too loud for a short email) or `h4` (same size as body text in Outlook).

## 0b. How the body is sent (the rule that was broken)

The Outlook send tool treats the body as **plain text unless `bodyType` is `"html"`** (set it on Gmail sends too, wherever the tool has the field). Pass `bodyType: "html"` on every send, scheduled or manual. A body that reads back with visible `<h3>` / `<p>` characters was sent as text and is a failed send. `assets/email_compose.py` builds the body from this format and returns the full argument object, `bodyType` included; `validate` and `stored` check it before and after the send.

## 1. Rules

0. **No date line at the top.** The email opens with the headline `h3`. The date is already in the subject (`Daily Brief — {Weekday}, {Month D}`) and the inbox row; printing it again as the first line of the body (`Thursday, October 1`) was removed in v1.9.8. The same applies to every email this plugin sends.

1. **Never rewrite content.** Facts, names, times, quotes, sources word for word. Only arrange.
2. **Fixed order** (section 2). Never reorder or add sections.
3. **Hierarchy by position, not size.** The headline is an `h3`, the same size as section headings. It leads because it comes first and stands alone, not because it shouts. Never use `h1`/`h2`; they swamp a short email.
4. **Three levels of emphasis, max:** `h3` > `strong` > plain > `em`.
5. **Status via wording, not colour.** Colour is impossible through this tool, so status goes in the heading or the meta line.
6. **Empty sections fold** into one plain line (Conflicts, Due). Other empty sections are left out.
7. **No attributes** except `href`. No `style`, no `class`, no `bgcolor`.
8. **No raw URLs.** The link text is the filename.
9. **The email is the summary; the PDF is the design.** Rich layout (cards, colour, timeline) lives in the PDF. See the `daily-brief-pdf-design.md` (in this skill's folder).

## 2. Structure — exact order

```
<h3>{Summary headline}</h3>                              headline
<p>{stat line}</p>                                       counts, one line
<hr>
<h3>Today's meetings</h3>
<table> schedule: upcoming → passed → canceled </table>
<h3>Needs attention ({n})</h3>
<ol> action items </ol>
<p>{Conflicts sentence} · {Due sentence}</p>            fold line, only when both are empty
<h3>Worth double-checking ({n})</h3>                     omit if empty
<ul> items / notes </ul>
<h3>Resolved ({n})</h3>                                  omit if 0
<ul> items </ul>
<hr>
<p>Full brief ({p} pages): <a href="{url}">{filename}</a></p>
<p><em>{version line} · Sent to {email}</em></p>
```

**Today's meetings comes first, right after the stat line** — matching this skill's own *Sections — fixed order* in SKILL.md and the client requirement that meetings appear at the beginning, followed by the remaining sections. The PDF renderer already draws meetings first; the email must match it rather than drifting into its own order.

If Conflicts or Due has items, it becomes a full `h3` section (same style as Needs attention) placed right after Needs attention, and drops out of the fold line. Today's meetings is never moved by this rule — it always stays first, immediately after the stat line.

## 3. Components

### 3.1 Stat line (not a table)
A table of counts collapses because cell padding is stripped: the labels run together and the numbers drift off their labels. Use one line instead. Bold only the non-zero counts, and keep this order: Needs attention · Conflicts · Due · Resolved.

```html
<p><strong>3 need attention</strong> · 0 conflicts · 0 due · 0 resolved</p>
```

For singular counts write "1 needs attention" and "1 conflict".

### 3.2 Action item (Needs attention, Conflicts, Due)
One `li` per item inside an `ol`. **Wrap the item's lines in a `<p>` inside the `<li>`.** Paragraph margins survive the sanitizer, so each item gets breathing room without empty rows. Start the action with `→ `, the one permitted marker (no `■`, `●` or emoji).

```html
<li><p><strong>→ {Action sentence}</strong><br>
{Detail sentence(s)}<br>
<em>Owner: {name} · {deadline} · {source}</em></p></li>
```

- Strip `[Open]` / `[Needs confirmation]` from the action line. If the status matters beyond the section heading, append it to the meta line: `· Needs confirmation`.
- Skip the detail line if it is empty.

### 3.3 Worth double-checking
Same item shape in a `ul`. A coverage note that is not a task (e.g. "No ticket tracker is connected…") is a single `<li><p><em>{note}</em></p></li>` at the end.

### 3.4 Meetings
The time and title go on one line and the details go on the next, so the times sit level with the titles. Pad the time cell with four `&nbsp;` so the time never touches the title. Order the rows **upcoming → passed → canceled** (chronological within each group), so any live meeting is always first.

```html
<table>
<tr><td><strong>9:45–10:05 pm</strong>&nbsp;&nbsp;&nbsp;&nbsp;</td><td>Daily Dev Sync<br><em>14 attendees, organizer Chris · Microsoft Teams or Google Meet · already passed</em></td></tr>
</table>
```

### 3.5 Resolved
A plain `ul`, one line per item, no bold.

### 3.6 Footer
The link line (the `.pdf` only — never a `.md` path), then one italic line: `allNeurons Productivity v<installed version>` and "Sent to". Leave out notes about the tool itself (e.g. "the mail tool cannot attach files"); they aren't something the reader acts on.

## 4. Text rules

- Times: `1:00–1:30 am`, with an en dash, lowercase am/pm, and the local timezone as the skill output it.
- Full name on first mention, first name after.
- Subject line unchanged: `Daily Brief — {Weekday}, {Month D}`.
- Bold only the action sentence, non-zero counts and meeting times. Nothing else.
- Italic only meta lines, meeting details and footer.

## 5. Full template

```html
<h3>{headline}</h3>
<p><strong>{n} need attention</strong> · {n} conflicts · {n} due · {n} resolved</p>
<hr>
<h3>Today's meetings</h3>
<table>
<tr><td><strong>{start–end}</strong>&nbsp;&nbsp;&nbsp;&nbsp;</td><td>{title}<br><em>{details}</em></td></tr>
</table>
<h3>Needs attention ({n})</h3>
<ol>
<li><p><strong>→ {action}</strong><br>{detail}<br><em>Owner: {name} · {deadline} · {source}</em></p></li>
</ol>
<p>{No scheduling conflicts today.} · {Nothing due today and nothing overdue.}</p>
<h3>Worth double-checking ({n})</h3>
<ul>
<li><p><em>{coverage note}</em></p></li>
</ul>
<hr>
<p>Full brief ({p} pages): <a href="{url}">{filename}</a></p>
<p><em>{version line} · Sent to {email}</em></p>
```

## 6. Checklist before send

- [ ] Zero `style=`, `class=`, `bgcolor=`, `border=`, `width=` attributes anywhere
- [ ] No stripped tags (`span`, `div`, `small`, `font`, `blockquote`, `u`, `mark`)
- [ ] No `h1`/`h2`; the headline is the first `h3`
- [ ] Stat line in order: Needs attention · Conflicts · Due · Resolved, with only non-zero counts bold
- [ ] Every `li` wraps its lines in a `<p>`; every action starts with `→ `
- [ ] Today's meetings is the first `h3` section, right after the stat line — never after Needs attention
- [ ] Meeting time cells padded with `&nbsp;`; rows ordered upcoming → passed → canceled
- [ ] Every action item = bold action / detail / italic meta
- [ ] Count in each `h3` matches the number of `li` under it
- [ ] Empty Conflicts + Due folded into one line; other empty sections omitted
- [ ] No raw URLs visible
- [ ] Content word for word

## 7. If richer visuals are required

Coloured card borders, grey stat boxes and custom font sizes are **not achievable through the mail connector** — the sanitizer is on the tool side, not in the mail client. The only routes to them are (a) a different send path that does not sanitize (e.g. Graph `sendMail` called directly, or an SMTP relay), or (b) putting the rich layout in the PDF, rendered by the `daily-brief-pdf-design.md` (in this skill's folder), and keeping the email as the sanitizer-safe summary above. Prefer (b).

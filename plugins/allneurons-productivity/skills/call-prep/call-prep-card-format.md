# Call Prep card — format

The card is read on a phone, five minutes before a call. The reader should find the one thing to do in 5 seconds. It goes in the **body of the prep block** on the calendar. It follows the same house format as every other email and document (`references/run-policy.md` §11): the one set of tags below, the same hierarchy, no date line at the top.

## How the body must be sent — the rule that was broken

`outlook_create_event` and `outlook_update_event` treat the body as **plain text unless `bodyType` is `"html"`**. Earlier versions never set it, so the calendar showed the raw markup (`<p><em>…</em></p><h3>…`) instead of a formatted card. That was the "unformatted Call Prep" defect.

1. **Every create and every update of a prep block passes `bodyType: "html"` together with the HTML body below.** `bodyType` is required on an update whenever `body` is supplied, so an existing event is never downgraded to text.
2. **After the create or update, read the event back** (`outlook_calendar_search` for the call key, or `read_resource` on the event) and check the stored body: it must start with a real element, and must contain no literal `&lt;p&gt;`, no visible `<p>`/`<h3>` characters and no `bodyType`-style escaping. A body that reads back as visible markup is a failed booking — update that same event once with `bodyType: "html"`; still wrong → use the plain-text layout below and say so in the run log.
3. **The plain-text layout is only for a calendar tool that rejects `html`.** It is never the default and never sent as HTML-looking text.

## Why only plain tags

The Microsoft 365 tools strip every `style=`, colour, font size, border and background. See `skills/daily-brief/daily-brief-email-format.md` §0 for the tested list. What survives: `h3`, `p`, `br`, `hr`, `strong`, `em`, `ul`, `ol`, `li`, `table/tr/td` and `a href`. **Never write a `style=` attribute.**

## Structure — exact order

```html
<h3>{Person} ({Company}) · {Meeting name}</h3>                      header line 1
<p><strong>{Whose call} · {your role} · {start–end}</strong></p>    header line 2
<hr>
<h3>Before you join</h3>
<ul>
<li><p>{fact} <em>[{source}]</em></p></li>                          up to 2
</ul>
<h3>Your move</h3>                                                   omit if nothing is owed
<ul>
<li><p><strong>→ {what you owe or must decide}</strong> <em>[{source}]</em></p></li>
</ul>
<h3>Open with</h3>
<p><em>"{one sentence you could say out loud}"</em></p>
<h3>Ask</h3>                                                         omit if there's no real question
<p>{one question}</p>
<hr>
<p>Full briefing: <a href="{verified webUrl}">{filename}.pdf</a></p>        the read-back-verified link, filename as text
<p><em>allNeurons Productivity v{installed version}</em></p>          the skill version, on every prep block
<p><em>ref: call-prep/{call key}</em></p>                 always last, one line
```

**The version line.** Every prep block names the plugin version that booked it, so a block on the calendar says which release made it (the same `allNeurons Productivity v<X.Y.Z>` every email already carries). The value is the version the run confirmed in shared §1 step 2a (`1.15.0`, or `(unknown)` when `plugin.json` could not be read). It is the card's `version` field; `call_prep_card.py compose` refuses a card without one and `audit` fails a stored block that lacks the line (an older block is repaired in place on its next update). It sits **just above** the `ref:` line, which stays last.

**There is no date or meta line above the header.** The event already sits on its date, and the time is in header line 2. For a block booked for a day other than today, header line 2 reads `{Whose call} · {your role} · {Day D Mon}, {start–end}`.

### Internal meetings (scope includes internal)

An internal meeting uses the **same card, the same order, the same tags**. Only the content differs:

- Header line 1: `{Organizer} (Internal) · {Meeting name}` — or `{Organizer} + {N} others (Internal) · {Meeting name}` when more than two people are on it.
- Header line 2: `{Whose call} · {your role} · {start–end}` — exactly as for an external call.
- *Before you join* draws on the last occurrence, the thread or ticket the meeting is about, and open decisions; *Your move* is what you owe the group. Nothing is borrowed from an external account's history.
- A recurring internal meeting still gets a block, focused on **what changed since the last occurrence**.

## If the calendar tool only takes plain text

Used only when `bodyType: "html"` is rejected (rule 3 above). Keep exactly the same order and words. Put each label on its own line, start bullets with `• `, start the Your move line with `→ `, wrap the Open with sentence in quotes, and leave one blank line between blocks. The card still ends with the Full briefing line, the version line and then the `ref:` line.

## Rules

1. **Never rewrite content.** Facts, names, times and sources word for word. Only arrange.
2. **Labels are sentence case** ("Before you join"), never ALL CAPS.
3. **Only "Your move" is bold with `→`.** It's the one thing to act on.
4. **Sources are italic and in brackets, at the end of the line**: `[Teams, 26 Sep]`.
5. **"Open with" is the only italic sentence** and has no source.
6. **Leave out empty blocks.** Never write "no prior record" or "goal: none stated".
7. **No raw system values.** Write "still unanswered", not `needsAction`.
8. **No raw URLs.** The link text is the PDF filename.
9. **The `ref:` line is always last**, italic, one line, with the `allNeurons Productivity v<version>` line just above it.
10. **Under 200 words** for the whole card.
11. **No date or meta line at the top.**
12. **`bodyType: "html"` on every create and update**, then read back.

## Subject (event title or failure email)

- Prep block title: `Review call prep notes for {meeting name}` (the title the skill already books; the person and time are inside the card)
- Failure email: `[Failed] Call prep — {what broke, in five words}`

## The link is audited in the stored notes

`assets/call_prep_card.py compose` writes the Full briefing line from the verified `webUrl` only (a local, sandbox or non-https path is refused), and `audit` re-reads the event and fails unless the stored notes hold that exact link, the filename as link text, the `allNeurons Productivity v<version>` line, the `ref:` line last and no visible markup. A card written without a verified URL says the briefing could not be linked and names where the PDF is saved; it never shows a fake link.

## Checklist
- [ ] `call_prep_card.py audit` passed on the notes read back from the calendar (link present and equal to the verified webUrl)

- [ ] `bodyType: "html"` was sent, and the read-back shows a formatted body, not visible tags
- [ ] No `style=` or other attributes except `href`
- [ ] No date or meta line above the header
- [ ] Header is two lines: who and what, then whose call, your role and the time
- [ ] "Your move" is the easiest thing to find
- [ ] Every fact has a source tag on the same line
- [ ] Empty blocks removed; nothing announces a missing fact
- [ ] PDF linked by filename; the `allNeurons Productivity v<installed version>` line is present; `ref:` line last

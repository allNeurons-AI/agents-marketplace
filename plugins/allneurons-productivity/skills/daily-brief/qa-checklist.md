# Daily Brief — QA checklist

Run top to bottom before the email goes. Any unticked box is fixed first, or reported as a gap in the closing line. This is the same list as SKILL.md "Final check"

## Content
- [ ] Every meaningful open item, commitment and pending response found is in the brief, including undated tracker items.
- [ ] Every pending item traces to a message, ticket or event read this run.
- [ ] Already-done check: nothing is Open without looking at what the user sent themselves; otherwise it is tagged Needs confirmation.
- [ ] Every status reflects a check against the whole batch, not the first mention.
- [ ] Every actionable item names what, who owns it, and by when (no banned vague phrasing).
- [ ] Every claim's source is in `sources`.
- [ ] Every meeting's start, end and duration match the event record, in the user's local timezone. All-day events say so.
- [ ] The brief says what needs attention and what to do next.

## Delivery
- [ ] The renderer exited 0 (or 6 was fixed and re-run once).
- [ ] `verify_pdf.py <file>.pdf` printed `"ok": true`.
- [ ] The file being attached and uploaded ends in `.pdf`. The `.md` is not attached, uploaded, linked or named anywhere.
- [ ] The upload's returned name ends in `.pdf` and its size equals the `bytes` printed by the gate.
- [ ] The email goes to the user's own address only, exactly once.
- [ ] The email carries the full content and the Drive link to the PDF.
- [ ] The closing line reads `allNeurons Productivity v<installed version>`.
- [ ] Phase 2 (read phase) ran: shortlisted email threads (≤10) and chat messages (≤8) were opened with `read_resource`; coverage note states *read N of M*, never a bare "no thread was read"
- [ ] The inbox was listed (no `?` query) and chat swept with `*`

## Email format
- [ ] Built by `email_compose.py compose --kind daily_brief`; `validate` exited 0.
- [ ] Sent with `bodyType: "html"`; the read-back passed `email_compose.py stored`.
- [ ] Today's meetings is first, with one row per meeting; the PDF opens it with the calendar day line.

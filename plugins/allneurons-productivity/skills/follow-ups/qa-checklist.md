# Follow-Ups — QA checklist

Run before any draft is created and again before the summary email is sent.

## Before drafting
- [ ] Coverage: the last 10 calendar days were read with pagination followed to the end.
- [ ] The recipient's latest message on the thread was read in full (not a snippet) before any ask for a time, decision or document.
- [ ] The recipient address comes from the specific thread's headers, and its domain matches the company the item is grouped under.
- [ ] An unsent draft did not suppress an item; a deleted or declined thread was skipped (no new activity).

## Each draft
- [ ] It is a reply on the real thread, saved as a draft. Nothing is sent to anyone.
- [ ] It matches the user's writing fingerprint and lifts their signature verbatim.
- [ ] Nothing is half-finished; no placeholder text remains.
- [ ] Read back clean: no leading whitespace (`draft_sanitize.py check`), signature text intact, signature image attached or reported as not included.
- [ ] It does not ask for information the thread already contains.

## Summary email
- [ ] One email, `bodyType: "html"`, to the user's own work address only.
- [ ] Fixed structure, ranked with a stated reason.
- [ ] Footer reads `allNeurons Productivity v<installed version> · Sent to <work address>`.

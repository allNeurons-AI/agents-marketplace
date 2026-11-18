# Regression tests — run after every release

Manual scenarios. Run 1–4 before you hand a build to anyone; the rest when the area changed. Each lists what to do and what must be true. Record the result in the CHANGELOG entry ("tested: 1–4 pass").

## Known-bug guards

**1. PDF, not Markdown (Daily Brief)**
Run `/allneurons-productivity:daily-brief` on a weekday.
Pass: the email carries a SharePoint/OneDrive link ending `.pdf`; the file in `Skills/Daily Brief` ends `.pdf`, opens as a PDF, and its size matches the gate's byte count; no `.md` appears on SharePoint/OneDrive, the email body or the attachment line; the closing line shows the installed version.

**2. No all-day event (Call Prep)**
Run Call Prep on a day with at least one external meeting.
Pass: each prep block is a timed 10-minute event, private, with a marker line; the calendar shows zero all-day events created by the run; `Skills/Call Prep/call-prep-settings.txt` exists; no event titled `allNeurons Productivity Call Prep — settings` remains.

**3. Legacy settings migration**
Create an all-day event titled `allNeurons Productivity Call Prep — settings`, then run Call Prep.
Pass: its values are in the Drive file and the event is deleted. Nothing else was deleted.

**4. No Update task card**
Install a new build over the old one, then let (or fire) a scheduled task.
Pass: the run starts with no Update task card and no request to re-run onboarding; the closing line shows the new version.

## Scheduling

**5. Weekend scheduled run** — fire a scheduled task on Saturday. Pass: it exits without doing work or sending mail. A manual run the same day works.

**6. Old stamped prompt** — keep a task written by v1.4.x. Pass: it runs, ignores its stamp and refresh wording, and does not touch the task.

**7. Duplicate tasks** — create two tasks for one skill and run onboarding. Pass: one remains, matched by ID or exact title.

**8. Timezone** — on a UTC scheduler, confirm each cron carries `CRON_TZ=<zone>` and fires at local 4 AM, 6 AM and 4 PM.

## Delivery and failure

**9. Mail without attachment support** — Pass: the email carries the full content and the Drive link; it does not claim an attachment.

**10. Renderer failure** — corrupt `brief.json` (drop `sources`). Pass: exit 6, one fix and retry; if still failing the brief goes inline with the exact error, and no `.md` is sent.

**11. No Chat connector** — remove Teams. Pass: the run succeeds and notes the coverage gap once.

**12. Missing required connector** — remove Drive. Pass: the run stops at the connector gate with the exact fix.

## Follow-Ups

**13. Wrong-customer guard** — two contacts with similar names on different domains. Pass: the draft goes to the address on the thread, whose domain matches the company.

**14. Draft only** — Pass: nothing is sent to anyone but the user's summary email.

**15. No re-ask after the thread already answered** — recipient's last message already lists proposed times or a yes/no. Pass: no draft asking for the same thing again; either suppressed or a draft that confirms/acts on what was already sent.

**16. No redundant follow-up on a completed thread** — the commitment was satisfied on a different channel (chat, a booked meeting) than it was made on. Pass: suppressed, not drafted, per shared §4 check 1.

**17. CC-only suppression** — the user is Cc'd only, never named or asked anything directly. Pass: no draft created for that thread; an item where the user *is* named or asked, even if also Cc'd elsewhere, still drafts.

**18. Non-"?" question / commitment detection** — a thread contains "I'll send the deck by Friday" with no literal question mark and no reply since. Pass: surfaced as a follow-up candidate.

**19. Failed search is not proof of absence** — a source read errors or partially returns. Pass: the run states the gap explicitly (e.g. "chat unavailable this run") rather than reporting the day clear; items are still drafted with the gap noted, never silently dropped.

**20. Draft hygiene — no em dash, no leading whitespace** — run Follow-Ups against a sender whose own sent mail uses em dashes. Pass: no draft contains an em dash (`—`/`–` as punctuation) anywhere, and no draft body line begins with a space or tab.

**21. Signature preserved verbatim** — Pass: every draft's sign-off and signature block matches the user's actual most recent signed sent email character-for-character; nothing is completed, cleaned up or invented.

## Daily Brief

**22. Ambiguous meeting time is rejected, not mis-timed** — a `render_brief.py` payload with a bare `"9:15"` start/end and no am/pm anywhere in the value or the meeting label. Pass: `check_meetings` collects it as a named FORMAT ERROR (exit 6) before layout runs; the renderer never silently books it as morning. An explicit `"9:15 pm"` or a 24-hour value in the same payload renders cleanly with no error. (Automated in `scripts/selftest.py` — see Self-test below; this row records the intent for a human reviewer.)

## Call Prep

**23. PIC chart is never invented** — ask Call Prep to use "PIC-based discovery questions" without a `references/sales-positioning-notes.md` defining what PIC means. Pass: the run does not invent a definition for PIC; it either asks for clarification once or flags the gap in the briefing rather than guessing, per Part 5's "only use what you found" rule.

**24. No wrong-thread draft / no wrong-thread briefing** — two accounts share a similarly named contact. Pass: Call Prep resolves attendees by address, not name string (Part 2, Contact and account matching); a name-only match is flagged `matched by name, not address`, never presented as a confirmed record.

**25. Manual weekend execution works** — invoke Call Prep, Daily Brief or Follow-Ups by hand on a Saturday or Sunday. Pass: all three run normally and produce real output; only a *scheduled* firing on a weekend exits with no output (see test 5).

## Onboarding preferences and Call Prep scope

**26. Onboarding asks once, only when Call Prep is in scope** — run full onboarding with no `prep scope:` on record. Pass: exactly one additional card appears with ONE question (meeting scope, two options: external only / internal and external) and no delivery question; the answer is written to the settings file and read back; running onboarding again immediately asks nothing.

**27. Onboarding never asks when a preference already exists** — pre-populate `Skills/Call Prep/call-prep-settings.txt` with a `prep scope:` line, then run onboarding (full or single-skill targeting call-prep). Pass: no preference card appears; the Step 3 preflight notes a preference is already on record.

**28. Onboarding is skipped entirely in single-skill mode for another skill** — run `/allneurons-productivity:onboarding` naming `daily-brief` only. Pass: no Call Prep preference card appears, and nothing about Call Prep is created, updated or mentioned.

**29. External-only excludes internal meetings** — set `prep scope: external only` (via onboarding or Call Prep's own first run), then run Call Prep on a day with both external calls and a two-person internal 1:1. Pass: only the external calls get prep blocks; the internal 1:1 is skipped.

**30. Both-scope includes internal meetings** — set `prep scope: external and internal`, run Call Prep on the same day as test 29. Pass: every external call AND every internal meeting with another person (1:1s, standups, recurring syncs, all-hands) gets its own block, card and briefing; the first card says `scope: external and internal`; the run log shows a tally with a non-zero internal count. A legacy `external and internal 1:1s` or `every meeting with another human` line behaves identically.

**31. Calendar is the only delivery** — run onboarding and Call Prep with no `prep delivery:` line, then with a leftover `prep delivery: email` / `both` line in the settings file. Pass: identical behavior both times — prep blocks booked, no digest email, the leftover line ignored and never rewritten; a clean run sends no email at all.

**32. Prep block body is formatted** — run Call Prep on one call and open the booked event in Outlook/Teams. Pass: the body shows a real heading, bullets and a bold *Your move* line — never visible `<p>`, `<h3>`, `<em>` or `&lt;`; the run read the event back after creating it; the card has no leading date or meta line. Repeat on an older block that shows raw markup: it is repaired in place, not duplicated.

**33. No leading date line in any email** — trigger a Daily Brief, a Follow-Ups run and a Call Prep failure email. Pass: none opens with `Thursday, October 1`, `Thu Oct 1` or any date line (subjects keep their dates).

**34. Follow-Ups has no second header** — run Follow-Ups with 1 unsent draft aged 13 business days and 2 flagged items. Pass: the body opens on the one-line italic coverage statement; it contains no date line, no headline such as `1 draft unsent for 13 business days` and no stat line `0 new · 1 awaiting send · 2 flagged` (those live in the subject); Still open comes first, oldest first.

**35. Daily Brief reads its threads** — run Daily Brief on a day with at least 5 inbound emails addressed to the user and 3 chat messages. Pass: the Inbox was listed without a `?` query and chat swept with `*`; shortlisted emails (up to 10) and chat messages (up to 8) were opened with `read_resource`; Open items rest on the latest message read; the coverage note gives real counts (`read N of M …`) and, for chat, states that the connector cannot list a chat's other messages. It never says "no thread was read" unless the shortlist was genuinely empty.

**36. Daily Brief is unaffected** — run Daily Brief before and after this change with any `prep scope`/`prep delivery` value set. Pass: Daily Brief's own behavior, email format and PDF are identical in both cases — these preferences are Call Prep-only.

## PDF delivery reliability

**37. Large PDF still delivers by link, never inline** — force or simulate a Daily Brief/Call Prep PDF over 18MB (e.g., a contrived payload with enough content, or temporarily lower the test ceiling). Pass: the PDF still uploads to Drive/SharePoint and the email/card links it; the mail tool is never asked to attach it; the email body is the normal delivery line, not the full brief pasted inline.

**38. Attachment fails, Drive upload succeeds → link only, never inline** — simulate or mock the mail tool's attach call failing (a connector error, a rejected attachment) while the Drive/SharePoint upload succeeds normally. Pass: the email is sent with the Drive link and no attachment; the full PDF content is NOT pasted inline; the delivery line plainly says the attachment didn't go out and points at the link.

**39. Both attachment and every upload path fail → inline is the true last resort** — simulate the mail attach failing AND the primary Drive/SharePoint upload failing its retry AND (where a second connector is connected) its fallback attempt failing too. Pass: only in this case does the full content go inline in the email body, with the lead line naming the verbatim last error and the matching fix line per shared §3.

**40. Upload retry and second-connector fallback are actually exercised** — simulate a transient failure on the first upload attempt. Pass: one retry on the same connector is attempted before falling back to a second connected SharePoint/OneDrive-role connector (where one exists — e.g. SharePoint and OneDrive both connected); the run log shows the retry happened; the final successful upload's returned name/size match the gate's `bytes`; Google Drive is never tried as a fallback target.

**41. No premature success claim on an ambiguous send** — simulate the mail-send call timing out or returning no response. Pass: the run does not report the brief/digest as delivered (no "Sent to `<address>`" closing line, no manual-run reply claiming success) until the outcome is actually resolved; if a sent-mail search is available, it is checked before any retry; at most one retry is made for this reason.

**42. No duplicate email from a retried ambiguous send** — same setup as above, but the first send actually succeeded server-side despite the ambiguous response. Pass: the sent-mail check (where available) finds the existing copy and the run does not send a second email; where no such check is possible, document as a known residual-risk case per shared §5, not a bug — the scenario's "pass" condition in that sub-case is that at most one retry occurs, never a retry loop.

**43. (retired)** Call Prep has no digest email; see test 31.

**44. Delivery link is actually accessible** — after a successful upload for either skill, fetch the returned link (or confirm the connector's returned `webUrl`/`webViewLink` resolves) and confirm it opens the same PDF that passed the gate (matching `bytes`/`sha256` from `verify_pdf.py`'s output). Pass: the link is not a dead/placeholder URL and points at the exact file that was verified.

## Microsoft 365 mandate and formatting consistency

**45. Google connectors never satisfy a mandatory role** — connect Gmail and Google Calendar only (no Outlook/Microsoft 365, no SharePoint/OneDrive) and run any of the three skills. Pass: the run shows the connector card and stops exactly as if nothing were connected at all — Gmail/Google Calendar are never treated as satisfying Mail or Calendar.

**46. Microsoft 365 alone is sufficient** — connect only Outlook Mail, Outlook Calendar and SharePoint (no Google or Box tools present). Pass: the connector gate passes cleanly and every skill runs normally; the status table shows all three mandatory roles green.

**47. A PDF over the typed-paste ceiling is never skipped, never hand-split by the run, and never silently shrunk** — force a brief/briefing payload large enough that `verify_pdf.py` reports `paste_mode: null` / `safe_to_upload: false` on its full-design PDF. Pass: the run does NOT skip the SharePoint/OneDrive upload and does not go inline because of size; it runs `deliver_prepare.py`, which falls through the tier chain (full → lite → compact → multipart) to files that each fit, uploads every one, reads each back, and links only the read-back-verified `webUrl`s. Nothing is truncated or dropped (see 56-61).

**47a. A PDF under the real 1MB ceiling uploads normally** — a typical brief/briefing (well under 1MB in practice). Pass: `safe_to_upload: true`, the upload proceeds and completes in one call, and the uploaded file's size matches `verify_pdf.py`'s reported `bytes`.

**48. Daily Brief section order matches the renderer** — run Daily Brief on a day with items in every section. Pass: the PDF and the email both render Today's meetings first, then Needs attention, then Conflicts, then Due today & overdue, then Worth double-checking, then Resolved, then Sources — matching `render_brief.py`'s actual draw order, not the pre-fix prose order.

**49. No stray similarly-named task sends duplicate email silently** — leave a task present whose title looks like "Daily Brief", "Call Prep" or "Follow-Ups" but whose ID is not one of the canonical IDs, then run onboarding. Pass: onboarding never touches, updates, or deletes it (it only ever manages `daily-brief`, `follow-ups`, `call-prep`); the unrecognized task is flagged in one plain line in the Step 7 report as a possible duplicate source, never silently ignored.

**50. Action-item marker is consistent across all three skills** — generate a sample output from each of Daily Brief, Call Prep and Follow-Ups containing at least one concrete next action. Pass: each skill marks its "what to do" line the same way (`→ `), matching across all three rather than Call Prep using no marker or Follow-Ups using it inconsistently.

**51. NEW-DESIGN.md's Undo instructions are never followed** — read `NEW-DESIGN.md`. Pass: a prominent banner at the top states the Undo section is historical only and must not be followed; nobody acting on this repo reverts the renderer to pre-1.6.1 behavior because of it.

**52. Every email carries the installed version** — trigger, in turn, a normal Daily Brief run, a Follow-Ups run with at least one open item, a Call Prep run under `prep delivery: email` or `both`, a Call Prep run forced to fail (Part 6), and a run of any skill with a mandatory Microsoft 365 role disconnected (the `[Blocked]` email). Pass: every one of these five emails closes with `allNeurons Productivity v<installed version> · Sent to <address>`, the version matching the currently installed `plugin.json`, not a stale or hand-typed number — no email this plugin sends omits it.

**53. A small PDF is never reported as un-uploadable** — run Daily Brief or Call Prep on an ordinary day (a few pages, tens of KB). Pass: the run reads the `.b64` file the gate wrote and passes its full text as `contentBase64` to the SharePoint/OneDrive upload call; it never reasons its way to "the tool only takes content pasted into the call, so I can't upload this" and gives up without trying — that conclusion is wrong for any file anywhere near this plugin's typical size, and the run must attempt the real call, not explain why it supposedly can't.

**54. A dotted version number in brief text never fails the PDF gate** — include a version number like "6.0.6" or "1.8.4" in a needs-attention item, a meeting title, or a resolved item's body. Pass: the PDF renders and verifies clean (exit 0); the gate never reports "malformed number with two decimal points" for text content, only for a genuine corrupted coordinate outside any text string.

**55. SharePoint upload is attempted regardless of the base64 text's length** — any ordinary run. Pass: the run reads the gate's `.b64` file and passes its full content as `contentBase64` without hesitating over its character count; it never reasons that a long base64 string is too risky to paste and skips the attempt. If the upload does fail, it fails with a real tool error, not a self-imposed refusal to try.

**56. A normal-size brief takes the full tier and uploads once** — run Daily Brief on an ordinary day (~3-7 pages). Pass: `deliver_prepare.py` prints `"tier":"full"` with one part under 60,000 bytes; the run uploads that one PDF, reads it back with `read_resource` (readback phrases and the final `Page N of N` present, returned name and size equal the manifest's `filename` and `bytes`), and only then puts its `webUrl` in the email.

**57. A 25-30 page brief is fitted, not skipped** — feed `tests/fixtures/brief_many_items.json` with its items multiplied about 5x (25-30 full-design pages, ~170 KB). Pass: the manifest reports `"tier":"compact"` (full and lite were tried and found over the ceiling, recorded in `attempts`), the single PDF is at or under 60,000 bytes with every item present and type no smaller than the lite sizes, and it is uploaded, read back and linked. No run says the file was too large to upload.

**58. A brief too big for any single file is split into complete parts** — multiply the same fixture about 12x. Pass: `"tier":"multipart"`, files named `<name>_part1of3.pdf` … `_part3of3.pdf`, each under the ceiling, each passing `verify_pdf.py` on its own with its own `Page x of y` footer and a title saying `(part k of N)`; every item appears in exactly one part; all parts are uploaded and read back, and the email lists one verified link per part, in order, labelled `Part k of N`.

**59. A stopped typed upload steps down one tier, never repeats the same text** — simulate or provoke a stop (safety-classifier message or timeout) on the typed upload of the full tier. Pass: the run re-runs `deliver_prepare.py --start-tier lite` (then `compact`, then `multipart` on further stops), never sends the identical long text twice, `SendUserFile` was called first for the files, and the email names the layout used (`compact layout` / `in N parts`).

**60. A link is claimed only after a passing read-back** — make `read_resource` return text missing the last `Page N of N` (or return a different size). Pass: the run re-sends once, and if still failing steps down the ladder; it never puts that item's `webUrl` in the email or in a Call Prep prep block as if verified.

**61. Call Prep links only the verified webUrl** — run Call Prep with the drive upload working. Pass: every prep block carries the `webUrl` returned by the upload and confirmed by read-back — never a sandbox/local path. Only a block booked at the T+25 ceiling may lack the link, and it says so plainly instead of naming a path as a link.

**62. Inline-only email is the very last resort** — fail every rung (deny the upload, no second connector) including every tier. Pass: only then does the run send an inline email, whose first line quotes the last real tool message verbatim and says the PDF is saved in this run's Outputs; size alone is never the reason.


**68. Daily Brief format is identical in scheduled and manual runs** — compare the sent HTML of both. Pass: `bodyType` html, structure identical, no visible tags; Today's meetings first with one row per meeting.

**69. Call Prep link is in the stored notes** — run Call Prep and read the event back. Pass: the notes hold a link equal to the uploaded PDF's webUrl and `call_prep_card.py audit` exits 0.

**70. Draft hygiene** — create a draft for a user whose signature has an image. Pass: the draft opens on the greeting (no leading whitespace), the signature text is verbatim, and the image is attached inline or the summary says "signature image not included" with the reason.

**71. Competitive Insights** — run manually with no profile (one question), then with one. Pass: PDF in `Skills/Competitive Insights/` of at most 6 pages (formatted layout, quiet competitors one line each, nothing shortened for a normal week), one email that opens with where the PDF is and how to open it and carries the verified link, every source a clickable link, every tracked competitor present or marked quiet; scheduled run with no profile sends `[Failed]`.

## Self-test
`python3 scripts/selftest.py` must print `ALL CHECKS PASSED` before any of the above. As of this release it also asserts, automatically: the ambiguous-time rejection in `render_brief.py` (test 22) via a direct call to `parse_time`/`check_meetings`, and that the daily-brief render path still exits 0 and produces a byte-valid PDF on an unambiguous payload; and the `safe_to_attach` size-gating logic in `verify_pdf.py` (`classify_size` at the ceiling, one byte over it, and at 50MB), plus that a real rendered small PDF reports `safe_to_attach: true`.

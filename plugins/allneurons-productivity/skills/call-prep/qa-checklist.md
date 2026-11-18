# Call Prep — QA checklist

Run before booking anything, and again after booking. Same content as SKILL.md "Pre-send gate", as ticks.

## Before booking
- [ ] The user's own domains were established, not assumed.
- [ ] Every event on the day was classified by domain alone; no external meeting was skipped.
- [ ] Every block's slot is derived from the event record, converted to local time; no block overlaps its call.
- [ ] Each card is under 200 words, five blocks in order, no announced gaps, no raw system values.
- [ ] The settings file `Skills/Call Prep/call-prep-settings.txt` was read first.

## Each block
- [ ] Start and end carry a real time-of-day and timezone on the call's date.
- [ ] Any all-day flag is false or absent.
- [ ] Private, no attendees (the reminder is the calendar default; the tool cannot set one).
- [ ] Marker line present and carrying the event ID.
- [ ] No duplicate for a call whose key is already on the calendar. No call is skipped for any reason; a call already under way has a linked briefing and no block.

## After booking
- [ ] Zero all-day events: re-read the day; every event this run created or updated has clock-time start and end. Anything all-day was deleted and rebooked timed, once.
- [ ] The settings file holds only `prep scope`, `prep lead` and `prep busy`; no booked or opt-out list was read or written.
- [ ] A failure marker, if any, is a timed event in the first block's slot.
- [ ] Failures carry the exact error, not a paraphrase.
- [ ] The closing line reads `allNeurons Productivity v<installed version>`.
- [ ] **Every prep block's notes carry `allNeurons Productivity v<installed version>`** (just above the `ref:` line); `call_prep_card.py audit --version` passed on the stored body, and any older block without the line was repaired in place.

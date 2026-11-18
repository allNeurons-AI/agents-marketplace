# Competitive Insights QA checklist

- [ ] Connector gate passed before anything else; weekday guard applied to a scheduled run only.
- [ ] Profile read (or rebuilt, with no question asked) from `Skills/Competitive Insights/profile.md`; nothing hard-coded.
- [ ] **Group discovery ran:** tenant directory domains, 60-day domain census and web verification; the group lists the user's own company, the parent and every sibling / subsidiary / brand found; each has its own competitor set; the coverage note says which were found and how.
- [ ] **No question or pop-up of any kind** was shown to the user, on a manual or a scheduled run.
- [ ] One batched research pass; dates verified; every claim sourced from this run.
- [ ] One `updates[]` entry per tracked competitor (quiet allowed); new entrants listed, not silently tracked.
- [ ] `deliver_prepare.py --kind competitive_insights` exited 0 (format gate, margin check, link annotations, `verify_pdf.py`).
- [ ] PDF uploaded and read back; the email carries the verified `webUrl` only.
- [ ] Email built by `email_compose.py compose --kind competitive`, validated, sent with `bodyType: "html"`, read back with `stored`.
- [ ] Closing line names the plugin version and the address.
- [ ] PDF recorded with `roi_assets.py record`.
- [ ] Failure path: any unfinished run sent `[Failed] Competitive insights — ...` with the verbatim error.

- [ ] **Depth and clarity.** Every update says who did what and when, with at least one date, price, number or named customer. A reader who has never heard of the company understands each paragraph on its own. No abstract filler words; any term of art is explained in the same sentence.
- [ ] Executive summary opens with a bottom line in one or two sentences, then full-sentence takeaways that each name a company and a fact.
- [ ] Every update with real news has `facts` and a `response`; every action has an `owner` and a `by_when` where one is clear.

- [ ] **Order and look.** Header and five stat tiles → boxed Executive summary (bottom line, then key takeaways each tagged with its company) → Product and market insights (01, 02 ...) → Your companies → Tracked competitors → I. Key competitor updates (with New entrants and What is working well) → II. Competitive threats → III. Opportunities for us → IV. Recommended actions → Sources last. Entries are numbered, statuses are tags, a quiet competitor is one line, every label is bold, no grey text.
- [ ] **At most 6 pages and 22,500 bytes with nothing cut:** the manifest has no `squeeze` for a normal week; a squeezed run is explained in the final reply (not in the PDF).
- [ ] **The email opens with where the PDF is and how to get it** (link, page count, folder, and either "attached" or "Click the link above ... save a copy in your local folder"; never "Nothing is attached"), then Executive summary and Competitive threats only.
- [ ] PDF attached only when the mail tool supports it (`delivery.attached: true`), link always present; exactly one email sent.

- [ ] **The uploaded PDF was read back with `assets/readback_check.py` and passed (every page, page 1 included)** before the link went into the email.

# Test matrix

Mark each row Pass or Fail with the date and tester. "Cowork" means desktop or web Cowork.

| # | Surface | Setup | Action | Expected |
|---|---|---|---|---|
| 1 | Claude Code (`--plugin-dir`) | Outlook, Outlook Calendar, SharePoint | `/allneurons-productivity:onboarding` | Tasks created or a clear scheduling message; final table printed |
| 2 | Claude Code | Gmail, Google Calendar, Drive | Run Daily Brief | PDF in Drive folder, link verified, one email |
| 3 | Cowork | Microsoft stack, scheduling on | Onboarding | Four tasks, permissions note shown |
| 4 | Cowork | Google stack, scheduling on | Onboarding, then each skill once | All four skills complete |
| 5 | Cowork | Outlook mail + Google Calendar + Drive | Daily Brief | Mixed providers work; no provider question |
| 6 | claude.ai chat | Any connectors | Onboarding | Says recurring runs need Cowork and names the admin setting; on-demand skills still work |
| 7 | Cowork | Scheduled tasks disabled by admin | Onboarding | Plain message, no partial setup, on-demand fallback offered |
| 8 | Cowork | "Run Cowork in the cloud" off | Onboarding | Tasks created, local-run caveat shown |
| 9 | Any | Mail send blocked | Daily Brief | PDF saved, link shown in chat, error stated once |
| 10 | Any | Code execution off | Daily Brief | Text summary in chat, no crash |
| 11 | Any | Drive write blocked | Call Prep | Exact error stated, summary in chat |
| 12 | Any | Mail connector missing | Any skill | Connect card, run stops, no question |
| 13 | Any | Slack connected | Daily Brief | Chat asks included |
| 14 | Any | Jira connected | Daily Brief | Tickets due or overdue included |
| 15 | Google Drive | Folder creation | Upload PDF | Works, or fallback chosen; note the tenant |
| 16 | OneDrive | Upload | Upload PDF and read back | Works or fallback; note the tenant |
| 17 | Any | Skill run directly, no task exists | Daily Brief | Same checks as onboarding, then one schedule offer |
| 18 | Any | Saturday, scheduled run | Daily Brief | Stops, sends nothing |
| 19 | Any | Saturday, manual run | Daily Brief | Runs for today |
| 20 | Any | `/allneurons-productivity:connectors` | Run | Table of roles, cards for gaps, nothing read |
| 21 | Claude Code | Follow-Ups | Run | Drafts created in thread, none sent |
| 22 | Any | Competitive Insights, no profile | Run | Profile built, one PDF, one email |

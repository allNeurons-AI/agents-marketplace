# Policy self-review (Software Directory Policy)

Checked by searching the plugin source. Sign below when reviewed.

| Check | Result | Evidence |
|---|---|---|
| Does not read Claude memory or chat history | Pass | No skill or script references memory or past chats. It reads only what connected apps return, plus web search. |
| No instructions fetched remotely | Pass | Skills and scripts are local. Web pages and connector content are treated as data, never instructions (stated in every skill). |
| No hidden or encoded instructions | Pass | Plain Markdown and Python. No base64 decoding, `eval` or `exec` of content. |
| No network calls of its own | Pass | No network library is imported in `assets/` or `scripts/`. The only network access it triggers is the one-time install of three pinned Python packages (reportlab, pypdf, pypdfium2). |
| No credentials, none read from the environment | Pass | No secrets in any file. The only environment variables are tuning flags (`SUITE_PDF_BUDGET`, `SUITE_BRAIN_DIR` and similar) and `SUITE_SESSION_ID`. |
| Descriptions match behaviour | Pass | Each description lists what the skill reads and produces. Skills send one email to the signed-in user and create drafts that are never sent. |
| Sends to nobody else | Pass | `email_compose.py` rejects any message without exactly one recipient, the signed-in user. |
| Data minimisation | Pass | Files saved only to the user's own Drive. Local state is a PDF-fit file and a run ledger on the user's machine, never uploaded. |
| Permission changes | Note | Onboarding tells the user to set the scheduled tasks to Automatically approve. It cannot do this itself, says so, and the README explains why. The user chooses. |
| Test account | Not applicable | The plugin has no service of its own. |

Reviewed by: ______________________  Date: ____________

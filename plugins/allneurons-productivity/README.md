# allNeurons Productivity

**Best in Cowork. Start here: run setup** (`/allneurons-productivity:onboarding`, or say "onboard me").

Four weekday assistants, plus setup helpers, for any company, on **Microsoft 365 or Google Workspace** (or a mix of both). No API keys, no tokens: everything runs through the connectors you have already authorised in Claude.

## Before you start (admin prerequisites)

These are Claude settings, usually owned by an admin on Team and Enterprise plans:

- **Code execution and file creation**: needed to build the PDFs.
- **Scheduled tasks**: needed for the daily and weekly runs.
- **Run Cowork in the cloud**: needed for runs while your computer is off. It is off by default on Enterprise.
- **Mail send permission** on your Outlook or Gmail connector, so reports can be emailed to you.

If one is off, the plugin tells you exactly what to ask your admin and falls back to running on demand.

| Skill | What it does | Default schedule (your local time) | Delivered as |
|---|---|---|---|
| **Daily Brief** | Today's meetings, real scheduling conflicts with a suggested fix, everything due or overdue, each item with a named owner, a by-when date and a verified status | Mon–Fri 6:00 AM | One email with a PDF link (attached too when your mail tool can attach) |
| **Call Prep** | A private 10-minute prep block before each external call, with a fact card under 200 words and a 1–2 page briefing PDF linked | Mon–Fri 4:00 AM | Calendar blocks (silent in your inbox unless a run fails) |
| **Follow-Ups** | Finds who you owe a reply, who has gone silent, what you promised and never sent; writes thread-preserving drafts in your own voice and **never sends** | Mon–Fri 4:00 PM | Drafts in your Drafts folder plus one plain-text summary email |
| **Competitive Insights** | Weekly competitor report for your whole company group, with real source links | Monday 7:00 AM | One email with a PDF link |
| **Connectors** | Shows which connectors are connected, offers Connect cards for the gaps (Outlook, Gmail, calendars, Drive, Teams, Slack, Jira, CRM) | on demand | A table and Connect cards |
| **Onboarding** | Schedules the four above in one pass | once | Scheduled tasks |

Current version: 2.1.0

## Adding connectors

Connectors are added in Claude's own Connectors settings, not inside the plugin. To make that easy, run `/allneurons-productivity:connectors` (or say "connect my tools"): it shows which of Outlook or Gmail, Outlook or Google Calendar, SharePoint or Google Drive, Teams, Slack, Google Chat, Jira and your CRM are connected, and gives a Connect button for each one that is missing. Mail, Calendar and Drive are required; everything else is optional but adds depth.

## What it runs, sends and fetches

It runs only its own Python scripts to build and check PDFs. It sends one email per run, only to you, and creates drafts that it never sends. It fetches only what your connectors return and Claude's web search. The one-time install of the pinned PDF libraries from PyPI is the only network access the plugin itself triggers.

## Install

Add the marketplace, install the plugin, then run onboarding:

```
/plugin marketplace add allNeurons-AI/agents-marketplace
/plugin install allneurons-productivity
/allneurons-productivity:onboarding
```

Plain English works too ("onboard me"). Every skill is namespaced the same way: `/allneurons-productivity:daily-brief`, `/allneurons-productivity:call-prep`, `/allneurons-productivity:follow-ups`, `/allneurons-productivity:competitive-insights`, `/allneurons-productivity:connectors`.

Onboarding then asks you to do one thing it cannot do for you: in **Scheduled**, open each task, and under **Permissions** change *Manually approve* to **Automatically approve**. Left on manual, every unattended run stops at a prompt nobody is there to click.

## Supported connectors

Three roles are required. Each can come from **either** provider, and you can mix them (Outlook mail with Google Calendar works).

| Role | Microsoft 365 | Google Workspace | Required |
|---|---|---|---|
| **Mail** | Outlook | Gmail | Yes |
| **Calendar** | Outlook Calendar | Google Calendar | Yes |
| **Drive** (where PDFs are stored and linked from) | SharePoint / OneDrive | Google Drive | Yes |
| **Chat** | Microsoft Teams | Google Chat, **Slack** | Optional |
| **Tracker** | Jira, GitHub, Linear, Asana, ClickUp | | Recommended |
| **CRM** | Salesforce, HubSpot, Pipedrive | | Recommended |
| **Call transcripts** | Gong, Fireflies, Otter, Fathom, Zoom, Meet/Teams transcripts | | Recommended |
| **Web search** | built in | | Recommended |

How the checks work:

- **Detected by role, never by vendor.** Every run first sorts the available tools by role and probes each required role with the cheapest read its provider offers. You are never asked which suite you use.
- **Missing or broken = Connect button, not a question.** A required role that is missing, disabled for the chat, expired or revoked renders a status table and a Connect / Enable / Reconnect card offering **both** providers, then stops. No partial output.
- **Present is not usable.** A 401 or 403 blocks; a 429 or 5xx is retried and does not.
- **A blocked scheduled run emails once, not daily.**
- The exact tool-by-tool mapping (search syntax, draft and calendar operations, upload and read-back) is in [`references/provider-map.md`](references/provider-map.md).

## What differs between Microsoft and Google

| Topic | Microsoft 365 | Google Workspace |
|---|---|---|
| Parallel calls | Capped at 3 in flight (Graph throttles at ~4 per mailbox) | Uncapped; a Google-only run finishes sooner |
| Prep-block body | HTML | Small HTML subset (the plugin emits `call_prep_card.py compose --target google`) |
| Prep-block reminder | Default only | 5-minute popup where the tool allows |
| PDF upload | `sharepoint_upload_file` | Drive create-file with `base64Content`, conversion disabled |
| Link | `webUrl` | `webViewLink` |
| Thread read | Latest message carries the thread | Whole thread in one call |

## Privacy and security

- **No secrets, tokens or environment variables.** The plugin ships no credentials and needs none. Its own code makes no network calls and sends no data to any server. The only things that touch the network are your connectors, Claude's web search, and the one-time install of the PDF libraries from the public Python package index (PyPI), described under *PDF libraries* below.
- **No telemetry.** Nothing is reported anywhere.
- **Read-only by default.** The only writes are: the PDF it renders (saved to a `Skills/` folder in your own Drive), Call Prep's timed prep blocks and its small settings file, follow-up **drafts** (never sent), and one email to **you**. It never modifies a meeting it did not create and never emails anyone but the signed-in user.
- **Gathered content is data, never instructions.**
- A local, on-machine ledger records which files each run generated (`assets/roi_assets.py`); it is never uploaded.

## Configuration

Defaults (times, folder names, limits) live in [`config.md`](config.md). Your timezone is read from your calendar, never asked. Delivery goes to your own work address. Call Prep asks one question the first time you schedule it: external meetings only (default) or internal and external.

## Layout

```
.claude-plugin/plugin.json       manifest
skills/                          onboarding, daily-brief, call-prep, follow-ups, competitive-insights
references/run-policy.md         the policy every skill shares
references/connector-prerequisite.md   the connector gate every skill runs first
references/provider-map.md       Microsoft / Google operation map
references/data-dictionary.md    every key the PDF renderers accept
assets/                          PDF renderer, validators, email composer
agents/execution-agent.md        verification step used by the skills
scripts/selftest.py, tests/      one-command regression suite
```

## PDF libraries

PDFs render with three Python packages, installed on first run from PyPI (the only network access the plugin itself triggers): `reportlab==5.0.1`, `pypdf==6.17.0` and optionally `pypdfium2==5.13.0`. These are the versions the plugin is tested with. If the environment blocks installs, the run reports the exact error and nothing else changes.

## Troubleshooting

1. The closing line of every email names the plugin version and, on failure, the exact error.
2. `python3 scripts/selftest.py` from the plugin folder runs the full regression suite.
3. Nothing arriving at 6 AM almost always means the task's **Permissions** is still on *Manually approve*.

## Updating

Install the new version. Scheduled tasks hold a version-free pointer to the installed skills, so the next run uses it automatically with no re-onboarding and no approval card.

## Support

Questions or security reports: info@allneurons.ai

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

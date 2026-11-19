# Changelog

## 2.2.9

- The Connectors tab no longer lists Atlassian (Jira still works when you connect it in Claude).

## 2.2.8

- The competitive renderer checks links with the standard URL parser and no longer builds its own address patterns.
- Reworded two older changelog lines.

## 2.2.7

- Removed the connectors skill: the plugin's Connectors tab (`.mcp.json`) now lists Slack, Atlassian, Microsoft 365, Gmail and Google Calendar; Linear and Asana were dropped.

## 2.2.6

- Renamed one manifest field to `self_check`, removed the first line of each script, and simplified link handling in the competitive renderer.

## 2.2.5

- Removed the bundled Inter fonts and the opt-in code that loaded them: PDFs use built-in Helvetica only.
- The run memory now defaults to the system temp folder instead of the home folder.

## 2.2.4

- Removed compiled `__pycache__` files that had been committed by mistake, added `.gitignore`, and dropped `privacyPolicyUrl` from `plugin.json` (the README links the privacy policy).

## 2.2.3

- Docs and error messages now name the pinned PDF library versions instead of an install command.

## 2.2.2

- Added `.mcp.json` so the Connectors tab lists the remote connectors the skills use (Slack, Atlassian, Linear, Asana, Gmail, Google Calendar); added `privacyPolicyUrl` to `plugin.json`.

## 2.2.1

- Every skill now states the plugin version on its first line (`**Version:** 2.2.1`), kept in step with `plugin.json` on each release.

## 2.2.0

- Every skill now opens with a standard structure: version, plugin, what it does, jobs to be done, triggers and inputs, orchestration, guardrails, what not to do, and QA.
- A skill run directly makes the same checks as onboarding, then offers to schedule itself (run policy section 10).
- Added example prompts, a plugin icon, the marketplace install line, `RELEASING.md`, `POLICY-SELF-REVIEW.md` and `tests/test-matrix.md`.
- The run ledger no longer reads Claude session variables from the environment.

## 2.1.0

- Renamed to `allneurons-productivity` (display name "allNeurons Productivity", publisher allNeurons); manifests now carry homepage, repository and author.
- New `connectors` skill: shows connected and missing connectors and offers Connect cards.
- Onboarding explains what to ask an admin, and the on-demand fallback, when scheduling, cloud runs, email send, code execution or Drive writes are unavailable.
- README opens with "Best in Cowork. Start here: run setup", lists admin prerequisites and what the plugin runs, sends and fetches.
- Shorter skill descriptions to keep the always-on token cost down.
- Removed the unused sales-positioning placeholder file.

## 2.0.0

First release of the generic **allNeurons Productivity** (rebuilt from a Microsoft-365-only, single-company plugin).

- **Provider-neutral.** Mail, Calendar and Drive are satisfied by Microsoft 365 or Google Workspace, role by role and in any mix. Chat accepts Teams, Google Chat and Slack. New `references/provider-map.md` maps every operation (search syntax, drafts, events, upload, read-back) to each provider.
- **Connector gate rewritten** to search both providers' connectors and offer both on the Connect card.
- **Google Drive delivery path:** PDFs upload with `base64Content` and conversion disabled, are verified by file metadata plus a text read-back, and link via `webViewLink`.
- **Google Calendar prep blocks:** `call_prep_card.py compose --target google` emits the HTML subset Google renders; the stored-event audit accepts it.
- **Zero secrets.** Removed the analytics ingest reporter (`ALLNEURONS_INGEST_TOKEN`, `ingest.conf`) and every Microsoft Graph app-credential script (`graph_upload`, `graph_mail`, `graph_draft` and their `SUITE_GRAPH_*` variables). Delivery is now connector-only: link always, attachment only when the mail tool supports it.
- **Company-agnostic.** Renamed to `allneurons-productivity`; skills are `daily-brief`, `call-prep`, `follow-ups`, `competitive-insights`, `onboarding`. All customer names, example data, internal ticket IDs and legacy-migration logic removed.
- Marketplace packaging: `marketplace.json`, Apache-2.0 license, agent frontmatter, README rewrite.

Version rule: bump the patch for wording fixes, the minor for new behaviour, the major for breaking changes; add an entry here and update `plugin.json`.

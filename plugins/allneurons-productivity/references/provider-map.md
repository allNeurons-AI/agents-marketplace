# Provider map — one plugin, Microsoft 365 or Google Workspace (or both)

**Every skill in this plugin is written in terms of *roles* and *operations*, not products.** "Search the inbox", "list the day's events", "upload the PDF to the drive" are operations. This file maps each operation to the tool a connected provider offers, and records the few places where the providers genuinely differ. Where a SKILL.md or `run-policy.md` names a specific tool (for example `outlook_email_search`), that is the Microsoft 365 spelling of an operation; **on Google Workspace use the row in this file for the same operation.** The behaviour the skill asks for is identical either way.

**Never ask the user which provider they use.** Detect it (Part 1), use it, and say nothing about the choice unless it explains a limit.

---

## Part 1 — Detecting the provider, per role

Roles are detected **independently**. A person can have Outlook mail and Google Calendar, or Gmail and Teams; nothing requires one vendor across roles. Detection is by connector family and tool-name prefix, case-insensitive, and the connector's own name wins when prefixes are ambiguous (for example the server called `Google_Drive`, `Microsoft_365`, `Slack`).

| Role | Microsoft 365 | Google Workspace | Other accepted |
|---|---|---|---|
| **Mail** | `outlook_*`, `microsoft365_*` (mail tools) | `gmail_*`, `google_workspace_*` (mail tools) | — |
| **Calendar** | `outlook_calendar_*`, `microsoft365_*` (calendar tools) | `gcal_*`, `google_calendar_*`, `google_workspace_*` (calendar tools) | — |
| **Drive** (file storage the PDFs are saved to and linked from) | `sharepoint_*`, `onedrive_*`, `microsoft365_*` (file tools) | `drive_*`, `google_drive_*`, `google_workspace_*` (file tools) | Box, Dropbox only if the connector can create a file and return a shareable link |
| **Chat** *(optional)* | `teams_*`, `chat_message_search` | `googlechat_*`, `google_chat_*` | `slack_*` |
| **Tracker** *(recommended)* | — | — | Jira / Atlassian, GitHub, Linear, Asana, ClickUp, Trello, Monday |
| **CRM** *(recommended)* | — | — | Salesforce, HubSpot, Pipedrive, Attio, Close |
| **Transcripts** *(recommended)* | Teams meeting transcripts via the Microsoft connector where exposed | Google Meet transcripts via Drive | Gong, Fireflies, Otter, Fathom, Granola, Zoom |

**One usable tool in a role satisfies the role.** If both providers are present for a role (a person with Outlook *and* Gmail), choose deterministically — the one whose signed-in domain matches the calendar the run is built from, otherwise the one that answers the probe first on the *first* run and is then used for the whole run — and **never split one run's reads across two providers of the same role.**

---

## Part 2 — Operation table

Search syntax differs. **Never send one provider's query syntax to the other.**

### Mail

| Operation | Microsoft 365 | Google Workspace |
|---|---|---|
| List the inbox, newest first, last N days | `outlook_email_search` with `folderName: "Inbox"`, `order: "newest"`, no `query` | Gmail search `in:inbox newer_than:2d` |
| List sent mail, last N days | `outlook_email_search` with `folderName: "Sent Items"` | Gmail search `in:sent newer_than:10d` |
| Keyword search | KQL-style `query` (one OR query: `due OR deadline OR overdue`) | Gmail search `(due OR deadline OR overdue) newer_than:10d` |
| Search by person | `from:`/`to:` in `query` | `from:name@x.com`, `to:`, `cc:` |
| Read one message / thread in full | `read_resource` on the `mail:///messages/…` URI (read the **latest** message — it carries the thread below it) | The thread-read tool on the thread id (returns **every** message in the thread) |
| Pagination | `nextOffset` / `moreResults` / `@odata.nextLink` | `nextPageToken` / `next_page_token` |
| Create a reply draft in the thread | `outlook_create_reply_draft` (or `outlook_create_draft` + `outlook_update_draft`) | Draft-create tool with the thread id (so it lands in the same conversation) |
| Send one email to the user | `outlook_send_mail` (`bodyType: "html"`) | Gmail send tool (HTML body) |
| Search the user's own Drafts | `outlook_email_search` with `folderName: "Drafts"` | Gmail search `in:drafts` |

### Calendar

| Operation | Microsoft 365 | Google Workspace |
|---|---|---|
| List the day's events with attendees | `outlook_calendar_search` / `list_events` (day window, full attendee expansion) | Calendar list-events tool with `timeMin`/`timeMax`, `singleEvents: true` |
| Find an event by title / marker | `outlook_calendar_search` on the text | Calendar list-events with the `q` text filter |
| Create a private timed block | `outlook_create_event` with `sensitivity: "private"`, `showAs`, no attendees | Calendar create-event with `visibility: "private"`, no attendees |
| Update a block you created | `outlook_update_event` (`bodyType` required whenever `body` is supplied) | Calendar update/patch-event tool |
| Delete a block you created | `outlook_delete_event` | Calendar delete-event tool |
| Event body format | HTML (`bodyType: "html"`) | Description field; Google renders a **small HTML subset** (`<b> <i> <u> <br> <a> <ul> <li>`). Build the card with those tags only |
| Reminder | **No reminder field** on `outlook_create_event`; the default applies | Set a popup reminder override (5 minutes) where the tool exposes it; otherwise the default applies |
| Conferencing | Teams link on the event | Meet link (`conferenceData`) or any other URL in the location/description |

### Drive (file storage)

| Operation | Microsoft 365 | Google Workspace |
|---|---|---|
| Find a folder | `sharepoint_folder_search` (name, then `parentItemId`) | Drive search `mimeType = 'application/vnd.google-apps.folder' and title = 'X' and parentId = '…'` |
| Create a folder (one level at a time) | `sharepoint_create_folder` (`driveId`, `name`, `parentItemId`) | Drive create-file with `mimeType: application/vnd.google-apps.folder`, `parentId` |
| Upload a PDF | `sharepoint_upload_file` with `content` (ASCII) or `contentBase64`, `expectedBytes`, `conflictBehavior: "replace"` | Drive create-file with `base64Content`, `contentMimeType: "application/pdf"`, **`disableConversionToGoogleType: true`**, `parentId`, `title` ending `.pdf` |
| Replace an existing file of that name | `conflictBehavior: "replace"` | Search the folder for the title; if found, the Drive update-file tool with the new content; otherwise create. **Never leave two files of the same name** |
| Verify the upload | Returned name ends `.pdf`, size equals `bytes`; `read_resource` on `resourceUri` returns the extracted text → `readback_check.py` | `get_file_metadata` → name ends `.pdf`, size equals `bytes`; `read_file_content` returns the extracted text → `readback_check.py` |
| The link | `webUrl` | `webViewLink` (from metadata) |
| Size limit per call | 1,048,576 bytes | Practically larger, but the typed-paste ceiling below still applies |
| Read a small text file (settings, profile) | `sharepoint_search` + `read_resource` | Drive search by title + `read_file_content` |
| Write a small text file | `sharepoint_upload_file` / `sharepoint_update_file` | Drive create-file with `textContent`, `contentMimeType: "text/plain"`, `disableConversionToGoogleType: true`; update-file when it exists |

### Chat (optional)

| Operation | Microsoft Teams | Slack | Google Chat |
|---|---|---|---|
| Search messages | `chat_message_search` | Slack search-messages tool | Chat search/list-messages tool |
| Read a message in full + its thread | `read_resource` on the `teams:///…` URI. **There is no tool that lists a chat's messages**, so Teams coverage is "read N of M matched messages" | Read-thread / conversation-replies tool — the **whole thread** is readable | List-messages on the space/thread |
| List channels / chats | `teams_list_channels`, `teams_list_chats`, `teams_list_channel_messages` | List-channels tool | List-spaces tool |

### Directory

| Operation | Microsoft 365 | Google Workspace |
|---|---|---|
| Resolve a person | `search_people`, `get_me` | Directory/people search tool, the signed-in profile |

---

## Part 3 — Differences that change behaviour

1. **Concurrency.** Microsoft Graph throttles at roughly four concurrent requests per mailbox, so **Microsoft-backed calls run at most 3 in flight** (run-policy §3). Google Workspace, Slack, trackers, CRMs and web search are **not capped by this plugin** and ride along in the first group. A pure-Google run therefore issues each batch in one message.
2. **Thread reads.** Gmail's thread read returns the whole conversation in one call; Outlook needs the latest message read (and, for history, further reads). Budgets written for Outlook are an upper bound on Gmail.
3. **Query syntax.** KQL-style on Microsoft, Gmail operators on Google. Never search for a bare `?`.
4. **Calendar bodies.** HTML on Microsoft; a small HTML subset on Google (Part 2). `call_prep_card.py compose` already emits only tags both accept; the audit still reads the stored event back.
5. **Reminders.** Settable on Google; not on Microsoft.
6. **Attachments.** Neither provider's connector is assumed to attach files. **A PDF is attached only when the connected mail tool exposes an attachment parameter this run; otherwise the email carries a verified link.** The link is always present either way.
7. **File links.** `webUrl` (Microsoft) and `webViewLink` (Google) are the same thing to the rest of the plugin: *the verified link*. Documents the plugin saves are visible only to the signed-in user until they share them; say so once in the closing delivery line if the person asks.

---

## Part 4 — Free-mail is a legitimate work mailbox on Google

On a Google Workspace organisation the user's work address is a company-domain Gmail address, and that is what the mailbox rule means by "corporate". A plain `@gmail.com` address is free-mail and is used **only** when it is the sole connected mailbox, and the run says so once. This is the same rule as before; it is restated here because "Gmail" and "free mail" are not synonyms.

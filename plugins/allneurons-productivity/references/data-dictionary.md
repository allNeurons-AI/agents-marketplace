# Data dictionary — renderer payloads

The JSON each skill hands to its renderer. Unknown keys are ignored; a missing required key exits with code 6 (run-policy §8).

## Daily Brief (`render_brief.py --in brief.json`)

| Key | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | e.g. `Daily Brief — Monday, September 28` |
| `headline` | string | yes | One sentence: what matters most today |
| `date` | `YYYY-MM-DD` | no | Used for the file name |
| `stats` | object of label → integer | yes | Conflicts, Due today & overdue, Needs attention, Resolved |
| `meetings[]` | list | yes | `start`, `end`, `kind` (`conflict` / `back_to_back` / normal), `label`, `who`, `format`, optional `status` (`upcoming` / `passed` / `canceled`) |
| `conflicts[]` | list | yes (may be empty) | `title`, `body`, `fix`, plus the action fields below |
| `due_today[]` | list | yes (may be empty) | `title`, `meta`, plus the action fields |
| `worth_double_checking[]` | list | yes (may be empty) | Action fields with status `Needs confirmation`; an entry with `"informational": true` and only `body` is a coverage note |
| `needs_attention[]` | list | yes (may be empty) | `title`, `body`, plus the action fields |
| `resolved[]` | list | yes (may be empty) | `title`, `body` |
| `sources[]` | list | yes | `label`, optional `url` (http/https only; anything else drops to plain text) |

**Action fields** (every actionable item): `action`, `owner` (a named person), `by_when` (a date/time or `no stated deadline — flag today`), `source`, `status`.

**Status values:** `Open`, `Waiting on <name>`, `Needs confirmation`, `Resolved`. No other values.

## Call Prep (`render_call_prep.py --in prep.json`)

Required keys (a missing or empty one exits with code 6): `company`, `context`, `time`, `attendees`, `what_you_need_to_know`, `objective`, `desired_outcome`, `questions`, `sources`, `duration`, `format`, `owner`, `stage`, `last_contact`, `absent_decision_maker`, `risks`, `actions`.

| Key | Notes |
|---|---|
| `attendees[]` | `name`, `role`/`title`, `company`, `why` (20 words max), optional `first_time` |
| `what_you_need_to_know[]` | `body` (28 words max), optional `source` |
| `questions[]` | Plain strings |
| `risks[]` | `body` (28 words max) |
| `actions[]` | `body` (22 words max), `owner` (a named person), `by_when`, `status` (run-policy §4 vocabulary) |
| `sources[]` | `label`, optional `url` |
| `classification_note` | Optional; printed only when present |

Over two pages exits with code 5 and deletes the file (Call Prep's ceiling is hard; the Daily Brief's is soft).

## Settings record (`call-prep-settings.txt`, Drive)
Plain `key: value` lines: `prep scope`, `prep lead`, `prep busy`. Older files may carry `opted out` and `booked` lists; they are ignored and dropped on the next write.

## Competitive Insights (`render_competitive.py` / `deliver_prepare.py --kind competitive_insights`)

| Key | Type | Required | Notes |
|---|---|---|---|
| `title`, `week` | string | yes | e.g. `Competitive Intelligence Report`, `Sep 28 - Oct 4, 2026` |
| `company` | string | no | from the profile; shown under the week |
| `sets[]` | list | yes | `key`, `name`, `competitors[]` (`name`, `description`), from `profile.md` |
| `group[]` | list | yes | `name`, `domain`, `description`: every company in the user's group |
| `sets[]` | list | yes | `key`, `entity` (a group name), `name`, `competitors[]` (`name`, `description`), from `profile.md` |
| `executive_summary` | string or list | yes | bottom line first, then takeaways |
| `company_summaries[]` | list | yes | one per group company: `entity`, `what_matters`, `why` |
| `updates[]` | list | yes | one per tracked competitor: `set`, `competitor`, `what`, `facts[]`, `why`, `response`, `sources[]` (ints), or `quiet: true` |
| `new_entrants[]` | list | yes (may be empty) | `entity`, `name`, `note`, `source` |
| `working_well[]`, `market_trends[]` | list | yes | `entity`, `title`, `body`, `source` (trends: `entity`, `title?`, `body`) |
| `threats[]` | list | yes | `set`, `title`, `level` (High/Medium/Low), `why`, `impact` |
| `opportunities[]` | list | yes | `set`, `title`, `body` |
| `actions[]` | list | yes | `entity`, `action`, `reason`, `priority` (High/Medium/Low), `owner`, `by_when` |
| `sources[]` | list | yes | `label`, optional `url` (http/https only; anything else drops to plain text) |

**Action fields** (every actionable item): `action`, `owner` (a named person), `by_when` (a date/time or `no stated deadline — flag today`), `source`, `status`.

**Status values:** `Open`, `Waiting on <name>`, `Needs confirmation`, `Resolved`. No other values.

## Call Prep (`render_call_prep.py --in prep.json`)

Required keys (a missing or empty one exits with code 6): `company`, `context`, `time`, `attendees`, `what_you_need_to_know`, `objective`, `desired_outcome`, `questions`, `sources`, `duration`, `format`, `owner`, `stage`, `last_contact`, `absent_decision_maker`, `risks`, `actions`.

| Key | Notes |
|---|---|
| `attendees[]` | `name`, `role`/`title`, `company`, `why` (20 words max), optional `first_time` |
| `what_you_need_to_know[]` | `body` (28 words max), optional `source` |
| `questions[]` | Plain strings |
| `risks[]` | `body` (28 words max) |
| `actions[]` | `body` (22 words max), `owner` (a named person), `by_when`, `status` (run-policy §4 vocabulary) |
| `sources[]` | `label`, optional `url` |
| `classification_note` | Optional; printed only when present |

Over two pages exits with code 5 and deletes the file (Call Prep's ceiling is hard; the Daily Brief's is soft).

## Settings record (`call-prep-settings.txt`, Drive)
Plain `key: value` lines: `prep scope`, `prep lead`, `prep busy`. Older files may carry `opted out` and `booked` lists; they are ignored and dropped on the next write.

## Competitive Insights (`render_competitive.py` / `deliver_prepare.py --kind competitive_insights`)

| Key | Type | Required | Notes |
|---|---|---|---|
| `title`, `week` | string | yes | e.g. `Competitive Intelligence Report`, `Sep 28 - Oct 4, 2026` |
| `company` | string | no | from the profile; shown under the week |
| `sets[]` | list | yes | `key`, `name`, `competitors[]` (`name`, `description`), from `profile.md` |
| `executive_summary` | string or list | yes | |
| `updates[]` | list | yes | one per tracked competitor: `set`, `competitor`, `what`, `why`, `sources[]` (ints), or `quiet: true` |
| `new_entrants[]` | list | no | `name`, `note`, `source` |
| `working_well[]`, `insights[]` | list | yes | `title`, `body`, `source`; insights may be plain strings |
| `threats[]` | list | yes | `set`, `title`, `level` (High/Medium/Low), `why`, `impact` |
| `opportunities[]` | list | yes | `set`, `title`, `body` |
| `actions[]` | list | yes | `action`, `reason`, `priority` (High/Medium/Low) |
| `sources[]` | list | yes | `label`, `url` (absolute https; each becomes a real link annotation) |

## Email composer (`email_compose.py compose --kind daily_brief|follow_ups|competitive|failure`)

Input is the skill's own payload plus a `delivery` block: `filename`, `link` (the read-back-verified webUrl) or `parts[]`, `pages`, `address`, `version`, optional `attached` (Competitive Insights only: true when the PDF went as a real attachment through `graph_mail.py`). Output is the exact `outlook_send_mail` argument object, `bodyType: "html"` included.

## Call Prep card (`call_prep_card.py compose`)

`header1`, `header2`, `before_you_join[]` (`fact`, `source`), `your_move[]` (`text`, `source`), `open_with`, `ask`, `filename`, `link` (verified https URL or null), `call_key`, optional `overlay_note`.

---
name: onboarding
description: "Schedules the weekday skills: Call Prep 4 AM, Daily Brief 6 AM, Follow-Ups 4 PM, Competitive Insights Monday 7 AM. Checks connectors first, explains plainly what to ask an admin when scheduling or email is blocked, and creates tasks only. Use for 'onboard me' or after an update."
---

# allNeurons Productivity Onboarding

Creates the recurring scheduled tasks. **It creates tasks. It does not run any of the four skills, read any data, or produce any brief, report or plan.** Finish in under a minute of actual work — a card waiting on a human does not count against that, and never rush a blocker decision to beat a clock. Budget ~12 tool calls in single-skill mode and **up to ~20 in full mode** — the Step 3 preflight batch, three creates, and as many as ten legacy deletes. The ceiling is there to stop exploration, never to skip a delete.

**Two modes:**

| Mode | When | What it touches |
|---|---|---|
| **Full** (default) | `/allneurons-productivity:onboarding`, "onboard me", "set up my productivity skills", or after a plugin update | All four tasks. |
| **Single-skill** | A target skill is named — by shared §10's offer, or by a person asking for one ("just schedule my daily brief") | **That one task only.** The other two are left completely alone: not created, not updated, not deleted, not mentioned. |

**There is no refresh mode, and a scheduled run never invokes this skill** — plugin updates reach live tasks through the installed files, never through a rewrite of the task (shared §14; *No refresh after an update* below). **In single-skill mode, every instruction phrased around three tasks means the one target skill** — "all three", "the three", "each of the three", "the three prompts", "Repeat for all three". There is no step whose three-ness survives the mode. **The one thing that never changes is that this skill is the only writer of scheduled tasks** — see *Why the worker skills hand off here*.

## How to invoke these skills

**Each skill is namespaced by the plugin, so the exact command is the plugin name, a colon, then the skill name:**

| Skill | Command |
|---|---|
| Onboarding — run this first | `/allneurons-productivity:onboarding` |
| Connectors | `/allneurons-productivity:connectors` |
| Call Prep | `/allneurons-productivity:call-prep` |
| Daily Brief | `/allneurons-productivity:daily-brief` |
| Follow-Ups | `/allneurons-productivity:follow-ups` |
| Competitive Insights | `/allneurons-productivity:competitive-insights` |

**Plain English works too** — "onboard me", "what's on my day", "find my follow-ups" — and is what most people use. The namespaced command is what to give someone when it matters that they hit the right skill first time: in setup instructions, in a runbook, or when two plugins expose similarly named skills.

**The namespace is never matched against when *resolving* a name** (see *Resolving skill names*). It is how a person types the command; it is not how this skill identifies a target.

## Ground rules

1. **Never prompt for days or times.** The schedule is fixed. No AskUserQuestion for scheduling.
2. **Never run the underlying skills.** No calendar reads, no email reads, no web research, no drafts, no briefs. **Detecting that a connector exists is not reading it** — the preflight in Step 3 checks which roles are *available* by tool name and reads nothing at all. If you find yourself listing events or searching mail, you have crossed the line.
3. **Reconcile, never skip.** List existing tasks first, then bring **every task in scope** to the installed plugin version — create the missing ones, **overwrite the ones that already exist**, and **delete their legacy equivalents** (see *Migration*). Scope is all four in full mode, the named skill in single-skill mode.
4. **Ask only what is genuinely missing.** Nothing missing → ask nothing.
5. **Never assume a bare skill name resolves.** Always resolve per *Resolving skill names*.
6. Schedule in the user's **local** time — write local times directly where cron is evaluated locally, and prefix `CRON_TZ=<IANA zone> ` where the scheduling tool evaluates cron in UTC (see *Version reconciliation*).
7. **Always finish with the Step 7 table plus the permissions block — and nothing beyond it.** The one exception is a Step 3 **blocker stop**: no scheduling tool means no task exists to set permissions on, so that run ends with the blocker stated and nothing else.
8. **The schedule is Monday to Friday. Strictly.** Never create, widen or suggest a cron including Saturday or Sunday.

## The fixed schedule

| # | Skill | Cadence | Local time | Cron |
|---|-------|---------|-----------|------|
| 1 | `call-prep` | Weekdays Mon–Fri | 4:00 AM | `0 4 * * 1-5` |
| 2 | `daily-brief` | Weekdays Mon–Fri | 6:00 AM | `0 6 * * 1-5` |
| 3 | `follow-ups` | Weekdays Mon–Fri | 4:00 PM | `0 16 * * 1-5` |
| 4 | `competitive-insights` | Weekly, Monday | 7:00 AM | `0 7 * * 1` |

**The schedule is Monday to Friday only** — Competitive Insights is weekly and fires on Monday, which is inside that rule; it is never moved to a weekend (the stand-alone skill this replaces ran Saturday night, and that slot is not available to an unattended run here). (Manual invocations are unrestricted — the weekend rule governs unattended runs, per shared §1.) The `1-5` day field is fixed — never widen it to `0-4`, `0-6`, `*`, or anything including day 0 or day 6, not even if the user asks for weekend or Monday-morning coverage. Each skill also carries its own weekend guard, so the rule is enforced twice: in the cron and in the skill.

Call Prep preps **today's** calls at 04:00, early enough that even an 8 AM call has its prep block booked hours ahead. The trade-off is that a meeting added to the calendar after 4 AM gets no block — say so in one clause if the person asks, and point them at running the skill by hand. It delivers by **booking a private prep block before each external call**, not by email — so its scheduled task produces nothing in the inbox unless the run fails.

**A manual Call Prep run works on any day, weekend included**, and where today has no calls left ahead of the clock it targets the next day that does. Never widen the cron to cover a weekend.

## Thin task prompts — the schedule points at the skill, it does not copy it

**A scheduled task stores a copy of its prompt, taken when the task was created. Updating the plugin does not update that copy.** An earlier design worked around that by baking every policy detail into a ~700-word prompt per task, which created the problem it was trying to solve: each fix then existed in two places — the SKILL.md and the stored prompt — and the copies drifted. One shipped with a sentence duplicated mid-clause; another kept a rule the skill had already retired.

**The prompts this skill generates are therefore deliberately thin.** Each one carries only:

1. **No version.** The prompt names no plugin version and restates no rule a later release might change, so it can never go stale and never needs rewriting (shared §14).
2. The **resolution preamble**, so the right skill is found whatever the namespace.
3. The **run parameters** — the resolved local timezone (never asked for; see *Timezone*), the delivery address, and for Call Prep the "today, book a block per call" instruction.
4. A **four-line safety floor** — the rules that must hold even if something goes wrong loading the skill: weekend guard, one email to the stamped address only, never send outward-facing mail, never ask a question.
5. One line handing the complete run contract back to the skill.

Everything else — deadlines, rate-limit backoff, coverage floors, correctness gates, the classification rule, delivery and attachment handling — lives in the skill and in `references/run-policy.md`, which are **real plugin content and therefore update the moment the plugin updates.** **So a plugin update reaches a live schedule completely on its own** — the next scheduled run follows the newly installed files, with no write to the task, no **Update task** card, and nobody involved. Re-running onboarding is never required after an update; it is only for changing settings or clearing duplicates.

**Never put `${CLAUDE_PLUGIN_ROOT}` in a task prompt.** That placeholder resolves in *plugin* skill content; a scheduled task is stored outside plugin content, so it would be passed through as a literal path and the run would fail to find the renderer. Task prompts say *what* to do; the skill supplies the path.

## Version reconciliation

**Read the installed version at the start of every run** — for the Step 7 report only:

```bash
python3 -c "import json;print(json.load(open('${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json'))['version'])"
```

**Never write the version into a task** — not into the prompt, not into the description, not into the title. A version inside a stored task is exactly what used to make it go stale and force a rewrite after every update; without one, there is nothing to reconcile when the plugin updates (shared §14).

**Overwrite unconditionally on a person-initiated run.** For each **in-scope** task:

- **Absent** → create it. Report `created`.
- **Present** → update it with the freshly generated `prompt`, `description` and schedule. **Always** — this is how an old stamped prompt is tidied into the version-free form, and how duplicates are collapsed. Report `updated`.

Never report a task as "already scheduled" and move on.

**Finding the existing task.** Match an in-scope task by its task ID **or** by its exact title from Step 6 — cloud scheduling tools list tasks by name and generated ID (`trig_…`), not by the IDs below. **More than one task matching the same skill is a duplicate**: keep one (update it), delete the rest in the same Step 6 batch, and report each as `duplicate removed`. Two tasks for one skill means two of every email.

Use the same four task IDs every time where the tool accepts an ID — `daily-brief`, `follow-ups`, `call-prep`, `competitive-insights` — and **never invent versioned IDs** like `daily-brief-v2`, which would leave the old task running alongside the new one and double every email.

**Cron and timezone.** Where the scheduling tool evaluates cron in the machine's local time (the desktop app's scheduled tasks), write the times in *The fixed schedule* as-is. **Where it evaluates cron in UTC (cloud scheduled tasks — their cron field documents UTC unless prefixed), prefix it with `CRON_TZ=<IANA zone> `**, e.g. `CRON_TZ=Asia/Kolkata 0 6 * * 1-5`. A bare `0 6 * * 1-5` on a UTC scheduler fires at 11:30 AM in India — the exact duplicate-at-the-wrong-hour bug an earlier install shipped.

## Single-skill mode

Triggered when a target skill is named. Shared §10 is the common path: a manual run of one worker skill found no task for itself, offered to schedule it, the person said yes, and that skill invoked this one naming itself. A person asking directly — "schedule just the follow-ups" — is the same thing.

**Do exactly one skill's worth of work:**

- **Resolve the named skill** per *Resolving skill names*, so `daily brief`, `daily-brief` and `productivity:daily-brief` all land on the same target.
- **Create or update only its task**, with its own row from *The fixed schedule* — same cron, same task ID, same title, same version-free prompt as full mode would have written. **Nothing about the schedule changes because the mode did.**
- **Delete only its legacy IDs** from the *Migration* table — the row for that skill, not the whole table. A legacy task belonging to a skill that is out of scope keeps running, which is correct: that skill has not been migrated yet.
- **Report one row**, then the permissions block naming **only that skill**.
- **Never create the other two, and never mention them.** Not as a suggestion, not as a "you might also want", not as a note that they are unscheduled. Someone who scheduled one skill made a choice; listing the others turns a completed action into a sales pitch. If they want the rest, they will run those skills, or run `/allneurons-productivity:onboarding`.

**If the named skill cannot be resolved to one of the four**, say so plainly and stop. Do not fall back to scheduling all four — that is the opposite of what was asked, and it creates two tasks nobody requested.

## No refresh after an update — by design

**There is no refresh mode.** Rewriting a scheduled task from inside a scheduled run raises the app's **Update task** card, which would stall the next unattended run after every plugin update until someone clicked it. So this plugin removes the need instead of the card: task prompts are version-free pointers (*Thin task prompts*), every rule lives in the installed files, and a plugin update therefore reaches every task on its very next run with **no write, no card and no person** (shared §14).

- **A scheduled run never invokes this skill.** If one ever does — an older task's wording, a misread instruction — do nothing: no list, no update, no output, and return control immediately.
- **Older stamped tasks need no migration.** They already defer to the installed files, and shared §14 tells the run to treat their version and refresh wording as a label. They keep firing correctly on the new version as-is.
- **A person who wants tidy tasks** runs full or single-skill mode, which overwrite unconditionally into the version-free form. That is optional housekeeping, never a requirement.

## Why the worker skills hand off here

A worker skill could technically create its own task. It must not, and the reason is specific: **the prompts written here are the only ones carrying the "unattended scheduled run" marker, and that marker is the sole thing that identifies a run as scheduled when it later fires** (shared §1).

A task written without it would fire, be treated as a manual run, skip the weekend guard, and — because shared §10 checks whether a task exists — quite possibly offer to schedule itself all over again. One writer avoids all of that. So a worker skill's yes arrives here, in single-skill mode, and this skill does the writing.

## Migration — don't let a stray task double-send

This skill owns exactly four scheduled task IDs — `daily-brief`, `follow-ups`, `call-prep`, `competitive-insights` — and never writes to, updates, or deletes any other task ID. An existing task with one of these four IDs is reconciled in place by the normal Step 3 update, never deleted and recreated.

**A task that looks like it might be sending the same kind of email is flagged, never touched.** Among the tasks returned by `list_scheduled_tasks` in Step 3, check for any task whose **title** contains "Daily Brief", "Call Prep", "Follow-Ups" or "Competitive" (case-insensitive) but whose **ID** is not one of the three canonical IDs above. Report it plainly, one line, non-blocking, in the Step 7 report: "Found another scheduled task that looks like it might send a similar brief/prep/follow-up (`<title>`, id `<id>`) — this skill doesn't recognize it and won't touch it, but you may be getting duplicate emails from it; check and remove it by hand if so." **Never auto-delete an unrecognized task** — this check is informational only, and the person decides whether it's safe to remove.

## Resolving skill names

The four may be installed standalone (`daily-brief`) or inside a plugin (`<plugin>:<skill>`).

**The namespace never decides *which skill's content* is the right one — but it does gate the loosest match (rule 4 below), so this plugin can never silently substitute a different vendor's unrelated skill.** Whatever this plugin's own namespace is called or however it is spelled or capitalized — `allneurons-productivity`, the same name in any casing, a misspelling of it — only the part after the final `:` is compared for rules 1–3. Never hardcode, guess, or ask about this plugin's own namespace.

**Comparison is normalized:** lowercase, then strip every non-alphanumeric character. So `daily-brief`, `SUITE_DAILY_BRIEF`, and that same name capitalised or punctuated any way at all, every one normalizes to `productivitysuitedailybrief`.

**The recognized family** — the only namespaces this package will ever treat as "this same plugin": normalized to `productivitysuite`, or **no namespace at all** (a standalone install with no `plugin:` prefix). This is a fixed, closed list of exactly two entries — never expanded by inference, and never by matching on a brand word appearing *inside* a name from any other namespace.

For each target, scan the available-skills list and take the first match:

1. Normalized post-colon name **equals** the normalized target.
2. Normalized post-colon name **ends with** the normalized target.
3. Same two checks after stripping a leading `productivity-` from **both** sides before normalizing. This covers `productivity:daily-brief` naming. Strip the hyphenated segment, never bare letters from the normalized string.
4. **Only among candidates whose namespace is in the recognized family above**, normalized post-colon name **contains** the distinctive tokens — `dailybrief`, `followup`, `callprep` — and **exactly one such in-family candidate** matches. Never guess between two candidates, and **never apply this rule to a candidate outside the recognized family, no matter how closely its name matches** — a skill called `daily-brief` living inside some other, unrelated plugin (for example one named `anthropic-skills`, or any third-party plugin) is not this plugin under another name, and matching it here is exactly the bug this rule exists to prevent: a real run once resolved `daily-brief` to an unrelated example skill from a different plugin because both names happened to contain `dailybrief`, and the different skill has no house renderer, no shared layout, and produced a brief in the wrong format with no warning. Note `followup` also matches `follow-ups`, which is the correct skill — **within the family only**.

Ties at the same tier: prefer a namespace normalizing to `productivitysuite` or `productivity`; otherwise take the first. Record the resolved name verbatim.

**No match within the recognized family → still create the task** (the plugin may be installed later, under one of its recognized names) **and mark it `created — skill not currently visible`.** This is the correct outcome even when an out-of-family candidate with a similar name exists — silently running the wrong skill is worse than a task that waits for the right one to be installed.

## When a feature is not available — say what to ask, then fall back

Never fail silently and never leave the person without a next step. Name the cause, say exactly what to ask their admin, and offer the on-demand fallback.

| What is missing | What to say | Fallback that still works |
|---|---|---|
| **No scheduling tool** (plain claude.ai chat or Claude Code, or scheduled tasks turned off by the admin or the user) | "Recurring runs need Cowork with Scheduled tasks turned on. Ask your admin to enable Scheduled tasks, or open this in Cowork." | Every skill runs on demand: say "daily brief", "prep my calls", "find my follow-ups" or "competitive insights". |
| **Cloud runs not available** ("Run Cowork in the cloud" is off, common on Enterprise) | "Scheduled runs only fire while your computer is awake and the Claude app is open. To run while you are away, ask your admin to turn on Run Cowork in the cloud." | Tasks are still created and run locally. |
| **Sending email is blocked** (the admin has removed the send permission on Outlook or Gmail) | "Your admin has blocked sending email, so reports cannot be emailed to you. Ask them to allow the Mail send permission for the connector." | Skills still build the PDF, save it to your Drive and show the link in the chat. Follow-Ups drafts only need draft access and still work. |
| **Code execution and file creation is off** | "PDFs need Code execution and file creation. Ask your admin to turn it on." | The brief and reports are delivered as text in the chat. |
| **Drive writes are blocked or fail** | "Saving the PDF to your Drive failed. Ask your admin to allow file creation for the Drive connector." | The summary is shown in the chat with the exact error. |
| **A required connector is missing** | The Connect card from the connector gate. | Run `/allneurons-productivity:connectors` to see every gap. |

Say each message once, in plain words, with no internal tool names.

## What this skill cannot do — say it plainly, never pretend otherwise

**Permissions** on a scheduled task is **UI-only**. No parameter on the create or update action exposes it — they cover the task's id, title, description, prompt, schedule, completion notification and enabled flag — and nothing that touches permissions.

It defaults to *Manually approve*. Left there, every run halts waiting for a connector approval, and an unattended 6 AM run never completes.

So this skill **cannot** flip it, and must never claim it did or say "I've set them to automatic". It creates the tasks correctly and states the one thing the user must change — in a single line, per Step 7.

**Connector approvals cannot be pre-authorised from here either, and this skill must not pretend otherwise.** An approval prompt appears when a tool is first *called*, so the only way to trigger one is to make the call — which is exactly the data read Ground rule 2 forbids, and which would be doing the skills' work rather than scheduling it. The preflight above can tell you a connector *exists*; it cannot tell you the first unattended run will be allowed to use it.

**There are exactly two real remedies, and Step 7 gives the first:**

1. **Set Permissions to Automatically approve** on each task. This is the actual fix, and without it an unattended run stops on a prompt nobody is watching.
2. **Run each skill once by hand**, while you are watching, so any approval prompt surfaces where someone can clear it. This is a *confidence* step, not a fix: remedy 1 is what makes unattended runs work. Offer it in one clause, **only on a person-initiated full-mode run**, and never in place of remedy 1. On a §10 handoff, say nothing about it — the person is already doing exactly that.

## The only questions allowed

At most **three** cards in a whole run, and none of them is about a connector:

- **Delivery email** — skip if the user's own address is known from session context. Use their own address, never anyone else's.
**Timezone is never a question.** It is resolved, always — see *Timezone* below.
**No card for a connector gap, ever.** A missing or unreachable connector is answered with a Connect / Enable / Reconnect **button** from the connector prerequisite, plus the status table. That includes a missing tracker. If the delivery address is still unknown after session context, it is asked in one small card of its own — that is about an address, not a connector.

- **Call Prep meeting scope** — one `AskUserQuestion` call carrying **one** question (which meetings to prepare for), asked once, only in full mode or single-skill mode targeting `call-prep`, and only when Step 3's preflight found no `prep scope:` line already on record in `Skills/Call Prep/call-prep-settings.txt`. Never asked on a §10 handoff (the worker already has its own answer or will ask itself). Never re-asked once a preference is on record — see *Updating Call Prep preferences later* below.

- **The permissions confirmation** — one card at the very end of Step 5, asking whether Permissions has been set to Automatically approve. Never re-asked.

Nothing else. No day pickers, no time pickers, no "which of these three", no confirmation before creating, **and no card about any connector, mandatory or optional** — connectors get buttons. Never ask which plugin the skills came from — resolve it.

## Procedure

**Seven steps, in this order. Each one either produces something the next needs, or decides whether there is any point continuing.**

| # | Step | Produces | Skipped when |
|---|---|---|---|
| 1 | Establish mode and invocation | full vs single-skill; person vs handoff | never |
| 2 | Run the connector gate | the card and status table, if anything is missing | on a §10 handoff |
| 3 | Preflight | existing tasks, legacy tasks, version, timezone, dependencies, roles | preflight questions skipped on a handoff |
| 4 | Resolve skill names | the real name of each in-scope skill | never |
| 5 | Generate task prompts | one version-free prompt per in-scope skill | never |
| 6 | Write the tasks | the created/updated tasks, legacy ones deleted | never |
| 7 | Report and hand over permissions | the table, the gap block, the permissions block, one card | only on a Step 3 blocker stop |

**Step 1 — Establish the mode, and whether this is a handoff.** Was a target skill named? No → **full mode**, all four. Yes → **single-skill mode**, that skill only. Everything after this reads "in scope" accordingly.

Then note *how* you were invoked, because it changes what Step 1 does:

| Invoked by | Preflight |
|---|---|
| A person — `/allneurons-productivity:onboarding`, "onboard me", "schedule my follow-ups" | **Run it in full**, per Steps 2 and 3. |
| **A worker skill's §10 handoff** | **Skip the preflight entirely.** Do the task list read, the version read, and nothing else. |
| **A scheduled run** (should never happen) | **Do nothing and return.** Scheduled runs never write tasks (shared §14). |

**Why the handoff skips it.** That worker is already mid-run: it sorted the connector roles at its own start (shared §7), it already called `list_scheduled_tasks` (shared §10), and it already took the single `date` reading that shared §2 says is taken **once** per run. Re-detecting the roles tells nobody anything new, a second `date` call breaks §2, and printing a gap block mid-run collides with the coverage gaps the worker is about to report itself.

**And ask nothing on a handoff.** The worker has already spent its one permitted question on the offer that sent you here (shared §10); a second card is exactly the "never make the person ask twice" failure that rule exists to prevent. No blocker card either — the worker is running, so its connectors evidently work. Create the task, report one line, print the permissions block, return.

**Step 2 — Run the connector gate.** `${CLAUDE_PLUGIN_ROOT}/references/connector-prerequisite.md` owns it and is the authority: **Calendar, Mail and Drive (Microsoft 365 or Google Workspace) are mandatory**, Chat is optional, detection is by tool-name prefix, and each mandatory role gets one cheap probe because present is not the same as usable.

**Onboarding runs the gate like every other skill, and shows the same card — what differs is what happens next.** Its Part 1 table documents the variation: show the card, show the status table, then **carry on and create the tasks**, and say in one line that those scheduled runs will stay blocked until the missing role is connected. Scheduling for later is still useful while a connector is being connected now, and refusing would deadlock the very person trying to fix it.

**Skip this step on a §10 handoff.** The worker that sent you here is mid-run and already passed the gate at its own start; running it again costs three probes and tells nobody anything new.

**Step 3 — Preflight: list, version, timezone, dependencies, roles.** One parallel batch, and **nothing in it reads the user's data**:

- The scheduled-tasks list action — note which in-scope tasks already exist, matched by task ID **or exact title** (that decides create vs update, and more than one match for a skill is a duplicate to delete) **and which of their legacy IDs from *Migration* are present** (that decides what to delete).
- The `plugin.json` version read above.
- `date`, for the timezone — **`date +%Z` and `date +%z` together**, so both the name and the offset are captured.
- **One dependency check**, reporting each package separately, because they fail differently:
  ```bash
  python3 -c "
  for m in ('reportlab','pypdf','pypdfium2'):
      try: __import__(m); print(m,'ok')
      except ImportError: print(m,'MISSING')"
  ```
  A combined `import reportlab, pypdf` cannot tell which one failed, and the two have very different consequences (see the table).

**When `call-prep` is in scope** (full mode, or single-skill mode targeting it), add one more read to this same batch: a drive read of `Skills/Call Prep/call-prep-settings.txt`. This is reading one small settings file to check whether a `prep scope:` line already exists — it is not a calendar read or an email read, so it does not violate Ground rule 2. **If the file is missing, or has no `prep scope:` line, note it** — "no Call Prep preference on record — the new preference card will be shown in Step 4." **If it already has one, note that too** — "Call Prep preference already on record — not re-asked." Skip this read entirely when Call Prep is out of scope.

Then check the connector roles, **by tool name only**. A role is present if a tool for it is in this session; that is a look at the tool list, not a call to the tool. **One tool in a role is enough** — the point is that the role is covered, not which vendor covers it.

### Tier 0 — the one hard blocker

| Role | Any of | Missing means |
|---|---|---|
| **Scheduled tasks** | the session's scheduling tool | **Stop.** There is nothing to create a task with, so nothing this skill does is possible. State it plainly and end the run; no card, no partial setup. **Name the likely cause, not just the symptom:** scheduled/recurring tasks are a Cowork capability — a plain claude.ai or Claude Code chat has no scheduling tool at all, so this is the expected (and only) reason this blocker fires there. Say in one line that recurring runs need Cowork, and that the three skills can still be run by hand, any time, from this same session — onboarding is only what is unavailable, not the worker skills.  Use the wording and the on-demand fallback in *When a feature is not available*. |

### Tier 1 — the mandatory set: calendar, mail, drive

**The connector gate enforces these at the start of every run: without all three, no skill produces output. Each is satisfied by Microsoft 365 or Google Workspace, role by role and in any mix** — Outlook or Gmail, Outlook Calendar or Google Calendar, SharePoint/OneDrive or Google Drive (`references/connector-prerequisite.md` and `references/provider-map.md` own the detection and are the authority). Never ask which suite the person uses; the card offers both. A gap here is answered with a **Connect / Enable / Reconnect button**, never a question. The impacts below are what to put in the report — they are not a menu of choices.

| Role | Accepted providers | If skipped, the real impact |
|---|---|---|
| **Mail** | **Outlook / Microsoft 365 Mail** · **Gmail** | **The heaviest loss.** Mail is where the Daily Brief and Follow-Ups *deliver*, so with none connected neither arrives at all. It is also Follow-Ups' entire subject matter: no mailbox means **no drafts**, not merely no delivery. And it is half of the Daily Brief's already-handled check, so items you have answered by email will read as still open. Call Prep still delivers — it books calendar blocks — but loses the email history that gives an account its real status, and loses its failure report, which then shows up only as a calendar marker. |
| **Calendar** | **Outlook / Microsoft 365 Calendar** · **Google Calendar** | **Nothing runs without it.** Call Prep has no meetings to classify and nowhere to book; The Daily Brief loses every meeting, the timeline and all conflict detection, which is most of what a 6 AM brief is for. Follow-Ups still runs, without the meeting signal. |
| **Drive** | **SharePoint** · **OneDrive** · **Google Drive** | Where every rendered document is stored and linked from. Call Prep's briefings have nowhere to live, so its prep blocks have nothing to link to, and the Daily Brief has no PDF link to send. It is also Call Prep's research source for proposals, SOWs, security reviews and prior briefings. |

### Tier 2 — recommended, reported not asked

Each of these makes the output materially better. **None of them blocks anything** — unlike the mandatory three above — and a task created without one picks it up on a later run with no re-onboarding. **Where one is missing it still goes into the same `suggest_connectors` call, so the person gets a button rather than a sentence** — it simply does not stop the run.

| Role | Any one of | What you lose without it |
|---|---|---|
| **Tracking / tickets** | **Jira** · **GitHub** · **Linear** · **Asana** · **ClickUp** | The Daily Brief's *Due today & overdue* falls back to an email and chat keyword sweep, so **undated open work goes unreported entirely** — the commonest silent gap. Call Prep also loses ticket status as evidence for whether a commitment is genuinely still open. **This is the one Tier 2 role worth connecting before the first run**, because what it covers nothing else covers. |
| **Call intelligence / transcripts** | a meeting-recording or transcript connector | Call Prep's highest-value source. Briefs still render, noticeably thinner — no record of what was actually promised, no objections as they were really phrased, none of the words the other side used for their own problem. |
| **CRM** | **Salesforce** · **HubSpot** · **Pipedrive** | No stage, amount, renewal date or last-activity signal, so Call Prep's call-at-a-glance strip is largely empty and Follow-Ups cannot rank by deal proximity. |
| **Chat** | **Slack** · **Microsoft Teams** · **Google Chat** | A large share of real asks live in chat, and none of them will be seen. The Daily Brief loses its chat sweep — the source of most *Needs attention* items. Follow-Ups' 10-day coverage floor drops from three sources to two, so a promise made in chat is invisible. Call Prep loses the internal chatter that usually holds an account's real status. **The most valuable of the optional roles.** |
| **Web search** | always available | No public signal — news, funding, leadership moves. The brief says "no recent public signal found" and leans on internal history, which is usually the better source anyway. |

### Tier 2 — the renderer's Python packages

| Package | Missing means |
|---|---|
| **`reportlab`** | **No PDF at all.** Daily Brief and Call Prep fall back to content inline in the email body — still delivered, just not as a document. |
| **`pypdf`** | PDFs still render; the renderer falls back to a weaker self-check. Worth fixing, not urgent. |

Install line: `pip install --break-system-packages reportlab==5.0.1 pypdf==6.17.0 pypdfium2==5.13.0` (`pypdfium2` is optional — it adds the near-empty-page check).

### Timezone — resolved, never asked

**Every task is scheduled in the person's own local timezone, and the schedule is always the same wall-clock time for them: 4 AM, 6 AM, 4 PM.** On a local scheduler the times in *The fixed schedule* are written as-is; on a UTC scheduler they carry the `CRON_TZ=` prefix with the resolved zone. Either way the wall-clock time never changes.

**Never ask what timezone someone is in.** It is on the machine, and asking is both avoidable friction and a chance to get it wrong. Resolve it in this order and stop at the first that answers:

1. **`date +%Z` / `date +%z`** from the preflight batch. This is the machine's own timezone and is the answer in almost every case.
2. **The connected calendar's own timezone**, if `date` somehow returns nothing usable.
3. **Write the local times anyway.** On a local scheduler an unresolved *name* does not change when the task fires (on a UTC scheduler, use the calendar's zone from step 2 for `CRON_TZ=`; if even that is missing, say so in the Step 7 report) — it only means the stamped `TIMEZONE` parameter is less specific. Stamp what you have (`local`), note it in one clause in the Step 7 report, and carry on.

**A task is never scheduled in UTC, never in the plugin author's timezone, and never at a converted time.** If someone's machine says `Asia/Kolkata`, their Daily Brief fires at 6 AM IST — not 6 AM UTC, and not 11:30 AM local.

### What to do with all that

**Tier 0 missing → stop.** State it and end. Nothing else applies.

**Any mandatory role missing → a button, never a question.** `${CLAUDE_PLUGIN_ROOT}/references/connector-prerequisite.md` owns this entirely, and it overrides anything here: work its ladder until a Connect / Enable / Reconnect card is on screen, show the status table, and **do not raise an `AskUserQuestion` about the gap.**

**There is no "continue anyway" choice to offer.** An earlier version asked one — *connected them just now / continue anyway / stop here* — and a real run showed that card instead of the buttons, because the two connectors involved were installed but not reachable in this chat and the search reported them as connected. The gate's state table now covers that case, and the question is gone. Deciding how to proceed is not the person's problem to solve in a dialog box: they need the connector, and the button is the connector.

**A missing tracker is also a button, not a question.** Include it in the same `suggest_connectors` call as any mandatory gap, so one card carries everything. Never ask "connect a tracker first?" — and never suggest or ask about the other Tier 2 roles, which are reported and nothing more.

**What onboarding does differently from the three worker skills** is only what happens *after* the card: it creates the tasks anyway (Part 1 of the gate file), and says in one line that those runs stay blocked until the connector is in. It does not ask permission to do that.

**Only if the gate's whole ladder failed** — no registry tool in the session, or the suggest call errored — fall back to words: name the role, the vendors that satisfy it, and where to connect them, and say which rung failed. **Never lead with the manual instruction.**

**Then report and proceed** per Step 7.

**Step 4 — Resolve.** Resolve every in-scope skill name — all four in full mode, the named one in single-skill mode. Email comes from session context. Ask only for what is still unknown, in one batched question.

**Then, if `call-prep` is in scope AND Step 3 found no `prep scope:` on record**, ask one `AskUserQuestion` call carrying exactly **one** question — the "Call Prep meeting scope" card from *The only questions allowed*:

**"Which meetings would you like Call Prep to prepare for?"** — exactly 2 options:

- **"External meetings only"** — customer calls, vendor meetings, prospects and other meetings with someone outside your company. *(default)*
- **"Internal and external meetings"** — everything above, **plus** every internal meeting that has another person on it: 1:1s, team syncs, standups, recurring series. Solo focus blocks and holds are never prepped.

**There is no delivery question.** Call Prep is delivered one way: a private prep block on your calendar before each meeting, with the formatted card and the full briefing linked. There is no email option, and onboarding never asks about one. Earlier versions asked "calendar, email or both"; that question and its settings line are gone.

**Persistence.** Immediately after the card, write (or create, if it does not exist) `Skills/Call Prep/call-prep-settings.txt` with one `prep scope:` line — map "External meetings only" → `prep scope: external only`, "Internal and external meetings" → `prep scope: external and internal`. **Never write a `prep delivery:` line**, and drop one if an older file carries it. **Preserve `prep lead:` and `prep busy:` if present** — merge, don't clobber. Drop any `opted out:` or `booked:` list: Call Prep has no opt-out logic and ignores them. Use the same `conflictBehavior: replace` upload pattern Call Prep itself uses. **Read the file back after the write** and confirm the `prep scope:` line is there with the value the person chose; a write that did not land is reported in Step 7 as `scope choice not saved`, never skipped silently — a scope that is chosen and not saved is exactly how a person who picked both ended up with external-only prep. **If the drive role is not connected**, say in the Step 7 report that the preference was chosen but could not be persisted — Call Prep's own first manual run will ask again since nothing was written.

### Safe fallback for the Call Prep scope

If the settings write fails, or the card goes unanswered, or an answer is otherwise invalid or unclear, **never guess wider** — leave `prep scope` unset so Call Prep's own default applies on its next run: `external only`. Call Prep states the scope it used on the first card of every run, so a missing preference is visible, never silent. Delivery is not a preference and has no fallback: it is always the calendar block.

### Updating Call Prep preferences later

Re-running `/allneurons-productivity:onboarding` (full mode) or naming call-prep in single-skill mode does **not** re-ask the scope card once a `prep scope:` line is already present (per Step 3/Step 4's gate). To actually change the preference, the person should either edit the settings file directly at `Skills/Call Prep/call-prep-settings.txt`, or tell Call Prep directly when running it by hand. Implementing a spoken "change my preference" trigger inside Call Prep itself is out of scope for onboarding — this paragraph documents the supported path today, and invents no reset command that doesn't exist.

**Step 5 — Generate a prompt per in-scope skill** from the template below. **No version goes into it.** Four in full mode, one in single-skill mode.

**Step 6 — Write everything in a single message, in parallel:** every in-scope create/update plus their legacy deletes. In single-skill mode that is one create/update and possibly one delete — still one message. Use these exact task IDs and titles. **The title is a real parameter on the create and update actions** — it is the display name in the **Scheduled** list, and it is what the Step 7 instructions tell the user to look for, so pass it there and keep the string exact. The `description` is the separate one-line summary below it:

| Task ID | Title (exact) |
|---|---|
| `daily-brief` | `allNeurons Productivity Daily Brief` |
| `follow-ups` | `allNeurons Productivity Follow-Ups` |
| `call-prep` | `allNeurons Productivity Call Prep` |
| `competitive-insights` | `allNeurons Productivity Competitive Insights` |

### The prompt template

Substitute `{{SKILL}}` (the resolved name), `<target>` and `<tokens>` per skill, plus `{{TIMEZONE}}` and `{{USER_EMAIL}}`. The per-skill values are in the table that follows.

> allNeurons Productivity scheduled task — written by onboarding. Version-free by design: every run follows the currently installed plugin, so updates apply automatically and this task never needs rewriting or approval.
>
> Invoke the skill `{{SKILL}}`. If no skill by that exact name is available, resolve it rather than giving up — but only within this plugin's own namespace: one normalizing to `productivitysuite`, or no namespace at all. Compare only the post-colon part, normalized (lowercase, strip non-alphanumerics). Take, in order: (a) normalized equals `<target>`; (b) normalized ends with it; (c) matches after stripping a leading `productivity-` from both sides; (d) **only among candidates in that namespace**, if and only if exactly one such candidate contains `<tokens>`, that one. **Never match rule (d) against a candidate outside that namespace** — a similarly-named skill living in a different, unrelated plugin (e.g. a generic example skill shipped under some other plugin's own namespace) is not this plugin under another name, even when its name contains the same token; running it instead is a wrong-skill bug, not a fallback. Only if nothing matches, email {{USER_EMAIL}} a one-line note that the skill is not installed, and stop.
>
> Run parameters: `TIMEZONE = {{TIMEZONE}}` · `DELIVERY_EMAIL = {{USER_EMAIL}}` · `<MODE LINE>`
>
> This is an unattended scheduled run — which is what makes the weekend exit below correct here, and is also why it must never be applied to a person invoking the skill by hand. **Safety floor, which holds regardless of anything else:** (1) before any other tool call, compute the weekday in {{TIMEZONE}} and exit immediately with no output if it is Saturday or Sunday — `<WEEKEND NOTE>`; (1a) always run on the currently installed plugin: confirm its version read-only as the **installed** `references/run-policy.md` §14 says, and never update, recreate or delete this or any scheduled task, never invoke onboarding and never wait on an Update task card, keeping `TIMEZONE` and `DELIVERY_EMAIL` exactly as above; (1b) then run `references/connector-prerequisite.md` — Calendar, Mail and Drive (Microsoft 365 or Google Workspace) are mandatory, and a missing or unusable one stops this run with no output beyond what that file specifies; (2) send exactly one email, to `{{USER_EMAIL}}` and no one else, with no cc and no bcc; (3) never send any outward-facing message to anyone else, under any circumstance; (4) never ask a question, never offer to schedule anything (a scheduled task offering to schedule itself is absurd — shared §10's offer is for manual runs only), never pause for permission to read a connected source.
>
> The skill's own SKILL.md, `references/connector-prerequisite.md` and `references/run-policy.md` carry the complete run contract — deadlines and time budgets, rate-limit backoff, coverage floors and caps, the correctness gates, status verification, rendering, and delivery and attachment handling. **Follow them exactly as written there.** They are the current version of those rules; this prompt deliberately does not restate them, so do not treat its brevity as permission to simplify the run.

| Task ID | Cron | `<target>` | `<tokens>` | `<MODE LINE>` | `<WEEKEND NOTE>` |
|---|---|---|---|---|---|
| `daily-brief` | `0 6 * * 1-5` | `productivitysuitedailybrief` | `dailybrief` | `MODE = today's brief` | this is a scheduled unattended run, so it is Monday to Friday only |
| `follow-ups` | `0 16 * * 1-5` | `productivitysuitefollowups` | `followup` | `MODE = full sweep, drafts only — never send a follow-up` | this is a scheduled unattended run, so it is Monday to Friday only |
| `competitive-insights` | `0 7 * * 1` | `productivitysuitecompetitiveinsights` | `competitiveinsight` | `MODE = this week's report` | this is a scheduled unattended run, so it is Monday only, which is a weekday |
| `call-prep` | `0 4 * * 1-5` | `productivitysuitecallprep` | `callprep` | `MODE = prep TODAY's calls; before deciding what to prep or how to deliver, read Skills/Call Prep/call-prep-settings.txt and follow its prep scope line exactly — never assume external-only, and never hardcode a scope or a delivery mode into this task; Call Prep is always delivered as calendar blocks` | this is a scheduled unattended run, so it is Monday to Friday only — **today's weekday is the only check**, because a 4 AM run preps today |

**Descriptions** (no version suffix — a version in the description would be stale after the next update):

- `allNeurons Productivity Daily Brief` — Weekday 6 AM briefing: today's meetings, conflicts, what's due, open asks, emailed as one PDF.
- `allNeurons Productivity Follow-Ups` — Weekday 4 PM sweep: finds who needs a follow-up, drafts replies in your voice, never sends.
- `allNeurons Productivity Call Prep` — Weekday 4 AM prep: a private prep block before each external call today, with the dossier linked.
- `allNeurons Productivity Competitive Insights` — Monday 7 AM report: what your tracked competitors did this week, what it means, what to do, emailed as one PDF.

**Step 7 — Report, then the permissions instructions. Nothing else.**

First print one compact table: skill, cadence, local time, status (`created` / `updated` / `created — skill not currently visible`), plus a row per legacy or duplicate task removed. Name the installed plugin version once, above the table.

**Then, only if the preflight found anything missing**, one short block naming each gap and what it costs — one line each, in the words of the Step 3 tables. A clean preflight gets no block at all: a list of things that are fine is noise.

Order it by what it actually costs the client:

1. **Any Tier 1 gap first, in bold** — mail, calendar or chat — with the impact, and the fact that they chose to continue. This is the record of an informed decision, so it belongs in writing rather than only on a card that has been dismissed.
2. **No tracker**, if that is the case, in one line: undated open work will go unreported until one is connected.
3. **Everything else** in one line each, plainly. A missing renderer package belongs here, not at the top: it has a documented fallback.

End that block with one clause saying gaps close themselves — connect the tool and the next scheduled run picks it up, with no need to re-onboard.

Then print this block **verbatim**, substituting only `<VERSION>` — plus, in single-skill mode, the opening line and the skill list, exactly as described immediately after the block. Every name and label below is the exact string in the interface — do not paraphrase, retitle or "tidy" any of them:

> ## Enable automatic skill execution
>
> All four skills are installed and scheduled on the cadence above, running plugin v`<VERSION>`.
>
> To ensure they run automatically each day without requiring manual approval, update the schedule permissions for each one:
>
> 1. Go to **Scheduled** in the sidebar.
> 2. Locate the skill and click **Edit**.
> 3. Click **Edit** again to open the schedule settings.
> 4. Under **Permissions**, change **Manually approve** to **Automatically approve**.
> 5. Click **Save**.
>
> Repeat for all four skills:
>
> - **allNeurons Productivity Daily Brief**
> - **allNeurons Productivity Follow-Ups**
> - **allNeurons Productivity Call Prep**
> - **allNeurons Productivity Competitive Insights**
>
> Once **Automatically approve** is set, each skill runs on its schedule without asking you to approve anything.
>
> Plugin updates apply automatically — nothing to re-run or approve. To change settings or clear duplicate tasks, use `/allneurons-productivity:onboarding`.

**In single-skill mode, two lines change and nothing else does.** The opening line becomes `**<Title>** is scheduled on the cadence above, running plugin v`<VERSION>`.`, and the "Repeat for all four skills" list collapses to the single bullet for that skill — drop the word "Repeat" and the other two bullets. **In full mode, if any skill was reported `created — skill not currently visible`, the opening line says "scheduled" rather than "installed and scheduled"** — the task exists, the skill does not yet, and claiming otherwise sends the person looking for something that is not there. The numbered steps, every interface string, and the closing line stay exactly as written. **Never list a skill that was not scheduled this run**, which would send the person hunting in Scheduled for a task that is not there.

**Exact strings — never alter these.** The four task titles are `allNeurons Productivity Daily Brief`, `allNeurons Productivity Follow-Ups`, `allNeurons Productivity Call Prep` and `allNeurons Productivity Competitive Insights` — that capitalisation exactly, including the hyphen and capital **U** in **Follow-Ups**. The sidebar section is **Scheduled**, not "Schedule" or "Schedules". The button is **Edit**, clicked **twice** — once on the task, once again to reach the schedule settings. The setting is **Permissions**, its values are **Manually approve** and **Automatically approve**, and the confirm button is **Save**. If you find yourself writing "Automatic Approval", "Auto-approve", "Settings" or "allNeurons Productivity Follow-ups" (missing the capital U), you have got it wrong — go back to the strings above.

In full mode, list the four in schedule order — Call Prep (4 AM), Daily Brief (6 AM), Follow-Ups (4 PM), Competitive Insights (Monday 7 AM). In single-skill mode there is one bullet.

**Then one line on updates, verbatim:** `Plugin updates apply automatically: the next scheduled run uses the new version, with no update prompt and nothing to approve.`

**Then ask once whether it is done, and stop.** One `AskUserQuestion` card, the last thing in the run: *"Set Permissions to Automatically approve for each task?"* — **Done** / **I'll do it later**.

That card is the whole point of the block above. Left on *Manually approve*, every unattended run halts on a prompt nobody is there to click, and the person discovers it days later by noticing nothing ever arrived. **Asking closes the loop; printing instructions and hoping does not.**

- **Done** → acknowledge in one line and stop.
- **I'll do it later** → one line saying what that costs: the tasks exist but will not complete unattended until it is set. No lecture, no repetition.
- **No answer** → nothing further. Never re-ask, and never claim it was set.

**Then stop for real.** No second switch, no "Only on this computer" explanation, no Run-now fallback, no caveats, no recap of what the skills do, no offer to run one. The table, that block, and that one card **are** the entire ending. If you are about to add another paragraph, don't.

**"Stop" means stop adding to this output — it does not end the caller's run.** When a worker skill invoked this one via shared §10, control returns to that skill, which prints its own one line and then does the work the person actually asked for. Never treat the end of onboarding's report as the end of the session.

## Failure handling

- A failed create, update or delete → report that row as failed with the error, continue with the rest, and still finish with the table **and the Step 7 permissions block**. Never abandon the remaining work.
- An unresolved skill name → **not** a reason to skip. Create the task with the resolution preamble intact and flag it in the table.
- A failed version read → report the version as `unknown` above the table and still write **every task in scope** — all four in full mode, the one target in single-skill mode. A failed version read never widens the scope.
- A **blocker stop** at Step 3 (no scheduling tool) legitimately ends without the Step 7 block — there is no task to permit. Every other run that ends without it is incomplete.
- A run that ends without the Step 7 permissions block is incomplete. A run that pads past it is also wrong. A run that leaves an **in-scope** task in its old form, a duplicate in place, or an in-scope legacy task in place, is a **failed** run even if it reports success.
- **A single-skill run that creates more than the one task it was asked for is a failed run**, even though every task it wrote is correct. Scope was the instruction.

## Anti-patterns (do not)

- **Do not write a version into a task's prompt, title or description.** A stamp goes stale on the next release and forces a rewrite, which raises the Update task approval card.
- **Do not create a task without checking for an existing one by ID or exact title.** Duplicates fire the same skill twice.
- **Do not schedule in UTC by accident.** Where the scheduler evaluates cron in UTC, prefix `CRON_TZ=<IANA zone>` so 6 AM means 6 AM local.
- **Do not delete a task the user did not ask you to touch.** Remove only exact duplicates of this plugin's four skills.
- **Do not run from a scheduled task.** Onboarding is a manual, watched run; any approval card it raises is expected.

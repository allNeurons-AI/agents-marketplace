# Plugin defaults — one place

These are the defaults the skills and onboarding use. Each person's own values (timezone, delivery address) are resolved at onboarding and stored in the scheduled task. This plugin holds no secrets, API keys or tokens: all access goes through the connectors the user has authorised in Claude. Change a default here, bump the version, and add a CHANGELOG entry.

| Setting | Default | Where it applies |
|---|---|---|
| Plugin package name | `allneurons-productivity` | Never change: a different name installs a second plugin |
| Call Prep time | 4:00 AM local, Mon–Fri | onboarding schedule |
| Daily Brief time | 6:00 AM local, Mon–Fri | onboarding schedule |
| Follow-Ups time | 4:00 PM local, Mon–Fri | onboarding schedule |
| Competitive Insights time | Monday 7:00 AM local (weekly) | onboarding schedule |
| Competitive Insights profile | `Skills/Competitive Insights/profile.md` (stale after 90 days) | competitive-insights SKILL |
| Attach the Competitive Insights PDF | Only when the connected mail tool exposes an attachment parameter; otherwise link only | competitive-insights SKILL |
| Timezone | Resolved from the calendar, never asked | `TIMEZONE` in the task prompt |
| Delivery address | The user's own work address | `DELIVERY_EMAIL` in the task prompt |
| Microsoft concurrency cap | 3 Microsoft-backed calls per batch; Google-backed calls uncapped | run-policy §3 |
| Retries | One retry per failing step, then report the exact error | run-policy §3 |
| Daily Brief length | 2-page soft target, never withheld | render_brief.py |
| Call Prep block length | 10 minutes, timed, private, never all-day | call-prep SKILL |
| Call Prep settings file | `Skills/Call Prep/call-prep-settings.txt` | call-prep SKILL |
| Brief upload folder | `Skills/Daily Brief` | daily-brief SKILL |
| Follow-Ups coverage | Last 10 calendar days | follow-ups SKILL |

## Why a first run can take ~15-20 minutes — an intentional trade-off, not a bug

Every skill's own deadline table already documents this per-run, but it is worth stating once, plainly, in one place: **the run time is a deliberate consequence of the correctness requirements above it, not an accidental inefficiency.** Three things specifically buy time for coverage rather than spending it for no reason:

1. **Pagination-to-completion** (Follow-Ups Rule 1, Daily Brief's batch reads) — a search is not done until its cursor is exhausted, because stopping at page 1 is the confirmed root cause of real missed follow-ups. A mailbox with a long history pays for this in wall-clock time on the *first* run especially, before caches or narrower windows apply.
2. **The 10-calendar-day zero-gap coverage floor** (Follow-Ups) — non-negotiable, and explicitly senior to the run's own deadline table: if the floor is not done when the clock says stop, the run keeps going until it is.
3. **The 3-concurrent-call Microsoft cap** (run-policy §3) — deliberately one below Microsoft Graph's own 4-call ceiling, so a stack with many Outlook/Teams/SharePoint reads turns what would be one round trip into several sequential ones. This is the single biggest multiplier on a Microsoft-heavy account (a Google Workspace stack has no such cap and is typically faster), and it is set conservatively on purpose: the alternative is tripping Microsoft's own throttling, which costs more time than the cap does and can fail a run outright.

**None of these are candidates for silently trading away** to make a first run faster — each one exists because removing it previously caused a real, reported correctness failure (a missed follow-up, an incomplete floor, a rate-limit failure). If ~15-20 minutes for a first, cold run is unacceptable for a given deployment, that is a product decision — narrowing the lookback windows, raising the Microsoft cap (at the cost of more frequent throttling), or splitting the run across more, shorter windows — and belongs to whoever owns this plugin deployment to decide explicitly, not something Claude should trade away unilaterally. Subsequent runs are materially faster in practice because the 10-day floor and the 21-day window overlap with what was already covered the day before.

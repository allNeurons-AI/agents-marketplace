# Example Competitive Insights profile

This is an **example**, not a default: it shows the shape of the file the skill **writes for itself** (no question is ever asked) to the person's own drive at
`Skills/Competitive Insights/profile.md`. The skill discovers the company group and the competitors on its own and rewrites the person's copy as it learns more; a person may also edit it by hand. Nothing in the plugin depends on these names — they are invented.

```
company: Northwind Holdings
about: Parent company of a logistics software product and a freight-analytics product.
profile confirmed: 2026-10-06

entity: Northwind Route | northwindroute.example | Route-planning and dispatch software for regional carriers.
entity: Northwind Insight | northwindinsight.example | Freight analytics and cost-benchmarking platform.
entity: Northwind Holdings | northwind.example | Parent company; builds and operates the products above.

set A (Northwind Route): Route Planning Software
- Example Competitor A: One-line description of what it does and who it sells to.
- Example Competitor B: Another one-line description.

set B (Northwind Insight): Freight Analytics
- Example Competitor C: One-line description of what it does and who it sells to.

set C (Northwind Holdings): Logistics Services
- Example Competitor D: One-line description of what it does and who it sells to.
```

Format rules: `company:`, `about:`, `profile confirmed:` (last verified) lines, then one `entity: <name> | <domain or -> | <what it does>` line for **every** company in the group (the user's own company, the parent, each sibling, subsidiary, brand), then one `set <key> (<entity name>): <market>` block per set with `- <name>: <one-line description>` lines. Every entity must have at least one set (the parser and the PDF format gate both fail otherwise). The renderer's `group[]` and `sets[]` are built straight from these lines.

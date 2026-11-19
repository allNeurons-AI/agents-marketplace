"""Parse and validate the Competitive Insights profile (``Skills/Competitive Insights/profile.md``).

The profile is the person's own data, kept in their drive, so nothing about their company or competitors is baked into
the plugin. ``parse`` turns it into the ``company`` / ``sets`` part of the renderer payload and reports every defect, so
a malformed profile fails the run with a specific reason (exit 6) instead of producing a report about the wrong things.

v1.11.0: the profile also lists the WHOLE COMPANY GROUP, one ``entity: <name> | <domain> | <what it does>`` line for the
signed-in user's own company and every parent, sibling, subsidiary, brand or product company associated with it, and every
``set`` names the entity it belongs to (``set A (<entity name>): <market>``). An entity with no competitor set, or a
set that names an entity that is not listed, is a defect: that is how an associated company can no longer be left out of the
analysis. Nothing here is asked of the person; the skill derives all of it itself (SKILL.md Step 2).

CLI  competitive_profile.py parse --in profile.md [--today YYYY-MM-DD]   -> JSON {"ok","company","about","confirmed","age_days","stale","entities","sets"}
Exit 0 ok · 2 unreadable · 6 invalid (reasons on stderr)
"""
import argparse
import datetime as dt
import json
import re
import sys

STALE_DAYS = 90


def parse(text, today=None):
    out, errs = {"company": "", "about": "", "confirmed": "", "entities": [], "sets": []}, []
    cur = None
    for raw in (text or "").splitlines():
        ln = raw.strip()
        if not ln or ln.startswith("```") or ln.startswith("#"):
            continue
        m = re.match(r"^(company|about|profile confirmed)\s*:\s*(.+)$", ln, re.I)
        if m:
            k = m.group(1).lower()
            out["confirmed" if k == "profile confirmed" else k] = m.group(2).strip()
            continue
        m = re.match(r"^entity\s*:\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*(.+)$", ln, re.I)
        if m:
            dom = m.group(2).strip().lower()
            out["entities"].append({"name": m.group(1).strip(), "domain": "" if dom in ("-", "n/a", "none") else dom,
                                    "description": m.group(3).strip()})
            continue
        if re.match(r"^entity\s*:", ln, re.I):
            errs.append("entity line must be 'entity: <name> | <domain or -> | <what it does>': %r" % ln[:70])
            continue
        m = re.match(r"^set\s+([A-Za-z0-9]+)\s*(?:\(([^)]+)\))?\s*:\s*(.+)$", ln, re.I)
        if m:
            cur = {"key": m.group(1).upper(), "entity": (m.group(2) or "").strip(), "name": m.group(3).strip(), "competitors": []}
            out["sets"].append(cur)
            continue
        m = re.match(r"^[-*]\s+([^:]+?)\s*:\s*(.+)$", ln)
        if m and cur is not None:
            cur["competitors"].append({"name": m.group(1).strip(), "description": m.group(2).strip()})
        elif ln.startswith(("-", "*")):
            errs.append("competitor line outside a set or without a description: %r" % ln[:60])
    if not out["company"]:
        errs.append("company: line is missing")
    if not out["sets"]:
        errs.append("no 'set <key>: <name>' block found")
    ents = [e["name"].lower() for e in out["entities"]]
    if not ents:
        errs.append("no 'entity:' lines: list the signed-in user's company and every associated company (parent, sibling, "
                    "subsidiary, brand, product company); re-run discovery (SKILL.md Step 2)")
    if len(ents) != len(set(ents)):
        errs.append("an entity is listed twice")
    for s_ in out["sets"]:
        if ents and not s_["entity"]:
            errs.append("set %s does not name its company, e.g. 'set %s (<entity name>): %s'" % (s_["key"], s_["key"], s_["name"]))
        elif s_["entity"] and s_["entity"].lower() not in ents:
            errs.append("set %s names company %r, which is not listed as an entity" % (s_["key"], s_["entity"]))
    covered = {s_["entity"].lower() for s_ in out["sets"] if s_["entity"]}
    for e in out["entities"]:
        if e["name"].lower() not in covered:
            errs.append("company %r has no competitor set: every associated company must be analysed" % e["name"])
    keys = [s["key"] for s in out["sets"]]
    if len(keys) != len(set(keys)):
        errs.append("duplicate set key")
    for s in out["sets"]:
        if not s["competitors"]:
            errs.append("set %s has no competitors" % s["key"])
    names = [c["name"].lower() for s in out["sets"] for c in s["competitors"]]
    if len(names) != len(set(names)):
        errs.append("a competitor is listed twice")
    out["age_days"], out["stale"] = None, False
    if out["confirmed"]:
        try:
            age = ((today or dt.date.today()) - dt.date.fromisoformat(out["confirmed"])).days
            out["age_days"], out["stale"] = age, age > STALE_DAYS
        except ValueError:
            errs.append("profile confirmed: %r is not YYYY-MM-DD" % out["confirmed"])
    else:
        errs.append("profile confirmed: line is missing")
    return out, errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["parse"]); ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--today")
    a = ap.parse_args(argv)
    try:
        text = open(a.inp, encoding="utf-8").read()
    except OSError as e:
        print("INPUT ERROR: %s" % e, file=sys.stderr)
        return 2
    out, errs = parse(text, dt.date.fromisoformat(a.today) if a.today else None)
    for e in errs:
        print("PROFILE ERROR: " + e, file=sys.stderr)
    print(json.dumps(dict(ok=not errs, **out), ensure_ascii=False))
    return 6 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

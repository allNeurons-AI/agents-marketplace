#!/usr/bin/env python3
"""Capture the assets a skill call generates, tied to the skill execution that produced them ().

Skills ROI counts what a skill produced. Assets made during a Cowork skill call (the PDF, the saved copy, a rendered
image, an exported file) were not reaching it because nothing recorded them against the call: they were written to the
session's outputs folder and forgotten. This module is the plugin-side half of the fix: every skill run appends one
record per generated asset to an append-only manifest, keyed by skill, run and session, with a content hash and name so a
re-render of the same file is not counted twice and a different file is never lost.

Manifest line (JSONL, ``roi-assets.jsonl``):
  {"ts","skill","run_id","session_id","name","path","kind","bytes","sha256","link","source"}

  * skill       one of SKILLS, given by the caller or inferred from the file name; an asset whose skill cannot be
                established is recorded as "unassigned" (visible, never silently dropped or guessed).
  * run_id      one id per skill execution (callers pass the same id to every record of the run)
  * session_id  the Cowork/Claude session, read from the environment (SUITE_SESSION_ID, CLAUDE_CODE_SESSION_ID,
                CLAUDE_SESSION_ID, in that order) when not passed
  * link        the verified drive link when the asset was uploaded, else null

Stdlib only.
CLI
  roi_assets.py record --manifest m.jsonl --skill daily-brief --run R --file x.pdf [--link URL]
  roi_assets.py scan   --manifest m.jsonl --run R --dir /mnt/user-data/outputs [--skill S] [--since EPOCH]
  roi_assets.py summary --manifest m.jsonl [--run R]
Exit: 0 ok · 2 unreadable input / missing file
"""
import argparse
import hashlib
import json
import os
import sys
import time

SKILLS = ("daily-brief", "follow-ups", "call-prep", "competitive-insights")
KINDS = {".pdf": "pdf", ".docx": "docx", ".xlsx": "xlsx", ".pptx": "pptx", ".csv": "csv", ".png": "image", ".jpg": "image",
         ".jpeg": "image", ".svg": "image", ".md": "markdown", ".html": "html", ".txt": "text", ".json": "json"}
HINTS = (("daily-brief", "daily-brief"), ("daily_brief", "daily-brief"), ("dailybrief", "daily-brief"),
         ("call-prep", "call-prep"), ("call_prep", "call-prep"), ("callprep", "call-prep"),
         ("follow-up", "follow-ups"), ("followup", "follow-ups"), ("follow_up", "follow-ups"),
         ("competitive", "competitive-insights"))
SCRATCH = ("__pycache__", ".tmp", "~$")


def session_id(env=os.environ):
    for k in ("SUITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID"):
        if env.get(k):
            return env[k]
    return ""


def infer_skill(name):
    n = name.lower()
    for hint, skill in HINTS:
        if hint in n:
            return skill
    return "unassigned"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(manifest):
    out = []
    if os.path.exists(manifest):
        for ln in open(manifest, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass                        # a torn last line never blocks the next run
    return out


def record(manifest, path, skill=None, run_id="", link=None, source="skill", env=os.environ, now=None):
    """Append one asset record; returns it, or None when this exact file is already recorded for this skill and run."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    name = os.path.basename(path)
    skill = skill or infer_skill(name)
    if skill not in SKILLS + ("unassigned",):
        raise ValueError("unknown skill %r" % skill)
    rec = {"ts": int(now if now is not None else time.time()), "skill": skill, "run_id": run_id or "",
           "session_id": session_id(env), "name": name, "path": os.path.abspath(path),
           "kind": KINDS.get(os.path.splitext(name)[1].lower(), "other"), "bytes": os.path.getsize(path),
           "sha256": sha256(path), "link": link, "source": source}
    for r in read(manifest):
        if (r.get("sha256"), r.get("name"), r.get("skill"), r.get("run_id")) == (rec["sha256"], name, skill, rec["run_id"]):
            if link and not r.get("link"):       # same file, link arrived later: record the linked version too
                break
            return None
    d = os.path.dirname(os.path.abspath(manifest))
    os.makedirs(d, exist_ok=True)
    with open(manifest, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def scan(manifest, directory, run_id="", skill=None, since=0, env=os.environ):
    """Record every asset under ``directory`` modified since ``since`` (epoch). The sweep that catches assets a skill
    wrote to the outputs folder without calling ``record`` itself."""
    made = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SCRATCH]
        for fn in sorted(files):
            if fn.startswith(".") or fn.startswith(SCRATCH[2]) or os.path.splitext(fn)[1].lower() not in KINDS:
                continue
            p = os.path.join(root, fn)
            if os.path.getmtime(p) >= since:
                r = record(manifest, p, skill, run_id, source="scan", env=env)
                if r:
                    made.append(r)
    return made


def summary(manifest, run_id=None):
    recs = [r for r in read(manifest) if run_id is None or r.get("run_id") == run_id]
    by = {}
    for r in recs:
        by.setdefault(r["skill"], {"assets": 0, "bytes": 0, "linked": 0})
        s = by[r["skill"]]
        s["assets"] += 1; s["bytes"] += r.get("bytes", 0); s["linked"] += 1 if r.get("link") else 0
    return {"assets": len(recs), "by_skill": by, "unassigned": by.get("unassigned", {}).get("assets", 0)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record"); r.add_argument("--manifest", required=True); r.add_argument("--skill"); r.add_argument("--run", default="")
    r.add_argument("--file", required=True); r.add_argument("--link")
    s = sub.add_parser("scan"); s.add_argument("--manifest", required=True); s.add_argument("--run", default=""); s.add_argument("--dir", required=True)
    s.add_argument("--skill"); s.add_argument("--since", type=float, default=0)
    m = sub.add_parser("summary"); m.add_argument("--manifest", required=True); m.add_argument("--run")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "record":
            print(json.dumps(record(a.manifest, a.file, a.skill, a.run, a.link)))
        elif a.cmd == "scan":
            print(json.dumps({"recorded": len(scan(a.manifest, a.dir, a.run, a.skill, a.since))}))
        else:
            print(json.dumps(summary(a.manifest, a.run)))
    except (OSError, ValueError) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

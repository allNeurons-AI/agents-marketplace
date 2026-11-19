#!/usr/bin/env python3
"""Self-evaluation and run memory ("brain") for the three PDF skills. Deterministic, local, no network, no questions.

  evaluate(kind, pdf, manifest)   -> {"passed", "score", "issues"}   checks the finished PDF against the hard rules:
                                     a real PDF, <= byte budget, <= page cap, every source link clickable, no run-coverage
                                     noise ("Read 3 of 25+ ..."), text extractable.
  record(kind, manifest, result)  -> remembers how the run went (tier, bytes, pages, whether the squeeze loop was needed and
                                     the description length that finally fit).
  hints(kind)                     -> short writing guidance for the NEXT run, learned from the last ones: the description
                                     length and list sizes that fit the page cap first time. The skills call this before
                                     they write the payload, so reports get tighter by themselves and the squeeze loop
                                     is needed less and less.
  start_in_squeeze(kind)          -> True when the last three runs of this kind all needed the squeeze loop: deliver_prepare
                                     then skips the tiers that cannot fit and goes straight to it.

State file: $SUITE_BRAIN_DIR/brain.json (default ~/.allneurons-productivity-brain/brain.json). Any read or write problem is ignored: the brain
only ever makes runs faster and tighter, it never blocks one.
CLI:  python3 brain.py hints --kind daily_brief | show | reset
"""
import json
import os, tempfile
import re
import sys

MAX_HISTORY = 12
NOISE = re.compile(r"\b(read|opened|reviewed|scanned|searched)\s+\d+\+?\s+of\s+\d+\+?|\bnot swept this run\b|\bmatched (chat|email|message)", re.I)
DEFAULT_CAPS = {"daily_brief": 4, "call_prep": 2, "competitive_insights": 6}


def _path():
    return os.path.join(os.environ.get("SUITE_BRAIN_DIR") or os.path.join(tempfile.gettempdir(), "allneurons-productivity-brain"), "brain.json")


def load():
    try:
        with open(_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(state):
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1)
    except Exception:
        pass


def evaluate(kind, pdf, budget=None, page_cap=None, expected_urls=()):
    """Score a finished PDF. 100 = every rule met; each failed rule costs points; `passed` needs no hard failure."""
    issues, hard = [], False
    if budget is None:
        budget = 22500 if kind == "competitive_insights" else 20000
    if page_cap is None:
        page_cap = DEFAULT_CAPS.get(kind)      # 0 = no page cap
    try:
        raw = open(pdf, "rb").read()
        if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-2048:]:
            issues.append("not a complete PDF"); hard = True
        if budget and len(raw) > budget:
            issues.append("%d bytes, over the %d budget" % (len(raw), budget)); hard = True
        from pypdf import PdfReader
        r = PdfReader(pdf)
        pages = len(r.pages)
        if page_cap and pages > page_cap:
            issues.append("%d pages, cap %d" % (pages, page_cap)); hard = True
        text = "\n".join((p.extract_text() or "") for p in r.pages)
        if len(text.strip()) < 40:
            issues.append("no extractable text"); hard = True
        m = NOISE.search(text)
        if m:
            issues.append("run-coverage noise in the PDF: %r" % m.group(0))
        links = set()
        for pg in r.pages:
            for a in pg.get("/Annots") or []:
                uri = (a.get_object().get("/A") or {}).get("/URI")
                if uri:
                    links.add(str(uri))
        for u in expected_urls:
            if u not in links:
                issues.append("source link not clickable: " + u); hard = True
    except Exception as e:
        issues.append("could not read the PDF: %s" % e); hard = True; pages = None; raw = b""
    score = max(0, 100 - sum(40 if "over the" in i or "cap" in i or "not a complete" in i else 15 for i in issues))
    return {"passed": not hard and not issues, "hard_fail": hard, "score": score, "issues": issues, "pages": pages, "bytes": len(raw)}


def record(kind, manifest, result):
    s = load()
    k = s.setdefault(kind, {"runs": []})
    sq = (manifest or {}).get("squeeze") or {}
    cap = None
    m = re.search(r"about (\d+) characters", str(sq.get("last_step", "")))
    if m:
        cap = int(m.group(1))
    k["runs"] = (k.get("runs", []) + [{
        "tier": (manifest or {}).get("tier"), "squeezed": bool(sq), "squeeze_step": sq.get("last_step"), "text_cap": cap,
        "list_cut": bool(sq.get("omitted")), "bytes": (result or {}).get("bytes"), "pages": (result or {}).get("pages"),
        "score": (result or {}).get("score"), "issues": (result or {}).get("issues", [])[:3]}])[-MAX_HISTORY:]
    _save(s)


def start_in_squeeze(kind):
    runs = load().get(kind, {}).get("runs", [])
    return len(runs) >= 3 and all(r.get("squeezed") for r in runs[-3:])


def hints(kind):
    runs = load().get(kind, {}).get("runs", [])
    cap_pages = DEFAULT_CAPS.get(kind)
    lines = ["Hard limits: at most %s pages and %s KB, every section present, only meaningful content (no run-coverage notes)." % (cap_pages, "22" if kind == "competitive_insights" else "20")]
    sq = [r for r in runs[-5:] if r.get("squeezed")]
    if sq:
        caps = [r["text_cap"] for r in sq if r.get("text_cap")]
        c = min(caps) if caps else 160
        lines.append("Recent runs had to be shortened to fit: keep every description to about %d characters (one or two sentences) "
                     "and every bullet list to 3 items or fewer, in priority order, so nothing is cut for you." % c)
        if any(r.get("list_cut") for r in sq):
            lines.append("Lists were also cut: include only the items that need action, not every item you found.")
    else:
        lines.append("Recent runs fit without cutting: keep the same level of detail.")
    bad = [i for r in runs[-3:] for i in r.get("issues", [])]
    if bad:
        lines.append("Last issues seen: " + "; ".join(sorted(set(bad))[:3]) + ".")
    return "\n".join(lines)


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a or a[0] not in ("hints", "show", "reset"):
        print(__doc__); return 2
    if a[0] == "show":
        print(json.dumps(load(), indent=1)); return 0
    if a[0] == "reset":
        _save({}); return 0
    kind = a[a.index("--kind") + 1] if "--kind" in a else "daily_brief"
    print(hints(kind)); return 0


if __name__ == "__main__":
    sys.exit(main())

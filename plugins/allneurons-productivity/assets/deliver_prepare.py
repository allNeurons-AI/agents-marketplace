#!/usr/bin/env python3
"""deliver_prepare.py -- the single entry point that turns a payload into upload-ready PDF(s), whatever the size.

The PDF must reach the Drive (SharePoint/OneDrive or Google Drive) and be linked in every Daily Brief and Call Prep run, regardless of size. The upload tool
takes the file only as text the model types (`content`, ASCII, gate ceiling verify_pdf.PASTE_CEILING_TEXT_CHARS), so this
script picks, deterministically and with no human choice, the first of these tiers that fits:

  full       full-design ASCII PDF                              (suite_pdf_design.py, the normal case)
  lite       same payload, LITE layout, ~40% of the size        (render_lite.py)
  compact    same payload, lite type sizes, byte overhead removed (render_compact.py: no per-page decoration, one text
             object per page, item lines and sources merged -- type never below the design floor, every item kept)
  multipart  N independent compact PDFs  <name>_part1ofN.pdf ... <name>_partNofN.pdf, each under the ceiling, packed
             in order at item boundaries; every part is a complete valid PDF that states "part k of N" in its title and
             footer and repeats its section headings; together they hold every item. Nothing is truncated or dropped.

Every part is run through verify_pdf.py's gate (--text writes the paste file). Exit non-zero only on a genuine failure:
2 input unreadable, 6 payload fails the format/accuracy gate, 3 a render or gate failure in every tier
(including multipart). Prints ONE JSON line on stdout:

  {"tier":"full|lite|compact|multipart","ceiling":60000,"md":"...",
   "parts":[{"index":1,"of":1,"filename":"X.pdf","pdf":"...","txt":"...","bytes":N,"expectedBytes":N,"pages":N,
             "sha256":"...","paste_mode":"content","readback_phrases":[...]}],
   "attempts":[{"tier":"full","bytes":N,"fits":false,"note":""}, ...],
   "fulldesign": null | {"pdf":"..._fulldesign.pdf","upload_as":"<name>.pdf","bytes":N,"pages":N,"readback_phrases":[...]}}
`fulldesign` is the over-ceiling full-design PDF, present only when tier != full: it is kept so the run can save it to its
outputs; the typed upload sends `parts`.

Usage:
  python3 deliver_prepare.py --kind daily_brief --in brief.json --out-dir OUT --name Daily_Brief_2026-10-01
  python3 deliver_prepare.py --kind call_prep   --in call.json  --out-dir OUT --name 1200-acme
Options:
  --start-tier lite|compact|multipart   skip the tiers before this one. Use it after a typed upload of the previous
                                        tier was stopped or refused: the next call goes one tier smaller, never the same text again.
  --ceiling N                           paste ceiling in bytes (default verify_pdf.PASTE_CEILING_TEXT_CHARS); for tests
"""
import argparse
import copy
import re
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import suite_pdf as core                 # noqa: E402
import suite_pdf_design as design        # noqa: E402
import render_compact                     # noqa: E402
import verify_pdf                         # noqa: E402

TIERS = ("full", "flate", "digest", "digest2", "digest3", "plain", "multipart")
# "lite" and "compact" were plain-text layouts with no colour blocks. They are retired: asking for either now means "flate",
# the SAME full design (stat tiles, tinted cards, accent bars, chips) with Flate-compressed streams. Shrinking never strips the design.
TIER_ALIASES = {"lite": "flate", "compact": "flate"}
DIGEST_CAP = {"digest": 600, "digest2": 300, "digest3": 140}   # max characters kept per descriptive block
# Kinds with one design only (no lite/compact/multipart renderer). When the full PDF is over the paste ceiling the manifest
# carries it in "fulldesign" with no typed "parts", and the run saves it to its outputs and reports
# the real reason; it is never silently shrunk or cut.
SINGLE_TIER = ("competitive_insights",)
PAGE_CAPS = {"daily_brief": 4, "call_prep": 2, "competitive_insights": 6}     # hard page ceilings (0 / no entry = off)

_NOISE_RE = re.compile(r"^\s*(read|opened|reviewed|scanned|searched)\s+\d+\+?\s+of\s+\d+\+?|\bwere not (opened|swept|read)\b|\bnot swept this run\b|"
                       r"\bmatched (chat|email|message)", re.I)


def _is_noise_item(it):
    if isinstance(it, dict):
        if it.get("informational") is True:
            return True
        return any(isinstance(it.get(k), str) and _NOISE_RE.search(it[k]) for k in ("action", "title", "body", "text", "note"))
    return isinstance(it, str) and bool(_NOISE_RE.search(it))


def strip_noise(kind, data):
    """Keep only meaningful content in the PDF: run-coverage notes ("Read 3 of 25+ matched chat messages ..."), the
    classification line and any other statement about the run itself are removed from the payload before drawing."""
    d = copy.deepcopy(data)
    if "classification_note" in d:
        d["classification_note"] = ""
    for k, v in list(d.items()):
        if isinstance(v, list) and v and k not in ("sources",):
            d[k] = [x for x in v if not _is_noise_item(x)]
    return d


def pdf_pages(path):
    try:
        from pypdf import PdfReader
        return len(PdfReader(path).pages)
    except Exception:
        return None
# Shrink ladder for typed uploads -- ONE PDF, ONE link, always. A typed upload that is stopped/refused is never retried at
# the same size: the next call sends a smaller version of the SAME single file.
#   flate    compact layout, every item and word kept, content streams Flate-compressed (~4x smaller), sent as base64
#   digest*  flate + each descriptive block trimmed to 600 / 300 / 140 characters (headline, owner, by-when, status and
#            sources are never trimmed; no item is dropped)
# Multipart (several PDFs) is no longer in the default chain; it exists only behind --allow-parts.
RUNGS = ((0, None, "full"), (1, None, "flate"), (2, None, "digest"), (3, None, "digest2"), (4, None, "digest3"), (5, None, "plain"))
RESERVE = 256          # headroom while packing parts: the final "part k of N" title can be a few bytes longer


def _log(msg):
    print(msg, file=sys.stderr)


def _ascii_ok(path):
    b = open(path, "rb").read()
    return b.startswith(b"%PDF-") and all(x < 128 and x != 0 for x in b)


def _render(tier, kind, data, path):
    """Render one single-PDF tier. Raises on a genuine failure (incl. core.ContentVolumeError)."""
    if tier == "compact":
        render_compact.draw(kind, data, path)
    else:
        design.LITE = (tier == "lite")
        core.RENDERERS[kind](data, path)
        design.LITE = False
    ok, problems = core.verify(path)
    if not ok:
        raise RuntimeError("render check failed: " + "; ".join(problems[:3]))


def _flate(src, dst):
    """Same pages, same text, content streams Flate-compressed. Output is binary, so it is delivered as base64."""
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter(clone_from=PdfReader(src))
    for pg in w.pages:
        pg.compress_content_streams()
    w.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    with open(dst, "wb") as f:
        w.write(f)
    _objstm(dst)
    _compress(dst, max_level=2)


def _compress(path, budget=None, max_level=2, check=None):
    """Run compressor.py's self-loop over the file in place (levels 0-4; 2 = invisible precision, 4 = whole points)."""
    try:
        import compressor
        tmp = path + ".cmp"
        r = compressor.compress_to_budget(path, tmp, budget, max_level=max_level, check=check)
        if os.path.getsize(tmp) < os.path.getsize(path):
            os.replace(tmp, path)
        elif os.path.exists(tmp):
            os.remove(tmp)
        return r
    except Exception as e:
        print("NOTE: compressor skipped (%s: %s)" % (type(e).__name__, e), file=sys.stderr)
        return None


def _objstm(path):
    """Extra lossless squeeze (~20-25% smaller): pack the page/annotation dictionaries into compressed object streams.
    Optional -- when pikepdf is missing or fails, the Flate file written above is kept as it is."""
    try:
        import pikepdf
        from pypdf import PdfReader
        tmp = path + ".objstm"
        with pikepdf.open(path) as pdf:
            pdf.save(tmp, object_stream_mode=pikepdf.ObjectStreamMode.generate, compress_streams=True, recompress_flate=True,
                     stream_decode_level=pikepdf.StreamDecodeLevel.generalized)
        a, b = PdfReader(path), PdfReader(tmp)
        same = len(a.pages) == len(b.pages) and all((x.extract_text() or "") == (y.extract_text() or "") for x, y in zip(a.pages, b.pages))
        if same and os.path.getsize(tmp) < os.path.getsize(path):
            os.replace(tmp, path)
        else:
            os.remove(tmp)
    except Exception as e:                       # never let the optional squeeze break a delivery
        print("NOTE: object-stream squeeze skipped (%s: %s)" % (type(e).__name__, e), file=sys.stderr)
        try:
            os.remove(path + ".objstm")
        except OSError:
            pass


def _trim_units(us, cap):
    """Trim each descriptive ('body'/'meta') block to `cap` characters at a word boundary. Headlines, owners, dates,
    statuses and sources live in the item headline / meta line or are short, and are never trimmed; no unit is dropped."""
    out = []
    for u in us:
        bl = []
        for b in u["blocks"]:
            st, t = b[0], b[1]
            if st == "body" and len(t) > cap:
                t = t[:cap].rsplit(" ", 1)[0].rstrip(" ,;:|") + " ..."
            bl.append((st, t) + tuple(b[2:]))
        out.append(dict(u, blocks=bl))
    return out


_TRIM_KEYS = {"what", "why", "body", "note", "impact", "reason", "description", "context", "what_matters", "facts", "response", "questions", "objective", "desired_outcome"}


def _cut(text, cap):
    """Shorten one descriptive text professionally: keep whole sentences while they fit; if even the first sentence is too
    long, end at the last clause break (; : , -) or word before the cap and close with '...'. Numbers, names and dates that
    sit inside the kept text are never altered."""
    text = " ".join(str(text).split())
    if len(text) <= cap:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = ""
    for sen in sentences:
        cand = (kept + " " + sen).strip()
        if len(cand) > cap:
            break
        kept = cand
    if kept:
        return kept
    head = text[:cap]
    clause = max(head.rfind("; "), head.rfind(": "), head.rfind(", "), head.rfind(" - "))
    cut = head[:clause] if clause >= cap * 0.5 else head.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-|") + "..."


def _trim_payload(obj, cap, key=None):
    """Trim long descriptive fields of a payload (never names, titles, levels, priorities, sources or URLs). Every entry and
    every section is kept; every source stays a clickable link."""
    if isinstance(obj, dict):
        return {k: _trim_payload(v, cap, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_trim_payload(v, cap, key) for v in obj]
    if isinstance(obj, str) and (key in _TRIM_KEYS or key == "executive_summary") and len(obj) > cap:
        return _cut(obj, cap)
    return obj


def _render_single(tier, kind, data, path):
    """Render one single-PDF tier. EVERY tier is the full design (colour blocks, cards, chips); the smaller tiers only
    compress the streams (flate) and trim long descriptive text (digest*) before drawing. Nothing is drawn plain."""
    if tier == "full":
        design.LITE = False
        core.RENDERERS[kind](data, path)
    elif tier == "plain":
        # LAST RESORT, only for a brief so long that even the compressed full design is over the typed-paste limit (about 40+
        # pages). Plain layout, every item kept, compressed. The manifest says design_lost so the run states it plainly.
        raw = path + ".raw.pdf"
        render_compact.draw(kind, _trim_payload(data, 600) if kind in SINGLE_TIER else data, raw,
                            us=None if kind in SINGLE_TIER else render_compact.units(kind, data))
        _flate(raw, path)
        os.remove(raw)
        ok, problems = core.verify(path)
        if not ok:
            raise RuntimeError("render check failed: " + "; ".join(problems[:3]))
        return
    else:
        raw = path + ".raw.pdf"
        cap = DIGEST_CAP.get(tier)
        if cap and kind in SINGLE_TIER:      # Competitive Insights has a depth floor (25 words): never trim below it
            cap = {"digest": 600, "digest2": 400, "digest3": 260}[tier]
        src = _trim_payload(data, cap) if cap else data
        design.LITE = False
        core.RENDERERS[kind](src, raw)
        _flate(raw, path)
        os.remove(raw)
    ok, problems = core.verify(path)
    if not ok:
        raise RuntimeError("render check failed: " + "; ".join(problems[:3]))
    problems = design_problems(path)
    if problems:
        raise RuntimeError("design check failed: " + "; ".join(problems))


def design_problems(pdf):
    """The shrink ladder must never drop the formatting. A PDF is accepted only if its pages actually carry filled colour
    blocks (tinted cards, tiles, accent bars) in more than one colour, and does not carry the retired plain-layout footer."""
    from pypdf import PdfReader
    r = PdfReader(pdf)
    fills, colours, text = 0, set(), []
    for pg in r.pages:
        c = pg.get_contents()
        data = c.get_data().decode("latin-1") if c is not None else ""
        toks = data.split()
        fills += sum(1 for t in toks if t in ("f", "f*", "B", "B*", "b", "b*"))
        for i, t in enumerate(toks):
            if t == "rg" and i >= 3:
                colours.add(tuple(toks[i - 3:i]))
        text.append(pg.extract_text() or "")
    out = []
    if "compact format" in " ".join(text).lower():
        out.append("page footer says 'compact format' (the retired plain layout)")
    if fills < 1 or len(colours) < 5:
        out.append("no colour blocks found (%d fills, %d colours): the design was lost" % (fills, len(colours)))
    return out


def _gate(pdf, txt):
    """verify_pdf.py's gate, exactly as a run would call it. Returns its JSON dict or raises."""
    r = subprocess.run([sys.executable, os.path.join(HERE, "verify_pdf.py"), pdf, "--text", txt, "--b64", os.path.splitext(txt)[0] + ".b64"],
                       capture_output=True, text=True)
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        j = {"ok": False, "reason": (r.stdout + r.stderr).strip()[:300]}
    if r.returncode != 0 or not j.get("ok"):
        raise RuntimeError("verify_pdf gate failed: %s" % j.get("reason"))
    return j


def _part_entry(pdf, txt, index, of, gate, direct=False):
    mode = gate.get("paste_mode")
    b64 = os.path.splitext(txt)[0] + ".b64"
    if mode == "content" and os.path.isfile(txt):
        pass
    elif mode == "base64" and os.path.isfile(b64):
        txt = None
    elif direct:
        txt = None                      # smallest-file mode: base64 only, nothing is typed as plain text
    else:
        raise RuntimeError("verify_pdf reports paste_mode=%r for %s" % (mode, os.path.basename(pdf)))
    return {"index": index, "of": of, "filename": os.path.basename(pdf), "pdf": pdf, "txt": txt,
            "b64": b64 if os.path.isfile(b64) else None,
            "bytes": gate["bytes"], "expectedBytes": gate["bytes"], "pages": gate["pages"], "sha256": gate["sha256"],
            "paste_mode": mode, "readback_phrases": gate["readback_phrases"]}


def _fulldesign(cand, out_dir, name, tmp):
    """The full-design PDF when it was too big to paste: kept as <name>_fulldesign.pdf so the run can save it to its outputs.
    None when not applicable."""
    if not cand or not os.path.isfile(cand):
        return None
    pdf = os.path.join(out_dir, name + "_fulldesign.pdf")
    shutil.move(cand, pdf)
    g = _gate(pdf, os.path.join(tmp, "fulldesign.txt"))
    return {"pdf": pdf, "filename": os.path.basename(pdf), "upload_as": name + ".pdf", "bytes": g["bytes"], "pages": g["pages"],
            "sha256": g["sha256"], "readback_phrases": g["readback_phrases"]}


def _pack(kind, data, tmp, ceiling):
    """Greedy, deterministic: the longest run of consecutive units that still renders <= ceiling-RESERVE, repeated."""
    us = render_compact.split_oversize(render_compact.units(kind, data), limit=max(400, min(20000, ceiling // 3)))
    header, rest = us[0], us[1:]
    probe = os.path.join(tmp, "probe.pdf")

    def size(chunk, first):
        us_ = [header] + chunk
        render_compact.draw(kind, data, probe, part=1 if first else 2, of=99, us=us_)
        return os.path.getsize(probe)

    groups, i = [], 0
    while i < len(rest):
        first = not groups
        lo, hi = i + 1, len(rest)       # at least one unit per part; find the largest j that fits
        if size(rest[i:lo], first) > ceiling - RESERVE:
            raise RuntimeError("a single content unit does not fit in one part (%d bytes)" % os.path.getsize(probe))
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if size(rest[i:mid], first) <= ceiling - RESERVE:
                lo = mid
            else:
                hi = mid - 1
        groups.append(rest[i:lo]); i = lo
    return header, groups


SMALL_BUDGET = 256 * 1024     # smallest-file mode: the compressed PDF must be under this (typically 6-25 KB; ~2 KB per page of text)



# ---------------------------------------------------------------------------------------------------------------------
# Strict size budget (v1.13.0): every PDF is at most BUDGET_BYTES (20,000) -- always, and a PDF always exists.
# If the normal tier chain cannot get under it, a deterministic self-loop keeps shrinking until it does:
#   phase A  drop the optional sections one at a time (lowest priority first)
#   phase B  keep the first 75 % of every remaining list (lists are already in priority order), again and again
#   phase C  last resort: trim long descriptive text to 140 characters
# Each variant is tried as the full design (compressed), then as the plain compressed layout, before the loop moves on, so
# content is only cut when design alone cannot make it fit. What was left out is recorded in the manifest only
# ("squeeze") and the complete text stays in the markdown backup.
# ---------------------------------------------------------------------------------------------------------------------
BUDGET_BYTES = int(os.environ.get("SUITE_PDF_BUDGET", "20000"))
# v1.15.0: the Competitive Insights report is the deliverable itself and runs to six pages, so its cap is the largest file that can
# still be typed into the upload as one base64 string (verify_pdf.PASTE_CEILING_B64_CHARS = 30,000 characters = 22,500 bytes). The
# formatted six-page report with every section lands at about 22 KB before any wording is shortened. SUITE_PDF_BUDGET, when set,
# still overrides every kind.
KIND_BUDGETS = {"competitive_insights": 22500}


def budget_for(kind):
    if "SUITE_PDF_BUDGET" in os.environ:
        return BUDGET_BYTES
    return KIND_BUDGETS.get(kind, BUDGET_BYTES)
MAX_SQUEEZE_ITERATIONS = 60
SHRINK_ORDER = {      # lists, least important first (they shrink first); sources always last
    "daily_brief": ("resolved", "worth_double_checking", "needs_attention", "due_today", "meetings", "conflicts", "sources"),
    "call_prep": ("risks", "questions", "attendees", "what_you_need_to_know", "actions", "sources"),
    "competitive_insights": ("opportunities", "market_trends", "working_well", "new_entrants", "updates", "actions", "threats", "company_summaries", "executive_summary", "sources"),
}
NOTE_FIELD = {"daily_brief": "headline", "call_prep": "context", "competitive_insights": "week"}


_LABEL_KEYS = ("competitor", "name", "label", "title", "action", "headline", "subject", "what", "body", "text")
_LIST_TITLES = {"needs_attention": "Needs attention", "due_today": "Due today", "meetings": "Meetings", "conflicts": "Conflicts",
                "sources": "Sources", "questions": "Questions", "attendees": "Attendees", "what_you_need_to_know": "What you need to know",
                "actions": "Actions", "updates": "Key competitor updates", "threats": "Competitive threats",
                "company_summaries": "Company summaries", "executive_summary": "Executive summary", "new_entrants": "New entrants",
                "working_well": "What is working well", "market_trends": "Market trends", "opportunities": "Opportunities"}
FLOORS = {"questions": 4}                       # call prep needs 4-6 questions; every other list may go down to one item
PROTECT = {"company_summaries"}                 # one entry per company is the point of the executive summary: never reduced


def _label(it):
    if isinstance(it, dict):
        for k in _LABEL_KEYS:
            if it.get(k):
                return _cut(str(it[k]), 34).rstrip(".")
        return "item"
    return _cut(str(it), 34).rstrip(".")


def _condense_note(kind, data, omitted):
    """No note is written into the PDF: the squeezed report looks exactly like a normal one. (What was shortened or left out
    is kept only in the manifest's `squeeze` object.)"""
    return copy.deepcopy(data)


TEXT_CAPS = (520, 400, 300, 220, 160, 120, 90)


def _shrink_list(k, lst, kind):
    """Keep the first 75 % of a list in priority order, never below its floor; competitive updates always keep one entry per
    competitor so every tracked competitor stays covered. Returns (kept, left_out)."""
    floor = FLOORS.get(k, 1)
    keep_n = max(floor, int(len(lst) * 0.75))
    if keep_n >= len(lst):
        return lst, []
    kept_idx = set(range(keep_n))
    if kind == "competitive_insights" and k == "updates":
        seen = {str(lst[i].get("competitor")).lower() for i in kept_idx if isinstance(lst[i], dict)}
        for i, u in enumerate(lst):
            if i not in kept_idx and isinstance(u, dict) and str(u.get("competitor")).lower() not in seen:
                kept_idx.add(i); seen.add(str(u.get("competitor")).lower())
    kept = [x for i, x in enumerate(lst) if i in kept_idx]
    return kept, [_label(x) for i, x in enumerate(lst) if i not in kept_idx]


def _squeeze_variants(kind, data):
    """Yield (payload, omitted, label), each no larger than the one before, ending in a skeleton that always fits.
    Never drops a section and never changes the design. Stage 1 only tightens wording (all items kept); stage 2 keeps the
    first 75 % of each list per round (lists are in priority order; floors and per-competitor coverage respected) with tight
    wording; stage 3 is the smallest allowed list with 70-character wording. `omitted` maps list -> labels of left-out items."""
    for cap in TEXT_CAPS:
        yield _trim_payload(data, cap), {}, "descriptions shortened to about %d characters" % cap
    d = _trim_payload(data, 120)
    omitted = {}
    order = [k for k in SHRINK_ORDER[kind] if k not in PROTECT]
    for it in range(1, MAX_SQUEEZE_ITERATIONS):
        changed = False
        for k in order:
            lst = d.get(k)
            if isinstance(lst, list) and len(lst) > 1:
                kept, gone = _shrink_list(k, lst, kind)
                if gone:
                    omitted.setdefault(k, []).extend(gone)
                    d[k] = kept
                    changed = True
        for k in ("updates", "threats", "needs_attention", "due_today"):         # nested bullet lists inside items: first 75 %, min 1
            for item in d.get(k) or []:
                if isinstance(item, dict) and isinstance(item.get("facts"), list) and len(item["facts"]) > 1:
                    item["facts"] = item["facts"][:max(1, int(len(item["facts"]) * 0.75))]; changed = True
        if not changed:
            break
        yield copy.deepcopy(d), {k: list(v) for k, v in omitted.items()}, "kept the first 75%% of each list (round %d), every section kept" % it
    yield _trim_payload(d, 70), {k: list(v) for k, v in omitted.items()}, "smallest allowed lists, descriptions about 70 characters"
    for it in d.get("updates") or []:                       # last design variant: no bullet facts, 45-character wording
        if isinstance(it, dict):
            it.pop("facts", None)
    yield _trim_payload(d, 45), {k: list(v) for k, v in omitted.items()}, "smallest allowed lists, descriptions about 45 characters"


def _squeeze(kind, data, out_dir, name, tmp, budget, attempts, small, md, full_cand, ceiling):
    """Self-loop to the byte budget. The design (colours, cards, chips, fonts) is NEVER changed: only wording and list length
    shrink. The plain layout is used only if the smallest allowed design still cannot fit, and the manifest says so."""
    import render_competitive, render_call_prep
    n_iter = 0
    variants = list(_squeeze_variants(kind, data))
    pratio = None                       # design pages per character of payload text, learned the same way
    ratio = None                        # design bytes per character of payload text, learned from the last design render
    plan = [("design", v) for v in variants] + ([] if kind in SINGLE_TIER else [("plain", variants[-1])])   # the competitive report is never drawn plain
    render_competitive.RELAXED = render_call_prep.RELAXED = render_competitive.TIGHT = render_competitive.COMPACT = True
    try:
        for mode, (payload, omitted, label) in plan:
            n_iter += 1
            src = _condense_note(kind, payload, omitted)
            cand = os.path.join(tmp, "squeeze.pdf")
            chars = len(json.dumps(src, ensure_ascii=False))
            pcap = PAGE_CAPS.get(kind)
            if mode == "design" and pratio and pcap and chars * pratio > 1.7 * pcap:
                _log("squeeze %d (%s, design) skipped: estimated %.1f pages" % (n_iter, label, chars * pratio))
                continue
            if mode == "design" and ratio and chars * ratio > 2.2 * budget:
                _log("squeeze %d (%s, design) skipped: estimated %d bytes" % (n_iter, label, chars * ratio))
                continue                # clearly still far over: do not spend a render on it, shrink further first
            try:
                raw = cand + ".raw.pdf"
                if mode == "design":
                    design.LITE = False
                    core.RENDERERS[kind](src, raw)
                else:
                    render_compact.draw(kind, src, raw, us=None if kind in SINGLE_TIER else render_compact.units(kind, src))
                _flate(raw, cand); os.remove(raw)
                ok, problems = core.verify(cand)
                if not ok:
                    raise RuntimeError("render check failed: " + "; ".join(problems[:2]))
                if os.path.getsize(cand) > budget:             # squeeze the file itself before cutting any more content
                    _compress(cand, budget, max_level=4, check=core.verify)
                pages = pdf_pages(cand)
                if pages and mode == "design":
                    pratio = pages / max(1, chars)
                if PAGE_CAPS.get(kind) and pages and pages > PAGE_CAPS[kind]:
                    raise RuntimeError("%d pages, cap %d" % (pages, PAGE_CAPS[kind]))
            except Exception as e:
                attempts.append({"tier": "squeeze-" + mode, "bytes": None, "fits": False, "note": "%s (%s): %s" % (label, type(e).__name__, str(e)[:120])})
                _log("squeeze %d (%s, %s) failed: %s" % (n_iter, label, mode, str(e)[:100]))
                continue
            n = os.path.getsize(cand)
            if mode == "design":
                ratio = n / max(1, chars)
            fits = n <= budget
            attempts.append({"tier": "squeeze-" + mode, "bytes": n, "fits": fits, "note": label})
            _log("squeeze %d (%s, %s): %d bytes (budget %d) -> %s" % (n_iter, label, mode, n, budget, "fits" if fits else "still over"))
            if fits:
                pdf = os.path.join(out_dir, name + ".pdf"); txt = os.path.join(out_dir, name + ".txt")
                shutil.move(cand, pdf)
                part = _part_entry(pdf, txt, 1, 1, _gate(pdf, txt), direct=True)
                left = {_LIST_TITLES.get(k, k): v for k, v in omitted.items()}
                return {"tier": "squeeze", "design_lost": mode == "plain", "ceiling": ceiling, "budget": budget, "md": md, "parts": [part],
                        "attempts": attempts, "fulldesign": _fulldesign(full_cand, out_dir, name, tmp),
                        "squeeze": {"iterations": n_iter, "mode": mode, "last_step": label, "omitted": left,
                                    "note": "Condensed to fit %d bytes: wording shortened%s; every section kept, design unchanged; the complete text is in the .md backup." % (
                                        budget, ("; left out: " + "; ".join("%s: %s" % (k, ", ".join(v)) for k, v in left.items())) if left else "")}}
    finally:
        render_competitive.RELAXED = render_call_prep.RELAXED = render_competitive.TIGHT = render_competitive.COMPACT = False
    raise RuntimeError("could not get under %d bytes even after %d squeeze iterations" % (budget, n_iter))


def prepare(kind, data, out_dir, name, start_tier="full", ceiling=None, allow_parts=False, small=None, budget=None):
    """small=True (opt-in via --small): start at the compressed tier (3-4x smaller than the readable ASCII PDF) and accept
    anything under SMALL_BUDGET. Same design, same text, same links."""
    small = bool(small)
    budget = budget_for(kind) if budget is None else budget      # 0 turns the strict cap off (old behaviour)
    if small and start_tier == "full":
        start_tier = "flate"
    ceiling = ceiling or verify_pdf.PASTE_CEILING_TEXT_CHARS
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, name + ".pdf")) + glob.glob(os.path.join(out_dir, name + ".txt")) + \
            glob.glob(os.path.join(out_dir, name + "_part*of*.pdf")) + glob.glob(os.path.join(out_dir, name + "_part*of*.txt")) + \
            glob.glob(os.path.join(out_dir, name + "_fulldesign.pdf")):
        os.remove(old)                  # never leave a stale part from an earlier run beside this run's files
    data = strip_noise(kind, data)
    md = os.path.join(out_dir, name + ".md")
    try:
        core.write_markdown(kind, data, md)
    except Exception as e:
        _log("WARN: markdown backup failed: %s" % e); md = None

    attempts, last_err, full_cand = [], None, None
    tmp = tempfile.mkdtemp(prefix=".fit-", dir=out_dir)
    try:
        for tier in ([] if start_tier == "squeeze" else TIERS[TIERS.index(start_tier):]):
            if tier == "multipart":
                break
            if tier == "plain" and (kind in SINGLE_TIER or (budget and not allow_parts)):
                continue                # with a byte budget the design is never given up: the squeeze loop below shrinks wording and lists instead                # Competitive Insights never goes plain: over the limit it is uploaded as the full design
            cand = os.path.join(tmp, tier + ".pdf")
            try:
                _render_single(tier, kind, data, cand)
            except Exception as e:                      # a tier that cannot render does not end the chain
                last_err = e
                attempts.append({"tier": tier, "bytes": None, "fits": False, "note": "%s: %s" % (type(e).__name__, str(e)[:200])})
                _log("tier %s failed: %s" % (tier, e))
                continue
            n = os.path.getsize(cand)
            if tier == "full" and n > ceiling:
                full_cand = cand            # kept: saved to the run's outputs
            if small and tier != "full":
                fits = n <= SMALL_BUDGET
            elif tier != "full":
                fits = 4 * ((n + 2) // 3) <= verify_pdf.PASTE_CEILING_B64_CHARS    # sent as one base64 string
            else:
                fits = n <= ceiling and _ascii_ok(cand)
            if budget and n > budget:
                fits = False
            cap_pages = PAGE_CAPS.get(kind) if (budget and not allow_parts) else None
            pg = pdf_pages(cand) if cap_pages else None
            if cap_pages and pg and pg > cap_pages:
                fits = False
                _log("tier %s: %d pages, cap %d" % (tier, pg, cap_pages))
            attempts.append({"tier": tier, "bytes": n, "fits": fits, "note": ""})
            _log("tier %s: %d bytes (ceiling %d) -> %s" % (tier, n, ceiling, "fits" if fits else "over, trying the next tier"))
            if fits:
                pdf = os.path.join(out_dir, name + ".pdf"); txt = os.path.join(out_dir, name + ".txt")
                shutil.move(cand, pdf)
                part = _part_entry(pdf, txt, 1, 1, _gate(pdf, txt), direct=small and tier != "full")
                return {"tier": tier, "design_lost": tier == "plain", "ceiling": ceiling, "budget": budget, "md": md, "parts": [part], "attempts": attempts,
                        "fulldesign": _fulldesign(full_cand, out_dir, name, tmp)}
        if budget and not allow_parts:
            return _squeeze(kind, data, out_dir, name, tmp, budget, attempts, small, md, full_cand, ceiling)
        if kind in SINGLE_TIER:
            if not full_cand:
                raise RuntimeError("the full design could not be rendered: %s" % (last_err or "no candidate"))
            return {"tier": "full", "ceiling": ceiling, "md": md, "parts": [], "attempts": attempts, "oversize": True,
                    "fulldesign": _fulldesign(full_cand, out_dir, name, tmp)}
        if not allow_parts:
            raise RuntimeError("no single-file tier fits (%s); re-run with --allow-parts only if several PDFs are acceptable"
                               % "; ".join("%s=%s" % (x["tier"], x["bytes"]) for x in attempts))
        # multipart (opt-in only): always possible, because it splits at item boundaries
        header, groups = _pack(kind, data, tmp, ceiling)
        total = len(groups)
        if total == 1:                                    # packing found it fits once more precisely measured
            groups_to_render = [(1, 1, groups[0])]
        else:
            groups_to_render = [(k, total, g) for k, g in enumerate(groups, 1)]
        parts = []
        for k, of, g in groups_to_render:
            stem = name if of == 1 else "%s_part%dof%d" % (name, k, of)
            pdf = os.path.join(out_dir, stem + ".pdf"); txt = os.path.join(out_dir, stem + ".txt")
            render_compact.draw(kind, data, pdf, part=k, of=of, us=[header] + g)
            ok, problems = core.verify(pdf)
            if not ok:
                raise RuntimeError("part %d render check failed: %s" % (k, "; ".join(problems[:3])))
            if os.path.getsize(pdf) > ceiling:
                raise RuntimeError("part %d is %d bytes, over the %d ceiling" % (k, os.path.getsize(pdf), ceiling))
            parts.append(_part_entry(pdf, txt, k, of, _gate(pdf, txt)))
        attempts.append({"tier": "multipart", "bytes": sum(p["bytes"] for p in parts), "fits": True, "note": "%d parts" % len(parts)})
        return {"tier": "multipart" if len(parts) > 1 else "compact", "ceiling": ceiling, "md": md, "parts": parts,
                "attempts": attempts, "fulldesign": _fulldesign(full_cand, out_dir, name, tmp)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_with_eval(kind, data, out_dir, name, start_tier="full", ceiling=None, allow_parts=False, small=None, budget=None):
    """prepare() inside a self-evaluation loop: the finished PDF is scored by brain.evaluate(); a hard failure (over the byte
    budget, over the page cap, unreadable) re-runs the squeeze with a 15 % tighter byte target, up to 3 attempts. The result
    and the lesson are recorded in the brain (brain.py) so the next run writes tighter content and skips hopeless tiers.
    SUITE_BRAIN=0 turns the memory off (the evaluation still runs)."""
    import brain
    memory = os.environ.get("SUITE_BRAIN", "1") != "0"
    base = budget_for(kind) if budget is None else budget
    if memory and start_tier == "full" and not allow_parts and base and brain.start_in_squeeze(kind):
        start_tier = "squeeze"
    res, ev, tries = None, None, 0
    for attempt in range(3):
        tries = attempt + 1
        b = int(base * (0.85 ** attempt)) if base else base
        res = prepare(kind, data, out_dir, name, start_tier if attempt == 0 else "squeeze", ceiling, allow_parts, small, b)
        if allow_parts or len(res.get("parts", [])) != 1:
            return res
        ev = brain.evaluate(kind, res["parts"][0]["pdf"], budget=base, page_cap=PAGE_CAPS.get(kind) if base else 0)
        if not ev["hard_fail"]:
            break
        _log("self-evaluation failed (%s): tightening and re-running" % "; ".join(ev["issues"]))
    res["eval"] = {"passed": ev["passed"], "score": ev["score"], "issues": ev["issues"], "attempts": tries}
    if memory:
        brain.record(kind, res, ev)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render upload-ready PDF(s) for a brief, whatever the size.")
    ap.add_argument("--kind", required=True, choices=("daily_brief", "call_prep", "competitive_insights"))
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--name", default=None, help="filename stem, no extension (default: the input file's name)")
    ap.add_argument("--start-tier", default="full", choices=TIERS + tuple(TIER_ALIASES))
    ap.add_argument("--ceiling", type=int, default=None)
    ap.add_argument("--small", dest="small", action="store_true", default=None, help="smallest-file mode (opt-in; default off)")
    ap.add_argument("--no-small", dest="small", action="store_false")
    ap.add_argument("--budget", type=int, default=None, help="hard size cap in bytes (default 20000; 22500 for the competitive report; 0 = off)")
    ap.add_argument("--allow-parts", action="store_true", help="permit the multi-PDF fallback (off by default: one PDF, one link)")
    ap.add_argument("--rung", type=int, choices=(0, 1, 2, 3, 4, 5), default=None,
                    help="shrink rung after a stopped/refused typed upload, same single PDF: 1=flate, 2=digest600, 3=digest300, 4=digest140, 5=plain (design lost; only for a 40+ page brief)")
    ap.add_argument("--manifest-out", default=None)
    a = ap.parse_args(argv)
    try:
        data = json.load(sys.stdin) if a.infile == "-" else json.load(open(a.infile, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print("INPUT ERROR: %s" % e, file=sys.stderr)
        return 2
    if a.rung:
        _, a.ceiling, a.start_tier = RUNGS[a.rung]
    a.start_tier = TIER_ALIASES.get(a.start_tier, a.start_tier)
    name = a.name or os.path.splitext(os.path.basename(a.infile))[0]
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    try:
        core.check_format(a.kind, data)
    except core.FormatError as e:
        print("FORMAT ERROR: %s" % e, file=sys.stderr)
        return 6
    try:
        res = run_with_eval(a.kind, data, a.out_dir, name, a.start_tier, a.ceiling, a.allow_parts, a.small, a.budget)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("RENDER FAILED: %s" % e, file=sys.stderr)
        return 3
    line = json.dumps(res)
    if a.manifest_out:
        open(a.manifest_out, "w").write(line)
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

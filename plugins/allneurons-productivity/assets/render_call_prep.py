#!/usr/bin/env python3
"""Call Prep briefing PDF — same design system as render_brief.py (see 'Call prep PDF.md').

Usage:  python3 render_call_prep.py --in prep.json --out prep.pdf
Exit:   0 ok · 2 JSON missing/unparseable · 3 crash or reportlab missing
        5 over the 2-page ceiling (file deleted) · 6 format contract broken
        (matches run-policy §8). A markdown backup is written next to every PDF.
"""
import argparse, json, os, sys
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Spacer, Flowable,
                                KeepTogether, CondPageBreak)

from render_brief import (fail_format, status_ok, NOBODY, write_md_backup, P, esc, FONTS, S, INK, BODY, MUTED, META, HAIR, SURFACE, RED, BLUE,
                          GREEN, AMBER, GREY, TINT, CONTENT_W, MARGIN, PAGE_W, PAGE_H,
                          Masthead, SectionLabel, ActionCard, make_canvas)

REQUIRED = ["company", "context", "time", "attendees", "what_you_need_to_know", "objective",
            "desired_outcome", "questions", "sources", "duration", "format", "owner", "stage",
            "last_contact", "absent_decision_maker", "risks", "actions"]


class Glance(Flowable):
    """Label/value strip in rounded cells — every basic fact once. At most 3 cells per row, so six facts become two
    rows of three instead of six cramped columns (a long owner name or time used to wrap one word per line and push
    text against the cell edge). Cells grow to fit their text."""
    PER_ROW = 3

    def __init__(self, pairs):
        super().__init__(); self.pairs = [(k, v) for k, v in pairs if v]

    def wrap(self, aw, ah):
        self.aw, gap = aw, S[2]
        n = len(self.pairs)
        cols = min(self.PER_ROW, max(1, n))
        self.cols, self.cw = cols, (aw - gap * (cols - 1)) / cols
        self.ps = []
        for k, v in self.pairs:
            p = P(esc(v), "SB", 11, 14, INK); _, h = p.wrap(self.cw - 2 * S[3], ah); self.ps.append((p, h))
        rows = [self.ps[i:i + cols] for i in range(0, n, cols)]
        self.row_h = [12 + 10 + 6 + max(h for _, h in r) + 12 for r in rows]
        self.height = sum(self.row_h) + gap * (len(rows) - 1)
        return aw, self.height

    def draw(self):
        c, gap, cols = self.canv, S[2], self.cols
        y_top = self.height
        for ri, rh in enumerate(self.row_h):
            y0 = y_top - rh
            for ci in range(cols):
                idx = ri * cols + ci
                if idx >= len(self.pairs):
                    break
                (k, _), (p, ph) = self.pairs[idx], self.ps[idx]
                x = ci * (self.cw + gap)
                c.setFillColor(SURFACE); c.roundRect(x, y0, self.cw, rh, 6, fill=1, stroke=0)
                c.setFillColor(MUTED); c.setFont(FONTS["SB"], 8)
                c.drawString(x + S[3], y0 + rh - 12 - 7, k.upper(), charSpace=0.5)
                p.drawOn(c, x + S[3], y0 + rh - 12 - 10 - 6 - ph)
            y_top = y0 - gap


class Callout(Flowable):
    """Accent box for the desired outcome."""
    def __init__(self, label, text, accent=BLUE):
        super().__init__(); self.label, self.accent = label, accent
        self.p = P(esc(text), "SB", 13, 18, INK)
    def wrap(self, aw, ah):
        self.aw = aw; _, h = self.p.wrap(aw - 34, ah); self.ph = h
        self.height = h + 44; return aw, self.height
    def draw(self):
        c, h = self.canv, self.height
        c.setFillColor(TINT[self.accent]); c.roundRect(0, 0, self.aw, h, 6, fill=1, stroke=0)
        c.setFillColor(self.accent); c.rect(0, 0, 3, h, fill=1, stroke=0)
        c.setFont(FONTS["SB"], 8); c.drawString(17, h - 20, self.label.upper(), charSpace=0.5)
        self.p.drawOn(c, 17, 14)


class PersonRow(Flowable):
    def __init__(self, a, last=False):
        super().__init__(); self.a, self.last = a, last
        if isinstance(a, str): a = {"body": a}
        self.a = a
        # plugin payload uses title (role) and body (why they matter); role/why also accepted
        role = " · ".join(x for x in [a.get("role") or a.get("title"), a.get("company")] if x)
        tag = '&nbsp;&nbsp;<font name="%s" size="7.5" color="#1976D2">FIRST TIME</font>' % FONTS["SB"] if a.get("first_time") else ""
        self.np = P(esc(a.get("name") or "Name not established") + tag, "SB", 12, 16, INK)
        self.rp = P(esc(role), "R", 10, 14, META)
        self.wp = P(esc(a.get("why") or a.get("body") or ""), "R", 11, 16, BODY)
    def wrap(self, aw, ah):
        self.aw = aw; lw = 170
        _, a = self.np.wrap(lw - 12, ah); _, b = self.rp.wrap(lw - 12, ah); _, w = self.wp.wrap(aw - lw, ah)
        self.a, self.b, self.w, self.lw = a, b, w, lw
        self.height = max(a + b + 2, w) + 2 * S[2]; return aw, self.height
    def draw(self):
        c, h = self.canv, self.height
        self.np.drawOn(c, 0, h - S[2] - self.a); self.rp.drawOn(c, 0, h - S[2] - self.a - 2 - self.b)
        self.wp.drawOn(c, self.lw, h - S[2] - self.w)
        if not self.last:
            c.setStrokeColor(HAIR); c.setLineWidth(0.5); c.line(0, 0, self.aw, 0)


class Bullet(Flowable):
    def __init__(self, text, source=None, num=None, accent=INK, lead=None):
        super().__init__(); self.num, self.accent = num, accent
        src = f'&nbsp;&nbsp;<font name="{FONTS["R"]}" size="9" color="#111111">[{esc(source)}]</font>' if source else ""
        head = f'<font name="{FONTS["SB"]}" color="#000000">{esc(lead)}</font>&nbsp;&nbsp;' if lead else ""
        self.p = P(head + esc(text) + src, "R", 11.5, 17, BODY)
    def wrap(self, aw, ah):
        self.aw = aw; _, h = self.p.wrap(aw - 22, ah); self.height = h + S[2]; return aw, self.height
    def draw(self):
        c, h = self.canv, self.height
        if self.num:
            c.setFont(FONTS["SB"], 11); c.setFillColor(META); c.drawString(0, h - 13, f"{self.num:02d}")
        else:
            c.setFillColor(self.accent); c.circle(4, h - 9, 2.4, fill=1, stroke=0)
        self.p.drawOn(c, 22, S[2])


NON_EMPTY = ["company", "context", "time", "attendees", "what_you_need_to_know", "objective",
             "desired_outcome", "questions", "sources"]
# word ceilings from the original call-prep SKILL.md; "well past" = more than 25% over
LIMITS = {"context": 28, "desired_outcome": 22, "objective": 25}


def words(t):
    return len(str(t or "").split())


RELAXED = False     # set only by deliver_prepare's 20 KB squeeze (word ceilings do not apply to the condensed note)


def validate(d):
    errs = [f"missing key: {k}" for k in REQUIRED if k not in d]
    if errs:
        return errs
    errs += [f"{k} is empty" for k in NON_EMPTY if not d.get(k)]
    over = (lambda n, lim: False) if RELAXED else (lambda n, lim: n > lim * 1.25)
    for k, lim in LIMITS.items():
        if over(words(d.get(k)), lim): errs.append(f"{k}: {words(d.get(k))} words, limit {lim}")
    for i, a in enumerate(d.get("attendees") or []):
        if over(words(a.get("why")), 20): errs.append(f"attendees[{i}].why: {words(a.get('why'))} words, limit 20")
    wk = d.get("what_you_need_to_know") or []
    if len(wk) > 4: errs.append(f"what_you_need_to_know: {len(wk)} bullets, maximum 4")
    for i, x in enumerate(wk):
        if over(words(x.get("body")), 28): errs.append(f"what_you_need_to_know[{i}]: {words(x.get('body'))} words, limit 28")
    q = d.get("questions") or []
    if not 4 <= len(q) <= 6: errs.append(f"questions: {len(q)}, must be 4–6")
    for i, x in enumerate(q):
        if over(words(x), 20): errs.append(f"questions[{i}]: {words(x)} words, limit 20")
    rk = d.get("risks") or []
    if len(rk) > 3: errs.append(f"risks: {len(rk)} bullets, maximum 3")
    for i, x in enumerate(rk):
        if over(words(x.get("body")), 28): errs.append(f"risks[{i}]: {words(x.get('body'))} words, limit 28")
    for i, a in enumerate(d.get("actions") or []):
        own = str(a.get("owner") or "").strip()
        if own.lower() in NOBODY: errs.append(f"actions[{i}]: owner '{own}' names nobody — use the person's name")
        if over(words(a.get("body")), 22): errs.append(f"actions[{i}]: {words(a.get('body'))} words, limit 22")
        if a.get("status") and not status_ok(a["status"]): errs.append(f"actions[{i}]: status '{a['status']}' not in the §4 vocabulary")
    return errs


def prep_markdown(d):
    L = [f"# Call Prep — {d['company']}", "", d["context"], "",
         " · ".join(x for x in [d["time"], d["duration"], d["format"], d["owner"] and "Owner: " + d["owner"],
                                 d["last_contact"] and "Last contact: " + d["last_contact"]] if x), "",
         f"**Desired outcome:** {d['desired_outcome']}", "", "## Who you'll be speaking with"]
    for a in d["attendees"]:
        L.append(f"- **{a['name']}** ({', '.join(x for x in [a.get('role'), a.get('company')] if x)}) — {a.get('why','')}")
    if d["absent_decision_maker"]: L.append(f"- Not on the invite: {d['absent_decision_maker']}")
    L += ["", "## What you need to know"] + [f"- {x['body']}" + (f" [{x['source']}]" if x.get("source") else "") for x in d["what_you_need_to_know"]]
    L += ["", "## What you should accomplish", d["objective"], "", "## Questions to ask"] + [f"{i}. {q}" for i, q in enumerate(d["questions"], 1)]
    if d["risks"]: L += ["", "## Risks to watch"] + [f"- {x['body']}" for x in d["risks"]]
    if d["actions"]:
        L += ["", "## Actions & owners"] + [f"- **{a['body']}** — {a['owner']} · {a.get('by_when','')} · {a.get('status','')}" for a in d["actions"]]
    L += ["", "## Sources"]
    for i, s in enumerate(d["sources"], 1):
        s = s if isinstance(s, dict) else {"label": s}
        L.append(f"{i}. {s['label']}" + (f" — {s['url']}" if s.get("url") else ""))
    return L


def build(d, out):
    """Standalone use: validate, draw (enforcing the 2-page ceiling), write the backup."""
    errs = validate(d)
    if errs:
        fail_format(errs)
    return _draw(d, out, standalone=True)


def draw(d, out):
    """Layout only. Used by suite_pdf.py, whose core owns validation, backup and page checks."""
    for k in REQUIRED:
        d.setdefault(k, [] if k in ("attendees", "what_you_need_to_know", "questions", "sources", "risks", "actions") else "")
    return _draw(d, out, standalone=False)


def _draw(d, out, standalone):
    # No "Generated <time>" stamp — see the note on Masthead in render_brief.py:
    # the renderer's own clock is not reliably the user's local time, and a
    # timestamp that might be wrong is worse than none.
    story = [Masthead(d["company"], d["context"], eyebrow="CALL PREP"),
             Glance([("When", d["time"]), ("Length", d["duration"]), ("Format", d["format"]),
                     ("Owner", d["owner"]), ("Stage", d.get("stage")), ("Last contact", d["last_contact"])]),
             Spacer(1, S[3]), Callout("Desired outcome", d["desired_outcome"])]
    if d.get("classification_note"):
        story.insert(1, P(esc(d["classification_note"]), "R", 10, 14, META))

    def sec(label, flows, accent=None, count=None):
        if not flows: return
        story.append(CondPageBreak(90))
        story.append(KeepTogether([SectionLabel(label, count, accent), flows[0]]))
        story.extend(flows[1:])

    ppl = d["attendees"]
    sec("Who you'll be speaking with", [PersonRow(a, i == len(ppl) - 1) for i, a in enumerate(ppl)], None, len(ppl))
    if d["absent_decision_maker"]:
        story.append(P("<b>Not on the invite:</b> " + esc(d["absent_decision_maker"]), "R", 11, 16, MUTED))
    def norm(x): return {"body": x} if isinstance(x, str) else x
    def bul(x, **kw):
        x = norm(x); body = x.get("body") or x.get("title") or ""
        lead = x.get("title") if x.get("title") and x.get("body") else None
        return Bullet(body, x.get("source"), lead=lead, **kw)
    sec("What you need to know", [bul(x) for x in d["what_you_need_to_know"]], BLUE)
    sec("What you should accomplish", [P(esc(d["objective"]), "SB", 13, 18, INK)])
    qtext = lambda q: q if isinstance(q, str) else (q.get("question") or q.get("body") or q.get("title") or "")
    sec("Questions to ask", [Bullet(qtext(q), num=i + 1) for i, q in enumerate(d["questions"])], None, len(d["questions"]))
    sec("Risks to watch", [bul(r, accent=AMBER) for r in d["risks"]], AMBER, len(d["risks"]))
    acts = [ActionCard({"action": a.get("body") or a.get("title") or "", "owner": a.get("owner"), "by_when": a.get("by_when"),
                        "status": a.get("status"), "source": a.get("source")}, RED, index=i + 1)
            for i, a in enumerate(d["actions"])]
    sec("Actions & owners", acts, RED, len(acts))
    if d["sources"]:
        rows = []
        for i, s in enumerate(d["sources"], 1):
            s = s if isinstance(s, dict) else {"label": s}
            lab = esc(s["label"])
            if s.get("url"): lab = f'<link href="{esc(s["url"])}" color="#1976D2">{lab}</link>'
            rows.append(P(f'<font color="#111111">{i}.</font>&nbsp;&nbsp;{lab}', "R", 10, 15, MUTED))
        sec("Sources", rows, None, len(rows))

    doc = BaseDocTemplate(out, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN - 6, bottomMargin=MARGIN + 6,
                          title="Call Prep — " + d["company"], author="allNeurons Productivity", pageCompression=0)
    frame = Frame(MARGIN, MARGIN + 6, CONTENT_W, PAGE_H - 2 * MARGIN, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])
    doc.build(story, canvasmaker=make_canvas("Call Prep · " + d["company"] + " · " + d["time"]))
    from render_brief import make_ascii
    make_ascii(out)
    if doc.page > 2 and not standalone:
        return doc.page          # the core turns this into exit 5 and deletes the file
    if doc.page > 2:
        os.remove(out)
        print(f"PAGE LIMIT: {doc.page} pages, Call Prep maximum is 2. The file was deleted. Cut, in this order "
              "(never shrink type): risks → what_you_need_to_know → questions (down to 4) → attendee 'why' lines → sources.",
              file=sys.stderr)
        sys.exit(5)
    if standalone:
        write_md_backup(out, prep_markdown(d))
    return doc.page


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--in", dest="inp", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--inter", action="store_true"); a = ap.parse_args()
    try: data = json.load(open(a.inp))
    except Exception as e: print(f"INPUT ERROR: {e}", file=sys.stderr); sys.exit(2)
    try: pages = build(data, a.out)
    except SystemExit: raise
    except Exception as e: print(f"RENDER ERROR: {type(e).__name__}: {e}", file=sys.stderr); sys.exit(3)
    print(f"OK {a.out} — {pages} page(s) · local .md working copy (never attach or upload it): {os.path.splitext(a.out)[0]}.md")

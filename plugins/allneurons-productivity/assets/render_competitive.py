"""Competitive Insights PDF renderer: same design system as the Daily Brief (tokens, masthead, footer, margin gate), a
different story. Implements skills/competitive-insights/SKILL.md.

Report order (v1.15.0, fixed every week, at most 6 pages):
  Header and five stat tiles
  Executive summary (boxed: bottom line, then key takeaways, each tagged with its company)
  Product and market insights (numbered 01, 02 ...)
  Your companies, Tracked competitors (by company)
  I.   Key competitor updates (by company; a quiet competitor is one line), then New entrants and What is working well
  II.  Competitive threats (High, Medium, Low)
  III. Opportunities for us
  IV.  Recommended actions (by company, High priority first)
  Sources (numbered, each a clickable link)

Payload (JSON):
  title, week, company, run_date (YYYY-MM-DD, optional)
  group[]             {name, domain?, description}   every company in the user's group (own company + parent/sibling/subsidiary/brand)
  sets[]              {key, entity, name, competitors[{name, description}]}   `entity` is one of group[].name; every group entity has a set
  executive_summary   str | [str]    bottom line first, then the takeaways
  company_summaries[] {entity, title?, what_matters, why}    one or more per group company: a key takeaway (title = its headline). Printed as a tagged entry in the executive summary
  updates[]           {set, competitor, what, facts?[str], why, response?, quiet?, sources?[int]}   one per tracked competitor
  new_entrants[]      {entity, name, note, source?}
  working_well[]      {entity, title, body, source?}
  market_trends[]     {entity, title?, body}
  threats[]           {set, title, level: High|Medium|Low, why, impact?}
  opportunities[]     {set, title, body}
  actions[]           {entity, action, reason, priority: High|Medium|Low, owner?, by_when?}
  sources[]           {label, url}      every URL absolute https; each one becomes a real clickable PDF link annotation

Exit codes match run-policy section 8: 0 ok, 2 unreadable JSON, 3 crash, 6 format contract broken.
Stdlib + reportlab (+ pypdf for the link read-back).
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_brief as rb  # noqa: E402  design tokens, SectionLabel, make_canvas, make_ascii
from render_brief import BODY, P, S, esc, MARGIN, CONTENT_W, PAGE_H, INK, MUTED, META, HAIR, SURFACE, RED, AMBER, GREEN, BLUE, GREY  # noqa: E402
from reportlab.lib.pagesizes import letter  # noqa: E402
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Spacer, KeepTogether, CondPageBreak, Table, TableStyle, Flowable  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.colors import HexColor  # noqa: E402
from reportlab.platypus import Paragraph  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402

LEVELS = ("High", "Medium", "Low")
LEVEL_COLOR = {"High": "#D32F2F", "Medium": "#E8590C", "Low": "#388E3C"}
REQUIRED = ["title", "week", "group", "sets", "executive_summary", "company_summaries", "updates", "new_entrants", "working_well",
            "market_trends", "threats", "opportunities", "actions", "sources"]
URL = re.compile(r"^https:/{2}[^\s/]+\.[^\s/]+(/\S*)?$")


def _s(x):
    """Text the standard PDF fonts can draw: anything outside cp1252 becomes '?', never a crash or a blank box."""
    t = str(x if x is not None else "")
    return t.encode("cp1252", "replace").decode("cp1252")


def _list(x):
    return x if isinstance(x, list) else ([x] if x else [])


COMPACT = False     # set only by deliver_prepare's squeeze: tighter page-break thresholds, empty per-company subsections folded into one line
TIGHT = False       # set only by deliver_prepare's squeeze: smaller card padding and gaps (type size and colours unchanged)
RELAXED = False     # set only by deliver_prepare's 20 KB squeeze: the minimum-depth word counts do not apply to a deliberately condensed copy


def check(data):
    """The format contract. Returns a list of problems ([] = ok)."""
    errs = []
    if not isinstance(data, dict):
        return ["payload must be a JSON object"]
    for k in REQUIRED:
        if k not in data:
            errs.append("missing key: " + k)
    if errs:
        return errs
    if not str(data["week"]).strip():
        errs.append("week is empty")
    if not _list(data["executive_summary"]):
        errs.append("executive_summary is empty")
    group = [g for g in _list(data["group"]) if isinstance(g, dict) and str(g.get("name") or "").strip()]
    if not group:
        errs.append("group is empty: list the user's own company and every associated company (parent, sibling, subsidiary, brand)")
    gnames = {str(g["name"]).strip().lower() for g in group}
    for s in data["sets"]:
        ent = str(s.get("entity") or "").strip().lower()
        if gnames and ent not in gnames:
            errs.append("set %r has entity %r, which is not in group (%s)" % (s.get("key"), s.get("entity"), ", ".join(sorted(g["name"] for g in group))))
    covered = {str(s.get("entity") or "").strip().lower() for s in data["sets"]}
    for g in group:
        if str(g["name"]).strip().lower() not in covered:
            errs.append("company %r is in the group but has no competitor set: every associated company must be analysed" % g["name"])
    set_keys = {s.get("key") for s in data["sets"] if isinstance(s, dict)}
    if not set_keys:
        errs.append("sets is empty: at least one tracked competitor set is required")
    tracked = {c["name"].lower() for s in data["sets"] for c in s.get("competitors", [])}
    seen = set()
    for i, u in enumerate(data["updates"]):
        tag = "updates[%d]" % i
        if u.get("set") not in set_keys:
            errs.append("%s: set %r is not one of %s" % (tag, u.get("set"), sorted(set_keys)))
        if not u.get("competitor"):
            errs.append("%s: competitor missing" % tag)
        seen.add(str(u.get("competitor", "")).lower())
        if u.get("quiet"):
            continue
        for k in ("what", "why"):
            if not str(u.get(k) or "").strip():
                errs.append("%s: %s missing (a quiet week is marked quiet:true, not left blank)" % (tag, k))
    for name in sorted(tracked - seen):
        errs.append("tracked competitor %r has no update entry (add one, or mark it quiet)" % name)
    gcanon = {str(g["name"]).strip().lower(): g["name"] for g in group}

    def ent_ok(tag, e):
        if str(e or "").strip().lower() not in gcanon:
            errs.append("%s: entity %r is not in group (%s)" % (tag, e, ", ".join(sorted(g["name"] for g in group))))

    cs_seen = set()
    for i, c in enumerate(_list(data["company_summaries"])):
        ent_ok("company_summaries[%d]" % i, c.get("entity"))
        cs_seen.add(str(c.get("entity") or "").strip().lower())
        for k in ("what_matters", "why"):
            if not str(c.get(k) or "").strip():
                errs.append("company_summaries[%d]: %s missing" % (i, k))
    for g in group:
        if str(g["name"]).strip().lower() not in cs_seen:
            errs.append("company %r has no company_summaries entry: the executive summary must say what matters this week and why for every company" % g["name"])
    for key in ("new_entrants", "working_well", "market_trends", "actions"):
        for i, x in enumerate(data[key]):
            if not isinstance(x, dict):
                errs.append("%s[%d] must be an object with an entity" % (key, i)); continue
            ent_ok("%s[%d]" % (key, i), x.get("entity"))
    for i, t in enumerate(data["threats"]):
        if t.get("level") not in LEVELS:
            errs.append("threats[%d]: level %r is not High/Medium/Low" % (i, t.get("level")))
        if not str(t.get("why") or "").strip():
            errs.append("threats[%d]: why missing" % i)
    for i, a in enumerate(data["actions"]):
        for k in ("action", "reason"):
            if not str(a.get(k) or "").strip():
                errs.append("actions[%d]: %s missing" % (i, k))
        if a.get("priority") not in LEVELS:
            errs.append("actions[%d]: priority %r is not High/Medium/Low" % (i, a.get("priority")))
    if not RELAXED:
        errs += depth_problems(data)
    if not data["sources"]:
        errs.append("sources is empty: every claim must trace to a source")
    for i, s in enumerate(data["sources"]):
        if not isinstance(s, dict) or not str(s.get("label") or "").strip():
            errs.append("sources[%d]: label missing" % i)
        elif not URL.match(str(s.get("url") or "")):
            errs.append("sources[%d]: url %r is not an absolute https link" % (i, s.get("url")))
    return errs


def _words(x):
    return len(str(x or "").split())


# Minimum depth. A report whose paragraphs are one short clause is not useful to the reader, so it fails the format gate
# with a message that says what to add. A quiet competitor is exempt: "nothing material this week" is a finding.
MIN_WORDS = {"update.what": 25, "update.why": 15, "threat.why": 12, "action.reason": 10, "working_well.body": 15,
             "trend.body": 15, "opportunity.body": 15, "company.what": 12, "company.why": 6}


def depth_problems(data):
    errs = []

    def need(tag, key, text):
        n = _words(text)
        if n < MIN_WORDS[key]:
            errs.append("%s is %d words; write at least %d (who, what, when, and one specific number, name or detail; plain words)" % (tag, n, MIN_WORDS[key]))

    if sum(_words(t if isinstance(t, str) else (t.get("body") if isinstance(t, dict) else "")) for t in _list(data.get("executive_summary"))) < 25:
        errs.append("executive_summary is under 25 words; give the bottom line first: the single most important thing this week and what it means for us")
    for i, u in enumerate(data.get("updates", [])):
        if u.get("quiet"):
            continue
        need("updates[%d].what" % i, "update.what", u.get("what")); need("updates[%d].why" % i, "update.why", u.get("why"))
        if u.get("facts") is not None and not (isinstance(u["facts"], list) and all(isinstance(f, str) and f.strip() for f in u["facts"])):
            errs.append("updates[%d].facts must be a list of short strings" % i)
    for i, t in enumerate(data.get("threats", [])):
        need("threats[%d].why" % i, "threat.why", t.get("why"))
    for i, a in enumerate(data.get("actions", [])):
        need("actions[%d].reason" % i, "action.reason", a.get("reason"))
    for i, w in enumerate(data.get("working_well", [])):
        need("working_well[%d].body" % i, "working_well.body", w.get("body"))
    for i, x in enumerate(data.get("market_trends", [])):
        need("market_trends[%d].body" % i, "trend.body", x.get("body") if isinstance(x, dict) else x)
    for i, c in enumerate(data.get("company_summaries", [])):
        need("company_summaries[%d].what_matters" % i, "company.what", c.get("what_matters"))
        need("company_summaries[%d].why" % i, "company.why", c.get("why"))
    for i, o in enumerate(data.get("opportunities", [])):
        need("opportunities[%d].body" % i, "opportunity.body", o.get("body"))
    return errs


def markdown(data):
    """The plain-text backup, in the same order as the PDF (v1.15.0). Payload **bold** markers are dropped."""
    t = lambda x: BOLD_MARK.sub(r"\1", _s(x))
    sets = {s.get("key"): s for s in _list(data.get("sets"))}
    L = ["# %s: Week of %s" % (t(data["title"]), t(data["week"])), ""]
    summ = _list(data["executive_summary"])
    L += ["## Executive summary", "Bottom line: " + re.sub(r"^\s*bottom line\s*[:\-]\s*", "", t(summ[0]), flags=re.I)] + [t(x) for x in summ[1:]] + [""]
    L += ["### Key takeaways"]
    for c in _list(data.get("company_summaries")):
        L += ["- **%s** %s: %s %s" % (t(c.get("entity")), t(c.get("title") or "What matters this week"), t(c.get("what_matters")), t(c.get("why")))]
    L += ["", "## Product and market insights"] + ["%02d. %s%s" % (n, (t(i["title"]) + ". ") if i.get("title") else "", t(i.get("body"))) for n, i in enumerate(_list(data.get("market_trends")), 1)] + [""]
    L += ["## Your companies"] + ["- **%s**: %s" % (t(g.get("name")), t(" | ".join(x for x in [g.get("domain"), g.get("description")] if x))) for g in _list(data.get("group"))] + [""]
    L += ["## Tracked competitors"]
    for s_ in _list(data.get("sets")):
        L += ["### %s: %s" % (t(s_.get("entity")), t(s_.get("name")))] + ["- **%s**: %s" % (t(c.get("name")), t(c.get("description"))) for c in s_.get("competitors", [])]
    L += ["", "## I. Key competitor updates"]
    for s_ in _list(data.get("sets")):
        L += ["### %s: %s" % (t(s_.get("entity")), t(s_.get("name")))]
        for n, u in enumerate([u for u in data["updates"] if u.get("set") == s_.get("key")], 1):
            if u.get("quiet"):
                L.append("%d. **%s** (quiet): Nothing material found this week." % (n, t(u.get("competitor"))))
                continue
            L += ["%d. **%s** %s" % (n, t(u.get("competitor")), "".join("[%s]" % r for r in _list(u.get("sources")))),
                  "   What happened: " + t(u.get("what"))]
            if u.get("facts"):
                L += ["   Key facts:"] + ["   - " + t(f) for f in u["facts"]]
            L.append("   Why it matters to us: " + t(u.get("why")))
            if u.get("response"):
                L.append("   Our proposed response: " + t(u["response"]))
    L += ["", "### New entrants"] + ["%d. **%s** (watch, %s) %s" % (n, t(e.get("name")), t(e.get("entity")), t(e.get("note"))) for n, e in enumerate(_list(data.get("new_entrants")), 1)]
    L += ["", "### What is working well"] + ["%d. **%s** (%s) %s" % (n, t(w.get("title")), t(w.get("entity")), t(w.get("body"))) for n, w in enumerate(_list(data.get("working_well")), 1)]
    L += ["", "## II. Competitive threats"]
    order = {l: n for n, l in enumerate(LEVELS)}
    for n, x in enumerate(sorted(_list(data.get("threats")), key=lambda x: order.get(x.get("level"), 3)), 1):
        L += ["%d. [%s] **%s** (%s)" % (n, x.get("level"), t(x.get("title")), t((sets.get(x.get("set")) or {}).get("entity") or "")),
              "   Why it is a threat: " + t(x.get("why"))] + (["   Potential impact: " + t(x["impact"])] if x.get("impact") else [])
    L += ["", "## III. Opportunities for us"] + ["%d. **%s** (%s) %s" % (n, t(o.get("title")), t((sets.get(o.get("set")) or {}).get("entity") or ""), t(o.get("body"))) for n, o in enumerate(_list(data.get("opportunities")), 1)]
    L += ["", "## IV. Recommended actions"]
    for n, a in enumerate(sorted(_list(data.get("actions")), key=lambda x: order.get(x.get("priority"), 3)), 1):
        L.append("%d. [%s priority] **%s** (%s) %s%s" % (n, a.get("priority"), t(a.get("action")), t(a.get("entity")), t(a.get("reason")),
                 (" Owner: %s, by: %s." % (t(a.get("owner") or "-"), t(a.get("by_when") or "-"))) if (a.get("owner") or a.get("by_when")) else ""))
    L += ["", "## Sources"] + ["%02d. [%s](%s)" % (i, t(x["label"]), x["url"]) for i, x in enumerate(data["sources"], 1)]
    return "\n".join(L) + "\n"


def _set_name(data, key):
    return next((s.get("name") for s in data["sets"] if s.get("key") == key), key)


def _src(refs, data=None):
    """[n] markers; each one links to its source so the reader can jump straight to it."""
    refs = [r for r in _list(refs) if isinstance(r, int)]
    if not refs:
        return ""
    srcs = (data or {}).get("sources") or []
    out = []
    for r in refs:
        url = srcs[r - 1]["url"] if 0 < r <= len(srcs) and isinstance(srcs[r - 1], dict) else None
        out.append("<link href=\"%s\" color=\"#1976D2\">%d</link>" % (esc(url), r) if url else str(r))
    return "&nbsp;&nbsp;<font name=\"%s\" size=\"9\" color=\"#111111\">[%s]</font>" % (rb.FONTS["R"], ", ".join(out))


def _para(text, size=10.5, lead=15.5, font="R", color=INK):
    return P(esc(_s(text)), font, size, lead, color)


def _group_by_set(items, data):
    out = []
    for s in data["sets"]:
        grp = [i for i in items if i.get("set") == s.get("key")]
        if grp:
            out.append((s, grp))
    return out



# -- Layout (v1.15.0): the formatted report -----------------------------------------------------------------------------------
# Order: header and five stat tiles, boxed executive summary (bottom line, key takeaways with a company tag), Product and market
# insights, Your companies, Tracked competitors, I. Key competitor updates (with New entrants and What is working well),
# II. Competitive threats, III. Opportunities for us, IV. Recommended actions, Sources. Every entry is numbered, every status is a
# small tag, every source marker is a link. A quiet competitor is one line, so the whole report stays within 6 pages.
TOP_M, BOT_M = 36, 46
FRAME_H_CI = PAGE_H - TOP_M - BOT_M
ENT_COLORS = [("#E4EAF3", "#1F3A66"), ("#DCEAFB", "#0F5FC2"), ("#D9F2EC", "#0A6B5B"), ("#E3F3E3", "#2E7D32"),
              ("#F1E8FB", "#6B33B8"), ("#FDEBDD", "#B94A0B")]
TAG_COLORS = {"QUIET": ("#F3EBD9", "#4A3B12"), "WATCH": ("#E3EEFB", "#0F5FC2"), "HIGH": ("#FDE3E3", "#C62828"),
              "MEDIUM": ("#FFEBD9", "#B94A0B"), "LOW": ("#E3F3E3", "#2E7D32"),
              "HIGH PRIORITY": ("#FDE3E3", "#C62828"), "MEDIUM PRIORITY": ("#FFEBD9", "#B94A0B"), "LOW PRIORITY": ("#E3F3E3", "#2E7D32")}
COUNT_COLORS = ("#DCEAFB", "#0F5FC2")
LIGHT_HEAD = ("#E3EEFB", "#0F5FC2")
BOLD_MARK = re.compile(r"\*\*(.+?)\*\*")


def _hx(c):
    return HexColor(c)


def _t(x):
    """Plain text from a payload field: standard-font safe, with **bold** markers removed."""
    return BOLD_MARK.sub(r"\1", _s(x))


def _m(x):
    """Markup for a payload field: escaped, with **bold** turned into the bold font (competitor names and the like)."""
    return BOLD_MARK.sub(lambda m: "<font name=\"%s\">%s</font>" % (rb.FONTS["B"], m.group(1)), esc(_s(x)))


def _fs():
    """(body size, body leading, small size, small leading): slightly smaller type only in the squeeze loop."""
    return (8.2, 10.3, 7.6, 9.0) if COMPACT else (8.6, 10.9, 7.9, 9.4)


def _gap():
    return 3 if TIGHT else 4


class Chip(Flowable):
    """A small rounded tag or pill: tinted fill, coloured bold text. Used for QUIET / WATCH / HIGH, company names and counts."""
    def __init__(self, text, fg, bg, size=7, cs=0.5, padx=5, h=None, upper=True):
        super().__init__()
        self.text = text.upper() if upper else text
        self.fg, self.bg, self.size, self.cs, self.padx = fg, bg, size, cs, padx
        self.w = pdfmetrics.stringWidth(self.text, rb.FONTS["B"], size) + cs * len(self.text) + 2 * padx
        self.h = h or (size + 5)
        self.width, self.height = self.w, self.h

    def wrap(self, aw, ah):
        return self.w, self.h

    def draw(self):
        self.draw_at(self.canv, 0, 0)

    def draw_at(self, c, x, y):
        c.setFillColor(_hx(self.bg))
        r = self.h / 2.0                                   # a capsule: one rectangle plus two end circles; the circle is a shared form per height, so every chip costs a few dozen bytes
        c.rect(x + r, y, self.w - 2 * r, self.h, fill=1, stroke=0)
        c.circle(x + r, y + r, r, fill=1, stroke=0); c.circle(x + self.w - r, y + r, r, fill=1, stroke=0)
        c.setFillColor(_hx(self.fg)); c.setFont(rb.FONTS["B"], self.size)
        c.drawString(x + self.padx, y + (self.h - self.size) / 2 + 1.1, self.text, charSpace=self.cs)


def tag(text):
    bg, fg = TAG_COLORS.get(text.upper(), ("#EEEEEE", "#111111"))
    return Chip(text, fg, bg, size=6.6, cs=0.6, padx=5, h=11.5)


def count_chip(n):
    return Chip(str(n), COUNT_COLORS[1], COUNT_COLORS[0], size=8, cs=0, padx=6, h=14, upper=False)


class Label(Flowable):
    """Letter-spaced capitals (section labels)."""
    def __init__(self, text, size=10.5, color=INK, cs=1.8):
        super().__init__()
        self.text, self.size, self.color, self.cs = text.upper(), size, color, cs

    def wrap(self, aw, ah):
        self.height = self.size + 4
        return pdfmetrics.stringWidth(self.text, rb.FONTS["B"], self.size) + self.cs * len(self.text), self.height

    def draw(self):
        c = self.canv; c.setFillColor(self.color); c.setFont(rb.FONTS["B"], self.size)
        c.drawString(0, 3, self.text, charSpace=self.cs)


class Header(Flowable):
    """Eyebrow, the week in large type, one subtitle line."""
    def wrap(self, aw, ah):
        self.height = 60
        return aw, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(INK); c.setFont(rb.FONTS["B"], 7.6); c.drawString(0, 51, "COMPETITIVE INSIGHTS", charSpace=1.8)
        c.setFont(rb.FONTS["B"], 24); c.drawString(0, 25, self.week)
        c.setFont(rb.FONTS["R"], 10.5); c.drawString(0, 9, "This week's competitive intelligence report")


class StatTiles(Flowable):
    """Equal tiles; a count above zero takes its accent colour, a zero stays neutral."""
    def __init__(self, items):
        super().__init__(); self.items = items; self.height = 46

    def wrap(self, aw, ah):
        return aw, self.height

    def draw(self):
        c, gap = self.canv, 8
        cw = (CONTENT_W - (len(self.items) - 1) * gap) / len(self.items)
        for i, (label, n, accent) in enumerate(self.items):
            x, hot = i * (cw + gap), n > 0
            c.setFillColor(rb.TINT[accent] if hot else SURFACE); c.roundRect(x, 0, cw, self.height, 6, fill=1, stroke=0)
            c.setFillColor(accent if hot else META); c.setFont(rb.FONTS["B"], 20); c.drawString(x + 10, 21, str(n))
            c.setFillColor(accent if hot else MUTED); c.setFont(rb.FONTS["B"], 6.4); c.drawString(x + 10, 8, label.upper(), charSpace=0.5)


class SectionHead(Flowable):
    """Section heading: letter-spaced capitals, an optional roman numeral and count chip, and a rule underneath."""
    def __init__(self, text, count=None, rule="#111111", rule_w=1.0, roman=None):
        super().__init__()
        self.text = ((roman + ". ") if roman else "") + text.upper()
        self.count, self.rule, self.rule_w = count, rule, rule_w
        self.chip = count_chip(count) if count is not None else None

    def wrap(self, aw, ah):
        top = FRAME_H_CI - 1 <= ah <= FRAME_H_CI + 1
        self.pre = 0 if top else (8 if TIGHT else 11)
        self.height = self.pre + 15 + 7
        return aw, self.height

    def draw(self):
        c = self.canv
        y = 7
        c.setFillColor(INK); c.setFont(rb.FONTS["B"], 10.5); c.drawString(0, y + 3, self.text, charSpace=1.7)
        if self.chip:
            x = pdfmetrics.stringWidth(self.text, rb.FONTS["B"], 10.5) + 1.7 * len(self.text) + 8
            self.chip.draw_at(c, x, y)
        c.setStrokeColor(_hx(self.rule)); c.setLineWidth(self.rule_w); c.line(0, 2, CONTENT_W, 2)


class GroupHead(Flowable):
    """A company tag, what its market is, and a count; with a hairline underneath. light=True is the plain blue heading used for
    New entrants / What is working well."""
    def __init__(self, label, descriptor=None, count=None, colors=None, light=False):
        super().__init__()
        fg_bg = colors or (LIGHT_HEAD if light else ENT_COLORS[0])
        self.pill = Chip(label, fg_bg[1], fg_bg[0], size=8.6 if not light else 9, cs=0, padx=7, h=15, upper=False)
        self.desc = descriptor
        self.chip = count_chip(count) if count is not None else None

    def wrap(self, aw, ah):
        self.pre = 3 if TIGHT else 5
        self.height = self.pre + 15 + 3
        return aw, self.height

    def draw(self):
        c = self.canv
        y = 5
        self.pill.draw_at(c, 0, y)
        x = self.pill.w + 8
        if self.desc:
            c.setFillColor(INK); c.setFont(rb.FONTS["B"], 10); c.drawString(x, y + 4, self.desc)
            x += pdfmetrics.stringWidth(self.desc, rb.FONTS["B"], 10) + 8
        else:
            x = self.pill.w + 8
        if self.chip:
            self.chip.draw_at(c, x, y + 0.5)
        c.setStrokeColor(HAIR); c.setLineWidth(0.7); c.line(0, 2, CONTENT_W, 2)


class EntryHead(Flowable):
    """'1. Name [1, 2]' in bold, then tags (QUIET, WATCH, HIGH, a company tag) on the same line, then an optional plain sentence.
    Wraps when the title is long; the tags then follow the last line, or drop to a line of their own."""
    def __init__(self, markup, tags=(), trail=None, size=10, indent=0, lead_gap=0):
        super().__init__()
        self.markup, self.tags, self.trail, self.size, self.indent = markup, list(tags), trail, size, indent

    def wrap(self, aw, ah):
        self.aw = aw
        tw = sum(t.w for t in self.tags) + 6 * max(0, len(self.tags))
        self.p = P(self.markup, "B", self.size, self.size + 3.0, INK)
        _, self.ph = self.p.wrap(aw - self.indent, ah)
        lw = self.p.getActualLineWidths0()
        self.last = lw[-1] if lw else 0
        trail_w = (pdfmetrics.stringWidth(self.trail, rb.FONTS["R"], 8.8) + 8) if self.trail else 0
        self.tag_below = bool(self.tags) and (self.indent + self.last + 8 + tw + trail_w > aw)
        self.height = self.ph + (13 if self.tag_below else 0) + 1.5
        return aw, self.height

    def draw(self):
        c = self.canv
        top = self.height - 1.5
        self.p.drawOn(c, self.indent, top - self.ph)
        if self.tag_below:
            x, y = self.indent, top - self.ph - 13
        else:
            x, y = self.indent + self.last + 8, top - self.ph + 1.6
            if len(self.p.getActualLineWidths0()) > 1:
                y = top - self.ph + 1.6
        for t in self.tags:
            t.draw_at(c, x, y); x += t.w + 6
        if self.trail:
            c.setFillColor(BODY); c.setFont(rb.FONTS["R"], 8.8); c.drawString(x + 2, y + 2.4, self.trail)


def _bullets(items, size, lead):
    return [Paragraph(_m(x), ParagraphStyle("b", fontName=rb.FONTS["R"], fontSize=size, leading=lead - 0.5, textColor=BODY,
                                            leftIndent=11, bulletIndent=2), bulletText="•") for x in items]


def block(rows, indent=14, box_from=None):
    """Labelled paragraphs under an entry. rows = [(LABEL or None, text | [bullets])]. Rows from `box_from` on sit on a light
    panel. One Table, so a long entry still splits between rows."""
    bs, bl, ss, sl = _fs()
    data, style, boxed, labelled = [], [], [], []
    lab = lambda t: P(esc(_s(t)), "B", bs, bl, INK)
    for i, (label, text) in enumerate(rows):
        if label:
            labelled.append(len(data))
            data.append([lab(label)])
        if isinstance(text, (list, tuple)):
            for b in _bullets(text, bs, bl):
                data.append([b])
        elif text:
            data.append([P(_m(text), "R", bs, bl, BODY)])
        if box_from is not None and i >= box_from:
            boxed.append(len(data))
    t = Table(data, colWidths=[CONTENT_W - indent], splitByRow=1, hAlign="RIGHT")
    st = [("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 0.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.2)]
    if box_from is not None:
        # find the first row of the boxed region and shade it to the end
        first = 0
        n = 0
        for i, (label, text) in enumerate(rows):
            if i == box_from:
                first = n
            n += (1 if label else 0) + (len(text) if isinstance(text, (list, tuple)) else (1 if text else 0))
        st += [("BACKGROUND", (0, first), (-1, -1), SURFACE), ("LEFTPADDING", (0, first), (-1, -1), 8), ("RIGHTPADDING", (0, first), (-1, -1), 8),
               ("TOPPADDING", (0, first), (-1, first), 4), ("BOTTOMPADDING", (0, -1), (-1, -1), 4),
               ("TOPPADDING", (0, first + 1), (-1, -1), 0.6)]
        # a hairline between the two boxed paragraphs
        for r in range(first, len(data) - 1):
            pass
    for r in labelled:                                     # a label is never left alone at the foot of a page
        if r + 1 < len(data):
            st.append(("NOSPLIT", (0, r), (0, r + 1)))
    t.setStyle(TableStyle(st))
    return t


def _ek(e):
    return str(e or "").strip().lower()


def _grid(cells, ncols, gap=6, boxed=False):
    """cells: list of lists of flowables. Equal columns separated by a gap; each cell a light tile (or an outlined card)."""
    cw = (CONTENT_W - gap * (ncols - 1)) / ncols
    rows, widths = [], []
    for i in range(ncols):
        widths += [cw] + ([gap] if i < ncols - 1 else [])
    st = [("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    data = []
    for r in range(0, len(cells), ncols):
        chunk = cells[r:r + ncols]
        row = []
        for i in range(ncols):
            row += [chunk[i] if i < len(chunk) else ""] + ([""] if i < ncols - 1 else [])
        data.append(row)
        ri = len(data) - 1
        for i in range(len(chunk)):
            c0 = i * 2
            if boxed:
                st += [("BOX", (c0, ri), (c0, ri), 0.6, HexColor("#D5D9DF")), ("ROUNDEDCORNERS", [4, 4, 4, 4])]
            else:
                st += [("BACKGROUND", (c0, ri), (c0, ri), SURFACE)]
            st += [("LEFTPADDING", (c0, ri), (c0, ri), 7), ("RIGHTPADDING", (c0, ri), (c0, ri), 7),
                   ("TOPPADDING", (c0, ri), (c0, ri), 3), ("BOTTOMPADDING", (c0, ri), (c0, ri), 3.5)]
        data.append([""] * len(row)); st.append(("ROWBACKGROUNDS", (0, ri + 1), (-1, ri + 1), [colors.white]))
        st.append(("TOPPADDING", (0, ri + 1), (-1, ri + 1), 0)); st.append(("BOTTOMPADDING", (0, ri + 1), (-1, ri + 1), 0))
    t = Table(data, colWidths=widths, rowHeights=[None if i % 2 == 0 else (2 if TIGHT else 3) for i in range(len(data))])
    t.setStyle(TableStyle(st))
    return t


def _canon(group):
    return {str(g["name"]).strip().lower(): g for g in group}


def _label_of(g):
    return " | ".join(x for x in [g.get("domain"), g.get("description")] if x)


def _footer_canvas(left, right):
    base = rb.make_canvas(left)

    class Canvas(base):
        def _chrome(self, total):
            y = MARGIN - 26
            self.setStrokeColor(HAIR); self.setLineWidth(0.5)
            self.line(MARGIN, y + 12, MARGIN + CONTENT_W, y + 12)
            self.setFont(rb.FONTS["R"], 8.2); self.setFillColor(META)
            tail = "Page %d of %d" % (self._pageNumber, total)
            name = right or ""
            while name and pdfmetrics.stringWidth(name + " · " + tail, rb.FONTS["R"], 8.2) > CONTENT_W * 0.42:   # a long company name never pushes the footer out of the margin
                name = name[:-2].rstrip()
                if pdfmetrics.stringWidth(name + "... · " + tail, rb.FONTS["R"], 8.2) <= CONTENT_W * 0.42:
                    name += "..."; break
            r = ("%s · %s" % (name, tail)) if name else tail
            room = CONTENT_W - pdfmetrics.stringWidth(r, rb.FONTS["R"], 8.2) - 16
            lft = left
            while len(lft) > 1 and pdfmetrics.stringWidth(lft, rb.FONTS["R"], 8.2) > room:
                lft = lft[:-2].rstrip()
                if pdfmetrics.stringWidth(lft + "...", rb.FONTS["R"], 8.2) <= room:
                    lft += "..."; break
            self.drawString(MARGIN, y, lft)
            self.drawRightString(MARGIN + CONTENT_W, y, r)
    return Canvas


def draw(data, out):
    errs = check(data)
    if errs:
        raise ValueError("; ".join(errs))
    group = [g for g in _list(data["group"]) if isinstance(g, dict) and str(g.get("name") or "").strip()]
    ekey = _ek
    bs, bl, ss, sl = _fs()
    ent_col = {ekey(g["name"]): ENT_COLORS[i % len(ENT_COLORS)] for i, g in enumerate(group)}
    ent_name = {ekey(g["name"]): _t(g["name"]) for g in group}
    set_entity = {s.get("key"): ekey(s.get("entity")) for s in data["sets"]}
    set_by_key = {s.get("key"): s for s in data["sets"]}
    comps = [c for s in data["sets"] for c in s.get("competitors", [])]
    live = [u for u in data["updates"] if not u.get("quiet")]
    hi = [t for t in data["threats"] if t.get("level") == "High"]
    story = []
    gap = _gap()

    def add(flow, keep=True, after=None):
        flow.spaceAfter = gap if after is None else after
        story.append(flow if (isinstance(flow, KeepTogether) or not keep) else KeepTogether([flow]))

    def sec(text, count=None, rule="#111111", roman=None, need=90):
        story.append(CondPageBreak(need * (0.4 if COMPACT else 1)))
        story.append(SectionHead(text, count, rule, 1.0 if rule == "#111111" else 1.4, roman))

    def ghead(*a, need=75, **k):
        story.append(CondPageBreak(need * (0.4 if COMPACT else 1)))
        story.append(GroupHead(*a, **k))

    def ent_pill(e, size=8):
        bg, fg = ent_col.get(ekey(e), ENT_COLORS[0])
        return Chip(ent_name.get(ekey(e), _t(e)), fg, bg, size=size, cs=0, padx=7, h=size + 8.5, upper=False)

    def ent_tag(e):
        bg, fg = ent_col.get(ekey(e), ENT_COLORS[0])
        return Chip(ent_name.get(ekey(e), _t(e)), fg, bg, size=7.2, cs=0, padx=6, h=11.5, upper=False)

    def set_head(s, count):
        ghead(ent_name.get(ekey(s.get("entity")), _t(s.get("entity"))), _t(s.get("name")), count, ent_col.get(ekey(s.get("entity"))))

    hdr = Header(); hdr.week = _t(data["week"]); story.append(hdr)
    story.append(StatTiles([("Companies", len(group), rb.PURPLE), ("Competitors", len(comps), BLUE), ("Competitor updates", len(live), AMBER),
                            ("High threats", len(hi), RED), ("Opportunities", len(data["opportunities"]), GREEN)]))
    story.append(Spacer(1, 8))

    # ── Executive summary: boxed ──────────────────────────────────────────────────────────────────────────────────────
    summ = _list(data["executive_summary"])
    bl_text = re.sub(r"^\s*bottom line\s*[:\-]\s*", "", str(summ[0]), flags=re.I)
    rows = [[Label("Executive summary", 10.5, INK, 1.8)],
            [P("<font name=\"%s\">Bottom line:</font> %s" % (rb.FONTS["B"], _m(bl_text)), "R", bs + 0.6, bl + 1, BODY)]]
    extra = [x for x in summ[1:] if str(x).strip()]
    cs_list = _list(data["company_summaries"])
    if extra or cs_list:
        rows.append([Label("Key takeaways", 8.4, INK, 1.4)])
    for x in extra:                                          # plain takeaways written as strings keep their place
        rows.append([P(_m(x), "R", bs, bl, BODY)])
    for c in cs_list:
        pill = ent_pill(c.get("entity"), 8)
        title = _m(c.get("title") or "What matters this week")
        head = Table([[pill, P(title, "B", bs + 0.5, bl + 1, INK)]], colWidths=[pill.w + 8, CONTENT_W - 28 - pill.w - 8])
        head.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                  ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        body = P(_m((str(c.get("what_matters") or "").strip() + " " + str(c.get("why") or "").strip()).strip()), "R", bs, bl, BODY)
        rows.append([[head, Spacer(1, 3), body]])
    box = Table(rows, colWidths=[CONTENT_W])
    st = [("BOX", (0, 0), (-1, -1), 0.9, INK), ("ROUNDEDCORNERS", [5, 5, 5, 5]), ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
          ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("TOPPADDING", (0, 0), (-1, 0), 9),
          ("BOTTOMPADDING", (0, -1), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    first_take = 3 + len(extra)
    for r in range(first_take, len(rows) - 1):
        st.append(("LINEBELOW", (0, r), (-1, r), 0.5, HAIR)); st.append(("BOTTOMPADDING", (0, r), (-1, r), 4)); st.append(("TOPPADDING", (0, r + 1), (-1, r + 1), 4))
    if len(rows) > 3:
        st.append(("LINEBELOW", (0, 2), (-1, 2), 0.5, HAIR))
    box.setStyle(TableStyle(st))
    story.append(box)

    # ── Product and market insights ───────────────────────────────────────────────────────────────────────────────────
    mts = _list(data["market_trends"])
    sec("Product and market insights", len(mts), "#E3E6EA", need=90)
    if not mts:
        add(P("No market trend stood out this week.", "R", bs, bl, BODY))
    for n, i in enumerate(mts, 1):
        txt = (("<font name=\"%s\">%s.</font> " % (rb.FONTS["B"], esc(_t(i["title"])))) if i.get("title") else "") + _m(i.get("body", ""))
        row = Table([[P("%02d" % n, "B", bs + 1, bl + 1, _hx("#1F3A66")), P(txt, "R", bs, bl, BODY)]], colWidths=[24, CONTENT_W - 24])
        row.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 2),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, HAIR)]))
        add(row, after=1)

    # ── Your companies / Tracked competitors ──────────────────────────────────────────────────────────────────────────
    sec("Your companies", len(group), "#1F3A66", need=90)
    cells = [[P(esc(_t(g["name"])), "B", bs + 1, bl + 1, INK), P(esc(_t(_label_of(g))), "R", ss, sl, BODY)] for g in group]
    add(_grid(cells, 2, 8, boxed=True), keep=False)
    sec("Tracked competitors", len(comps), "#E3E6EA", need=90)
    for s in data["sets"]:
        cs = s.get("competitors", [])
        set_head(s, len(cs))
        cells = [[P(esc(_t(c["name"])), "B", bs, bl, INK), P(esc(_t(c.get("description", ""))), "R", ss, sl, BODY)] for c in cs]
        add(_grid(cells, 3, 6), keep=False)

    # ── I. Key competitor updates (with New entrants and What is working well) ────────────────────────────────────────
    sec("Key competitor updates", len(data["updates"]), "#1976D2", roman="I", need=90)
    for s in data["sets"]:
        grp = [u for u in data["updates"] if u.get("set") == s.get("key")]
        if not grp:
            continue
        set_head(s, len(grp))
        quiet_names = [u["competitor"] for u in grp if u.get("quiet")] if COMPACT else []
        for n, u in enumerate(grp, 1):
            if u.get("quiet"):
                if COMPACT:
                    continue
                add(EntryHead("%d. %s" % (n, esc(_t(u["competitor"]))), [tag("Quiet")], "Nothing material found this week.", 9.6, 0), after=1)
                continue
            head = EntryHead("%d. %s%s" % (n, esc(_t(u["competitor"])), _src(u.get("sources"), data)), [], None, 10.5, 0)
            rws = [("What happened", u["what"])] + ([("Key facts", u["facts"])] if u.get("facts") else [])
            nbox = len(rws)
            rws += [("Why it matters to us", u["why"])] + ([("Our proposed response", u["response"])] if u.get("response") else [])
            body = block(rws, 14, box_from=nbox)
            story.append(CondPageBreak(80 * (0.4 if COMPACT else 1)))
            story.append(head); story.append(Spacer(1, 2)); story.append(body); story.append(Spacer(1, gap + 1))
        if quiet_names:
            add(P("Quiet this week, nothing material found: " + ", ".join(esc(_t(x)) for x in quiet_names) + ".", "R", bs, bl, BODY))

    ne = _list(data["new_entrants"])
    ghead("New entrants", None, len(ne), light=True)
    if not ne:
        add(P("No new entrants this week.", "R", bs, bl, BODY))
    for n, e in enumerate(ne, 1):
        add(KeepTogether([EntryHead("%d. %s%s" % (n, esc(_t(e.get("name"))), _src(e.get("source"), data)), [tag("Watch"), ent_tag(e.get("entity"))], None, 10, 0),
                          Spacer(1, 1), block([(None, e.get("note", ""))], 14)]), after=gap)
    ww = _list(data["working_well"])
    ghead("What is working well", None, len(ww), light=True)
    if not ww:
        add(P("Nothing notable this week.", "R", bs, bl, BODY))
    for n, w in enumerate(ww, 1):
        add(KeepTogether([EntryHead("%d. %s%s" % (n, esc(_t(w.get("title"))), _src(w.get("source"), data)), [ent_tag(w.get("entity"))], None, 10, 0),
                          Spacer(1, 1), block([(None, w.get("body", ""))], 14)]), after=gap)

    # ── II. Competitive threats ───────────────────────────────────────────────────────────────────────────────────────
    order = {l: n for n, l in enumerate(LEVELS)}
    sec("Competitive threats", len(data["threats"]), "#111111", roman="II", need=90)
    if not data["threats"]:
        add(P("No threats rated this week.", "R", bs, bl, BODY))
    for s in data["sets"]:
        grp = sorted([t for t in data["threats"] if t.get("set") == s.get("key")], key=lambda t: order[t["level"]])
        if not grp:
            continue
        set_head(s, len(grp))
        for n, t in enumerate(grp, 1):
            rws = [("Why it is a threat", t["why"])] + ([("Potential impact", t["impact"])] if t.get("impact") else [])
            add(KeepTogether([EntryHead("%d. %s" % (n, esc(_t(t.get("title")))), [tag(t["level"])], None, 10, 0), Spacer(1, 1), block(rws, 14)]), after=gap)

    # ── III. Opportunities for us ─────────────────────────────────────────────────────────────────────────────────────
    sec("Opportunities for us", len(data["opportunities"]), "#111111", roman="III", need=90)
    if not data["opportunities"]:
        add(P("No opportunity identified this week.", "R", bs, bl, BODY))
    for s in data["sets"]:
        grp = [o for o in data["opportunities"] if o.get("set") == s.get("key")]
        if not grp:
            continue
        set_head(s, len(grp))
        for n, o in enumerate(grp, 1):
            add(KeepTogether([EntryHead("%d. %s" % (n, esc(_t(o.get("title")))), [], None, 10, 0), Spacer(1, 1), block([(None, o.get("body", ""))], 14)]), after=gap)

    # ── IV. Recommended actions ───────────────────────────────────────────────────────────────────────────────────────
    sec("Recommended actions", len(data["actions"]), "#111111", roman="IV", need=90)
    if not data["actions"]:
        add(P("No action recommended this week.", "R", bs, bl, BODY))
    for g in group:
        k = ekey(g["name"])
        acts = sorted([a for a in data["actions"] if ekey(a.get("entity")) == k], key=lambda a: order[a["priority"]])
        if not acts:
            continue
        desc = "; ".join(_t(s.get("name")) for s in data["sets"] if ekey(s.get("entity")) == k)
        ghead(ent_name[k], desc or None, len(acts), colors=ent_col[k])
        for n, a in enumerate(acts, 1):
            meta = []
            if a.get("owner"):
                meta.append("<font name=\"%s\">Owner:</font> %s" % (rb.FONTS["B"], esc(_t(a["owner"]))))
            if a.get("by_when"):
                meta.append("<font name=\"%s\">by:</font> %s" % (rb.FONTS["B"], esc(_t(a["by_when"]))))
            text = _m(a["reason"]) + ((" " + ", ".join(meta) + ".") if meta else "")
            tb = Table([[P(text, "R", bs, bl, BODY)]], colWidths=[CONTENT_W - 14], hAlign="RIGHT")
            tb.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 0.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5)]))
            add(KeepTogether([EntryHead("%d. %s" % (n, esc(_t(a["action"]))), [tag(a["priority"] + " priority")], None, 10, 0), Spacer(1, 1), tb]), after=gap)

    # ── Sources ───────────────────────────────────────────────────────────────────────────────────────────────────────
    sec("Sources", len(data["sources"]), "#111111", need=90)
    for i, s in enumerate(data["sources"], 1):
        host = re.sub(r"^https:/{2}(www\.)?", "", s["url"]).split("/")[0]
        row = Table([[P("%02d" % i, "B", bs, bl, INK),
                      P("<link href=\"%s\" color=\"#1976D2\">%s</link>" % (esc(s["url"]), esc(_t(s["label"]))), "R", bs, bl, INK),
                      Paragraph(esc(host), ParagraphStyle("h", fontName=rb.FONTS["R"], fontSize=ss, leading=sl, textColor=INK, alignment=2))], ],
                    colWidths=[22, CONTENT_W - 22 - 112, 112])
        row.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, HAIR)]))
        add(row, after=0)

    return _finish(story, data, out)


def _finish(story, data, out):
    doc = BaseDocTemplate(out, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=TOP_M, bottomMargin=BOT_M,
                          title="%s: %s" % (_s(data["title"]), _s(data["week"])), author="allNeurons Productivity", pageCompression=0)
    frame = Frame(MARGIN, BOT_M, CONTENT_W, FRAME_H_CI, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])
    doc.build(story, canvasmaker=_footer_canvas("Competitive Insights · " + _s(data["week"]), _s(data.get("company") or "")))
    rb.make_ascii(out)
    return doc.page


def link_problems(pdf, expected_urls):
    """Every source URL must exist as a real /URI link annotation in the PDF (not coloured text made to look like one)."""
    from pypdf import PdfReader
    found = set()
    for pg in PdfReader(pdf).pages:
        for a in pg.get("/Annots") or []:
            a = a.get_object()
            uri = (a.get("/A") or {}).get("/URI")
            if uri:
                found.add(str(uri))
    return ["source link missing from the PDF: " + u for u in expected_urls if u not in found]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    try:
        data = json.load(open(a.inp, encoding="utf-8"))
    except Exception as e:
        print("INPUT ERROR: %s" % e, file=sys.stderr); sys.exit(2)
    errs = check(data)
    if errs:
        print("FORMAT ERROR: payload does not match the documented format.", file=sys.stderr)
        for e in errs:
            print("  - " + e, file=sys.stderr)
        sys.exit(6)
    try:
        pages = draw(data, a.out)
    except Exception as e:
        print("RENDER FAILED: %s" % e, file=sys.stderr); sys.exit(3)
    lp = link_problems(a.out, [s["url"] for s in data["sources"]])
    if lp:
        print("\n".join(lp), file=sys.stderr); sys.exit(3)
    print("OK %s (%d pages)" % (a.out, pages))

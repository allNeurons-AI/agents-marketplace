#!/usr/bin/env python3
"""Daily Brief PDF renderer — implements SKILL.md in this folder.

Usage:  python3 render_brief.py --in brief.json --out Daily_Brief_YYYY-MM-DD.pdf
Input:  the same brief.json the daily-brief skill already produces,
        plus two optional keys: "date" (YYYY-MM-DD) and meetings[].status
        ("upcoming" | "passed" | "canceled").
Exit:   0 ok · 2 JSON missing/unparseable · 3 crash or reportlab missing · 6 format contract broken
        (matches run-policy §8). A markdown backup is written next to every PDF.
"""
import argparse, json, os, re, sys
from datetime import datetime, date

try:
    import reportlab  # noqa: F401
except ImportError:
    print("DEPENDENCY ERROR: reportlab is not installed. Install reportlab 5.0.1 with pip", file=sys.stderr)
    sys.exit(3)
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Flowable, KeepTogether, CondPageBreak)
from reportlab.pdfgen import canvas as rl_canvas
from reportlab import rl_config
rl_config.useA85 = 0          # raw Flate streams: ~20% smaller than ASCII85

# ── Tokens (SKILL.md §3) ───────────────────────────────────────────────────
# v1.12.0: no grey text anywhere. MUTED and META used to be #333333 / #111111, which read as pale grey in the PDF viewers and
# the Cowork UI. Hierarchy now comes from size and weight, never from a lighter text colour. (GREY below is for bars, rules
# and chip fills only; text never uses it.)
INK, BODY, MUTED, META = map(HexColor, ("#000000", "#0D0D0D", "#111111", "#111111"))
HAIR, SURFACE = map(HexColor, ("#EAECEF", "#F6F8FA"))
RED, BLUE, GREEN, GREY, AMBER, PURPLE = map(HexColor, ("#D32F2F", "#1976D2", "#388E3C", "#9E9E9E", "#E8590C", "#7B3FC4"))
TINT = {RED: HexColor("#FDECEC"), BLUE: HexColor("#E8F1FB"), GREEN: HexColor("#EAF4EB"),
        GREY: HexColor("#F1F2F4"), AMBER: HexColor("#FFF0E5"), PURPLE: HexColor("#F3EDFB")}

def text_on(col):
    """Text drawn on a chip in colour `col`: never the pale GREY, which is for fills only."""
    return INK if col == GREY else col


PAGE_W, PAGE_H = letter
MARGIN = 54                       # 0.75in
CONTENT_W = PAGE_W - 2 * MARGIN   # 504pt
FRAME_H = PAGE_H - 2 * MARGIN
S = {1: 4, 2: 8, 3: 12, 4: 16, 5: 24, 6: 32, 7: 48}   # spacing scale

# ── Fonts (SKILL.md §4): built-in Helvetica only, so PDFs stay small (~8-15 KB) and uploadable ────────────
FONTS = {"R": "Helvetica", "M": "Helvetica", "SB": "Helvetica-Bold",
         "B": "Helvetica-Bold", "I": "Helvetica-Oblique"}


def make_ascii(path):
    """Make the written PDF pure 7-bit ASCII so it can be uploaded as plain text (no base64 to transcribe).
    With uncompressed streams the only non-ASCII bytes ReportLab writes are the 4 binary-marker bytes on line 2 of the
    header; replace them in place (same length, so every xref offset stays valid). Skipped when fonts are embedded."""
    d = open(path, "rb").read()
    d = d.replace(b"\x93\x8c\x8b\x9e", b"XXXX", 1)
    open(path, "wb").write(d)
    if os.environ.get("SUITE_PDF_MINIFY", "1") != "0":      # lossless compaction (see pdf_minify.py)
        try:
            from pdf_minify import minify
            minify(path)
        except Exception as e:                                # never let compaction cost the run its PDF
            print(f"NOTE: pdf_minify skipped ({type(e).__name__}: {e})", file=sys.stderr)


# ── Reusable shapes (v1.9.5) ────────────────────────────────────────────────
# The PDF reaches the Drive by the model re-typing its text, and the full design repeated the same ~13-line rounded-
# rectangle path dozens of times (cards, pills, stat boxes, accent bars). Each distinct (width, height, radius, mode) is
# now written ONCE as a Form XObject and re-used with a 3-line `q / cm / Do / Q`. The look is identical (colours and
# line width are inherited from the page, not baked into the form); the file is smaller and far less repetitive.
# Set SUITE_PDF_REUSE=0 to draw every shape inline as before.
if os.environ.get("SUITE_PDF_REUSE", "1") != "0":
    from reportlab.pdfgen import canvas as _rl_canvas
    _orig_round = _rl_canvas.Canvas.roundRect
    _orig_circle = _rl_canvas.Canvas.circle

    def _form(self, key, draw):
        forms = self.__dict__.setdefault("_hz_forms", None)
        reg = getattr(self._doc, "_hz_forms", None)
        if reg is None:
            reg = self._doc._hz_forms = {}
        name = reg.get(key)
        if name is None:
            name = reg[key] = "Hz%d" % (len(reg) + 1)
            w, h = key[1], key[2]
            self.beginForm(name, -2, -2, w + 2, h + 2)
            draw()
            self.endForm()
        return name

    def _reuse_round(self, x, y, width, height, radius, stroke=1, fill=0):
        if not (fill or stroke):
            return
        key = ("r", round(float(width), 3), round(float(height), 3), float(radius), int(bool(stroke)), int(bool(fill)))
        name = _form(self, key, lambda: _orig_round(self, 0, 0, width, height, radius, stroke=stroke, fill=fill))
        self.saveState(); self.translate(x, y); self.doForm(name); self.restoreState()

    def _reuse_circle(self, x_cen, y_cen, r, stroke=1, fill=0):
        d = 2 * float(r)
        key = ("c", round(d, 3), round(d, 3), float(r), int(bool(stroke)), int(bool(fill)))
        name = _form(self, key, lambda: _orig_circle(self, r, r, r, stroke=stroke, fill=fill))
        self.saveState(); self.translate(x_cen - r, y_cen - r); self.doForm(name); self.restoreState()

    _rl_canvas.Canvas.roundRect = _reuse_round
    _rl_canvas.Canvas.circle = _reuse_circle


def esc(s):
    return (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def P(text, font="R", size=9.5, lead=None, color=BODY, **kw):
    st = ParagraphStyle("p", fontName=FONTS[font], fontSize=size,
                        leading=lead or round(size * 1.45, 1), textColor=color,
                        alignment=TA_LEFT, **kw)
    return Paragraph(text, st)


# ── Status system (SKILL.md §5.3) ──────────────────────────────────────────
def status_color(status):
    s = (status or "").lower()
    if s in ("open", "blocked"): return RED
    if s == "needs confirmation": return AMBER
    if s.startswith("waiting on"): return GREY
    if s in ("completed", "resolved"): return GREEN
    if s == "new": return BLUE
    return GREY


SECTION_ACCENT = {"needs_attention": RED, "conflicts": BLUE, "due_today": AMBER,
                  "worth_double_checking": PURPLE, "resolved": GREEN}


# ── Flowables ──────────────────────────────────────────────────────────────
class Masthead(Flowable):
    """Eyebrow row · date display · headline · hairline.

    No "Generated <time>" stamp: the renderer runs wherever the plugin's
    Python process happens to execute (often a cloud sandbox on UTC), which
    is not reliably the user's own local time. A timestamp that might be
    wrong is worse than no timestamp — so it is left out rather than guessed.
    The masthead's own **date** (title_date) is the brief's subject date,
    supplied by the skill from its own local `date` call, and is accurate.
    """
    def __init__(self, title_date, headline, eyebrow="DAILY BRIEF"):
        super().__init__()
        self.title_date, self.headline, self.eyebrow = title_date, headline, eyebrow
        self.hl = P(esc(headline), "M", 16, 22, INK)
        # The title is a Paragraph, not a drawString: a long company name (Call Prep) used to be drawn as one
        # unbounded 30pt line and ran off the right margin. It now wraps inside the content width.
        self.tp = P(esc(title_date), "B", 30, 36, INK)

    def wrap(self, aw, ah):
        _, hh = self.hl.wrap(aw * 0.86, ah)
        _, th = self.tp.wrap(aw, ah)
        self.hh, self.th = hh, th
        self.height = 14 + 6 + th + S[2] + hh + S[4]
        return aw, self.height

    def draw(self):
        c, w, y = self.canv, CONTENT_W, self.height
        c.setFillColor(MUTED); c.setFont(FONTS["SB"], 8.5)
        c.drawString(0, y - 9, self.eyebrow, charSpace=1.4)
        self.tp.drawOn(c, 0, y - 14 - 6 - self.th)
        self.hl.drawOn(c, 0, y - 14 - 6 - self.th - S[2] - self.hh)


STAT_ACCENT = {"Needs attention": RED, "Conflicts": BLUE, "Due today & overdue": AMBER, "Resolved": GREEN}


class StatRow(Flowable):
    """Four equal cards. A count above 0 takes its own status colour (tinted
    background, number and label in that colour); a zero stays neutral grey."""
    def __init__(self, stats):
        super().__init__()
        order = ["Needs attention", "Conflicts", "Due today & overdue", "Resolved"]
        self.items = [(k, int(stats.get(k, 0) or 0)) for k in order]
        self.height = 66

    def wrap(self, aw, ah):
        return aw, self.height

    def draw(self):
        c, gap = self.canv, S[2]
        cw = (CONTENT_W - 3 * gap) / 4
        y0 = 0
        for i, (label, n) in enumerate(self.items):
            x = i * (cw + gap)
            hot = n > 0
            accent = STAT_ACCENT[label]
            c.setFillColor(TINT[accent] if hot else SURFACE); c.setStrokeColor(TINT[accent] if hot else SURFACE)
            c.roundRect(x, y0, cw, self.height, 6, fill=1, stroke=0)
            c.setFillColor(accent if hot else META); c.setFont(FONTS["B"], 28)
            c.drawString(x + S[3], y0 + 28, str(n))
            c.setFillColor(accent if hot else MUTED); c.setFont(FONTS["SB"], 8)
            c.drawString(x + S[3], y0 + 12, label.upper(), charSpace=0.5)


def parse_time(t, hint=None):
    """'9:35 pm' / '21:35' / '1:00' → minutes from midnight. Bare h:mm borrows am/pm from hint.

    A bare hour in 1-12 with no am/pm anywhere — not on the value, not on the
    label hint — is genuinely ambiguous: 9:15 could be morning or evening, and
    guessing silently is exactly how a brief has previously shown an evening
    meeting as if it were in the morning. Real 24-hour values (13-23, or 0)
    are unambiguous on their own and need no hint.
    """
    if isinstance(t, (int, float)): return int(t)
    m = re.match(r"\s*(\d{1,2})(?::(\d{2}))?\s*([ap]m)?", str(t).lower())
    if not m: raise ValueError(f"bad time {t!r}")
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3) or hint
    if ap is None and 1 <= h <= 12:
        raise ValueError(
            f"ambiguous time {t!r} — no am/pm marker on the value or in the "
            f"meeting label, and hour {h} could be either. Pass an explicit "
            f"am/pm (e.g. \"9:15 pm\") or a 24-hour/minutes-from-midnight value."
        )
    if ap == "pm" and h != 12: h += 12
    if ap == "am" and h == 12: h = 0
    return h * 60 + mi


def meeting_status(m):
    s = (m.get("status") or "").lower()
    if s: return s
    blob = (m.get("format", "") + " " + m.get("label", "")).lower()
    if "cancel" in blob: return "canceled"
    if "passed" in blob: return "passed"
    return "upcoming"


def meeting_times(m):
    lab = m.get("label", "").lower()
    ap = re.findall(r"\b([ap]m)\b", lab)
    s = parse_time(m["start"], ap[0] if ap else None)
    e = parse_time(m["end"], ap[-1] if ap else None)
    if e <= s: e += 12 * 60 if e + 12 * 60 > s else 24 * 60
    return s, min(e, 24 * 60)


class SectionLabel(Flowable):
    """Tracked caps label + count chip + hairline to the right edge."""
    def __init__(self, text, count=None, accent=None, space_before=S[5] + S[1]):
        super().__init__()
        self.text, self.count, self.accent, self.sb = text.upper(), count, accent, space_before
        self.height = 14

    def wrap(self, aw, ah):
        # First thing on a page: no space above. Only an availHeight that IS the frame height means "top of page";
        # KeepTogether measures with a huge height, which used to be misread as top-of-page, dropped the space-before
        # from the measurement and let a heading strand itself at the foot of a page with its first item on the next.
        top = FRAME_H - 1 <= ah <= FRAME_H + 1
        return aw, (0 if top else self.sb) + self.height + S[3]

    def draw(self):
        c, y = self.canv, S[3] + 2
        if self.accent is not None:
            c.setFillColor(self.accent); c.circle(3, y + 3, 2.6, fill=1, stroke=0); x = 11
        else:
            x = 0
        c.setFillColor(INK); c.setFont(FONTS["SB"], 10)
        c.drawString(x, y, self.text, charSpace=0.8)
        x += c.stringWidth(self.text, FONTS["SB"], 10) + 0.8 * len(self.text) + 6
        if self.count:
            txt = str(self.count); cw = c.stringWidth(txt, FONTS["SB"], 8.5) + 4
            c.setFillColor(MUTED); c.setFont(FONTS["SB"], 8.5); c.drawString(x, y + 0.5, txt)
            x += cw + 8
        c.setStrokeColor(HAIR); c.setLineWidth(0.75); c.line(x, y + 3, CONTENT_W, y + 3)


class ActionCard(Flowable):
    """Plain item (v1.14.0): bold action · detail · labelled meta row, a coloured status word, one hairline underneath.
    No background block, no accent bar, no pill."""
    PAD = S[2]

    def __init__(self, item, accent, index=None, informational=False):
        super().__init__()
        self.item, self.accent, self.idx, self.info = item, accent, index, informational
        self.status = None if informational else item.get("status")

    def _parts(self, aw):
        it, parts = self.item, []
        inner = aw
        self.pill_w = 0
        if self.status:
            self.pill_w = pdfmetrics.stringWidth(self.status.upper(), FONTS["SB"], 8) + 6
        if self.info:
            parts.append(P(esc(it.get("body")), "I", 11.5, 17, MUTED))
            return parts, inner
        action = it.get("action") or it.get("title") or ""
        head = (f'<font name="{FONTS["SB"]}" color="#111111">{self.idx:02d}&nbsp;&nbsp;</font>' if self.idx else "") + esc(action)
        parts.append(("head", P(head, "SB", 13, 18, INK)))
        lead = it.get("title") if it.get("title") and it.get("action") else ""
        rest = " ".join(x for x in [it.get("body"), it.get("meta")] if x)
        if lead or rest:
            lead_html = f'<font name="{FONTS["SB"]}" color="#000000">{esc(lead.rstrip("."))}.</font>&nbsp;&nbsp;' if lead else ""
            parts.append(P(lead_html + esc(rest), "R", 11.5, 17, BODY))
        if it.get("fix"):
            parts.append(P(f'<font name="{FONTS["SB"]}" color="#000000">Suggested fix&nbsp;&nbsp;</font>{esc(it["fix"])}', "R", 11.5, 17, BODY))
        lab = lambda k: f'<font name="{FONTS["SB"]}" size="8" color="#111111">{k}</font>&nbsp;&nbsp;'
        bits = []
        if it.get("owner"): bits.append(lab("OWNER") + esc(it["owner"]))
        if it.get("by_when"): bits.append(lab("DUE") + esc(it["by_when"]))
        if bits:
            parts.append(P("&nbsp;&nbsp;&nbsp;&nbsp;".join(bits), "R", 10, 14, MUTED))
        if it.get("source"):
            parts.append(P(lab("SOURCE") + esc(it["source"]), "R", 10, 14, MUTED))
        return parts, inner

    def wrap(self, aw, ah):
        self.aw = aw
        self.parts, inner = self._parts(aw)
        self.laid, h = [], 0
        for i, p in enumerate(self.parts):
            head = isinstance(p, tuple)
            para = p[1] if head else p
            wid = inner - (self.pill_w + S[2] if head else 0)
            _, ph = para.wrap(wid, ah)
            txt = getattr(para, "text", "")
            is_meta = "OWNER" in txt or "DUE" in txt or "SOURCE" in txt
            prev_meta = i > 0 and self.laid and self.laid[-1][4]
            gap = 0 if i == 0 else (2 if (is_meta and prev_meta) else (S[2] if is_meta else S[1]))
            h += gap
            self.laid.append((para, ph, gap, head, is_meta))
            h += ph
        self.height = h + self.PAD * 2
        return aw, self.height + S[2]

    def draw(self):
        c, h = self.canv, self.height
        y0 = S[2]
        c.setStrokeColor(HAIR); c.setLineWidth(0.75)
        c.line(0, y0, self.aw, y0)                       # the only decoration: one hairline under the item
        y = y0 + h - self.PAD
        x = 0
        for para, ph, gap, head, _m in self.laid:
            y -= gap + ph
            para.drawOn(c, x, y)
            if head and self.status:
                col = status_color(self.status)          # status is a coloured word, not a filled pill
                c.setFillColor(text_on(col)); c.setFont(FONTS["SB"], 8)
                c.drawRightString(self.aw, y + ph - 12, self.status.upper())


class DayLine(Flowable):
    """The calendar line (): the whole day as one horizontal strip with every meeting drawn at its real
    time. Overlapping meetings stack in lanes and draw red, so a double-booking is visible at a glance.
    Meetings whose times cannot be placed (all-day) are not drawn here; they still appear in the list below."""
    LANE_H, LANE_GAP, AXIS_H = 12, 3, 14
    SOLID = {"blue": HexColor("#8DB9E8"), "grey": HexColor("#C9CCD1"), "red": HexColor("#EE9A9A")}
    EDGE = {"blue": BLUE, "grey": GREY, "red": RED}

    def __init__(self, meetings):
        super().__init__()
        raw = []
        for m in meetings:
            try:
                s_, e_ = meeting_times(m)
            except Exception:
                continue
            if e_ > s_:
                raw.append((s_, e_, meeting_status(m), m.get("kind") or ""))
        raw.sort()
        self.blocks, lane_end = [], []              # blocks: (start, end, colour key, lane)
        for s_, e_, st, kind in raw:
            lane = next((i for i, end in enumerate(lane_end) if s_ >= end), None)
            if lane is None:
                lane_end.append(e_); lane = len(lane_end) - 1
            else:
                lane_end[lane] = e_
            overlaps = any(o[0] < e_ and s_ < o[1] and o is not (s_, e_, st, kind) for o in raw if o[:2] != (s_, e_)) \
                or sum(1 for o in raw if o[0] < e_ and s_ < o[1]) > 1
            live = st != "canceled"
            colour = "red" if (live and (kind == "conflict" or overlaps)) else ("blue" if st == "upcoming" else "grey")
            self.blocks.append((s_, e_, colour, lane))
        self.n_lanes = max(1, len(lane_end))
        self.items = self.blocks
        if raw:
            lo = min(r[0] for r in raw); hi = max(r[1] for r in raw)
            self.t0 = max(0, (lo // 60) * 60 - 60)
            self.t1 = min(24 * 60, -(-hi // 60) * 60 + 60)
            while self.t1 - self.t0 < 360:          # never a hair-thin day
                if self.t1 < 24 * 60: self.t1 += 60
                elif self.t0 > 0: self.t0 -= 60
                else: break
            self.height = self.AXIS_H + self.n_lanes * (self.LANE_H + self.LANE_GAP) + S[2]
        else:
            self.t0 = self.t1 = 0; self.height = 0

    def wrap(self, aw, ah):
        return aw, self.height

    def _x(self, minute):
        return CONTENT_W * (minute - self.t0) / float(self.t1 - self.t0)

    def draw(self):
        if not self.blocks:
            return
        c, top, base = self.canv, self.height - S[2], self.AXIS_H
        c.setStrokeColor(HAIR); c.setLineWidth(0.5)
        step = 60 if self.t1 - self.t0 <= 600 else 120
        h = -(-self.t0 // step) * step
        c.setFont(FONTS["R"], 7.5); c.setFillColor(META)
        while h <= self.t1:
            x = self._x(h); c.line(x, base - 2, x, top)
            hr = (h // 60) % 24
            lab = "%d%s" % (hr % 12 or 12, "am" if hr < 12 else "pm")
            tw = pdfmetrics.stringWidth(lab, FONTS["R"], 7.5)
            c.drawString(min(max(x - tw / 2, 0), CONTENT_W - tw), 2, lab)
            h += step
        for s_, e_, colour, lane in self.blocks:
            x0, x1 = self._x(max(s_, self.t0)), self._x(min(e_, self.t1))
            y = base + lane * (self.LANE_H + self.LANE_GAP)
            c.setFillColor(self.SOLID[colour]); c.roundRect(x0, y, max(x1 - x0, 3), self.LANE_H, 3, fill=1, stroke=0)
            c.setFillColor(self.EDGE[colour]); c.rect(x0, y, 2.5, self.LANE_H, fill=1, stroke=0)


class MeetingRow(Flowable):
    """Compact calendar line: time column, then **title** and dim details on one flowing line, status chip right.
    One line per meeting when it fits (SKILL.md: 'every event, one line'); wraps, never overflows."""
    TIME_W, CHIP_W = 112, 70

    def __init__(self, m, last=False):
        super().__init__()
        self.m, self.last = m, last
        self.st = meeting_status(m)
        lab = m.get("label", "")
        self.time = lab.split("\u2014")[0].strip() if "\u2014" in lab else f'{m["start"]}\u2013{m["end"]}'
        self.title = lab.split("\u2014", 1)[1].strip() if "\u2014" in lab else lab
        dim = self.st != "upcoming"
        det = " \u00b7 ".join(x for x in [m.get("who"), re.sub(r"\s*\((already passed|canceled)\)", "", m.get("format", ""), flags=re.I)] if x)
        head = f'<font name="{FONTS["SB"] if not dim else FONTS["M"]}" size="11" color="#000000">{esc(self.title)}</font>'
        tail = f'&nbsp;&nbsp;<font name="{FONTS["R"]}" size="9" color="#111111">{esc(det)}</font>' if det else ""
        self.tp = P(head + tail, "R", 11, 14, INK)
        self.timep = P(esc(self.time), "SB", 10.5, 14, INK)

    def wrap(self, aw, ah):
        self.aw = aw
        tw = aw - self.TIME_W - self.CHIP_W - 8
        _, a = self.tp.wrap(tw, ah)
        _, b = self.timep.wrap(self.TIME_W - 8, ah)
        self.h1 = max(a, b)
        self.height = 6 + self.h1 + 6
        return aw, self.height

    def draw(self):
        c, h = self.canv, self.height
        self.timep.drawOn(c, 0, h - 6 - self.timep.height)
        self.tp.drawOn(c, self.TIME_W, h - 6 - self.tp.height)
        lab = {"upcoming": "UPCOMING", "passed": "PASSED", "canceled": "CANCELED"}[self.st]
        col = {"upcoming": BLUE, "passed": GREY, "canceled": GREY}[self.st]
        cw = pdfmetrics.stringWidth(lab, FONTS["SB"], 7.5) + 12
        c.setFillColor(text_on(col)); c.setFont(FONTS["SB"], 7.5); c.drawRightString(self.aw, h - 6 - 8.8, lab)
        if not self.last:
            c.setStrokeColor(HAIR); c.setLineWidth(0.5); c.line(0, 0, self.aw, 0)


# ── Page chrome: running footer with Page X of Y (two-pass canvas) ─────────
def make_canvas(footer_left):
    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k); self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__)); self._startPage()

        def save(self):
            n = len(self._saved)
            for st in self._saved:
                self.__dict__.update(st); self._chrome(n); super().showPage()
            super().save()

        def _chrome(self, total):
            y = MARGIN - 26
            self.setStrokeColor(HAIR); self.setLineWidth(0.5)
            self.line(MARGIN, y + 12, PAGE_W - MARGIN, y + 12)
            self.setFont(FONTS["R"], 8.5); self.setFillColor(META)
            right = f"Page {self._pageNumber} of {total}"
            room = CONTENT_W - pdfmetrics.stringWidth(right, FONTS["R"], 8.5) - 16   # never collide with the page number
            left = footer_left
            while len(left) > 1 and pdfmetrics.stringWidth(left, FONTS["R"], 8.5) > room:
                left = left[:-2].rstrip()
                if pdfmetrics.stringWidth(left + "...", FONTS["R"], 8.5) <= room:
                    left += "..."; break
            self.drawString(MARGIN, y, left)
            self.drawRightString(PAGE_W - MARGIN, y, right)
    return NumberedCanvas


# ── Format contract (run-policy §8, exit 6) ─────────────────────────
STATUSES = ("open", "completed", "blocked", "needs confirmation", "new")
NOBODY = ("you", "team", "the team", "them", "tbd", "todo", "")


def status_ok(st):
    s = (st or "").strip().lower()
    return s in STATUSES or (s.startswith("waiting on ") and len(s) > 11)


def check_items(section, items, errs):
    for i, it in enumerate(items or []):
        if it.get("informational"):
            continue
        tag = f"{section}[{i}]"
        for k in ("action", "owner", "by_when"):
            if not str(it.get(k) or "").strip():
                errs.append(f"{tag}: missing {k}")
        if str(it.get("owner") or "").strip().lower() in NOBODY and it.get("owner") is not None:
            errs.append(f"{tag}: owner '{it.get('owner')}' names nobody — use the person's name")
        if not status_ok(it.get("status")):
            errs.append(f"{tag}: status '{it.get('status')}' is not Open / Completed / Blocked / Waiting on <name> / Needs confirmation / New")
        if (it.get("status") or "").lower() == "completed" and not it.get("source"):
            errs.append(f"{tag}: Completed with no source")


def fail_format(errs):
    print("FORMAT ERROR: payload does not match the documented format.", file=sys.stderr)
    for e in errs:
        print("  - " + e, file=sys.stderr)
    sys.exit(6)


def write_md_backup(pdf_path, lines):
    md = os.path.splitext(pdf_path)[0] + ".md"
    with open(md, "w") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return md


def brief_markdown(d):
    L = [f"# {d['title']}", "", d["headline"], ""]
    st = d.get("stats") or {}
    L += [" · ".join(f"{k}: {v}" for k, v in st.items()), ""]
    def items(title, arr):
        L.append(f"## {title}")
        if not arr:
            L.extend(["None.", ""]); return
        for it in arr:
            if it.get("informational"):
                L.append(f"- {it.get('body','')}"); continue
            head = it.get("action") or it.get("title") or ""
            L.append(f"- **{head}**" + (f" [{it['status']}]" if it.get("status") else ""))
            for k in ("title", "body", "meta", "fix"):
                if it.get(k) and not (k == "title" and head == it.get("title")):
                    L.append(f"  {it[k]}")
            meta = " · ".join(x for x in [it.get("owner") and "Owner: " + it["owner"], it.get("by_when"), it.get("source")] if x)
            if meta: L.append(f"  {meta}")
        L.append("")
    items("Needs attention", d["needs_attention"]); items("Conflicts", d["conflicts"])
    items("Due today & overdue", d["due_today"]); items("Worth double-checking", d["worth_double_checking"])
    L.append("## Today's meetings")
    for m in d["meetings"] or []:
        L.append(f"- {m.get('label','')} — {m.get('who','')} · {m.get('format','')}")
    L.append("")
    items("Resolved", d["resolved"])
    if d["sources"]:
        L.append("## Sources")
        for i, s in enumerate(d["sources"], 1):
            s = s if isinstance(s, dict) else {"label": s}
            L.append(f"{i}. {s['label']}" + (f" — {s['url']}" if s.get("url") else ""))
    return L


# ── Build ──────────────────────────────────────────────────────────────────
REQUIRED = ["title", "headline", "stats", "meetings", "conflicts", "due_today",
            "worth_double_checking", "needs_attention", "resolved", "sources"]


def check_meetings(meetings, errs):
    """Reject an ambiguous start/end before layout ever runs `meeting_times`,
    so a bad payload is a named FORMAT ERROR (exit 6) rather than a raw
    traceback (exit 3) or — worse — a silent AM/PM misread."""
    for i, m in enumerate(meetings or []):
        try:
            meeting_times(m)
        except ValueError as e:
            errs.append(f"meetings[{i}] ({m.get('label') or m.get('title') or 'untitled'}): {e}")


def build(data, out):
    """Standalone use: validate, draw, write the markdown backup."""
    errs = [f"missing key: {k}" for k in REQUIRED if k not in data]
    if not errs:
        if not str(data.get("headline") or "").strip(): errs.append("headline is empty")
        if not data.get("stats"): errs.append("stats is empty")
        for sec in ("needs_attention", "conflicts", "due_today", "worth_double_checking"):
            check_items(sec, data.get(sec), errs)
        check_meetings(data.get("meetings"), errs)
    if errs:
        fail_format(errs)
    pages = draw(data, out)
    write_md_backup(out, brief_markdown(data))
    return pages


def draw(data, out):
    """Layout only — no validation, no backup. Used by suite_pdf.py, whose core owns the checks."""
    for k in REQUIRED:
        data.setdefault(k, [] if k not in ("title", "headline", "stats") else ("" if k != "stats" else {}))

    d = datetime.strptime(data["date"], "%Y-%m-%d").date() if data.get("date") else date.today()
    title_date = d.strftime("%A, %B ") + str(d.day)
    short = d.strftime("%a ") + str(d.day) + d.strftime(" %b %Y")
    story = [Masthead(title_date, data["headline"]),
             StatRow(data["stats"])]

    # Today's meetings comes first after the stat row (design spec): no timeline
    # bar, just the ordered rows (upcoming -> passed -> canceled).
    ms = data["meetings"]
    if ms:
        order = {"upcoming": 0, "passed": 1, "canceled": 2}
        ms_sorted = sorted(ms, key=lambda m: (order[meeting_status(m)], meeting_times(m)[0]))
        rows = [MeetingRow(m, last=(i == len(ms_sorted) - 1)) for i, m in enumerate(ms_sorted)]
        dl = DayLine(ms_sorted)
        head_items = [SectionLabel("Today's meetings", len(ms))] + ([dl] if dl.items else []) + [rows[0]]
        story.append(KeepTogether(head_items))
        story.extend(rows[1:])
    else:
        story += [SectionLabel("Today's meetings", 0), P("No meetings on the calendar today.", "I", 11.5, 17, MUTED)]

    def section(key, label, numbered=False):
        items = data.get(key) or []
        if not items: return
        acc = SECTION_ACCENT[key]
        real = [i for i in items if not i.get("informational")]
        cards = []
        n = 0
        for it in items:
            info = bool(it.get("informational"))
            if not info: n += 1
            cards.append(ActionCard(it, GREY if info else acc, index=(n if numbered and not info else None), informational=info))
        story.append(CondPageBreak(90))
        story.append(KeepTogether([SectionLabel(label, len(real), acc), cards[0]]))
        story.extend(cards[1:])

    section("needs_attention", "Needs attention", numbered=True)
    section("conflicts", "Conflicts", numbered=True)
    section("due_today", "Due today & overdue", numbered=True)

    folds = []
    if not data["conflicts"]: folds.append("No scheduling conflicts today.")
    if not data["due_today"]: folds.append("Nothing due today and nothing overdue.")
    if folds:
        story.append(Spacer(1, S[3]))
        story.append(P("&nbsp;&nbsp;·&nbsp;&nbsp;".join(folds), "R", 11, 16, MUTED))

    section("worth_double_checking", "Worth double-checking")

    if data["resolved"]:
        section("resolved", "Resolved")

    if data["sources"]:
        story.append(CondPageBreak(80))
        story.append(SectionLabel("Sources", len(data["sources"])))
        for i, s in enumerate(data["sources"], 1):
            s = s if isinstance(s, dict) else {"label": s}
            lab = esc(s["label"])
            if s.get("url"):
                lab = f'<link href="{esc(s["url"])}" color="#1976D2">{lab}</link>'
            story.append(P(f'<font color="#111111">{i}.</font>&nbsp;&nbsp;{lab}', "R", 10, 15, MUTED))

    doc = BaseDocTemplate(out, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN - 6, bottomMargin=MARGIN + 6,
                          title=data["title"], author="allNeurons Productivity", pageCompression=0)
    frame = Frame(MARGIN, MARGIN + 6, CONTENT_W, PAGE_H - 2 * MARGIN, id="f", leftPadding=0,
                  rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])
    doc.build(story, canvasmaker=make_canvas("Daily Brief · " + short))
    make_ascii(out)
    return doc.page


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-inter", action="store_true", help="deprecated no-op: built-in Helvetica is always used")
    a = ap.parse_args()
    try:
        data = json.load(open(a.inp))
    except Exception as e:
        print(f"INPUT ERROR: {e}", file=sys.stderr); sys.exit(2)
    try:
        pages = build(data, a.out)
    except SystemExit:
        raise
    except Exception as e:
        print(f"RENDER ERROR: {type(e).__name__}: {e}", file=sys.stderr); sys.exit(3)
    if pages > 2:
        print(f"ACCURACY WARNING: {pages} pages — over the 2-page soft target; the PDF is still valid, attach it.", file=sys.stderr)
    md = os.path.splitext(a.out)[0] + ".md"
    print(f"OK {a.out} — {pages} page(s) · local .md working copy (never attach or upload it): {md} · fonts: {FONTS['R']}")

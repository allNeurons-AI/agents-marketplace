"""COMPACT renderer -- tier 3 of the size-fit chain (full -> lite -> compact -> multipart), and the part renderer.

Same payload, same words, the same type sizes as the lite layout (body 9.5 pt, meta 8.5 pt -- never smaller, the design
floor) and the same margins and leading. Only byte overhead is removed, with these levers and no others:

  * no per-page decoration: the footer rule is dropped (the footer TEXT stays: it carries `Page N of N`, which the
    format gate and the upload read-back both require);
  * one text object per page (one `BT ... ET`) instead of one `q/cm/BT/ET/Q` wrapper per paragraph;
  * each item's lines merged into a single flowing paragraph (title + body + owner/by/source on one run of text);
  * all sources merged into one numbered flowing paragraph.

Every content item is kept. Nothing is dropped, abbreviated or reworded. (The markdown backup is a local working copy
that is never part of an upload, so there is nothing to strip there.) The output is pure 7-bit ASCII with uncompressed
streams, like the other tiers, so it can be uploaded as plain text.

`units(kind, data)` exposes the content as ordered, independently placeable units (a header, then one unit per item,
per meeting, per source...). The multipart tier packs consecutive units into parts; each part re-states its section
headings, so every part is a complete, readable PDF on its own.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas as rl_canvas
from reportlab import rl_config

rl_config.useA85 = 0

M = 54
W = letter[0] - 2 * M
TOP = letter[1] - M
BOTTOM = M + 6                      # room for the footer line; text never goes below this
# style -> (font, size, leading, space_before)   (sizes/leading are exactly lite's; never shrunk)
ST = {
    "title": ("Helvetica-Bold", 18, 22, 0),
    "head": ("Helvetica", 11.5, 15, 2),
    "sec": ("Helvetica-Bold", 11, 14, 10),
    "item": ("Helvetica-Bold", 10, 13, 5),
    "body": ("Helvetica", 9.5, 12.5, 0),
    "meta": ("Helvetica-Oblique", 8.5, 11, 0),
    "src": ("Helvetica", 9.5, 12.5, 0),
}


def _s(x):
    return " ".join(str(x if x is not None else "").split())


def _unit(section, blocks, heading=None, empty=False):
    return {"section": section, "blocks": blocks, "heading": heading, "empty": empty}


def _item_unit(section, it):
    if not isinstance(it, dict):
        return _unit(section, [("body", _s(it))])
    lead = _s(it.get("action") or it.get("title") or it.get("body"))
    if it.get("status"):
        lead += " [%s]" % _s(it["status"])
    parts = []
    if it.get("title") and it.get("action") and it["title"] != it["action"]:
        parts.append(_s(it["title"]))
    for k in ("body", "meta", "fix"):
        if it.get(k) and _s(it.get(k)) != _s(it.get("action") or it.get("title") or it.get("body")):
            parts.append(("Suggested fix: " if k == "fix" else "") + _s(it[k]))
    bits = []
    if it.get("owner"):
        bits.append("Owner: " + _s(it["owner"]))
    if it.get("by_when"):
        bits.append("By: " + _s(it["by_when"]))
    if it.get("source"):
        bits.append("Source: " + _s(it["source"]))
    if bits:
        parts.append(" | ".join(bits))
    blocks = [("item", lead)]
    if parts:
        blocks.append(("body", " ".join(parts)))
    return _unit(section, blocks)


def _sec_units(out, title, items, empty_text):
    if not items:
        out.append(_unit(title, [("meta", empty_text)], heading=title, empty=True))
        return
    for it in items:
        out.append(_item_unit(title, it))
        out[-1]["counted"] = True


def _src_text(i, s):
    s = s if isinstance(s, dict) else {"label": s}
    return "%d. %s" % (i, _s(s.get("label")))


def units(kind, d):
    """Ordered content units. The first unit(s) with section None are the header; sources always come last."""
    u = []
    if kind == "daily_brief":
        hdr = [("title", _s(d.get("title", "Daily Brief"))), ("head", _s(d.get("headline", "")))]
        st = d.get("stats") or {}
        if st:
            hdr.append(("meta", "  |  ".join("%s: %s" % (k, v) for k, v in st.items())))
        u.append(_unit(None, hdr))
        ms = d.get("meetings") or []
        if ms:
            for m in ms:
                u.append(_unit("Today's meetings", [("body", "%s - %s - %s" % (_s(m.get("label")), _s(m.get("who")), _s(m.get("format"))))],
                               heading="Today's meetings"))
        else:
            u.append(_unit("Today's meetings", [("meta", "No meetings today.")], heading="Today's meetings", empty=True))
        _sec_units(u, "Needs attention", d.get("needs_attention") or [], "Nothing needs attention.")
        _sec_units(u, "Conflicts", d.get("conflicts") or [], "No scheduling conflicts today.")
        _sec_units(u, "Due today & overdue", d.get("due_today") or [], "Nothing due or overdue.")
        _sec_units(u, "Worth double-checking", d.get("worth_double_checking") or [], "Nothing to double-check.")
        _sec_units(u, "Resolved", d.get("resolved") or [], "Nothing resolved.")
    elif kind == "competitive_insights":
        u += _comp_units(d)
    else:
        u.append(_unit(None, [("title", "Call Prep - " + _s(d.get("company"))), ("head", _s(d.get("context"))),
                              ("meta", " | ".join(x for x in [d.get("time"), d.get("duration"), d.get("format"),
                                                              d.get("owner") and "Owner: " + d["owner"],
                                                              d.get("last_contact") and "Last contact: " + d["last_contact"]] if x)),
                              ("body", "Desired outcome: " + _s(d.get("desired_outcome")))]))
        sec = "Who you'll be speaking with"
        for a in d.get("attendees") or []:
            u.append(_unit(sec, [("body", "%s, %s, %s - %s" % (_s(a.get("name")), _s(a.get("title")), _s(a.get("company")), _s(a.get("body"))))], heading=sec))
        if d.get("absent_decision_maker"):
            u.append(_unit(sec, [("body", "Not on the invite: " + _s(d["absent_decision_maker"]))], heading=sec))
        sec = "What you need to know"
        for x in d.get("what_you_need_to_know") or []:
            u.append(_unit(sec, [("body", "- " + _s(x.get("body")) + (" [%s]" % _s(x.get("source")) if x.get("source") else ""))], heading=sec))
        u.append(_unit("What you should accomplish", [("body", _s(d.get("objective")))], heading="What you should accomplish"))
        sec = "Questions to ask"
        for i, q in enumerate(d.get("questions") or [], 1):
            q = q if isinstance(q, str) else q.get("question") or q.get("body") or q
            u.append(_unit(sec, [("body", "%d. %s" % (i, _s(q)))], heading=sec))
        sec = "Risks to watch"
        for x in d.get("risks") or []:
            u.append(_unit(sec, [("body", "- " + _s(x.get("body")))], heading=sec))
        sec = "Actions & owners"
        for a in d.get("actions") or []:
            u.append(_unit(sec, [("body", "%s - %s - %s - %s" % (_s(a.get("body")), _s(a.get("owner")), _s(a.get("by_when")), _s(a.get("status"))))], heading=sec))
    # all sources merged into one numbered flowing paragraph (one unit per source so multipart can still split them)
    for i, s in enumerate(d.get("sources") or [], 1):
        if kind == "competitive_insights":   # one line per source, with its URL so the line becomes a real link annotation
            u.append(_unit("Sources", [("src", _src_text(i, s), s.get("url"))], heading="Sources"))
        else:
            u.append(_unit("Sources", [("body", _src_text(i, s))], heading="Sources"))
    return _mark(u)


def _refs(r):
    r = [x for x in (r if isinstance(r, list) else [r]) if isinstance(x, int)]
    return (" [%s]" % ", ".join(str(x) for x in r)) if r else ""


def _comp_units(d):
    """Competitive Insights in the compact (plain-text) layout: every section and every entry, links on the sources."""
    u = [_unit(None, [("title", _s(d.get("company") and "%s: %s" % (d["company"], d["title"]) or d.get("title"))),
                      ("head", _s(d.get("week"))),
                      ("meta", "Tracked competitors: %d  |  Updates: %d  |  High threats: %d  |  Opportunities: %d" % (
                          sum(len(x.get("competitors", [])) for x in d.get("sets", [])),
                          len([x for x in d.get("updates", []) if not x.get("quiet")]),
                          len([x for x in d.get("threats", []) if x.get("level") == "High"]), len(d.get("opportunities", []))))])]
    es = d.get("executive_summary"); es = es if isinstance(es, list) else [es]
    for t in es:
        u.append(_unit("Executive summary", [("body", _s(t))], heading="Executive summary"))
    for x in d.get("sets", []):
        u.append(_unit("Tracked competitors", [("body", "%s - %s: %s" % (_s(x.get("key")), _s(x.get("name")), "; ".join(
            "%s (%s)" % (_s(c.get("name")), _s(c.get("description"))) for c in x.get("competitors", []))))], heading="Tracked competitors"))
    for x in d.get("updates", []):
        if x.get("quiet"):
            u.append(_unit("Key competitor updates", [("body", "%s: quiet week, nothing material found." % _s(x.get("competitor")))], heading="Key competitor updates"))
        else:
            u.append(_unit("Key competitor updates", [("item", _s(x.get("competitor")) + _refs(x.get("sources"))),
                                                       ("body", "%s%s Why it matters to us: %s%s" % (_s(x.get("what")), (" Key facts: " + "; ".join(_s(f) for f in x["facts"]) + ".") if x.get("facts") else "",
                                                                               _s(x.get("why")), (" Our response: " + _s(x["response"])) if x.get("response") else ""))], heading="Key competitor updates"))
    for x in d.get("new_entrants") or []:
        u.append(_unit("New entrants to watch", [("body", "%s: %s%s" % (_s(x.get("name")), _s(x.get("note")), _refs(x.get("source"))))], heading="New entrants to watch"))
    for x in d.get("working_well", []):
        u.append(_unit("What is working well", [("item", _s(x.get("title")) + _refs(x.get("source"))), ("body", _s(x.get("body")))], heading="What is working well"))
    for x in d.get("insights", []):
        x = x if isinstance(x, dict) else {"body": x}
        u.append(_unit("Product and market insights", [("body", ((_s(x["title"]) + ": ") if x.get("title") else "") + _s(x.get("body")))], heading="Product and market insights"))
    for x in d.get("threats", []):
        u.append(_unit("Competitive threats", [("item", "[%s] %s" % (_s(x.get("level")).upper(), _s(x.get("title")))),
                                               ("body", _s(x.get("why")) + ((" Potential impact: " + _s(x["impact"])) if x.get("impact") else ""))], heading="Competitive threats"))
    for x in d.get("opportunities", []):
        u.append(_unit("Opportunities for us", [("item", _s(x.get("title"))), ("body", _s(x.get("body")))], heading="Opportunities for us"))
    order = {"High": 0, "Medium": 1, "Low": 2}
    for n, x in enumerate(sorted(d.get("actions", []), key=lambda a: order.get(a.get("priority"), 3)), 1):
        u.append(_unit("Recommended actions", [("item", "%02d [%s] %s" % (n, _s(x.get("priority")).upper(), _s(x.get("action")))),
                                               ("body", "Reason: " + _s(x.get("reason")) + ((" Owner: " + _s(x["owner"]) + ".") if x.get("owner") else "") + ((" By: " + _s(x["by_when"]) + ".") if x.get("by_when") else ""))], heading="Recommended actions"))
    return u


def _mark(us):
    """Post-pass: flag the first unit of each section and the number of items in counted sections."""
    totals = {}
    for u in us:
        if u.get("counted"):
            totals[u["section"]] = totals.get(u["section"], 0) + 1
    seen = set()
    for u in us:
        s = u["section"]
        u["first"] = s is not None and s not in seen
        u["total"] = totals.get(s)
        seen.add(s)
    return us


def split_oversize(us, limit=20000):
    """A single block longer than `limit` characters is split at word boundaries into consecutive units of the same
    section, so the multipart packer can always place every unit. Nothing is cut: the pieces concatenate to the original."""
    out = []
    for u in us:
        big = [i for i, b in enumerate(u["blocks"]) if len(b[1]) > limit]
        if not big:
            out.append(u); continue
        for i, b in enumerate(u["blocks"]):
            st, t = b[0], b[1]
            if i not in big:
                out.append(dict(u, blocks=[b], counted=u.get("counted") and i == 0))
                continue
            words, piece, n = t.split(" "), [], 0
            for w in words:
                if n + len(w) + 1 > limit and piece:
                    out.append(dict(u, blocks=[(st, " ".join(piece))], counted=False)); piece, n = [], 0
                piece.append(w); n += len(w) + 1
            out.append(dict(u, blocks=[(st, " ".join(piece))], counted=False))
    return _mark(out)


def blocks_for_part(us, part=None, of=None):
    """Flatten units into (style, text) blocks. A section heading is emitted whenever the section changes; a part that
    starts mid-section says '(continued)'. Consecutive sources are merged into one flowing paragraph."""
    out, prev = [], None
    for u in us:
        sec = u["section"]
        if sec is None:
            blocks = list(u["blocks"])
            if part and of and of > 1:
                blocks[0] = (blocks[0][0], "%s (part %d of %d)" % (blocks[0][1], part, of))
                if part > 1:       # parts after the first carry only the title; the header detail lives in part 1
                    blocks = blocks[:1] + [("meta", "Continued: part %d of %d of this document. All parts together hold every item; "
                                                    "each part is a complete PDF." % (part, of))]
            out.extend(blocks)
            prev = None
            continue
        if sec != prev:
            label = sec
            if not u["first"]:
                label += " (continued)"
            elif u["total"]:
                label += " (%d)" % u["total"]
            out.append(("sec", label))
        if sec == "Sources" and prev == "Sources" and len(u["blocks"][0]) == 2 and len(out[-1]) == 2:
            out[-1] = ("body", out[-1][1] + "   " + u["blocks"][0][1])
        else:
            out.extend(u["blocks"])
        prev = sec
    return out


def _wrap(text, font, size, width):
    lines, cur = [], ""
    for word in text.split(" "):
        while stringWidth(word, font, size) > width:       # a single unbroken token wider than the line
            k = len(word)
            while k > 1 and stringWidth(word[:k], font, size) > width:
                k -= 1
            if cur:
                lines.append(cur); cur = ""
            lines.append(word[:k]); word = word[k:]
        t = (cur + " " + word) if cur else word
        if cur and stringWidth(t, font, size) > width:
            lines.append(cur); cur = word
        else:
            cur = t
    if cur or not lines:
        lines.append(cur)
    return lines


def _layout(blocks):
    """-> list of pages; each page is a list of (font, size, leading, space_before, text) lines."""
    pages, page, y = [], [], TOP
    for blk in blocks:
        style, text = blk[0], blk[1]
        url = blk[2] if len(blk) > 2 else None
        font, size, lead, before = ST[style]
        lines = _wrap(text, font, size, W)
        need = (before if page else 0) + lead * min(len(lines), 2)    # keep at least 2 lines (or all of a 1-line block) together
        if style in ("sec", "item"):
            need += lead * 2                                           # a heading never ends a page alone
        if y - need < BOTTOM and page:
            pages.append(page); page, y = [], TOP
        for i, ln in enumerate(lines):
            b = before if (i == 0 and page) else 0
            if y - b - lead < BOTTOM and page:
                pages.append(page); page, y, b = [], TOP, 0
            page.append((font, size, lead, b, ln, url)); y -= b + lead
    if page or not pages:
        pages.append(page)
    return pages


def draw_blocks(blocks, out, title, footer_left):
    pages = _layout(blocks)
    c = rl_canvas.Canvas(out, pagesize=letter, pageCompression=0, invariant=0)
    c.setTitle(title); c.setAuthor("allNeurons Productivity")
    n = len(pages)
    for pno, lines in enumerate(pages, 1):
        t = c.beginText(M, TOP)
        cur = None
        first = True
        yb, links = TOP, []
        for font, size, lead, before, text, url in lines:
            if (font, size, lead) != cur:
                t.setFont(font, size, lead); cur = (font, size, lead)
            if before and not first:
                t.moveCursor(0, before)
            if not first:
                yb -= before + lead
            if url:                      # a real /URI link annotation over the whole line (never just coloured text)
                links.append((url, M, yb - 2.5, M + stringWidth(text, font, size), yb + size))
            t.textLine(text); first = False
        c.drawText(t)
        for url, x0, y0, x1, y1 in links:
            c.linkURL(url, (x0, y0, x1, y1), relative=0)
        c.setFont("Helvetica", 8.5)
        c.drawString(M, M - 14, footer_left)
        c.drawRightString(letter[0] - M, M - 14, "Page %d of %d" % (pno, n))
        c.showPage()
    c.save()
    d = open(out, "rb").read().replace(b"\x93\x8c\x8b\x9e", b"XXXX", 1)
    open(out, "wb").write(d)
    if os.environ.get("SUITE_PDF_MINIFY", "1") != "0":
        try:
            from pdf_minify import minify
            minify(out)
        except Exception as e:
            print("NOTE: pdf_minify skipped (%s: %s)" % (type(e).__name__, e), file=sys.stderr)
    return n


def draw(kind, data, out, part=None, of=None, us=None):
    us = us if us is not None else units(kind, data)
    blocks = blocks_for_part(us, part, of)
    foot = "allNeurons Productivity - compact format" + (" - part %d of %d" % (part, of) if part and of and of > 1 else "")
    title = str(data.get("title") or data.get("company") or "brief")
    return draw_blocks(blocks, out, title, foot)

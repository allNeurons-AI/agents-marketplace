"""Lite renderer -- the same payload as the full Daily Brief / Call Prep, drawn as plain flowing text.

Why it exists (v1.9.3): the Drive upload tools only accepts a file as text the model re-types into the call, and
a full-design PDF is 20-50 KB of drawing commands. A run that is stopped while writing that much text has delivered
nothing. The lite PDF carries the identical content in a fraction of the size (no cards, pills or rules), so it is the
fallback when the full file cannot be pasted. Used via SUITE_PDF_LITE=1 with suite_pdf_design.py; same JSON, same
format gate, same ASCII/uncompressed output as the full renderer.
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer


def _esc(s):
    return (str(s or "")).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_ST = {
    "title": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=18, leading=22, spaceAfter=4),
    "head": ParagraphStyle("h", fontName="Helvetica", fontSize=11.5, leading=15, spaceAfter=6),
    "sec": ParagraphStyle("s", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=10, spaceAfter=4),
    "item": ParagraphStyle("i", fontName="Helvetica-Bold", fontSize=10, leading=13, spaceBefore=5),
    "body": ParagraphStyle("b", fontName="Helvetica", fontSize=9.5, leading=12.5),
    "meta": ParagraphStyle("m", fontName="Helvetica-Oblique", fontSize=8.5, leading=11, textColor="#444444"),
}


def _P(text, st):
    return Paragraph(text, _ST[st])


def _item(it):
    out = []
    lead = it.get("action") or it.get("title") or it.get("body") or ""
    st = f' [{_esc(it["status"])}]' if it.get("status") else ""
    out.append(_P(f"{_esc(lead)}{st}", "item"))
    if it.get("title") and it.get("action") and it["title"] != it["action"]:
        out.append(_P(_esc(it["title"]), "body"))
    for k in ("body", "meta", "fix"):
        if it.get(k) and it.get(k) != lead:
            out.append(_P(("Suggested fix: " if k == "fix" else "") + _esc(it[k]), "body"))
    bits = [f"Owner: {_esc(it['owner'])}" if it.get("owner") else "",
            f"By: {_esc(it['by_when'])}" if it.get("by_when") else "",
            f"Source: {_esc(it['source'])}" if it.get("source") else ""]
    bits = [b for b in bits if b]
    if bits:
        out.append(_P(" | ".join(bits), "meta"))
    return out


def _section(story, title, items, empty):
    story.append(_P(f"{_esc(title)} ({len(items)})" if items else _esc(title), "sec"))
    if not items:
        story.append(_P(_esc(empty), "meta")); return
    for it in items:
        if isinstance(it, dict):
            story.extend(_item(it))
        else:
            story.append(_P(_esc(it), "body"))


def _brief(d, story):
    story.append(_P(_esc(d.get("title", "Daily Brief")), "title"))
    story.append(_P(_esc(d.get("headline", "")), "head"))
    st = d.get("stats") or {}
    if st:
        story.append(_P(_esc("  |  ".join(f"{k}: {v}" for k, v in st.items())), "meta"))
    story.append(_P("Today's meetings", "sec"))
    for m in d.get("meetings") or []:
        story.append(_P(f"<b>{_esc(m.get('label',''))}</b> - {_esc(m.get('who',''))} - {_esc(m.get('format',''))}", "body"))
    if not d.get("meetings"):
        story.append(_P("No meetings today.", "meta"))
    _section(story, "Needs attention", d.get("needs_attention") or [], "Nothing needs attention.")
    _section(story, "Conflicts", d.get("conflicts") or [], "No scheduling conflicts today.")
    _section(story, "Due today & overdue", d.get("due_today") or [], "Nothing due or overdue.")
    _section(story, "Worth double-checking", d.get("worth_double_checking") or [], "Nothing to double-check.")
    _section(story, "Resolved", d.get("resolved") or [], "Nothing resolved.")
    if d.get("sources"):
        story.append(_P("Sources", "sec"))
        for i, s in enumerate(d["sources"], 1):
            s = s if isinstance(s, dict) else {"label": s}
            story.append(_P(f"{i}. {_esc(s.get('label',''))}", "body"))


def _call_prep(d, story):
    story.append(_P("Call Prep - " + _esc(d.get("company", "")), "title"))
    story.append(_P(_esc(d.get("context", "")), "head"))
    story.append(_P(_esc(" | ".join(x for x in [d.get("time"), d.get("duration"), d.get("format"),
                                                 d.get("owner") and "Owner: " + d["owner"],
                                                 d.get("last_contact") and "Last contact: " + d["last_contact"]] if x)), "meta"))
    story.append(_P("Desired outcome: " + _esc(d.get("desired_outcome", "")), "body"))
    story.append(_P("Who you'll be speaking with", "sec"))
    for a in d.get("attendees") or []:
        story.append(_P(f"<b>{_esc(a.get('name'))}</b>, {_esc(a.get('title'))}, {_esc(a.get('company'))} - {_esc(a.get('body'))}", "body"))
    if d.get("absent_decision_maker"):
        story.append(_P("Not on the invite: " + _esc(d["absent_decision_maker"]), "body"))
    story.append(_P("What you need to know", "sec"))
    for x in d.get("what_you_need_to_know") or []:
        story.append(_P("- " + _esc(x.get("body")) + (f" [{_esc(x.get('source'))}]" if x.get("source") else ""), "body"))
    story.append(_P("What you should accomplish", "sec")); story.append(_P(_esc(d.get("objective", "")), "body"))
    story.append(_P("Questions to ask", "sec"))
    for i, q in enumerate(d.get("questions") or [], 1):
        story.append(_P(f"{i}. " + _esc(q if isinstance(q, str) else q.get("question") or q.get("body") or q), "body"))
    if d.get("risks"):
        story.append(_P("Risks to watch", "sec"))
        for x in d["risks"]:
            story.append(_P("- " + _esc(x.get("body")), "body"))
    if d.get("actions"):
        story.append(_P("Actions & owners", "sec"))
        for a in d["actions"]:
            story.append(_P(f"<b>{_esc(a.get('body'))}</b> - {_esc(a.get('owner'))} - {_esc(a.get('by_when'))} - {_esc(a.get('status'))}", "body"))
    story.append(_P("Sources", "sec"))
    for i, s in enumerate(d.get("sources") or [], 1):
        s = s if isinstance(s, dict) else {"label": s}
        story.append(_P(f"{i}. {_esc(s.get('label'))}", "body"))


def draw(kind, data, out):
    story = []
    (_brief if kind == "daily_brief" else _call_prep)(data, story)
    M = 54
    doc = BaseDocTemplate(out, pagesize=letter, leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M,
                          title=str(data.get("title") or data.get("company") or "brief"),
                          author="allNeurons Productivity", pageCompression=0)
    frame = Frame(M, M, letter[0] - 2 * M, letter[1] - 2 * M, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    from render_brief import make_canvas      # shared "Page X of Y" footer the format gate requires
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])
    doc.build(story, canvasmaker=make_canvas("allNeurons Productivity - lite format"))
    # pure 7-bit ASCII so it can be uploaded as plain text (see render_brief.make_ascii)
    d = open(out, "rb").read().replace(b"\x93\x8c\x8b\x9e", b"XXXX", 1)
    open(out, "wb").write(d)
    return doc.page

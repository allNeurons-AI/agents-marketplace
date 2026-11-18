#!/usr/bin/env python3
"""Compose and validate the plugin's emails deterministically .

Why this exists. ``outlook_send_mail`` (and some Gmail send tools) default ``bodyType`` to ``"text"``. A run that forgets to pass
``bodyType: "html"`` sends the whole formatted brief as one flat wall of tags, and a *scheduled* run, with nobody
steering it, forgot far more often than a manual one: the Daily Brief and Follow-Ups specs said "write the body as in
the format file" and never said how it had to be sent. Call Prep had been fixed for exactly this in v1.9.8; the other
two had not. The fix is to stop asking a model to re-derive the markup every morning:

  compose   builds the email from the same JSON the PDF is built from and prints the *exact* arguments for the send
            call, ``bodyType: "html"`` included, so a manual and a scheduled run send byte-identical structure;
  validate  refuses anything the sanitizer would flatten or that breaks the documented format (formatting
            regressions are caught before the send, not noticed by the customer after it);
  stored    reads back what Sent Items actually holds and detects a body that was stored as text.

Everything here is sanitizer-safe: only h3 p br hr strong em ul ol li table thead tbody tr th td a[href].

CLI
  email_compose.py compose  --kind daily_brief|follow_ups --in data.json [--out send.json]
  email_compose.py validate --kind ... --in send.json [--data data.json]
  email_compose.py stored   --in stored_body.txt
Exit: 0 ok · 2 unreadable input · 6 payload cannot be composed or fails validation (reasons on stderr)
"""
import argparse
import html as _html
import json
import os
import re
import sys

ALLOWED_TAGS = {"h3", "p", "br", "hr", "strong", "em", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td", "a"}
PLACEHOLDER = re.compile(r"\[[A-Za-z ]{2,24}\]|<date>|\bTBD\b|\bTODO\b|\bXX\b|insert\b.{0,20}\bhere", re.I)
NBSP4 = "&nbsp;" * 4
DOT = " · "


class ComposeError(Exception):
    pass


def esc(s):
    return _html.escape(str(s if s is not None else ""), quote=False)


def _plural(n, one, many):
    return one if n == 1 else many


def _fix_time(label):
    """'9:15 – 9:35 am' -> '9:15–9:35 am' (no spaces around the en dash, per the email format)."""
    return re.sub(r"\s*–\s*", "–", label.strip())


def _footer(version, address):
    return "<p><em>allNeurons Productivity v%s%sSent to %s</em></p>" % (esc(version), DOT, esc(address))


def _status_suffix(it):
    st = (it.get("status") or "").strip()
    return DOT + esc(st) if st and st.lower() != "open" else ""


# --------------------------------------------------------------------------------------------- daily brief
def _meeting_status(m):
    s = (m.get("status") or "").lower()
    if s:
        return s
    blob = ((m.get("format") or "") + " " + (m.get("label") or "")).lower()
    return "canceled" if "cancel" in blob else ("passed" if "passed" in blob else "upcoming")


def _meeting_rows(meetings):
    order = {"upcoming": 0, "passed": 1, "canceled": 2}
    rows = []
    for i, m in enumerate(meetings):
        lab = m.get("label") or ""
        time_, _, title = lab.partition("—")
        if not _:
            time_, title = "%s–%s" % (m.get("start", ""), m.get("end", "")), lab
        st = _meeting_status(m)
        det = DOT.join(x for x in [m.get("who"), re.sub(r"\s*\((already passed|canceled)\)", "", m.get("format") or "",
                                                           flags=re.I), {"passed": "already passed", "canceled": "canceled"}.get(st)] if x)
        rows.append((order.get(st, 0), i, "<tr><td><strong>%s</strong>%s</td><td>%s%s</td></tr>" % (
            esc(_fix_time(time_)), NBSP4, esc(title.strip()), ("<br><em>%s</em>" % esc(det)) if det else "")))
    return "\n".join(r for _, _, r in sorted(rows))


def _action_li(it):
    action = it.get("action") or it.get("title") or ""
    title, body = it.get("title"), it.get("body")
    lead = (esc(title.rstrip(".")) + ". ") if (title and it.get("action")) else ""
    detail = (lead + esc(" ".join(x for x in [body, it.get("meta"), it.get("fix") and "Suggested fix: " + it["fix"]] if x))).strip()
    meta = DOT.join(esc(x) for x in [("Owner: " + it["owner"]) if it.get("owner") else "", it.get("by_when"), it.get("source")] if x)
    return "<li><p><strong>→ %s</strong>%s<br>\n<em>%s%s</em></p></li>" % (
        esc(action), ("<br>\n" + detail) if detail else "", meta, _status_suffix(it))


def _note_li(it):
    return "<li><p><em>%s</em></p></li>" % esc(it.get("body") or it.get("title") or "")


def _plain_li(it):
    t, b = it.get("title"), it.get("body")
    return "<li>%s</li>" % (esc(t) + (": " if t and b else "") + esc(b))


def compose_daily_brief(d):
    """-> (subject, html). ``d`` is the brief payload plus d['delivery'] = {filename, link, pages, parts, address,
    version}."""
    dl = d.get("delivery") or {}
    for k in ("address", "version"):
        if not dl.get(k):
            raise ComposeError("delivery.%s is required" % k)
    st = d.get("stats") or {}
    na, nc, nd, nr = (int(st.get(k, 0) or 0) for k in ("Needs attention", "Conflicts", "Due today & overdue", "Resolved"))
    na_items = d.get("needs_attention") or []
    real = lambda arr: [i for i in arr if not i.get("informational")]
    subject = d["title"]
    if not subject.lower().startswith("daily brief"):
        subject = "Daily Brief — " + subject
    out = ["<h3>%s</h3>" % esc(d["headline"])]
    b = lambda n, txt: ("<strong>%s</strong>" if n else "%s") % txt   # only non-zero counts are bold
    stat = [b(na, "1 needs attention" if na == 1 else "%d need attention" % na),
            b(nc, "%d %s" % (nc, _plural(nc, "conflict", "conflicts"))),
            b(nd, "%d due" % nd), b(nr, "%d resolved" % nr)]
    out += ["<p>%s</p>" % DOT.join(stat), "<hr>", "<h3>Today's meetings</h3>"]
    ms = d.get("meetings") or []
    out.append("<table>\n%s\n</table>" % _meeting_rows(ms) if ms else "<p>No meetings on the calendar today.</p>")
    if na_items:
        out += ["<h3>Needs attention (%d)</h3>" % len(real(na_items)), "<ol>", *[_action_li(i) for i in real(na_items)], "</ol>"]
    fold = []
    for key, label, empty in (("conflicts", "Conflicts", "No scheduling conflicts today."),
                              ("due_today", "Due today & overdue", "Nothing due today and nothing overdue.")):
        items = real(d.get(key) or [])
        if items:
            out += ["<h3>%s (%d)</h3>" % (esc(label), len(items)), "<ol>", *[_action_li(i) for i in items], "</ol>"]
        else:
            fold.append(empty)
    if fold:
        out.append("<p>%s</p>" % esc(DOT.join(fold)))
    wdc = d.get("worth_double_checking") or []
    if wdc:
        n = len(real(wdc))
        out += ["<h3>Worth double-checking (%d)</h3>" % n, "<ul>",
                *[_note_li(i) if i.get("informational") else _action_li(i) for i in wdc], "</ul>"]
    res = d.get("resolved") or []
    if res:
        out += ["<h3>Resolved (%d)</h3>" % len(res), "<ul>", *[_plain_li(i) for i in res], "</ul>"]
    out.append("<hr>")
    parts = dl.get("parts") or []
    if parts:
        out.append("<p>The brief is in %d parts; every part is complete.</p>" % len(parts))
        for p in parts:
            out.append('<p>Part %d of %d: <a href="%s">%s</a></p>' % (p["k"], len(parts), esc(p["link"]), esc(p["filename"])))
    elif dl.get("link"):
        pg = (" (%d pages)" % dl["pages"]) if dl.get("pages", 1) and dl.get("pages", 1) > 1 else ""
        out.append('<p>Full brief%s: <a href="%s">%s</a></p>' % (pg, esc(dl["link"]), esc(dl["filename"])))
    else:
        raise ComposeError("delivery.link (or delivery.parts) is required: the email only goes out after the upload "
                           "was read back (run-policy section 5); for the inline fallback use compose with "
                           "delivery.inline=true")
    out += [_footer(dl["version"], dl["address"])]
    return subject, "\n".join(x for x in out if x)


def compose_clear_day(d):
    dl = d["delivery"]
    body = ("<p>Clear day — no meetings, nothing due, no open asks.</p>\n"
            "<p><em>allNeurons Productivity v%s%sSent to %s</em></p>" % (esc(dl["version"]), DOT, esc(dl["address"])))
    return d["title"], body


# ------------------------------------------------------------------------------------------------ follow-ups
def compose_follow_ups(d):
    dl = d.get("delivery") or {}
    for k in ("address", "version"):
        if not dl.get(k):
            raise ComposeError("delivery.%s is required" % k)
    date = d["date"]
    still, new, needs = d.get("still_open") or [], d.get("new_drafts") or [], d.get("needs_input") or []
    n_created = sum(1 for i in new if i.get("drafted", True))
    n_flag = sum(1 for i in new if not i.get("drafted", True)) + len(needs)
    n_open = len(still)
    ver = _footer(dl["version"], dl["address"])
    if not (n_created or n_open or n_flag):
        body = ("<p>%s</p>\n%s" % (esc(d.get("early_exit") or "Checked %s threads over %s days. Nothing needs a follow-up "
                                          "today. No drafts created." % (d.get("threads", 0), d.get("days", 10))),
                ver)).replace("\n\n", "\n")
        return "Follow-ups checked — nothing open · %s" % date, body
    subject = "Follow-ups ready for review — %d new, %d awaiting send, %d flagged · %s" % (n_created, n_open, n_flag, date)
    cov = d["coverage"].rstrip()
    nsig = int(d.get("signature_image_missing") or 0)
    if nsig:
        cov = cov.rstrip(".") + ". Signature image not included in %d %s (the draft tools cannot carry images; signature text kept)." % (
            nsig, _plural(nsig, "draft", "drafts"))
    out = ["<p><em>%s</em></p>" % esc(cov), "<hr>"]
    if still:
        out += ["<h3>Still open (%d)</h3>" % n_open, "<ol>"]
        for i in still:
            out.append("<li><p><strong>→ %s — %s</strong><br>\n%s<br>\n<em>drafted %s · still unsent · %s business days · %s</em></p></li>" % (
                esc(i["contact"]), esc(i["topic"]), esc(i["reason"]), esc(i["drafted_on"]), esc(i["age_days"]),
                esc(i["priority"])))
        out.append("</ol>")
    if new:
        out += ["<h3>New drafts (%d)</h3>" % len(new), "<ol>"]
        for i in new:
            drafted = i.get("drafted", True)
            meta = ("%s · reply on the %s thread" % (i["priority"], i["thread"])) if drafted else \
                   ("%s · not drafted this run, draft cap reached" % i["priority"])
            out.append("<li><p><strong>%s%s — %s</strong><br>\n%s<br>\n<em>%s</em></p></li>" % (
                "→ " if drafted else "", esc(i["contact"]), esc(i["topic"]), esc(i["reason"]), esc(meta)))
        out.append("</ol>")
    if needs:
        out += ["<h3>Needs your input (%d)</h3>" % len(needs), "<ul>"]
        for i in needs:
            out.append("<li><p><strong>%s — %s</strong><br>\n%s<br>\nNext: %s<br>\n<em>Not drafted · %s · %s</em></p></li>" % (
                esc(i["contact"]), esc(i["topic"]), esc(i["what"]), esc(i["next"]), esc(i["reason"]), esc(i["status"])))
        out.append("</ul>")
    out.append("<hr>")
    out.append("<p><strong>Nothing has been sent.</strong>%s</p>" % (" Review, edit and send the drafts from your Drafts folder." if n_created or n_open else ""))
    out += [ver]
    return subject, "\n".join(x for x in out if x)


# ------------------------------------------------------------------------------------ competitive insights
def _words(t):
    return len(str(t or "").split())


def compose_competitive(d):
    """-> (subject, html). The email is the short version of the report:
         Executive summary: a one-line bottom line, then WHAT MATTERS THIS WEEK AND WHY for every company in the group
                            (named, with the competitors looked at for it), so the reader knows what each point is about.
         Competitive threats: succinct, one line each (company, level, what); the detail stays in the PDF.
       d: {week, summary{bottom_line, companies[{name, competitors[], matters, why}]}, threats[{company, level, title, line}],
           delivery{filename, link, pages, address, version, attached?, folder?}}
       The email opens with where the PDF is and how to open it (attached, or a link: nothing is attached), then the two sections."""
    dl = d.get("delivery") or {}
    for k in ("address", "version", "link", "filename"):
        if not dl.get(k):
            raise ComposeError("delivery.%s is required (the email goes out only after the upload was read back)" % k)
    sm = d.get("summary") or {}
    if not str(sm.get("bottom_line") or "").strip():
        raise ComposeError("summary.bottom_line is required: one sentence with the week's headline")
    comps = [c for c in (sm.get("companies") or []) if isinstance(c, dict) and str(c.get("name") or "").strip()]
    if not comps:
        raise ComposeError("summary.companies must name every company in the group with what matters this week and why")
    for c in comps:
        for k in ("matters", "why"):
            if not str(c.get(k) or "").strip():
                raise ComposeError("summary.companies[%s].%s is required" % (c["name"], k))
            if _words(c[k]) > 45:
                raise ComposeError("summary.companies[%s].%s is %d words; keep it to 45 or fewer (the PDF holds the detail)" % (c["name"], k, _words(c[k])))
    thr = [t for t in (d.get("threats") or []) if isinstance(t, dict)]
    if len(thr) > 6:
        raise ComposeError("threats: at most 6 lines in the email (the PDF holds the rest); got %d" % len(thr))
    for t in thr:
        if not str(t.get("title") or "").strip():
            raise ComposeError("every threat needs a title")
        if _words(t.get("line")) > 28:
            raise ComposeError("threat lines must be succinct: %d words, maximum 28" % _words(t.get("line")))
    pg = (" (%d pages)" % dl["pages"]) if dl.get("pages", 1) and dl.get("pages", 1) > 1 else ""
    folder = str(dl.get("folder") or "Skills/Competitive Insights")
    # v1.15.0: the first thing in the email says where the PDF is and how to open it, so nobody has to hunt for it.
    if dl.get("attached"):
        how = ("The PDF is attached to this email: open the attachment, or use the link above. "
               "A copy is also saved in your Drive folder %s.") % esc(folder)
    else:
        how = ("Click the link above to open the PDF in your browser; "
               "choose Download there to save a copy in your local folder. It is saved in your Drive folder %s.") % esc(folder)
    out = ['<p><strong>Your report is a PDF%s: <a href="%s">%s</a></strong></p>' % (pg, esc(dl["link"]), esc(dl["filename"])),
           "<p>%s</p>" % how, "<hr>",
           "<h3>Executive summary</h3>", "<p><strong>%s</strong></p>" % esc(sm["bottom_line"]), "<ul>"]
    for c in comps:
        tracked = [str(x) for x in (c.get("competitors") or []) if str(x).strip()]
        out.append("<li><strong>%s</strong>%s: %s <em>Why it matters:</em> %s</li>" % (
            esc(c["name"]), (" (looked at: %s)" % esc(", ".join(tracked))) if tracked else "", esc(c["matters"]), esc(c["why"])))
    out.append("</ul>")
    out.append("<h3>Competitive threats</h3>")
    if thr:
        order = {"High": 0, "Medium": 1, "Low": 2}
        out.append("<ul>")
        for t in sorted(thr, key=lambda t: order.get(t.get("level"), 3)):
            out.append("<li><strong>%s</strong>%s: %s%s</li>" % (
                esc(t.get("level") or ""), (" | " + esc(t["company"])) if t.get("company") else "", esc(t["title"]),
                (" " + esc(t["line"])) if str(t.get("line") or "").strip() else ""))
        out.append("</ul>")
    else:
        out.append("<p>No competitive threats this week.</p>")
    out += ["<hr>", '<p>The full report, with the detail for every company, is in the PDF: <a href="%s">%s</a></p>' % (esc(dl["link"]), esc(dl["filename"])),
            _footer(dl["version"], dl["address"])]
    return "Competitive Intelligence Report — Week of %s" % d["week"], "\n".join(x for x in out if x)


def compose_failure(d):
    """The one [Failed] email (run-policy section 12): which skill and when, what was done, the verbatim error, what it
    means, what to do next. d: {skill, short, when, did, error, meaning, next, delivery{address, version}}"""
    dl = d.get("delivery") or {}
    for k in ("skill", "short", "when", "error", "meaning"):
        if not str(d.get(k) or "").strip():
            raise ComposeError("failure.%s is required" % k)
    for k in ("address", "version"):
        if not dl.get(k):
            raise ComposeError("delivery.%s is required" % k)
    out = ["<h3>%s did not finish</h3>" % esc(d["skill"]), "<p><strong>%s</strong>%s</p>" % (esc(d["when"]), (" " + esc(d["did"])) if d.get("did") else ""),
           "<p>Error, verbatim:<br>%s</p>" % esc(d["error"]), "<p>%s</p>" % esc(d["meaning"])]
    if d.get("next"):
        out.append("<p><strong>Next:</strong> %s</p>" % esc(d["next"]))
    out.append(_footer(dl["version"], dl["address"]))
    return "[Failed] %s — %s" % (d["skill"], d["short"]), "\n".join(out)


COMPOSERS = {"daily_brief": compose_daily_brief, "follow_ups": compose_follow_ups, "competitive": compose_competitive,
             "failure": compose_failure}


def send_args(kind, data):
    """The exact argument object for the mail send tool (outlook_send_mail / the Gmail send tool). bodyType is always html: that is the whole point."""
    if kind == "daily_brief" and data.get("clear_day"):
        subject, body = compose_clear_day(data)
    else:
        subject, body = COMPOSERS[kind](data)
    addr = data["delivery"]["address"]
    return {"to": [addr], "subject": subject, "body": body, "bodyType": "html"}


# --------------------------------------------------------------------------------------------------- validation
_TAG = re.compile(r"<\s*(/?)\s*([a-zA-Z0-9]+)([^>]*)>")


def validate_html(body):
    errs = []
    for m in _TAG.finditer(body):
        tag, attrs = m.group(2).lower(), m.group(3)
        if tag not in ALLOWED_TAGS:
            errs.append("tag <%s> is stripped by the send tool's sanitizer" % tag)
        elif tag == "a":
            if not m.group(1) and not re.fullmatch(r'\s+href="[^"]+"\s*', attrs):
                errs.append("<a> may carry only href")
        elif attrs.strip().rstrip("/").strip():
            errs.append("<%s> carries attributes (%s); only href survives" % (tag, attrs.strip()[:30]))
    stripped = re.sub(r"<a [^>]*>.*?</a>", "", body, flags=re.S)
    if re.search(r"https?://", _html.unescape(re.sub(r"<[^>]+>", " ", stripped))):
        errs.append("a raw URL is visible in the text; links must be anchors with a label")
    if PLACEHOLDER.search(re.sub(r"<[^>]+>", " ", body)):
        errs.append("a placeholder survived (%s)" % PLACEHOLDER.search(re.sub(r"<[^>]+>", " ", body)).group(0))
    if re.search(r"—\s*</h3>", body):
        errs.append("a heading ends on a dangling dash")
    if "‘" in body and "’" not in body:
        errs.append("unbalanced quote")
    return errs


def validate_send(kind, args, data=None):
    errs = []
    if args.get("bodyType") != "html":
        errs.append('bodyType is %r: the send tool defaults to text, which flattens the whole email; it must be "html"' % args.get("bodyType"))
    body = args.get("body") or ""
    if not body.lstrip().startswith("<"):
        errs.append("the body does not start with an HTML element")
    if args.get("bodyType") == "html" and body != body.lstrip():
        errs.append("the body starts with whitespace")
    errs += validate_html(body)
    if len(args.get("to") or []) != 1:
        errs.append("exactly one recipient (the signed-in user) is allowed; got %d" % len(args.get("to") or []))
    if args.get("cc") or args.get("bcc"):
        errs.append("no cc or bcc, ever")
    ver = re.search(r"allNeurons Productivity v[\d.]+ · Sent to \S+", re.sub(r"<[^>]+>", "", body))
    if not ver:
        errs.append("closing line 'allNeurons Productivity v<version> · Sent to <address>' is missing")
    if kind == "failure" and not str(args.get("subject", "")).startswith("[Failed]"):
        errs.append("a failure email's subject must start with [Failed]")
    if kind == "competitive":
        if not re.search(r'<a href="https://[^"]+">[^<]+\.pdf</a>', body):
            errs.append("the verified PDF link is missing from the email")
        h3s = re.findall(r"<h3>(.*?)</h3>", body, flags=re.S)
        if h3s[:2] != ["Executive summary", "Competitive threats"]:
            errs.append("the email must hold the sections Executive summary then Competitive threats, in that order")
    if kind == "daily_brief" and not (data or {}).get("clear_day"):
        errs += _validate_daily(body, data)
    if kind == "follow_ups":
        errs += _validate_follow_ups(args, body)
    return errs


def _count_li(block):
    return len(re.findall(r"<li>", block))


def _validate_daily(body, data):
    errs = []
    h3 = re.findall(r"<h3>(.*?)</h3>", body, flags=re.S)
    if not body.lstrip().startswith("<h3>"):
        errs.append("the email must open on the headline <h3> (no date line)")
    if "Today's meetings" not in h3:
        errs.append("the Today's meetings section is missing")
    elif h3.index("Today's meetings") != 1:
        errs.append("Today's meetings must be the first section after the headline")
    if data is not None and data.get("meetings"):
        rows = len(re.findall(r"<tr>", body))
        if rows != len(data["meetings"]):
            errs.append("calendar line: %d meetings in the brief but %d rows in the email" % (len(data["meetings"]), rows))
    if not re.search(r"<p>(<strong>)?\d+ needs? attention", body):
        errs.append("the stat line is missing or out of order")
    for m in re.finditer(r"<h3>([^<]*?) \((\d+)\)</h3>\s*<(ol|ul)>(.*?)</\3>", body, flags=re.S):
        if _count_li(m.group(4)) != int(m.group(2)):
            errs.append("section %r says %s but lists %d" % (m.group(1), m.group(2), _count_li(m.group(4))))
    for m in re.finditer(r"<li><p><strong>(.*?)</strong>", body):
        if not m.group(1).startswith("→"):
            errs.append("an action does not start with the arrow marker")
    if not re.search(r'<p>(Full brief|The brief is in)', body) or not re.search(r'<a href="https://', body):
        errs.append("the delivery line with a verified https link is missing")
    return errs


def _validate_follow_ups(args, body):
    errs = []
    subj = args.get("subject") or ""
    m = re.match(r"Follow-ups ready for review — (\d+) new, (\d+) awaiting send, (\d+) flagged", subj)
    if m:
        n, mm, p = map(int, m.groups())
        def sect(name):
            r = re.search(r"<h3>%s \((\d+)\)</h3>\s*<(?:ol|ul)>(.*?)</(?:ol|ul)>" % name, body, flags=re.S)
            return (int(r.group(1)), _count_li(r.group(2)), r.group(2)) if r else (0, 0, "")
        so, nw, ni = sect("Still open"), sect("New drafts"), sect("Needs your input")
        if so[0] != so[1] or nw[0] != nw[1] or ni[0] != ni[1]:
            errs.append("a section heading count does not match its list")
        if so[1] != mm:
            errs.append("subject says %d awaiting send, body lists %d" % (mm, so[1]))
        drafted = len(re.findall(r"<li><p><strong>→", nw[2]))
        if drafted != n:
            errs.append("subject says %d new, body lists %d drafted" % (n, drafted))
        if (nw[1] - drafted) + ni[1] != p:
            errs.append("subject says %d flagged, body lists %d" % (p, (nw[1] - drafted) + ni[1]))
        if "<em>" not in body.split("</p>", 1)[0]:
            errs.append("the body must open on the italic coverage line")
        if "Nothing has been sent." not in body:
            errs.append("the closing line must say nothing has been sent")
    return errs


def stored_body_ok(stored, content_type=None):
    """Read-back check on what Sent Items holds. ``content_type`` is the body contentType the read-back reports, when it
    does. A brief stored as text shows its own tags (or escaped tags) as visible characters; a real HTML body does not."""
    errs = []
    s = stored or ""
    if (content_type or "").lower() == "text" and re.search(r"</?(p|h3|em|strong|li|ul|ol|table|tr|td|br)\b", s, re.I):
        errs.append("the stored body is contentType text but contains markup: it was sent without bodyType html")
    if re.search(r"&lt;\s*/?\s*(p|h3|em|strong|li|ul|ol|br)\b", s, re.I):
        errs.append("the stored body shows escaped markup as visible text")
    if s and "<h3" not in s and "<b>" not in s and "<br><br>" not in s and "\n\n" not in s and len(s) > 400:
        errs.append("the stored body is one flat block with no structure")
    return errs


# --------------------------------------------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compose"); c.add_argument("--kind", required=True, choices=list(COMPOSERS)); c.add_argument("--in", dest="inp", required=True); c.add_argument("--out")
    v = sub.add_parser("validate"); v.add_argument("--kind", required=True, choices=list(COMPOSERS)); v.add_argument("--in", dest="inp", required=True); v.add_argument("--data")
    s = sub.add_parser("stored"); s.add_argument("--in", dest="inp", required=True); s.add_argument("--content-type")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "stored":
            errs = stored_body_ok(open(a.inp, encoding="utf-8").read(), a.content_type)
            print(json.dumps({"ok": not errs, "problems": errs}))
            return 0 if not errs else 6
        data = json.load(open(a.inp, encoding="utf-8"))
    except Exception as e:
        print("INPUT ERROR: %s" % e, file=sys.stderr)
        return 2
    try:
        if a.cmd == "compose":
            args = send_args(a.kind, data)
            errs = validate_send(a.kind, args, data)
            if errs:
                raise ComposeError("; ".join(errs))
            txt = json.dumps(args, ensure_ascii=False)
            if a.out:
                open(a.out, "w", encoding="utf-8").write(txt)
            print(txt)
        else:
            errs = validate_send(a.kind, data, json.load(open(a.data)) if a.data else None)
            print(json.dumps({"ok": not errs, "problems": errs}))
            return 0 if not errs else 6
    except ComposeError as e:
        print("FORMAT ERROR: %s" % e, file=sys.stderr)
        return 6
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Compose the Call Prep card and audit the briefing link in the *stored* notes ().

The defect: the briefing PDF was rendered and uploaded, but the calendar block's notes did not end up holding a working
link to it (the link was left out of the body, was replaced by a local path, or an update overwrote the body without
it) and nothing checked the event as stored. Two deterministic steps close that:

  compose   builds the card HTML from the payload and the *verified* webUrl, so the link is part of the body by
            construction, and prints the exact create/update arguments (``bodyType: "html"`` included for Outlook; ``--target google`` returns the
            ``description`` in the small HTML subset Google Calendar renders);
  audit     takes the body read back from the calendar event and the verified webUrl and fails unless the stored notes
            hold a clickable link to exactly that URL, the filename as its text, the ``ref:`` line last, and no visible
            markup. A card booked without a link (the upload really failed) must say so and carry no fake link.

The caller repairs a failed audit by updating the same event once (same call key, same ``ref:``), re-reads it, and
reports ``[Failed]`` if the second read-back still fails. Stdlib only; reuses email_compose's sanitizer-safe validator.

CLI  call_prep_card.py compose --in card.json [--out event.json] [--target outlook|google]
     call_prep_card.py audit   --body stored.html --url <webUrl> [--filename x.pdf] [--call-key K] [--content-type html] [--version 1.15.0]
Exit 0 ok · 2 unreadable input · 6 card cannot be composed / audit failed (reasons on stderr)
"""
import argparse
import html as _html
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import email_compose as ec  # noqa: E402

DOT = " · "
LOCAL = re.compile(r"^(file:|/|[A-Za-z]:\\|computer:|sandbox:|\.{1,2}/)", re.I)


class CardError(Exception):
    pass


def _src(s):
    return (" <em>[%s]</em>" % ec.esc(s)) if s else ""


def verified_url(url):
    """True only for an absolute https URL that is not a local, sandbox or placeholder path."""
    if not url or LOCAL.match(url.strip()):
        return False
    p = urllib.parse.urlparse(url.strip())
    return p.scheme == "https" and bool(p.netloc) and "." in p.netloc


VERSION_LINE = re.compile(r"allNeurons Productivity v(\S+)")


def _version(c):
    """The installed plugin version the run confirmed in step 2a (`1.15.0`, or `(unknown)` when plugin.json was unreadable)."""
    v = str(c.get("version") or "").strip().lstrip("vV")
    if not v:
        raise CardError("card.version is required: the installed plugin version (shared section 1 step 2a), e.g. 1.15.0, or (unknown)")
    return v


def to_google(body):
    """Google Calendar renders only a small HTML subset in an event description (b, i, u, br, a, ul, ol, li). Map the card's
    sanitizer-safe tags onto it: headings become bold lines, paragraphs become lines, strong/em become b/i."""
    s = body
    s = re.sub(r"<h3>(.*?)</h3>", r"<b>\1</b><br>", s, flags=re.S)
    s = re.sub(r"<li><p>(.*?)</p></li>", r"<li>\1</li>", s, flags=re.S)
    s = re.sub(r"<p>(.*?)</p>", r"\1<br>", s, flags=re.S)
    s = s.replace("<hr>", "<br>").replace("<strong>", "<b>").replace("</strong>", "</b>").replace("<em>", "<i>").replace("</em>", "</i>")
    s = re.sub(r"\n+", "", s)
    return s


def compose(c, target="outlook"):
    for k in ("header1", "header2", "open_with", "call_key"):
        if not c.get(k):
            raise CardError("card.%s is required" % k)
    ver = _version(c)
    out = ["<h3>%s</h3>" % ec.esc(c["header1"]), "<p><strong>%s</strong></p>" % ec.esc(c["header2"]), "<hr>"]
    if c.get("overlay_note"):
        out.append("<p><em>%s</em></p>" % ec.esc(c["overlay_note"]))
    byj = c.get("before_you_join") or []
    if byj:
        out += ["<h3>Before you join</h3>", "<ul>"] + ["<li><p>%s%s</p></li>" % (ec.esc(i["fact"]), _src(i.get("source"))) for i in byj[:2]] + ["</ul>"]
    mv = c.get("your_move") or []
    if mv:
        out += ["<h3>Your move</h3>", "<ul>"] + ["<li><p><strong>→ %s</strong>%s</p></li>" % (ec.esc(i["text"]), _src(i.get("source"))) for i in mv] + ["</ul>"]
    out += ["<h3>Open with</h3>", "<p><em>\"%s\"</em></p>" % ec.esc(c["open_with"].strip('"“”'))]
    if c.get("ask"):
        out += ["<h3>Ask</h3>", "<p>%s</p>" % ec.esc(c["ask"])]
    out.append("<hr>")
    url, name = c.get("link"), c.get("filename") or "briefing.pdf"
    if verified_url(url):
        out.append('<p>Full briefing: <a href="%s">%s</a></p>' % (ec.esc(url.strip()), ec.esc(name)))
    elif url:
        raise CardError("card.link %r is not a verified https URL (never a local or sandbox path)" % url[:80])
    else:
        out.append("<p>Full briefing: could not be linked this run. The PDF is saved in this run's Outputs as %s.</p>" % ec.esc(name))
    out.append("<p><em>allNeurons Productivity v%s</em></p>" % ec.esc(ver))              # the skill version, on every prep block
    out.append("<p><em>ref: call-prep/%s</em></p>" % ec.esc(c["call_key"]))
    body = "\n".join(out)
    errs = ec.validate_html(re.sub(r"<em>\[[^\]]*\]</em>", "", body))   # bracketed sources are the format, not placeholders
    if errs:
        raise CardError("; ".join(errs))
    words = len(re.sub(r"<[^>]+>", " ", body).split())
    if words > 230:
        raise CardError("card is %d words; the format caps it near 200" % words)
    if target == "google":
        return {"subject": c.get("subject"), "description": to_google(body), "target": "google"}
    return {"subject": c.get("subject"), "body": body, "bodyType": "html"}


def _hrefs(body):
    return [_html.unescape(h) for h in re.findall(r'<a\b[^>]*\bhref=["\']([^"\']+)["\']', body or "", re.I)]


def _same_url(a, b):
    na, nb = urllib.parse.urlparse(a), urllib.parse.urlparse(b)
    return (na.netloc.lower(), urllib.parse.unquote(na.path), na.query) == (nb.netloc.lower(), urllib.parse.unquote(nb.path), nb.query)


def audit(body, url, filename=None, call_key=None, content_type=None, version=None):
    """Problems with the notes as stored on the calendar event ([] = the link and the format are really there)."""
    errs = []
    body = body or ""
    if not verified_url(url):
        errs.append("no verified briefing URL was supplied to audit against")
    errs += ec.stored_body_ok(body, content_type)
    links = _hrefs(body)
    if verified_url(url):
        if not any(_same_url(h, url) for h in links):
            errs.append("the stored notes do not contain a link to the uploaded briefing (%s)" % url[:90])
        if any(LOCAL.match(h) for h in links):
            errs.append("the stored notes contain a local or sandbox path as a link")
        if filename:
            m = re.search(r'<a\b[^>]*href=["\'][^"\']*["\'][^>]*>(.*?)</a>', body, re.I | re.S)
            texts = [re.sub(r"<[^>]+>", "", t).strip() for t in re.findall(r"<a\b[^>]*>(.*?)</a>", body, re.I | re.S)]
            if filename not in texts:
                errs.append("the briefing link text is not the filename %r" % filename)
    plain = _html.unescape(re.sub(r"<[^>]+>", "\n", body)).strip()
    lines = [l.strip() for l in plain.split("\n") if l.strip()]
    if call_key:
        want = "ref: call-prep/%s" % call_key
        if not lines or lines[-1] != want:
            errs.append("the last line of the stored notes is not %r" % want)
    m = VERSION_LINE.search(plain)
    if not m:
        errs.append("the stored notes carry no 'allNeurons Productivity v<version>' line (the skill version belongs on every prep block)")
    elif version and m.group(1).rstrip(".") != str(version).lstrip("vV"):
        errs.append("the stored notes name version %s, not the installed %s" % (m.group(1), str(version).lstrip("vV")))
    if verified_url(url) and re.search(r"could not be linked", body, re.I):
        errs.append("the notes say the briefing could not be linked although a verified URL exists")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compose"); c.add_argument("--in", dest="inp", required=True); c.add_argument("--out"); c.add_argument("--target", choices=("outlook", "google"), default="outlook")
    a_ = sub.add_parser("audit"); a_.add_argument("--body", required=True); a_.add_argument("--url", required=True)
    a_.add_argument("--filename"); a_.add_argument("--call-key"); a_.add_argument("--content-type"); a_.add_argument("--version")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "compose":
            data = json.load(open(a.inp, encoding="utf-8"))
        else:
            body = open(a.body, encoding="utf-8").read()
    except Exception as e:
        print("INPUT ERROR: %s" % e, file=sys.stderr)
        return 2
    if a.cmd == "compose":
        try:
            res = compose(data, a.target)
        except (CardError, KeyError) as e:
            print("CARD ERROR: %s" % e, file=sys.stderr)
            return 6
        txt = json.dumps(res, ensure_ascii=False)
        (open(a.out, "w", encoding="utf-8").write(txt) if a.out else print(txt))
        return 0
    errs = audit(body, a.url, a.filename, a.call_key, a.content_type, a.version)
    for e in errs:
        print("LINK AUDIT: " + e, file=sys.stderr)
    print(json.dumps({"ok": not errs, "problems": errs}))
    return 6 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

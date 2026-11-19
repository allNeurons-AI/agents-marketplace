"""Clean and verify Follow-Up drafts (leading whitespace, signature image).

. Drafts came out indented: a blank first paragraph, a stray ``<br>``, ``&nbsp;`` or a space run before the
greeting. ``sanitize`` removes all of that from the start of the body and from the start of every line, for both text
and HTML bodies, and never touches the middle of a sentence. ``check`` is the gate run on the *final* draft (the one
read back from the Drafts folder), so the fix is verified on the artifact the person sees, not on the text the model
meant to write.

. The signature of a sent email can hold an image (logo, handwritten name, banner). The draft tools reject
``<img>``, ``span``, ``font`` and ``blockquote`` outright (they error, they do not strip), so a draft that pastes the
signature as HTML either fails or silently loses the image. The rule is therefore:

  * ``signature`` splits the user's own sent mail into the signature *text* (kept verbatim) and its *images*;
  * the draft is written with the text only, and ``check`` reports ``signature image not included`` unless the image
    was attached by some other route (the plugin ships none: the summary reports it once);
  * the signature text is never altered to make room for the image, and ``check`` fails a draft whose signature text
    is missing or changed.

Stdlib only.
CLI
  draft_sanitize.py sanitize  --in draft.txt [--out clean.txt]
  draft_sanitize.py check      --in final_draft.txt [--signature-text sig.txt] [--image-expected] [--image-attached]
  draft_sanitize.py signature  --in sent_mail.html            # prints {"text": ..., "images": [...]} as JSON
Exit: 0 ok · 2 unreadable input · 6 problems found (one per line on stderr)
"""
import argparse
import html as _html
import json
import re
import sys

_ZW = "​‌‍⁠﻿"
_WS = r"[ \t\r\n   　" + _ZW + r"]"
_HAS_HTML = re.compile(r"</?(p|div|br|span|table|ul|ol|li|h[1-6]|strong|em|b|i|a|img|blockquote|font)\b", re.I)
_EMPTY_BLOCK = re.compile(r"^(?:\s|&nbsp;|&#160;|<br\s*/?>)*$", re.I)
_BAD_TAGS = re.compile(r"<\s*(img|span|font|blockquote|script|style)\b", re.I)
_EM_DASH = "—"
_PLACEHOLDER = re.compile(r"\[(?:name|date|company|your [a-z ]+|insert[^\]]*|tbd)\]|<name>|\bTODO\b|\bXXX\b|\{\{[^}]*\}\}", re.I)
_SIG_MARKER = re.compile(r"(?:id|class)=[\"'](?:[^\"']*\b)?(?:x_)?(?:divtagdefaultwrapper|signature|ms-outlook-mobile-signature|"
                         r"outlook-signature|gmail_signature)\b[^\"']*[\"']", re.I)


def is_html(body):
    return bool(_HAS_HTML.search(body or ""))


def _strip_leading_html(body):
    """Drop empty leading blocks (<p></p>, <p>&nbsp;</p>, <div><br></div>, bare <br>) and whitespace, repeatedly."""
    prev = None
    while prev != body:
        prev = body
        body = re.sub(r"^" + _WS + r"+", "", body)
        body = re.sub(r"^(?:<br\s*/?>)+", "", body, flags=re.I)
        body = re.sub(r"^&nbsp;|^&#160;", "", body, flags=re.I)
        m = re.match(r"^<(p|div|h[1-6])\b[^>]*>(.*?)</\1\s*>", body, re.I | re.S)
        if m and _EMPTY_BLOCK.match(m.group(2)):
            body = body[m.end():]
    # whitespace at the start of the first text of a block: "<p>   Hi" -> "<p>Hi"
    body = re.sub(r"(<(?:p|div|li|td)\b[^>]*>)(?:" + _WS + r"|&nbsp;|&#160;)+", r"\1", body, flags=re.I)
    body = re.sub(r"(<br\s*/?>)[ \t ]+", r"\1", body, flags=re.I)
    return body


def sanitize(body):
    """Return the body with all leading whitespace removed (start of the draft and start of every line/paragraph)."""
    body = body or ""
    if is_html(body):
        return _strip_leading_html(body).rstrip()
    body = re.sub(r"^" + _WS + r"+", "", body.replace("\r\n", "\n"))
    lines = [re.sub(r"^[ \t   　" + _ZW + r"]+", "", ln).rstrip() for ln in body.split("\n")]
    return "\n".join(lines).rstrip()


def leading_whitespace(body):
    """Description of any leading whitespace left in ``body`` (empty string when clean)."""
    body = body or ""
    if not body:
        return ""
    if re.match(r"^" + _WS, body):
        return "starts with whitespace"
    if is_html(body):
        if _strip_leading_html(body) != body.rstrip():
            return "starts with an empty paragraph, line break or indented text"
        return ""
    for n, ln in enumerate(body.split("\n"), 1):
        if re.match(r"^[ \t   　" + _ZW + r"]+\S", ln):
            return "line %d is indented" % n
    return ""


def visible_text(body):
    t = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", body or "", flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return _html.unescape(t).replace(" ", " ")


def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


# ---------------------------------------------------------------------------------------------------- signature
def signature(sent_html):
    """Split a sent email's signature into verbatim text and images.

    Looks for the signature container Outlook/Gmail/mobile clients mark with an id or class; failing that, for the
    last block that contains an image. Returns {"text": str, "images": [{"src","alt","cid"}], "found": bool}.
    """
    html = sent_html or ""
    start = None
    m = _SIG_MARKER.search(html)
    if m:
        start = html.rfind("<", 0, m.start())
    else:
        imgs = list(re.finditer(r"<img\b[^>]*>", html, re.I))
        if imgs:
            start = max(html.rfind("<div", 0, imgs[-1].start()), html.rfind("<table", 0, imgs[-1].start()),
                        html.rfind("<p", 0, imgs[-1].start()))
    if start is None or start < 0:
        return {"text": "", "images": [], "found": False}
    block = html[start:]
    block = re.sub(r"<(?:blockquote|div[^>]*id=[\"']?(?:appendonsend|divRplyFwdMsg))[\s\S]*$", "", block, flags=re.I)
    images = []
    for im in re.finditer(r"<img\b([^>]*)>", block, re.I):
        attrs = im.group(1)
        g = lambda k: (re.search(k + r"=[\"']([^\"']*)[\"']", attrs, re.I) or [None, ""])[1]
        src = g("src")
        images.append({"src": src, "alt": g("alt"), "cid": src[4:] if src.lower().startswith("cid:") else ""})
    text = visible_text(re.sub(r"<img\b[^>]*>", "", block, flags=re.I))
    text = "\n".join(ln.strip() for ln in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return {"text": text, "images": images, "found": bool(text or images)}


# -------------------------------------------------------------------------------------------------------- gate
def check(body, signature_text="", image_expected=False, image_attached=False, banned=()):
    """Problems with a *final* draft body ([] = good). ``image_expected`` means the user's sent mail carries a signature
    image; ``image_attached`` means it was attached and read back by some other route."""
    problems = []
    body = body or ""
    if not body.strip():
        return ["draft body is empty"]
    lw = leading_whitespace(body)
    if lw:
        problems.append("leading whitespace: " + lw)
    if _BAD_TAGS.search(body) and not image_attached:
        problems.append("draft contains img/span/font/blockquote markup that the draft tools reject")
    text = visible_text(body)
    if _EM_DASH in text:
        problems.append("draft contains an em dash")
    if _PLACEHOLDER.search(text):
        problems.append("draft contains a placeholder (%s)" % _PLACEHOLDER.search(text).group(0))
    for phrase in banned:
        if phrase and phrase.lower() in text.lower():
            problems.append("draft contains banned phrase %r" % phrase)
    if signature_text:
        want = [_norm(l) for l in signature_text.split("\n") if l.strip()]
        have = _norm(text)
        missing = [l for l in want if l not in have]
        if missing:
            problems.append("signature text missing or changed (first missing line: %r)" % missing[0][:60])
    if image_expected and not image_attached:
        problems.append("signature image not included (the draft tool cannot carry <img>; "
                        "say so once in the summary)")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sanitize"); s.add_argument("--in", dest="inp", required=True); s.add_argument("--out")
    c = sub.add_parser("check"); c.add_argument("--in", dest="inp", required=True)
    c.add_argument("--signature-text"); c.add_argument("--image-expected", action="store_true"); c.add_argument("--image-attached", action="store_true")
    g = sub.add_parser("signature"); g.add_argument("--in", dest="inp", required=True)
    a = ap.parse_args(argv)
    try:
        raw = open(a.inp, encoding="utf-8").read()
        sig = open(a.signature_text, encoding="utf-8").read() if getattr(a, "signature_text", None) else ""
    except Exception as e:
        print("INPUT ERROR: %s" % e, file=sys.stderr)
        return 2
    if a.cmd == "sanitize":
        out = sanitize(raw)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(out)
        else:
            sys.stdout.write(out + "\n")
        return 0
    if a.cmd == "signature":
        print(json.dumps(signature(raw), ensure_ascii=False))
        return 0
    probs = check(raw, sig, a.image_expected, a.image_attached)
    for p in probs:
        print("DRAFT PROBLEM: " + p, file=sys.stderr)
    print(json.dumps({"ok": not probs, "problems": probs}))
    return 6 if probs else 0


if __name__ == "__main__":
    sys.exit(main())

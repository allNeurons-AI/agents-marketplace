#!/usr/bin/env python3
"""Lossless compaction of the (uncompressed, ASCII) PDFs the renderer writes -- same pages, same look, fewer bytes.

Why not Flate + base64 (the usual way to 'compress a PDF')?  The SharePoint upload tool only takes the file as text the
model types into the call.  Flate output is random-looking bytes; base64 of it is a long opaque string that the model
cannot reliably re-type (two attempts at a 10 KB base64 string both came out the wrong length) and that safety guards
treat as an encoded blob.  So the file is kept as readable ASCII and made smaller by lossless rewriting instead:

  * numbers trimmed: shape coordinates to 0.01 pt and colours to 0.001 (text positions and spacing are never touched)
  * empty save/restore blocks removed (q ... cm ... Q with nothing drawn in between)
  * obsolete page-dictionary entries dropped (/ProcSet, /Rotate 0, empty /Trans)
  * the PDF is re-assembled with a fresh, correct xref table

Safety net: the result must have the same page count and byte-identical extracted text per page, otherwise the original
file is left untouched.  tests/ and scripts/selftest.py additionally compare rendered pixels.  SUITE_PDF_MINIFY=0 turns
it off.
"""
import os
import re

_NUM = re.compile(r"^-?(\d+\.\d*|\.\d+)$")
_COLOR_OPS = {"rg", "RG", "g", "G", "k", "K"}
_PATH_OPS = {"m", "l", "c", "v", "y", "re"}   # vector-shape coordinates: 0.01 pt is far below what any renderer resolves


def _fmt(v, p):
    s = f"{round(v, p):.{p}f}".rstrip("0").rstrip(".")
    if s.startswith("0."):
        s = s[1:]
    elif s.startswith("-0."):
        s = "-" + s[2:]
    return "0" if s in ("", "-0", "-") else s


def _tokens(line):
    """Split one content-stream line into ('s', '(...)') string literals and ('w', word) words."""
    out, i, n = [], 0, len(line)
    while i < n:
        c = line[i]
        if c == "(":
            depth, j = 0, i
            while j < n:
                if line[j] == "\\":
                    j += 2; continue
                if line[j] == "(":
                    depth += 1
                elif line[j] == ")":
                    depth -= 1
                    if depth == 0:
                        j += 1; break
                j += 1
            out.append(("s", line[i:j])); i = j
        elif c in " \t":
            i += 1
        else:
            j = i
            while j < n and line[j] not in " \t(":
                j += 1
            out.append(("w", line[i:j])); i = j
    return out


def _line(line):
    toks = _tokens(line)
    # 1) round numeric operands according to the operator that consumes them
    pending = []
    for idx, (k, t) in enumerate(toks):
        if k == "w" and _NUM.match(t):
            pending.append(idx)
        elif k == "w" and not re.match(r"^-?\d+$", t) and not t.startswith("/"):
            # Only colours and vector-shape coordinates are trimmed. Text positions/spacing are left EXACTLY as written:
            # viewers snap glyphs to whole pixels, so even a 0.00003 pt change can flip a glyph by 1 px on a borderline value.
            p = 3 if t in _COLOR_OPS else (2 if t in _PATH_OPS else None)
            if p is not None:
                for pi in pending:
                    toks[pi] = ("w", _fmt(float(toks[pi][1]), p))
            pending = []
        elif k == "s" or t.startswith("/") or re.match(r"^-?\d+$", t):
            if k == "s":
                pending = []
    # NOTE: consecutive (A) Tj (B) Tj are deliberately NOT merged. Viewers place every Tj run on a pixel boundary, so
    # merging can nudge the second run by a pixel at some zoom levels (seen in testing) for a ~2% saving.
    return " ".join(t for _, t in toks)


_CM = re.compile(r"^[-\d. ]+ cm$")


def _drop_empty_q(lines):
    changed = True
    while changed:
        changed = False
        out, i = [], 0
        while i < len(lines):
            if lines[i] == "q" and i + 1 < len(lines) and lines[i + 1] == "Q":
                i += 2; changed = True; continue
            if (lines[i] == "q" and i + 2 < len(lines) and _CM.match(lines[i + 1]) and lines[i + 2] == "Q"):
                i += 3; changed = True; continue
            out.append(lines[i]); i += 1
        lines = out
    return lines


_TM = re.compile(r"^BT 1 0 0 1 (\S+) (\S+) Tm (.*)$")
_FONTONLY = re.compile(r"^BT (/F\d+ \S+ Tf \S+ TL) ET$")


def _text_blocks(lines):
    """BT 1 0 0 1 x y Tm  ->  BT x y Td   (identical at the start of a BT: the line matrix is the identity)
    'BT <font> ET' + 'BT ... ET' -> one BT (text state persists, so only the redundant ET/BT is removed)"""
    out = []
    for ln in lines:
        m = _TM.match(ln)
        if m:
            ln = "BT %s %s Td %s" % (m.group(1), m.group(2), m.group(3))
        # NOTE: a trailing "T* ET" is deliberately KEPT. It draws nothing, but text extractors (search, copy, the
        # post-upload read-back) use it as the line break between blocks; removing it glues neighbouring cells together.
        out.append(ln)
    merged, i = [], 0
    while i < len(out):
        f = _FONTONLY.match(out[i])
        if f and i + 1 < len(out) and out[i + 1].startswith("BT ") and out[i + 1].endswith(" ET"):
            merged.append("BT " + f.group(1) + " " + out[i + 1][3:])
            i += 2
        else:
            merged.append(out[i]); i += 1
    return merged


def _stream(data):
    lines = [_line(l.rstrip()) if l.strip() else "" for l in data.split("\n")]
    lines = [l for l in lines if l != ""]
    lines = _drop_empty_q(lines)
    lines = [l for l in lines if l != "1 0 0 1 0 0 cm"]
    lines = _text_blocks(lines)
    return "\n".join(lines)


def _pages_text(path):
    from pypdf import PdfReader
    r = PdfReader(path)
    return [" ".join((p.extract_text() or "").split()) for p in r.pages]


def minify(path):
    """Rewrite *path* in place. Returns (old_bytes, new_bytes); (n, n) when left unchanged."""
    raw = open(path, "rb").read()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return len(raw), len(raw)
    head = text[: text.index("\n", text.index("\n") + 1) + 1]          # %PDF-1.x + binary-marker comment line
    objs = re.findall(r"(\d+) 0 obj\n(.*?)\nendobj\n", text, flags=re.S)
    if not objs:
        return len(raw), len(raw)
    body = [head]
    offsets = {}
    pos = len(head)
    for num, content in objs:
        if "\nstream\n" in content:
            d, s = content.split("\nstream\n", 1)
            s = s[: s.rindex("endstream")]
            if s.endswith("\n"):
                s = s[:-1]
            s = _stream(s)
            d = re.sub(r"/Length \d+", f"/Length {len(s)}", d)
            piece = f"{num} 0 obj\n{d}\nstream\n{s}\nendstream\nendobj\n"
        else:
            c = re.sub(r"/ProcSet \[[^\]]*\]\s*", "", content)
            c = re.sub(r"/Rotate 0 /Trans <<\s*>>\s*", "", c)
            c = re.sub(r"/PageMode /UseNone ", "", c)
            c = re.sub(r"[ \t]+\n", "\n", c)
            c = re.sub(r"\n{2,}", "\n", c)
            piece = f"{num} 0 obj\n{c}\nendobj\n"
        offsets[int(num)] = pos
        pos += len(piece)
        body.append(piece)
    tr = text[text.rindex("trailer\n") + 8: text.rindex("\nstartxref")]
    tr = "\n".join(l for l in tr.split("\n") if l.strip() and not l.startswith("%"))
    size = max(offsets) + 1
    xref = "xref\n0 %d\n0000000000 65535 f \n" % size + "".join(
        "%010d 00000 n \n" % offsets.get(i, 0) for i in range(1, size))
    out = "".join(body) + xref + "trailer\n" + tr + "\nstartxref\n%d\n%%%%EOF\n" % pos
    tmp = path + ".min"
    open(tmp, "wb").write(out.encode("ascii"))
    try:
        ok = _pages_text(tmp) == _pages_text(path)
    except Exception:
        ok = False
    if not ok or len(out) >= len(raw):
        os.remove(tmp)
        return len(raw), len(raw)
    os.replace(tmp, path)
    return len(raw), len(out)


if __name__ == "__main__":
    import sys
    for f in sys.argv[1:]:
        a, b = minify(f)
        print(f"{f}: {a} -> {b} bytes ({100 * (a - b) / a:.0f}% smaller)")

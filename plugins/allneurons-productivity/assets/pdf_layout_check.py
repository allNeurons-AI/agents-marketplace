"""Layout gate: no visible text may sit outside the printable content area.

Why this exists (): a Call Prep briefing shipped with a long company
name drawn as one unwrapped line, so the heading ran off the right margin and
the PDF still passed every structural check (it parsed, had text, had footers).
Nothing looked at *where* the text was. This module does.

It walks every text run on every page with pypdf's visitor, computes the run's
horizontal extent from the PDF's own text matrix plus the standard-font width
tables, and reports any run that crosses the left or right content margin (or
the page edge). Dependency: pypdf + reportlab, both already required.

Usage:  python3 pdf_layout_check.py file.pdf [--margin 54] [--tol 1.5]
Exit :  0 inside the margins · 1 overflow found (lines on stdout) · 2 unreadable
"""
import argparse
import sys

PAGE_W = 612.0          # US Letter, the only page size the plugin renders
DEFAULT_MARGIN = 54.0   # 0.75 in, render_brief.MARGIN
DEFAULT_TOL = 1.5       # pt of slack for rounding and glyph side-bearings


def _width(text, font_name, size):
    try:
        from reportlab.pdfbase import pdfmetrics
        return pdfmetrics.stringWidth(text, font_name, size)
    except Exception:
        return len(text) * size * 0.5          # conservative fallback


def _font_name(font_dict):
    try:
        base = str(font_dict.get("/BaseFont") or "Helvetica")
    except Exception:
        base = "Helvetica"
    base = base.lstrip("/")
    if "+" in base[:8]:
        base = base.split("+", 1)[1]
    std = ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique",
           "Times-Roman", "Courier")
    return base if base in std else ("Helvetica-Bold" if "bold" in base.lower() else "Helvetica")


def runs(path):
    """Yield (page_no, text, x0, x1) for every non-blank text run."""
    from pypdf import PdfReader
    reader = PdfReader(path)
    for pno, page in enumerate(reader.pages, 1):
        found = []

        def visit(text, cm, tm, font_dict, font_size, _found=found):
            if not text or not text.strip():
                return
            try:
                a, b, c, d, e, f = [float(v) for v in cm]
                ta, tb, tc, td, te, tf = [float(v) for v in tm]
            except Exception:
                return
            x = te * a + tf * c + e                     # origin of the run in user space
            scale = abs(ta * a) or 1.0
            size = float(font_size or 0) * (scale if scale != 1.0 else 1.0)
            if size <= 0:
                return
            w = _width(text.rstrip("\n"), _font_name(font_dict or {}), size)
            _found.append((text, x, x + w))

        page.extract_text(visitor_text=visit)
        for text, x0, x1 in found:
            yield pno, text, x0, x1


def check(path, margin=DEFAULT_MARGIN, tol=DEFAULT_TOL, page_w=PAGE_W):
    """Return a list of human-readable problems (empty = every run inside the margins)."""
    problems = []
    lo, hi = margin - tol, page_w - margin + tol
    for pno, text, x0, x1 in runs(path):
        if x1 > hi:
            problems.append("page %d: text runs %.1fpt past the right margin: %r"
                            % (pno, x1 - (page_w - margin), text.strip()[:60]))
        elif x0 < lo:
            problems.append("page %d: text starts %.1fpt left of the left margin: %r"
                            % (pno, (margin) - x0, text.strip()[:60]))
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf")
    ap.add_argument("--margin", type=float, default=DEFAULT_MARGIN)
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL)
    a = ap.parse_args(argv)
    try:
        probs = check(a.pdf, a.margin, a.tol)
    except Exception as exc:                       # unreadable file is not "inside the margins"
        print("LAYOUT CHECK ERROR: %s" % exc, file=sys.stderr)
        return 2
    for p in probs:
        print("OVERFLOW: " + p)
    if not probs:
        print("OK: all text inside the %.0fpt content margins" % a.margin)
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())

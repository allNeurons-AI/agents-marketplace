#!/usr/bin/env python3
"""Self-looping PDF compressor: same pages, same text, same layout and colour blocks -- fewer bytes, at the cost of
invisible precision. Used by deliver_prepare.py before it ever trims content.

Levels (each includes the ones before it; the loop stops at the first level that is under the byte budget):
  0  lossless        Flate level 9 on every stream, objects packed into object streams, duplicate objects merged
  1  metadata        document info, XMP metadata, page labels, thumbnails, unused resources and annotation extras removed
  2  precision       (+ zopfli re-deflate when installed) numbers in the page content rounded: shapes to 0.1 pt, colours to 0.02, text positions to 0.05 pt
  3  coarse          shapes to 0.5 pt, text positions to 0.1 pt, colours to 0.05 (still invisible at normal zoom)
  4  tight           shapes and text positions to whole points, colours to 0.1 (quality visibly softer, layout the same)

Safety net: a level's output is used only if it has the same page count and byte-identical extracted text on every page.
A level that fails that check is skipped; the best file so far is kept.
CLI:  python3 compressor.py in.pdf out.pdf [--budget 20000]    (prints a JSON line)
"""
import argparse
import json
import os
import shutil
import sys
import tempfile

LEVELS = (0, 1, 2, 3, 4)
_SHAPE_STEP = {2: 0.1, 3: 0.5, 4: 1.0}
_TEXT_STEP = {2: 0.05, 3: 0.1, 4: 1.0}
_COLOR_STEP = {2: 0.02, 3: 0.05, 4: 0.1}
_SHAPE_OPS = {"m", "l", "c", "v", "y", "re"}
_TEXT_POS_OPS = {"Td", "TD", "Tm"}
_COLOR_OPS = {"rg", "RG", "g", "G", "k", "K"}


def _q(v, step):
    r = round(round(float(v) / step) * step, 4)
    return int(r) if r == int(r) else r


def _num(v):
    """Compact PDF number: no leading zero, no trailing zeros."""
    t = ("%.4f" % float(v)).rstrip("0").rstrip(".")
    if t.startswith("0."):
        t = t[1:]
    elif t.startswith("-0."):
        t = "-" + t[2:]
    return b"0" if t in ("", "-", "-0") else t.encode()


def _round_stream(pdf, page, level):
    import pikepdf
    out = []
    for operands, op in pikepdf.parse_content_stream(page):
        name = str(op)
        if name == "INLINE IMAGE":
            return                                           # leave pages with inline images exactly as they are
        step = None
        if name in _SHAPE_OPS:
            step = _SHAPE_STEP[level]
        elif name in _TEXT_POS_OPS:
            step = _TEXT_STEP[level]
        elif name in _COLOR_OPS:
            step = _COLOR_STEP[level]
        parts = []
        for i, x in enumerate(operands):
            if _is_num(x) and not isinstance(x, (str, bytes)) and not isinstance(x, pikepdf.String):
                keep = step is None or (name == "Tm" and i < 4)       # Tm scale/shear entries (font size) stay exact
                parts.append(_num(x) if keep else _num(_q(x, step)))
            else:
                parts.append(x.unparse() if hasattr(x, "unparse") else str(x).encode())
        out.append(b" ".join(parts + [name.encode()]))
    page.Contents = pdf.make_stream(b"\n".join(out))


def _is_num(x):
    try:
        float(x)
        return True
    except Exception:
        return False


def _strip(pdf):
    for k in ("/Info",):
        if k in pdf.trailer:
            del pdf.trailer[k]
    root = pdf.Root
    for k in ("/Metadata", "/PageLabels", "/Names", "/Outlines", "/StructTreeRoot", "/MarkInfo", "/ViewerPreferences"):
        if k in root:
            del root[k]
    for page in pdf.pages:
        for k in ("/Thumb", "/Group", "/Metadata", "/PieceInfo", "/Rotate"):
            if k in page and not (k == "/Rotate" and int(page[k]) != 0):
                del page[k]
        for a in (page.get("/Annots") or []):
            for k in ("/C", "/H", "/StructParent", "/P"):          # /Border and /BS stay: without them a viewer draws a box around every link
                if k in a:
                    del a[k]
    try:
        pdf.remove_unreferenced_resources()
    except Exception:
        pass


def _save(pdf, dst):
    import pikepdf
    pdf.save(dst, object_stream_mode=pikepdf.ObjectStreamMode.generate, compress_streams=True, recompress_flate=True,
             stream_decode_level=pikepdf.StreamDecodeLevel.generalized,
             linearize=False, deterministic_id=True)


def _zopfli(path):
    """Optional: re-deflate every page stream with zopfli (2-4 % smaller than zlib level 9). Silently skipped when the
    zopfli package is not installed."""
    try:
        import zopfli.zlib as zz
    except ImportError:
        return
    import pikepdf
    tmp = path + ".zop"
    with pikepdf.open(path) as pdf:
        for o in pdf.objects:
            if isinstance(o, pikepdf.Stream) and o.get("/Filter") == "/FlateDecode" and str(o.get("/Type")) not in ("/ObjStm", "/XRef") \
                    and "/DecodeParms" not in o:
                o.write(zz.compress(o.read_bytes(), numiterations=15), filter=pikepdf.Name.FlateDecode)
        pdf.save(tmp, object_stream_mode=pikepdf.ObjectStreamMode.preserve, compress_streams=False, recompress_flate=False)
    if os.path.getsize(tmp) < os.path.getsize(path):
        os.replace(tmp, path)
    else:
        os.remove(tmp)


def _same_text(a_path, b_path):
    from pypdf import PdfReader
    a, b = PdfReader(a_path), PdfReader(b_path)
    return len(a.pages) == len(b.pages) and all((x.extract_text() or "") == (y.extract_text() or "") for x, y in zip(a.pages, b.pages))


def compress_level(src, dst, level):
    """Write `src` compressed to `level` into `dst`. Returns the byte size, or None when the result is not text-identical."""
    import pikepdf
    with pikepdf.open(src) as pdf:
        if level >= 1:
            _strip(pdf)
        if level >= 2:
            for page in pdf.pages:
                _round_stream(pdf, page, level)
        _save(pdf, dst)
    if level >= 2:
        _zopfli(dst)
    if level >= 2 and not _same_text(src, dst):
        os.remove(dst)
        return None
    return os.path.getsize(dst)


def compress_to_budget(src, dst, budget=None, max_level=4, check=None):
    """Self-loop over the levels: keep the smallest valid file; stop at the first one under `budget`.
    `check(path) -> (ok, problems)` is an optional extra gate (the layout gate) every candidate must pass.
    Returns {"bytes", "level", "fits", "tried": [(level, bytes|None)]}; `dst` always holds the best valid file."""
    tmp = tempfile.mkdtemp(prefix=".cmp-")
    best, best_level, tried = None, -1, []
    try:
        shutil.copyfile(src, dst)
        best = os.path.getsize(dst)
        for level in LEVELS:
            if level > max_level:
                break
            cand = os.path.join(tmp, "l%d.pdf" % level)
            try:
                n = compress_level(src, cand, level)
            except Exception as e:                           # a level that cannot run is skipped, never fatal
                print("NOTE: compressor level %d skipped (%s: %s)" % (level, type(e).__name__, e), file=sys.stderr)
                n = None
            if n is not None and check is not None:
                ok, _ = check(cand)
                if not ok:
                    n = None
            tried.append((level, n))
            if n is not None and n < best:
                shutil.copyfile(cand, dst)
                best, best_level = n, level
            if budget and best <= budget:
                break
        return {"bytes": best, "level": best_level, "fits": bool(budget is None or best <= budget), "tried": tried}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument("--max-level", type=int, default=4)
    a = ap.parse_args(argv)
    r = compress_to_budget(a.src, a.dst, a.budget, a.max_level)
    print(json.dumps(r))
    return 0 if r["fits"] else 1


if __name__ == "__main__":
    sys.exit(main())

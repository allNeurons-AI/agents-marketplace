"""Post-upload read-back, as a script so it cannot be skipped or waved through.

After the Drive upload, read the item back (SharePoint/OneDrive: read_resource on the returned resourceUri; Google Drive: read_file_content on the returned file id), save the text it returns to a file, then:

    python3 readback_check.py --pdf <the PDF that was uploaded> --text <saved read_resource text>

It rebuilds three short phrases from EVERY page of the local PDF and looks for each in the uploaded item's text. Exit 0 =
every page of the uploaded copy is intact. Exit 1 = at least one page is missing or garbled (the output names the pages):
the upload was corrupted in transfer (a typed copy can lose a character inside a compressed page and that page then opens
blank in the browser). Delete that item, re-send from the gate once, and run this check again.  Exit 2 = unreadable input.
"""
import argparse, json, re, sys


def _norm(t):
    return " ".join((t or "").split())


def phrases_by_page(path):
    from pypdf import PdfReader
    out = []
    for pg in PdfReader(path).pages:
        t = _norm(pg.extract_text())
        ph = []
        if t:
            ph.append(t[:40].strip())
            ph.append(t[-30:].strip())
            for frac in (0.15, 0.5, 0.85):
                i = int(len(t) * frac)
                w = t[i:i + 60].split(" ")
                x = " ".join(w[1:6]).strip()
                if len(x) >= 18:
                    ph.append(x)
        out.append([x for x in dict.fromkeys(ph) if x])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--text", required=True, help="file holding the text read_resource returned for the uploaded item")
    a = ap.parse_args()
    try:
        by_page = phrases_by_page(a.pdf)
        got = _norm(open(a.text, encoding="utf-8", errors="replace").read())
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)})); return 2
    bad = []
    for n, ph in enumerate(by_page, 1):
        miss = [x for x in ph if x not in got]
        if not ph or miss:
            bad.append({"page": n, "missing": miss[:3] or ["(page has no text)"]})
    res = {"ok": not bad, "pages": len(by_page), "bad_pages": bad}
    print(json.dumps(res))
    if bad:
        print("READ-BACK FAILED: page(s) %s of the uploaded copy are missing or garbled. Delete the item, re-send once from the gate, "
              "and run this again." % ", ".join(str(b["page"]) for b in bad), file=sys.stderr)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())

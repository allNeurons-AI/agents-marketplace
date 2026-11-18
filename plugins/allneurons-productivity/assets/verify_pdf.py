#!/usr/bin/env python3
"""Gate every file before it is attached or uploaded: it must be this run's real PDF.

Usage:
  python3 verify_pdf.py <file.pdf> [--b64 <out.b64>]

Exit 0 and one JSON line
  {"ok":true,"path":..,"bytes":..,"pages":..,"sha256":..,"safe_to_attach":true,"safe_to_upload":true}
when the file is a genuine PDF. Exit 1 with {"ok":false,"reason":..} otherwise.
"safe_to_attach" is reported (not enforced here) so a delivery step never has
to guess whether a size-related attach failure is coming: false means the file
is over the safe-attach ceiling and should be uploaded/linked instead of attached.

"safe_to_upload" is reported against this deployment's actual connected
SharePoint/OneDrive upload tool (the strictest connector the plugin supports): that tool
accepts content up to UPLOAD_CEILING_BYTES per call and documents no
chunked or resumable upload at all, so a file over it cannot be uploaded
through that tool in ONE call. false NEVER means skip the upload: the upload
and a verified link are mandatory whatever the size. false means this exact
file is over the single-call ceiling, so produce an upload-sized version with
the fit-for-upload tier chain (deliver_prepare.py: full -> lite -> compact ->
multipart, N independent PDFs that are each under the ceiling) and upload
that.

--b64 writes the exact bytes as one unbroken standard-base64 string, for a
connector upload that takes contentBase64. Pass the printed "bytes" value as the
upload's expectedBytes so a truncated or wrong payload is refused.

Why this exists: a real run uploaded the Markdown backup to Drive under the
brief's name instead of the PDF. Never attach or upload a file this script has
not passed.
"""
import base64, hashlib, json, os, sys, warnings
warnings.filterwarnings("ignore")

# Conservative headroom under the ~25MB attachment caps common to Gmail/Outlook
# APIs, once base64 encoding overhead (~33%) is accounted for. This is a
# theoretical ceiling for a mail tool that supports attachments at all — see
# UPLOAD_CEILING_BYTES below for this deployment's real, binding limit.
SAFE_ATTACH_CEILING_BYTES = 18 * 1024 * 1024

# The hard per-call content limit of this deployment's connected
# SharePoint/OneDrive upload tool (sharepoint_upload_file /
# sharepoint_update_file), taken from that tool's own description:
# "content up to 1048576 bytes" with "no chunked upload" of any kind.
# Microsoft Graph itself supports far larger files via a resumable
# createUploadSession, but no tool exposing that call is connected here —
# so for this plugin, today, 1MB is the real ceiling, not Graph's own.
# Re-check the connected tool's own description before trusting this
# number forever; it tracks that tool, not a hardcoded assumption.
UPLOAD_CEILING_BYTES = 1024 * 1024


# The upload tool takes the file only as a STRING argument (contentBase64) -- there is no file-path or artifact
# parameter -- so the agent must read the .b64 text and pass it back verbatim. That only works while the text fits in
# one tool result (Bash output is cut at ~30,000 characters; Read at ~25,000 tokens) and is short enough to copy
# without error. 30,000 base64 characters ~= 22 KB of PDF. Helvetica PDFs are 8-15 KB; an embedded-font PDF (~55 KB,
# ~72,000 chars) is NOT pasteable, which is what broke delivery in v1.9.0.
PASTE_CEILING_B64_CHARS = 30000
# Preferred path (v1.9.1): an ASCII-only PDF with uncompressed streams (what the renderer now writes) can be passed to
# sharepoint_upload_file as plain text in `content` -- no base64, nothing high-entropy to transcribe. Verified against
# the live tool: a 1,296-byte ASCII PDF uploaded via `content` with exactly matching size. Readable PDF operators copy
# reliably; compressed/base64 data does not (two attempts at a 10 KB base64 string both came out the wrong length).
PASTE_CEILING_TEXT_CHARS = 60000   # proven: a 7-page, 54,479-byte brief uploaded byte-exact and read back intact (v1.9.1 test)


def classify_paste_size(b64_chars):
    return b64_chars <= PASTE_CEILING_B64_CHARS


def classify_size(nbytes):
    return nbytes <= SAFE_ATTACH_CEILING_BYTES


def classify_upload_size(nbytes):
    return nbytes <= UPLOAD_CEILING_BYTES


def fail(reason):
    print(json.dumps({"ok": False, "reason": reason}))
    sys.exit(1)


def main():
    args = sys.argv[1:]
    if not args:
        fail("usage: verify_pdf.py <file.pdf> [--b64 <out.b64>] [--text <out.txt>]")
    path = args[0]
    b64_out = None
    text_out = None
    if "--text" in args:
        i = args.index("--text")
        if i + 1 >= len(args):
            fail("--text needs an output path")
        text_out = args[i + 1]
    if "--b64" in args:
        i = args.index("--b64")
        if i + 1 >= len(args):
            fail("--b64 needs an output path")
        b64_out = args[i + 1]

    if not path.lower().endswith(".pdf"):
        fail(f"not a .pdf filename: {os.path.basename(path)} — only the PDF may be attached or uploaded, never the .md backup")
    if not os.path.isfile(path):
        fail(f"file not found: {path}")
    data = open(path, "rb").read()
    if len(data) < 200:
        fail(f"file too small to be a real PDF ({len(data)} bytes)")
    if not data.startswith(b"%PDF-"):
        fail("file does not start with %PDF- — it is not a PDF (a Markdown or text file renamed .pdf fails here)")
    if b"%%EOF" not in data[-2048:]:
        fail("no %%EOF trailer — the PDF is truncated")

    pages = None
    readback_phrase = None
    try:
        from pypdf import PdfReader
        _r = PdfReader(path)
        pages = len(_r.pages)
        _first = " ".join((_r.pages[0].extract_text() or "").split())
        _last = " ".join((_r.pages[-1].extract_text() or "").split())
        # Post-upload check: read_resource on the uploaded item returns the PDF's text; it must contain these.
        readback_phrase = [x for x in (_first[:40].strip(), _last[-30:].strip()) if x]
        # A typed upload can corrupt the middle of a file while the first and last words survive (a real report came back as
        # "quiketweek,; nthdinga4tvergalfnoud.."). So the read-back also checks two phrases from the middle of EVERY page
        # (three per page, so page 1 is always checked): the upload is only accepted when all of them are found in the uploaded item's text.
        for _pg in _r.pages:
            _t = " ".join((_pg.extract_text() or "").split())
            for _frac in (0.15, 0.5, 0.85):
                _i = int(len(_t) * _frac)
                _w = _t[_i:_i + 60].split(" ")
                _ph = " ".join(_w[1:6]).strip()                       # whole words only, 5 words
                if len(_ph) >= 18 and _ph not in readback_phrase:
                    readback_phrase.append(_ph)
        readback_phrase = readback_phrase[:2] + readback_phrase[2:][:3 * pages + 2]
        if pages < 1:
            fail("PDF has no pages")
    except ImportError:
        pass
    except Exception as e:  # unreadable structure
        fail(f"PDF could not be parsed: {e}")

    # Layout gate (): a PDF whose text runs past the content margin is not shippable, however well it parses.
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import pdf_layout_check
        overflow = pdf_layout_check.check(path)
    except ImportError:
        overflow = []
    except Exception as e:
        overflow = []
        print(f"NOTE: layout check skipped ({type(e).__name__}: {e})", file=sys.stderr)
    if overflow:
        fail("text outside the printable margins — " + "; ".join(overflow[:3]))

    if b64_out:
        with open(b64_out, "w") as f:
            f.write(base64.b64encode(data).decode("ascii"))

    safe_to_attach = classify_size(len(data))
    if not safe_to_attach:
        print(
            f"NOTE: {len(data)} bytes exceeds the {SAFE_ATTACH_CEILING_BYTES}-byte "
            "safe-attach ceiling — upload to the Drive and link it; do not "
            "attempt to attach this file to the email.",
            file=sys.stderr,
        )

    ascii_only = all(b < 128 and b != 0 for b in data)
    paste_mode = "content" if (ascii_only and len(data) <= PASTE_CEILING_TEXT_CHARS) else None
    over_paste = not paste_mode and not classify_paste_size(4 * ((len(data) + 2) // 3))
    if paste_mode and text_out:
        with open(text_out, "w", newline="") as f:
            f.write(data.decode("ascii"))
    b64_chars = 4 * ((len(data) + 2) // 3)
    safe_to_paste = bool(paste_mode) or classify_paste_size(b64_chars)
    if not paste_mode and classify_paste_size(b64_chars):
        paste_mode = "base64"
    if not safe_to_paste:
        print(
            f"NOTE: base64 is {b64_chars} characters (limit {PASTE_CEILING_B64_CHARS}); do not paste this file as base64. "
            "The upload is still mandatory: use paste_mode 'content' (ASCII text) when it is present, otherwise run the "
            "fit-for-upload tier chain (deliver_prepare.py) so the PDF is re-rendered smaller or split into parts that fit.",
            file=sys.stderr,
        )

    safe_to_upload = classify_upload_size(len(data))
    if not safe_to_upload:
        print(
            f"NOTE: {len(data)} bytes exceeds the {UPLOAD_CEILING_BYTES}-byte "
            "single-call upload ceiling of the strictest supported Drive tool. The upload is still mandatory: "
            "use the fit-for-upload tier chain (deliver_prepare.py: full -> lite -> compact -> multipart) so every "
            "PDF is under the ceiling.",
            file=sys.stderr,
        )

    print(json.dumps({
        "ok": True,
        "path": path,
        "bytes": len(data),
        "pages": pages,
        "sha256": hashlib.sha256(data).hexdigest(),
        "safe_to_attach": safe_to_attach,
        "safe_to_upload": safe_to_upload,
        "readback_phrases": readback_phrase,
        "ascii_only": ascii_only,
        "paste_mode": paste_mode,
        "b64_chars": b64_chars,
        "safe_to_paste": safe_to_paste,
        "next_step": ("over the paste ceiling: run deliver_prepare.py (tier chain full -> lite -> compact -> multipart); "
                      "the upload is never skipped") if (over_paste or not safe_to_upload) else None,
    }))


if __name__ == "__main__":
    main()

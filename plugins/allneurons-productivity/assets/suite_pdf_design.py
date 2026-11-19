"""allNeurons Productivity — PDF renderer with the new design (add-on).

Same command line, exit codes, batch mode, format/accuracy gate, markdown
backup and PDF self-check as suite_pdf.py — it imports that file unchanged
and swaps in only the page drawing:
  Daily Brief -> render_brief.py      (design: skills/daily-brief/daily-brief-pdf-design.md)
  Call Prep   -> render_call_prep.py  (design: skills/call-prep/call-prep-pdf-design.md)
  Competitive Insights -> render_competitive.py (design: skills/competitive-insights/competitive-insights-format.md)

Usage (identical to suite_pdf.py)
    python3 suite_pdf_design.py --kind daily_brief --in brief.json --out Daily_Brief_2026-09-09.pdf
    python3 suite_pdf_design.py --kind call_prep   --in call.json  --out 1200-acme.pdf
    python3 suite_pdf_design.py --batch manifest.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import suite_pdf as core        # noqa: E402  the original renderer, untouched
import render_brief                  # noqa: E402
import render_call_prep              # noqa: E402
import render_competitive            # noqa: E402


LITE = os.environ.get("SUITE_PDF_LITE", "") == "1"   # same payload, plain flowing text, a fraction of the size


def _daily_brief(data, path):
    if LITE:
        import render_lite
        return render_lite.draw("daily_brief", data, path)
    return render_brief.draw(data, path)


def _call_prep(data, path):
    if LITE:
        import render_lite
        pages = render_lite.draw("call_prep", data, path)
    else:
        pages = render_call_prep.draw(data, path)
    if pages > core.CALL_PREP_MAX_PAGES:
        try:
            os.remove(path)
        except OSError:
            pass
        raise core.ContentVolumeError(
            "%d pages; Call Prep is 1-2 pages. The file was deleted. Cut, in this order "
            "(never shrink type): risks, what_you_need_to_know, questions (down to 4), "
            "attendee lines, sources." % pages)
    return pages


def _competitive(data, path):
    return render_competitive.draw(data, path)       # one design, no lite/compact tier (see deliver_prepare.SINGLE_TIER)


_core_check_format = core.check_format


def _check_format(kind, data):
    """Competitive Insights has its own contract (render_competitive.check); the other kinds keep the core's."""
    if kind == "competitive_insights":
        errs = render_competitive.check(data)
        if errs:
            raise core.FormatError("competitive_insights payload does not match the documented format.\n  - %s"
                                   % "\n  - ".join(errs))
        return
    return _core_check_format(kind, data)


core.check_format = _check_format
core.RENDERERS = {"daily_brief": _daily_brief, "call_prep": _call_prep, "competitive_insights": _competitive}

if __name__ == "__main__":
    sys.exit(core.main())

""" (Call Prep text in the margin), PDF format regressions."""
import os
import unittest

from _common import fixture, run, tmpdir
import pdf_layout_check as plc
from pypdf import PdfReader


def render(kind, data, name):
    import json
    t = tmpdir(); i, o = os.path.join(t, "in.json"), os.path.join(t, name)
    json.dump(data, open(i, "w"))
    r = run("suite_pdf_design.py", "--kind", kind, "--in", i, "--out", o)
    return r, o


def text(path):
    return "\n".join(p.extract_text() for p in PdfReader(path).pages)


class Layout(unittest.TestCase):
    def test_gate_detects_an_overflowing_line(self):
        from reportlab.pdfgen import canvas
        t = tmpdir(); p = os.path.join(t, "o.pdf"); c = canvas.Canvas(p, pagesize=(612, 792))
        c.setFont("Helvetica-Bold", 30); c.drawString(54, 700, "Northwind Traders International Holdings Incorporated"); c.save()
        probs = plc.check(p)
        self.assertTrue(probs and "right margin" in probs[0])
        self.assertEqual(run("pdf_layout_check.py", p).returncode, 1)

    def test_gate_passes_a_clean_page(self):
        from reportlab.pdfgen import canvas
        t = tmpdir(); p = os.path.join(t, "o.pdf"); c = canvas.Canvas(p, pagesize=(612, 792))
        c.setFont("Helvetica", 12); c.drawString(54, 700, "Inside the margins"); c.save()
        self.assertEqual(plc.check(p), [])

    def test_call_prep_with_very_long_content_stays_inside_margins(self):
        d = fixture("call_prep_long_content.json")
        r, out = render("call_prep", d, "cp.pdf")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(plc.check(out), [])
        self.assertIn(d["company"].split()[0], text(out))                 # the long title is wrapped, not dropped

    def test_call_prep_hostile_company_and_urls_stay_inside_margins(self):
        d = fixture("call_prep_long_content.json")
        d["company"] = "Northwind Traders International Holdings and Subsidiaries Incorporated " * 2
        d["time"] = d.get("time") or "10:00 am"
        r, out = render("call_prep", d, "cp2.pdf")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(plc.check(out), [])

    def test_daily_brief_with_long_title_and_footer_stays_inside_margins(self):
        d = fixture("brief_overlapping_meetings.json")
        d["headline"] = "ACME-34 " * 40
        r, out = render("daily_brief", d, "b.pdf")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(plc.check(out), [])

    def test_verify_gate_fails_a_pdf_with_overflow(self):
        from reportlab.pdfgen import canvas
        t = tmpdir(); p = os.path.join(t, "o.pdf"); c = canvas.Canvas(p, pagesize=(612, 792), pageCompression=0)
        c.setFont("Helvetica", 30); c.drawString(54, 700, "Northwind Traders International Holdings Incorporated")
        c.drawString(54, 40, "Page 1 of 1"); c.save()
        r = run("verify_pdf.py", p)
        self.assertNotEqual(r.returncode, 0)


class DailyBriefPdf(unittest.TestCase):
    def test_meetings_section_first_with_one_row_per_meeting(self):
        d = fixture("brief_overlapping_meetings.json")
        r, out = render("daily_brief", d, "b.pdf")
        self.assertEqual(r.returncode, 0, r.stderr)
        t = text(out)
        self.assertIn("TODAY'S MEETINGS", t.upper())
        for m in d["meetings"]:
            self.assertIn(m["label"].split("—")[-1].strip()[:18], t.replace("\n", " "))
        first_action = d["needs_attention"][0]["action"][:24]
        self.assertLess(t.upper().index("TODAY'S MEETINGS"), t.index(first_action))

    def test_calendar_line_is_drawn_for_meetings_and_absent_without(self):
        d = fixture("brief_overlapping_meetings.json")
        _, with_m = render("daily_brief", d, "w.pdf")
        d2 = dict(d, meetings=[])
        _, without = render("daily_brief", d2, "n.pdf")
        # the DayLine draws filled rectangles in the three meeting colours; the empty day has none of them
        raw = lambda p: open(p, "rb").read().decode("latin-1")
        solid = ".553 .725 .91 rg"                                           # #8DB9E8, the upcoming-meeting block colour
        self.assertIn(solid, raw(with_m))
        self.assertNotIn(solid, raw(without))
        self.assertIn("No meetings on the calendar today", text(without))

    def test_overlapping_meetings_do_not_collide_in_the_strip(self):
        import render_brief as rb
        ms = fixture("brief_overlapping_meetings.json")["meetings"]
        dl = rb.DayLine(sorted(ms, key=lambda m: rb.meeting_times(m)[0]))
        self.assertEqual(len(dl.blocks), len(ms))
        lanes = {}
        for st, en, colour, lane in dl.blocks:
            lanes.setdefault(lane, []).append((st, en))
        self.assertGreater(len(lanes), 1)                                    # the overlaps really do stack
        for its in lanes.values():
            its.sort()
            for a, b in zip(its, its[1:]):
                self.assertLessEqual(a[1], b[0], "two meetings share a lane and overlap")
        self.assertIn("red", [c for _, _, c, _ in dl.blocks])                # a double-booking reads red

    def test_pdf_is_ascii_and_passes_the_verify_gate(self):
        r, out = render("daily_brief", fixture("brief_many_items.json"), "m.pdf")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(run("verify_pdf.py", out).returncode, 0)


if __name__ == "__main__":
    unittest.main()

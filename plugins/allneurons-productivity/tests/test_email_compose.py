""" (bodyType html in every run, meeting rows). v1.12.0: no feedback or Yes/No links in any email."""
import json
import re
import unittest

from _common import fixture, run, tmpdir
import email_compose as ec

DL = {"filename": "Daily-Brief-2026-10-01.pdf", "link": "https://x.sharepoint.com/Daily.pdf", "pages": 3,
      "address": "me@example.com", "version": "1.10.0"}


def brief():
    d = fixture("brief_overlapping_meetings.json")
    d["delivery"] = dict(DL)
    return d


def followups():
    return {"date": "Oct 6", "coverage": "Checked 40 threads over 10 days", "delivery": dict(DL),
            "still_open": [{"item_id": "a1", "contact": "Ann", "topic": "Quote", "reason": "No reply since Sep 28",
                            "drafted_on": "Oct 1", "age_days": 3, "priority": "High"}],
            "new_drafts": [{"item_id": "b2", "contact": "Bob", "topic": "Contract", "reason": "Asked Friday",
                            "priority": "Medium", "thread": "Contract"}]}


class DailyBrief(unittest.TestCase):
    def test_send_args_always_html(self):
        a = ec.send_args("daily_brief", brief())
        self.assertEqual(a["bodyType"], "html")                               # the  root cause
        self.assertEqual(a["to"], ["me@example.com"])
        self.assertEqual(ec.validate_send("daily_brief", a, brief()), [])

    def test_missing_bodytype_is_caught(self):
        a = ec.send_args("daily_brief", brief()); del a["bodyType"]
        self.assertTrue(any("bodyType" in e for e in ec.validate_send("daily_brief", a, brief())))
        a["bodyType"] = "text"
        self.assertTrue(any("bodyType" in e for e in ec.validate_send("daily_brief", a, brief())))

    def test_manual_and_automatic_runs_are_byte_identical(self):
        self.assertEqual(ec.send_args("daily_brief", brief()), ec.send_args("daily_brief", brief()))

    def test_meetings_first_one_row_each_status_ordered(self):
        a = ec.send_args("daily_brief", brief())
        body = a["body"]
        h3 = re.findall(r"<h3>(.*?)</h3>", body)
        self.assertEqual(h3[1], "Today's meetings")
        self.assertEqual(len(re.findall(r"<tr>", body)), len(brief()["meetings"]))
        self.assertLess(body.index("Board prep"), body.index("Standup"))      # upcoming before passed

    def test_dropping_a_meeting_row_is_a_validation_error(self):
        a = ec.send_args("daily_brief", brief())
        a["body"] = a["body"].replace("<tr>", "<tr hidden>", 1) if False else re.sub(r"<tr>.*?</tr>\n?", "", a["body"], count=1, flags=re.S)
        self.assertTrue(any("meetings" in e for e in ec.validate_send("daily_brief", a, brief())))

    def test_stripped_tags_and_raw_urls_are_rejected(self):
        a = ec.send_args("daily_brief", brief())
        a["body"] += '<p style="color:red">x</p> https://example.com/raw <span>y</span>'
        errs = " ".join(ec.validate_send("daily_brief", a, brief()))
        self.assertIn("style", errs); self.assertIn("raw URL", errs); self.assertIn("span", errs)

    def test_version_line_present_and_no_feedback_links(self):
        a = ec.send_args("daily_brief", brief())
        self.assertIn("allNeurons Productivity v1.10.0 · Sent to me@example.com", a["body"])
        self.assertNotIn("feedback", a["body"].lower()); self.assertNotIn("mailto:", a["body"])

    def test_no_link_means_no_email(self):
        d = brief(); d["delivery"].pop("link")
        with self.assertRaises(ec.ComposeError):
            ec.compose_daily_brief(d)

    def test_body_does_not_start_with_whitespace_or_date(self):
        b = ec.send_args("daily_brief", brief())["body"]
        self.assertTrue(b.startswith("<h3>"))

    def test_multipart_links(self):
        d = brief(); d["delivery"].pop("link")
        d["delivery"]["parts"] = [{"k": 1, "filename": "a_part1of2.pdf", "link": "https://x.co/a1.pdf"},
                                  {"k": 2, "filename": "a_part2of2.pdf", "link": "https://x.co/a2.pdf"}]
        body = ec.send_args("daily_brief", d)["body"]
        self.assertIn("Part 1 of 2", body); self.assertIn("every part is complete", body)

    def test_cli_exit_codes(self):
        t = tmpdir()
        json.dump(brief(), open(t + "/in.json", "w"))
        self.assertEqual(run("email_compose.py", "compose", "--kind", "daily_brief", "--in", t + "/in.json", "--out", t + "/s.json").returncode, 0)
        self.assertEqual(run("email_compose.py", "validate", "--kind", "daily_brief", "--in", t + "/s.json", "--data", t + "/in.json").returncode, 0)
        s = json.load(open(t + "/s.json")); s["bodyType"] = "text"; json.dump(s, open(t + "/s.json", "w"))
        self.assertEqual(run("email_compose.py", "validate", "--kind", "daily_brief", "--in", t + "/s.json").returncode, 6)


class StoredBody(unittest.TestCase):
    def test_text_stored_html_is_detected(self):
        self.assertTrue(ec.stored_body_ok("<h3>x</h3><p>y</p>", "text"))
        self.assertTrue(ec.stored_body_ok("&lt;h3&gt;x&lt;/h3&gt;", "html"))
        self.assertEqual(ec.stored_body_ok("<h3>x</h3><p>y</p>", "html"), [])


class FollowUps(unittest.TestCase):
    def test_html_and_no_yes_no(self):
        a = ec.send_args("follow_ups", followups())
        self.assertEqual(a["bodyType"], "html")
        self.assertEqual(ec.validate_send("follow_ups", a, followups()), [])
        self.assertNotIn("mailto:", a["body"]); self.assertNotIn(">Yes</a>", a["body"]); self.assertNotIn("Give feedback", a["body"])

    def test_counts_reconcile_with_subject(self):
        a = ec.send_args("follow_ups", followups())
        self.assertIn("1 new, 1 awaiting send, 0 flagged", a["subject"])

    def test_clear_result_is_html(self):
        d = {"date": "Oct 6", "delivery": dict(DL), "threads": 12, "days": 10}
        a = ec.send_args("follow_ups", d)
        self.assertEqual(a["bodyType"], "html"); self.assertIn("nothing open", a["subject"])


class Other(unittest.TestCase):
    def test_failure_email_subject(self):
        a = ec.send_args("failure", {"skill": "Competitive Insights", "short": "profile missing", "when": "Mon 07:02",
                                     "error": "profile.md not found", "meaning": "No report was built.", "delivery": dict(DL)})
        self.assertTrue(a["subject"].startswith("[Failed]"))
        self.assertEqual(ec.validate_send("failure", a), [])
        a["subject"] = "Competitive"
        self.assertTrue(ec.validate_send("failure", a))

    def test_competitive_email_needs_the_verified_link(self):
        d = {"week": "Sep 28 - Oct 4", "summary": {"bottom_line": "A and B moved on pricing.", "companies": [{"name": "Acme", "competitors": ["A", "B"], "matters": "A shipped X.", "why": "Buyers will ask about it."}]}, "threats": [{"company": "Acme", "level": "High", "title": "A undercuts us", "line": "Cheaper review tier."}], "delivery": dict(DL, filename="Report.pdf")}
        a = ec.send_args("competitive", d)
        self.assertEqual(ec.validate_send("competitive", a), [])
        d["delivery"]["link"] = ""
        with self.assertRaises(ec.ComposeError):
            ec.compose_competitive(d)


class Misc(unittest.TestCase):
    def test_competitive_email_is_summary_per_company_then_succinct_threats(self):
        d = {"week": "Sep 28", "summary": {"bottom_line": "A and B moved.", "companies": [
             {"name": "Acme", "competitors": ["A"], "matters": "A shipped X.", "why": "Buyers will ask."},
             {"name": "Beta", "competitors": ["B"], "matters": "B cut price.", "why": "Deals get harder."}]},
             "threats": [{"company": "Beta", "level": "Low", "title": "t3", "line": "l"}, {"company": "Acme", "level": "High", "title": "t1", "line": "l"}],
             "delivery": dict(DL, filename="Report.pdf")}
        subj, html = ec.compose_competitive(d)
        self.assertLess(html.index("Executive summary"), html.index("Competitive threats"))
        self.assertIn("Acme", html); self.assertIn("Beta", html); self.assertIn("Why it matters", html)
        self.assertLess(html.index("t1"), html.index("t3"))                      # High before Low
        d["threats"][0]["line"] = "word " * 40
        with self.assertRaises(ec.ComposeError):
            ec.compose_competitive(d)                                           # long threat prose belongs in the PDF


    def test_competitive_email_says_attached_only_when_it_is(self):
        d = {"week": "Sep 28", "summary": {"bottom_line": "A and B moved on pricing.", "companies": [{"name": "Acme", "competitors": ["A", "B"], "matters": "A shipped X.", "why": "Buyers will ask about it."}]}, "threats": [{"company": "Acme", "level": "High", "title": "A undercuts us", "line": "Cheaper review tier."}], "delivery": dict(DL, filename="Report.pdf")}
        body = ec.send_args("competitive", d)["body"]
        self.assertNotIn("Nothing is attached", body); self.assertIn("Click the link above", body); self.assertIn("save a copy in your local folder", body); self.assertNotIn("is attached to this email:", body)
        d["delivery"]["attached"] = True
        a = ec.send_args("competitive", d)
        self.assertIn("The PDF is attached to this email", a["body"]); self.assertNotIn("Nothing is attached", a["body"])
        self.assertEqual(ec.validate_send("competitive", a), [])

    def test_competitive_email_opens_with_where_the_pdf_is_and_how_to_open_it(self):
        d = {"week": "Sep 28", "summary": {"bottom_line": "A and B moved on pricing.", "companies": [{"name": "Acme", "competitors": ["A"], "matters": "A shipped X.", "why": "Buyers will ask about it."}]},
             "threats": [], "delivery": dict(DL, filename="Report.pdf", pages=6)}
        body = ec.send_args("competitive", d)["body"]
        first_link = body.index('<a href="https://'); first_h3 = body.index("<h3>")
        self.assertLess(first_link, first_h3)                                        # the PDF link comes before any section
        self.assertIn("Your report is a PDF (6 pages)", body)
        self.assertIn("Skills/Competitive Insights", body)                           # and says where it is saved
        self.assertLess(body.index("Click the link above"), first_h3)                 # and how to get it, before the summary

    def test_signature_image_note_is_one_deduped_line(self):
        d = followups(); d["signature_image_missing"] = 5
        a = ec.send_args("follow_ups", d)
        self.assertEqual(a["body"].count("Signature image not included"), 1)
        self.assertIn("5 drafts", a["body"]); self.assertEqual(ec.validate_send("follow_ups", a), [])


if __name__ == "__main__":
    unittest.main()

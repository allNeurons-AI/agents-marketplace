""": the Call Prep briefing link must be in the stored meeting notes."""
import json
import unittest

from _common import run, tmpdir
import call_prep_card as cc

URL = "https://example.sharepoint.com/Call%20Prep/2026-10-06/1000-acme.pdf"
CARD = {"header1": "Ann (Acme) · Renewal call", "header2": "Your call · Owner · 10:00–10:30",
        "before_you_join": [{"fact": "Quote expires Friday", "source": "Teams, 26 Sep"}],
        "your_move": [{"text": "Send the revised quote", "source": "Mail, 29 Sep"}],
        "open_with": "Thanks for making time.", "ask": "Who signs on your side?",
        "filename": "1000-acme.pdf", "link": URL, "call_key": "AAMkAGI2", "version": "1.15.0"}


class Link(unittest.TestCase):
    def test_composed_card_holds_the_verified_link_and_passes_audit(self):
        r = cc.compose(CARD)
        self.assertEqual(r["bodyType"], "html")
        self.assertIn('<a href="%s">1000-acme.pdf</a>' % URL, r["body"])
        self.assertEqual(cc.audit(r["body"], URL, "1000-acme.pdf", "AAMkAGI2", "html"), [])

    def test_ref_line_is_last(self):
        body = cc.compose(CARD)["body"]
        self.assertTrue(body.rstrip().endswith("<p><em>ref: call-prep/AAMkAGI2</em></p>"))
        self.assertNotIn("feedback", body.lower())

    def test_every_prep_block_carries_the_skill_version(self):
        body = cc.compose(CARD)["body"]
        self.assertIn("<p><em>allNeurons Productivity v1.15.0</em></p>", body)
        self.assertLess(body.index("allNeurons Productivity v1.15.0"), body.index("ref: call-prep"))   # just above the ref line, which stays last
        self.assertEqual(cc.audit(body, URL, "1000-acme.pdf", "AAMkAGI2", "html", "1.15.0"), [])
        self.assertIn("v(unknown)", cc.compose(dict(CARD, version="(unknown)"))["body"])           # plugin.json unreadable: still printed
        self.assertIn("v1.15.0", cc.compose(dict(CARD, version="v1.15.0"))["body"])                 # a leading v is not doubled
        self.assertNotIn("vv", cc.compose(dict(CARD, version="v1.15.0"))["body"])

    def test_a_card_without_a_version_cannot_be_composed_and_fails_audit(self):
        with self.assertRaises(cc.CardError):
            cc.compose({k: v for k, v in CARD.items() if k != "version"})
        old = cc.compose(CARD)["body"].replace("<p><em>allNeurons Productivity v1.15.0</em></p>\n", "")      # a block booked by an older version
        self.assertTrue(any("skill version" in e for e in cc.audit(old, URL, "1000-acme.pdf", "AAMkAGI2", "html")))
        self.assertTrue(any("not the installed" in e for e in cc.audit(cc.compose(CARD)["body"], URL, None, None, "html", "1.16.0")))

    def test_audit_catches_a_body_overwritten_without_the_link(self):
        body = cc.compose(CARD)["body"]
        stripped = body.replace('<a href="%s">1000-acme.pdf</a>' % URL, "1000-acme.pdf")
        errs = cc.audit(stripped, URL, "1000-acme.pdf", "AAMkAGI2", "html")
        self.assertTrue(any("do not contain a link" in e for e in errs))

    def test_audit_catches_a_different_url(self):
        body = cc.compose(CARD)["body"].replace(URL, "https://example.sharepoint.com/other.pdf")
        self.assertTrue(cc.audit(body, URL, "1000-acme.pdf"))

    def test_audit_catches_local_path_link(self):
        body = cc.compose(CARD)["body"].replace("<p><em>ref:", '<p><a href="/home/claude/x.pdf">x</a></p>\n<p><em>ref:', 1)
        self.assertTrue(any("local or sandbox" in e for e in cc.audit(body, URL)))

    def test_audit_catches_visible_markup_and_wrong_link_text_and_ref(self):
        body = cc.compose(CARD)["body"]
        self.assertTrue(cc.audit(body, URL, "1000-acme.pdf", "AAMkAGI2", "text"))
        self.assertTrue(cc.audit(body, URL, "other.pdf"))
        self.assertTrue(cc.audit(body, URL, None, "OTHERKEY"))

    def test_percent_encoding_differences_do_not_cause_false_failures(self):
        body = cc.compose(CARD)["body"].replace("Call%20Prep", "Call Prep")
        self.assertEqual(cc.audit(body, URL, "1000-acme.pdf"), [])

    def test_local_or_sandbox_path_is_refused_at_compose(self):
        for bad in ("/home/claude/x.pdf", "computer:///x.pdf", "file:///x.pdf", "C:\\x.pdf", "http://insecure.example.com/x.pdf"):
            with self.assertRaises(cc.CardError):
                cc.compose(dict(CARD, link=bad))

    def test_no_verified_url_says_so_and_carries_no_link(self):
        r = cc.compose(dict(CARD, link=None))
        self.assertIn("could not be linked", r["body"])
        self.assertNotIn("1000-acme.pdf</a>", r["body"])
        self.assertTrue(cc.audit(r["body"], URL))                      # and it would fail an audit against a real URL

    def test_card_stays_short_and_sanitizer_safe(self):
        self.assertEqual(cc.compose(CARD)["body"].count("style="), 0)
        with self.assertRaises(cc.CardError):
            cc.compose(dict(CARD, before_you_join=[{"fact": "word " * 400, "source": "x"}]))

    def test_cli(self):
        t = tmpdir(); json.dump(CARD, open(t + "/c.json", "w"))
        self.assertEqual(run("call_prep_card.py", "compose", "--in", t + "/c.json", "--out", t + "/e.json").returncode, 0)
        body = json.load(open(t + "/e.json"))["body"]; open(t + "/b.html", "w").write(body)
        self.assertEqual(run("call_prep_card.py", "audit", "--body", t + "/b.html", "--url", URL, "--filename", "1000-acme.pdf").returncode, 0)
        open(t + "/b.html", "w").write(body.replace(URL, "https://x.co/y.pdf"))
        self.assertEqual(run("call_prep_card.py", "audit", "--body", t + "/b.html", "--url", URL).returncode, 6)


if __name__ == "__main__":
    unittest.main()

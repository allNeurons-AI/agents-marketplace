"""(leading whitespace) and (signature image) on the final draft."""
import base64
import json
import os
import unittest

from _common import ROOT, run, tmpdir
import draft_sanitize as ds


class LeadingWhitespace(unittest.TestCase):
    CASES = ["\n\n  Hi Ann,\n   Thanks.\n\nBest,\nMe", "   Hi Ann,", " Hi Ann,", "﻿Hi Ann,", "\t\nHi Ann,",
             "<p></p><p>&nbsp;</p><br><p>  &nbsp;Hi Ann,</p><p>Body</p>", "<div><br></div>Hi Ann,", "<br><br>Hi Ann,",
             "<p> </p>\n<p>Hi Ann,</p>", "<p>  Hi Ann,</p>"]

    def test_every_leading_whitespace_form_is_removed(self):
        for c in self.CASES:
            out = ds.sanitize(c)
            self.assertEqual(ds.leading_whitespace(out), "", repr(c))
            self.assertIn("Hi Ann,", out)

    def test_check_flags_each_case_before_sanitizing(self):
        for c in self.CASES:
            self.assertTrue(ds.leading_whitespace(c), repr(c))

    def test_clean_body_untouched_and_middle_whitespace_kept(self):
        body = "Hi Ann,\n\nThanks for the call.  Two spaces stay.\n\nBest,\nMe"
        self.assertEqual(ds.sanitize(body), body)
        self.assertEqual(ds.check(body), [])

    def test_indented_later_lines_are_flattened_in_text_drafts(self):
        self.assertEqual(ds.sanitize("Hi Ann,\n    Body line\nBest"), "Hi Ann,\nBody line\nBest")

    def test_cli_sanitize_and_check(self):
        t = tmpdir(); open(t + "/d.txt", "w").write("\n  Hi Ann,\n\nBody.\n\nBest,\nMe")
        self.assertEqual(run("draft_sanitize.py", "check", "--in", t + "/d.txt").returncode, 6)
        run("draft_sanitize.py", "sanitize", "--in", t + "/d.txt", "--out", t + "/c.txt")
        self.assertEqual(run("draft_sanitize.py", "check", "--in", t + "/c.txt").returncode, 0)


class Gate(unittest.TestCase):
    def test_other_draft_defects(self):
        p = " ".join(ds.check("Hi Ann, thanks — [name] here <img src=x>"))
        self.assertIn("em dash", p); self.assertIn("placeholder", p); self.assertIn("img", p)

    def test_signature_text_must_be_intact(self):
        sig = "Alex Morgan\nExample Co"
        self.assertEqual(ds.check("Hi,\n\nBest,\nAlex Morgan\nExample Co", sig), [])
        self.assertTrue(any("signature text" in x for x in ds.check("Hi,\n\nBest,\nAlexa Morgan\nExample Co", sig)))


SENT = ('<p>Hi</p><div id="Signature"><p>Alex Morgan<br>Example Co</p><img src="cid:logo123" alt="logo"></div>'
        '<blockquote>old thread</blockquote>')


class SignatureImage(unittest.TestCase):
    def test_signature_split_keeps_text_verbatim_and_finds_image(self):
        s = ds.signature(SENT)
        self.assertEqual(s["text"], "Alex Morgan\nExample Co")
        self.assertEqual(s["images"][0]["cid"], "logo123")
        self.assertNotIn("old thread", s["text"])

    def test_image_missing_is_reported_not_hidden(self):
        s = ds.signature(SENT)
        probs = ds.check("Hi,\n\nBest,\n" + s["text"], s["text"], image_expected=True)
        self.assertTrue(any("signature image not included" in p for p in probs))
        self.assertEqual(ds.check("Hi,\n\nBest,\n" + s["text"], s["text"], image_expected=True, image_attached=True), [])

    def test_no_signature(self):
        self.assertFalse(ds.signature("<p>Hi</p>")["found"])



if __name__ == "__main__":
    unittest.main()

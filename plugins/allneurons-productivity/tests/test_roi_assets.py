""": assets generated during a skill call are captured against that skill execution."""
import json
import os
import time
import unittest

from _common import run, tmpdir
import roi_assets as ra


class Assets(unittest.TestCase):
    def setUp(self):
        self.d = tmpdir(); self.m = os.path.join(self.d, "m.jsonl"); self.out = os.path.join(self.d, "outputs"); os.makedirs(self.out)

    def f(self, name, data=b"x"):
        p = os.path.join(self.out, name); open(p, "wb").write(data); return p

    def test_record_ties_asset_to_skill_run_and_session(self):
        r = ra.record(self.m, self.f("Daily_Brief_2026-10-06.pdf", b"%PDF-1"), run_id="R1", link="https://x.co/a.pdf",
                      env={"CLAUDE_CODE_SESSION_ID": "sess-9"})
        self.assertEqual((r["skill"], r["run_id"], r["session_id"], r["kind"], r["link"]), ("daily-brief", "R1", "sess-9", "pdf", "https://x.co/a.pdf"))
        self.assertEqual(len(r["sha256"]), 64)

    def test_session_env_precedence(self):
        self.assertEqual(ra.session_id({"SUITE_SESSION_ID": "a", "CLAUDE_SESSION_ID": "b"}), "a")
        self.assertEqual(ra.session_id({}), "")

    def test_same_file_same_run_not_double_counted_but_new_file_is(self):
        p = self.f("Call-Prep-1.pdf", b"one")
        self.assertIsNotNone(ra.record(self.m, p, run_id="R1")); self.assertIsNone(ra.record(self.m, p, run_id="R1"))
        self.assertIsNotNone(ra.record(self.m, p, run_id="R2"))
        self.assertIsNotNone(ra.record(self.m, self.f("Call-Prep-2.pdf", b"two"), run_id="R1"))
        self.assertEqual(ra.summary(self.m)["assets"], 3)

    def test_link_that_arrives_later_is_recorded(self):
        p = self.f("Daily_Brief_x.pdf", b"a")
        ra.record(self.m, p, run_id="R1"); r = ra.record(self.m, p, run_id="R1", link="https://x.co/z.pdf")
        self.assertEqual(r["link"], "https://x.co/z.pdf")

    def test_scan_catches_assets_a_skill_wrote_without_recording(self):
        t0 = time.time() - 5
        self.f("Competitive_Intelligence_Report_x.pdf"); self.f("chart.png"); self.f("notes.md"); self.f("x.bin")
        made = ra.scan(self.m, self.out, "R7", since=t0)
        self.assertEqual(sorted(r["name"] for r in made), ["Competitive_Intelligence_Report_x.pdf", "chart.png", "notes.md"])
        s = ra.summary(self.m, "R7")
        self.assertEqual(s["by_skill"]["competitive-insights"]["assets"], 1)
        self.assertEqual(s["unassigned"], 2)                                    # visible, never dropped or guessed
        self.assertEqual(ra.scan(self.m, self.out, "R7", since=t0), [])         # re-scan adds nothing

    def test_scan_skips_files_older_than_the_run(self):
        p = self.f("old.pdf"); os.utime(p, (1, 1))
        self.assertEqual(ra.scan(self.m, self.out, "R", since=time.time() - 60), [])

    def test_explicit_skill_overrides_inference_and_unknown_skill_is_rejected(self):
        self.assertEqual(ra.record(self.m, self.f("report.pdf"), skill="follow-ups", run_id="R")["skill"], "follow-ups")
        with self.assertRaises(ValueError):
            ra.record(self.m, self.f("r2.pdf"), skill="nonsense", run_id="R")

    def test_torn_manifest_line_does_not_block_recording(self):
        open(self.m, "w").write('{"skill": "daily-brief"\n')
        self.assertIsNotNone(ra.record(self.m, self.f("Daily_Brief_y.pdf"), run_id="R"))

    def test_cli(self):
        self.f("Daily_Brief_z.pdf")
        r = run("roi_assets.py", "scan", "--manifest", self.m, "--run", "R", "--dir", self.out)
        self.assertEqual(json.loads(r.stdout)["recorded"], 1)
        self.assertEqual(run("roi_assets.py", "record", "--manifest", self.m, "--file", "/nonexistent.pdf").returncode, 2)


if __name__ == "__main__":
    unittest.main()

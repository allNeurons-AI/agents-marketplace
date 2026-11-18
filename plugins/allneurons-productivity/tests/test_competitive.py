"""Competitive Insights v1: profile, payload contract, PDF (margins + real links), delivery manifest, email, failure."""
import copy
import json
import os
import re
import unittest

from _common import ASSETS, ROOT, fixture, run, tmpdir
import competitive_profile as cp
import render_competitive as rc
import pdf_layout_check as plc
from pypdf import PdfReader

PROFILE = """company: Example Co
about: Makes widgets.
profile confirmed: 2026-10-01

entity: Example Co | example.test | Makes widgets.
entity: Example Gadgets | gadgets.example.test | Sister company that makes gadgets.

set A (Example Co): Widget Makers
- Acme: Big widget maker.
- Beta: Small widget maker.

set B (Example Gadgets): Gadget Makers
- Gamma: Gadgets.
"""


class Profile(unittest.TestCase):
    def test_parse_ok_and_staleness(self):
        import datetime as dt
        out, errs = cp.parse(PROFILE, dt.date(2026, 10, 6))
        self.assertEqual(errs, []); self.assertEqual([s["key"] for s in out["sets"]], ["A", "B"])
        self.assertEqual(len(out["sets"][0]["competitors"]), 2); self.assertFalse(out["stale"])
        self.assertTrue(cp.parse(PROFILE, dt.date(2027, 3, 1))[0]["stale"])

    def test_defects_are_all_reported(self):
        _, errs = cp.parse("about: x\n- Orphan: line\n")
        joined = " ".join(errs)
        for want in ("company", "set", "confirmed", "outside a set", "entity"):
            self.assertIn(want, joined)
        self.assertTrue(cp.parse(PROFILE.replace("set B", "set A"))[1])                 # duplicate key
        self.assertTrue(cp.parse(PROFILE.replace("Gamma: Gadgets.", ""))[1])            # empty set

    def test_the_shipped_example_profile_parses(self):
        txt = open(os.path.join(ROOT, "references", "competitive-profile-example.md"), encoding="utf-8").read().split("```")[1]
        out, errs = cp.parse(txt); self.assertEqual(errs, []); self.assertEqual(len(out["sets"]), 3); self.assertEqual(len(out["entities"]), 3)

    def test_nothing_company_specific_is_hardcoded_in_code(self):
        for f in ("competitive_profile.py", "render_competitive.py", "deliver_prepare.py", "email_compose.py"):
            src = open(os.path.join(ASSETS, f), encoding="utf-8").read().lower()
            for word in ("northwind", "acme corp"):
                self.assertNotIn(word, src, f)

    def test_cli_exit_codes(self):
        t = tmpdir(); open(t + "/p.md", "w").write(PROFILE)
        self.assertEqual(run("competitive_profile.py", "parse", "--in", t + "/p.md").returncode, 0)
        open(t + "/p.md", "w").write("nonsense")
        self.assertEqual(run("competitive_profile.py", "parse", "--in", t + "/p.md").returncode, 6)
        self.assertEqual(run("competitive_profile.py", "parse", "--in", t + "/missing.md").returncode, 2)


class Contract(unittest.TestCase):
    def d(self):
        return copy.deepcopy(fixture("competitive_insights.json"))

    def test_fixture_is_valid(self):
        self.assertEqual(rc.check(self.d()), [])

    def test_each_defect_is_named(self):
        cases = [(lambda d: d.pop("threats"), "missing key"), (lambda d: d["updates"].pop(0), "has no update entry"),
                 (lambda d: d["updates"][0].update(why=""), "why missing"), (lambda d: d["threats"][0].update(level="Severe"), "level"),
                 (lambda d: d["actions"][0].update(priority="Soon"), "priority"),
                 (lambda d: d["sources"][0].update(url="http://insecure.example.com"), "https"),
                 (lambda d: d["sources"][0].update(url="/home/claude/x.pdf"), "https"), (lambda d: d.update(sources=[]), "sources"),
                 (lambda d: d["updates"][0].update(set="Z"), "not one of"),
                 (lambda d: d.pop("company_summaries"), "missing key"), (lambda d: d["company_summaries"].pop(0), "no company_summaries entry"),
                 (lambda d: d["actions"][0].update(entity="Nobody"), "not in group")]
        for mutate, want in cases:
            d = self.d(); mutate(d)
            self.assertIn(want, " ".join(rc.check(d)), want)

    def test_a_quiet_week_is_valid_and_not_padded(self):
        d = self.d()
        for u in d["updates"]:
            u.pop("what", None); u.pop("why", None); u["quiet"] = True
        self.assertEqual(rc.check(d), [])


class Pdf(unittest.TestCase):
    def render(self, d):
        t = tmpdir(); i, o = t + "/in.json", t + "/o.pdf"
        json.dump(d, open(i, "w"), ensure_ascii=False)
        r = run("suite_pdf_design.py", "--kind", "competitive_insights", "--in", i, "--out", o)
        return r, o

    def test_renders_through_the_shared_entry_point(self):
        r, o = self.render(fixture("competitive_insights.json"))
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual(run("verify_pdf.py", o).returncode, 0)

    def test_every_source_is_a_real_link_annotation(self):
        d = fixture("competitive_insights.json"); _, o = self.render(d)
        self.assertEqual(rc.link_problems(o, [s["url"] for s in d["sources"]]), [])
        self.assertTrue(rc.link_problems(o, ["https://not-in-the-pdf.example.com/x"]))

    def test_sections_in_fixed_order(self):
        """v1.15.0 order: summary, product and market insights, your companies, tracked competitors, I-IV, sources last."""
        _, o = self.render(fixture("competitive_insights.json"))
        t = " ".join(re.sub(r"\s+", " ", p.extract_text()) for p in PdfReader(o).pages).upper()
        t = re.sub(r"(?<=\b\w) (?=\w\b)", "", t)            # letter-spaced capitals extract with gaps between letters
        order = ["EXECUTIVE SUMMARY", "KEY TAKEAWAYS", "PRODUCT AND MARKET INSIGHTS", "YOUR COMPANIES", "TRACKED COMPETITORS",
                 "I. KEY COMPETITOR UPDATES", "NEW ENTRANTS", "WHAT IS WORKING WELL", "II. COMPETITIVE THREATS", "III. OPPORTUNITIES FOR US",
                 "IV. RECOMMENDED ACTIONS", "SOURCES"]
        idx = [t.index(x) for x in order]
        self.assertEqual(idx, sorted(idx), dict(zip(order, idx)))
        self.assertEqual(t.rindex("SOURCES") > idx[-2], True)

    def test_the_report_is_numbered_and_every_status_is_a_tag(self):
        d = fixture("competitive_insights.json"); _, o = self.render(d)
        t = "\n".join(p.extract_text() for p in PdfReader(o).pages)
        for want in ("1. Clausewell", "2. Draftly", "QUIET", "Nothing material found this week.", "WATCH", "HIGH", "1. Pactline",
                     "What happened", "Key facts", "Why it matters to us", "Our proposed response", "Why it is a threat", "Potential impact", "Owner:"):
            self.assertIn(want, t, want)
        self.assertIn("01", t)                                                       # Product and market insights are numbered 01, 02 ...
        for tile in ("COMPANIES", "COMPETITORS", "COMPETITOR UPDATES", "HIGH THREATS", "OPPORTUNITIES"):
            self.assertIn(tile, t.upper())

    def test_bold_markers_become_bold_text_not_asterisks(self):
        d = fixture("competitive_insights.json"); d["company_summaries"][0]["what_matters"] = "**Clausewell** released Playbook Check on Sep 30, which compares a contract with approved clauses."
        r, o = self.render(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("**", "\n".join(p.extract_text() for p in PdfReader(o).pages))
        self.assertNotIn("**Clausewell** released", rc.markdown(d))                      # the backup drops the payload markers
        self.assertIn("Clausewell released Playbook Check", rc.markdown(d))

    def test_no_grey_text_and_labels_are_bold(self):
        _, o = self.render(fixture("competitive_insights.json"))
        raw = open(o, "rb").read().decode("latin-1")
        import re as _re
        for line in raw.splitlines():
            m = _re.fullmatch(r"([0-9.]+) ([0-9.]+) ([0-9.]+) rg", line.strip())
            if m and m.group(1) == m.group(2) == m.group(3) and 0.15 < float(m.group(1)) < 0.9:
                self.fail("a mid-grey fill colour is present: " + line)
        self.assertIn("Helvetica-Bold", raw)

    def test_actions_sorted_by_priority(self):
        _, o = self.render(fixture("competitive_insights.json"))
        t = "\n".join(p.extract_text() for p in PdfReader(o).pages)
        self.assertLess(t.index("Run a head-to-head accuracy test"), t.index("Re-check Pactline"))

    def test_long_content_stays_in_margins_and_unsupported_characters_do_not_crash(self):
        d = fixture("competitive_insights.json")
        d["company"] = "Northwind Traders International Holdings Incorporated " * 3
        d["executive_summary"].append("x" * 400 + " 日本語 → ✓")
        d["updates"][0]["what"] = "word " * 300
        d["sources"][0]["label"] = "A very long source label " * 12
        r, o = self.render(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(plc.check(o), [])

    def test_bad_payload_exits_6_with_reasons(self):
        d = fixture("competitive_insights.json"); d["sources"] = []
        r, _ = self.render(d)
        self.assertEqual(r.returncode, 6); self.assertIn("sources", r.stderr)


class Delivery(unittest.TestCase):
    def small(self):
        d = fixture("competitive_insights.json")
        for u in d["updates"]:
            u.pop("facts", None); u.pop("response", None)
        d["working_well"] = d["working_well"][:1]; d["market_trends"] = d["market_trends"][:1]; d["actions"] = d["actions"][:2]
        return d

    def prepare(self, *extra, small=False):
        t = tmpdir(); json.dump(self.small() if small else fixture("competitive_insights.json"), open(t + "/in.json", "w"), ensure_ascii=False)
        r = run("deliver_prepare.py", "--kind", "competitive_insights", "--in", t + "/in.json", "--out-dir", t + "/out",
                "--name", "Competitive_Intelligence_Report_2026-10-05", *extra)
        return r, t

    def test_manifest_for_a_normal_report(self):
        r, t = self.prepare()
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertIn(m["tier"], ("full", "flate", "squeeze")); self.assertEqual(len(m["parts"]), 1)
        self.assertLessEqual(m["parts"][0]["bytes"], 22500)       # the size cap (the largest file that can still be typed into an upload as base64)
        self.assertLessEqual(m["parts"][0]["pages"], 6)           # and the 6-page cap
        self.assertTrue(m["parts"][0]["filename"].endswith(".pdf"))

    def test_heavy_report_stays_within_six_pages_and_the_size_cap(self):
        t = tmpdir(); json.dump(fixture("competitive_heavy.json"), open(t + "/in.json", "w"), ensure_ascii=False)
        r = run("deliver_prepare.py", "--kind", "competitive_insights", "--in", t + "/in.json", "--out-dir", t + "/out", "--name", "heavy")
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertLessEqual(m["parts"][0]["bytes"], 22500); self.assertLessEqual(m["parts"][0]["pages"], 6)

    def test_four_companies_and_24_competitors_fit_six_pages_with_nothing_cut(self):
        """The shape of a real week: 4 companies, 24 tracked competitors (most quiet), 5 summaries, 4 entrants, 14 sources.
        It must come out as ONE formatted PDF of at most 6 pages with every word kept: no squeeze, no left-out list items."""
        d = fixture("competitive_wide.json")
        t = tmpdir(); json.dump(d, open(t + "/in.json", "w"), ensure_ascii=False)
        r = run("deliver_prepare.py", "--kind", "competitive_insights", "--in", t + "/in.json", "--out-dir", t + "/out", "--name", "wide")
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads(r.stdout.strip().splitlines()[-1])
        p = m["parts"][0]
        self.assertLessEqual(p["pages"], 6); self.assertLessEqual(p["bytes"], 22500)
        self.assertIsNone(m.get("squeeze"), "the squeeze loop cut content: %s" % (m.get("squeeze") or {}).get("note"))
        text = re.sub(r"\s+", " ", " ".join((pg.extract_text() or "") for pg in PdfReader(p["pdf"]).pages))
        for u in d["updates"]:
            self.assertIn(u["competitor"], text)
            if not u.get("quiet"):
                self.assertIn(re.sub(r"\s+", " ", u["what"].replace("**", ""))[:60], text)
        for k in ("new_entrants", "working_well", "threats", "opportunities", "actions"):
            for it in d[k]:
                self.assertIn(re.sub(r"\s+", " ", str(it.get("name") or it.get("title") or it.get("action"))), text, k)
        for sct in d["sources"]:
            self.assertIn(sct["label"][:40], text)
        uris = {str((a.get_object().get("/A") or {}).get("/URI")) for pg in PdfReader(p["pdf"]).pages for a in (pg.get("/Annots") or [])}
        self.assertTrue({sct["url"] for sct in d["sources"]} <= uris)

    def test_over_the_paste_ceiling_stays_one_compressed_pdf(self):
        r, t = self.prepare("--ceiling", "9000", "--budget", "0", small=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(m["tier"], "flate"); self.assertEqual(len(m["parts"]), 1)
        p = m["parts"][0]
        self.assertEqual(p["paste_mode"], "base64"); self.assertTrue(os.path.exists(p["b64"]))
        from pypdf import PdfReader
        uris = {str((a.get_object().get("/A") or {}).get("/URI")) for pg in PdfReader(p["pdf"]).pages for a in (pg.get("/Annots") or [])}
        self.assertTrue({s["url"] for s in fixture("competitive_insights.json")["sources"]} <= uris)   # every source still a link

    def test_rung_shrinks_the_same_single_pdf(self):
        r, t = self.prepare("--rung", "3", "--budget", "0", small=True)
        m = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(m["tier"], "digest2"); self.assertEqual(len(m["parts"]), 1)

    def test_thin_content_fails_the_depth_gate_with_a_useful_message(self):
        t = tmpdir(); d = fixture("competitive_insights.json"); d["updates"][0]["what"] = "Shipped a feature."
        json.dump(d, open(t + "/in.json", "w"))
        r = run("deliver_prepare.py", "--kind", "competitive_insights", "--in", t + "/in.json", "--out-dir", t + "/o", "--name", "x")
        self.assertEqual(r.returncode, 6); self.assertIn("write at least 25", r.stderr)

    def test_invalid_payload_exits_6_before_rendering(self):
        t = tmpdir(); d = fixture("competitive_insights.json"); d["updates"] = []
        json.dump(d, open(t + "/in.json", "w"))
        r = run("deliver_prepare.py", "--kind", "competitive_insights", "--in", t + "/in.json", "--out-dir", t + "/o", "--name", "x")
        self.assertEqual(r.returncode, 6)

    def test_other_kinds_are_unaffected(self):
        t = tmpdir(); json.dump(fixture("brief_many_items.json"), open(t + "/b.json", "w"))
        r = run("deliver_prepare.py", "--kind", "daily_brief", "--in", t + "/b.json", "--out-dir", t + "/o", "--name", "b")
        self.assertEqual(r.returncode, 0, r.stderr)


class Wiring(unittest.TestCase):
    def test_skill_files_and_onboarding_schedule(self):
        for f in ("SKILL.md", "qa-checklist.md", "competitive-insights-pdf-design.md"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, "skills", "competitive-insights", f)), f)
        onb = open(os.path.join(ROOT, "skills", "onboarding", "SKILL.md"), encoding="utf-8").read()
        self.assertIn("`competitive-insights` | Weekly, Monday | 7:00 AM | `0 7 * * 1`", onb)
        self.assertIn("allNeurons Productivity Competitive Insights", onb)
        skill = open(os.path.join(ROOT, "skills", "competitive-insights", "SKILL.md"), encoding="utf-8").read()
        self.assertIn("name: competitive-insights", skill)
        for need in ("connector-prerequisite.md", "[Failed]", "bodyType", "roi_assets.py", "deliver_prepare.py"):
            self.assertIn(need, skill)


if __name__ == "__main__":
    unittest.main()


class GroupCoverage(unittest.TestCase):
    """v1.11.0: every associated company must be analysed; none can be silently left out."""

    def test_parser_rejects_a_company_with_no_competitor_set(self):
        out, errs = cp.parse(PROFILE.replace("set B (Example Gadgets)", "set B (Example Co)"))
        self.assertTrue(any("Example Gadgets" in e and "no competitor set" in e for e in errs), errs)

    def test_parser_rejects_a_set_naming_an_unlisted_company(self):
        _, errs = cp.parse(PROFILE.replace("set B (Example Gadgets)", "set B (Unlisted Sibling)"))
        self.assertTrue(any("not listed as an entity" in e for e in errs), errs)

    def test_old_profile_without_entities_is_flagged_for_rediscovery(self):
        old = "company: X\nabout: y\nprofile confirmed: 2026-10-01\n\nset A: M\n- Acme: a\n"
        _, errs = cp.parse(old)
        self.assertTrue(any("entity" in e for e in errs), errs)

    def test_pdf_gate_fails_when_a_group_company_has_no_set(self):
        d = fixture("competitive_insights.json")
        d["group"].append({"name": "Forgotten Sibling", "domain": "sibling.example", "description": "A sister company nobody analysed."})
        errs = rc.check(d)
        self.assertTrue(any("Forgotten Sibling" in e and "no competitor set" in e for e in errs), errs)

    def test_pdf_gate_requires_group_and_valid_entity(self):
        d = fixture("competitive_insights.json"); d.pop("group")
        self.assertTrue(any("group" in e for e in rc.check(d)))
        d = fixture("competitive_insights.json"); d["sets"][0]["entity"] = "Nobody"
        self.assertTrue(any("not in group" in e for e in rc.check(d)))

    def test_report_names_every_company_covered(self):
        t = tmpdir(); d = fixture("competitive_insights.json")
        out = t + "/r.pdf"; rc.draw(d, out)
        txt = " ".join((p.extract_text() or "") for p in PdfReader(out).pages)
        for g in d["group"]:
            self.assertIn(g["name"], txt)
        self.assertIn("COMPANIES", txt.upper())

    def test_skill_never_asks_and_discovers_siblings(self):
        src = open(os.path.join(ROOT, "skills", "competitive-insights", "SKILL.md"), encoding="utf-8").read()
        self.assertIn("Zero questions on a scheduled run", src)
        self.assertNotIn("ask exactly one question", src.lower())
        for need in ("sibling", "subsidiar", "search_people", "domain census", "two independent signals"):
            self.assertIn(need, src)

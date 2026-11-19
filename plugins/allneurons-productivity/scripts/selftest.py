#!/usr/bin/env python3
"""Static self-test for the plugin. Run from anywhere: python3 scripts/selftest.py

Checks that version numbers agree, required files exist, no skill tells anyone to
attach or upload the .md, every skill has a checklist and anti-patterns, and the
PDF gate and renderers work on a sample payload. Exit 0 = pass, 1 = fail.
"""
import json, os, re, subprocess, sys, tempfile
os.environ["SUITE_BRAIN"] = "0"   # the run memory must not change what the tests expect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errs, ok = [], []


def check(cond, msg):
    (ok if cond else errs).append(msg)


def read(rel):
    p = os.path.join(ROOT, rel)
    return open(p, encoding="utf-8").read() if os.path.isfile(p) else ""


manifest = json.loads(read(".claude-plugin/plugin.json") or "{}")
ver = manifest.get("version", "")
check(manifest.get("name") == "allneurons-productivity", "plugin name is allneurons-productivity")
check(re.fullmatch(r"\d+\.\d+\.\d+", ver or ""), f"plugin.json version is semver ({ver})")

cl = read("CHANGELOG.md")
m = re.search(r"^## (\d+\.\d+\.\d+)", cl, re.M)
check(bool(m) and m.group(1) == ver, f"CHANGELOG top entry matches plugin.json ({m.group(1) if m else 'none'} vs {ver})")
check(f"v{ver}" in read("README.md") or ver in read("README.md"), "README mentions the current version")
check("## Install" in read("README.md"), "README documents installation")

skills = ["daily-brief", "call-prep", "follow-ups", "competitive-insights", "onboarding", "connectors"]
for s in skills:
    body = read(f"skills/{s}/SKILL.md")
    check(bool(body), f"{s}/SKILL.md exists")
    check("Anti-patterns (do not)" in body, f"{s} has an anti-patterns section")
    if s not in ("onboarding", "connectors"):
        check(bool(read(f"skills/{s}/qa-checklist.md")), f"{s}/qa-checklist.md exists")

for rel in ["config.md", "tests/test-prompts.md", "references/data-dictionary.md",
            "references/run-policy.md",
            "assets/verify_pdf.py", "assets/render_brief.py",
            "assets/render_call_prep.py"]:
    check(os.path.isfile(os.path.join(ROOT, rel)), f"{rel} exists")

# Onboarding's new Call Prep preferences card and Call Prep's prep-delivery
# gating must agree on vocabulary, or the settings file one writes is the
# settings file the other silently ignores.
onb_body = read("skills/onboarding/SKILL.md")
cp_body = read("skills/call-prep/SKILL.md")
check("Call Prep meeting scope" in onb_body, "onboarding documents the Call Prep meeting-scope card")
check("prep scope:" in onb_body, "onboarding writes prep scope: to the settings file")
check("There is no delivery question" in onb_body, "onboarding no longer asks calendar-vs-email delivery")
check("Never write a `prep delivery:` line" in onb_body, "onboarding never writes a prep delivery line")
check("PART 4a" not in cp_body and "THE EMAIL DIGEST" not in cp_body, "call-prep has no email-digest part")
check(not os.path.exists(os.path.join(ROOT, "skills/call-prep/call-prep-email-format.md")), "call-prep digest format file is gone")
check("external and internal" in cp_body and "Step 2b" in cp_body, "call-prep applies the external-and-internal scope in Step 2b")
check("bodyType: \"html\"" in cp_body and "bodyType: \"html\"" in read("skills/call-prep/call-prep-card-format.md"),
      "call-prep requires bodyType html on every prep-block create/update, with read-back")
check("No date or meta line at the top" in read("skills/call-prep/call-prep-card-format.md"), "call-prep card has no leading date/meta line")
# every email template: no leading date line
for rel in ["skills/daily-brief/daily-brief-email-format.md", "skills/follow-ups/follow-ups-email-format.md"]:
    body = read(rel)
    check("<p><em>{Weekday, Month D}</em></p>" not in body and "Friday, September 25" not in body, f"{rel} has no leading date line")
fu = read("skills/follow-ups/follow-ups-email-format.md")
check("No second header" in fu and "{Headline" not in fu and "<strong>{N} new</strong>" not in fu, "follow-ups body has no date line, headline or stat line")
db = read("skills/daily-brief/SKILL.md")
check("Phase 2 — the read phase" in db and "read_resource" in db and "Do not search for `?`" in db, "daily-brief has a mandatory read phase and no '?' sweeps")
check("snippets only" not in db, "daily-brief no longer reads email 'from snippets only'")

# A real run once hardcoded "external calls" / "do not email" into the stored
# scheduled-task prompt. Guard against that regression.
check("never hardcode a scope or a delivery mode into this task" in onb_body,
      "onboarding's Call Prep mode-line template defers to the settings file")
check("The mode line is never a source of scope or delivery mode" in cp_body or "mode line is never a source of scope" in cp_body.lower(),
      "call-prep explicitly ignores any scope/delivery wording in a stale mode line")

# A real run once resolved a skill name to an unrelated plugin's similarly-
# named skill (a wrong-skill bug), because the loose "contains token" fallback
# had no namespace restriction. Guard against that regression.
check("recognized family" in onb_body,
      "onboarding's skill-name resolution restricts its loose fallback to a recognized namespace family")
check("Never match rule (d) against a candidate outside that namespace" in onb_body,
      "onboarding's stored-task resolution preamble excludes out-of-namespace candidates from the loose fallback")

# No instruction may say to attach/upload the markdown working copy.
bad = re.compile(r"(attach|upload|link|send)[^\n]{0,40}(?<![\w-])\.md\b", re.I)
neg = re.compile(r"never|not |no |don't|do not|without", re.I)
for dp, _, fs in os.walk(ROOT):
    if "tests" in dp or "scripts" in dp:
        continue
    for f in fs:
        if not f.endswith(".md") or f in ("CHANGELOG.md", "README.md"):
            continue
        for i, line in enumerate(open(os.path.join(dp, f), encoding="utf-8"), 1):
            if bad.search(line) and not neg.search(line):
                errs.append(f"{os.path.relpath(os.path.join(dp, f), ROOT)}:{i} may tell a run to attach/upload the .md")

# Scheduled tasks must never be told to carry a version.
onb = read("skills/onboarding/SKILL.md")
check("never update, recreate or delete" in onb.lower() or "never update" in onb.lower(), "onboarding forbids task rewrites in scheduled runs")

# Functional: gate + renderer on a sample payload.
try:
    with tempfile.TemporaryDirectory() as t:
        payload = {"title": "Daily Brief — Test", "headline": "Selftest.", "stats": {"Conflicts": 0},
                   "meetings": [], "conflicts": [], "due_today": [], "needs_attention": [],
                   "resolved": [], "worth_double_checking": [], "sources": [{"label": "Selftest"}], "date": "2026-01-05"}
        pj, pdf = os.path.join(t, "b.json"), os.path.join(t, "Daily_Brief_2026-01-05.pdf")
        json.dump(payload, open(pj, "w"))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "assets/render_brief.py"), "--in", pj, "--out", pdf],
                           capture_output=True, text=True, timeout=120)
        if r.returncode == 3:
            print("SKIP: reportlab missing, functional checks skipped")
        else:
            check(r.returncode == 0, f"render_brief.py exit 0 (got {r.returncode}) {r.stderr.strip()[:120]}")
            g = subprocess.run([sys.executable, os.path.join(ROOT, "assets/verify_pdf.py"), pdf],
                               capture_output=True, text=True)
            check(g.returncode == 0 and '"ok": true' in g.stdout, "verify_pdf.py passes the rendered PDF")
            try:
                parsed = json.loads(g.stdout.strip())
                check(parsed.get("safe_to_attach") is True, "verify_pdf.py reports safe_to_attach:true for a small real PDF")
            except Exception as e:
                errs.append(f"could not parse verify_pdf.py JSON output: {e}")
            md = pdf[:-4] + ".md"
            g2 = subprocess.run([sys.executable, os.path.join(ROOT, "assets/verify_pdf.py"), md],
                                capture_output=True, text=True)
            check(g2.returncode == 1, "verify_pdf.py rejects the .md working copy")
            fake = os.path.join(t, "fake.pdf")
            open(fake, "w").write("# markdown pretending\n" * 30)
            g3 = subprocess.run([sys.executable, os.path.join(ROOT, "assets/verify_pdf.py"), fake],
                                capture_output=True, text=True)
            check(g3.returncode == 1, "verify_pdf.py rejects a text file renamed .pdf")
except Exception as e:
    errs.append(f"functional check crashed: {e}")

# Functional: ambiguous meeting times are rejected as a named FORMAT ERROR,
# never silently mis-timed (the customer-reported "evening shown as morning" bug).
try:
    sys.path.insert(0, os.path.join(ROOT, "assets"))
    import importlib
    rb = importlib.import_module("render_brief")
    ambiguous_raised = False
    try:
        rb.parse_time("9:15", hint=None)
    except ValueError:
        ambiguous_raised = True
    check(ambiguous_raised, "parse_time rejects a bare ambiguous time with no am/pm anywhere")
    check(rb.parse_time("9:15 pm") == rb.parse_time("21:15"), "parse_time agrees on pm vs 24h for the same instant")
    gate_errs = []
    rb.check_meetings([{"label": "Standup", "start": "9:15", "end": "9:35"}], gate_errs)
    check(bool(gate_errs), "check_meetings collects the ambiguous time as a FORMAT ERROR before layout")
    clean_errs = []
    rb.check_meetings([{"label": "Client call 9:15 pm", "start": "9:15 pm", "end": "9:35 pm"}], clean_errs)
    check(not clean_errs, "check_meetings passes an unambiguous meeting with no errors")
except Exception as e:
    errs.append(f"ambiguous-time regression check crashed: {e}")

# Functional: the "malformed number with two decimal points" false positive.
# A real production run's brief text contained a dotted version number
# ("6.0.6") and suite_pdf.verify() flagged a perfectly valid PDF as
# corrupted, because its regex scanned raw content-stream bytes without
# distinguishing visible text (inside a (...)Tj operator) from a real
# numeric drawing operand. Confirmed reproducible, then fixed by stripping
# literal-string contents before running the check.
try:
    sys.path.insert(0, os.path.join(ROOT, "assets"))
    import importlib
    core = importlib.import_module("suite_pdf")
    check(hasattr(core, "_strip_pdf_string_literals"), "suite_pdf.py defines _strip_pdf_string_literals")

    # A dotted version number inside a text-showing operator must not survive
    # stripping as something a numeric regex would match.
    text_stream = b"q\nBT\n(Update dependency to 6.0.6 before release) Tj\nET\nQ\n"
    stripped = core._strip_pdf_string_literals(text_stream)
    check(re.search(rb"(?<![\w/])\.?\d*\.\d+\.\d", stripped) is None,
          "a dotted version number inside PDF text is no longer flagged as a malformed number")
    check(len(stripped) == len(text_stream), "_strip_pdf_string_literals preserves byte length (blanks, never removes)")

    # An escaped paren inside the string must not desynchronize the depth
    # counter and leak real content out as "operator" bytes.
    esc_stream = b"q\nBT\n(a \\(1.2.3\\) note) Tj\nET\nQ\n"
    stripped_esc = core._strip_pdf_string_literals(esc_stream)
    check(re.search(rb"(?<![\w/])\.?\d*\.\d+\.\d", stripped_esc) is None,
          "an escaped-paren version number inside text is also not flagged")

    # A GENUINE malformed coordinate (outside any string literal) must still
    # be caught — the fix narrows the check, it does not disable it.
    corrupt_stream = b"q\n1 0 0 1 0 0 cm\n420.18778.96 300 l\nS\nQ\n"
    stripped_corrupt = core._strip_pdf_string_literals(corrupt_stream)
    check(re.search(rb"(?<![\w/])\.?\d*\.\d+\.\d", stripped_corrupt) is not None,
          "a genuine run-together malformed coordinate outside any text is still caught")

    # End-to-end: a real rendered brief whose text contains a dotted version
    # number must pass verify() cleanly (exit 0), not fail with exit 4.
    with tempfile.TemporaryDirectory() as t2:
        ver_payload = {"title": "Daily Brief — Version Regression", "headline": "Testing 6.0.6 in body text.",
                       "stats": {"Needs attention": 1}, "meetings": [], "conflicts": [], "due_today": [],
                       "needs_attention": [{"action": "Update dependency to 6.0.6 before release",
                                             "body": "The library was bumped to version 6.0.6 last night.",
                                             "owner": "Dev", "by_when": "2026-01-06", "source": "Jira", "status": "Open"}],
                       "resolved": [], "worth_double_checking": [], "sources": [], "date": "2026-01-05"}
        vj = os.path.join(t2, "v.json")
        vpdf = os.path.join(t2, "v.pdf")
        json.dump(ver_payload, open(vj, "w"))
        rv = subprocess.run([sys.executable, os.path.join(ROOT, "assets/suite_pdf_design.py"),
                              "--kind", "daily_brief", "--in", vj, "--out", vpdf],
                             capture_output=True, text=True, timeout=120)
        if rv.returncode == 3:
            print("SKIP: reportlab missing, version-number regression check skipped")
        else:
            check(rv.returncode == 0,
                  f"a brief containing a dotted version number in its text renders and verifies clean (got exit {rv.returncode}) {rv.stderr.strip()[:200]}")
except Exception as e:
    errs.append(f"malformed-number false-positive regression check crashed: {e}")

# PDF delivery reliability: size-based attach/link routing (safe_to_attach).
rp = read("references/run-policy.md")
check("safe_to_attach" in read("skills/call-prep/SKILL.md"), "call-prep SKILL.md references safe_to_attach")
vp_src = read("assets/verify_pdf.py")
check("SAFE_ATTACH_CEILING_BYTES" in vp_src, "verify_pdf.py defines SAFE_ATTACH_CEILING_BYTES")
check("classify_size" in vp_src, "verify_pdf.py defines classify_size")
check("UPLOAD_CEILING_BYTES" in vp_src, "verify_pdf.py defines UPLOAD_CEILING_BYTES")
check("classify_upload_size" in vp_src, "verify_pdf.py defines classify_upload_size")
check("safe_to_upload" in vp_src, "verify_pdf.py's output JSON reports safe_to_upload")

try:
    sys.path.insert(0, os.path.join(ROOT, "assets"))
    import importlib
    vp = importlib.import_module("verify_pdf")
    check(vp.classify_size(1000) is True, "a 1KB size classifies as safe to attach")
    check(vp.classify_size(vp.SAFE_ATTACH_CEILING_BYTES) is True, "exactly the ceiling classifies as safe (inclusive boundary)")
    check(vp.classify_size(vp.SAFE_ATTACH_CEILING_BYTES + 1) is False, "one byte over the ceiling classifies as unsafe to attach")
    check(vp.classify_size(50 * 1024 * 1024) is False, "a 50MB size classifies as unsafe to attach (large-PDF regression guard)")
    check(vp.classify_upload_size(1000) is True, "a 1KB size classifies as safe to upload")
    check(vp.classify_upload_size(vp.UPLOAD_CEILING_BYTES) is True, "exactly the upload ceiling classifies as safe (inclusive boundary)")
    check(vp.classify_upload_size(vp.UPLOAD_CEILING_BYTES + 1) is False, "one byte over the upload ceiling classifies as unsafe to upload")
    check(vp.UPLOAD_CEILING_BYTES == 1024 * 1024, "the upload ceiling matches the connected SharePoint/OneDrive tool's actual 1MB content limit")
except Exception as e:
    errs.append(f"classify_size/classify_upload_size regression check crashed: {e}")

# Microsoft 365 is the sole mandatory connector for this deployment — Gmail,
# Google Calendar, Google Drive and Box must never satisfy a mandatory role.
cpr = read("references/connector-prerequisite.md")
daily_body = read("skills/daily-brief/SKILL.md")
followups_body = read("skills/follow-ups/SKILL.md")
readme = read("README.md")
check("Microsoft 365" in cpr and "Microsoft 365" in onb_body,
      "connector-prerequisite.md and onboarding both document the Microsoft-365-only requirement")
check("Microsoft 365" in manifest.get("description", ""), "plugin.json's description names Microsoft 365")
check("gmail_*" in read("references/provider-map.md") and "outlook_*" in read("references/provider-map.md"), "provider-map.md maps both Gmail and Outlook tool prefixes")
check("SharePoint/OneDrive" in rp or "SharePoint / OneDrive" in rp, "run-policy.md uses the SharePoint/OneDrive role name")
check("SharePoint/OneDrive" in cpr or "SharePoint / OneDrive" in cpr, "connector-prerequisite.md uses the SharePoint/OneDrive role name")
check("1,048,576 bytes" in rp and "no chunked or split upload" in rp,
      "run-policy.md states the connected SharePoint/OneDrive tool's real 1MB-no-chunking limit, not a hypothetical Graph figure")
check("do not attempt to hand-split it" in rp or "forbids it" in rp,
      "run-policy.md forbids manually splitting an oversized PDF to work around the upload ceiling")
check("safe_to_upload" in rp, "run-policy.md references safe_to_upload for the real upload-size gate")

# A real scheduled run concluded a tiny 6-page PDF couldn't be uploaded because
# "the tool only takes file content pasted into the call" and gave up — the
# procedure for reading the .b64 file and passing it as contentBase64 was
# documented, but never spelled out explicitly enough to stop that conclusion.
check("read the entire contents of the" in rp and "contentBase64" in rp,
      "run-policy.md explicitly tells the run to read the .b64 file and pass it as contentBase64")
check("is itself the bug" in rp,
      "run-policy.md explicitly forbids concluding an upload is impossible because content must be read and passed as text")
check("so I couldn't pass it the 6-page file" in rp,
      "run-policy.md documents the real production incident this fix addresses")
check("never written to the person, because this case must not reach them" in rp,
      "run-policy.md's fix-line table guards against reporting a fabricated capability gap instead of actually calling the tool")
check("The size of the base64 text is never a reason to skip the attempt" in rp,
      "run-policy.md forbids skipping the upload over a fear of base64 transcription risk, since expectedBytes and the post-upload size check already cover it")
check("Google Workspace" in rp and "provider-map.md" in rp, "run-policy.md is dual-provider and points at provider-map.md")

# The live renderer entry point must be named correctly everywhere, so a
# future fix never lands in the dead suite_pdf.py drawing code by mistake.
check("suite_pdf_design.py" in rp and "now-unreachable drawing functions" in rp,
      "run-policy.md correctly names suite_pdf_design.py as the live entry point")



# Daily Brief's prose section order must match the renderer's real draw
# order (needs_attention before conflicts), and the removed timeline bar
# must not still be mentioned as current behavior.
check("Needs attention" in daily_body and "Conflicts" in daily_body,
      "daily-brief SKILL.md names both Needs attention and Conflicts")
na_idx, conf_idx = daily_body.find("Needs attention"), daily_body.find("Conflicts")
check(0 <= na_idx < conf_idx, "daily-brief SKILL.md's prose lists Needs attention before Conflicts, matching the renderer")

# The email template, not just SKILL.md's prose, must put Today's meetings
# first — a real gap found by independent review: the renderer and SKILL.md
# agreed, but the email template had drifted and put meetings after the
# actionable sections.
email_fmt = read("skills/daily-brief/daily-brief-email-format.md")
meet_idx, na_email_idx = email_fmt.find("Today's meetings"), email_fmt.find("Needs attention")
check(0 <= meet_idx < na_email_idx, "daily-brief-email-format.md's template puts Today's meetings before Needs attention")

# Onboarding owns exactly its own three canonical task IDs — simplified
# from an earlier multi-brand legacy-ID migration design — and must flag an
# unrecognized same-looking task rather than touch or ignore it, guarding
# against a silently-surviving duplicate scheduled task.
check("exactly four scheduled task IDs" in onb_body,
      "onboarding states plainly that it owns exactly four canonical task IDs and nothing else")
check("doesn't recognize it and won't touch it" in onb_body or "found another scheduled task that looks like it might send" in onb_body.lower(),
      "onboarding flags an unrecognized similarly-named scheduled task as a possible duplicate source")
check("never auto-delete an unrecognized task" in onb_body.lower(),
      "onboarding never auto-deletes a task it doesn't recognize")

# Every email this plugin sends must carry the installed plugin version in
# its closing line, matching Daily Brief's own closing line exactly — not
# just the normal-run emails, but Call Prep's digest and failure emails,
# Follow-Ups' summary and early-exit emails, and the one-time [Blocked] email.
followups_fmt = read("skills/follow-ups/follow-ups-email-format.md")
VERSION_LINE = "allNeurons Productivity v{installed version}"
check(followups_fmt.count("allNeurons Productivity v{installed version}") >= 2,
      "follow-ups-email-format.md's full-report AND early-exit templates both carry the version")
check("allNeurons Productivity v<installed version>" in cp_body,
      "call-prep SKILL.md's failure closing-line spec carries the version")
check("allNeurons Productivity v<installed version>" in followups_body,
      "follow-ups SKILL.md's closing-line spec carries the version")
check("allNeurons Productivity v<installed version>" in cpr,
      "connector-prerequisite.md's [Blocked] email spec carries the version")
check("no plugin version" not in followups_body.lower() and "no version" not in followups_fmt.lower(),
      "follow-ups no longer bans the plugin version from its email")
check("every single email or chat reply this plugin produces, with no exception" in rp,
      "run-policy.md §14 states the version belongs in every email with no exception")

# v1.9.1 -- PDFs must stay small enough to upload by pasting contentBase64.
import subprocess, tempfile, base64 as _b64
rb_src = read("assets/render_brief.py")
check("TTFont" not in rb_src and "Helvetica" in rb_src, "renderer uses built-in Helvetica only")
vp = read("assets/verify_pdf.py")
check("safe_to_paste" in vp and "paste_mode" in vp and "ascii_only" in vp, "verify_pdf.py reports safe_to_paste / paste_mode / ascii_only")
check("The PDF delivery flow" in rp and "contentBase64" in rp, "run-policy.md has the single PDF delivery flow")
check("The PDF delivery flow" in read("skills/daily-brief/SKILL.md") and "The PDF delivery flow" in read("skills/call-prep/SKILL.md"),
      "Daily Brief and Call Prep both point at the single delivery flow")
try:
    _d = tempfile.mkdtemp()
    _j = os.path.join(_d, "b.json"); _p = os.path.join(_d, "b.pdf")
    json.dump({"title":"Daily Brief","headline":"x","stats":{"Conflicts":0,"Due today & overdue":0,"Needs attention":0,"Resolved":0},
               "meetings":[],"conflicts":[],"due_today":[],"worth_double_checking":[],"needs_attention":[],"resolved":[],"sources":[]}, open(_j,"w"))
    _env = dict(os.environ)
    subprocess.run([sys.executable, os.path.join(ROOT,"assets","suite_pdf_design.py"),"--kind","daily_brief","--in",_j,"--out",_p], env=_env, check=True, capture_output=True)
    _n = os.path.getsize(_p)
    _raw = open(_p, "rb").read()
    check(all(b < 128 and b != 0 for b in _raw), "default render is pure ASCII (uploadable as plain text)")
    check(_n <= 30000, f"default render is pasteable ({_n} bytes)")
    # Call Prep uses the same renderer and must also come out as pasteable ASCII.
    _cp = os.path.join(_d, "cp.pdf")
    subprocess.run([sys.executable, os.path.join(ROOT,"assets","suite_pdf_design.py"),"--kind","call_prep","--in",
                    os.path.join(ROOT,"tests","fixtures","call_prep_sample.json"),"--out",_cp], env=_env, check=True, capture_output=True)
    _craw = open(_cp, "rb").read()
    check(all(b < 128 and b != 0 for b in _craw) and len(_craw) <= 30000, f"Call Prep render is pure ASCII and pasteable ({len(_craw)} bytes)")
    _g = json.loads(subprocess.run([sys.executable, os.path.join(ROOT,"assets","verify_pdf.py"), _cp], capture_output=True, text=True).stdout)
    check(_g.get("paste_mode") == "content" and _g.get("readback_phrases"), "gate reports paste_mode=content and read-back phrases")
    check("readback_phrases" in rp and "read_resource" in rp, "run-policy.md requires the post-upload read-back")
except Exception as _e:
    check(False, f"default render produced a pasteable PDF ({_e})")

check("flate" in rp and "design_problems" in rp and "stopped, denied, blocked" in rp, "run-policy.md has the full -> flate (same design, compressed) -> inline upload ladder")
check("attach only when the mail tool can" in rp.lower() or "link first" in rp.lower(), "run-policy.md: link first, attach only when the mail tool can")
check("deliver_prepare.py" in read("skills/daily-brief/SKILL.md") and "deliver_prepare.py" in read("skills/call-prep/SKILL.md"),
      "Daily Brief and Call Prep both deliver through the size-fit tier chain (deliver_prepare.py), lite included")
check("Attach as `Daily_Brief" not in read("skills/daily-brief/SKILL.md"), "Daily Brief no longer says to attach the PDF")
# lite renderer: same payload, much smaller, still passes the gate (both kinds)
try:
    _env2 = dict(_env); _env2["SUITE_PDF_LITE"] = "1"
    _lb = os.path.join(_d, "lb.pdf"); _lc = os.path.join(_d, "lc.pdf")
    subprocess.run([sys.executable, os.path.join(ROOT,"assets","suite_pdf_design.py"),"--kind","call_prep","--in",
                    os.path.join(ROOT,"tests","fixtures","call_prep_sample.json"),"--out",_lc], env=_env2, check=True, capture_output=True)
    _full = os.path.getsize(_cp); _lite = os.path.getsize(_lc)
    check(_lite < _full * 0.6, f"lite Call Prep PDF is much smaller than the full one ({_lite} vs {_full} bytes)")
    check(all(b < 128 and b != 0 for b in open(_lc, "rb").read()), "lite PDF is pure ASCII")
except Exception as _e:
    check(False, f"lite renderer works ({_e})")
# v1.9.5: repeated shapes are written once as Form XObjects (far less repetition in the text the model must re-type)
try:
    _big = json.load(open(os.path.join(ROOT, "tests", "fixtures", "brief_many_items.json")))
    _bj = os.path.join(_d, "big.json"); json.dump(_big, open(_bj, "w"))
    _pr = os.path.join(_d, "reuse.pdf"); _pi = os.path.join(_d, "inline.pdf")
    subprocess.run([sys.executable, os.path.join(ROOT,"assets","suite_pdf_design.py"),"--kind","daily_brief","--in",_bj,"--out",_pr], env=_env, check=True, capture_output=True)
    _env3 = dict(_env); _env3["SUITE_PDF_REUSE"] = "0"
    subprocess.run([sys.executable, os.path.join(ROOT,"assets","suite_pdf_design.py"),"--kind","daily_brief","--in",_bj,"--out",_pi], env=_env3, check=True, capture_output=True)
    _r = open(_pr, "rb").read(); _i = open(_pi, "rb").read()
    _curves = lambda b: sum(1 for ln in b.split(b"\n") if ln.rstrip().endswith(b" c"))
    check(b"/Subtype /Form" in _r and b"/Subtype /Form" not in _i, "default render re-uses shapes as Form XObjects")
    check(_curves(_r) < _curves(_i) * 0.4, f"shape reuse cuts curve lines sharply ({_curves(_r)} vs {_curves(_i)})")
    check(all(b < 128 and b != 0 for b in _r), "reuse render is still pure ASCII")
except Exception as _e:
    check(False, f"shape-reuse render works ({_e})")
# v1.9.6: lossless compaction (pdf_minify) -- smaller, same pages, same extracted text; pixels compared when pdfium exists
try:
    _env4 = dict(_env); _env4["SUITE_PDF_MINIFY"] = "0"
    _mn = os.path.join(_d, "min.pdf"); _nm = os.path.join(_d, "nomin.pdf")
    subprocess.run([sys.executable, os.path.join(ROOT,"assets","suite_pdf_design.py"),"--kind","daily_brief","--in",_bj,"--out",_mn], env=_env, check=True, capture_output=True)
    subprocess.run([sys.executable, os.path.join(ROOT,"assets","suite_pdf_design.py"),"--kind","daily_brief","--in",_bj,"--out",_nm], env=_env4, check=True, capture_output=True)
    check(os.path.getsize(_mn) < os.path.getsize(_nm) * 0.95, f"compaction shrinks the full-design PDF ({os.path.getsize(_mn)} vs {os.path.getsize(_nm)} bytes)")
    check(all(b < 128 and b != 0 for b in open(_mn, "rb").read()), "compacted PDF is still pure ASCII")
    from pypdf import PdfReader as _PR
    _t = lambda f: [" ".join((p.extract_text() or "").split()) for p in _PR(f).pages]
    check(_t(_mn) == _t(_nm), "compaction leaves every page's extracted text identical")
    try:
        import pypdfium2 as _pdfium
        from PIL import ImageChops as _IC
        _A = _pdfium.PdfDocument(_nm); _B = _pdfium.PdfDocument(_mn); _w = 0
        for _i in range(len(_A)):
            _x = _A[_i].render(scale=2).to_pil().convert("RGB"); _y = _B[_i].render(scale=2).to_pil().convert("RGB")
            _w = max(_w, max(_IC.difference(_x, _y).getextrema()[c][1] for c in range(3)))
        check(_w <= 8, f"compaction is visually identical (worst pixel difference {_w}/255)")
    except ImportError:
        pass
except Exception as _e:
    check(False, f"compaction check crashed ({_e})")
check("SendUserFile" in read("references/run-policy.md") and "Outputs" in read("references/run-policy.md"), "run-policy.md ladder: save to outputs first, then typed upload")

# ── Size-fit delivery (requirement 7): tier chain, multipart, verify_pdf honesty, chunked Graph upload ──────────────
try:
    import copy, glob, shutil, threading
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    _DP = os.path.join(ROOT, "assets", "deliver_prepare.py")
    _fx = json.load(open(os.path.join(ROOT, "tests", "fixtures", "brief_many_items.json"), encoding="utf-8"))

    def _mult(d, n):
        o = dict(d)
        for k, v in d.items():
            if isinstance(v, list):
                o[k] = []
                for i in range(n):
                    for it in v:
                        it = copy.deepcopy(it)
                        if i and isinstance(it, dict):
                            for f in ("title", "action"):
                                if f in it:
                                    it[f] = "%s (batch %d)" % (it[f], i + 1)
                        o[k].append(it)
        return o

    _fz = tempfile.mkdtemp()

    def _dp(payload, name, *extra, kind="daily_brief", jname=None, capped=False):
        if not capped and "--budget" not in extra:
            extra = (*extra, "--budget", "0")       # tier-chain tests run without the 20 KB / page caps; the cap tests pass capped=True
        jf = os.path.join(_fz, (jname or name) + ".json"); json.dump(payload, open(jf, "w"))
        od = os.path.join(_fz, "out_" + name)
        r = subprocess.run([sys.executable, _DP, "--kind", kind, "--in", jf, "--out-dir", od, "--name", name, *extra],
                           capture_output=True, text=True, timeout=600)
        man = None
        try:
            man = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            pass
        return r, man, od

    def _gate(path):
        g = subprocess.run([sys.executable, os.path.join(ROOT, "assets", "verify_pdf.py"), path], capture_output=True, text=True)
        try:
            return g.returncode, json.loads(g.stdout.strip().splitlines()[-1]), g.stderr
        except Exception:
            return g.returncode, {}, g.stderr

    def _manifest_ok(man, od, label):
        good = bool(man) and man.get("tier") in ("full", "flate", "squeeze", "digest", "digest2", "digest3", "multipart") and man.get("parts")
        for pt in (man or {}).get("parts", []):
            rc, g, _ = _gate(pt["pdf"])
            good = good and rc == 0 and g.get("ok") and g.get("paste_mode") in ("content", "base64")
            good = good and pt["bytes"] == os.path.getsize(pt["pdf"]) == pt["expectedBytes"] == g.get("bytes")
            good = good and pt["filename"] == os.path.basename(pt["pdf"]) and pt["filename"].endswith(".pdf")
            if g.get("paste_mode") == "content":
                good = good and g.get("bytes") <= man["ceiling"] and open(pt["txt"], "rb").read() == open(pt["pdf"], "rb").read()
            good = good and pt["pages"] == g.get("pages")
            good = good and pt["readback_phrases"] == g.get("readback_phrases") and pt["paste_mode"] == g.get("paste_mode")
        check(good, "deliver_prepare manifest is correct and every part passes verify_pdf (%s)" % label)

    # small payload -> full tier, one part
    r, man, od = _dp(_fx, "small", capped=True)
    check(r.returncode == 0 and man and man["tier"] in ("full", "flate", "squeeze") and len(man["parts"]) == 1 and man["parts"][0]["bytes"] <= 20000,
          "deliver_prepare: a normal-size brief is one PDF of at most 20,000 bytes (full or compressed tier)")
    if man:
        _manifest_ok(man, od, "full")
    # 5x stress payload (25-30 full-design pages) -> the SAME full design, Flate-compressed, one PDF
    r, man, od = _dp(_fx, "stress5", "--ceiling", "20000")
    att = {a["tier"]: a for a in (man or {}).get("attempts", [])}
    check(r.returncode == 0 and man and man["tier"] == "flate" and len(man["parts"]) == 1 and man["parts"][0]["paste_mode"] == "base64",
          "deliver_prepare: a brief over the paste ceiling falls full -> flate (full design compressed) and stays ONE PDF")
    check(bool(att) and att.get("full", {}).get("fits") is False and att.get("flate", {}).get("fits"),
          "deliver_prepare: attempts record full as over the ceiling and flate as fitting")
    check(bool(man) and bool(man.get("fulldesign")) and os.path.isfile(man["fulldesign"]["pdf"]) and man["fulldesign"]["upload_as"] == "stress5.pdf",
          "deliver_prepare: the over-ceiling full-design PDF is kept for the typed upload (rung 1)")
    if man:
        _manifest_ok(man, od, "flate")
        try:
            from pypdf import PdfReader
            import deliver_prepare as _dpm
            _pdf = man["parts"][0]["pdf"]
            check(_dpm.design_problems(_pdf) == [], "flate tier keeps the colour design (tinted blocks, tiles, accent bars), not a plain layout: %s" % _dpm.design_problems(_pdf))
            _t = " ".join(" ".join(pg.extract_text().split()) for pg in PdfReader(_pdf).pages)
            check("compact format" not in _t.lower(), "no page says 'compact format' (the retired plain layout)")
            _lead = lambda it: " ".join(str(it.get("action") or it.get("title") or it.get("body") or "").split()) if isinstance(it, dict) else " ".join(str(it).split())
            _items = [it for k in ("needs_attention", "due_today", "worth_double_checking", "resolved", "conflicts") for it in _fx.get(k, []) if not _dpm._is_noise_item(it)]
            check(all(_lead(it) in _t for it in _items), "flate tier keeps every item (%d items)" % len(_items))
        except ImportError:
            print("SKIP: pypdf missing, flate content checks skipped")
    # 12x -> multipart
    r, man, od = _dp(_mult(_fx, 12), "stress12x", capped=True)
    check(r.returncode == 0 and man and man["tier"] == "squeeze" and man.get("design_lost") is False and len(man["parts"]) == 1 and man["parts"][0]["bytes"] <= 20000,
          "deliver_prepare: a 60+ page brief stays ONE PDF under 20 KB in the full design (squeeze loop, design never lost)")
    r, man, od = _dp(_mult(_fx, 12), "stress12", "--allow-parts", "--start-tier", "multipart")
    _ps = (man or {}).get("parts", [])
    _n = len(_ps)
    check(r.returncode == 0 and man and man["tier"] == "multipart" and _n >= 2, "deliver_prepare: a brief too big for one file is split into a multipart delivery (%d parts)" % _n)
    check(all(pt["filename"] == "stress12_part%dof%d.pdf" % (i, _n) and pt["index"] == i and pt["of"] == _n for i, pt in enumerate(_ps, 1)),
          "multipart parts are named <name>_partKofN.pdf, in order")
    check(all(pt["bytes"] <= man["ceiling"] for pt in _ps), "every multipart part is under the paste ceiling")
    if man:
        _manifest_ok(man, od, "multipart")
        try:
            from pypdf import PdfReader
            _tx = []
            for i, pt in enumerate(_ps, 1):
                rd = PdfReader(pt["pdf"]); tt = " ".join(" ".join(pg.extract_text().split()) for pg in rd.pages)
                _tx.append(tt)
                check(("part %d of %d" % (i, _n)) in tt and ("Page %d of %d" % (len(rd.pages), len(rd.pages))) in tt,
                      "multipart part %d is independently valid: titled 'part %d of %d', footer on its last page" % (i, i, _n))
            _all = " ".join(_tx)
            _items = [it for k in ("needs_attention", "due_today", "worth_double_checking", "resolved", "conflicts") for it in _mult(_fx, 12).get(k, []) if not _dpm._is_noise_item(it)]
            _lead = lambda it: " ".join(str(it.get("action") or it.get("title") or it.get("body") or "").split()) if isinstance(it, dict) else " ".join(str(it).split())
            check(all(_lead(it) in _all for it in _items), "multipart keeps every item across the parts (%d items)" % len(_items))
            import render_compact as _rc
            _ref = os.path.join(_fz, "ref.pdf"); _rc.draw("daily_brief", _mult(_fx, 12), _ref)
            _rt = " ".join(" ".join(pg.extract_text().split()) for pg in PdfReader(_ref).pages)
            check(all(_all.count(w) == _rt.count(w) for w in ("Owner:", "By:", "Source:", "[Open]")),
                  "multipart repeats no item and drops none (Owner/By/Source/status counts equal the unsplit render)")
            check(all(("%d. " % i) in _all for i in range(1, len(_mult(_fx, 12)["sources"]) + 1)), "multipart keeps every source")
        except ImportError:
            print("SKIP: pypdf missing, multipart content checks skipped")
    # --start-tier and --ceiling: a stopped paste steps down exactly one tier; tiny ceilings force the chain on a small payload
    r, man, od = _dp(_fx, "steplite", "--start-tier", "lite")
    check(r.returncode == 0 and man and man["tier"] == "flate" and [a["tier"] for a in man["attempts"]] == ["flate"], "deliver_prepare --start-tier lite (retired plain tier) now means flate: the full design, compressed")
    r, man, od = _dp(_fx, "tinyceil", "--ceiling", "9000")
    check(r.returncode == 0 and man and man["tier"] in ("flate", "digest", "digest2", "digest3") and len(man["parts"]) == 1,
          "deliver_prepare --ceiling forces the chain on a small payload (tier %s)" % (man or {}).get("tier"))
    _cp = json.load(open(os.path.join(ROOT, "tests", "fixtures", "call_prep_sample.json"), encoding="utf-8"))
    r, man, od = _dp(_cp, "cpfull", kind="call_prep")
    check(r.returncode == 0 and man and man["tier"] == "full" and man["parts"][0]["pages"] <= 2, "deliver_prepare: Call Prep takes the full tier (<= 2 pages)")
    r, man, od = _dp(_cp, "cptiny", "--ceiling", "3500", kind="call_prep")
    check(r.returncode == 0 and man and man["tier"] in ("flate", "digest", "digest2", "digest3") and len(man["parts"]) == 1,
          "deliver_prepare: Call Prep also steps down the chain, never skips (tier %s)" % (man or {}).get("tier"))
    if man:
        _manifest_ok(man, od, "call_prep forced")
    r, man, od = _dp({"title": "x"}, "bad")
    check(r.returncode == 6, "deliver_prepare exits 6 on a payload that fails the format gate (got %s)" % r.returncode)
    r = subprocess.run([sys.executable, _DP, "--kind", "daily_brief", "--in", os.path.join(_fz, "nope.json"), "--out-dir", _fz], capture_output=True, text=True)
    check(r.returncode == 2, "deliver_prepare exits 2 on unreadable input")

    # verify_pdf honesty: oversize results never say skip, keys unchanged
    _dp(_mult(_fx, 5), "stress5big")
    _big = os.path.join(_fz, "out_stress5big", "stress5big_fulldesign.pdf")
    rc, g, err = _gate(_big)
    check(rc == 0 and all(k in g for k in ("ok", "bytes", "pages", "sha256", "safe_to_attach", "safe_to_upload", "readback_phrases", "ascii_only", "paste_mode", "b64_chars", "safe_to_paste")),
          "verify_pdf keeps every backward-compatible JSON key on an oversize PDF")
    check(g.get("paste_mode") is None and "tier chain" in err and "skip" not in err.replace("never skip", "").replace("not skip", "").lower() and "skip" not in (g.get("next_step") or "").replace("never skipped", ""),
          "verify_pdf's oversize NOTE points at the tier chain and never tells anyone to skip the upload")
    _vsrc = read("assets/verify_pdf.py")
    check("do not attempt the upload call at all" not in _vsrc and "fall through to inline" not in _vsrc, "verify_pdf.py no longer instructs skipping the upload or inline fallback")
    _bad = os.path.join(_fz, "bad.pdf"); open(_bad, "wb").write(b"%PDF-1.4\n" + b"x" * 400)
    rc, g, _ = _gate(_bad)
    check(rc == 1 and not g.get("ok"), "verify_pdf still fails a PDF with no %%EOF trailer")

    # docs: no instruction to skip the upload remains
    _docs = {f: read(f) for f in ("references/run-policy.md", "skills/daily-brief/SKILL.md", "skills/call-prep/SKILL.md")}
    check(all("skip the upload call" not in b and "skip the upload attempt" not in b for b in _docs.values()), "no doc tells the run to skip the upload call/attempt")
    rp_ = _docs["references/run-policy.md"]
    check("tier chain" in rp_ and "multipart" in rp_ and "deliver_prepare.py" in rp_ and "mandatory in every Daily Brief and Call Prep run" in rp_,
          "run-policy.md section 5 documents the mandatory upload and the tier chain")
    check("A link is claimed only when the read-back passed" in rp_, "run-policy.md: a link is claimed only after a passing read-back")
    check("Inline-only email is permitted only after" in rp_ and "verbatim" in rp_, "run-policy.md: inline-only is the last resort with the verbatim tool message")
    check("never a local path" in _docs["skills/call-prep/SKILL.md"], "Call Prep links only the verified webUrl, never a local path")

    # smallest-file mode: with small mode the compressed tier is the default and the report stays a few KB
    import deliver_prepare as _dpm
    _sd = tempfile.mkdtemp()
    _res = _dpm.prepare("competitive_insights", json.load(open(os.path.join(ROOT, "tests", "fixtures", "competitive_insights.json"))), _sd, "small", small=True)
    _sz = os.path.getsize(_res["parts"][0]["pdf"])
    check(_res["tier"] in ("flate", "squeeze") and _sz <= 22500, "smallest-file mode: the competitive report renders as one PDF within 22.5 KB and 6 pages (%d bytes, %s)" % (_sz, _res["tier"]))
    _bres = _dpm.prepare("daily_brief", json.load(open(os.path.join(ROOT, "tests", "fixtures", "brief_many_items.json"))), _sd, "smallb", small=True)
    check(os.path.getsize(_bres["parts"][0]["pdf"]) < 20000, "smallest-file mode: the 7-page brief stays under 20 KB")
    import copy as _cp
    _big = _cp.deepcopy(json.load(open(os.path.join(ROOT, "tests", "fixtures", "competitive_insights.json"))))
    for _k in ("updates", "new_entrants", "working_well", "market_trends", "threats", "opportunities", "actions", "sources"):
        _big[_k] = _big[_k] * 4
    _r4 = _dpm.prepare("competitive_insights", _big, _sd, "small4", small=True)
    check(_r4["tier"] in ("flate", "squeeze") and os.path.getsize(_r4["parts"][0]["pdf"]) <= 22500,
          "strict cap: a 20-page competitive report is condensed by the self-loop to one PDF of at most 22,500 bytes")
    for _kind, _fxn, _keys in (("daily_brief", "brief_many_items", ("meetings", "due_today", "needs_attention", "resolved", "sources")),
                               ("competitive_insights", "competitive_insights", ("updates", "new_entrants", "working_well", "market_trends", "threats", "opportunities", "actions", "sources")),
                               ("call_prep", "call_prep_long_content", ("what_you_need_to_know", "questions", "risks", "actions", "sources"))):
        _base = json.load(open(os.path.join(ROOT, "tests", "fixtures", _fxn + ".json")))
        for _mul in (1, 6, 40):
            _x = _cp.deepcopy(_base)
            for _k in _keys:
                if isinstance(_x.get(_k), list):
                    _x[_k] = _x[_k] * _mul
            try:
                _rr = _dpm.prepare(_kind, _x, _sd, "cap_%s_%d" % (_kind, _mul))
                _okc = os.path.getsize(_rr["parts"][0]["pdf"]) <= (22500 if _kind == "competitive_insights" else 20000)
            except Exception as _e:
                _okc = False; print("   cap test error:", _kind, _mul, _e)
            check(_okc, "strict cap: %s x%d always yields one PDF within its size cap (20,000 bytes; 22,500 for the competitive report)" % (_kind, _mul))
    shutil.rmtree(_fz, ignore_errors=True)
except Exception as _e:
    import traceback
    traceback.print_exc()
    check(False, "size-fit delivery tests crashed (%s)" % _e)

# v1.10.0: the per-issue regression suites in tests/test_*.py (email format, drafts and signature, Call Prep
# link, PDF layout and calendar line, assets, Graph mail, Competitive Insights).
try:
    import subprocess as _sp
    _r = _sp.run([sys.executable, "-W", "ignore", "-m", "unittest", "discover", "-s", os.path.join(ROOT, "tests"), "-p", "test_*.py"],
                 capture_output=True, text=True, cwd=os.path.join(ROOT, "tests"))
    _tail = (_r.stderr.strip().splitlines() or [""])[-1]
    check(_r.returncode == 0, "tests/test_*.py regression suites pass (%s)" % (_tail if _r.returncode == 0 else _r.stderr[-1500:]))
except Exception as _e:
    check(False, "regression suites could not run (%s)" % _e)

# ---- v1.13.2: page caps, noise stripping, compressor, self-evaluation, brain ----
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets"))
    import deliver_prepare as _d2, brain as _b2, compressor as _c2
    from pypdf import PdfReader as _PR
    _root2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    for _k, _f, _cap in (("daily_brief", "brief_many_items", 4), ("call_prep", "call_prep_long_content", 2),
                         ("competitive_insights", "competitive_insights", 6)):
        _d = json.load(open(os.path.join(_root2, "tests", "fixtures", _f + ".json")))
        with tempfile.TemporaryDirectory() as _o:
            _r = _d2.run_with_eval(_k, _d, _o, "t")
            _p = _r["parts"][0]
            check(_p["bytes"] <= (22500 if _k == "competitive_insights" else 20000) and _p["pages"] <= _cap and _r["eval"]["passed"] and not _r.get("design_lost"),
                  "%s: within its byte cap and <= %d pages in the full design, self-evaluation passed (%d B, %d pages, tier %s)" % (_k, _cap, _p["bytes"], _p["pages"], _r["tier"]))
    # run-coverage noise never reaches a PDF
    _d = json.load(open(os.path.join(_root2, "tests", "fixtures", "brief_many_items.json")))
    _d["worth_double_checking"] = list(_d.get("worth_double_checking", [])) + [{"body": "Read 3 of 25+ matched chat messages and 1 email in full (Rajan's PR request).", "informational": True},
                                                                                   {"body": "Read 4 of 9 threads in full; 5 were not opened.", "action": "x"}]
    _n = _d2.strip_noise("daily_brief", _d)
    check(not any("Read 3 of" in json.dumps(x) or "Read 4 of" in json.dumps(x) for x in _n["worth_double_checking"]), "coverage notes ('Read N of M ...') are stripped from the payload before drawing")
    # compressor: never changes text, never grows the file
    with tempfile.TemporaryDirectory() as _o:
        _r = _d2.prepare("call_prep", json.load(open(os.path.join(_root2, "tests", "fixtures", "call_prep_long_content.json"))), _o, "c", budget=0)
        _src = _r["parts"][0]["pdf"]; _dst = os.path.join(_o, "z.pdf")
        _cr = _c2.compress_to_budget(_src, _dst, None, max_level=4)
        _a, _bb = _PR(_src), _PR(_dst)
        check(os.path.getsize(_dst) <= os.path.getsize(_src) and len(_a.pages) == len(_bb.pages)
              and all((x.extract_text() or "") == (y.extract_text() or "") for x, y in zip(_a.pages, _bb.pages)),
              "compressor.py: smaller or equal, same pages, identical text (level %s)" % _cr["level"])
    # brain: records, learns, hints, resets
    with tempfile.TemporaryDirectory() as _bd:
        os.environ["SUITE_BRAIN_DIR"] = _bd
        _b2.record("daily_brief", {"tier": "squeeze", "squeeze": {"last_step": "descriptions shortened to about 160 characters", "omitted": {"x": ["y"]}}}, {"bytes": 9000, "pages": 4, "score": 100, "issues": []})
        _h = _b2.hints("daily_brief")
        check("160 characters" in _h and "4 pages" in _h, "brain: hints carry the learned description length and the page cap")
        for _ in range(2):
            _b2.record("daily_brief", {"tier": "squeeze", "squeeze": {"last_step": "kept the first 75%"}}, {"bytes": 9000, "pages": 4, "score": 100, "issues": []})
        check(_b2.start_in_squeeze("daily_brief") and not _b2.start_in_squeeze("call_prep"), "brain: three trimmed runs in a row start the next one in the squeeze loop")
        check(_b2.evaluate("daily_brief", os.path.join(_root2, "tests", "fixtures", "does-not-exist.pdf"))["hard_fail"], "brain.evaluate: a missing PDF is a hard failure")
        del os.environ["SUITE_BRAIN_DIR"]
except Exception as _e:
    import traceback; traceback.print_exc()
    check(False, "v1.13.2 checks could not run (%s: %s)" % (type(_e).__name__, _e))

for m_ in ok:
    print("PASS ", m_)
for m_ in errs:
    print("FAIL ", m_)
print("ALL CHECKS PASSED" if not errs else f"{len(errs)} CHECK(S) FAILED")
sys.exit(1 if errs else 0)

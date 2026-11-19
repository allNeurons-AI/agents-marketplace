# Releasing

The marketplace tracks the `main` branch of `allNeurons-AI/agents-marketplace`.

1. Make the change under `plugins/allneurons-productivity/`.
2. Bump `version` in `plugins/allneurons-productivity/.claude-plugin/plugin.json` and in the root `.claude-plugin/marketplace.json`, update the `**Version:**` line at the top of every `skills/*/SKILL.md` and the README's "Current version", and add a top entry to `CHANGELOG.md`. Anthropic's directory expects a new version on every release.
3. Run `python3 scripts/selftest.py` and the files in `tests/` (about 7 minutes).
4. Run `claude plugin validate . --strict` in the plugin folder and in the repo root.
5. Check the repo has no `bin/`, no symlinks, no `.DS_Store` or `__MACOSX`, no `.pyc`, no file over 256 KiB except fonts and images, and fewer than 512 files.
6. Commit to `main` and push. With the push webhook on, the directory re-validates and re-scans automatically.
7. Scheduled tasks hold version-free prompts, so users need no re-onboarding.

# flextext-onestory-injector — repo notes for Claude sessions

Python/Tkinter tool that splices a story from a `.flextext` into a OneStory
Editor `.onestory` project. AGPL-3.0-or-later; the `<story>` structure is
adapted from OneStory Editor (MIT) — see THIRD-PARTY-NOTICES.md.

## Hard rules
- **Never commit a real `.onestory`, `.flextext`, or `.eaf`** — not as a
  fixture, not temporarily. `sample/` is git-ignored for local copies. A real
  project file carries member names, emails and stored HgPassword values.
- **The target project file is bytes, not text.** Binary I/O only; splice by
  byte offsets; never parse-and-reserialize it; never normalise line endings
  (real projects hold thousands of legitimate bare LFs inside note fields).
  The invariant every write must pass: byte-identical outside the inserted
  range.
- All test fixtures are synthetic — placeholder language "Alpha", ISO `qaa`.

## ⚠️ GitHub costs — ask before anything billable
Never add/modify `.github/workflows/**`, use non-standard runners, add cron
triggers, make this repo private while it has workflows, use LFS/Packages/
Codespaces, or touch billing — without Seth's explicit pre-approval and a
stated cost. The `.git/hooks/pre-push` guard blocks main pushes unless
`ALLOW_MAIN_PUSH=1` and workflow pushes unless `ALLOW_WORKFLOW_PUSH=1`.

## Testing
`python3 tests/run_tests.py` — 48 synthetic checks; add a local project copy
under `sample/` to also run the real inject→verify→undo cycle on a copy.

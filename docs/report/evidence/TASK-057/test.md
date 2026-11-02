PROGRESS: COMPLETE
SKILLS: unit-test, token-efficiency, crosscheck
## Added (tests only)
- .claude/tests/evidence_e2e_test.sh (new, 13 checks, 7.1-7.7): flagged end to end via advance.sh in temp repos; reuses the fixture prelude of .claude/scripts/checks/advance_test.sh.
  Flagged VERIFIED refused on a url (nothing published); passes with publish (tracked, verification.published set); workflow-check fails on empty published;
  DONE fails with no cited evidence; passes with citation + INDEX row (tracked); fails when the INDEX row is removed; unflagged = WARN only, nothing published.
- .claude/tests/evidence_scope_test.sh (new, 5 checks, E1-E5): commit-check foreign evidence dir OK, own unstaged FAIL, staged OK, INDEX.md unstaged FAIL / staged OK.
- Could NOT edit .claude/scripts/checks/advance_test.sh (guard: tester limited to tests/ and .claude/tests/); main may fold the e2e file into it. Not wired into any runner yet.
## Results (evidence in work/TASK-057/evidence/)
- e2e57.txt: PASS 13/0. scope57.txt: PASS 5/0. cc.txt (commit_scope_test): 9/0.
- adv57/advance_test.txt 58/0; advance_adv_test.txt 32/0; task_readers.txt 0 fail; sanity.txt: scan docs/report/evidence rc 0.
- unit57.txt: 951 run; failures=3 errors=1, all known (multipage_adversarial docx, check_examples 12b, req0012 cwd, scripts_exam check_examples).
- test_evidence.py (22, coder's) already covers (2),(3),(5): per-rule positive+negative, publish idempotent/outside/redact/all-or-nothing, index twice + --check stale, calibration.
## Mutations (scratch kit, each caught)
- scan rules neutered one by one: head, opt, answer-line, answer-json, answer-tsv, url, secret, binary, ext, size, private-dir -> each fails its own unit test.
- publish: redact off, outside-src check off -> fail. index: --check always 0, unsorted -> fail.
- gate off when flagged (workflow-check) -> e2e 7.3/7.4/7.5/7.6 fail; unit only test_flagged_scan_fail.
- _path_ok evidence clause removed -> test_scope fails.
- Old code (d79362f~1): e2e fails 7.1-7.5+; scope E1 fails (bite 1 of 5; E2 now passes by the FAIL path on old code too).
- Idempotence-mutation (rewrite always): not caught by any test (file content equal either way); low.
## Defects
- D1 low, tests/unit/test_evidence.py:218 test_flagged_verified_needs_published: passes with the gate disabled (asserts only "published"/"FAIL" substrings, WARN text contains "published"). e2e 7.3 covers it; tighten to assert "verification.published".
- D2 low, commit-check.sh:233-237: a foreign task's evidence dir is not filtered when docs/report/evidence/ has no tracked file (git status collapses to `docs/report/evidence/`); first-ever evidence dir would block another task's commit. Real repo has tracked evidence, so no live impact.
- D3 info: publish idempotence (same bytes no rewrite) is only checked via output, not mtime/no-op; mutation survives.
- G1 redaction implemented and tested (redact-off mutation fails).

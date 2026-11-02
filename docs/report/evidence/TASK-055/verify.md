PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency
## Fix verdicts (static read + saved evidence; no real run)
- D1 dry-run grouped prompt: VERIFIED. cli.py:86-89 passes ids; test_55_4_dry_run_passage_once_per_group ok, no expectedFailure (ac-tests.txt:1); head-after-fix.txt: only the known 3 fail + 1 error.
- D2 lone-question header: VERIFIED. solver.py:95 (header only if len(own)>1 or passage); test_group_header_only_for_real_groups ok (ac-tests.txt:19).
- D3 own-text rule: VERIFIED. refcheck.py:164-167,185; test_passage_promised_but_empty, test_passage_promised_stem_has_text_warns_not_declines ok (ac-tests.txt:16,20). Residual: short stems (<200 chars, <3 sentences) still decline.
- Sibling-answer retry test bites: VERIFIED-thin (test_dependent_retry_has_sibling_answer; one mutation fails exactly that test per test.md).
## REQ-0058 AC table (test names from evidence/ac-tests.txt; ACs from REQ-0058.md:46-50)
| AC | Verdict | Evidence |
|---|---|---|
| AC1 kind derived from guide+passage, unknown -> independent + warning | VERIFIED (unit) | test_kinds_and_deps, test_no_labels_no_groups; test_vague_ref_only_warns; e2e `group_link_uncertain: q 12` |
| AC2 independent: guide + own stem only | VERIFIED (unit, golden hash) | test_unlabelled_unchanged, test_round1_passage_once_and_content_equal, test_55_golden_retry_qa_unchanged (25 inputs == 083d0e4). Real English cloze 31-35 exam not run |
| AC3 passage once per prompt; missing passage declined | VERIFIED (unit+mock e2e) | test_55_4_round1_prompt_passage_once, test_55_4_dry_run_passage_once_per_group, test_retry_only_open_with_context_once, test_slice_keeps_passage; decline: test_passage_promised_but_empty, test_55_5_mock_statuses (q13 missing_text passage). Câu 46-52 real exam not run |
| AC4 dependent: sibling answer passed in; missing sibling declined | VERIFIED (unit) | test_dependent_retry_has_sibling_answer, test_sibling_answers_each_rendered, test_qa_prompt_context_and_siblings, test_missing_dependency_declined_no_call, test_55_5_mock_statuses (q11 ref q99). Cycle case: no test named in ac-tests.txt -> UNVERIFIED |
| AC5 design doc rationale, non-English, tests-first on 2-page slices | PARTIAL/UNVERIFIED | slices: test_group_slice.*, test_group_e2e (2-page); design doc rationale and non-English coverage not read in this pass |
## Security pass (src diff areas: solver.py, refcheck.py, cli.py)
- No eval/exec/subprocess/shell/network/new AI call in solver.py (grep 0).
- Regexes refcheck.py:156-161: bounded alternations, no nested quantifiers -> linear; no ReDoS. Exam text only goes into prompt strings.
## Gaps
- No paid real run; mock/e2e only.
- Prompt release not bumped (config pins v1.0.0; solve.md rule 5 unreleased), so a real model does not see the new rule.
- REQ-0059 follow-up holds the pre-solve figure warning.
- Dependency cycle decline untested; full-suite failures pre-existing (qa-full.txt), not re-run by me.
## Defects
- none new

PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency

Verifier: Argus. Tier 0/1 (static + mock unit suite). Unit evidence: work/TASK-017/evidence/unit.txt:7 rc=0, "Ran 423 tests ... OK" (head 8d6993d+dirty). I did not re-run anything; verdicts come from code reading plus that file.

## Verdicts
- AC1 VERIFIED (mock part). Off by default: it is a separate command `ingest-refine` (cli.py:21, 409), so plain `ingest` never calls it. Exactly one of --mock/--dry-run/--real is required, otherwise exit 2 "never defaults to real" (cli.py:342-345; tests test_no_mode_is_usage, test_two_modes_is_usage). --dry-run prints pages, "calls <= N" and the cap, plus the prompt, and makes no call (cli.py:361-367; test_dry_run_no_call patches make_real_llm to raise). The real run prints pages, calls and cap before the first call (cli.py:373). Real call site is only make_real_llm (refine.py:84-95) via claude.run_claude_images with an empty temp cwd (cli.py:371-372). Tests patch run_claude_images to raise AssertionError (test_ingest_refine.py:83-87). The "tools off" and "stream-json image" behaviour lives in adapters/claude.py, which I did not read, so it is UNVERIFIED here. The "user's go" gate is only the explicit --real flag. There is no interactive confirm, so the coordinator must hold the real run.
- AC2 VERIFIED. pick_pages keeps only pages that are both in the spec and flagged by a warning code or status ocr (refine.py:42-53). A page outside the document gives invalid_pages (47-49). check_key_pages refuses pages inside an answer_key part with answer_key_present, unless --allow-key-pages (56-65), and it runs before anything else (refine.py:184, cli.py:359; exit 3 at cli.py:386). Tests: test_selected_and_flagged_only, test_key_pages_refused_unless_allowed, test_unflagged_page_not_sent, test_cli_calls_only_flagged_selected, test_key_pages_exit_3.
- AC3 VERIFIED. out = deepcopy(doc), and only out["refined"] and one warning are added (refine.py:186, 203-211). origin is always "ai" (200). validate_refined rejects the fields answer, answers, solution, solutions, key and explanation at both reply and question level (21, 109-116). It also checks id, text, options, unreadable, figures and consecutive ids. _ask makes at most 2 calls and then raises RefineError invalid_reply, exit 3 (161-175, cli.py:381-383). A failed call is not retried and raises call_failed. Tests: test_valid_stored_source_untouched, test_retry_on_invalid_json, test_two_invalid_is_structured_error, test_answer_in_reply_rejected, test_solution_field_rejected, test_non_consecutive_ids_rejected_with_retry. Note: a "hash equal" check is only as strong as the test at line 128, which I did not read in detail.
- AC4 VERIFIED. similarity() is a difflib ratio of folded text against the same-numbered source question, else the share found in the page text (refine.py:147-158). needs_review is true when unreadable or sim < 0.6 (202). The CLI exits 1 when any question needs review (cli.py:398). Tests: test_low_similarity_and_unreadable_need_review, test_threshold_boundary. No accuracy claim is made in code; that belongs to AC5.
- AC5 (mock part) VERIFIED. All tests use mock replies and the unit suite cost $0. The real benchmark is NOT done and stays pending the user's go.

## Cross-cutting
- Cost cap and call count: the cap is checked before each page (refine.py:190-192), so cost can overshoot by up to one page (2 attempts). Calls and cost are summed over all attempts (162-167, 205-206) and printed (cli.py:395). Test: test_cost_cap_stops. VERIFIED.
- No key text in the prompt: the prompt is a static template plus "Page: n" (refine.py:38-39). The template (prompts/dev/ingest/refine.md:1-13) has no key or answer text and forbids answers (rule 7). Test: test_no_answers_or_keys_in_prompt. VERIFIED.
- Real mode unreachable from tests: VERIFIED (setUp patch above; test_real_without_source_file_fails_before_any_call fails before any call).

## Limits
- render_page tests (TestRenderPage x5, test_ingest_refine.py:244+) were NOT skipped and did run. They use a synthetic FakeFitz injected through a patched optional.load (246), so they ran in the 423-test pass. The tester says pymupdf is not installed, and no real pymupdf rendering was exercised. Real rendering is UNVERIFIED until AC5 or an install.
- stream-json against the real CLI is untested. The only coverage is test_stream_format_error_is_structured with a fake runner.
- In the unit.txt run the OCR tests did emit Tesseract warnings, so OCR is installed there. That is unrelated to pymupdf.

## Defects
- D1 (low): the cost cap can overshoot by one page's retry, because it is checked per page and not per call (refine.py:189-193). Document it, or check it inside _ask.
- D2 (info): no interactive confirm for --real. The cost gate relies on the coordinator.

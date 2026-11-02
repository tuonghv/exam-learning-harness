PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency
(No Bash: judged from code reads and evidence files. security/SKILL.md does not exist at .claude/skills/security; pass done by hand on the listed items.)

## Goals (REQ-0059, design phase-59-page-image-check.md)
- AC1 trigger set = flagged only: VERIFIED. engine.py:98-101 visual_flags (refcheck), :120-142 image_targets iterate flags only; tests 2a/6 (test.md). Marker-skipped ids excluded by design G4 (design:117).
- AC2 (G1) unreadable/absent image: VERIFIED. engine.py:175-182 text kept + UNCERTAIN "needs_review: image unreadable", declined stays declined with reason; render/call/malformed -> finding only (:194-209). Mutation M9 killed (test.md).
- AC3 real small slice (TASK-020 Q10/Q18): NOT RUN (paid, awaits user go, Q-1793619815).
- AC4 pre-solve WARN: VERIFIED (unit). engine.py:109-117, called :285 before round 1; test_1a. Not seen in CLI runs (0 WARN in 25 qa inputs).

## Checks
- No --pdf byte-identical: VERIFIED. qa-no-pdf-identity.txt (25 inputs vs 760fbac; plan.json only timestamps). Code: image=None unless cfg image_pdf (engine.py:277), sink called without new kwargs (:61). Evidence file has no header (rc unknown).
- id + stem-prefix matching: VERIFIED. cross.py:63-69 asks by `id N ... "prefix..."`; test_3/3b; M1 killed.
- Key-page refusal: VERIFIED. engine.py:133; cli.py:210-213 key_pages from answer_key parts; M2 killed.
- Unreadable image keeps text: VERIFIED (see AC2).
- PNG signature/size guard: VERIFIED in engine.py:196-198 (8-byte sig, 8 MB); tests 7/7b. Real render also checks (refine.py:84). BUT see D1.
- Call cap +1 only with --pdf: VERIFIED. engine.py:23; M5 killed, test_4d.
- Page images not stored (hash only): VERIFIED. engine.py:57-59 sink gets page_sha256 + page numbers; planrun.py:113-131 writes only those.
- Suite: suite-final.txt Ran 1027, same 3 FAIL + 1 ERROR (+1 harness ERROR line) as baseline-failures.txt names; head-failures identical. UNVERIFIED rc: files have no `# rc:` header (only qa-full-suite has, rc 1).

## Security pass (engine/cli diff, by reading)
- Paths: --pdf goes through _load_source_doc (cli.py:190-201): .json is schema-validated, else api.ingest_document; pages are ints from the validated doc; render_page(src, n) with n from doc pages only. OK.
- Subprocess: none new in engine; real call reuses claude.run_claude_images (tools off, empty cwd tmp, cli.py:218-220). OK.
- Size caps: 8 MB engine guard + 5 MB refine.render_page; page cap max_image_pages (default 4), <=0 disables. OK.
- Prompt injection: flagged_prompt embeds id, printed number, stem prefix (cross.py:66); stem prefix is exam text (untrusted) but is the same text already in the solver prompt; reply is parsed by parse_reply and extra ids ignored (engine.py:211). Low risk, no new capability (tools off).
- Secrets: calls/ gets prompt + page hashes; error text masked/limited (str(exc)[:200]; claude.mask in build_result). No secret path seen. OK.

## Defects
- D1 medium, cli.py:224 vs engine.py:197: mock stub render returns b"\x89PNG" (4 bytes), but fix-round-1 guard requires the full 8-byte signature, so `solve --pdf ... --mock` never makes the image call (always finding image_unavailable). test_image_plan patches engine.run (test_image_plan.py:87-93), so no test catches it. Fix: stub = engine.PNG_SIG (+ padding) and add a CLI-level mock test that asserts the image call happens. Not run (no Bash); derived from the code.
- D2 info: evidence files other than qa-full-suite.txt lack the save-evidence header (rc/head). Re-save if rc is needed.

## Open
- AC3 NOT RUN (paid). Real fitz render of a valid PDF and real image call unverified.
- Verdict for task state: fix D1 (small), then AC1/2/4 and invariants are sufficient for VERIFIED pending the user's go on AC3.

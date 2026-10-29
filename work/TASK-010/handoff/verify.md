PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency

# TASK-010 / REQ-0014 verification (Argus)

## AC verdicts
- AC1 layout + contract.json: VERIFIED. prompts/dev/lang/vi/{system.md,exam/solve.md,verification/verify_answer.md,subjects/*.md}; prompts/contract.json:1-22 (markers + output anchor/schema per prompt); lookup settings.py:68-77.
- AC2 check-prompts exit codes: VERIFIED. prompts.py:178-266 (missing marker :155, key structure :168, stray/ill-named :202-218, code regex :104/:204; exit 1 on errors :263). Evidence: evidence/check-prompts.txt rc 0 "OK: 21 files, 1 variants"; evidence/variant-mutation.txt: drop marker/change key/stray file each rc=1, restore rc=0; suite.txt rc 0, 238 tests.
- AC3 engine picks variant by subject language, fallback to base: VERIFIED by code (solver.py:18-22,52,77; verifier.py:109,123 pass router.language(exam); router.py:38-42; settings.py:72-75 fallback to default). Tests test_prompt_variants.py:140-163. Schema stays SOLVE_OUT because the example is checked against the schema (prompts.py:165).
- AC4 broken variant => exit 1; mock runs vi/en schema-valid: PARTIAL. Broken-variant part VERIFIED (test_dropped_marker :71, mutation evidence). The "mock runs of vi and en give schema-valid results" part is UNVERIFIED: the tests (:140-163) only assert which prompt text is chosen; I found no test that runs a mock solve with vi and en and validates the result against SOLVE_OUT. Missing: a mock-run with Language: vi and en whose output goes through the schema validation.

## Content diff dev vs dev/lang/vi (read in full)
system.md, exam/solve.md, verification/verify_answer.md, 4 subjects: same rules, same numbering, same limits (6 steps / concise 3, at most 3 findings), same JSON example (identical), all markers kept verbatim (`answer_status`, `sqrt(3)`, `c-a-d-b-e`, `Open`, `Passage`, ...). Nothing added or dropped; no key hints. Vietnamese is correct and natural. Rule drift: none. Cosmetic only: literature "2 defensible readings" -> "2 cach hieu"; `Given:`/`Find:` kept in English (consistent with the default).

## Validator cannot be fooled? 
- Marker in a comment or elsewhere: NOT guarded (prompts.py:155 is a plain substring test). Weak markers: `agree` is a substring of `disagree`, `Open`, `issues`, `expr` are common words, so a dropped `agree` rule would pass. Minor.
- Output example not extracted: guarded (anchor not found -> ERROR :136; unparsable -> ERROR :140; test_output_example_missing). The first anchor occurrence is used, so an anchor in a comment before the real example could hide a broken real example. Minor.
- Variant dir `../x`: guarded in the validator (os.listdir returns plain names; CODE_RE ^[a-z]{2}$ at :204; stray file in lang/ :201).
- Subject variant without default subject file -> "not in the prompt contract" (:215-218). OK.

## Defects
- D1 (major, security): settings.py:72-75 `read_prompt` joins `lang` into a path with no check, and `lang` comes from the exam file header `Language:` (router.py:38-41, untrusted input; solver.py:18). `Language: ../../../x` makes `os.path.join(root,"lang",lang,rel)` escape the prompt root; if `<x>/system.md` exists (isfile) its text goes into the prompt. Impact is limited (only a file with the same relative name is read), but the file is arbitrary and the exam is untrusted. Fix: accept only `^[a-z]{2}$` (reuse prompts.CODE_RE, or put the regex in settings) else use the default. Add a test with `../x`.
- D2 (minor, AC4): no mock-run test with vi and en variants validating the output against the SOLVE_OUT schema (see AC4).
- D3 (minor): marker checks are substring-based (`agree` inside `disagree`; anchor/marker in a comment passes); consider word-boundary markers or checking the output-example block only.
- D4 (minor): evidence/variant-mutation.txt baseline reads "14 files" (channel dev) vs check-prompts.txt "21 files" (--all); consistent with scope, noted only for like-for-like.

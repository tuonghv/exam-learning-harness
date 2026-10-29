PROGRESS: COMPLETE
SKILLS: verify, crosscheck, token-efficiency

# TASK-011 / REQ-0015 verification (Argus)

## Independent re-solve (before reading keys)
- 001: 1011010 = 64+16+8+2 = 90 -> C. Key examples/informatics/expected-001.md:5 = C. VERIFIED
- 002: F=(a|b)&!(a&c): only C (1,1,0) gives 1. Key expected-002.md:5 = C; truth set at :23 is right. VERIFIED
- 003: i=1,4,7 -> s=12 -> B. Key evals/keys/informatics/expected-003.md:5 = B. VERIFIED
- 004: diem<5 matches 4.5, 3.0, 4.5; NULLs excluded -> 3. Key expected-004.md:5 = 3. VERIFIED
- 005: /26 -> 2^6-2 = 62. Key expected-005.md:5 = 62. VERIFIED
- Distractor reasons: every wrong option or wrong value has a stated cause (001 :16-19, 002 :15-19, 003 :16-19, 004 :17-20, 005 :18-20). 45 = reversed bits (0101101 = 45), correct.
- Inputs hold no hints: the five input files contain no answer or method text. Originality: these are plain textbook-style items and I found no copied source.
- Edge-case line: present in 001, 002, 004, 005. Absent in 003 (see D1).

## Code review
- fold (src/exam_engine/utils/text.py:5-9): NFD, then strip combining marks, then đ/Đ -> d, then casefold and collapse spaces. This handles `đ`/`Đ`, any case, and None (gives ""). norm (:12-17) is untouched and still used by parser and examples_check. fold is used only in router.py, so there is no side effect on other code. VERIFIED
- router.py:13-19 compares fold(name) with fold(key) and fold(alias). config/subjects.json:2-16 aliases cover every AC1 name: toán/math/mathematics; vật lý/physics; ngữ văn/văn/literature; tiếng anh/english; tin học/it/information technology/informatics (plus cntt). I found no alias or key collision across the five subjects (van, it, cntt are unique). AC1 VERIFIED
- Unknown subject: parser.py:153-154 returns "unsupported Subject: X". tests/unit/test_subjects.py:53-61 covers Chemistry, Hóa học, "" and None. AC4 VERIFIED
- Routing: test_subjects.py:65-76 runs `Subject: Tin hoc` through cli.solve_main --dry-run and expects "Quy tắc môn (Tin học)". solver.py:20 loads policy["prompt"]. AC2 VERIFIED
- Prompts: prompts/dev/subjects/informatics.md:1 and prompts/dev/lang/vi/subjects/informatics.md:1 say the same thing (representation or base first, trace table, exact value). VERIFIED
- FORMAT.md:116-119 has the Informatics section (representation first, trace or truth table, Check recompute, edge cases). Lines :14 and :22 list informatics. VERIFIED

## AC verdicts
- AC1 VERIFIED (config + test_subjects.py:16-23, 44-48, 50-51; suite rc 0, 250 tests: work/TASK-011/evidence/suite.txt:7,11-13).
- AC2 VERIFIED (check-prompts rc 0, "OK: 16 files": evidence/check-prompts.txt:7,9).
- AC3 VERIFIED (check-examples rc 0, "25 pairs (10 few-shot, 15 eval)": evidence/examples-check.txt:7,10). I recomputed all five keys by hand. The wrong-key mutation (key 004 changed 3 -> 4) made the suite fail, then it passed after the key was restored (evidence/wrong-key-mutation.txt:1-9).
- AC4 VERIFIED (test_subjects.py:44-61).

## Defects
- D1 (minor): evals/keys/informatics/expected-003.md:21-26 has no `Edge case:` line. The off-by-one bound i<10 is covered only in the Explanation (:16). FORMAT.md:118 lists the off-by-one loop bound as an informatics edge case. Add `- Edge case: i = 10 không thỏa i < 10, nên không cộng thêm.`
- D2 (minor): there is no test that aliases are unique across subjects. The review found none today, but a future alias collision would not be caught.
- D3 (minor, evidence): evidence/wrong-key-mutation.txt has no `# cmd/# rc` header, so I could not confirm the command or rc. It was judged from the "FAILED then OK" content.
- No major defects.

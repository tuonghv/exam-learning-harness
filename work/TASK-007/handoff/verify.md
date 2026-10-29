PROGRESS: COMPLETE
SKILLS: verify
(Argus, verifier)

## Independent re-solve (10/10 match the keys)
- math few-shot 001 log_2 x + log_2(x-2)=3: x>2, x(x-2)=8, x=4 or -2 -> {4} = A. VERIFIED (examples/math/expected-001.md:5-14). One correct option; B,C,D wrong.
- math few-shot 002 integral x e^(x^2) 0..1 = (e-1)/2 ~0.8591. VERIFIED (examples/math/expected-002.md:5-11).
- math eval 003 two extrema, m<3, m in [-5,5] -> -5..2 = 8 = A; m=3 excluded (double root). VERIFIED (evals/keys/math/expected-003.md:5-13). B(9) and C(7), D(6) wrong.
- math eval 004 1 - C(5,3)/C(9,3) = 74/84 = 37/42. VERIFIED (expected-004.md:5-11).
- math eval 005 |z| = sqrt10/sqrt5 = sqrt2. VERIFIED (expected-005.md:5-11).
- phys few-shot 001 T=2pi sqrt(0.2/50)=0.397 s ~0.40 = A; B 12.6, C 2.5 (f), D 0.063 wrong. VERIFIED.
- phys few-shot 002 p2=2e5*400/300=2.67e5 Pa; wrong via Celsius = 9.4e5 checks out. VERIFIED.
- phys eval 003 ZL=40, ZC=80, tan phi=-4/3, phi=-0.927 rad = B; arctan(3/4)=0.644 explains C. VERIFIED (evals/keys/physics/expected-003.md:5-14).
- phys eval 004 lambda=2 cm, AB/lambda=5, k=-4..4 = 9. VERIFIED (expected-004.md:5-14).
- phys eval 005 hc/lambda=6.625e-19 J, A=4.8e-19 J, Wd=1.825e-19 ~1.8e-19 J (1.14 eV, lambda0=0.414 um ok). VERIFIED (expected-005.md:9-13).

## Per-AC
- AC1 (answer, steps, verification, grading in every item): VERIFIED - all 10 files have Final answer, Solution, Explanation, Verification (Check lines + Status: Verified), Grading.
- AC2 (independent stdlib recompute; wrong key -> fail): VERIFIED with a note. oracle.txt rc 0 (10 tests), wrong-key-mutation.txt shows FAILED (failures=1) for a mutated phys key, check-examples OK 11 pairs, suite 208 OK (suite.txt). Note: oracle is a unittest (tests/unit/test_examples_oracle.py:31-83, uses fractions/math), so "exit 1" is the unittest failure, not a checker CLI.
- AC3 (>=2 edge cases per subject, labelled): VERIFIED. Math: examples/math/input-001.md:8 (domain), evals/inputs/math/input-003.md:8 (parameter boundary). Physics: all 5 labelled (Skill line + "Edge case:" in Verification).
- AC4 (MC exactly one correct, distractors wrong): VERIFIED for math 001, 003 and phys 001, 003 (reasoning above; test_001/003 cover them).

## Other checks
- Solvable from input alone: yes (constants given; math 005 asks exact form).
- Leakage: no Final answer/Correct answer strings in evals/inputs (grep empty). Eval items are distinct topics from few-shot (not reworded copies).
- Vietnamese: natural, correct terminology.

## Defects
- D1 (minor, content) evals/keys/math/expected-003.md:19 option C explanation "bỏ sót một giá trị biên" vague about which distractor logic; D (line 20) "chỉ đếm m từ -3 đến 2" gives 6 values, consistent. No wrong fact, wording only.
- D2 (minor) math keys (expected-003:22-27 etc.) have no "Edge case:" line unlike physics keys; the label lives only in input Skill line. Acceptable for AC3 ("labelled in the item") but inconsistent.
- D3 (info) mutation evidence mutates a real key file in place and restores it by cp from /tmp (wrong-key-mutation.txt:3); safe now (rc 0, git status shows only solver.md modified) but fragile.
- D4 (minor) evals/keys/physics/expected-004.md:32 grading mentions "10" as typical error without explanation; harmless.
No major or critical defects.

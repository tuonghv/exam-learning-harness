# Benchmark findings (prompts v1.2.0, sonnet, 15 items, 31 calls, $0.567; first attempt with v1.0.0 stopped at informatics: no subject prompt in that release)

Solver answers vs key, non-open items (12): all 12 answers equal the key in substance. Literature (3) is open-ended: UNCERTAIN by design, no key comparison.
Engine verdicts: 6 items PASS, 6 FAIL, 3 UNCERTAIN. The 6 FAILs are engine checks, not wrong answers:
- math/004 (37/42), math/005 (sqrt(2)), physics/005 (1.8e-19 J): `computed` check reads only the first number of the answer ("answer 37", "answer 2", "answer 1.8"), so a fraction, a radical or a rounded value fails although the key matches (math/004, math/005 scored 1/1 yet verdict FAIL).
- english/004 (b-d-a-e-c): `quote` check fails on ordering sentences quoted with a "b:" label although the key matches (1/1, verdict FAIL).
- physics/004 ("9 điểm" vs "9 (cực đại)"), informatics/005 ("62 host" vs "62 địa chỉ host"), physics/005: key match fails on trailing unit/remark text.
n=15, one run, one model: no accuracy claim. Any fix must cite these items and be re-measured on the same items (REQ-0009 AC4).

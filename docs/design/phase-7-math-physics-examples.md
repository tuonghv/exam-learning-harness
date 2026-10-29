# Phase 7: Math and Physics examples (REQ-0003, TASK-007)

Standard: `examples/FORMAT.md` (approved). Per subject 5 items: few-shot 001-002 in `examples/<s>/`, eval 003-005 in `evals/inputs/<s>/` + `evals/keys/<s>/`.
- Original text, Vietnamese, self-contained, no hint of the key in inputs. Multiple choice has exactly four options, one correct.
- Math edge cases (>=2): domain restriction / extraneous root, no solution or parameter boundary. Physics edge cases (>=2): unit conversion, sign/direction or limiting value. Label each in the input `Skill:` line and in Verification.
- Every key has Final answer, Solution, Explanation, Verification (`- Check:` recompute another way, `Status: Verified`), Grading.
- Proof: `scripts/exam.py check-examples` recomputes each final answer (exact fraction or tolerance with unit); a deliberately wrong key must exit 1.
- Eval keys never go in few-shot or prompts; a question is not reused across sets.
Roles: one coder per subject (content), tester wrong-key mutations, coordinator independent recompute (python), verifier reads.

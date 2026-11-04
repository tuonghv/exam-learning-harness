# Report phase 73: the 2025 DGNL sample scored (TASK-073; REQ-0081)

Verdict: 113 of 120 correct, 94.2 percent (Wilson 95 percent [88.4, 97.1]) on a new exam with no exam-specific code, cost 2.33 USD. The 2026 sample scored 92.5 percent (run 3) with the same pipeline. Per subject: Vietnamese 29/30, English 28/30, Math 29/30, Science 27/30.

## Where the signal is
- By source of the answer: text only 101/103 (98.1 percent), text plus page image 8/10, image only 4/7 (57.1 percent). Three of the seven wrong answers (English 59 and 60, Science 111) came from the image call alone.
- By status: UNCERTAIN 110/116, FAIL 3/4; no answer reached PASS.
- By solver uncertainty: low 100/105, medium 13/15.
- Flag check (questions I listed before scoring: 1, 17, 28, 106, 107, 108, 117): 2 of the 7 flagged are wrong (107, 117); 5 of the 7 wrong answers carried no FAIL or image-differs flag.

## Root causes of the 7 wrong answers (inspector, the prompts matched the PDF in all seven; no extraction or figure error)
- Engine defects: Science 107 and 117 (the page-image answer equalled the key but the engine kept the text answer); English 59 (round 1 had the key answer, uncertain, and the image call flipped it); the English retry reply held two JSON objects (the model corrected itself), `extract_json` failed with "Extra data" and 9 questions (59, 60 among them) were marked malformed and moved to the image call; Science 111 carried a false "missing_text referenced_part_missing" flag and so went to the image call.
- Solver reasoning or key oddity: Vietnamese 16, English 60, Math 67 (an independent recomputation of the printed problem gives the option we chose; the key says another one), Science 111.
- Merge-rule gap: "prefer image on difference" would fix 107 and 117; "prefer an answered text round" would keep 59; neither is right on its own, a tie-break is needed. These fixes are REQ-0083.

## Limits
Seven wrong answers; the image-only pattern is a hypothesis; two possible key oddities across both samples (2026 Math 65, 2025 Math 67): please check the official solutions.

Evidence (untracked): `work/TASK-073/evidence/dgnl2025-score.txt`; the answer list stays in `input/dgnl/` (git-ignored). User instructions honoured: RAW-00198, RAW-00199.

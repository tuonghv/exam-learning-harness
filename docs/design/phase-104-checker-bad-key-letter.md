# Phase 104: checker scores a bad key letter like the engine
Task: TASK-104 (REQ-0112 AC1-AC3)

## Goal
`tools/check_report_pack.py --key` on reports/dhqg2024/main/run-20261114-140941 gives `0 failed`;
key entry "Câu 65. I" is excluded from the scorable total and from WRONG and printed as a key issue.

## Plan modes
- None: read-only checker change; no solve, plan run, cache or pipeline input touched; single-source and pipeline plans unaffected.

## Engine rule (the one to mirror; not imported)
- src/exam_engine/pipeline/explain.py:77-99 `parse_key`: tokens `[^\W\d_]+|\d+`; number followed by
  `[A-Da-d]` = key; number followed by any other 1-char token, number not yet keyed and not yet seen
  = issue `bad_letter`.
- src/exam_engine/pipeline/report_pack.py:50-61 `_score_rows`: key None + number in issues = `keybad`;
  key None otherwise = `nokey`; both outside SCORABLE (:70). Summary md total `**correct / scorable**`
  (:122), scorable = correct + WRONG + declined (dhqg2024 shows 105/119).
- Decision: reimplement the 3-line rule in the checker, do not import `exam_engine`. Why: the checker is
  the independent oracle (`crosscheck`); it already reimplements key parsing (key_map :64) and runs as a
  standalone `python3 -I` tool with no engine on sys.path. Importing would make engine bugs self-confirm.

## Today's defect (cause)
- tools/check_report_pack.py:241-263: a question with no usable key (`k is None`) falls into `wrong`
  (answer given) or `declined` (no answer); denominator is `total` (all questions), not scorable.

## Design
### 104.1 key_map returns bad-letter issues (owner: check_report_pack.py:64 `key_map`)
- Signature `key_map(path) -> (dict[int, str], list[(int, str)])`; second item = (number, token) for each
  number followed by a 1-char non-A-D token while that number is not yet keyed and not yet listed
  (same conditions as explain.py:92). Only caller :242 (grep: no test imports key_map).
### 104.2 recount excludes keyless items (owner: main, :241-263)
- Loop: `k is None` -> `keybad += 1` when the number is in the issue set, else `nokey += 1`; `continue`
  (never correct/WRONG/declined). `scorable = correct + wrong + declined`.
- `score-summary md total` expects `"%d / %d" % (correct, scorable)` (was `total`).
- New check `chk("score-vs-key keybad", keybad, count of tsv rows r[4]=="keybad")` so a mislabelled
  row still bites. `score-vs-key rows` stays `total` (engine writes every question).
### 104.3 key issues listed, not FAIL (owner: main, print block :275-279)
- After the check rows, before `RESULT`: one line per issue `KEYISSUE\t<number>\tbad_letter\t<token>`
  (not in `rows`, so not counted as failed). Output format of existing rows unchanged.

## Failure modes
| Failure | System response | Operator sees |
| key has bad letter, pack agrees | ok, issue listed | `KEYISSUE 65 bad_letter I`, `0 failed` |
| pack summary counts bad item as scored | FAIL | `score-summary md total ... FAIL` |
| engine labels keybad row WRONG | FAIL | `score-vs-key WRONG` and `score-vs-key keybad` FAIL |

## Unit tests (tests/unit/test_report_kinds.py, beside test_85_10_*; fixture setUpClass :171-199)
- T1 `test_104_bad_key_letter_is_key_issue_not_fail`: key file `1 A\n2 I\n3 C\n` in a temp dir, build
  pack with `report_pack.build_pack(..., key=bad)`, run checker with `--key bad` -> rc 0, `0 failed`,
  output contains `KEYISSUE\t2\tbad_letter\tI` and `score-vs-key keybad\t<n>\t<n>\tok` with n >= 1.
- T2 `test_104_summary_disagreeing_with_recount_still_fails`: same pack, rewrite the `**c / s**` total in
  the score-summary md to `**c / s+1**` -> rc 1, regex `score-summary md total\t.*\tFAIL`.
- Existing test_85_10_checker_passes_on_a_complete_pack stays green (key 1 A/2 B/3 C: no keyless item).

## Verification
| Item | command -> expected | tier |
| 104.1-3 | `python3 -I tools/run_tests.py --affected` -> T1, T2 pass | unit |
| real | `python3 -I tools/check_report_pack.py reports/dhqg2024/main/run-20261114-140941 <plan_runs[].dir...> --key input/dgnl/De-thi-mau-DHQG-HCM-2024.answer.txt` -> `0 failed`, `KEYISSUE\t65\tbad_letter\tI`, md total `105 / 119 ok` | free, main runs |

## Risks
- A key file with numbers that have no letter at all (nokey) now drops from the denominator; this
  matches the engine (scorable excludes nokey) and only turns former FAILs into ok when the pack agrees.
- Printed number = `int(q["id"]) + offset_of(plan)` (:248) as today; no change to offset handling.
- No cache/rule key involved (checker is read-only).

## Out of scope
- `missing`/`duplicate` key issues (engine lists them; not named by REQ-0112).
- Manifest `score.total` check (only `total_correct` checked today).

## Defects
- none (content defect in key file "Câu 65. I" is data; engine already reports it as keybad).


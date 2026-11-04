# Phase 76 - Engine fixes from the 2025 scoring (TASK-076)
Task: TASK-076 · REQ-0083 · Status: designed.

# Phase 76 - engine merge fixes (draft for docs/design/phase-76-<slug>.md; slug suggestion `reply-merge-fixes`)
Task: TASK-076 · REQ-0083 · Status: draft
Ids below are exam ids (English printed 59 = id 29, 60 = id 30; Science printed 107/111/117 = id 17/21/27). No key content used.

## Goal
Three engine defects found by scoring DGNL 2025 (work/TASK-073/evidence/dgnl2025-score.txt:13-15) are fixed:
a reply with a self-correction parses, text/image disagreements are settled by a recorded tie-break, and a
group question whose table sits on an earlier group member is not flagged missing_text. Seen when the
replay shows the 9 English ids parsed, ids 17/27/29 adjudicated, id 21 unflagged, and the paid slice re-run scores.

## Constraints
- Single-object, fenced and garbage replies parse exactly as today (all extract_json callers).
- No `--pdf` run: prompts, calls/, result.json byte-identical. Adjudication never changes a PASS (status before the image call).
- Prompts unchanged (adjudicate_prompt cross.py:120 reused as is). No solve reply cache exists (only ingest ReplyCache, keyed on prompt+model; no prompt changes), so no cache-key issue.
- Trust boundary unchanged: replies stay untrusted, validated by core/schema.

## Generality
All exam kinds: parsing, merge and the group-sharing key are format-level (FORMAT.md four-level form, `Source pages:` line); no subject/language literal; one synthetic non-DGNL test per item.

## Known incidents
none found in brief scope (main: check docs/notes/incidents.md for "Extra data" / image merge rows).

## Plan modes
- `--dry-run`: shows the adjudication call in the estimate when image targets exist. `--mock`: replays; an adjudication reply is one more list entry. No `--pdf`: unaffected.

## Design
### 76.1 Multi-object reply (owner: adapters/claude.py:133 extract_json)
- Signature: `extract_json(text, schema=None) -> (obj, None) | (None, reason)`.
- Order: the three existing tries (whole text :137, single fence :140-146, first-{..last-} span :147-151) unchanged.
  New 4th try only when `schema is not None` and the earlier ones failed: `json.JSONDecoder().raw_decode` loop from each `{`
  (skip past each decoded object; ValueError -> next `{`; RecursionError/MemoryError -> stop, as _load :128).
  Fires only with >=2 decoded dicts: return the LAST if `schema.validate(last, schema) == []`, else
  `(None, "last of N JSON objects invalid: <first problem>")`. Never falls back to an earlier object (the model retracted it).
  0 or 1 dict -> today's reason "no valid JSON object found".
- "more than one code fence" (:141-142): unchanged (fences are out of scope; evidence reply is unfenced: plans/dgnl2025/out-English/calls/003-reply.txt lines 1,3,5 = object, prose, object).
- Callers passing `schema=sch.SOLVE_OUT`: solver.py:150, engine.py:264, cross.py:165. Other callers (verifier.py:290, genexam.py:137/229/350, refine.py:304, boundary.py:355, cli.py:335) unchanged.
- Import of core.schema inside claude.py: function-local if a cycle appears.

### 76.2 Text/image tie-break via adjudication (owner: engine.py apply_image :167, image_check :291, adjudicate :214)
- Conflict set (computed in image_check after apply_image):
  (i) answered text + image answer differ (:184-189), ANY status (today :322 filters on reason, so a FAIL like id 17 is missed);
  (ii) NEW "tentative" text: `ans` has a non-empty answer but `answer_status != "answered"` (declined() true, decision.py:12) and the
  image answer differs. apply_image :190-199 then stores `r["text_ans"] = old ans` before replacing (id 29 round 1 shape).
  Excluded: ids whose status was PASS before the image call (snapshot `before = {i: status}` taken in image_check before apply_image).
- Default: adjudication runs whenever the conflict set is non-empty and an image call ran (needs `--pdf`); `--no-adjudicate`
  opts out (cfg["adjudicate"] default True under --pdf; cli.py:64-72, 107-108). See Decision D2 (user OK needed: adds a paid call).
- adjudicate(exam, recs, rn, ids): items = (id, text side, image side), text side = `text_ans` for (ii) else `ans`.
  One call for all conflict ids of the run (unchanged prompt). Outcome per id:
  - reply answer == text side: `ans` = text side; FAIL keeps FAIL+reason; else UNCERTAIN "needs_review: adjudicated".
  - reply answer == image side or other: `ans` = reply; status UNCERTAIN "needs_review: adjudicated" (a FAIL about the old answer no longer applies).
  - `r["source"] = "adjudicated"`; finding ("image","adjudicated","adjudicated: X (text T, image I)") as today :225.
  - failed/missing/declined reply: finding adjudication_failed (:223) and the pre-76 result stays (text kept for (i), image kept for (ii)).
- Budget Stop during the call: same as failed (findings only). est_calls :23 already counts +1.

### 76.3 Group figure sharing key (owner: core/refcheck.py:48-58 _first_line/_shared_figure_flags)
- Rule that fired: refcheck.py:43 (`_FIG` on "bảng dưới đây" in the shared passage, no figure line in id 21's text) because
  `shared_figure` was False: _shared_figure_flags :55-58 keys on the first non-blank line, which is the
  `Source pages:` line written by ingest/api.py:184-186. Ids 19/20 ("Source pages: 18") share the table line of id 19;
  id 21 ("Source pages: 18-19", plans/dgnl2025/Science.md:489) does not -> marker at Science.md:504 (written at ingest, api.py:211/236).
- Change: `_first_line` skips lines matching `^Source pages:` and `^#{1,6}\s` (FORMAT.md section heads); the key becomes the
  group instruction / passage first line. Nothing else (no option-data heuristic: larger, unproven).
- Side effect to check: questions that shared only a `Source pages:` line (same page, different group or no group) used to
  share a figure; now they do not -> possible NEW flags (these were false negatives). Gate in Verification row 76.3b.
- Existing md files keep the baked marker; the fix shows after the exam text is rebuilt from the saved ingest doc (0 calls).

## Failure modes
| Failure | System response | Operator sees |
|---|---|---|
| several objects, last invalid | malformed_output (as today) | finding "last of N JSON objects invalid: ..." |
| hostile nesting in loop | stop loop, old reason | malformed_output |
| adjudication call fails / budget stop | pre-76 merge kept | finding adjudication_failed |
| adjudicator returns a third answer | taken, UNCERTAIN adjudicated | finding with all three letters |
| conflict id was PASS | not adjudicated | existing image_differs finding |
| sharing key change adds flags | more image targets / declines | WARN lines (59.1); row 76.3b diff |

## Unit tests (synthetic, stdlib)
- 76.1: two valid SOLVE_OUT objects with prose between -> last returned; first valid + last invalid -> None with "last of 2"; single object, fenced object, garbage, two fences -> byte-identical results to today (table test); schema=None with two objects -> old reason; deep nesting -> no crash.
- 76.1 integration: solve_round with a fake runner whose reply holds two objects -> ids answered, no malformed_output.
- 76.2: differ + UNCERTAIN -> adjudicated, source "adjudicated"; differ + FAIL (wider scope) is in the set; tentative text + differing image -> text_ans kept, both sides sent; pre-image PASS -> never adjudicated, status unchanged; adjudication failure -> pre-76 result + adjudication_failed; reply = text side on FAIL -> FAIL kept; `--no-adjudicate` -> calls equal today's; no --pdf -> no call.
- 76.3: three texts with same group head but different `Source pages:` lines, figure on the first -> [[],[],[]]; two ungrouped texts with same `Source pages:` line, figure on one -> the other flagged; existing test_refcheck.py:89-106 and test_multipage_assembly.py:165 unchanged; synthetic non-DGNL (English-language) group.
- Full suite: `python3 -I -m unittest discover -s tests/unit`.

## Verification (lowest tier first)
| Item | command -> expected | cost |
|---|---|---|
| 76.1 | replay English: `--mock` list built from out-English/calls/001-005 reply files (+1 synthetic adjudicate reply), same config.json flags -> no malformed_output on the 9 retry ids | 0 |
| 76.2 | same replay + Science replay -> ids 17, 27, 29 carry finding adjudicated (synthetic reply), no PASS changed (diff of statuses vs saved result.json) | 0 |
| 76.3a | rebuild Science exam text from the saved ingest doc (TASK-073 command, ingest cache) -> no marker on id 21 | 0 |
| 76.3b | rebuild all 2025 + 2026 exam texts, diff `[Incomplete:` lines and solve `--dry-run` WARN lines old vs new -> only id 21 removed; any added line listed and reviewed by main | 0 |
| paid | slice re-run of changed ids with their groups (English retry ids + Science 17/21/27), `--dry-run` estimate first, cap 1.0 USD (full two subjects ~0.93 + ~0.12 adjudication would exceed it) -> scored against the 2025 answers by main | <=1.0 |
| regression | 2026 regset `benchmark --set evals/regset.json --channel dev` -> score not below run 3 (111/120), calls +<=1 per subject | ~0.7 |

## Cost per fix
76.1: 0 (may save a retry/image page). 76.2: +1 call per run with a conflict, ~0.04-0.08 USD; 2025 run would have had 2 (English, Science). 76.3: 0 (may remove image targets).

## Decisions
- D1 extract_json: last object + schema check, opt-in by schema - rejected: first object (the retracted one), any-valid object (hides a bad correction), always-on for all callers (changes genexam/refine parsing untested).
- D2 tie-break: (a) adjudication, default on under --pdf with `--no-adjudicate` - NEEDS USER OK (adds one paid call per run).
  - (b) uncertainty rule: 0 USD but fitted to 3 cases; id 17/27 text was medium, id 29 text tentative; image side uncertainty not comparable; would encode a guess. Rejected.
  - (c) third vote via --second-sample: ~0.06-0.1 USD per batch, a text-only resolve correlates with the text round (wrong in 17/27), and 75.2 defines it as never touching `ans`. Rejected.
  - (a) expected: the adjudicator sees both explanations; effect on 17/27/29 unknown until the paid slice; worst case equals today (status stays UNCERTAIN/FAIL, never PASS). Alternative if user declines default-on: keep `--adjudicate` opt-in and enable it in the DGNL plan/benchmark config.
- D3 refcheck: skip structural lines in the sharing key - rejected: "options carry their own data" heuristic (subject-specific, untestable generally), group-context table lookup (needs parser groups at ingest).

- D-coordinator-1 (D2, taken within my autonomy, user told afterwards): adjudication is on by default under `--pdf` with `--no-adjudicate` to opt out. It runs only when the conflict set is non-empty (a few ids per run, one call about 0.05 USD) and only on runs that already use the paid image call; the worst case equals today (status stays UNCERTAIN or FAIL, never PASS).
- D-coordinator-2 Gain is reported on both exams (learn 2025, hold-out 2026 and the regression set), see REQ-0084.
## Out of scope
Fences with several objects; reasoning errors (Vietnamese 16, English 60, Math 67, Science 111 answer); key oddities; prompt changes.

## Defects
- DEF-76-1 (high) adapters/claude.py:147-152: reply with two objects fails "Extra data"; evidence out-English/calls/003-reply.txt; 9 ids malformed.
- DEF-76-2 (high) engine.py:322: adjudication set filters on reason "text/image differ", missing a FAIL conflict (id 17, doubt scope keeps FAIL :187).
- DEF-76-3 (high) engine.py:190-199: a tentative text answer (answer_status uncertain, letter given) is replaced silently by the image answer (id 29).
- DEF-76-4 (medium) core/refcheck.py:48-58 with ingest/api.py:184-186: figure sharing keyed on the `Source pages:` line; false missing_text on a group member spanning another page span (Science id 21); same key also over-shares across groups on one page.
- DEF-76-5 (low) docs: adjudication is off by default, so the phase-73 run had no tie-break at all (config.json has no adjudicate).

Nova

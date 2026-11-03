# Report phase 62: exam-kind generality, slice A (TASK-062; REQ-0068)

Verdict: slice A adopted. A new exam kind (other language, subject, part headings, generator profile) is now data, not code, for ingest, checks and gen-exams. Default config keeps every old input byte-identical: before/after over 102 inputs and 4 gen-exams profiles shows 0 differences; the only two intended differences are the `PART` heading (D2: `refine.split_part` PART II was None, now II) and the manifest `prompt_sha256` of the 3 non-hs profiles (D1: it now follows the profile's own prompt).

## What changed (all free, no prompt change)
- 62.G golden test freezes today's patterns before any edit (33 tests).
- 62.1 `config/lang.json` word lists merged with the existing vi+en literals (union, not switched by `Language:` which only sets the explanation language); words are escaped, never regex from config; a bad file fails naming it.
- 62.2/62.3 verdict and reference-check tables; 62.4 `config/subjects.json` for answer shapes and open tasks (a task alias such as `văn` also counts, V3); 62.5 allowed scripts for the garble test (Cyrillic, Greek tested); 62.6 `config/genexam_profiles.json` with prompt paths validated (`..`, absolute, empty, non-str refused, V1).
- 62.9 the "Generality" rule is in the design skill and docs/guide/architecture.md.
- Audit (REQ-0068 AC1): about 17 hard-codes to generalise, 9 data to keep.

## Evidence (work/TASK-062/evidence/, not published: evidence_required off)
Full suite 1200 tests, only baseline failures; 9/9 mutations (merge, escape, loader, casefold) killed; a French/chemistry exam handled with data edits only.

## Limits
Slice B (62.7 route-B part structure, 62.8 generic dev prompt wording, with a paid check) is REQ-0070. This is a code and tests result: it does not show a quality gain on real exams; REQ-0069 (scoreboard) measures that.

User instructions honoured: RAW-00187.

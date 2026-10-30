# Phase 28 report: extract and solve the whole real ĐGNL sample (REQ-0033, TASK-028)

## Result
- Extraction: `ingest-refine --all-pages` (vision, 22 pages in batches) gave all 120 questions, about $0.8. Exam files per section (Vietnamese 1-30, English 31-60, math 61-90, science 91-120) via `ingest --refined --questions`.
- Solve: unchanged engine, v1.2.0, 4 sections, $1.53 for the last run (about $4 spent over three runs). No key exists: every status is `uncertain`/`unresolved`, none `pass`.
- Answers by printed exam number (a dash = engine declined; 66 needs the cable diagram):

| Section | n | Answers |
|---|---|---|
| Vietnamese |30|1D 2B 3D 4B 5D 6B 7D 8A 9B 10- 11A 12C 13A 14- 15C 16D 17B 18A 19C 20D 21D 22B 23- 24C 25D 26A 27C 28C 29D 30C |
| English |30|31C 32B 33A 34D 35B 36C 37B 38C 39A 40B 41C 42D 43A 44C 45B 46A 47C 48C 49B 50C 51A 52B 53B 54D 55B 56D 57A 58C 59A 60C |
| Math |30|61B 62C 63C 64D 65A 66- 67A 68C 69A 70B 71B 72D 73A 74C 75B 76C 77B 78A 79B 80D 81D 82A 83C 84B 85A 86D 87C 88B 89A 90C |
| Science |30|91C 92B 93D 94C 95C 96A 97C 98C 99B 100C 101C 102A 103C 104D 105D 106A 107A 108A 109D 110C 111A 112D 113D 114A 115A 116A 117B 118B 119C 120A |

- Check: math 61-71 equals my hand computation 10/10 (66 excluded), now from vision extraction, not my transcription. Other sections have no oracle: 103 of 120 answers carry solver doubt "low", 10 "not low", 4 unanswered (10, 14, 23, 66). Seven science numeric answers (97, 98, 99, 101, 102, 105, 107) came back as a value, mapped to the one option that equals it.

## Findings (engine gaps, fixed in extraction, not in the solver)
- First solve: 21 quote-check fails, 18 "missing text": the group passage was only in the first question. Fixed (context per question, carry across pages, joined split questions): fails 21 -> 1 on language, declines 18 -> 6.
- Open: solver returns the value instead of the letter for numeric MC questions (science), format check fails; figure questions rely on the vision description of the figure.
- Not verified: language and science accuracy (no key). Agreement is not an accuracy figure.

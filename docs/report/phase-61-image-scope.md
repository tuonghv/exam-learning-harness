# Report phase 61: image scope for cut/declined and doubtful questions (TASK-061; REQ-0067)

Verdict: adopted, opt-in. `solve --pdf FILE --image-scope flagged|declined|doubt` (default `flagged` = old behaviour, byte-identical on 134 golden cases / 47 inputs). `declined` also sends cut or marker-declined questions to the one capped page-image call; `doubt` adds answered questions whose reason is doubtful (uncertain, reviewer unsure/disagrees, no review). A second read is a labelled proxy (`image_agrees` finding), never PASS; a differing image answer sets `needs_review`; an unreadable image keeps the text result or the decline; optional `--adjudicate` (+1 call, only for differing ids) records a finding and keeps the status UNCERTAIN. Metrics rows: `image_scope`, `image_agrees`, `image_differs`.

## General by design (RAW-00187)
Scope is chosen from generic signals (decline reason, flagged figure refs, doubt reasons), not from exam, subject or question number. Defect D5 found in the real run: `Source pages:` was written only for four-level questions, so unlabelled exams had no pages for the image check. Ingest now writes it for every refined question with a page; the parser keeps it as `q.pages` and removes it from unlabelled prompt text (prompts byte-equal, 5 mutations killed).

## Real checks (paid, coordinator inside caps, RAW-00186)
P1 `declined`: 0.149 USD, 4/4 answered, 0 declined (the window path already returns cut questions whole), image checked 1, changed 1. P2 `doubt`: 0.183 USD, 2 checked, 1 agrees, 0 differs. P3 not needed. Total 0.33 USD of a 2.50 cap.

## Limits
4 questions, one exam, no answer key: no accuracy claim. The declined path was not exercised on a real declined question (mocks only); adjudication never ran live; a dry run cannot list doubtful ids before the solve. REQ-0068 (generality fixes, about 17 items) follows.

Evidence: work/TASK-061/evidence/ (not published: evidence_required off). User instructions honoured: RAW-00183, RAW-00186, RAW-00187.

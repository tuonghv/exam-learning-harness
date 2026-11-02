# Report phase 48: provenance sidecar and prompt lines (TASK-048; REQ-0052)

Verdict: adopted at tier 0 (mock/fixtures; no paid run needed). Ingest now writes `<exam-out>.assembly.json` beside the exam text: per question id, printed number, `source_pages` (refined: page + continued pages; text path: empty list, no page data exists), `assembly_status` complete|uncertain (orphan, cut unresolved) and `validation_status` passed|failed with reasons. `ingest-inspect` prints it as an `## Assembly` table, and solve / `plan-import` copy it into the plan run (`input/`). The exam text, doc.json and refined outputs are unchanged (byte-identical to baseline 63a5299; the sidecar is the only new file). Two prompt lines on the dev channel only: refine.md "never transcribe running headers, footers or page numbers"; system.md (and lang/vi) decline rule extended to incomplete or merged questions, `issues` starting `missing_text:`.

## Evidence (docs/report/evidence/TASK-048/)
suite-final.txt and head-failures.txt vs baseline-failures.txt (same known failures as baseline 083d0e4), test.md (21 assembly tests, 5 mutations killed, golden identical), verify.md.

## Limits
- Prompt lines are dev channel only; the frozen release stays v1.0.0 (config/engine.json), so a normal solve does not see the system.md change until a release is promoted.
- Editing refine.md voids cached refine pages (the cache key contains the prompt hash).
- The added solve line costs about 46 tokens (en), not the 25-30 estimated.
- A `missing_text:` decline produced by the new rule counts in `declined` but not in `declined_missing_text` in the REQ-0060 metrics.
- Text-path questions have empty `source_pages`. The verifier had no shell and judged from code and the tester's saved evidence; one low test hygiene item (unclosed files in test_assembly_qa.py).

User instructions honoured: RAW-00146 (completeness guide).
Evidence files for crosscheck: docs/report/evidence/TASK-048/test.md, docs/report/evidence/TASK-048/verify.md (index: docs/report/INDEX.md).

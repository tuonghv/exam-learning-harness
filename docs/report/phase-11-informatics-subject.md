# Report: TASK-011 Informatics subject + bilingual names (REQ-0015)

**Verdict: adopted.** Subjects resolve from Vietnamese or English names (diacritics optional, any case) via `utils/text.fold`; `informatics` (Tin hoc, IT, Information Technology, Informatics, CNTT) has a config entry, default and vi prompts, a FORMAT.md section and 5 examples.

## Items (answers recomputed with Python stdlib, sqlite3 for SQL)
001 binary 1011010 = 90 (C); 002 boolean value (C); 003 loop trace s = 12 (B); 004 `COUNT(*) WHERE diem < 5` = 3 (NULL trap); 005 /26 hosts = 62.

## Verification
- Suite 251 unit + integration OK; `check-examples` OK 25 pairs; `check-prompts --channel dev` OK; wrong key 004 fails the oracle.
- Verifier re-solved all five: match; AC1-AC4 pass. Minor D1 (edge-case line in key 003), D2 (alias uniqueness test) fixed; D3 (evidence header) noted.

## Limitations
- Informatics prompt overlay lives in dev only: default release v1.0.0 and v1.1.0 do not include it. Cut a new release (v1.2.0) before a benchmark.
- Question types are limited to checkable items; no programming essays.

## Next
REQ-0009 real benchmark (needs your go), architecture doc (REQ-0007).

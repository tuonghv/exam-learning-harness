# Phase 10: prompt language variants + interface validator (REQ-0014, TASK-010; EPIC-004)

## Goal
Many prompt variants (by language), one interface, one engine, one output JSON. A script proves each variant keeps the interface. Answers accepted (RAW-00046): language axis first, subject overlay second; English instructions are the default, a Vietnamese variant proves the mechanism.

## Layout (inside each channel, so releases freeze variants too)
- `prompts/<ch>/` root files = the **default** variant (English instructions; unchanged, so release v1.0.0 stays valid).
- `prompts/<ch>/lang/<code>/<same relative path>` = a variant, e.g. `lang/vi/system.md`, `lang/vi/exam/solve.md`, `lang/vi/verification/verify_answer.md`, `lang/vi/subjects/<subject>.md`.
- Lookup `read_prompt(rel, lang=None)`: `lang/<lang>/<rel>` if it exists, else `<rel>`. Missing file in a variant = fallback, never an error.
- Variant code = the exam's explanation language (`router.language(exam)`: `vi`, `en`; `en` has no dir, so it uses the default). Callers pass `lang`; nothing else changes.

## Interface contract: `prompts/contract.json` (engine-owned, not per channel)
```
{"schema_version":"1.0",
 "prompts":{
  "system.md":{"markers":[...],"output":null},
  "exam/solve.md":{"markers":[...],"output":{"anchor":"{\"schema_version\"","schema":"solve_out"}},
  "verification/verify_answer.md":{"markers":[...],"output":{"anchor":"{\"reviews\"","schema":"qa_out"}}},
 "subjects":{"literature":{"markers":["Passage"]},"*":{"markers":[]}}}
```
Markers are language-neutral tokens that must appear verbatim in every variant (field names and enum values, not prose):
- system.md: `answer_status`, `uncertain`, `unanswerable`, `not_independently_verified`, `uncertainty`, `issues`, `sqrt(3)`.
- exam/solve.md: `Language:`, `expr`, `checks`, `answer_status`, `schema_version`, `Open`, `c-a-d-b-e`.
- verification/verify_answer.md: `verdict`, `agree`, `disagree`, `unsure`, `findings`, `reviews`.
- subjects/literature.md: `Passage`.
Output example: the JSON object starting at `anchor` is extracted (`json.JSONDecoder().raw_decode`), must parse, must have the same key structure (recursive keys, not values) as the default variant's, and its keys must exist in the named schema.

## Validator
`scripts/exam.py check-prompts [--channel C] [--version V] [--all]` -> for each prompt present in the default and each variant file: markers present, output example parses and matches the default's key structure, no file outside the contract list under `lang/<code>/` (typo guard), variant code matches `^[a-z]{2}$`, default files all exist. Output: one line per problem `ERROR <path>: <what>`, final `OK: N files, M variants`, exit 1 on any error. `--all` = dev + every release. Stdlib only.

## Files
- A (code): `settings.read_prompt(rel, lang=None)`, callers in `pipeline/solver.py` and `pipeline/verifier.py`, `pipeline/prompts.py` `check_prompts()`, CLI `check-prompts`, `prompts/contract.json`, tests `tests/unit/test_prompt_variants.py` (broken-variant mutations on a TEMP copy: drop marker, change output key, stray file, bad code; fallback; vi chosen for `Language: vi`).
- B (content): `prompts/dev/lang/vi/{system.md,exam/solve.md,verification/verify_answer.md,subjects/{math,physics,english,literature}.md}`: faithful Vietnamese versions, same rules and the same JSON example, all markers kept verbatim.
- Release: coordinator runs `prompts release v1.1.0` after check-prompts is green and bumps `config/engine.json` `prompt_release` (frozen v1.0.0 untouched).

## Out of scope
New subjects (REQ-0015). Benchmark of vi vs default (REQ-0009).

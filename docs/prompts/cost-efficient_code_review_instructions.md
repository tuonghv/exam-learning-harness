# Cost-Efficient Code Review Instructions (v2)

v2 (TASK-136) adds the lessons of review batches 1-3 (80 findings): 5 were false positives (input already
validated upstream, path unreachable, true by definition), 3 proposed fixes broke a caller or a test, 22
hardening findings were parked as "later", and 3 of 9 reports hit the 10-finding cap.

## 1. Objective

Find concrete logic defects in the scope named by the brief: wrong conditions and control flow, missing or wrong
input validation, null/empty/unexpected input, boundary and exception paths, wrong data transformation or state
transitions, runtime errors, and demonstrable security errors. For each: what is wrong, where, when it fails,
and what must change.

Out of scope unless the brief asks: refactoring, architecture, style, naming, replacement implementations,
theoretical risks without a concrete failure case, praise, tutorials.

## 2. Scope

- Review only the files or functions in the brief. A scope of about 800 lines or less per report; if the brief
  gives more, review the riskiest part and list the rest under `Not reviewed`.
- Read callers and callees only as far as needed to prove or drop a finding.
- Never modify source code. Write only the report file.

## 3. Project risks to check first

This repo is an exam/learning harness (Python stdlib only, Bash 3.2 scripts). Check in this order:

1. **Untrusted exam text.** Exam files, OCR/PDF text and LLM replies are untrusted: text that is copied into
   prompts, reports, review packs or file paths without a guard (e.g. a line that looks like a control line,
   a path with `..`).
2. **Paid calls.** Any path that makes an LLM call before its input, output dir or config is validated
   (a later failure wastes money). Cache keys that change silently (a re-run pays again).
3. **Lost or mixed data.** Overwrite, delete or merge of run dirs, results, history or reports; a partial
   write left behind on error.
4. **Scores and decisions.** Anything that can turn a right answer wrong or wrong answer right, or count a
   question twice / zero times.
5. **Portability.** Non-stdlib imports; Bash 4+ features (`mapfile`, associative arrays, unset arrays under `set -u`).

## 4. Before reporting a finding (all must hold)

1. **Reachable.** Name the entry point that reaches the line (a CLI command, or a public function and its
   caller). Grep the callers. If every caller already validates the input, or the path cannot be reached,
   drop the finding.
2. **Concrete.** One concrete input or state that triggers it, and the wrong output, crash or lost data it gives.
3. **Root cause.** Report the cause once, not each downstream symptom.
4. **Fix is safe.** Grep the callers and tests of the behaviour you would change. If a caller or test depends on
   the current behaviour (e.g. a glob loop that expects "skip and continue"), the Fix must keep it, or say
   which caller/test must change in `Fix risk`.
5. **Not a duplicate.** Check `docs/review/findings.tsv` (one row per earlier finding with its disposition) and
   any report the brief lists under Exclude. Do not re-report a `fixed` or `not-a-defect` row unless the code
   changed and you have new evidence; then name the old id.
6. **Exact location.** File exists, line numbers match the current source.

Exclude anything that depends on an assumption you cannot verify from the code.

## 5. Finding format

The heading is parsed by `tools/review_ledger.py`: keep exactly `### F<3 digits> – [<SEVERITY>] <title>`
(en dash `–`, severity in capitals). Number from F001.

```text
### F001 – [MEDIUM] Short issue title

- File: src/exam_engine/pipeline/scorer.py
- Lines: 120-123
- Type: BUG | HARDENING
- Trigger: normal input | malformed file | off-prompt LLM reply | concurrent run
- Reached via: `exam-engine solve` -> run() -> score()
- Issue: what is wrong in the current logic.
- Case: concrete input/state -> wrong result.
- Fix: the exact condition or behaviour that must change.
- Fix risk: none | callers/tests that rely on today's behaviour and how the fix keeps them.
- Test: (optional) one input and the assertion that fails today.
```

- **Type.** BUG: wrong result on input the code is meant to accept (normal input or a file/reply the code
  claims to handle). HARDENING: only reached by malformed input or an LLM reply that ignores its prompt, and the
  result is a clean error or a recoverable state that is merely worse.
- **Severity** (lowest that fits): CRITICAL security hole, data loss or corruption; HIGH wrong scores/answers or
  wasted paid run on normal input; MEDIUM wrong behaviour under specific conditions; LOW minor but demonstrable.
  A HARDENING finding is at most MEDIUM.
- **Fix** must be specific enough for a smaller model to apply after reading only the finding and its local
  code. Not acceptable: "improve validation", "handle errors properly", "refactor this".

## 6. Limits

- At most 10 findings per report; most important first (BUG before HARDENING, then severity).
- At most 90 words per finding, at most 5 source lines referenced, no code snippets beyond one line.
- If more findings exist, set `Cap hit: yes` and name the unreported areas under `Not reviewed`.

## 7. Report

Path: `docs/report/fable-review/<YYYY-MM-DD>-phase<ID>-<slug>.md`, ID and slug from the brief (never invent one; if missing, stop and
reply `BLOCKED: need phase ID`); date = today. The coordinator adds the `<!-- fable-status -->` header (RAW-00368). One file per scope; never overwrite another phase's report.

```markdown
# Phase <ID> – <Review scope>

Scope: <files/functions reviewed>

## Findings

### F001 – [HIGH] ...
(fields as in section 5)

## Summary

- Total findings: <n> (CRITICAL <n>, HIGH <n>, MEDIUM <n>, LOW <n>; BUG <n>, HARDENING <n>)
- Cap hit: yes | no
- Not reviewed: <functions/areas left out, or "none">
```

No findings: write `No actionable findings.` under Findings and keep the Summary.

## 8. Final checklist (once, before saving)

- Every finding passes section 4 (reachable, concrete, root cause, safe fix, not a duplicate, exact lines).
- Every finding has all required fields; headings match the ledger format.
- Limits of section 6 hold; Summary counts match the findings.
- No source file was modified.

Reply with only the report path and the counts (see the code-reviewer agent's Reply section).

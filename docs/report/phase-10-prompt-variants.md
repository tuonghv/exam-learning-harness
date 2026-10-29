# Report: TASK-010 prompt language variants + validator (REQ-0014)

**Verdict: adopted.** Variants live in `prompts/<channel>/lang/<code>/` over the default (English) files; `prompts/contract.json` lists language-neutral markers and the output-JSON example per prompt; `exam.py check-prompts [--channel C|--version V|--all]` exits 1 on any drift. The engine picks the variant from the exam `Language:`; the output JSON and schema are the same.

## Shipped
- Vietnamese variant (system, solve, verify, 4 subject overlays), verified by the verifier as rule-for-rule faithful.
- Release `v1.1.0` (includes vi). **Default release stays `v1.0.0`** (no variants): the accepted decision is English instructions by default and vi only if the benchmark shows a gain (REQ-0009). Switch with `prompt_release` in `config/engine.json` or `--prompt-version v1.1.0`.

## Verification
- Suite 241 unit + integration OK; `check-prompts --all` OK; real-file mutations on dev (dropped marker, changed output key, stray file) each exit 1.
- Verifier: AC1-AC3 pass, AC4 partial. Found major D1 (untrusted `Language:` header used in a path): fixed with a 2-letter code check, tested. D2 (mock run per variant), D3 (substring markers -> word-boundary) fixed with tests.

## Limitations
- Markers prove interface, not translation quality; vi quality is judged only by the benchmark.
- Markers are tokens; a marker in a comment still counts.

## Next
REQ-0015 (IT subject and bilingual aliases).

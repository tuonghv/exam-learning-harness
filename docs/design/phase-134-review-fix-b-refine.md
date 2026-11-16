# Phase 134 – Review leftovers fix B: refine hardening (TASK-134, REQ-0141)

Source: re-triage work/TASK-131/handoff/design-ingest.md (rows 108-F003..F009, current lines, minimal fixes, repros).

## Plan modes
`ingest-refine` (paid AI path, used by single-source and pipeline plans). Only the merge of replies changes; no
prompt, reply schema or cache key change (cached replies are re-read by the new logic). Well-formed replies give the
same output (existing refine tests and goldens stay green).

## Design
- 134.1 108-F003 refine `_attach`: number check on the continuation's first line only
  (`segment._Q.match(cont["text"].split("\n", 1)[0])`).
- 134.2 108-F006 bridge: `owner_has_options` only when the continuation's option letters overlap the owner's;
  otherwise merge (`dict(o["options"], **cont["options"])`).
- 134.3 108-F007 keep `carried` when a reply has no `continues` key (`if carried and not numbered:`).
- 134.4 108-F008 consume `carried` only for kept entries (move the block below the heading-only skip).
- 134.5 108-F009 window-path gap check over the pending question's pages only (same filter as `done`).

## Verification ($0)
tests/unit/test_review_fix_b_134.py with the Fake llm of test_ingest_refine (one test per id + a `2) ...`
continuation case), each failing on old code; existing refine tests green; `--fast` NEW 0; 5 ledger rows fixed.

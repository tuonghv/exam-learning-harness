# Report phase 34: compaction and hook bytes in a later session (TASK-034; REQ-0038)

Verdict: the REQ-0006 fix is effective. A later session (12.8 MB, about 28.6 h, 48 user prompts) had 1 compaction against 18 in the 34 MB baseline (0.08 per MB vs 0.53). Hook output per event fell: SessionStart startup about 1,058 B (baseline 1,732,848 B, about 1,600x smaller), SessionStart compact about 872 B (104,194 B, about 120x), UserPromptSubmit 494 B average (1,127 B; 0.44x, and 0.74x in total with 241 events), PreToolUse:Bash about 235 B (751 B; 0.31x), skill listing about 0.1x. Stop hook (not in the baseline): 127 events at 140 B, negligible.

## Method
Counts from the session transcript (numbers only): compactions via the compact_boundary entry and the isCompactSummary marker (both 1); hook bytes from attachment stdout (counted once); cross-checked by an independent recount (UserPromptSubmit 242 events, 119,155 B vs the inspector's 241 / 119,009 B). Table: `work/TASK-034/evidence/measure.txt`.

## Limits
Small sample (one compaction, two SessionStart events); the baseline counting method was not re-verified, so ratios are approximate; preTokens at the single compaction (436,984) is close to the baseline's first compaction and cannot be compared for later ones. Watch item: UserPromptSubmit has the most events and the largest recurring total (119 KB); its 494 B average is within the 1,000 B cap and grows with prompt count; no new REQ.

User instructions honoured: RAW-00128.

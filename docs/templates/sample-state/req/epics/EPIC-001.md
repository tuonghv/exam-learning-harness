---
id: EPIC-001
title: Run-over-run accuracy of pipeline reports
source: [RAW-00003, RAW-00004]
created: 2026-09-27 16:07
updated: 2026-09-29 18:18
---
## Original (verbatim, never edit)
> **[RAW-00003]** 2026-09-27 15:59
> please just last run for run-20260927-112049 for Upzi_g02. I see some new findings. So please analyze why have new findings, is it wrong, is it accuracy, do we change model for phase 0, 1, 2b. What is impact the report. Is new findings is just improvement. But consider  VulnerabilityCategory, Severity with High then Mediun and others. Have any improvement recently impact to report with more accuary or just noice.

> **[RAW-00004]** 2026-09-27 16:06
> open REQs for 2, 3 and 4, it could be better, if any false positive findings just please help to improve. Verify carefully any miss findings with High, Medium and for each new findings should deep dive why, we can also choose opus model if needed to qualify the the result report in correct. conclude finding json is correct.

## Goal
Make each pipeline run's report reflect real changes only: consistent run diffs, trust-model false positives flagged in the deterministic layer, not-re-found findings kept visible, and new/missing High/Medium findings verified by a model before hand-over.

## Decomposition
<!-- One line per child: "- REQ-0012" (auto-added) or "- [ ] TBD: <coarse item not yet specified>". TBD lines are tracked until converted into REQs. -->
- REQ-0001
- REQ-0002
- REQ-0003
- REQ-0004
- REQ-0005
- REQ-0006
- REQ-0028
- REQ-0020
- REQ-0028

## Notes
Evidence, run 20260927-112049 vs 20260925-142931 (2026-09-27, no source read):
- Same model (claude-sonnet-5) in phases 0/1/2b; phase 1 prompts byte-identical; phase 0 recon mode only.
- 2b cap 6 -> 30 (default): 16 units, XR 1 -> 8 (6 of 7 new are R5; R4/R5 reasoning treats X-User-Id as client-controlled -> REQ-0002).
- New High/Medium already upheld by 2b finding_checks: jobseeker-003, jobseeker-006, jobseekers-info-service-005 (second route disputed).
- Not verified by anything: jobseeker-005 (secrets, confidence Low), jobseekers-info-service-004 (check-application-exist); not re-found: old -004 delete-user body userId, old -007 filePath (likely = new -005) -> REQ-0003/REQ-0004.
- conclusion.json: 15 shown / 0 hidden, High 6 / Medium 9, coverage gaps=0; 9 of 15 not-checked (4 High, all found in both runs).
- Chain diff: X-R3 meta-service chains listed as fixed+new after meta-service-001 CWE-749 -> CWE-284 relabel -> REQ-0001.

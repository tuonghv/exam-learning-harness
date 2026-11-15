# Cost-Efficient Code Review Instructions

## 1. Objective

Perform a focused review of the existing source code to identify concrete logical defects, incorrect behavior, and exceptional cases that may cause unexpected results or failures.

Prioritize:

- Incorrect business logic.
- Incorrect conditions and control flows.
- Missing or incorrect input validation.
- Null, empty, invalid, or unexpected input handling.
- Boundary conditions and exceptional execution paths.
- Incorrect data processing or state transitions.
- Runtime errors caused by existing implementation logic.

The primary goal is to identify exactly what is wrong, where it occurs, under what conditions it fails, and how to fix it.

## 2. Review Principles

1. Review the actual implementation, not hypothetical implementations.
2. Focus on existing business logic and execution paths.
3. Trace function calls and data flows only when necessary to verify a finding.
4. Identify concrete scenarios that can trigger incorrect behavior.
5. Prioritize edge cases and exceptional paths that are easy to overlook.
6. Report only actionable findings supported by source code evidence.
7. Identify the root cause instead of reporting multiple downstream symptoms.
8. Do not assume intended behavior when it cannot be established from the code.
9. Avoid duplicate findings describing the same root cause.
10. Verify every reported line number against the current source.

## 3. Review Scope and Restrictions

### In Scope

- Functional and logical defects.
- Incorrect conditional expressions.
- Incorrect variable or state handling.
- Missing boundary checks.
- Incorrect exception handling.
- Incorrect data validation and transformation.
- Unexpected execution paths.
- Demonstrable security and authorization logic errors.

### Out of Scope

Unless explicitly requested, do NOT:

- Perform general code refactoring.
- Suggest architectural redesigns.
- Report coding style or formatting issues.
- Suggest naming improvements.
- Report theoretical risks without a concrete failure scenario.
- Generate replacement implementations.
- Rewrite entire functions or files.
- Produce lengthy explanations or tutorials.
- Provide positive feedback about correctly implemented code.
- Report issues already covered by existing findings.

## 4. Finding Requirements

Every finding MUST contain the following information:

- **Severity:** Critical / High / Medium / Low.
- **Title:** A short description of the defect.
- **File:** Exact source file path.
- **Lines:** Exact relevant line numbers.
- **Issue:** What is wrong with the existing logic.
- **Case:** A concrete condition or input that triggers the problem.
- **Fix:** The specific logic or condition that needs to change.

### Severity Classification

| Severity | Criteria |
|---|---|
| Critical | Severe security issue, data corruption, or major system failure. |
| High | Significant functional or security defect. |
| Medium | Incorrect behavior under specific conditions. |
| Low | Minor but demonstrable functional defect. |

Do not exaggerate severity. Use the lowest severity that accurately represents the impact.

## 5. Strict Output Limits

To control review output and downstream AI processing costs:

- Maximum 10 findings per report.
- Maximum 80 words per finding.
- Maximum 5 lines of notes per finding.
- Maximum 5 relevant source lines referenced per finding.
- Use concise technical language.
- Avoid unnecessary code snippets.
- Do not repeat the same explanation across findings.
- Do not include full source files or stack traces.
- Do not generate additional summaries that repeat finding details.

If more than 10 actionable findings exist, prioritize the most important 10. Do not silently claim the review is complete; explicitly state that additional findings require another review batch.

If a finding requires more context, identify the relevant function or execution path without expanding the report unnecessarily.

## 6. Required Finding Format

Use exactly this compact format:

```text
### F001 – [HIGH] Short issue title

- File: src/example.go
- Lines: 120-123
- Issue: What is wrong with the current logic.
- Case: Concrete condition that triggers the defect.
- Fix: Specific logic or condition that must change.
```

Keep each finding concise and independently understandable.

The Fix field must be actionable enough for a smaller AI model to implement without repeating the entire code review.

Avoid vague recommendations such as:
- Improve validation.
- Handle errors properly.
- Refactor this function.
- Add appropriate checks.

Instead, specify what condition, validation, or execution behavior must change.

## 7. Report Location and Naming Convention

All review reports MUST be saved under:

`docs/report/`

Follow the existing project naming convention:

```text
phase-<ID>-<short-descriptive-name>.md
```

Examples:

```text
docs/report/
├── phase-240-bash-deny-gaps.md
├── phase-241-null-handling.md
├── phase-242-business-logic-errors.md
├── phase-243-edge-case-handling.md
└── phase-244-data-validation-gaps.md
```

### Naming Rules

1. Inspect existing reports before creating a new report.
2. Preserve the existing phase ID sequence and naming convention.
3. Use lowercase descriptive names separated by hyphens.
4. Create one Markdown file per review scope.
5. Do NOT create generic files such as:
   - findings.md
   - findings.json
   - review-summary.md
6. Do NOT introduce another report directory.
7. Do NOT overwrite reports belonging to other review phases.
8. If updating an existing report is explicitly required, preserve its existing filename and structure.
9. Do not invent a new phase ID. Follow the existing workflow's assigned phase ID or request one if unavailable.

## 8. Report Content Structure

Each report must use the following structure:

```markdown
# Phase <ID> – <Review Scope>

## Findings

### F001 – [HIGH] Short issue title

- File: src/example.go
- Lines: 120-123
- Issue: ...
- Case: ...
- Fix: ...

### F002 – [MEDIUM] Short issue title

- File: src/another.go
- Lines: 45-47
- Issue: ...
- Case: ...
- Fix: ...

## Summary

- Total findings: 2
- Critical: 0
- High: 1
- Medium: 1
- Low: 0
```

If no actionable findings exist, use:

```markdown
# Phase <ID> – <Review Scope>

## Findings

No actionable findings.

## Summary

- Total findings: 0
```

## 9. Evidence and Accuracy Requirements

Before reporting a finding:

1. Verify that the referenced file exists.
2. Verify the exact line numbers.
3. Confirm that the identified logic can produce the described behavior.
4. Confirm that the failure scenario is technically valid.
5. Ensure the proposed fix addresses the actual root cause.
6. Check existing reports to avoid duplicate findings.

Do not report speculative issues as confirmed defects.

If an issue depends on an assumption or external behavior that cannot be verified, exclude it from confirmed findings.

Do not modify source code during the review.

## 10. Downstream AI Implementation Requirements

Reports are intended to be consumed by smaller and lower-cost AI models for subsequent verification and code fixes.

Therefore:

- Each finding must be understandable independently.
- Include exact source file paths and line references.
- Describe the problematic logic, not just the symptom.
- Provide a concrete failure scenario.
- Specify the expected logic change.
- Avoid requiring the downstream model to repeat the entire review.
- Do not prescribe unnecessary architectural changes.
- Preserve existing implementation patterns unless they are the root cause.

The downstream model should be able to read one finding, inspect its local code context, understand the defect, and implement the targeted fix.

## 11. Final Validation

Before completing the review:

- Verify report filename and location.
- Verify all findings against the current source.
- Verify line numbers and file paths.
- Remove duplicate and unverified findings.
- Ensure every finding has a concrete failure scenario.
- Ensure every finding contains an actionable Fix instruction.
- Enforce all output limits.
- Ensure the report follows the existing Markdown convention.
- Ensure no source code has been modified.

## 12. Final Execution Rules

- Only create or update reports inside `docs/report/`.
- Do not modify source code.
- Do not generate additional documentation unless explicitly requested.
- Do not output lengthy review results in the conversation.
- After saving the report, return only the report path and a concise finding count.
- If no issues are found, explicitly report that no actionable findings were identified.

**Core Principle: Identify exactly what is wrong, where it is wrong, when it fails, and what must change to fix it. Keep findings minimal, precise, evidence-based, and actionable for a smaller AI implementation model.**

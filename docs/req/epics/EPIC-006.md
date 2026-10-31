---
id: EPIC-006
title: Verified math extraction: LaTeX, source regions, independent verification, solve gate, measured accuracy
source: [RAW-00064]
created: 2026-10-29 16:06
updated: 2026-10-31 08:37
---
## Original (verbatim, never edit)
> **[RAW-00064]** 2026-10-29 16:06
> <pasted_content id="7c68">
> Act as a senior AI data engineer specializing in mathematical exam processing. Enhance the existing exam-learning-harness input pipeline without changing the current exam-solving engine or over-engineering the architecture.
>
> Requirements:
>
> 1. Preserve the original PDF as the source of truth; never rely on extracted JSON alone.
> 2. Extract text, mathematical formulas, tables, and diagrams accurately. Represent formulas in LaTeX and preserve original images with page and region references.
> 3. Validate extracted content against the original PDF, especially mathematical symbols, signs, exponents, fractions, radicals, answer choices, geometric labels, and diagram relationships.
> 4. Use OCR, mathematical recognition, and vision models as appropriate. Apply independent verification to detect extraction errors.
> 5. Never silently guess missing or ambiguous content. Flag uncertain questions for reprocessing or human review.
> 6. Define a structured JSON schema with source traceability and explicit verification status.
> 7. Allow the solving engine to process only questions that meet the configured verification requirements.
> 8. Build representative test cases and measure exact question-level extraction accuracy, including formulas and diagrams.
>
> Prioritize mathematical fidelity, traceability, reliability, and minimal changes to the existing architecture. Do not claim 99.999% accuracy without statistically meaningful validation.
> </pasted_content id="7c68">

## Goal
Extraction fidelity for math exams that can be shown, not claimed: LaTeX, region traceability, independent verification, a gate before solving, and a measured accuracy. Builds on EPIC-005 (REQ-0019 images, REQ-0021 refine); the solving engine is unchanged.

## Decomposition
<!-- One line per child: "- REQ-0012" (auto-added) or "- [ ] TBD: <coarse item not yet specified>". TBD lines are tracked until converted into REQs. -->
- REQ-0022
- REQ-0023
- REQ-0024
- REQ-0025
- REQ-0026
- REQ-0039
- REQ-0040

## Notes

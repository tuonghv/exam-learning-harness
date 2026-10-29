---
name: coding
description: Apply clean, maintainable, reusable and testable software engineering practices during implementation.
---

# Coding

Before creating code:
- search for existing implementation and similar patterns
- reuse before duplicating
- keep functions focused
- keep interfaces explicit
- avoid speculative abstractions
- avoid unnecessary dependencies
- preserve compatibility where practical

Review after implementation:
- diff scope
- duplication
- error handling
- resource cleanup
- logging/observability
- configuration and defaults
- testability

Follow the `python` skill, then run
`python3 -I -m unittest discover -s tests/unit`.

- Match a doc section by heading regex (`^## X`), never a substring: prose naming it passes (TASK-124).

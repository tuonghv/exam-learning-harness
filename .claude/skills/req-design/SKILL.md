---
name: req-design
description: Design one requirement at a time without blowing the context window. Use when a REQ enters DESIGN, when a design is getting too large, or when resuming a design after compaction.
---

# req-design: one REQ, written to disk as you go

Tool: `python3 .claude/req/req.py` (below: `req`).
Rule: **the design lives in the REQ file, not in the conversation.** Compaction may happen any
moment; whatever is not saved in `docs/req/` is lost.

## Start
```
req focus REQ-0012 --next "design: data model"
req status REQ-0012 DESIGN          # refuses if open questions remain -> ask the user first
req show REQ-0012 --section Requirement,Acceptance,Open questions
```
Read only this REQ (and its EPIC Goal if needed). Do not read other REQs, INDEX.md, or the whole codebase.

## Explore cheaply
Code exploration eats context fast. Follow skill `token-efficiency`: targeted `grep`/`sed -n` on the
files the reference names, and read `docs/guide/toolkit-reference.md` sections, not whole scripts.

## Write in small checkpoints
Fill `## Design` in this order, **saving the file after each item** and updating the next step:
1. Approach (3-6 lines) and what is explicitly out of scope
2. Components / files touched
3. Interfaces / data changes
4. Test plan mapped to acceptance: `AC1 -> test_x`, `AC2 -> test_y`
5. Risks / decisions (`D1: chose X over Y because ...`)

After each: `req focus --next "design: <next item>"`.
In this repo the design doc is the workflow's `docs/design/phase-<N>-<slug>.md` (skill `design`),
which owns sections, reuse and `## Plan modes`. Write it there; `## Design` in the REQ holds only a
3-line summary + that path. Link tasks: `req task REQ-0012 TASK-049`.

## Too big? Split, don't push through
Signs: more than ~1 screen of design, > ~6 acceptance items, several independent components,
or you have used a large share of the context already. Then:
- keep this REQ to the first coherent slice,
- move the rest into new REQs (`req new --title ... --epic <same epic>`) or `- [ ] TBD:` lines in the EPIC,
- log it: `req log REQ-0012 "split: rest moved to REQ-0019, REQ-0020"`.

Design reveals a gap in the requirement? Add an acceptance item or an open question (ask the user)
- never keep the knowledge only in chat.

## Finish
```
req status REQ-0012 IMPLEMENTING    # refuses if Design is empty
req focus --next "implement: <first concrete step>"
```
Good moment for a manual `/compact` (clean boundary; the SessionStart hook reloads the REQ state).

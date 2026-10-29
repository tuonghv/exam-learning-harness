## Sizing lessons (observed)

- 2026-09-29 TASK-064: a coder brief with six hook items plus a new test suite ran into the 60-turn
  cap with no handoff and skipped its halfway checkpoint; the soft `Turns:` is not self-enforced.
  Keep a brief to ≤ 3 design items in one file, put a new test suite in its own brief, and set
  `Expect:` so STALL fires before the cap (≈ 1 min per 5 turns: roles ran 5-7 turns a minute). When a role hits the cap, resume it
  with "stop coding, save the handoff in ≤ 6 turns, reply PARTIAL" before re-briefing the rest.

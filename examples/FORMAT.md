# Example format (standard input / expected output)

Learned from `examples/english/input-001.md` + `expected-001.md` (RAW-00005). One example = two
Markdown files with the same number: `input-NNN.md` (what the solver sees) and `expected-NNN.md`
(the key). Lines written as `Key: value` are read by the checker; keep them on one line.

## Where files go

| Set | Input | Expected (key) |
|---|---|---|
| Few-shot (may be shown to the solver) | `examples/<subject>/input-NNN.md` | `examples/<subject>/expected-NNN.md` |
| Evaluation (never shown with its key) | `evals/inputs/<subject>/input-NNN.md` | `evals/keys/<subject>/expected-NNN.md` |

`<subject>` = `math`, `physics`, `english`, `literature`. A question used in one set is never
reused, reworded, in the other.

## Input: `input-NNN.md`

```markdown
# Exam Input

Subject: English                     # Mathematics | Physics | English | Literature
Level: Grade 12
Exam type: High School Graduation    # or: University Entrance (<profile name>)
Task: Multiple Choice                # Multiple Choice | Short Answer | Sentence Ordering | Reading Comprehension | Essay
Mode: Solve                          # Solve | Grade | Teach
Skill: Grammar - first conditional   # topic tag, free text
Language: vi                         # language of the explanation: vi | en

## Instructions

Choose the best answer and explain why.

## Passage                           # only when the task has a text (reading, literature)

...

## Question 1

If I ______ enough time tomorrow, I will help you prepare for the examination.

A. have
B. had
C. will have
D. would have

## Learner answer                    # only with Mode: Grade

...

## Rubric                            # only with Mode: Grade, when the exam supplies one
```

Rules: self-contained (everything needed is in the file), original text, no answer, no hint
of the key. Multiple choice always has exactly four options A-D.

## Expected output: `expected-NNN.md`

One block per question, in this order:

```markdown
# Expected Output

## Question 1

Final answer: A
Correct answer: A. have

### Solution

1. Identify the structure: "tomorrow" + "will help" -> first conditional.
2. First conditional: If + present simple, will + base verb.
3. The if-clause needs the present simple: "have".

### Explanation

- A. have: present simple in the if-clause - correct.
- B. had: past simple belongs to the second conditional (unreal present) - wrong.
- C. will have: "will" is not used in this if-clause - wrong.
- D. would have: third-conditional / unreal form - wrong.

### Verification

- Check: substitute A -> "If I have enough time tomorrow, I will help you..." - grammatical. Pass
- Check: each distractor breaks the conditional pattern. Pass
- Final answer: A
- Status: Verified

### Grading

- 1 point: option A. 0 points: any other option.
```

### Required in every expected file

| Item | Rule |
|---|---|
| `Final answer:` | one line per question; the option letter, the value with unit, the order (`c-a-d-b-e`) or `Open (rubric)` |
| `### Solution` | numbered steps a learner can follow |
| `### Explanation` | why the answer is right; for multiple choice one line per wrong option |
| `### Verification` | at least one `- Check:` line that confirms the answer a different way, then `- Final answer:` (same as above) and `- Status: Verified` |
| `### Grading` | how points are given (1 line for objective items, a table for open answers) |

## Per-subject additions

**Mathematics** - `### Solution` states the domain/conditions first. A `Check:` substitutes the
answer back or recomputes it another way. Exact values (`x = 1/3`, `2*sqrt(3)`); state when there
is no solution or infinitely many. Edge cases: domain restriction, extraneous root, parameter
boundary.

**Physics** - `### Solution` starts with `Given:` (SI units) and `Find:`, then the law used.
`Final answer:` carries a unit (`2.5 m/s^2`) and the rounding used. `Check:` lines: unit analysis,
order of magnitude, a limiting case. Edge cases: sign/direction, zero or limiting value, unit
conversion.

**English** - grammar/vocabulary: name the rule or collocation. Reading: a `Check:` quotes the
line of the passage that proves the answer. Sentence ordering: `Final answer: c-a-d-b-e`, and the
Explanation names the link words or pronouns that force each step.

**Literature** - `Final answer: Open (rubric)`. Add before `### Grading`:

```markdown
### Accepted interpretations

1. <reading 1> - evidence: "<exact quote from the Passage>"
2. <reading 2> - evidence: "<exact quote from the Passage>"
Any other reading is accepted only if it is supported by quoted evidence from the passage.

### Model answer outline

1. Opening ... 2. Body ... 3. Closing ...
```

and a rubric table in `### Grading` (Content, Evidence, Structure, Language; points per band,
total stated). Quotes must appear word for word in the input passage.

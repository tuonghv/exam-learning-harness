# Exam report: English

- Exam: English, Grade 12, High School Graduation, task Sentence Ordering, mode Solve
- Run: claude-p (sonnet), 2 call(s), cost $0.0328
- Totals: PASS 0, FAIL 1, UNCERTAIN 0, unresolved 1
- Points: 1 / 1

## Question 1

- Answer: b-d-a-e-c
- Verdict: **FAIL**
- Reason: check_failed: quote
- Evidence: key match
- Score: 1 / 1 (official_key)

| Check | Result | Independent | Detail |
| --- | --- | --- | --- |
| format | pass | no | ordering uses each given letter once |
| quote | fail | no | verbatim in passage/question: b: Last year, Linh decided to become a primary school teacher. |
| quote | fail | no | verbatim in passage/question: d: She had always loved children, so the choice seemed easy at first. |
| quote | fail | no | verbatim in passage/question: a: However, she soon realised that the job required far more patience than she h |
| quote | fail | no | verbatim in passage/question: e: Because of this, she began to attend extra training courses on classroom mana |
| quote | fail | no | verbatim in passage/question: c: Now, after finishing the courses, she says it is the most rewarding decision |
| key_match | pass | yes | matches the key |

### QA findings

- deterministic / quote: verbatim in passage/question: b: Last year, Linh decided to become a primary school teacher.
- deterministic / quote: verbatim in passage/question: d: She had always loved children, so the choice seemed easy at first.
- deterministic / quote: verbatim in passage/question: a: However, she soon realised that the job required far more patience than she h
- deterministic / quote: verbatim in passage/question: e: Because of this, she began to attend extra training courses on classroom mana
- deterministic / quote: verbatim in passage/question: c: Now, after finishing the courses, she says it is the most rewarding decision

### Explanation

The paragraph follows a chronological order: decision (b), reason (d), problem (a), action (e), result (c). 'However' in a needs the earlier idea that the choice seemed easy, so a cannot come before d. 'Because of this' in e needs a problem before it, so e must follow a. 'the courses' in c refers back to the courses in e, so c must be last. Placing a before b or d would leave 'she' and 'the job' without a clear referent.

### Solution

1. b opens the story: it introduces Linh and her decision (Last year, Linh decided...).
2. d follows b: it gives her reason for the choice (She had always loved children, so the choice seemed easy at first).
3. a follows d: 'However' contrasts with 'seemed easy at first' and shows the problem (the job needed more patience).
4. e follows a: 'Because of this' refers to the lack of patience and gives her response (extra training courses).
5. c closes the story: 'Now, after finishing the courses' is the result and present outcome.

### Uncertainty

low: Discourse markers (However, Because of this, Now, the courses) fix the order uniquely.

# TASK-104 evidence

Verifier: VERDICT PASS (AC1-AC3); bad_letter rule matches src/exam_engine/pipeline/explain.py:77-99.
- fast suite: `python3 -I tools/run_tests.py --fast` 1946 tests, KNOWN 4 NEW 0 (work/TASK-104/evidence/t104-fast.txt)
- real dhqg-main: KEYISSUE 65 bad_letter I;RESULT 64 checks 0 failed ok
- real dhqg-t81: KEYISSUE 65 bad_letter I;RESULT 64 checks 0 failed ok
- real dgnl2025: RESULT 58 checks 0 failed ok
- real dgnl2026: RESULT 58 checks 0 failed ok
- bites: test_104_bad_key_letter_is_key_issue_not_fail fails on the c77e611 checker (work/TASK-104/evidence/t104-bites-old.txt)

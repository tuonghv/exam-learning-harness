# Extraction accuracy (exact match)

gold: /home/tuonghv/Documents/git/online-system/exam-learning-harness/evals/extract/gold/synthetic-001.json  extracted: /home/tuonghv/Documents/git/online-system/exam-learning-harness/tests/unit/fixtures/extract_eval/perfect.json
n=20 matched=20 missing=none extra=none

## Metrics

| Metric | k/n | rate | Wilson 95% |
|---|---|---|---|
| overall | 20/20 | 100.0% | 83.9%-100.0% |
| text | 20/20 | 100.0% | 83.9%-100.0% |
| formula | 20/20 | 100.0% | 83.9%-100.0% |
| options | 20/20 | 100.0% | 83.9%-100.0% |
| figures | 20/20 | 100.0% | 83.9%-100.0% |
| formula (applicable only) | 10/10 | 100.0% | 72.2%-100.0% |
| figures (applicable only) | 4/4 | 100.0% | 51.0%-100.0% |
| verified precision | 20/20 | 100.0% | 83.9%-100.0% |
| needs_review | 0/20 | 0.0% | 0.0%-16.1% |

Lines:

- overall 20/20 = 100.0% (Wilson 95% 83.9%-100.0%)
- text 20/20 = 100.0% (Wilson 95% 83.9%-100.0%)
- formula 20/20 = 100.0% (Wilson 95% 83.9%-100.0%)
- options 20/20 = 100.0% (Wilson 95% 83.9%-100.0%)
- figures 20/20 = 100.0% (Wilson 95% 83.9%-100.0%)
- formula (applicable only) 10/10 = 100.0% (Wilson 95% 72.2%-100.0%)
- figures (applicable only) 4/4 = 100.0% (Wilson 95% 51.0%-100.0%)
- verified precision 20/20 = 100.0% (Wilson 95% 83.9%-100.0%)
- needs_review 0/20 = 0.0% (Wilson 95% 0.0%-16.1%)

## Claims

99.999% is NOT claimed: needs >= 299572 error-free questions (n=20); 95% lower bound 83.89%.

| target | n needed (error-free, 95%) |
|---|---|
| 99% | 299 |
| 99.9% | 2995 |
| 99.999% | 299572 |

## Wrong questions

none

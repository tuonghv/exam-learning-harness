# Extraction accuracy (exact match)

gold: /home/tuonghv/Documents/git/online-system/exam-learning-harness/evals/extract/gold/synthetic-001.json  extracted: /home/tuonghv/Documents/git/online-system/exam-learning-harness/tests/unit/fixtures/extract_eval/corrupted.json
n=20 matched=19 missing=['15'] extra=['99']

## Metrics

| Metric | k/n | rate | Wilson 95% |
|---|---|---|---|
| overall | 14/20 | 70.0% | 48.1%-85.5% |
| text | 18/20 | 90.0% | 69.9%-97.2% |
| formula | 17/20 | 85.0% | 64.0%-94.8% |
| options | 18/20 | 90.0% | 69.9%-97.2% |
| figures | 18/20 | 90.0% | 69.9%-97.2% |
| formula (applicable only) | 7/10 | 70.0% | 39.7%-89.2% |
| figures (applicable only) | 2/4 | 50.0% | 15.0%-85.0% |
| verified precision | 14/19 | 73.7% | 51.2%-88.2% |
| needs_review | 0/20 | 0.0% | 0.0%-16.1% |

Lines:

- overall 14/20 = 70.0% (Wilson 95% 48.1%-85.5%)
- text 18/20 = 90.0% (Wilson 95% 69.9%-97.2%)
- formula 17/20 = 85.0% (Wilson 95% 64.0%-94.8%)
- options 18/20 = 90.0% (Wilson 95% 69.9%-97.2%)
- figures 18/20 = 90.0% (Wilson 95% 69.9%-97.2%)
- formula (applicable only) 7/10 = 70.0% (Wilson 95% 39.7%-89.2%)
- figures (applicable only) 2/4 = 50.0% (Wilson 95% 15.0%-85.0%)
- verified precision 14/19 = 73.7% (Wilson 95% 51.2%-88.2%)
- needs_review 0/20 = 0.0% (Wilson 95% 0.0%-16.1%)

## Claims

99.999% is NOT claimed: needs >= 299572 error-free questions (n=20); 95% lower bound 48.10%.

| target | n needed (error-free, 95%) |
|---|---|
| 99% | 299 |
| 99.9% | 2995 |
| 99.999% | 299572 |

## Wrong questions

- Q3 [verified]: formula
- Q5 [verified]: formula
- Q7 [verified]: text
- Q9 [verified]: options
- Q12 [verified]: figures
- Q15 [missing]: text, formula, options, figures

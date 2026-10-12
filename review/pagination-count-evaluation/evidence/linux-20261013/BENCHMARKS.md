# Query-shape measurements, 13 October 2026

One synthetic project: 1,000 work items; 4 KiB in each HTML, JSON, stripped and binary description representation. Every item has a label, assignee and module. Two warmups and ten randomized trials per variant/case. Median [IQR] in milliseconds; SQL/model/allocation/plan probes are separate from timings.

| Surface / case | Baseline | Stage A only | Submitted automatic B | Revised opt-in B | SQL baseline / revised | Issue models baseline / revised |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| public/default-first | 231.2 [7.3] | 56.9 [3.4] | 59.1 [3.9] | 58.9 [2.2] | 9 / 9 | 1020 / 20 |
| public/sequence-control | 232.4 [13.7] | 58.8 [3.5] | 57.6 [3.3] | 57.8 [7.3] | 9 / 9 | 1020 / 20 |
| public/default-middle | 229.9 [8.8] | 57.4 [2.0] | 58.9 [2.8] | 56.4 [4.1] | 9 / 9 | 1020 / 20 |
| public/default-last | 229.4 [6.5] | 59.7 [3.3] | 57.5 [1.9] | 56.9 [3.4] | 9 / 9 | 1020 / 20 |
| public/default-beyond | 217.2 [12.8] | 42.4 [1.9] | 41.0 [1.6] | 42.7 [3.0] | 7 / 7 | 1000 / 0 |
| public/default-large | 278.6 [29.5] | 101.5 [2.4] | 103.3 [2.3] | 102.8 [5.6] | 9 / 9 | 1100 / 100 |
| app/default-first | 245.2 [2.1] | 58.9 [1.6] | 54.9 [4.6] | 55.6 [2.8] | 7 / 7 | 1020 / 0 |
| app/sequence-control | 240.1 [7.6] | 57.9 [2.5] | 52.0 [2.0] | 54.7 [1.6] | 7 / 7 | 1020 / 0 |
| app/default-middle | 244.8 [6.2] | 59.9 [5.1] | 59.4 [10.9] | 55.6 [6.3] | 7 / 7 | 1020 / 0 |
| app/default-last | 247.5 [7.9] | 59.6 [1.2] | 56.9 [6.1] | 55.8 [3.2] | 7 / 7 | 1020 / 0 |
| app/default-beyond | 237.3 [9.4] | 52.9 [3.0] | 54.2 [3.1] | 53.0 [1.8] | 7 / 7 | 1000 / 0 |
| app/default-large | 262.1 [3.5] | 78.7 [6.4] | 60.3 [5.9] | 61.4 [5.3] | 7 / 7 | 1100 / 0 |
| app/priority-large | 264.6 [9.4] | 83.6 [4.8] | 65.1 [4.2] | 62.5 [3.3] | 7 / 7 | 1100 / 0 |
| app/filtered-related | 68.5 [4.0] | 47.6 [2.2] | 43.4 [2.7] | 49.5 [5.5] | 7 / 7 | 120 / 0 |

Default order means no order_by parameter. The matrix uses page size 20 at zero-based page indices 0, 25, 49 and 50; page size 100 at index 3; a sequence_id first-page control; app priority order at size 100; and app priority/label/assignee filters at page index 2. The filtered case matches 100 rows. Exact ordered identities, counts, cursor flags and full cross-variant response hashes passed.

The public priority case was excluded after the initial harness incorrectly assumed a tie-breaker: that endpoint orders by priority alone. The app priority case has a created_at tie-breaker and remains in the matrix. A second harness attempt assumed high-before-low app priority, but the existing paginator receives -priority_order and returns low-before-high; the expectation now preserves that behavior. Both failing harnesses/logs/XML are preserved in the archive. This is a benchmark expectation correction, not an application change.

Most improvement is from Stage A. Stage B avoids raw-page model construction for the opted-in app projection without removing a SQL statement. Close timing differences and outliers are observations, not statistical significance or universal superiority. These APIClient timings include response parsing and assertions, not TCP. Full raw trials, parameterized SQL without parameter values, and actual count/projection plans are in the archive.

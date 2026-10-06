# Local pagination measurements

20 randomized trials per variant after two warmups; APIClient request handling plus JSON parsing, DEBUG=False. SQL and allocation probes are separate. No TCP or production performance claim.

| Rows | Body bytes per representation | Surface | Median ms: baseline / count-only / combined | IQR ms: baseline / count-only / combined | Models constructed: baseline / count-only / combined | SQL statements |
| ---: | ---: | --- | ---: | ---: | ---: | ---: |
| 100 | 0 | public | 45.4 / 42.4 / 44.3 | 5.9 / 5.4 / 4.0 | 120 / 20 / 20 | 9 |
| 100 | 0 | app | 37.3 / 33.9 / 34.7 | 3.8 / 5.8 / 4.3 | 120 / 20 / 0 | 7 |
| 100 | 4096 | public | 70.3 / 51.2 / 48.9 | 10.2 / 3.5 / 3.6 | 120 / 20 / 20 | 9 |
| 100 | 4096 | app | 61.4 / 40.7 / 37.1 | 5.1 / 5.5 / 3.5 | 120 / 20 / 0 | 7 |
| 1000 | 0 | public | 76.6 / 46.6 / 45.7 | 6.8 / 4.1 / 3.0 | 1020 / 20 / 20 | 9 |
| 1000 | 0 | app | 72.0 / 42.8 / 42.0 | 4.1 / 5.1 / 3.2 | 1020 / 20 / 0 | 7 |
| 1000 | 4096 | public | 242.1 / 52.7 / 53.2 | 8.2 / 4.2 / 5.6 | 1020 / 20 / 20 | 9 |
| 1000 | 4096 | app | 243.5 / 48.4 / 43.9 | 5.7 / 4.0 / 2.6 | 1020 / 20 / 0 | 7 |
| 10000 | 0 | public | 478.7 / 100.3 / 101.3 | 12.2 / 6.8 / 7.5 | 10020 / 20 / 20 | 9 |
| 10000 | 0 | app | 534.4 / 151.1 / 150.6 | 30.3 / 12.8 / 12.2 | 10020 / 20 / 0 | 7 |
| 10000 | 4096 | public | 2380.5 / 113.3 / 110.6 | 100.7 / 12.8 / 5.2 | 10020 / 20 / 20 | 9 |
| 10000 | 4096 | app | 2345.9 / 830.5 / 825.1 | 201.9 / 68.7 / 35.2 | 10020 / 20 / 0 | 7 |

All measured response hashes agree across the three variants. The SQL statement count is unchanged. Read VALIDATION.md for the semantic boundaries, methodology limits, and interpretation of small timing differences.

# Corrected-packet integration verification

Verified 6 October 2026 against the corrected public checkout `a0ecbd6a15f5348061d5e46f58589b65cd014158`. Fork PR #1 was merged into the review branch as `ac453a0783f0774b196d44d665afafb2b5fcbc39`.

## Application identity

The submitted upstream commit in [Plane PR #9952](https://github.com/makeplane/plane/pull/9952) is `a96adb7fb4d408e9bd1651289631bd8b5fcd1461`, based directly on upstream `7466675e471efe1c96b122615f7a0d30c9b2eb05`. Its only changed files are the project-list handler and expansion regression file. Their Git blobs are respectively `ef2f157f4e6ad6cfb75716717a7e7c61985048ff` and `bc93068624ae46fe7e6c58bc7db65739fbf03c45`, identical to the previously validated local `c70e805` snapshot and corrected review checkout. The review packet is excluded from the upstream branch.

## Fresh execution results

| Check | Result | Log |
| --- | --- | --- |
| Dependency-free packet checks | 5 passed | `checks/test_packet.py` |
| Application expansion regressions | 32 passed | [log](../logs/integration/application-regressions.log) |
| Corrected refined harness | 4 passed | [log](../logs/integration/refined-benchmark.log) |
| Corrected exploratory harness | 5 passed | [log](../logs/integration/exploratory-benchmark.log) |
| Corrected final endpoint harness | 4 passed, including TCP identity check | [log](../logs/integration/final-endpoint.log) |
| Changed-file Ruff lint and format | Passed | Two application files |

These are separate checks, not additions to the 732-test backend count. Both corrected sibling-import entry points executed their complete database-backed fixture sets. The final endpoint harness asserted identical responses and the 408-to-10 populated-audit-user statement counts, with 8-to-8 for null audit users.

Runs used the configured Windows Python 3.12.6 / Django 5.2.17 environment and dedicated local PostgreSQL/Redis test services. Commands were run serially from `apps/api` with `DJANGO_SETTINGS_MODULE=plane.settings.test` and `PYTHONPATH` pointing to that directory. See the [reproduction guide](../benchmarks/README.md); the optional exploratory command was also executed in full. The 32-case run emitted seven missing-static-directory warnings in the fresh checkout. The generated `plane/static-assets/collected-static` directory was created before subsequent harness runs; no application change was needed.

The earlier full Linux Docker and Windows suites each passed all 732 tests. They were not rerun for these packet-only corrections: the submitted commit and local `c70e805` have the same complete Git tree, `52c384b0d106559f632c1f5644aa4833cc661ac5`. Local validation does not establish hosted GitHub CI or maintainer approval.

## Evidence preservation

The historical benchmark table and ZIP remain unchanged. The ZIP SHA256 was recomputed and still equals `553d5caf5624f4dbc6f179c92ff8c18fa2d7a21dae3da4dbe7ddef4a3d144e19`. This replay verifies the corrected workflow; it does not replace the historical timing samples with newer values. The supplied new logs omit local checkout/environment paths and contain synthetic-workload summaries. Corrected throttle-history terminology applies to new outputs; the [accounting report](QUERY_ACCOUNTING.md) explains the old archive label.

The upstream PR description uses the newer replay measurements, with raw trials provided separately: [distinct](../raw/integration/final-http-uninstrumented-distinct.json), [shared](../raw/integration/final-http-uninstrumented-shared.json), and [null](../raw/integration/final-http-uninstrumented-null.json). The older archive and reports retain their original results. Timing varied between runs, so the preserved query-count and response-equality invariants are stronger evidence than a universal latency claim.

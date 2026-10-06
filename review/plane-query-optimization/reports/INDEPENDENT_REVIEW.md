# Independent architecture and publication review

Reviewed snapshot: `48166c4ef6bee3babe56b3ca92d919adb503ec6e` on
`GODOSTROYER/plane:plane-query-review-20261006`, 6 October 2026.

## Verdict and boundary

No blocking production-loader defect was identified by source review. Retain the
conditional batched-prefetch design. The corrective PR concerns the published
review tools and documentation only; it does not modify `apps/`, the application
patch, the copied regression file, or the evidence archive.

This reviewer read the pinned application change, regression source, benchmark
scripts, decision, final review, critique, SQL accounting, PR draft and publication
audit through GitHub. Reconstructed working copies used for local checks were
verified against their Git blob IDs. The source-path and packet-copy regression
files both have blob ID `bc93068624ae46fe7e6c58bc7db65739fbf03c45`.

Five dependency-free packet checks reproduce **four failures and one pass** on
the published snapshot and **five passes** after correction. These checks cover
file-path resolution, benchmark module import without running workloads, metadata,
Markdown table structure and compilation. They do not reproduce the reported
732 backend passes, query counts, or timings. Django, PostgreSQL and Docker were
not available in this review environment. The ZIP could not be independently
retrieved/decoded here, so its claimed SHA256, CRC, member count and privacy scan
remain publisher-reported, not independently verified by this reviewer.

## Findings and corrections

### P2: both comparison harnesses point to a nonexistent file

`test_benchmark_local.py` and `test_refined_benchmark.py` construct their import
path as `EVIDENCE / "tools/benchmark_project_expansion.py"`. In this public layout,
`EVIDENCE` is the packet directory and the executable is in `benchmarks/`, not
`tools/`. A checkout therefore fails when the dynamic loader executes, after
fixture setup. Resolve the sibling with
`Path(__file__).resolve().with_name("benchmark_project_expansion.py")`.
The two dedicated packet tests reproduce this defect without starting services.

### P2: cold authentication-cache metadata is inaccurate

The final endpoint harness labels the eviction
`cold_api_token_cache_per_request`. The actual key comes from
`ApiKeyRateThrottle.get_cache_key()` in `apps/api/plane/api/rate_limit.py`.
It is a throttle-history reset. `APIKeyAuthentication` performs the database token
lookup, last-used write and user resolution on each request; this is not a cache
hit/miss experiment for authentication or the database.

Correct the key and clock description for future output, and annotate the older
label in QUERY_ACCOUNTING. Preserve archived bytes and measurements. No timing
loop, cache behavior, fixture size or application logic changes in this correction.

### P3: PR draft table has incompatible column counts

The header/body have four cells; the delimiter has three. Add its fourth cell so
the measurement table is valid GitHub-flavored Markdown. No numerical values change.

### P3: an upstream PR is not a universal prerequisite for hosted CI

The previous review/critique wording conflates upstream review with availability
of GitHub Actions. A fork may run workflows when configured and permitted. State
only that the packet establishes no hosted result and that upstream checks and
approval remain separate. Do not claim this corrective PR automatically executes
the backend suite; workflow triggers and target-branch filters still apply.

## Architectural assessment

The production handler intersects `expand` with `fields`, allowlists four user
relations, retains the original authorization query and pagination boundary, and
loads users with their avatar assets. That explicit dependency graph is preferable
to speculative automatic relation traversal. Keeping the existing `project_lead`
join and prefetching only its avatar avoids refetching an already-loaded parent.

The base-manager selection preserves forward foreign-key lookup semantics. It is
not a new authorization filter and should not be replaced by an active-user filter.
Leaving the queryset's database alias unspecified also avoids hardcoding primary
reads. Actual router/replica behavior remains an untested topology, however.

The strategy reduces round trips per included relationship, not total computational
complexity. It still materializes and serializes O(page size) data, and its IN-list
and allocation costs depend on page size. It deduplicates users within a relation
batch, not globally across all four roles. Neither issue justifies a custom identity
map or caching layer without further evidence.

## Test assessment

The strengthened file checks exact user/avatar identity, shared users including
one user filling all roles, inactive historical users, null relations, soft-deleted
avatars, sparse fields, visibility and cursor behavior. HTTP growth checks cover
both audit-only and all-four expansions. This is a strong bounded-scope suite.

Some tests intentionally inspect private queryset structures and require exactly
one added fetch per populated expansion. Such assertions document this plan; they
are not immutable API contracts. A future better plan may legitimately require
updating them. The zero-SQL serialization and response/visibility assertions are
the longer-lived invariants. No rewrite is needed for this submission.

## Interpretation of reported performance

The current report's distinct-user result is 408 to 10 statements and 954.3 to
269.5 ms median on a synthetic 100-project audit-only request. This is roughly
97.55% fewer statements and 71.76% less median time, not a production guarantee.
The optimized IQR is 164.3 ms; tail behavior is not established by the median.
Null-user medians move from 60.8 to 66.7 ms with eight statements in both variants;
retain the possible overhead signal rather than declaring it harmless noise.

The headline baseline is reconstructed by removing the added prefetches at the
pagination boundary, whereas the reported regression fail-before run uses pristine
upstream. These are complementary, different experiments. Historical join-versus-
prefetch trials capture SQL during timing; the newer headline A/B loop does not.
Do not combine them or claim a fresh uninstrumented join comparison was performed.

## Nonblocking follow-ups, outside this PR

1. Verify routing on an actual primary/replica topology, including intended database
   hints and response behavior under replica lag. Do not add `.using("default")`.
2. Measure a fixed page inside a much larger workspace with realistic membership
   density. Existing synthetic fixtures do not establish that scaling behavior.
3. Investigate sparse-response membership prefetch cost and project cover-image
   loading separately. Retain all permission predicates and annotations.
4. If revisiting strategy selection, repeat joins and prefetch uninstrumented on
   the same current build, preserving raw order, IQR and tail observations.

## Publication and next action

The ZIP audit is a scoped risk-reduction report, not proof that an upload approval
establishes correctness or absence of every possible secret. It covers that archive,
not every commit or branch file. No credential finding was identified in the text
review; no archive replacement or history rewrite is proposed.

Use the [checkout reproduction guide](../benchmarks/README.md), run the focused
backend/benchmark commands in the configured environment, and review the corrected
packet. When preparing an eventual upstream PR, use the isolated application patch
or a clean application-only branch: do not submit the entire review packet and ZIP
to upstream. No upstream PR or change is authorized by this corrective work.

## Primary reference points

- Django 5.2 QuerySet documentation: https://docs.djangoproject.com/en/5.2/ref/models/querysets/
- Django 5.2 related-object managers: https://docs.djangoproject.com/en/5.2/topics/db/managers/
- GitHub workflow dispatch: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-running-a-workflow
- In-repository evidence: DECISION.md, QUERY_ACCOUNTING.md, FINAL_REVIEW.md and the pinned benchmark source.

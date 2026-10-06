> Historical research document from October 5, 2026. Its join-first recommendation and statement that Plane tests and benchmarks had not been run describe the initial investigation only. The final implementation uses batched prefetching, selected after comparative measurements; the final tests and evidence are documented in FINAL_REVIEW.md and DECISION.md.
# Plane project-list API: expansion-aware query optimization

**Research date:** October 5, 2026  
**Inspected upstream branch:** `preview`  
**Pinned revision:** `7466675e471efe1c96b122615f7a0d30c9b2eb05`  
**Status:** Source-verified design and draft implementation; not a database-benchmarked or integration-tested PR.

## Executive decision

Implement **explicit, conditional eager loading of the public project list's included user expansions, including their avatar assets**, in `ProjectListCreateAPIEndpoint.get()` immediately before `self.paginate()`.

The initial loading graph should cover the four project fields already expanded through `UserLiteSerializer`: `created_by`, `updated_by`, `project_lead`, and `default_assignee`. Activate each path only when requested through `expand` and not excluded by `fields`. Use `<field>__avatar_asset`, not only `<field>`.

Keep the existing scoped queryset, permissions, annotations, ordering, pagination and serializers unchanged. Do not add a cache, a package, an index, a migration, arbitrary relation traversal or a repository-wide optimizer for this PR.

This is my recommended first implementation because it removes the identified repeated reads with ordinary Django mechanisms and a small review surface. It is **not a proven universal latency optimum**. Batched prefetching is a genuine contender, particularly for large pages that repeatedly reference a few users. Run the supplied comparison before claiming which wins on representative data.

### Verification boundary

The repository files and dependency graph were read through the connected GitHub tools. Official Django/DRF documentation and analogous open-source implementations were researched. The exact new field-selection block passed 66,564 dependency-free input combinations, and all supplied Python files passed syntax parsing. The patch also applied to a synthetic file containing the exact fetched source context at the inspected line offset.

**Not performed:** importing/running the complete Plane backend, executing its new or existing pytest tests, obtaining PostgreSQL execution plans, measuring request latency or validating hosted CI. Django/DRF are not installed in this environment, and direct network access from its container could not fetch the source/dependencies. The runnable artifacts are drafts that require these real-environment checks.

## 1. What is actually wrong

The earlier merged PR #9717 explicitly deferred the project-list expansion N+1 problem. Its description identifies creator/editor lookups per returned project. Inspection at the pinned revision corroborates this. [S1–S5]

The relevant route is:

```http
GET /api/v1/workspaces/{slug}/projects/?expand=created_by,updated_by
```

The request path is:

1. `BaseAPIView.fields` and `.expand` split comma-separated query parameters, remove empty elements and return a list or `None`.
2. `ProjectListCreateAPIEndpoint.get_queryset()` scopes projects to the workspace and to active project membership or public visibility, adds annotations, joins `project_lead`, orders, and applies `distinct()`.
3. `.get()` adds sort-order context, prefetches project membership rows, and calls the existing paginator.
4. The paginator slices a still-lazy queryset before its `on_results` callback constructs `ProjectSerializer(..., many=True, fields=..., expand=...)`.
5. `BaseSerializer.to_representation()` accesses requested relation objects via `getattr(instance, expand, ...)` and passes them to the expansion serializer.
6. `UserLiteSerializer` includes `avatar_url`. `User.avatar_url` accesses `avatar_asset`; `FileAsset.asset_url` produces a static URL for a correctly typed avatar. [S2–S8]

The project-list queryset does not load the two audit-user relations. That causes separate user reads for populated audit references. Loading only those users does not completely fix the path: an uploaded avatar can trigger another asset read per expanded user.

### Five important findings

**A. The dependency graph has a hidden second level.** The required paths are `created_by__avatar_asset` and `updated_by__avatar_asset`. `avatar_url` looks like a scalar serializer field but calls a property that traverses another relationship. A serializer-field-only optimizer can miss this. [S4–S7]

**B. `fields` takes precedence.** The existing serializer removes excluded top-level fields before expansion. A request for `fields=id,name&expand=created_by` should not make the new code load the creator. Preserve the current parser's behavior; do not silently add whitespace normalization, nested field syntax or validation rules in a performance patch. [S3–S4]

**C. The existing membership prefetch does not solve audit loading.** It prepares `project_projectmember` and its `member`, not `Project.created_by` or `Project.updated_by`. Do not infer that fetching the same underlying user through one path warms every other object's FK cache. Leave that prefetch alone in this PR. [S2]

**D. Project cover images are a separate source of per-row reads.** `ProjectSerializer.cover_image_url` calls `Project.cover_image_url`, which dereferences `cover_image_asset`. Consequently, fixing user expansions does not prove every full project-list response is N+1-free. Use a sparse field set to isolate the user-expansion regression and record the cover-image issue separately. [S5, S9]

**E. A naive fixture can hide the entire problem.** `BaseModel.save()` sets audit fields from the current request user, and leaves `updated_by` null on creation. Explicit constructor arguments are not sufficient to prove those fields remained populated. The supplied test fixture sets persisted audit IDs using `QuerySet.update()` and refetches the project. It also creates real avatar rows rather than mocking avatar properties. [S10]

## 2. Scope of the first PR

### Included

- Public project-list **GET** only.
- Conditional loading for the four existing user expansions.
- Uploaded-avatar loading for those expansions.
- Sparse-field exclusion, null and inactive user behavior, duplicates, empty results, project visibility and cursor-pagination regression coverage.
- Real-query regression checks and reproducible benchmarks.

The same `UserLiteSerializer` and relationship depth apply to all four fields, so extending the fix from two audit users to these four is bounded. If maintainers prefer the narrowest possible change, restrict the allowlist and tests to `created_by` and `updated_by`; the design remains identical.

### Excluded

Do not change the app API, project detail/create/update handlers, unsupported expansion behavior, asset visibility policy, project memberships, annotations/counting, fields returned, cache invalidation, ordering policy, index layout or database routing. Also exclude cover-image optimization, general M2M expansion, serializer CPU caching and a shared optimizer across unrelated endpoints.

In particular, `expand=name` currently has its own undesirable fallback behavior. Do not repair that alongside performance work; doing so would obscure whether response changes come from a fix or a regression. [S1, S4]

## 3. Comparison of approaches

| Approach | Benefits | Costs / failure modes | Decision |
|---|---|---|---|
| Always join users and avatars | Very simple, removes identified lazy lookups | Adds work even when fields are unexpanded or excluded | Reject for this request-sensitive API |
| Conditional `select_related` through avatars | No additional relationship-fetch statements; ordinary Django; small diff; preserves same-query relation snapshot | Repeats related columns/objects across rows; can widen sorting/deduplication work | **Recommended first implementation** |
| Conditional `Prefetch` of each user queryset with its avatar joined | Constant additional statements; can reuse users within each relation; keeps main query narrower | Additional round trips; separate snapshots; cached-parent and manager subtleties | **Benchmark competitor**, not an inferior fallback |
| One union-of-user-IDs request-local loader | Can deduplicate across creator/editor/lead/assignee paths in one user batch | Custom mapping/caching/serializer integration, null/manager/routing obligations | Only with evidence that ordinary prefetching is insufficient |
| Global automatic-prefetch package | Broader automated detection | New dependency, shared model/view behavior changes, custom-property and dynamic-expansion limitations | Not justified for this PR |
| Redis or process-global response/user cache | Can hide repeated DB reads on warm paths | Cold misses remain; invalidation, tenant/user scope and stale-profile risks | Do not introduce for an ORM loading defect |
| Raw SQL or JSON aggregation | Greater control and potentially fewer Python objects | Reimplements serializer contract, increases coupling and review burden | Defer unless profiling establishes a need |
| Index addition | May improve a separately measured plan | Does not eliminate issuing a query for every object; write/storage overhead | No migration without separate plan evidence |

DRF explicitly makes queryset optimization the application's responsibility and recommends `select_related` for single-valued relations. Django explains when joins and prefetches trade speed, memory and query shape. [D1–D3]

The closest directly relevant analogue is `drf-flex-fields`: its example conditionally eager-loads requested expansions, and sparse fields suppress excluded expansions. Borrow that policy; do not replace Plane's serialization system. Its own automatic optimization feature is described as experimental and limited to one nesting level. [A1]

Serializer-inspection approaches such as `django-auto-prefetching` and model-level approaches such as `django-auto-prefetch` solve broader problems with correspondingly wider integration. They reinforce why the explicit graph matters here: the user-avatar access is inside a property, and Plane's expansion selection is implemented dynamically in `to_representation()`. [A2–A3]

## 4. Recommended implementation

Insert the following in `apps/api/plane/api/views/project.py`, inside `ProjectListCreateAPIEndpoint.get()`, after the existing `projects = (...)` construction. Replace only the existing pagination return block as shown. The accompanying `production.patch` does this at the inspected source location.

```python
        fields = self.fields
        expand = self.expand
        expanded_user_fields = set(expand or ()) & {
            "created_by",
            "updated_by",
            "project_lead",
            "default_assignee",
        }
        if fields:
            expanded_user_fields.intersection_update(fields)

        # UserLiteSerializer reads avatar_url, which also dereferences avatar_asset.
        # Keep this opt-in so excluded or unexpanded fields add no new joins.
        if expanded_user_fields:
            projects = projects.select_related(
                *(f"{field}__avatar_asset" for field in sorted(expanded_user_fields))
            )

        return self.paginate(
            request=request,
            queryset=(projects),
            on_results=lambda projects: (
                ProjectSerializer(projects, many=True, fields=fields, expand=expand).data
            ),
        )
```

### Why these details matter

**The allowlist is application-owned.** Never call `select_related(*self.expand)` using client strings. Unknown fields and attempted traversal strings should not become ORM lookups.

**The empty-set guard is essential.** `select_related(*[])` is `select_related()` with no arguments, which means broad automatic relation selection, not “do nothing.” [D2]

**The path includes the user automatically.** Joining `<field>__avatar_asset` also joins `<field>`; a separate duplicate user path is unnecessary.

**Nothing evaluates the queryset early.** Do not add `list(projects)` before pagination. Selection remains bounded by the existing page slicing. [S8]

**Existing joins are preserved.** Chaining named `select_related` calls adds paths. The old `project_lead` join remains, even when unexpanded; this patch makes no claim of removing existing overfetch. [D2, S2]

**The change is read-local.** `get_queryset()` is reused by project creation in this class. Placing this in `.get()` avoids changing how the write path retrieves its newly created project. No global `BaseAPIView` or `BaseSerializer` changes are necessary. [S2]

**No fields are deferred.** `only()` can create fresh lazy loads when model properties need omitted columns. It also risks conflicts with joined FK connector fields. Add projection optimization only after separately enumerating all required fields and testing it. [D2–D3]

## 5. Correctness and security invariants

The change must not alter which projects qualify. Preserve the workspace predicate, membership/public predicate, active-membership check, existing manager, `distinct`, annotations and order expression. Nullable user/asset relations must not remove a project from results.

An inactive user may still be the historical creator/editor. Do not add an `is_active=True` filter to audit-user loading; this is not a membership enumeration endpoint.

Do not infer asset visibility from `FileAsset.objects`. Django forward-FK access normally uses a base manager, not necessarily the filtered default manager. The supplied soft-deleted-avatar comparison checks optimized output against fresh legacy loading instead of inventing new policy. [S6–S7, S11, D4]

Do not construct avatar URLs directly from `avatar_asset_id`: that would bypass the existing `asset_url` property and its entity-type handling. The proposed graph covers properly typed avatar assets. A malformed/legacy avatar reference pointing at a non-avatar entity can cause `asset_url` to access `workspace.slug`; this PR should not claim query-free behavior for arbitrary invalid asset relationships without additional reproduction and design. [S7]

Preserve the existing serializer's returned user fields. Eager-loading an ORM row does not itself expose new JSON fields, because the same `UserLiteSerializer` still controls the response. Do not attach raw model dictionaries or user credentials to the response or benchmark output.

The endpoint is replica-eligible. The join plan retains the outer queryset's database selection; do not hardcode `.using("default")` in production. Tests capture actual statements across aliases. Replica lag, concurrent profile updates and cache behavior remain outside this optimization's guarantees. [S2, S12]

## 6. Expected query improvement — not benchmark results

Use this isolated request shape for the key measurement:

```http
GET /api/v1/workspaces/{slug}/projects/?fields=id,name,created_by,updated_by&expand=created_by,updated_by&per_page=100
```

Let `N` be returned projects, both audit users be non-null, and both have correctly typed uploaded avatars. Let `B` represent all other statements for the controlled request path.

| Loading plan | Expected statements for this controlled case |
|---|---:|
| Current legacy loading | `B + 4N` |
| Load only the two user rows | `B + 2N` |
| Join both users and their avatars | `B` |
| Prefetch each audit user with its avatar joined | Approximately `B + 2` for nonempty relations |

At 100 rows, the source-derived model predicts removing 400 relation-fetch statements compared with the fully populated legacy case. **This is an expected count, not an observed Plane benchmark.** Null relations and other request fields change the count. Do not put “400 queries eliminated” or a latency percentage in the PR until measured.

This is constant query *count* for the targeted relationships, not constant runtime. Rows still need fetching, materializing and serializing, and the existing correlated annotations can still perform work per project inside the database. The complete HTTP request also includes authentication, permissions, counts and membership prefetching; it does not become one SQL statement.

## 7. Regression-test strategy

The included draft file uses existing repository fixtures (`workspace`, `create_user`, `api_key_client`), real persisted models and real ORM statements. It does not mock user/asset fetches. It includes both query-level checks and actual API-key client requests. [S13–S14]

The strongest assertion is:

> After the actual GET path has built its optimized queryset and a page has been loaded, serializing the included user expansions executes **zero SQL statements**.

This detects an avatar N+1 even when total request counts are hard to stabilize. Page materialization is measured separately and must genuinely hit the database. The test fixture contains non-null audit fields and real avatar assets, and results must contain the requested users; zero queries on an empty or null-only fixture would be meaningless.

The draft also covers sparse fields, unknown/traversal-looking names, duplicate expansions, inactive/null audit users, a soft-deleted avatar parity comparison, shared users, no-expansion controls, empty results, project visibility and two cursor pages. The HTTP test compares expanded/unexpanded statement counts at page sizes 1 and 12 rather than hardcoding an arbitrary global request budget.

Run it first with only the new tests on an unchanged base. The query-regression cases should fail because of relation reads. Then apply the production patch and run again. An import, fixture, environment or authentication failure is not evidence of the original N+1; investigate the failure reason.

The existing API test package clears its API-key throttle bucket between tests. Keep that behavior. Do not disable production throttling or clear the entire cache to obtain green tests. [S14]

### Real-environment command

From the repository root, with the standard test configuration prepared:

```sh
docker compose -f docker-compose-test.yml run --rm --build api-tests \
  pytest plane/tests/contract/api/test_project_list_expansion_queries.py -q
```

Also run the relevant existing project-list/creation/expansion tests and then the full backend suite. Check formatting and lint separately without modifying unrelated files:

```sh
ruff check apps/api/plane/api/views/project.py \
  apps/api/plane/tests/contract/api/test_project_list_expansion_queries.py
ruff format --check apps/api/plane/api/views/project.py \
  apps/api/plane/tests/contract/api/test_project_list_expansion_queries.py
```

These are commands to execute, **not results already obtained**. At the inspected revision, the hosted API build/lint workflow runs Ruff, not pytest, so a green API lint badge is not backend regression-suite evidence. [S15]

## 8. Benchmark procedure and decision rule

The supplied `tools/benchmark_project_expansion.py` executes four loading plans against the same scoped project query: legacy, users-only, users-plus-avatars and batched prefetch. It uses fresh queryset/model caches for every trial, randomizes strategy order, records individual trials and compares JSON response hashes. It records fetch/serialization query counts, stage times, response bytes and distinct/non-null user-reference counts. Optional Python memory measurement runs separately from the timing trials.

Its output is **page fetch + serialization + JSON encoding**, not end-to-end HTTP latency. The script intentionally skips authentication, middleware, pagination count queries and network transport. It performs no data writes or HTTP calls. It requires a local-test-data acknowledgement and explicitly configured settings.

Example, from `apps/api` in a configured local environment:

```sh
DJANGO_SETTINGS_MODULE=plane.settings.local python \
  /absolute/path/to/plane_query_optimization/tools/benchmark_project_expansion.py \
  --workspace YOUR_SEEDED_WORKSPACE \
  --actor-id YOUR_LOCAL_USER_UUID \
  --sizes 10,50,100,500 \
  --repeat 30 --warmup 3 --measure-memory \
  --confirm-local-test-data \
  --output /tmp/plane-project-expansion-results.json
```

Use your environment's settings and database alias; do not copy this against production. The script refuses to silently benchmark fewer records than requested. It does not seed data for you. Use real supported fixture/model creation paths to prepare an isolated workspace.

Test multiple data distributions: mostly distinct users, a small shared user pool, no uploaded avatars, uploaded avatars, null audit fields, sparse responses and full responses containing covers. Page size and total workspace size are separate dimensions: a 100-row page from 100,000 projects exercises different count/filter/sort costs than 100 rows total.

Measure the complete HTTP endpoint separately using equivalent read-only requests and bounded concurrency against a local/staging stack. Report machine, versions, dataset, page size, expansion fields, cache condition, trial count, base/fixed commit and baseline failures. Do not compare a debug-toolbar run with a production-config run or reuse an already-evaluated queryset as the “after” benchmark.

For PostgreSQL, inspect the actual page SELECT with `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` in the isolated environment. Look at execution time, row width, join behavior, sort/hash memory, spills, loops in correlated subqueries and estimate-versus-actual row counts. `EXPLAIN ANALYZE` executes the query, and its timing is not end-to-end API latency. [D3, D5]

**Decision rule:** retain conditional joins unless the representative measurements show a material repeatable regression or clearly favor prefetching. Prefer prefetching if it substantially reduces duplicate row transport/object allocations or avoids expensive widened query work without unacceptable latency or behavioral tradeoffs. Do not switch dynamically by page-size threshold without enough evidence to maintain that policy.

A one-batch request-local loader is a third-stage optimization, not the first deliverable. Its additional design obligations must be justified by measured gains over Django's standard facilities.

## 9. PR preparation

Suggested title:

`perf(api): eager-load included user expansions in project lists`

Reference #9717 as the source of the deliberately deferred performance work, without saying that this PR re-fixes the earlier null-expansion issue or closes every API N+1.

Keep the production diff small. The value of this contribution is the complete dependency analysis, proof of preserved behavior and measured improvement—not the number of lines changed. Discuss a larger shared loading hook only after this endpoint demonstrates a repeatable pattern across other serializers.

The repository search performed for related open work did not establish a reservation or maintainer approval. Recheck overlapping PRs and coordinate before filing; do not describe this as an assigned issue.

Use `PR_DRAFT.md` only after replacing verification placeholders with actual results. State exactly what remains unverified. Do not claim this has improved production traffic, a release, or customer latency before such evidence exists.

## Sources

Repository source references are pinned unless the source is a historical PR or search.

- **S1:** https://github.com/makeplane/plane/pull/9717
- **S2:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/api/views/project.py
- **S3:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/api/views/base.py
- **S4:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/api/serializers/base.py
- **S5:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/api/serializers/project.py
- **S6:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/db/models/user.py
- **S7:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/db/models/asset.py
- **S8:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/utils/paginator.py
- **S9:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/db/models/project.py
- **S10:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/db/models/base.py
- **S11:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/db/mixins.py
- **S12:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/utils/core/mixins/view.py
- **S13:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/tests/conftest.py
- **S14:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/apps/api/plane/tests/contract/api/conftest.py
- **S15:** https://github.com/makeplane/plane/blob/7466675e471efe1c96b122615f7a0d30c9b2eb05/.github/workflows/pull-request-build-lint-api.yml
- **D1:** https://www.django-rest-framework.org/api-guide/relations/
- **D2:** https://docs.djangoproject.com/en/5.2/ref/models/querysets/
- **D3:** https://docs.djangoproject.com/en/5.2/topics/db/optimization/
- **D4:** https://docs.djangoproject.com/en/5.2/topics/db/managers/
- **D5:** https://www.postgresql.org/docs/current/using-explain.html
- **D6:** https://pytest-django.readthedocs.io/en/latest/helpers.html
- **A1:** https://github.com/rsinger86/drf-flex-fields
- **A2:** https://github.com/GeeWee/django-auto-prefetching
- **A3:** https://github.com/adamchainz/django-auto-prefetch

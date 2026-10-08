# Verification report

This report distinguishes tests actually executed during authoring from supplied acceptance tests that require a local runtime.

## Executed

| Check | Result |
|---|---|
| Python source compile | Passed for backend and tests |
| Backend unit/API tests | 11 passed |
| PostgreSQL integration tests | 9 skipped: no TEST_DATABASE_URL / PostgreSQL server |
| Frontend motion calculation tests | 4 passed |
| TypeScript check and Vite production build | Passed; see build notes below |
| PostgreSQL grammar parsing | Passed: 25 schema statements, 12 demonstration statements and 62 static backend SQL statements (manufacturing revision) |
| Compose YAML parsing | Passed; 8 service definitions parsed |
| Playwright test discovery | 6 tests discovered; not executed |
| Generated hero inspection | Image inspected; not a rendered browser page |

Backend tests actually executed: SQLSTATE-based cause ranking, conflicting-cause abstention and contradiction references, duration-only ambiguity, insufficient-evidence outcome, real sklearn training/scoring on separated synthetic train/evaluation samples, three invalid-control cases, unrestricted explorer query rejection, invalid import/fault validation, cross-origin mutation rejection visible database-unavailable API response and evidence-based production-quantity mismatch ranking. The 11-test count includes parametrized invalid controls.

Motion tests exercised the pure calculation functions for reversal, simultaneous scale/tracking changes, clamping, reduced-motion completion and the 10% drag threshold. A 1440×900 viewport calculation exceeds 100 px of panel travel at 700 px scroll. **This is not measured browser element travel.**

Dependencies were installed and the frontend compiled. The final build uses React 19.1.0, Vite 6.3.5, TypeScript 5.8.3 and Recharts 3.3.0 with a committed npm lockfile. Python tests ran with the pinned direct backend dependencies, including scikit-learn 1.6.1 and numpy 2.2.5. The build may warn about a bundle larger than 500 kB; optimization/code splitting remains future work. Starlette test execution emitted an AnyIO alias deprecation warning; tests passed.

## Not verified here

- No Docker executable or native PostgreSQL runtime was available. Attempting ordinary PostgreSQL installation encountered environment permission restrictions; no privilege bypass was attempted.
- Consequently no claim is made that the PostgreSQL faults, lock cleanup, rollback logging, baseline integration, actual worker processes, volume persistence or full HTTP rehearsal ran in this environment.
- A supported browser QA capability was unavailable under the environment's site-preview rules. No preview server, browser automation or screenshots were used to claim visual success.
- Pointer capture/cancel, actual scroll-linked travel, physical mobile vertical gestures, reduced-motion rendering, no-JavaScript browser output, focus visibility, contrast, control obstruction and overflow remain local acceptance checks.
- SQL grammar checks do not validate runtime types, table dependencies, query results, transaction semantics or container startup.

## Supplied local acceptance coverage

`tests/test_postgres.py` contains nine PostgreSQL tests (including three fault parameter cases), isolated in unique schemas. They cover normal stage transitions/correlation; real delay, lock timeout and duplicate-key exceptions; logging surviving rollback; downstream quality blocking; observed recovery; baseline exclusion/current evaluation separation; duplicate Start; stop/fault cleanup; application-process persistence; per-schema advisory locks; idempotent external imports; explorer reads and three distinct worker processes.

`frontend/qa/visual.playwright.ts` contains six browser tests. These check measured portal movement/reversal/growth/tracking and clickable access, keyboard and pointer deck cycling/cancel handling, reduced motion, mobile overflow/scroll support, no-JavaScript fallback, API error and file-import error presentation. Test discovery succeeded but these tests were not run. Physical-device gestures still require manual verification.

`scripts/rehearse.py` runs the requested normal → history → faults → evidence → recovery → saved history sequence against a running Docker application. Container/database restart persistence is an additional manual acceptance step in README, not falsely covered by opening a new connection.

## Before presenting

Run Docker startup, the database integration command, the HTTP rehearsal, browser tests and the explicit restart demonstration in README. Reconcile any observed runtime issue before calling the project fully verified. Keep this report with the source so “implemented” is never confused with “verified in every environment.”

Manufacturing revision: worker schemas, SQL operations, API stages, UI labels and documentation adapted together. Fresh database isolation preserves earlier demo history. The manufacturing revision still requires local PostgreSQL and browser acceptance; prior screenshots only demonstrate the earlier version. A new integration test verifies material quantities, batch units and an inspection hold.

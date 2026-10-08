# ROOTLENS
### Manufacturing process investigator · controlled local demonstration

RootLens follows synthetic steel-bracket production orders through three separate software workers: **Materials → Production → Quality**. It records real PostgreSQL transactions and bounded database faults, detects unusual durations with per-worker Isolation Forest models, and saves evidence-based investigations.

**Verification status:** source and production frontend build are supplied; database/runtime and rendered-browser acceptance are not verified in the authoring environment. See `docs/VERIFICATION.md` for the exact executed checks. This is a local application, not a hosted demo URL.

## Switching from the earlier version

1. In your **old** rootlens folder, stop the old project while keeping its data:

```powershell
docker compose -p rootlens down
```

2. Extract the updated ZIP into a **new folder**, then open its inner `rootlens` directory. Do not mix the old and new source files.
3. Run the startup commands below. This version uses project name `rootlens-manufacturing`, giving manufacturing its own database volume. Earlier records and baselines remain in the old volume; they are not relabeled.
4. Start workload and collect fresh manufacturing baselines. Do not use `down -v` or change the new project name.

The first manufacturing build may take several minutes. Your old app can still be restarted separately, but both apps cannot use the same host ports simultaneously.

## Start on Windows

Install Docker Desktop and enable Linux containers. Extract this ZIP. Open PowerShell in the extracted `rootlens` directory (the one containing compose.yaml):

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

Wait for the initial builds, then open **http://localhost:8080**. Click **Open workspace → Start workload**. Nothing produces orders until you click Start. An optional `start.ps1` runs the same commands; no PowerShell policy changes are necessary if you use the commands above.

Requires internet for the first Docker/dependency build. After building, the application uses no external API, hosted fonts or paid keys. Allow roughly 2 GB free disk for images and dependencies. Ports 8080, 8000 and 5432 must be free.

Linux/macOS: `cp .env.example .env`, then the same Docker Compose command.

## What to click

1. Start workload. Confirm A, B and C have recent heartbeats and completed operations.
2. Wait for **40 normal historical samples per worker**; usually less than a minute on a normal laptop, but no timing is guaranteed.
3. Open **Database explorer** to inspect committed orders, production records, events and baselines.
4. Open **Live operations**, choose **B / Production**, select **LOCK TIMEOUT**, and click **Apply**.
5. Follow **Investigate ↗** from an error. Look at SQLSTATE 55P03, supporting and contradictory evidence, affected orders and pending production/quality stages.
6. Click **Recover**. This clears faults; the incident closes only after three new healthy observations.
7. Try **SLOW QUERY** and **CONSTRAINT VIOLATION** separately, recovering between them. Reopen **History** for saved reports.
8. Click **Stop** when finished. This stops production/processing and clears configured faults. In-flight work is bounded and may finish within five seconds.

The full 7-minute script is `docs/DEMO.md`.

## Where data and errors come from

Orders are clearly labeled synthetic-local. Each worker claims eligible orders and writes a stage-specific database record. Actual durations include connection, query and commit time; they are not preassigned numbers. Materials reserves two blank units per bracket. Production computes completed units from that reservation and writes a batch record. Quality compares produced units with ordered units and records pass/hold. These are genuine SQL operations representing a factory workflow, not physical fabrication or sensor inspection.

Slow query executes PostgreSQL `pg_sleep(1.25)`. Lock contention holds a dedicated row in another connection and triggers a real 450 ms lock timeout. Constraint violation inserts a duplicate demo key. The failed transaction rolls back before a separate connection records the actual database exception. These faults do not modify unrelated data.

“Orders store business state. Event logs record what happened while processing those orders.”

## Live architecture

- Browser: React + TypeScript + Vite, local Syne/Sora fonts, Recharts, custom CSS.
- Web: Nginx proxies `/api` and serves the compiled application.
- API: FastAPI with input validation and predefined read-only explorer queries.
- Persistence: PostgreSQL 16 named volume, parameterized psycopg SQL.
- Three processes/services: materials (A), production (B), quality (C).
- Engine: singleton order producer, event detector and bounded investigator, independent of the browser.
- ML: one Isolation Forest per worker, historical-only training and a persisted training cutoff; no LLM or API key.

See `docs/ARCHITECTURE.md` for evidence rules, thresholds, recovery and known failure windows. The investigation does not read the selected fault mode or audit table. Evidence strength is not a calibrated probability.

## Database connection and independent SQL

| Setting | Default local value |
|---|---|
| Host | localhost |
| Port | 5432 |
| Database | rootlens |
| User | rootlens |
| Password | POSTGRES_PASSWORD in your .env; example is rootlens_local |

Use DBeaver/pgAdmin, the built-in explorer, or:

```powershell
docker compose exec db psql -U rootlens -d rootlens
```

Paste any SELECT from `demo_queries.sql`. The file only reads records. `backend/schema.sql` initializes manufacturing schema version 2 automatically; `schema_versions` records initialization. The `.env.example` contains a local demo credential, not a real secret. If your password contains URI-reserved characters, URL-encode it in the compose DATABASE_URL values or use a simple local-only password.

## External input

Data sources / setup → Import JSON file, using `samples/external-events.json` as the format. Or POST `{ "events": [...] }` to `/api/import`. Maximum 500 events / 1 MB; UTC-aware timestamps and nonnegative finite durations are required. All fields requested in the brief are represented. UUID event IDs make repeated imports idempotent.

External records are prefixed `ext:` / `external:` and cannot enter local training or masquerade as local worker success. The supplied example is an illustrative external log, not proof of a newly executed database fault. Imported logs do not create or change local orders. Unknown upstream business state is not fabricated. API documentation: http://localhost:8080/api/docs.

## Tests

Unit/integration suite in a container:

```powershell
docker compose --profile test run --rm test
```

Without TEST_DATABASE_URL, nine database tests deliberately skip. To run those tests against the local database, with all services running:

```powershell
docker compose --profile test run --rm -e TEST_DATABASE_URL=postgresql://rootlens:rootlens_local@db:5432/rootlens test
```

Adjust the credential if changed. Every PostgreSQL test creates and removes its own uniquely named test schema. Existing demo rows remain intact. The test owner needs CREATE SCHEMA permission. Tests cover real timeout/delay/constraint behavior, rollback evidence, worker/order correlation, downstream blocking, baselines, observed recovery, idempotent import, application-process persistence, advisory locks, cleanup, and distinct worker processes.

Full running-system HTTP rehearsal, from your host with Python 3.12 installed:

```powershell
python scripts/rehearse.py
```

This enables the demo and applies all three faults; it always tries to Stop at the end. Use a rehearsal session, not a concurrent presentation.

Frontend checks (Node 22):

```powershell
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:browser
```

Keep Docker Compose running for browser tests. These test portal travel, reversal, simultaneous growth/tracking, deck pointer/keyboard behavior, reduced motion, mobile layout, no-JavaScript content and error states. A touch-action CSS assertion is not a physical-device gesture test; manually verify mobile vertical dragging on your phone too.

## Persistence demonstration

Note a saved investigation ID in History. Run:

```powershell
docker compose restart api engine materials production quality
```

Reopen that ID. Then, if desired, use `docker compose restart db`; wait for health and reopen History. PostgreSQL volume persistence is configured but server/container restart verification was not run in the authoring environment. These are explicit local acceptance steps.

To shut down without losing records: `docker compose down`. **Do not add `-v` unless you intentionally want to delete all demo history.** Fault/running control flags persist; use Stop before ending a rehearsal so a later startup does not resume activity unexpectedly.

## Without Docker (advanced)

Install PostgreSQL 16, create the rootlens database and user, set DATABASE_URL, then:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -c "from backend.db import init; init()"
.venv\Scripts\python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

In four other terminals with the same DATABASE_URL: run `python -m backend.engine`, and run `python -m backend.worker` separately with WORKER_ID set to A, B, and C. Activate the virtual environment or use its full interpreter path. In frontend, `npm ci` then `npm run dev`; open http://localhost:5173. Vite proxies /api to the local backend. Docker remains the recommended route.

## Scope

Implemented source: six-section presentation, scroll-linked portal, accessible throwable deck, six workspace views, live SQL records, imports, bounded real faults, ML baselines, independent detector labels, saved evidence ranking, order impact, queue snapshots and observed recovery.

Controlled simulations: order arrivals, local materials reservations, production batches and quantity inspections, intentionally injected SQL faults, illustrative scenario cards before reports exist, generated industrial hero image. All are labeled.

Future work: authenticated production hosting, durable transactional outbox, telemetry during full database outages, CPU/memory metrics, query-plan capture, drift-aware retraining, stronger causal inference, real production/stock adapters, pagination/export, retention/archival and broader accessibility testing. No production accuracy, physical hardware, LLM planning or financial-loss claims are made.

Other deliverables: `docs/TROUBLESHOOTING.md`, `docs/TEAM-AND-PANEL.md`, `docs/VERIFICATION.md`, `docs/ASSETS.md`, sample input, SQL queries, PowerShell helpers, automated tests and full source. No screenshots are included because no browser rendering was verified here.

Manufacturing framing and presentation wording: see `docs/MANUFACTURING.md`. Quality inspection here means quantity reconciliation only. A genuine quality hold remains pending for human disposition; Recover is not a quality-release approval.

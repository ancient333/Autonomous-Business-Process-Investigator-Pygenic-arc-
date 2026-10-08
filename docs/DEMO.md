# Seven-minute demonstration

Prepare first: Docker Desktop running; `docker compose up --build -d`; open http://localhost:8080. Allow image builds to finish before the panel. Never describe the background image as connected equipment.

**0:00–0:45 — State the problem.** “A steel-bracket production order crosses Materials, Production and Quality. A delay in production can hold up quality. RootLens preserves the activity and investigates possible causes.” Briefly scroll the portal and reverse once. Use Open workspace immediately if time is short.

**0:45–1:45 — Start and establish normal history.** Click Start workload. Show all three workers and growing completed counts. Wait for 40 historical normal samples per worker (typically 30–60 seconds). Start again: it changes one persisted control flag, never spawns another producer. Show `docker compose ps`; the materials, production and quality containers are distinct processes. Orders are synthetic; SQL operations and durations are real.

**1:45–2:30 — Show business state and event evidence.** Database explorer → orders, production, events, baselines. “Orders store business state. Event logs record what happened while processing those orders.” Open demo_queries.sql in DBeaver if desired. Verify matching order and correlation IDs across workers.

**2:30–3:30 — Inject production lock contention.** Live operations → worker B / Production → LOCK TIMEOUT → Apply. Within a few seconds, inspect a real `55P03` error and open its investigation. Production transaction rolled back; the independent logging connection committed the error. Quality can remain Running while pending production grow.

**3:30–4:30 — Explain the investigation.** Open the first explanation, supporting event IDs, contradictory evidence and missing blocker identity. Show affected orders and incomplete stages. Compare the process backlog snapshots; they measure the whole process, not proven incident-specific causation. The investigator reads logs, never the selected fault mode. A score of 95 is an explicit rule strength, not 95% probability.

**4:30–5:15 — Recover.** Click Recover. Point out that this only clears fault controls. Watch three new successful B operations before the incident becomes recovered. Pending orders retry and quality catches up. Reopen History to show the report is retained.

**5:15–6:15 — Contrast two other conditions.** Apply SLOW QUERY to B: PostgreSQL executes pg_sleep(1.25); the measured operation becomes slow. Its report should keep competing explanations because duration alone does not establish causality. Recover, wait for confirmation, then apply CONSTRAINT VIOLATION: show actual SQLSTATE 23505 and the named dedicated demo table. Recover again.

**6:15–7:00 — Close honestly.** Show Data sources → import samples/external-events.json. It is explicitly an unverified sample, not a newly executed database error. Stop workload. Explain duration-only ML, fixed evidence workflow, bounded faults, no physical machines, no LLM agent and no actual machine actuation or physical defect inspection. `docker compose restart api` retains SQL history; `docker compose down` also retains the volume.

If a baseline is not ready, use deterministic errors immediately and say ML is still collecting history. If a service is unavailable, show the error rather than presenting saved rows as live.

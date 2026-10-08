# Architecture and evidence model

The React/TypeScript browser requests a snapshot every two seconds. It never produces business activity. Nginx serves the build and proxies /api to FastAPI. Polling is deliberately used for a small, inspectable local demo: one request completes before the next is scheduled, failures are visible, and the backend remains independent of browser tabs.

PostgreSQL persists orders, materials reservations, production batch records, quantity-inspection records, append-only events, workers/heartbeats, historical baselines, anomalies, investigations, fault audit and process queue snapshots. The Docker named volume survives container and application restarts. `schema.sql` is the idempotent version-2 initialization, with a schema_versions row. Future schema evolution needs numbered migrations; it is not a general migration framework.

A singleton engine holds PostgreSQL advisory lock (hashtext(current_schema()), 7000) for its session. It generates one synthetic order each cycle while enabled and the unfinished backlog is below 150. The same engine consumes committed event sequence numbers from a persistent checkpoint. Separate A/B/C worker processes hold identity-specific advisory locks and claim eligible orders with FOR UPDATE SKIP LOCKED. Stage changes and stage records commit together. Failed orders become eligible to retry after two seconds; a later stage cannot bypass a prerequisite.

Actual local operations:
- Materials reserves two STEEL-BLANK material units per requested bracket. Reservations are local demo records; there is no finite physical stock ledger.
- Production reads reserved material quantities and records a completed batch with produced_quantity = material quantity // 2 and a unique batch_id. No physical fabrication occurs.
- Quality reads the batch record, compares produced units with requested units, and saves a unique inspection_id, expected_units, checked_units and pass/hold outcome. This checks record quantities, not physical dimensions or defects. A mismatch holds that order and records a business validation error; it is not mislabeled a database exception.
- A variable-size SQL aggregate supplies a small normal measured workload.

Faults are restricted to a row per worker in demo_records. Slow query executes pg_sleep(1.25). Lock timeout opens an independent connection, locks that row, then the worker operation tries to update it under 450 ms lock_timeout. The holder has a three-second idle transaction timeout and always rolls back/closes in finally. Constraint violation attempts to insert the already-existing worker primary key. Statement timeout bounds each business SQL statement to five seconds. Stop clears conditions; a bounded in-flight operation may still finish.

A business transaction rollback occurs before error evidence is inserted using an independent connection. There is a known crash window between business commit and event insert; an outbox is future work. A whole database outage can also prevent evidence persistence; it is logged to process stderr, not falsely represented as committed event evidence.

# Anomaly detection

One real scikit-learn IsolationForest per local worker. First 40 eligible successful historical duration samples train it. Current evaluation has a strictly later sequence number; the training event IDs, features, cutoff, seed and parameters are saved. Models are cached in memory and reconstructed deterministically after an engine restart. Random seed 42; contamination .05; 100 trees. The first fitted baseline remains frozen. No accuracy claim, automatic concept-drift adaptation or calibration is made.

Training excludes external input, errors, retried orders and all operations initiated while any demo fault is active. This is provenance gating in collection, not an investigator lookup. A tiny control-change/in-flight boundary can exist; see limitations. Duration is the only ML feature. Failure rates and queue depths remain inspectable deterministic business data rather than secretly claimed ML inputs.

Three distinct detectors are stored as labels:
1. deterministic_error for an actual error event;
2. statistical_safeguard above max(500 ms, median + 8 × max(MAD,1 ms)); cold-start fallback is 500 ms;
3. ml_isolation_forest when decision_function < 0.

A significant event starts/updates an investigation: any error, any safeguard breach, or a slow-tail ML flag above max(50 ms, 3 × training median). Other ML flags are recorded without opening an incident. This prevents ordinary fast-tail ML outliers from flooding reports. Positive or negative scores and detector labels are available in SQL. Cold-start errors work before an ML model exists.

# Bounded evidence investigation

The workflow queries at most 300 events from the worker's preceding 60 seconds and the triggering correlation ID up to trigger time. It projects SQLSTATE but does not read fault provenance, controls or audit tables. It records execution-step times, candidate causes, supporting/contradictory event IDs, missing evidence and diagnostic advice. At most 500 affected order IDs accumulate per open incident. Reports are updated until recovery; they are snapshots, not exhaustive distributed traces.

Documented ranking:

| Candidate | Strength rule |
|---|---|
| Lock contention | 95 if SQLSTATE 55P03; otherwise 15 for long duration, else 0 |
| Duplicate/invalid data | 95 for SQLSTATE 23505, else 0 |
| Slow database operation | 60 for duration >500 ms without errors; 20 if also errors |
| Resource pressure | 45 for long duration without errors; otherwise 5 |
| Upstream failure | 85 for a correlated preceding-stage error; otherwise 0 |
| Production quantity mismatch | 90 for an observed quantity-reconciliation validation error; otherwise 0 |
| Missing monitoring data | 10 as a missing-evidence hypothesis, not a detected outage |

Specific incompatible SQLSTATE evidence appears in contradiction lists. Two strong competing codes prevent a confident conclusion. A named leading cause requires strength ≥80 and a ≥20-point lead; otherwise the result is “Competing explanations remain.” or “Insufficient evidence.” Strength is not a probability. Successful records alone do not contradict an intermittent error. Resource pressure lacks direct measurements and is never asserted as proven.

Recovery requires three consecutive new successful events after the last anomaly, at or below the safeguard threshold, from the same observed source. Clearing a fault or clicking Recover cannot directly mark an incident recovered. Fast-tail ML oddities do not prevent operational recovery. External source recovery is based only on supplied logs and remains unverified.

Impact is computed from actual affected order rows: pending materials/production/quality and incomplete orders. Process-wide backlog differences come from stored snapshots before and during the incident. A baseline/current duration comparison is observational and can mix activity; it is not a controlled causal estimate. No financial loss is fabricated.

# Boundary and deployment

This is intentionally a localhost Docker application, not a hosted Cloudflare app: the requested Python/scikit-learn and native PostgreSQL workers do not run in a Cloudflare Worker isolate. All published host ports bind to 127.0.0.1. There is no production identity provider or multi-tenant authorization. Do not expose the local API to a network. External imports receive an ext: worker prefix and external: source prefix, cannot enter local training and cannot spoof local worker recovery.

Implementation references consulted:
- psycopg transaction contexts and rollback: https://www.psycopg.org/psycopg3/docs/basic/transactions.html
- IsolationForest decision function and contamination: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html

Manufacturing v2 runs under the distinct Compose project rootlens-manufacturing and a new named volume. Earlier retail records are not relabeled or imported. A guard rejects the old payment_state schema. Quality holds require human disposition; Recover clears injected database faults and verifies worker health but does not release a held batch.

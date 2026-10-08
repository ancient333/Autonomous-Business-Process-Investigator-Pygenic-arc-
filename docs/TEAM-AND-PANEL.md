# Four-person split

| Person | Ownership | What to demonstrate |
|---|---|---|
| 1 — Process/backend | schema.sql, db.py, worker.py, Docker Compose | genuine transactions, three processes, correlation, retries and faults |
| 2 — ML/evidence | detector.py, investigate.py, engine.py | historical-only baselines, score labels, conflicting evidence and recovery |
| 3 — Product/frontend | React workspace, CSS, portal and deck | operational controls, errors, mobile/reduced motion, data explorer |
| 4 — Integration/presentation | tests, imports, README, demo_queries.sql, rehearsal | repeatable startup, persistence, end-to-end tests, panel explanation |

Each person should run the entire local demo once; do not leave system knowledge divided into isolated pieces.

# Panel questions and honest answers

**What is autonomous?** Committed events are analyzed in a background process. Significant anomalies trigger a bounded retrieval-and-ranking workflow without a user selecting an investigation. It is a fixed workflow, not an LLM planning agent.

**Are these real machines?** No. Three separate local software worker processes represent machines or services in a business workflow. The hero photo is illustrative.

**Is the data real?** Orders are labeled synthetic. They cause actual PostgreSQL writes, measured SQL operations, and genuine database exceptions under contained demo faults. Imported sample logs are unverified external input and clearly separate.

**Where is the machine learning?** A scikit-learn Isolation Forest learns each worker's historical normal duration distribution and scores later observations. Errors and safeguards are labeled independently. We have not measured production precision or recall.

**Does the model know which fault we clicked?** The investigator does not read fault controls. Collection excludes fault-active data from normal training, but cause ranking uses observed logs, SQLSTATE and correlated records.

**Why not just read the error message?** SQLSTATE can strongly identify a lock or constraint failure, but impact depends on which order and stage were affected. The investigation follows those records, shows downstream waiting and preserves contradictory or missing evidence.

**Is 95 a confidence percentage?** No. It is a documented evidence rule strength, not calibrated probability.

**Why might a slow query report have competing explanations?** Measured operation latency alone cannot establish whether a query, contention or resource pressure caused the delay. Query plans, waits or resource metrics would be needed.

**How do you know it recovered?** Only three later healthy operations meeting the threshold can close the incident. The Recover button clears the fault and leaves verification pending.

**What happens when the entire database is down?** API calls return a visible 503 error, worker/engine operations log stderr failures, and persistent evidence may be unavailable. A separate durable telemetry sink is future work.

**Why polling?** Two-second sequential polling is simple and adequate for a local hackathon. Backend collection does not depend on an open browser. SSE/WebSockets could reduce repeated snapshot transfer at larger scale.

**Why PostgreSQL?** It lets judges independently inspect committed business state, event history, locks and errors with standard SQL, while transactions enforce stage data consistency.

**What is not production ready?** Authentication, encryption deployment, resource telemetry, external production/stock integrations, retention policies, robust event outbox, drift detection and large-scale causal analysis remain future work.

**Which domain?** Manufacturing operations monitoring / Industry 4.0 software. The demonstration models a steel-bracket production line.

**Is this predictive maintenance?** No. It detects current operation anomalies and investigates observed evidence; it does not predict equipment lifetime or future physical failures.

**Is this a real quality inspection system?** It reconciles quantities in stored records. It has no camera, PLC, temperature sensor, tolerance measurement or defect classifier. Those are future integrations.

# Troubleshooting

**Docker command not found / daemon unavailable:** install and start Docker Desktop, use Linux containers, and wait until its engine is ready. Run `docker compose version`.

**Port already allocated:** stop the application currently using 8080/8000/5432, or edit the host-side port in compose.yaml. If changing the web port, add the new local origin to the API's allowlist too.

**Build failure:** ensure internet access for Docker images, npm and PyPI. Run `docker compose build --progress plain`. Frontend uses the committed package-lock.json and npm ci. Python direct dependencies are pinned in requirements.txt.

**Database unavailable / 503:** `docker compose ps`, then `docker compose logs --tail 80 db api`. Host applications use localhost:5432; containers use db:5432. Do not paste credentials into public screenshots.

**Changing .env password does not change an existing database password:** PostgreSQL initializes its account on the first empty volume only. Use the original credential or deliberately update the database user's password. Do not delete the volume merely to hide a connection problem.

**Workers show Not started or Offline:** check `docker compose logs --tail 80 materials production quality`. Start workload in the UI. Two containers/processes with the same identity cannot own the advisory lock concurrently; stop duplicates before restarting the intended process.

**Baselines stay collecting:** allow 40 eligible successful events per worker before injecting faults. All active-fault periods, retries and external events are excluded. Workers must be progressing through every stage. Cold-start real database errors still appear without ML.

**No new orders appear after repeated faults:** the local backlog cap is 150. Click Recover, keep the workload running, and let pending orders drain. No orders are silently dropped to manufacture recovery.

**Recover did not instantly close a report:** expected. Three new successful under-threshold observations are required. If workload is stopped, click Start. A second active fault elsewhere can delay the observed stage.

**Lock holder remains after Stop:** an in-flight operation may be finishing. The demo lock is rolled back in finally, idle transaction timeout is three seconds and SQL statement timeout is five seconds. If a process has died, PostgreSQL releases its connection's locks. Stop the worker container if necessary; never kill unrelated PostgreSQL sessions.

**An error shows before an investigation link:** the background detector polls committed events. Refresh after a few seconds. If it persists, inspect engine logs. Deterministic evidence is still stored even before ML baseline readiness.

**Imported sample has old dates:** the sample intentionally includes a fixed example UTC date. Replace timestamps and UUIDs for a new external demonstration. Re-importing the same event UUID does not duplicate it. External input does not update local business orders.

**Frontend reports unavailable but shows prior counts:** the connection-error banner marks retained data as stale. Do not represent it as current. The table refreshes after reconnection.

**Tests skipped:** set TEST_DATABASE_URL exactly as shown in README to run PostgreSQL integration tests. A skipped database test is not a passing integration test.

**Database test isolation:** advisory locks are keyed by the current database schema and process identity. Each integration test uses a unique schema, so its workers and engine do not claim the normal application's process locks.

**No JavaScript / reduced motion:** landing content is statically readable. Operational controls require JavaScript and show an explanatory fallback. Reduced-motion users see an open hero and can use deck buttons without large animations.

**Persistence checks:** down/restart preserve the named volume; down -v removes it. The full rehearsal does not automatically restart your database. Perform the explicit README restart check after saving an investigation ID.

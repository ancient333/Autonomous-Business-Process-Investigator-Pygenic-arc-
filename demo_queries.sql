-- Connect to localhost:5432, database rootlens, user rootlens; password from .env.
-- Run each SELECT independently. This file performs no writes.
SELECT worker_id,stage,status,heartbeat FROM workers ORDER BY worker_id;
SELECT order_id,correlation_id,materials_state,production_state,quality_state,attempts FROM orders ORDER BY created_at DESC LIMIT 20;
SELECT seq,event_id,timestamp AT TIME ZONE 'UTC' AS utc_time,worker_id,process_stage,order_id,correlation_id,status,duration_ms,error_type,metadata->>'sqlstate' AS sqlstate FROM events ORDER BY seq DESC LIMIT 40;
-- Failed activity persists even when production_records has no matching row.
SELECT e.order_id,e.error_type,e.error_message,p.batch_id FROM events e LEFT JOIN production_records p USING(order_id) WHERE e.status='error' ORDER BY e.seq DESC LIMIT 20;
-- A healthy quality worker can wait for unsuccessful production.
SELECT order_id,production_state,quality_state FROM orders WHERE materials_state='done' AND production_state!='done' ORDER BY created_at;
-- Correlate one real order: replace this subquery with its order UUID if desired.
SELECT * FROM events WHERE correlation_id=(SELECT correlation_id FROM orders ORDER BY created_at DESC LIMIT 1) ORDER BY timestamp;
SELECT worker_id,sample_count,training_max_seq,threshold_ms,metadata FROM baselines;
SELECT event_id,detectors,ml_score,investigation_id FROM anomalies ORDER BY timestamp DESC LIMIT 20;
SELECT id,worker_id,started_at,last_anomaly_at,status,recovered_at,report->>'conclusion' AS conclusion FROM investigations ORDER BY started_at DESC;
SELECT * FROM process_snapshots ORDER BY timestamp DESC LIMIT 30;
-- Inspect current bounded locks while LOCK TIMEOUT is active.
SELECT pid,wait_event_type,wait_event,state FROM pg_stat_activity WHERE datname=current_database();
-- Separate fault audit: the investigator never reads this table.
SELECT * FROM fault_audit ORDER BY id DESC LIMIT 20;

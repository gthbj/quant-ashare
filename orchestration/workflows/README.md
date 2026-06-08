# Workflows migration scaffolding

This directory contains the first implementation slice of the Composer exit plan.

Included in this PR:
- `ashare_ods_ingestion_daily.yaml`: ODS daily ingestion workflow with explicit task-status writes, SSE non-trading-day gate support, Cloud Run Job execution, ODS readiness QA, and synchronous child workflow invocation.
- `ashare_warehouse_window_refresh.yaml`: warehouse window refresh workflow with explicit task-status writes, GCS-backed distributed lock, window DWD/DWS refresh, market-state refresh, and QA chain execution.
- `ashare_pipeline_alert_checker.yaml`: hourly alert-check workflow with parameter normalization and a single authenticated call into `ashare-pipeline-control /v1/tasks/alert-check`.
- `ashare_warehouse_full_rebuild.yaml`: code-only draft for a manual full rebuild workflow with explicit confirmation gate, shared warehouse-write lock, full DIM/DWD/DWS rebuild order, metadata refresh, and QA chain execution.
- `Dockerfile.pipeline_control`: thin Cloud Run control-plane adapter image that executes bundled SQL, writes `pipeline_run` / `pipeline_task_status`, and manages orchestration leases.
- `deploy_pipeline_control_service.sh`: build and deploy the control-plane Cloud Run service.
- `deploy_workflows.sh`: deploy the three production-ready workflows after substituting the control-service URL; `ashare_warehouse_full_rebuild` is opt-in only via `DEPLOY_FULL_REBUILD=true`.
- `deploy_scheduler_jobs.sh`: create or update the hourly Cloud Scheduler job that invokes the alert-check workflow through the Workflows Executions API.

Also included in this PR:
- `ashare-pipeline-control` alert-check endpoint that reuses `scripts/alerting/check_alerts.py`
- hourly alert-check scheduling target (`0 * * * *`) for the non-Composer path via `Cloud Scheduler -> Workflows -> ashare-pipeline-control`
- alert-check workflow intentionally does not write `ashare_meta.pipeline_run` / `pipeline_task_status`, to avoid self-referential alerts and observability-table pollution

Not included in this PR:
- production deployment of `ashare_warehouse_full_rebuild`
- ODS / warehouse production Cloud Scheduler cutover jobs
- IAM bootstrap / production cutover scripts

Design boundary:
- Workflows remains the orchestrator.
- BigQuery remains the execution engine for SQL tasks.
- Cloud Run Job `ashare-ingest-current-scope` remains the execution engine for ODS ingestion.
- `ashare-pipeline-control` is a thin adapter for status writeback, SQL execution, SSE gate queries, and distributed lock management. It is not a general custom orchestrator.
- `ashare_pipeline_alert_checker` is the exception to workflow-level state writeback: it relies on Workflows execution status plus Cloud Logging heartbeat/absence alerting, and intentionally does not write `pipeline_run` / `pipeline_task_status`.

Deploy order:
1. Deploy `ashare-pipeline-control`
2. Grant the workflow runtime service account access to:
   - invoke the control service
   - run `ashare-ingest-current-scope`
   - execute child workflows
   - query BigQuery and write `ashare_meta`
   - read/write the orchestration lock bucket
3. Deploy the three production-ready workflows
4. Leave `ashare_warehouse_full_rebuild` undeployed by default; only deploy it later with `DEPLOY_FULL_REBUILD=true` after the BigQuery execution path becomes async/polled and production-ready
5. Grant the Cloud Scheduler caller service account `roles/workflows.invoker` on `ashare_pipeline_alert_checker`
6. Deploy the hourly alert-check scheduler job, and pause or delete the Composer DAG `ashare_pipeline_alert_checker` at the same time to avoid double-running the checker
7. Verify manual workflow execution plus one real Scheduler fire before cutover
8. Add ODS / warehouse production triggers in a later PR

Example:
```bash
cd orchestration/workflows
./deploy_pipeline_control_service.sh
PIPELINE_CONTROL_URL="https://ashare-pipeline-control-xxxxx-uc.a.run.app" ./deploy_workflows.sh
# Optional only after full rebuild is production-ready:
# DEPLOY_FULL_REBUILD=true PIPELINE_CONTROL_URL="https://ashare-pipeline-control-xxxxx-uc.a.run.app" ./deploy_workflows.sh
./deploy_scheduler_jobs.sh
```

# Workflows migration scaffolding

This directory contains the first implementation slice of the Composer exit plan.

Included in this PR:
- `ashare_ods_ingestion_daily.yaml`: ODS daily ingestion workflow with explicit task-status writes, SSE non-trading-day gate support, Cloud Run Job execution, ODS readiness QA, and synchronous child workflow invocation.
- `ashare_warehouse_window_refresh.yaml`: warehouse window refresh workflow with explicit task-status writes, GCS-backed distributed lock, window DWD/DWS refresh, market-state refresh, daily-current weak dividend event DWD/QA tail steps, and QA chain execution.
- `ashare_pipeline_alert_checker.yaml`: hourly alert-check workflow with parameter normalization and a single authenticated call into `ashare-pipeline-control /v1/tasks/alert-check`.
- `ashare_warehouse_full_rebuild.yaml`: manual full rebuild workflow with explicit confirmation gate, shared warehouse-write lock, async BigQuery submit+poll execution, full DIM/DWD/DWS rebuild order, metadata refresh, and QA chain execution.
- `Dockerfile.pipeline_control`: thin Cloud Run control-plane adapter image that executes bundled SQL, writes `pipeline_run` / `pipeline_task_status`, and manages orchestration leases.
- `deploy_pipeline_control_service.sh`: build and deploy the control-plane Cloud Run service.
- `deploy_workflows.sh`: deploy the three production-ready workflows after substituting the control-service URL; `ashare_warehouse_full_rebuild` is opt-in only via `DEPLOY_FULL_REBUILD=true`.
- `bootstrap_scheduler_iam.sh`: idempotently restore the scheduler caller and workflows runtime IAM needed for the Composer-free production path, including job-level `run.jobsExecutorWithOverrides` for the ODS ingestion Cloud Run Job and project-level Cloud Run viewer access for operation polling.
- `deploy_scheduler_jobs.sh`: create or update the hourly alert-checker Scheduler job and the daily ODS production Scheduler job, both through the Workflows Executions API.
- `cutover_scheduler_jobs.sh`: bootstrap IAM, create Scheduler jobs in `PAUSED` state, pause the Composer business DAGs, and only resume the Scheduler jobs after an explicit validation step.

Also included in this PR:
- `ashare-pipeline-control` alert-check endpoint that reuses `scripts/alerting/check_alerts.py`
- hourly alert-check scheduling target (`0 * * * *`) for the non-Composer path via `Cloud Scheduler -> Workflows -> ashare-pipeline-control`
- daily ODS production scheduling target (`0 20 * * *`, `Asia/Shanghai`) via `Cloud Scheduler -> ashare_ods_ingestion_daily -> child ashare_warehouse_window_refresh`
- alert-check workflow intentionally does not write `ashare_meta.pipeline_run` / `pipeline_task_status`, to avoid self-referential alerts and observability-table pollution

Not included in this PR:
- production scheduling of `ashare_warehouse_full_rebuild`
- deleting the Composer environment itself

Design boundary:
- Workflows remains the orchestrator.
- BigQuery remains the execution engine for SQL tasks.
- Cloud Run Job `ashare-ingest-current-scope` remains the execution engine for ODS ingestion.
- `ashare-pipeline-control` is a thin adapter for status writeback, SQL execution, SSE gate queries, and distributed lock management. It is not a general custom orchestrator.
- `ashare_pipeline_alert_checker` is the exception to workflow-level state writeback: it relies on Workflows execution status plus Cloud Logging heartbeat/absence alerting, and intentionally does not write `pipeline_run` / `pipeline_task_status`.
- There is deliberately no standalone daily Scheduler job for `ashare_warehouse_window_refresh`; the production daily path remains a synchronous child workflow of `ashare_ods_ingestion_daily`, so there is still only one production scheduler entrypoint for write traffic.
- In `daily_current`, `ashare_warehouse_window_refresh` runs `sql/dwd/12_dwd_stock_dividend_event.sql` and `sql/qa/14_corporate_action_event_checks.sql` after the price / market-state window chain. These two tasks are weak and local-non-blocking: failure writes failed task status for `task_failure` alerting but does not rethrow or fail the main pipeline run. `backfill` and `qa_only` do not run these write-side event tasks.
- `ashare_warehouse_full_rebuild` polls BigQuery through the control service; each `get_job(...)` poll can block a Cloud Run worker for up to about 15 seconds of backoff (`1+2+4+8`) before surfacing a terminal poll failure back into `pipeline_task_status`. That is acceptable for this thin adapter, but it is an explicit runtime constraint, not “free” behavior.

Deploy order:
1. Deploy `ashare-pipeline-control`
2. Grant the workflow runtime service account access to:
   - invoke the control service
   - run `ashare-ingest-current-scope` with overrides
   - read Cloud Run operation status while polling the ingestion execution
   - execute child workflows
   - query BigQuery and write `ashare_meta`
   - read/write the orchestration lock bucket
3. Deploy the three production-ready workflows
4. Leave `ashare_warehouse_full_rebuild` undeployed by default; deploy it with `DEPLOY_FULL_REBUILD=true` when you want the manual workflow available in the target project
5. Run `bootstrap_scheduler_iam.sh` so the dedicated Scheduler caller service account has `roles/workflows.invoker`, and the workflows runtime bindings are restored idempotently
6. Deploy the Scheduler jobs for `ashare_pipeline_alert_checker` and `ashare_ods_ingestion_daily` in `PAUSED` state
7. Pause the Composer business DAGs before any Scheduler job is resumed
8. Verify one real fire for the paused Scheduler path, then resume the Scheduler jobs so the production write path has exactly one active scheduler entrypoint

Example:
```bash
cd orchestration/workflows
./deploy_pipeline_control_service.sh
PIPELINE_CONTROL_URL="https://ashare-pipeline-control-xxxxx-uc.a.run.app" ./deploy_workflows.sh
# Optional only after full rebuild is production-ready:
# DEPLOY_FULL_REBUILD=true PIPELINE_CONTROL_URL="https://ashare-pipeline-control-xxxxx-uc.a.run.app" ./deploy_workflows.sh
./bootstrap_scheduler_iam.sh
ENABLE_JOBS=false ./deploy_scheduler_jobs.sh
# Real cutover helper stages jobs as paused by default:
# ./cutover_scheduler_jobs.sh
# After a successful manual fire:
# RESUME_SCHEDULER_JOBS=true ./cutover_scheduler_jobs.sh
```

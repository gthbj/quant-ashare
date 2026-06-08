# Workflows migration scaffolding

This directory contains the first implementation slice of the Composer exit plan.

Included in this PR:
- `ashare_ods_ingestion_daily.yaml`: ODS daily ingestion workflow with explicit task-status writes, SSE non-trading-day gate support, Cloud Run Job execution, ODS readiness QA, and synchronous child workflow invocation.
- `ashare_warehouse_window_refresh.yaml`: warehouse window refresh workflow with explicit task-status writes, GCS-backed distributed lock, window DWD/DWS refresh, market-state refresh, and QA chain execution.
- `Dockerfile.pipeline_control`: thin Cloud Run control-plane adapter image that executes bundled SQL, writes `pipeline_run` / `pipeline_task_status`, and manages orchestration leases.
- `deploy_pipeline_control_service.sh`: build and deploy the control-plane Cloud Run service.
- `deploy_workflows.sh`: deploy the two workflows after substituting the control-service URL.

Not included in this PR:
- `ashare_warehouse_full_rebuild` workflow migration
- `ashare_pipeline_alert_checker` migration off Composer
- Cloud Scheduler jobs / IAM bootstrap / production cutover scripts

Design boundary:
- Workflows remains the orchestrator.
- BigQuery remains the execution engine for SQL tasks.
- Cloud Run Job `ashare-ingest-current-scope` remains the execution engine for ODS ingestion.
- `ashare-pipeline-control` is a thin adapter for status writeback, SQL execution, SSE gate queries, and distributed lock management. It is not a general custom orchestrator.

Deploy order:
1. Deploy `ashare-pipeline-control`
2. Grant the workflow runtime service account access to:
   - invoke the control service
   - run `ashare-ingest-current-scope`
   - execute child workflows
   - query BigQuery and write `ashare_meta`
   - read/write the orchestration lock bucket
3. Deploy the workflows
4. Add Cloud Scheduler or other production triggers in a later PR

Example:
```bash
cd orchestration/workflows
./deploy_pipeline_control_service.sh
PIPELINE_CONTROL_URL="https://ashare-pipeline-control-xxxxx-uc.a.run.app" ./deploy_workflows.sh
```

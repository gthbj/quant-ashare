> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #150 已合并到 `main`；D3/E main 镜像已构建并部署到五个 Strategy1 jobs，digest `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2`。
> - 五个现有 jobs 的 `--help` boot smoke 全部成功：`train-predict-job-rrjmf`、`prepare-matrix-job-7bgfl`、`train-candidate-fanout-job-jtw78`、`select-register-predict-job-p88c9`、`backtest-report-job-glntc`。
> - 分支 `codex/package-entrypoints` 已为五个 jobs 建立 `quant_ashare.strategy1.*` package entrypoint，并用 pytest 覆盖旧/新入口 `--help` 与关键 dry-run parity；PR #153 review follow-up 已补 wrapper alias 注释和 cutover 范围约束；本轮不改线上 job command。
> - 新建专用 promotion SA `strategy1-promotion-runner@data-aquarium.iam.gserviceaccount.com` 与 Cloud Run job `strategy1-promote-research-to-ads-job`；help smoke `...-6kqd7` 与完整参数 review-only dry-run `...-4mkrv` 成功。
> - Dry-run promotion smoke 未写 manifest：`promo_deploy_smoke_20260610_01` 在 `research_promotion_manifest` 行数为 `0`；`sql/research/03_qa_research_schema_readiness.sql` 7 条断言通过。
> - Owner 已选择 OQ-013 方案 1：接受普通 runner compute SA 暂保留 `ashare_ads` WRITER，但保留流程约束；OQ-013 已关闭归档，未改线上 IAM。
> - 尚未执行真实 owner-approved promotion；后续必须 owner 指定 accepted research run 后，按 runbook 先 review-only 再带 `--execute`。

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 五个 Strategy1 Cloud Run package entrypoint

### 已完成工作

- 新增五个稳定 package entrypoint：`quant_ashare.strategy1.train_predict`、`quant_ashare.strategy1.prepare_matrix`、`quant_ashare.strategy1.train_candidate_task`、`quant_ashare.strategy1.select_register_predict`、`quant_ashare.strategy1.backtest_report`。
- 将旧 `scripts.strategy1_cloudrun.train_predict`、`prepare_matrix`、`train_candidate_task`、`select_register_predict`、`backtest_report` 缩为兼容 wrapper；普通 import 下 alias 到 package 实现模块，CLI 运行仍调用同一 `main()`。
- PR #153 review follow-up 已给五个 wrapper 的 `sys.modules[__name__] = _impl` alias 加注释，明确这是 legacy import / monkeypatch 兼容关键路径。
- 新增 `tests/strategy1/test_cloudrun_package_entrypoints.py`，覆盖五个旧/新入口 `--help` 输出一致和关键 `--dry-run` JSON plan 一致。
- 扩展 `tests/strategy1/test_package_boundaries.py` 的 package import smoke 与 wrapper alias 检查。

### 重要上下文

- 本轮是代码入口准备，不修改正式 Cloud Run Job command，不构建镜像，不部署线上 jobs，不删除旧 wrapper。
- 线上五个 jobs 仍通过 `scripts.strategy1_cloudrun.*` command 启动；后续迁到 `quant_ashare.strategy1.*` 必须单独 PR、构建镜像并做五 job boot smoke。
- Cutover PR 范围不能只改 job spec；还必须同步 orchestrator / pipeline-control / native search / annual rolling 的 Cloud Run override args、catalog `caller` 字段和 active runbook / 示例命令。删除旧 wrapper 前，active scopes 内五个旧模块路径 grep 必须为 0，并应把旧模块路径纳入 retired-reference linter 防回流。

### 改动文件

- `src/quant_ashare/strategy1/train_predict.py`
- `src/quant_ashare/strategy1/prepare_matrix.py`
- `src/quant_ashare/strategy1/train_candidate_task.py`
- `src/quant_ashare/strategy1/select_register_predict.py`
- `src/quant_ashare/strategy1/backtest_report.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/train_candidate_task.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 手工五入口 old/new `--help` smoke：通过。
- 手工五入口 old/new 关键 `--dry-run` JSON plan parity：通过。
- `python3 -m pytest -q tests/strategy1/test_package_boundaries.py tests/strategy1/test_cloudrun_package_entrypoints.py tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1_cloudrun/test_dynamic_cv_folds.py`：35 passed。
- `python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun`：87 passed。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无代码阻塞。生产 job command 尚未迁移。

### 下一步建议

- 合并代码入口 PR 后，单独构建 main 镜像，把五个正式 Cloud Run jobs 的 command args、override args、catalog caller 和 active runbook / 示例命令迁到 `quant_ashare.strategy1.*`，并跑五 job boot smoke。
- 旧 wrapper 只能在正式 job command 迁移且 smoke 通过后再考虑删除。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - OQ-013 IAM 收敛决策记录

### 已完成工作

- 记录 owner 对 OQ-013 的选择：采用方案 1，接受现状但保留流程约束。
- 将 `TODO.md` 中 OQ-013 勾选完成。
- 将 OQ-013 从 `OPEN_QUESTIONS.md` 移出并归档到 `archive/CLOSED_QUESTIONS.md`。
- 追加 `DECISION-20260610-12`，明确普通 runner compute SA 暂保留 `ashare_ads` WRITER，但普通新实验不得以 ADS 为默认写入路径。
- 更新 `KNOWN_CONSTRAINTS.md` 和 `IMPLEMENTATION_STATUS.md`，说明本轮不修改线上 IAM。

### 重要上下文

- 本决策不改变 D2/D3 的流程边界：普通实验默认 research-first，ADS 正式发布只走 owner-approved promotion job。
- 显式 `--output-dataset-role ads` / `dataset_role="ads"` 仅保留为历史 ADS audit / 兼容路径。
- 后续若要做 IAM 硬隔离，需要新的 owner 决策，并先设计 ADS audit / 历史报告重渲染替代路径。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 本轮为文档 / 记忆决策记录；未改代码、SQL、BigQuery、Cloud Run 或 IAM。

### 阻塞项

- 无。

### 下一步建议

- 继续按 promotion runbook 等待 owner 指定 accepted research run 后执行首次真实 promotion。
- Cloud Run entrypoint 从 wrapper 迁到 package module 仍需单独 PR 和镜像 smoke。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - PR #151 review follow-up IAM 收敛留痕

### 已完成工作

- 复核 PR #151 review 指出的 IAM 收敛缺口：五个普通 Strategy1 runner jobs 仍使用 `241358486859-compute@developer.gserviceaccount.com`。
- 复核 `ashare_ads` dataset access，确认该 compute SA 仍具备 WRITER；promotion 专用 SA 也具备 WRITER。
- 新增 OQ-013 / TODO，记录普通 runner ADS 写权限的 owner 决策点：接受现状、收回并为 ADS audit 特批、或按表级 / 专用 SA 收窄。
- 更新 `KNOWN_CONSTRAINTS.md`，明确在 OQ-013 决策前不要直接 revoke 普通 runner ADS 写权限，避免破坏 ADS audit / 历史报告重渲染回写路径。

### 重要上下文

- 本轮没有修改线上 IAM、Cloud Run job spec、BigQuery table 或 dataset。
- 当前流程边界仍成立：普通实验默认 research-first，正式发布 ADS 必须走 owner-approved promotion job；但 IAM 层硬隔离尚未闭合。

### 改动文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- `gcloud run jobs describe` 确认五个普通 Strategy1 runner jobs 的 service account 均为 `241358486859-compute@developer.gserviceaccount.com`。
- `bq show --format=json data-aquarium:ashare_ads` 确认 `241358486859-compute@developer.gserviceaccount.com` 仍有 WRITER access。

### 阻塞项

- OQ-013 需要 owner 决策后才能调整 live IAM。

### 下一步建议

- 在 owner 选择 IAM 收敛方案前，不要直接 revoke 普通 runner 的 `ashare_ads` 写权限。
- 若选择收窄权限，先设计 ADS audit / 历史报告重渲染的特批路径，再执行 live IAM 变更和 smoke。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - D3/E main 镜像部署与 promotion job dry-run

### 已完成工作

- 从 `origin/main` merge commit `f421c83c1987d5f8eb067991e9d4f6624206306a` 创建 detached 部署 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-d3e-main-deploy`。
- 构建正式 Strategy1 runner 镜像 `research-d3e-main-f421c83-20260610-01`；Cloud Build id `e6b385e7-c386-40be-8adb-e00fc48045c1`，digest `sha256:fdb61f8141e240c377b3faaa21b5e6efef9c783ebb9e04923ff3b675b8d54bc2`。
- 将五个现有 Strategy1 jobs 更新到该 digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 新建 promotion 专用 service account `strategy1-promotion-runner@data-aquarium.iam.gserviceaccount.com`，授予 project `roles/bigquery.jobUser`，以及 `ashare_research` / `ashare_ads` dataset WRITER。
- 新建 promotion 专用 Cloud Run job `strategy1-promote-research-to-ads-job`，使用同一 digest，command 为 `python -m scripts.strategy1.promote_research_to_ads`，SA 为 `strategy1-promotion-runner@data-aquarium.iam.gserviceaccount.com`。

### 重要上下文

- 普通五个 Strategy1 runner jobs 仍使用原 compute SA 和旧 wrapper command；本轮只更新 image digest，没有迁移 Cloud Run entrypoint。
- Promotion job 已部署但只做 review-only dry-run，没有执行真实 promotion，没有写 ADS，也没有写 manifest。
- 真实 promotion 仍必须由 owner 指定 accepted research run/backtest/model 和 approval metadata 后，按 runbook 先 review-only，再显式加 `--execute`。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 本地 targeted tests：`python3 -m pytest -q tests/strategy1/test_promotion.py tests/strategy1/test_package_boundaries.py tests/strategy1_cloudrun/test_dataset_role_routing.py`，29 passed。
- `python3 -m compileall -q src scripts`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- 五个 existing jobs `--help` boot smoke 成功：`strategy1-train-predict-job-rrjmf`、`strategy1-prepare-matrix-job-7bgfl`、`strategy1-train-candidate-fanout-job-jtw78`、`strategy1-select-register-predict-job-p88c9`、`strategy1-backtest-report-job-glntc`。
- Promotion job `--help` boot smoke：`strategy1-promote-research-to-ads-job-6kqd7` succeeded。
- Promotion job 完整参数 review-only dry-run：`strategy1-promote-research-to-ads-job-4mkrv` succeeded，日志包含 review-only 提示。
- BigQuery 反向确认：`research_promotion_manifest` 中 `promotion_id='promo_deploy_smoke_20260610_01'` 行数为 `0`。
- `bq query --project_id=data-aquarium --location=asia-east2 --use_legacy_sql=false < sql/research/03_qa_research_schema_readiness.sql`：7 条断言全部 successful。

### 阻塞项

- 无部署阻塞。真实 promotion 仍待 owner 指定具体 accepted research source 和 approval。

### 下一步建议

- 若需要首次真实 promotion，先用 `strategy1-promote-research-to-ads-job` 对 owner 指定 run 跑 review-only dry-run，确认 SQL/target tables/window 后再加 `--execute`。
- Cloud Run entrypoint 从 `scripts.strategy1_cloudrun.*` 迁到 package module 仍需单独 PR 和镜像 smoke。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - PR #150 review follow-up

### 已完成工作

- 修复 `--allow-unaccepted` 路径下 promotion 伪造验收状态的问题：registry / summary / 普通 research 输出只写 promotion lifecycle 字段，不再写 `acceptance_status='accepted'` 或 `research_status='accepted'`。
- 为 source backtest trade / NAV 增加 promotion window 外行数为 0 的 ASSERT，并检查 summary `start_date` / `end_date` 被本次 promotion window 完整覆盖。
- 将 promotion CLI 改为默认 review-only；真实写 ADS / manifest 必须显式传 `--execute`，单独 `--print-sql` 只打印 plan + SQL。
- 更新 runbook、research README、ARCHITECTURE / KNOWN_CONSTRAINTS / DECISION / TODO，记录失败 attempt 审计方式和 D3/E 同 PR 交付的一次性边界豁免。

### 重要上下文

- Promotion ASSERT 失败会整体回滚，因此不会留下 `research_promotion_manifest` 成功行；失败 attempt 需要查 BigQuery job history 或 Cloud Run execution logs。
- 本轮仍未执行真实 promotion，未部署专用 promotion Cloud Run job，也未迁移 Cloud Run entrypoint。

### 改动文件

- `src/quant_ashare/strategy1/promotion.py`
- `scripts/strategy1/promote_research_to_ads.py`
- `tests/strategy1/test_promotion.py`
- `docs/策略1ResearchPromotion运行手册.md`
- `sql/research/README.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests`：79 passed。
- `python3 -m compileall -q src scripts tests`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：通过，35 actions。
- `git diff --check`：通过。
- `python3 -m scripts.strategy1.promote_research_to_ads ... --dry-run --print-sql`：成功输出 plan + SQL，未执行写入。
- `python3 -m scripts.strategy1.promote_research_to_ads ... --print-sql`：review-only，未执行写入。
- BigQuery client dry-run：`dry_run=True`。
- 程序化 self-review invariant：55 PASS / 0 FAIL。

### 阻塞项

- 无代码阻塞。真实 promotion / promotion Cloud Run job 部署未在本轮执行。

### 下一步建议

- PR #150 合并后如需线上 promotion，基于 main 构建/部署 owner-approved promotion job，或按 runbook 手工先 review-only 再 `--execute`。
- Cloud Run entrypoint 从 `scripts.strategy1_cloudrun.*` 迁到 package module 仍需单独 PR 和镜像 smoke。

### 已更新记忆文件

- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase D3/E promotion 与包化

### 已完成工作

- 新增 D3 promotion package：`src/quant_ashare/strategy1/promotion.py`，生成并执行 owner-approved research-to-ADS BigQuery promotion script。
- 新增 CLI：`scripts/strategy1/promote_research_to_ads.py`，支持 `--dry-run` / `--print-sql`、显式 approval metadata、source run/backtest/model、date window、`--force-replace` 和 `--allow-unaccepted`。
- Promotion 默认复制 publishable outputs：model registry、prediction、candidate、portfolio target、order plan、backtest trade/position/NAV/ledger state/summary、signal monitor；training panel 默认不复制，只能显式 opt-in。
- Promotion SQL 默认要求 accepted research，ADS 目标已有行时 fail-fast，成功后更新 research lifecycle 并写 `research_promotion_manifest`。
- Phase E 包化：把 `acceptance`、`ledger`、`backtest_report`、`orchestrate_experiments` 实现迁入 `src/quant_ashare/strategy1/{acceptance,ledger,reporting,pipeline_control}.py`；旧 `scripts.strategy1_cloudrun.*` 文件只保留兼容 wrapper。
- Dataset role helper 迁入 `src/quant_ashare/strategy1/dataset_roles.py`；旧 `scripts.strategy1_cloudrun.dataset_roles` re-export package API。
- 新增 `src/quant_ashare/strategy1/legacy_names.py`，并把 retired-reference linter active scope 扩展到 `src/**`。
- 新增 `docs/策略1ResearchPromotion运行手册.md`，更新 `sql/research/README.md`。

### 重要上下文

- 本轮没有执行真实 promotion，没有部署专用 promotion Cloud Run job，也没有迁移 Cloud Run job command；旧 `python -m scripts.strategy1_cloudrun.backtest_report` 和 `python -m scripts.strategy1_cloudrun.orchestrate_experiments` 仍是兼容入口。
- 上线 promotion 前，应给 owner-approved promotion identity 配置 research 读写、ADS 写和 manifest 写权限；普通 experiment runner 不应因此获得常规 ADS 写权限。
- `accepted != promoted` 仍是硬边界；`--allow-unaccepted` 只是显式 owner override 开关，默认关闭。

### 改动文件

- `src/quant_ashare/strategy1/promotion.py`
- `scripts/strategy1/promote_research_to_ads.py`
- `src/quant_ashare/strategy1/dataset_roles.py`
- `src/quant_ashare/strategy1/{acceptance,ledger,reporting,pipeline_control,legacy_names}.py`
- `scripts/strategy1_cloudrun/{dataset_roles,acceptance,ledger,backtest_report,orchestrate_experiments}.py`
- `configs/strategy1/active_step_catalog.yml`
- `tests/strategy1/test_promotion.py`
- `tests/strategy1/test_package_boundaries.py`
- `tests/strategy1/test_retired_lint.py`
- `docs/策略1ResearchPromotion运行手册.md`
- `sql/research/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests`：77 passed。
- `python3 -m compileall -q src scripts tests`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：通过，35 actions。
- `git diff --check`：通过。
- `python3 -m scripts.strategy1.promote_research_to_ads ... --dry-run`：成功输出 promotion plan。
- BigQuery client dry-run 对 generated promotion script 返回 `dry_run=True`。
- 旧 wrapper help smoke：`python3 -m scripts.strategy1_cloudrun.backtest_report --help`、`python3 -m scripts.strategy1_cloudrun.orchestrate_experiments --help`、`python3 -m scripts.strategy1.promote_research_to_ads --help` 均可启动。
- 41 条程序化 self-review invariant 全部 PASS。

### 阻塞项

- 无代码阻塞。真实 promotion / promotion Cloud Run job 部署未在本轮执行。

### 下一步建议

- 开 PR review；合并后如需线上 promotion，基于 main 构建/部署 owner-approved promotion job，或按 `docs/策略1ResearchPromotion运行手册.md` 手工执行一次 accepted research promotion dry-run 后再 execute。
- Cloud Run entrypoint 从 `scripts.strategy1_cloudrun.*` 迁到 package module 仍需单独 PR 和镜像 smoke。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase D2 main 镜像部署与默认 research smoke

### 已完成工作

- 合并 PR #148 到 `main`，merge commit `13bf0b512b5def2b2ef51c42e504f439f87a4dcf`。
- 从合并后的 `origin/main` 在独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-d2-main-deploy` 构建正式 Strategy1 runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:research-d2-main-13bf0b5-20260610-01`。
- Cloud Build `e874d1bf-faad-4262-bacd-33cf01551425` 成功，immutable digest 为 `sha256:92c348536776cbcd8fb4f09def63509f0f1dfdf2f13f54d472dc078582b410f0`。
- 已把五个 Strategy1 Cloud Run jobs 更新到该 digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 读回 job spec，确认 image、service account、command/args、CPU/memory、taskCount/parallelism 保持预期。
- 跑通只读 boot smoke `strategy1-backtest-report-job-7g2mj`；入口 args 未传 `--output-dataset-role`，stdout plan 显示默认 `output_dataset_role=research`。
- 跑通真实默认 research-first smoke `strategy1-backtest-report-job-2xr6f`，run/backtest 为 `s1_default_research_d2_smoke_20260610_03` / `bt_s1_default_research_d2_smoke_20260610_03`，复用 D1 research prediction run `s1_sklearn_native_research_d1_smoke_20260610_04__l2_c_0_1` 的连续 2025H1 窗口。

### 重要上下文

- 真实 smoke 未传 `--output-dataset-role`；Cloud Run entrypoint 使用 main 镜像默认配置进入 `research`。
- `_01` smoke 跨了 D1 prediction 的不连续 2024H1 + 2025H1 窗口，触发 `QA-EXP-4`；`_02` 的 valid 窗口仍覆盖未预测的 2024H2，触发 `QA-POOL-5`。最终 `_03` 将 valid/test 与 D1 prediction 实际覆盖段对齐后成功。
- 本轮只完成 D2 部署与验收，不实现 promotion，不把 research run 自动复制到 ADS。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `sql/strategy1/README.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build 成功：build id `e874d1bf-faad-4262-bacd-33cf01551425`，digest `sha256:92c348536776cbcd8fb4f09def63509f0f1dfdf2f13f54d472dc078582b410f0`。
- 五个 Cloud Run jobs spec 读回通过：image、SA、command/args、resources、taskCount/parallelism 均符合预期。
- Boot smoke `strategy1-backtest-report-job-7g2mj` succeeded，未传 `--output-dataset-role` 时默认 plan 为 `research`。
- Default research-first smoke `strategy1-backtest-report-job-2xr6f` succeeded，耗时约 `3m22s`；日志中 `build_candidates`、`build_portfolio_targets`、`build_order_plan`、`build_metrics_and_report_inputs`、`qa_runner_outputs`、`qa_lot_aware_ledger_outputs`、`qa_model_diagnosis_outputs`、`qa_tail_risk_outputs` 均记录 `dataset_role=research`。
- BigQuery 验收：research candidate `61,620`、target `135`、order `157`、trade `203`、position `570`、NAV `117`、ledger state `117`、summary `1`、signal monitor `117`；ADS candidate/target/order/trade/NAV/summary 同 run/backtest 均为 `0`。
- `bq query --project_id=data-aquarium --use_legacy_sql=false < sql/research/03_qa_research_schema_readiness.sql` 通过，7 条 assertion successful。

### 阻塞项

- 无。

### 下一步建议

- 继续单独实现 PRD Phase D3 owner-approved promotion job；promotion 前不得让普通 research run 隐式写 ADS。
- Phase E 包化时收敛读侧 routing 模块级全局态。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase D2 default research-first

### 已完成工作

- 将 Strategy1 默认 `output_dataset_role` 从 `ads` 切为 `research`。
- 更新 `RunnerConfig`、默认 Cloud Run 配置、年度滚动配置、SQL runner、report、model diagnosis、tail-risk、acceptance v2/window/v3 replay、comparison 和 factor attribution 的默认 role。
- 更新 `configs/strategy1/active_step_catalog.yml`：`current_dataset_role=research`、`previous_dataset_role=ads`、`research.enabled_by_default=true`，并把 step 级 `output_dataset_role_current` 同步为 `research`。
- `resolve_table_role()` 与 SQL render 的裸默认现在跟随 catalog 当前 role；显式 `dataset_role="ads"` 保留 ADS / meta status 回放路径。
- Cloud Run command helper 改为始终显式下发 `--output-dataset-role=research|ads`，candidate fanout task 也显式下发 role，避免子 job 在镜像滚动更新期间继承错误默认值。

### 重要上下文

- 本轮只做 D2 default research-first，不实现 owner-approved promotion job，不把普通 runner 隐式写 ADS。
- PR 合并后仍需从 merge/main commit 重建正式 runner 镜像并更新五个 Strategy1 Cloud Run jobs；当前生产 jobs 仍跑 PR #147 后部署的 main 镜像。
- D3 需单独实现 promotion manifest / ADS copy；Phase E 仍需收敛读侧 routing 模块级全局态。

### 改动文件

- `configs/strategy1/active_step_catalog.yml`
- `configs/strategy1/cloudrun_runner_default.yml`
- `configs/strategy1/annual_rolling_lgbm_regression_v0.yml`
- `src/quant_ashare/strategy1/sql_render.py`
- `src/quant_ashare/strategy1/table_roles.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/dataset_roles.py`
- `scripts/strategy1_cloudrun/sql_runner.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1_cloudrun/state.py`
- `scripts/strategy1/*.py` 相关 report / diagnosis / acceptance / comparison 脚本
- `tests/strategy1/**`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `sql/research/README.md`
- `sql/strategy1/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests` -> 69 passed（Python / SSL environment warnings only）。
- `python3 -m pytest -q tests/strategy1_cloudrun/test_dataset_role_routing.py` -> 19 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过。
- `npx --yes @dataform/cli compile dataform` 通过。
- `python3 -m compileall -q src scripts/strategy1 scripts/strategy1_cloudrun` 通过。
- `git diff --check` 通过。
- Programmatic smoke / self-review 42 条 invariant 全部通过：覆盖默认 research、显式 ADS fallback、candidate fanout 显式 role flag、catalog current role、renderer 默认、测试覆盖、文档、TODO 和记忆状态。
- 普通 orchestrator、sklearn native search、annual rolling dry-run 共 9 条 `train_candidate_task` 命令均显式包含 `--output-dataset-role=research`。
- Live BigQuery `bq query --use_legacy_sql=false --location=asia-east2 < sql/research/03_qa_research_schema_readiness.sql` 通过，7 条 `QA-RESEARCH-SCHEMA-*` assertion successful。

### 阻塞项

- 无代码阻塞；PR #148 已创建为 draft，待 review 后再转正式 / 合并。

### 下一步建议

- PR review 通过后再转正式 / 合并。
- PR 合并后从 merge/main commit 重建正式 runner 镜像并更新五个 Strategy1 Cloud Run jobs。
- D3 promotion job 和 Phase E 包化继续单独 PR。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase D1 收尾 research smoke

### 已完成工作

- 部署 `sql/00_create_datasets.sql` 与 `sql/research/01_research_strategy1_tables.sql`，确认 `ashare_research` 15 张表存在。
- 给 runtime service account `241358486859-compute@developer.gserviceaccount.com` 补 `ashare_research` dataset 写权限。
- 修复 D1 smoke 暴露的运行问题：`research_experiment_run_status.log_dir` 缺列、search QA 参数缺 `p_strategy_id`、heartbeat 覆盖 terminal status、`QA-POOL-5` 把 valid/test gap 算入 DWS legacy 行数、research registry 显式契约列未写出。
- 重建并部署 Strategy1 Cloud Run jobs 到 D1 smoke 镜像 digest `sha256:7ef5601980f1b202654b504a52c96e33c09f95d009ebdcf455b002e4913571f9`。
- 跑通显式 research-mode smoke `sklearn_native_research_d1_smoke_20260610_04`，覆盖 prepare、5 候选 fanout、select/register/predict、Top-1 backtest/report、diagnosis、tail-risk、acceptance patch 和 search-level QA。

### 重要上下文

- 本轮只验证显式 `--output-dataset-role=research`，没有切 default research-first，也没有实现 promotion。
- Research 验收行数：training panel `2,742,853`、prediction `502,501`、candidate `61,620`、target `135`、order `157`、trade `203`、position `570`、NAV `117`、ledger state `117`、summary `1`、registry `1`；lifecycle bad count 全部为 `0`。
- ADS 污染检查同一 run/backtest 在 ADS run-scoped 表均为 `0` 行。
- 当前五个 Strategy1 Cloud Run jobs 指向 D1 smoke 验证镜像；正式 PR 合并后应以 merge/main commit 重建并部署 runner 镜像，避免长期运行未合并分支镜像。
- PR #146 review Low follow-up 已登记到 TODO：D2 default research-first 前补 research additive migration 约定和 research schema/readiness QA；`QA-POOL-5` 双窗口修复对 ADS 模式同样生效，未来复跑历史组合时 QA 结论可能翻转。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `sql/research/01_research_strategy1_tables.sql`
- `sql/strategy1/qa/qa_model_diagnosis_outputs.sql`
- `tests/strategy1/test_research_contract.py`
- `tests/strategy1/test_sql_render.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests` -> 63 passed（4 个 Python / SSL 环境 warning）。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过。
- `npx --yes @dataform/cli compile dataform` 通过。
- `python3 -m compileall scripts/strategy1_cloudrun/orchestrate_experiments.py scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py scripts/strategy1_cloudrun/train_predict.py sql src` 通过。
- `git diff --check` 通过。
- BigQuery / Cloud Run research-mode smoke `sklearn_native_research_d1_smoke_20260610_04` 通过，ADS 污染检查为 0。

### 阻塞项

- 无代码阻塞；尚未 commit / push / open PR。

### 下一步建议

- 提 PR 前复核 diff 并提交。
- 合并后用 merge/main commit 重建正式 runner 镜像并更新五个 Strategy1 Cloud Run jobs。
- D1 合并后再进入 D2 default research-first 或 D3 owner-approved promotion job。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - Strategy1 年度滚动执行 P0 工程骨架

### 已完成工作

- 新增 `sql/ads/03_create_strategy1_backtest_ledger_state_daily.sql`，用 additive `CREATE TABLE IF NOT EXISTS` 补齐 Cloud Run ledger resume state 表。
- 新增 `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`，检查 Cloud Run backtest/report 所需 ADS 表、字段类型、分区和 `backtest_id` clustering。
- 在 `configs/strategy1/active_step_catalog.yml` 注册 `qa_cloudrun_schema_readiness`，并声明其 ADS role 覆盖。
- 新增 `configs/strategy1/annual_rolling_lgbm_regression_v0.yml`，固定 PRD_03 的 11 个 LightGBM regression 候选。
- 新增 `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`，生成年度 resolved experiment payload、matrix URI、Cloud Run command plan、B26 diagnostic-only reference 标记和连续 ledger backtest id。
- Review follow-up：`subtract_weekdays` 明确限制为 12 月年末 label window，新增 ledger state DDL 漂移测试，并在 D1 TODO 标注 research readiness 缺口。

### 重要上下文

- 本实现只覆盖 PRD_04 的 P0 工程骨架和 dry-run / resolved plan，不启动 Cloud Run。
- 非 dry-run 现在 fail-fast；完整 live annual rolling 仍需要先跑 readiness QA 和 dry-run，再按 owner 指令执行。
- continuous ledger 结果仍必须来自单条连续 ledger 或已验收 resume-continuous segment，不能拼接 yearly fresh-run NAV。

### 改动文件

- `sql/ads/03_create_strategy1_backtest_ledger_state_daily.sql`
- `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`
- `configs/strategy1/annual_rolling_lgbm_regression_v0.yml`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `configs/strategy1/active_step_catalog.yml`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest tests` 58 passed（4 个 Python / SSL 环境 warning）。
- 未运行 BigQuery、Cloud Run 或 Dataform。

### 阻塞项

- 无代码阻塞；live 执行前需要 owner 明确允许运行 readiness QA / dry-run / Cloud Run smoke。

### 下一步建议

- 先跑 `qa_cloudrun_schema_readiness`。
- 再跑 `orchestrate_annual_rolling_selection.py --dry-run` 审核 resolved payload 和 command plan。
- 若 dry-run 正常，再执行 2021 单年 smoke 或完整 2021-2026 年度链路。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`。
> - PRD 把 2021 smoke 暴露的三个工程问题转成后续实现要求：annual rolling orchestrator 自动生成 resolved experiment payload、ADS additive migration、Cloud Run schema readiness QA。
> - PRD 明确 P0 不改模型、不扩参数、不调 v3 gate、不切 `ashare_research`；完整 `2021-2026` 正式结果必须来自单一 continuous ledger，或通过 resume-continuous QA 的 segment ledger，禁止拼年度 fresh-run。
> - PR #144 review follow-up 已处理：`biweekly` 口径、既有 `02` migration 关系、无数字前缀 QA + catalog step、过渡 namespace 和 B26 diagnostic-only reference 均已补齐。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #141 已合并，正式 Strategy1 Cloud Run runner 已构建并部署到镜像 `strategy1-cloudrun-runner:2565e0f`。
> - 2021 annual-selection smoke 已在正式 jobs 上闭环：candidate fanout `5f6qg`、select/register/predict `pxtbw`、backtest/report `t5fg6` 均 succeeded。
> - CV 修复实证：11 个候选全部 `cv_confirmation_status=passed`、`cv_fold_count=3`，fold 为 `cv_2018/cv_2019/cv_2020`；选中候选为 `risk_lgbm_prd_strong_regularized_l5_l63_lr002_n300_leaf800_ff07_bf10`。
> - 本次手工补齐生产 ADS additive schema：创建 `ads_backtest_ledger_state_daily`，并为 `ads_backtest_performance_summary` 补 4 个复合年化字段。2021 回测结果为 total_return -8.08%、compound annual -8.39%、Sharpe -0.382、MaxDD -19.54%、vs `000001.SH` excess -12.88%。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/strategy1-research-routing-d1b` 已处理 PR #143 review follow-up：默认 ADS 子命令不下发 `--output-dataset-role=ads`，保持旧 Cloud Run 镜像兼容；显式 research 仍下发 role flag。
> - Research contract 已补 lifecycle 默认值：普通 research 输出默认 `research_status='candidate'`、`promotion_status='not_promoted'`，`research_promotion_manifest.promotion_status` 默认 `planned`。
> - D1 真实 research smoke 仍是独立收尾项：部署 D0 DDL、重建镜像、补 runtime SA `ashare_research` 写权限并跑显式 research-mode smoke 后，才能进入 D2 default research-first；读侧 routing 全局态收敛已登记到 Phase E。验证包括 `python3 -m pytest tests` 57 passed、Dataform `--check`、Dataform compile、BigQuery DDL dry-run、主要 CLI help/dry-run、41 条程序化 self-review checks、compileall 和 `git diff --check`。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/strategy1-research-routing-d1a` 已 rebase 到最新 `origin/main`（含 PR #141 dynamic CV fold 修复），并继续用于 PR #142。
> - PR #142 review follow-up 已处理：补全非 retired Strategy1 step 的 catalog `inputs` / `outputs`，使其覆盖 SQL 中实际 `data-aquarium.ashare_ads.*` 引用；新增 pytest 校验 catalog role 覆盖和 research 渲染无 ADS 残留。
> - 验证：`python3 -m pytest tests` 42 passed；Dataform `--check`、Dataform compile、catalog ADS role 覆盖扫描、88 条程序化 self-review checks、compileall 和 `git diff --check` 均通过。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/fix-dynamic-cv-folds` 修复 Strategy1 Cloud Run Python CV fold 硬编码问题：`train_predict.py` 现在基于 `cv_panel` 中 `split_tag='train'` 的年份动态生成最多 3 个 rolling fold，并排除外部 valid 年。
> - 新增 `tests/strategy1_cloudrun/test_dynamic_cv_folds.py` 覆盖年度滚动选参窗口 `2015-2019 -> cv_2017/cv_2018/cv_2019`，以及旧窗口完整边界 `2019-04-03..2023-12-31 -> cv_2021/cv_2022/cv_2023`。
> - 验证：`python3 -m pytest tests` 34 passed。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/strategy1-research-routing-d1a` 已实现项目结构重构 Phase D1a：Strategy1 SQL render 支持按 catalog step 的 `inputs` / `outputs` 做 table role / dataset role 改写。
> - 默认渲染仍是 `data-aquarium.ashare_ads.*`；显式 `dataset_role="research"` 必须传 `allow_future_research=True`，并且只作为 contract / dry-run / 后续 runner 接线验证。本轮不改 Cloud Run 默认写入、不创建或写入 BigQuery `ashare_research`。
> - 已处理共享 ADS 源表歧义：无 step 上下文的全局 research 替换会 fail-fast，避免 `ads_model_registry` 被误替到 `research_acceptance_result`。
> - 验证：`pytest tests` 38 passed、Dataform `--check`、Dataform compile、21 个 catalog step ADS/research 双渲染 smoke、40 条 self-review checks、compileall 和 `git diff --check` 均通过。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/add-research-table-contract` 已实现项目结构重构 Phase D0：新增 `ashare_research` schema contract、`sql/research/01_research_strategy1_tables.sql`、research README 和 catalog contract metadata。
> - D0 只定义 `research_*` 表族、`research_acceptance_result`、`research_experiment_run_status` 与 `research_promotion_manifest`；不部署 BigQuery、不切 runner 默认写入、不迁移历史 ADS、不实现 promotion job。
> - PR #140 review follow-up 已处理：`experiment_run_status` 当前侧通过 `ads_dataset: ashare_meta` 解析到既有 meta 表；`build_order_plan.partition_columns` 已改为 `rebalance_date`；新增测试防止 step/output 分区和 resolver dataset 漂移。
> - 验证：`pytest tests` 32 passed、Dataform `--check`、Dataform compile、BigQuery combined dry-run 和 `git diff --check` 均通过。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - OQ-005 Cloud Run Job IAM bootstrap TODO 已收口：PR #126 已合并到 `main`，`bootstrap_scheduler_iam.sh` 已固化 `roles/run.jobsExecutorWithOverrides`、`roles/run.viewer` 并移除旧 job-level `run.invoker`。
> - 本轮只清理过期状态，勾选 `TODO.md` 对应项并同步 `IMPLEMENTATION_STATUS` / `AGENT_HANDOFF`；未修改 Workflows、IAM bootstrap 脚本、Cloud Run、BigQuery 或生产配置。
> - 验证：复核 PR #126 merge commit `54fe077bb656f23b5ff9384f348e49b7a5259e94`，并确认 `origin/main` 当前 bootstrap 脚本仍包含正确 IAM 绑定。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/fix-dataform-generated-drift` 已修复 Dataform generated SQLX drift：从 canonical `sql/` 与 `dataform/action_manifest.json` 重新生成 6 个 stale `dataform/definitions/**/*.sqlx` 文件。
> - PR review 的 Low 防复发建议已处理：新增 `tests/dataform/test_generated_sqlx.py`，直接调用 `generate_sqlx_from_sql.py --check`，让 pytest 暴露后续 generated SQLX drift。
> - 本轮未修改 canonical `sql/`、manifest、Workflows、Cloud Run 或 BigQuery 执行入口；只同步 generated SQLX、测试和项目记忆/TODO。
> - 验证：`python3 -m pytest tests` 25 passed、`generate_sqlx_from_sql.py --check`、Dataform compile 和 `git diff --check` 均通过。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #136 review follow-up 已处理：retired linter 在 Python 3.11/3.12 下递归扫描 active scope，不再空跑；当时显式 `dataset_role="research"` fail-fast，不再静默降级 ADS。
> - Owner 已确认 PR #136 可一次性合并项目结构重构 Phase A/A2/B/C；该豁免已记录为 `DECISION-20260610-07`，后续 Phase D/E 仍需单独 PR。
> - 已删除 PASS 型 self-review 文档，`sql/strategy1/README.md` 已说明 `audit_only` SQL 同 namespace 但执行状态以 catalog 为准，`TODO.md` 已补 Dataform generated SQLX drift cleanup 项。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 分支 `codex/strategy1-structure-refactor` 已实现项目结构重构 PRD Phase A/B/C：active step catalog、retired linter、table role / dataset role resolver、`src/quant_ashare/**` package foundation、`sql/strategy1/**` active SQL 命名空间。
> - 当时 table role 默认仍解析到 `ashare_ads`；显式 `dataset_role="research"` fail-fast，未创建或写入 `ashare_research`，也未迁移 Cloud Run entrypoint。
> - 验证：pytest 24 passed、catalog validate、retired linter、active step render smoke、compileall、CLI dry-run/help 和 `git diff --check` 均通过；Dataform `--check` 仍因既有 generated SQLX stale/missing 失败，本分支无 `dataform/` diff。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`。
> - PRD 定义年度 walk-forward 参数选择：上一整年 valid 选择参数，选中参数在最近 5 年 final refit，再回测下一年；2021-2026 结果必须用年度预测合并后的一条连续 ledger 评价。
> - P0 固定 feature set、20 只、7.5% 单票上限、biweekly 和 `ledger_exec_v1_lot100`，只搜索 11 个冻结 LightGBM regression 可选候选；B26 binary 只作为 diagnostic-only reference。
> - PR #137 review follow-up 已处理：第 1 点只修理由、不改门；第 2 点修正 label embargo 措辞；第 3 点明确 B26 binary 不参与 `selected_candidate_id`。
> - 本轮只写方案和同步 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/DECISION_LOG.md`、`TODO.md`；未改代码、SQL、BigQuery、Cloud Run 或 Dataform。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260610_02_项目结构重构方案.md`，作为 `quant-ashare` 项目结构重构总 PRD。
> - Owner 已确认关键决策：采用 `ashare_research` dataset、`research_*` 表名前缀、`accepted != promoted`、先 table-role abstraction 后 research-first、`sql/strategy1/**` 目标 SQL 命名空间、`src/quant_ashare/**` Python 包根、短期保留 `scripts/strategy1_cloudrun/**` wrapper，且 P0 不强制创建 `docs/retired/`。
> - PRD 已改为已确认口径；新实验、候选、诊断和 acceptance replay 目标态默认写 research，`ashare_ads` 只承载 owner promotion 后的正式产物。
> - Review 指出的 `sql/cloudrun/strategy1/01_build_training_panel.sql`、ADS 硬编码耦合、retired linter allowlist、SQL `DECLARE p_*` 参数默认值漂移、`optional_params` schema 语义、`16-25` 逐个分类、`bqml_reference_run_id` exception registry 和 Python package 交付方式均已补进 PRD。
> - 本轮只写方案和同步 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/DECISION_LOG.md`、`TODO.md`；未改代码、SQL、BigQuery、Cloud Run 或 Dataform。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #134 已从 PRD-only 扩展为实现分支：新增 Strategy1 回测 `compound_annual_return`、`return_period_count`、`annualization_target_period_count`、`annualization_method` 字段与 ADS additive migration。
> - `09` summary、`10` runner QA、`24` v3 replay QA、`render_report.py` 与 `replay_acceptance_gate_v3.py` 已切到 NAV 首尾值 + NAV 有效交易日数减一的复合年化口径；legacy `annual_return` / `sharpe` 保留旧算术口径并显式标注。
> - PR #134 review follow-up 已修复 `total_return = -100%` 边界：SQL、report 和 v3 replay 统一允许 `gross == 0` 返回复合年化 `-100%`，仅拒绝 `gross < 0`。
> - 未运行 BigQuery / Cloud Run / pytest；后续需要 owner 决定是否部署 schema migration、是否重跑 2020-2022 R14 hold=10/20 报告或生成 sidecar，以及是否调整 compound Sharpe / Calmar 阈值。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #131 分支已完成 Strategy1 旧 BQML / SQL ledger runner P0 退役实现。
> - 已删除 BQML-only `sql/ml/strategy1/02-04`、SQL ledger fallback `08_run_backtest.sql` 和旧 `scripts/strategy1/run_oq010_experiments.py`；Cloud Run Python runner 已移除 `--use-bq-ledger` 参数和透传。
> - 当前 active path 收口为 Cloud Run Python training / prediction / ledger + 共享 SQL `01`、`05-07`、`09-10`、`12`、`16-24`；未运行 BigQuery / Cloud Run / pytest。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #132 已合并，`ashare-pipeline-control` 已重新部署到 revision `ashare-pipeline-control-00007-tst`。
> - 重新触发 2015 年 backfill execution `209bd2bf-86f4-455c-85c7-b6b1f4ec8025`，已越过 `dim_stock` 生命周期缺口。
> - 新失败点在 `sql/qa/01_core_smoke_checks.sql`：旧 core smoke 仍把 `2019-01-01` 当成 DWD 价格表全表存在下限；分支 `codex/fix-historical-backfill-core-smoke` 已改为只拒绝早于 `1990-12-19` 的异常行，`daily_current` 2019+ 下限继续由窗口 SQL/QA 约束。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #130 合并并部署 `ashare-pipeline-control` 后，重跑 2015 年 backfill execution `be12a12f-1e65-4cef-b60d-3945ef8da13a`，已越过指数窗口旧失败点。
> - 新失败点在股票窗口 QA `QA-WIN-13`：2015 ODS daily 有 `5,486` 行、`76` 个代码未写入 `dwd_stock_eod_price`。
> - 分支 `codex/fix-historical-dim-stock-lifecycle` 已修复 `dim_stock` 历史生命周期：缺主数据代码从全量 ODS daily 派生，`stock_basic.list_date` 晚于首个日线交易日时用 `first_trade_date` 兜底；PR #132 review follow-up 已改为直接复用 `daily_lifecycle`，避免重复全量扫描 ODS daily。

> 当前交接补充（2026-06-10，GPT-5 Codex）
> - PR #127 review follow-up 已修复 Cloud Run ledger resume 代码断链：`LedgerParams`/manifest/CLI/SQL metadata 贯通，Python ledger 写入并恢复 `ads_backtest_ledger_state_daily`，`25` QA 改为 `ashare_ads` 与当前 ADS 字段。
> - 未运行测试、BigQuery 或 Cloud Run smoke；后续需要按 owner 指令做最小验证。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 手工触发 2015 年 `ashare_warehouse_window_refresh` backfill 时失败，根因是窗口刷新 SQL 固定以 `2019-01-01` 作为写入下限，导致 `2015-01-01 ~ 2015-12-31` 被推成 `write_start=2019-01-01`。
> - 分支 `codex/fix-2015-index-backfill` 已将股票、指数、market-state 窗口刷新及股票/指数窗口 QA 改为按 `warehouse_mode` 区分日期下限：`daily_current` 保持 2019+，显式 `backfill` 允许 2019 年以前历史窗口。
> - 合并并部署后，下一步重新触发 2015 年窗口补数；2015 成功后再按年触发 2016、2017、2018。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 新增 `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`。
> - PRD 固定当前 R14 LightGBM regression 方法，不重新搜索参数，名义训练窗口为 `2015-04-01 ~ 2019-12-31`，先跑 `2020-01-02 ~ 2022-12-30` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。
> - 关键边界：训练必须做 5d label embargo，避免 2019 年末训练样本使用 2020 回测期收益；追加段不能和 `2020-2022` fresh segment 拼接成正式连续回测，除非 Cloud Run Python ledger resume 已实现并通过 resume consistency QA。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 旧 Composer-era 补跑 helper `scripts/pipeline/run_warehouse_refresh.py` 已删除。
> - 该脚本仍通过 `gcloud composer environments run` 触发已退役的 `ashare-composer`，与当前 `Cloud Scheduler + Cloud Workflows` 生产入口冲突。
> - 后续窗口补跑 / QA-only / full rebuild 恢复路径继续以 `docs/Pipeline-补跑与故障恢复-Runbook.md` 和 `orchestration/workflows/**` 为准。
> - PR #129 review follow-up 已同步清理 `.agent/memory/OPEN_QUESTIONS.md` 中对旧 helper 的现行工具描述。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - Strategy1 Cloud Run Python live acceptance gate 已在分支 `codex/implement-v3-live-gate` 从 v1 切到 v3。
> - live orchestrator 现在会在 ADS 写回前按实际 backtest span / manifest final_holdout window 重算五指数相对门、复合年化、Sharpe / Calmar 和 final_holdout 诊断字段，并写入 registry、backtest summary 与 comparison artifact。
> - PR #125 分支已完成 2 候选 live v3 smoke：prepare、candidate fanout、select/register/predict、backtest/report、19 QA 和 artifact 上传均 succeeded；smoke 中发现并修复了 `v3_relative_gate_by_benchmark.csv` 的 `search_id` 透传缺口。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - `TODO.md` 已从“完成历史 + 进行中事项混排”重写为短版，只保留当前可执行事项。
> - 当前 TODO 只剩 3 个主动作：OQ-005 补短观察窗记录、OQ-010 继续找 accepted Python baseline、OQ-012 决定是否正式归档关闭。
> - 完成历史不再放在 `TODO.md`，统一回到 `IMPLEMENTATION_STATUS.md` / `AGENT_HANDOFF.md` / `OPEN_QUESTIONS.md`。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - PR #124 review 指出 active on-call runbook 仍指向已删除的 `ashare-composer`；该问题已处理。
> - `docs/Pipeline-补跑与故障恢复-Runbook.md` 已改写为 Scheduler + Workflows 版恢复手册，当前恢复命令使用 Workflows executions、Scheduler jobs、Cloud Run Jobs 和 BigQuery 状态表。
> - `scripts/alerting/README.md` 与 `scripts/alerting/setup_alerts.py` 也已同步，不再把 alert checker 部署/故障描述指向 Composer。

> 当前交接补充（2026-06-09，GPT-5 Codex）
> - 2026-06-09 20:00 scheduled ODS workflow 已触发，但先后暴露 Cloud Run Job 权限缺口：缺 `run.jobs.runWithOverrides` 和 `run.operations.get`。
> - live IAM 已补：`ashare-ingest-current-scope` job-level `roles/run.jobsExecutorWithOverrides`，以及 workflows runtime SA 的 project-level `roles/run.viewer`。
> - `bootstrap_scheduler_iam.sh` 已同步改成该真实权限口径，避免后续 bootstrap 回到错误的 job-level `run.invoker`。

> 当前交接补充（2026-06-08，GPT-5 Codex）
> - OQ-005 已完成 production cutover：生产调度入口固定为 `Cloud Scheduler + Cloud Workflows`，`ashare-composer` 环境已删除，Composer 业务 DAG 不再是现行生产路径。
> - `orchestration/composer/` 已收口为 retired / audit-only 历史目录，只保留审计、迁移对照和受控回滚参考价值。
> - Strategy1 `v3` replay 与 helper 驱动的 `24` QA 已按最新 contract 真执行通过；当前真正开放的主线只剩 OQ-010 可接受 Python baseline 和 OQ-012 是否正式归档。

## 当前交接摘要

- 2026-06-10：PR #146 已合并到 `main`（merge commit `bca0e791abb57b3fb7efaa01b46e7444ac15cfb2`），并已从 merge 后 `origin/main` 重建正式 Strategy1 runner 镜像 `sha256:c0ae9b2ec72b1299a08db66eb02881d0d3156735c14f08193d60e4388c9cc357`。五个 Strategy1 Cloud Run jobs 已更新到该 immutable digest，读回确认资源/SA/args 未改乱；只读 boot smoke execution `strategy1-backtest-report-job-8krjt` succeeded。
- 2026-06-10：分支 `codex/research-schema-readiness` 已补 D2 前 research additive migration 约定与 readiness QA：新增 `sql/research/02_research_strategy1_additive_migrations.sql` 和 `sql/research/03_qa_research_schema_readiness.sql`，catalog 登记 `qa_research_schema_readiness`，README 写明 `01 contract -> 02 additive migrations -> 03 readiness QA`。live BigQuery readiness QA 7 条断言全部 successful；本地 `python3 -m pytest -q tests` 66 passed，Dataform check/compile、compileall、`git diff --check` 均通过。
- 下一步：合并 `codex/research-schema-readiness` PR 后，再单独开 Phase D2 default research-first PR；D3 promotion job 和 Phase E 包化/命名收敛仍保持后续独立 PR。
- 2026-06-10：新增年度滚动执行工程化 PRD `docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`；范围只解决 annual rolling 从手工 smoke 到可重复正式执行的工程路径，包括 resolved experiment payload 自动生成、ADS additive migration、schema readiness QA、run_id/artifact 规则和 continuous ledger 执行规则。不改模型、不扩参数、不调 v3 gate、不切 `ashare_research`；正式 `2021-2026` 结果不得拼接年度 fresh-run。
- 2026-06-10：2021 annual-selection Cloud Run smoke 已在正式 Strategy1 jobs 上闭环。PR #141 合并后构建部署 `strategy1-cloudrun-runner:2565e0f`；candidate fanout `strategy1-train-candidate-fanout-job-5f6qg` 成功，11 个候选全部 `cv_fold_count=3`、CV passed；select/register/predict `strategy1-select-register-predict-job-pxtbw` 成功并选中 `risk_lgbm_prd_strong_regularized_l5_l63_lr002_n300_leaf800_ff07_bf10`；backtest/report `strategy1-backtest-report-job-t5fg6` 成功，2021 结果 total_return -8.08%、compound annual -8.39%、Sharpe -0.382、MaxDD -19.54%、vs `000001.SH` excess -12.88%。运行中已用 additive DDL 补齐 `ads_backtest_ledger_state_daily` 和 performance summary 复合年化字段。
- 2026-06-10：项目结构重构 Phase D1b runner research routing 已在 `codex/strategy1-research-routing-d1b` 实现并处理 PR #143 review follow-up；新增 `output_dataset_role` 配置/CLI、`dataset_roles.py` helper 和 runner/report/diagnosis/QA/acceptance/comparison/factor attribution 显式 research routing。默认仍是 ADS，且默认 ADS 子命令不下发 `--output-dataset-role=ads`，保持旧 Cloud Run 镜像兼容；显式 `research` 模式下 run-scoped Strategy1 表解析到 `ashare_research.research_*`，research status 表解析到 `ashare_research.research_experiment_run_status`。Research DDL 已补 lifecycle 默认值：普通输出为 `candidate/not_promoted`，promotion manifest 为 `planned`。本轮不创建或部署 BigQuery `ashare_research` 对象、不修改 Cloud Run Job spec、不切 default research-first、不实现 promotion；D2 前新增 D1 收尾验收项，读侧 routing 全局态风格收敛登记到 Phase E。验证：`python3 -m pytest tests` 57 passed、Dataform `--check`、Dataform compile、BigQuery DDL dry-run、主要 CLI help/dry-run、41 条程序化 self-review checks、compileall 和 `git diff --check` 均通过。
- 2026-06-10：项目结构重构 Phase D1a SQL render table-role routing 已在 `codex/strategy1-research-routing-d1a` 实现并 rebase 到最新 `origin/main`；PR #142 review follow-up 已补全 catalog step role 覆盖，并新增 pytest 防止 research 渲染残留 `data-aquarium.ashare_ads.`。`sql_render.py` 可按 catalog step 的 role 集合把 ADS 表引用显式改写为 `ashare_research.research_*`，`sql_runner.py` wrapper 已透传 `dataset_role` / `allow_future_research`，默认 ADS 行为不变。无 step 上下文的全局 research 替换会 fail-fast，防止 `model_registry` / `acceptance_result` 共享 ADS 表造成误替换。本轮不启用 Cloud Run 默认写 research、不写 BigQuery、不做 promotion；D1b 仍需单独接 runner config / report / diagnosis / QA / acceptance/comparison research source。
- 2026-06-10：项目结构重构 Phase D0 research table contract 已在 `codex/add-research-table-contract` 实现；新增 `sql/research/**`、`ashare_research` schema contract、catalog research contract metadata 和 DDL drift tests。PR #140 review follow-up 已补 `experiment_run_status` 当前侧 `ashare_meta` dataset override 和 `build_order_plan` 分区列一致性测试；D0 不部署 BigQuery、不写 research、不迁移历史 ADS、不实现 promotion。D1a 已新增 render-only research opt-in，真正 runner 写 research 仍需 D1b 单独 PR。
- 2026-06-10：OQ-005 Cloud Run Job IAM bootstrap TODO 已收口；PR #126 已合并到 `main`，`orchestration/workflows/bootstrap_scheduler_iam.sh` 已固化 runtime SA 的 job-level `roles/run.jobsExecutorWithOverrides`、project-level `roles/run.viewer` 并移除旧 job-level `roles/run.invoker`；本轮只清理过期 TODO / 记忆状态，不改运行代码。
- 2026-06-10：Dataform generated SQLX drift 已在 `codex/fix-dataform-generated-drift` 单独 cleanup 分支修复；重新生成 `dataform/definitions/**/*.sqlx` 中 6 个 stale 文件，并新增 `tests/dataform/test_generated_sqlx.py` 直接调用 `generate_sqlx_from_sql.py --check` 防复发；未修改 canonical `sql/` 或 `dataform/action_manifest.json`，`python3 -m pytest tests` 25 passed，`--check`、Dataform compile 和 `git diff --check` 均通过。
- 2026-06-10：项目结构重构 PRD Phase A/A2/B/C 已在 `codex/strategy1-structure-refactor` 实现并完成 PR #136 review follow-up：新增 Strategy1 active step catalog、retired linter、table-role/dataset-role resolver 与 `src/quant_ashare/**` 包基础，active/shared SQL 已迁到 `sql/strategy1/**`；旧 `sql/ml/strategy1/**`、`sql/cloudrun/strategy1/**` 只保留 historical/audit README。当时默认仍解析/写入 `ashare_ads`，显式 `dataset_role="research"` fail-fast，不创建 `ashare_research`；D1a 已在后续分支补 render-only research opt-in。Owner 已确认 PR #136 一次性合并 Phase A/A2/B/C 的豁免，记录为 `DECISION-20260610-07`。
- 2026-06-10：新增 Strategy1 年度滚动选参 PRD `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`；P0 固定 11 个 LightGBM regression 可选候选、B26 binary diagnostic-only reference、20 只持仓、7.5% 单票上限、biweekly 和 `ledger_exec_v1_lot100`，每年用上一整年 valid 选参数，再用最近 5 年 final refit，最终用年度预测合并后的一条连续 ledger 评价 `2021-2026`。
- 2026-06-10：新增项目结构重构总 PRD `docs/prd/PRD_20260610_02_项目结构重构方案.md`；owner 已确认采用 `ashare_research` / `research_*` / `accepted != promoted`、`sql/strategy1/**`、`src/quant_ashare/**`、短期保留 `scripts/strategy1_cloudrun/**` wrapper，且 P0 不强制创建 `docs/retired/`。实施顺序为先做 active path catalog、防误用护栏和 table role / dataset role resolver，再迁移 Strategy1 active shared SQL（同时覆盖 `sql/ml/strategy1/**` 与 `sql/cloudrun/strategy1/**`）到 `sql/strategy1/**`，随后抽 Strategy1 package foundation，最后再分段实现 `ashare_research` / `ashare_ads` 生命周期隔离和 deeper package split。
- 2026-06-10：新增 Strategy1 回测复合年化收益 PRD，范围为 summary / report / v3 gate 的复利年化字段口径；本 PR 不改代码、不跑 BigQuery / Cloud Run。
- OQ-005 当前状态：`ashare-ods-ingestion-daily`（`0 20 * * *`）与 `ashare-pipeline-alert-checker`（`0 * * * *`）两个 Scheduler job 已是唯一生产调度入口，ODS parent -> warehouse child、alert checker、manual full rebuild dry-run 都已有 live smoke 证据。
- OQ-005 代码边界：`orchestration/workflows/**` 是唯一现行调度实现面；`orchestration/composer/**` 只保留历史快照，不再接受新的生产逻辑或运维 runbook 变更；旧 Composer-era 补跑 helper `scripts/pipeline/run_warehouse_refresh.py` 已删除。
- Strategy1 当前状态：`v3` acceptance gate replay/QA 已 contract-driven 收口并通过；旧 BQML-only `02-04`、SQL ledger fallback `08` / `--use-bq-ledger` 和旧 `run_oq010_experiments.py` 已在 PR #131 分支退役删除；当前没有 accepted Python baseline，OQ-010 仍然 open；R14 长训练补数已越过历史 backfill 日期下限和 `dim_stock` 生命周期问题，但 2015 年重跑又暴露 core smoke 2019 全表下限误杀，需合并部署 `codex/fix-historical-backfill-core-smoke` 后再重跑 2015 年窗口。
- OQ-012 当前状态：schema contract / repair tooling / QA 都已具备，当前 BigQuery 读层无 mismatch 报警；剩余是 owner 是否把该问题正式关闭或保留防复发工程项。
- 下一步：结构重构若继续推进，应单独做 Phase D2 default research-first 或 Phase D3 owner-approved promotion job；D1b 合并前不应切默认写入，也不应把 research 结果自动 promotion 到 ADS。


# Agent 交接（Agent Handoff）

本文件只保留当前交接摘要和最近 3 条交接。更早内容已归档到 `archive/AGENT_HANDOFF_2026-06.md`。

> **语言约定（2026-06-01 起）**：新增交接条目一律用中文撰写；更早的英文条目保留在 archive 中，不再放回当前文件。

## 2026-06-10 GPT-5 Codex - Research additive migration 与 readiness QA

### 已完成工作

- 合并 PR #146 到 `main`，merge commit 为 `bca0e791abb57b3fb7efaa01b46e7444ac15cfb2`。
- 从 merge 后 `origin/main` 新建部署 worktree，使用 Cloud Build 构建正式 Strategy1 runner 镜像 `research-d1-main-bca0e79-20260610-01`，digest 为 `sha256:c0ae9b2ec72b1299a08db66eb02881d0d3156735c14f08193d60e4388c9cc357`。
- 将五个 Strategy1 Cloud Run jobs 更新到该 immutable digest：`strategy1-train-predict-job`、`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 新增 `sql/research/02_research_strategy1_additive_migrations.sql`，用 idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 固化 `research_experiment_run_status.log_dir`。
- 新增 `sql/research/03_qa_research_schema_readiness.sql`，只读 `INFORMATION_SCHEMA` 检查 15 张 research 表、关键列/类型、分区、聚簇、lifecycle DEFAULT、partition filter 和 `log_dir`。
- 在 `configs/strategy1/active_step_catalog.yml` 登记 `qa_research_schema_readiness`，并更新 `sql/research/README.md`、`sql/README.md`、`sql/strategy1/README.md`。
- 新增 pytest 覆盖 research additive migration、readiness QA catalog 登记、表覆盖、lifecycle 默认值和 `log_dir`。
- 追加 `DECISION-20260610-09`，并同步 `KNOWN_CONSTRAINTS.md` / `IMPLEMENTATION_STATUS.md` / `TODO.md`。

### 重要上下文

- `01_research_strategy1_tables.sql` 仍是新环境 canonical contract，但 `CREATE TABLE IF NOT EXISTS` 不会更新已有表；后续新增 research 列必须同步 `02` migration 和 `03` readiness QA。
- 本 PR 不切 default research-first，不实现 promotion，不迁移 ADS 历史数据。
- D2 的前置变为：本 PR 合并后，再单独开 D2 default research-first PR。

### 改动文件

- `configs/strategy1/active_step_catalog.yml`
- `sql/research/02_research_strategy1_additive_migrations.sql`
- `sql/research/03_qa_research_schema_readiness.sql`
- `sql/research/README.md`
- `sql/README.md`
- `sql/strategy1/README.md`
- `tests/strategy1/test_research_contract.py`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build `ce178068-c6eb-4921-a3f4-c1a8ba18f917` succeeded。
- 五个 Strategy1 jobs 读回均指向 `sha256:c0ae9b2ec72b1299a08db66eb02881d0d3156735c14f08193d60e4388c9cc357`，资源/SA/args 保持原配置。
- 只读 Cloud Run boot smoke `strategy1-backtest-report-job-8krjt` succeeded。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/research/02_research_strategy1_additive_migrations.sql` 执行为 no-op skip。
- `bq query --use_legacy_sql=false --location=asia-east2 < sql/research/03_qa_research_schema_readiness.sql` 7 条断言全部 successful。
- `python3 -m pytest -q tests` -> 66 passed（4 个 Python / SSL 环境 warning）。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check` 通过。
- `npx --yes @dataform/cli compile dataform` 通过。
- `python3 -m compileall -q src scripts/strategy1_cloudrun scripts/strategy1` 通过。
- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 提交并推送 `codex/research-schema-readiness`，开单独 PR。
- PR 合并后进入 Phase D2 default research-first；D3 promotion job 和 Phase E 包化继续单独 PR。

### 已更新记忆文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 年度滚动执行工程化 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`。
- PRD 将 2021 annual-selection smoke 暴露的问题收敛为三个 P0 工程要求：resolved experiment payload 自动生成、ADS additive migration、schema readiness QA。
- PRD 明确年度 rolling orchestrator 的建议入口、输入输出、run_id 命名、artifact 要求、连续 ledger 执行规则和验收标准。
- PR #144 review follow-up 已处理 5 项：`--rebalance-frequency` 固定为 `biweekly`；migration 文件不再建议冲突的 `02_strategy1_additive_migrations.sql`；schema readiness QA 使用无数字前缀并要求登记 catalog；`scripts/strategy1_cloudrun/` 标记为过渡 wrapper namespace；B26 binary 明确为 diagnostic-only reference。
- 同步更新 `IMPLEMENTATION_STATUS`、`AGENT_HANDOFF` 和 `TODO.md`。

### 重要上下文

- 本轮只写 PRD，不改 runner、不改 SQL、不改 BigQuery、不跑 Cloud Run。
- PRD 明确 P0 不改模型、不扩 LightGBM 参数、不调整 v3 gate、不把默认输出切到 `ashare_research`。
- 正式 `2021-2026` 结果必须来自单一 continuous ledger，或经过 resume-continuous QA 的 segment ledger；不能拼接年度 fresh-run。

### 改动文件

- `docs/prd/PRD_20260610_04_策略1年度滚动执行工程化.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未运行测试；本轮为文档和记忆更新。

### 阻塞项

- 无。

### 下一步建议

- 按 PRD 实现 ADS additive migration 与 schema readiness QA。
- 再实现 annual rolling orchestrator dry-run / resolved payload 生成，并用它重跑 2021 smoke。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 年度滚动选参 2021 smoke 闭环

### 已完成工作

- 合并 PR #141 后，从 `main` commit `2565e0f` 构建并部署正式 Strategy1 Cloud Run runner 镜像 `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:2565e0f`。
- 四个正式 jobs 已更新到该镜像：`strategy1-prepare-matrix-job`、`strategy1-train-candidate-fanout-job`、`strategy1-select-register-predict-job`、`strategy1-backtest-report-job`。
- 重跑 2021 annual-selection candidate fanout：execution `strategy1-train-candidate-fanout-job-5f6qg` 成功，11 个候选全部 `cv_confirmation_status=passed`、`cv_fold_count=3`。
- 重跑 `select_register_predict`：execution `strategy1-select-register-predict-job-pxtbw` 成功，选中 `risk_lgbm_prd_strong_regularized_l5_l63_lr002_n300_leaf800_ff07_bf10`，`prediction_rows=808433`。
- 重跑 `backtest_report`：execution `strategy1-backtest-report-job-t5fg6` 成功，ledger、report、runner QA、lot-aware ledger QA、model diagnosis QA、tail-risk diagnosis 和 tail-risk QA 全部走完。
- 手工补齐生产 ADS additive schema：创建 `ashare_ads.ads_backtest_ledger_state_daily`，并为 `ashare_ads.ads_backtest_performance_summary` 补 4 个复合年化字段。

### 重要上下文

- 第一次 `select_register_predict` 失败是因为 annual-selection experiment 不在 `configs/strategy1/oq010_experiments_v0.json` 中；后续使用 base64 resolved experiment payload 解决。
- 第一次 `backtest_report` 失败是因为缺 `ads_backtest_ledger_state_daily`；第二次失败是因为 `ads_backtest_performance_summary` 缺复合年化字段；两者均为 BigQuery schema 未同步最新代码契约，不是模型训练或 CV 逻辑失败。
- 2021 smoke 只验证单年度链路闭环；还没有执行完整 `2021-2026` 年度滚动参数选择和连续 ledger。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build `945cead1-c916-42af-a471-193928c8ca78`：SUCCESS。
- `strategy1-train-candidate-fanout-job-5f6qg`：succeeded，11/11 candidate metrics updated。
- Candidate metrics：全部 `cv_confirmation_status=passed`、`cv_fold_count=3`，fold ids `cv_2018/cv_2019/cv_2020`。
- `strategy1-select-register-predict-job-pxtbw`：succeeded，selected candidate `risk_lgbm_prd_strong_regularized_l5_l63_lr002_n300_leaf800_ff07_bf10`。
- `strategy1-backtest-report-job-t5fg6`：succeeded。
- BigQuery summary：`bt_s1_annual_param_select_train2015_2019_valid2020_pred2021_n20_w075_v20260610_01` 覆盖 `2021-01-04..2021-12-31`，`total_return=-0.08075416625099796`、`compound_annual_return=-0.08394704034322242`、`annual_vol=0.18489507632796431`、`sharpe=-0.3820502523215857`、`max_drawdown=-0.1953798536113548`、`excess_return=-0.12875580760744898`。

### 阻塞项

- 无当前阻塞。2021 单年度 smoke 已闭环，但策略表现不达可接受 baseline。

### 下一步建议

- 扩展实现完整年度滚动 `2021-2026`：逐年参数选择、逐年预测生成，最后用一条连续 `ledger_exec_v1_lot100` 评价，不拼接年度 fresh-run。
- 后续正式 annual walk-forward 建议使用新的 run_id，不复用本次 smoke 的 `s1_annual_param_select_train2015_2019_valid2020_pred2021_n20_w075_v20260610_01`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Runner research routing D1b

### 已完成工作

- 从最新 `origin/main` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-research-routing-d1b` 和分支 `codex/strategy1-research-routing-d1b`；未触碰主工作树 `/Users/fisher/Desktop/git/quant-ashare`。
- 新增 `scripts/strategy1_cloudrun/dataset_roles.py`，封装 `TableResolver`、`output_dataset_role` 校验、research opt-in 和 SQL dataset-role rewrite；默认 rewrite 排除 `acceptance_result`，避免 `ads_model_registry` 双 role 歧义。
- `RunnerConfig`、通用 CLI、resolved manifest、orchestrator status payload 和 Cloud Run job args 已透传 `output_dataset_role`；默认值保持 `ads`。
- `train_predict.py`、`prepare_matrix.py`、`select_register_predict.py`、`ledger.py`、`backtest_report.py`、`orchestrate_experiments.py`、`orchestrate_sklearn_native_search.py` 和 `state.py` 已接入 resolver；显式 research 模式下 run-scoped 表指向 `ashare_research.research_*`。
- `render_report.py`、`diagnose_model_quality.py`、`analyze_tail_risk.py`、`replay_acceptance_gate_v3.py`、`compare_oq010_experiments.py`、`diagnose_acceptance_gate_v2.py`、`diagnose_acceptance_window.py` 和 `attribute_factor_contribution.py` 已新增 `--output-dataset-role`，并在查询或 summary 回写前做 dataset-role rewrite。
- 新增 `tests/strategy1_cloudrun/test_dataset_role_routing.py`，覆盖默认 ADS、显式 research、resolver/SQL rewrite、subcommand 透传、ledger/status routing、native query helper、acceptance diagnostic helper 和 factor attribution summary 回写。
- PR #143 review follow-up 已处理：默认 ADS 子命令不下发 `--output-dataset-role=ads`，保持旧 Cloud Run 镜像兼容；显式 research 仍下发 role flag。
- `sql/research/01_research_strategy1_tables.sql` 已补 lifecycle 默认值：普通 research 输出默认 `research_status='candidate'`、`promotion_status='not_promoted'`，`research_promotion_manifest.promotion_status` 默认 `planned`。
- 新增 D1 收尾 TODO 和 `DECISION-20260610-08`，明确 D2 前必须完成 D0 DDL 部署、Cloud Run 镜像重建、runtime SA `ashare_research` 写权限和真实 research-mode smoke。
- 同步更新 `TODO.md`、`IMPLEMENTATION_STATUS`、`KNOWN_CONSTRAINTS`、`ARCHITECTURE_MEMORY`、`DECISION_LOG` 和 `AGENT_HANDOFF`。

### 重要上下文

- D1b 仍是 explicit opt-in；不切 default research-first。
- 本轮不创建或部署实际 BigQuery `ashare_research` 表，不修改 Cloud Run Job spec，不迁移历史 ADS，不实现 promotion job。
- historical BQML parity reference 仍按设计读取 ADS，不随当前 run 的 output role 改写。
- D1b 单测 / dry-run 不是 PRD D1 的真实验收；进入 D2 前必须完成显式 research-mode smoke。

### 改动文件

- `scripts/strategy1_cloudrun/dataset_roles.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/train_predict.py`
- `scripts/strategy1_cloudrun/prepare_matrix.py`
- `scripts/strategy1_cloudrun/select_register_predict.py`
- `scripts/strategy1_cloudrun/ledger.py`
- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1_cloudrun/state.py`
- `scripts/strategy1/*.py` report / diagnosis / acceptance / comparison helpers
- `configs/strategy1/cloudrun_runner_default.yml`
- `sql/research/01_research_strategy1_tables.sql`
- `sql/research/README.md`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `tests/strategy1/test_research_contract.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest tests -q`：57 passed。
- `PYTHONPATH=src python3 -m pytest tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1/test_research_contract.py -q`：21 passed。
- `python3 -m compileall -q src/quant_ashare/strategy1 scripts/strategy1_cloudrun scripts/strategy1 tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1/test_research_contract.py`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：通过。
- `(cat sql/00_create_datasets.sql; cat sql/research/01_research_strategy1_tables.sql) | bq query --dry_run --use_legacy_sql=false --location=asia-east2`：通过。
- CLI help 覆盖 `orchestrate_experiments`、`orchestrate_sklearn_native_search` 和 `backtest_report`。
- CLI dry-run 覆盖 `orchestrate_experiments`、`orchestrate_sklearn_native_search` 和 `backtest_report` 默认 ADS 路径；两个 orchestrator dry-run 均确认默认计划不含 `--output-dataset-role`。
- 41 条程序化 self-review checks：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 合并 D1b 前继续保持默认 ADS；后续先做 D1 收尾验收，再单独推进 Phase D2 default research-first，Phase D3 单独实现 owner-approved promotion job；Phase E 包化时收敛读侧 routing 全局态。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - SQL render table-role routing D1a

### 已完成工作

- 从最新 `origin/main` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-research-routing-d1a` 和分支 `codex/strategy1-research-routing-d1a`；未触碰主工作树 `/Users/fisher/Desktop/git/quant-ashare`。
- 已 rebase 到最新 `origin/main`，吸收 PR #141 dynamic CV fold 修复；本分支继续承载 PR #142。
- 在 `src/quant_ashare/strategy1/sql_render.py` 接入 table role / dataset role resolver：按 catalog step 的 `inputs` / `outputs` 构造替换表，默认 ADS 不变，显式 research 需 `allow_future_research=True`。
- 增加无 step 上下文的 research 替换 fail-fast，以及重复 ADS 源表不同 research 目标的歧义保护，避免 `ads_model_registry` 被误替换到 `research_acceptance_result`。
- `scripts/strategy1_cloudrun/sql_runner.py` 的 path / step wrapper 已透传 `dataset_role` 与 `allow_future_research`，但现有调用默认仍是 ADS。
- PR #142 review follow-up 已补全非 retired Strategy1 step 的 catalog `inputs` / `outputs`，使其覆盖 SQL 中实际 `data-aquarium.ashare_ads.*` 引用。
- 新增 `tests/strategy1/test_sql_render.py` 覆盖默认 ADS、显式 research、meta dataset override、字符串字面量替换、全局 research 歧义保护和所有 active step 的 research 渲染无 ADS 残留。
- 新增 `tests/strategy1/test_strategy1_catalog.py` 覆盖 step role contract 与 SQL 实际 ADS 引用一致，避免 catalog 欠声明导致 research 渲染混写。
- 同步更新 `sql/strategy1/README.md`、`TODO.md`、`IMPLEMENTATION_STATUS`、`KNOWN_CONSTRAINTS`、`ARCHITECTURE_MEMORY` 和 `AGENT_HANDOFF`。

### 重要上下文

- 本轮是 Phase D1a render-only；未修改 `backtest_report.py` 默认参数，未部署 Cloud Run，未执行 BigQuery 写入，未创建实际 `ashare_research` 表。
- `dataset_role="research"` 仍不是普通调用默认能力；只有显式 `allow_future_research=True` 的 contract / dry-run / 后续接线验证可以使用。
- 后续新增或修改 Strategy1 SQL 中的 run-scoped ADS 引用时，必须同步 catalog `inputs` / `outputs`，否则 pytest 会在 role 覆盖或 research residual 断言中失败。
- D1b 仍需单独实现 runner CLI/config `output_dataset_role=research`、report / diagnosis / QA / acceptance/comparison 全链路读取 research output。

### 改动文件

- `src/quant_ashare/strategy1/sql_render.py`
- `configs/strategy1/active_step_catalog.yml`
- `scripts/strategy1_cloudrun/sql_runner.py`
- `tests/strategy1/test_sql_render.py`
- `tests/strategy1/test_strategy1_catalog.py`
- `sql/strategy1/README.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `python3 -m pytest tests`：42 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform > /tmp/quant_ashare_dataform_compile_d1a_rebased.json`：通过。
- catalog ADS role 覆盖扫描：`missing_count=0`。
- 88 条程序化 self-review checks：通过。
- `python3 -m compileall -q src/quant_ashare/strategy1 scripts/strategy1_cloudrun`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- Phase D1b 单独 PR：为 Cloud Run runner 增加显式 `output_dataset_role=research` CLI/config 接线，并让 report、diagnosis、QA、acceptance/comparison 从同一 resolver 读取 research output；完成前不要切 default research-first。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Research table contract D0

### 已完成工作

- 从最新 `origin/main` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-research-contract` 和分支 `codex/add-research-table-contract`；未触碰主工作树 `/Users/fisher/Desktop/git/quant-ashare`。
- 在 `sql/00_create_datasets.sql` 中新增 `data-aquarium.ashare_research` schema contract。
- 新增 `sql/research/01_research_strategy1_tables.sql`，定义 Strategy1 research 表契约：训练面板、模型注册、预测、候选池、组合目标、订单计划、回测成交/持仓/NAV/ledger state/summary、信号监控、acceptance result、experiment run status 和 append-only promotion manifest。
- 新增 `sql/research/README.md`，说明 D0 只定义 contract，不切 runner 默认写入。
- 更新 `configs/strategy1/active_step_catalog.yml`，记录 research contract SQL，并校准 `model_prediction_daily` / `order_plan_daily` 的分区列元数据。
- 新增 `tests/strategy1/test_research_contract.py`，校验 catalog research target 与 DDL 一致、表名使用 `research_*`、分区列一致，且默认 `dataset_role="research"` 仍 fail-fast。
- PR #140 review follow-up 已处理：`experiment_run_status` 当前侧通过 `ads_dataset: ashare_meta` 解析到既有 `ashare_meta.strategy1_experiment_run_status`；`resolve_table_role` 支持 per-role dataset/project override；`build_order_plan.partition_columns` 与 `order_plan_daily` 的 `rebalance_date` 对齐，并新增 step 输出分区一致性测试。
- 同步更新 `TODO.md`、`IMPLEMENTATION_STATUS`、`KNOWN_CONSTRAINTS`、`ARCHITECTURE_MEMORY` 和 `AGENT_HANDOFF`。

### 重要上下文

- 本轮是 Phase D0 contract-only；未创建实际 BigQuery dataset / table，未切 `output_dataset_role=research`，未迁移历史 ADS，未实现 promotion job。
- `resolve_table_role(..., dataset_role="research")` 默认仍必须 fail-fast；`allow_future_research=True` 在 D0 用于 contract-only 解析与测试，D1a 后也用于 SQL render-only / dry-run 接线验证。
- 当前策略产出表默认仍指向 `ashare_ads`；meta / orchestration role 可用 per-role dataset override，当前只用于 `experiment_run_status`。
- 后续 D1b 才做实际 runner 显式 research routing，D2 才做 default research-first，D3 才做 owner-approved promotion。

### 改动文件

- `sql/00_create_datasets.sql`
- `sql/research/01_research_strategy1_tables.sql`
- `sql/research/README.md`
- `configs/strategy1/active_step_catalog.yml`
- `src/quant_ashare/strategy1/table_roles.py`
- `tests/strategy1/test_research_contract.py`
- `tests/strategy1/test_strategy1_catalog.py`
- `sql/README.md`
- `sql/strategy1/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest tests`：32 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform > /tmp/quant_ashare_dataform_compile_research_contract.json`：通过。
- `(cat sql/00_create_datasets.sql; cat sql/research/01_research_strategy1_tables.sql) | bq query --dry_run --use_legacy_sql=false --location=asia-east2`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- Phase D1b 单独 PR：新增显式 runner `output_dataset_role=research` routing，并让 report / diagnosis / QA / acceptance 从同一 table-role resolver 读取 research output。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/ARCHITECTURE_MEMORY.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - OQ-005 IAM bootstrap TODO 收口

### 已完成工作

- 复核 [PR #126](https://github.com/gthbj/quant-ashare/pull/126) 已合并到 `main`，merge commit 为 `54fe077bb656f23b5ff9384f348e49b7a5259e94`。
- 复核 `orchestration/workflows/bootstrap_scheduler_iam.sh` 已包含 Workflows runtime SA 所需的 `roles/run.viewer` 与 `roles/run.jobsExecutorWithOverrides`，并移除旧 job-level `roles/run.invoker`。
- 将 `TODO.md` 中 “OQ-005：合并 2026-06-09 scheduled ODS run 暴露的 Cloud Run Job IAM bootstrap 修正” 勾选完成。
- 同步更新 `IMPLEMENTATION_STATUS` 与 `AGENT_HANDOFF`，说明该项是过期 TODO 清理，不是新增运行逻辑。

### 重要上下文

- 本轮未修改 `orchestration/workflows/bootstrap_scheduler_iam.sh`；代码修复已由 PR #126 进入 `main`。
- 仍未关闭 OQ-005；剩余主要是 cutover 后短观察窗记录和少量非阻断运维收尾。

### 改动文件

- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `gh pr view 126 --json number,title,state,mergedAt,url,mergeCommit,headRefName,baseRefName`：确认 PR #126 为 `MERGED`。
- `git grep` / `git show origin/main:orchestration/workflows/bootstrap_scheduler_iam.sh`：确认 `roles/run.viewer`、`roles/run.jobsExecutorWithOverrides` 和移除旧 job-level `roles/run.invoker` 的 bootstrap 口径仍在 `main`。

### 阻塞项

- 无。

### 下一步建议

- 继续处理 OQ-005 cutover 后短观察窗记录；该项完成后再判断 OQ-005 是否可以正式收口。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Dataform generated SQLX drift cleanup

### 已完成工作

- 从最新 `origin/main` 新建分支 `codex/fix-dataform-generated-drift`。
- 运行 `scripts/dataform/generate_sqlx_from_sql.py`，同步 6 个 stale generated SQLX 文件：
  - `dataform/definitions/setup/01_create_meta_tables.sqlx`
  - `dataform/definitions/dim/02_dim_stock.sqlx`
  - `dataform/definitions/metadata/01_core_table_column_descriptions.sqlx`
  - `dataform/definitions/assertions/01_core_smoke_checks.sqlx`
  - `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`
  - `dataform/definitions/assertions/12_windowed_index_refresh_checks.sqlx`
- 勾选 `TODO.md` 中的 Dataform generated SQLX drift cleanup 项，并同步 `IMPLEMENTATION_STATUS` / `AGENT_HANDOFF`。
- 按 PR review 的 Low 防复发建议，新增 `tests/dataform/test_generated_sqlx.py`，直接调用 `generate_sqlx_from_sql.py --check`。

### 重要上下文

- 本轮只修 generated SQLX drift；canonical `sql/` 与 `dataform/action_manifest.json` 没有改动。
- 防复发测试复用真实生成脚本的 check 模式，不复制生成逻辑，也不会写出文件。
- 未运行 BigQuery、Cloud Run、Workflows 或生产 Dataform invocation。

### 改动文件

- `dataform/definitions/setup/01_create_meta_tables.sqlx`
- `dataform/definitions/dim/02_dim_stock.sqlx`
- `dataform/definitions/metadata/01_core_table_column_descriptions.sqlx`
- `dataform/definitions/assertions/01_core_smoke_checks.sqlx`
- `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`
- `dataform/definitions/assertions/12_windowed_index_refresh_checks.sqlx`
- `tests/dataform/test_generated_sqlx.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `python3 -m pytest tests/dataform/test_generated_sqlx.py`：通过。
- `python3 -m pytest tests`：25 passed。
- `npx --yes @dataform/cli compile dataform > /tmp/quant_ashare_dataform_compile.json`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 合并本 cleanup PR 后，后续修改 manifest 覆盖的 canonical SQL 时继续同时提交 generated SQLX，并保持 `--check` clean。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 项目结构重构 Phase A-C 实现

### 已完成工作

- 新增 `configs/strategy1/active_step_catalog.yml`，记录 Strategy1 SQL stable step、旧路径、目标路径、调用方、参数契约、table role、当前 ADS role 与未来 research role。
- 新增 `src/quant_ashare/strategy1/catalog.py`、`sql_render.py`、`table_roles.py`、`retired_lint.py` 和 `pyproject.toml`。
- 将当前 active/shared Strategy1 SQL 从旧 `sql/ml/strategy1/**`、`sql/cloudrun/strategy1/**` 迁移到 `sql/strategy1/**`；旧目录只保留 historical/audit README。
- `backtest_report.py`、`orchestrate_sklearn_native_search.py`、risk-feature manifest、v3 replay QA helper 和 SQL runbook 已切到 catalog step / 新命名空间。
- 恢复 `ledger.py` 中被后置同名函数覆盖的 resume 参数校验，使现有 ledger resume 单测通过。
- PR #136 review follow-up 已修复 retired linter 递归扫描、research role fail-fast、audit-only README 说明、Dataform drift TODO 和自查文档协议问题。

### 重要上下文

- 本轮只实现 PRD Phase A/B/C；未创建 `ashare_research` dataset，未默认 research-first，未迁移历史 ADS/GCS，未迁移 Cloud Run Job entrypoint。
- 当前 `table_roles.resolve_table_role(..., dataset_role="research")` 会 fail-fast；默认不传 `dataset_role` 时仍返回 `data-aquarium.ashare_ads.*`。
- Owner 已确认 PR #136 可一次性合并 Phase A/A2/B/C；后续 Phase D/E 仍按 PRD 单独拆分。
- Dataform `--check` 失败是既有 generated SQLX stale/missing；本分支相对 `origin/main` 没有 `dataform/` diff。

### 改动文件

- `configs/strategy1/active_step_catalog.yml`
- `src/quant_ashare/strategy1/**`
- `sql/strategy1/**`
- `scripts/strategy1_cloudrun/**` wrapper 相关文件
- `scripts/strategy1/run_acceptance_gate_v3_replay_qa.py`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/策略1报告GCS上传运行手册.md`
- `sql/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src:. <venv>/bin/python -m pytest tests/strategy1 tests/strategy1_cloudrun tests/pipeline_control`：24 passed。
- `PYTHONPATH=src /tmp/quant-ashare-structure-venv/bin/python -m quant_ashare.strategy1.retired_lint`：通过。
- catalog validate、active step render smoke、compileall、`backtest_report --dry-run`、search orchestrator `--help`、v3 replay QA helper `--help`、`git diff --check` 均通过。
- `scripts/dataform/generate_sqlx_from_sql.py --check`：失败，原因是既有 `dataform/definitions/**` generated SQLX stale/missing；本分支无 `dataform/` diff。

### 阻塞项

- 无实现阻塞；Dataform generated SQLX stale 需要单独 cleanup PR 或 owner 决策。

### 下一步建议

- 后续 Phase D/E 单独做 `ashare_research` table contract、optional research routing、default research-first、promotion job 和 deeper package split。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Strategy1 年度滚动选参 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`。
- PRD 定义年度 walk-forward 参数选择方案：用上一整年 valid 选择参数和方向，再用选中参数在最近 5 年 final refit，预测并回测下一年。
- 年度窗口固定为 `2021` 至 `2026`：从 `2015-2019 train / 2020 valid / 2016-2020 final refit / 2021 backtest` 开始逐年滚动。
- P0 固定 feature set、股票池、成本、`20` 只持仓、`7.5%` 单票上限、`biweekly` 和 Cloud Run Python `ledger_exec_v1_lot100`，只搜索 11 个预先冻结的 LightGBM regression 可选候选；B26 binary 只作为 diagnostic-only reference。
- valid 选参门按 owner 确认口径写入：`valid_rank_ic > 0`、`valid_top_minus_bottom > 0`、五指数任一 valid 超额收益 `> 0`、valid 最大回撤 `>= -33.33%`、`valid_sharpe >= 0.3`、`valid_calmar >= 0.3`、五指数任一 `valid_excess_calmar_ratio > 0.3`；PR #137 review follow-up 后明确删除 `valid_total_return > 0` 只是避免重复硬门，不表示允许负收益候选通过。
- PRD 明确年度预测可分年生成，但最终评价必须来自一条连续 ledger，不能拼接每年 fresh-run。
- 同步更新 `IMPLEMENTATION_STATUS`、`AGENT_HANDOFF`、`DECISION_LOG` 和 `TODO`。

### 重要上下文

- 本轮是 PRD-only，不改 runner、不改 SQL、不运行 BigQuery / Cloud Run / Dataform。
- 该方案和刚完成的固定 R14 annual walk-forward 不同：固定 R14 只验证一个参数；本文要求每年从固定 regression 可选候选池中重新选参数。
- valid 年只用于选择下一年参数，不能作为同年最终样本外成绩。
- 候选池必须先冻结并生成 hash；如果后续新增候选，必须新开 experiment version。

### 改动文件

- `docs/prd/PRD_20260610_03_策略1年度滚动选参.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 未执行。此次为 PRD 与项目记忆更新。

### 阻塞项

- 无代码阻塞。

### 下一步建议

- owner review PRD。若认可，先实现 `2021` 单年度 smoke，再扩展到完整 `2021-2026` annual walk-forward 参数选择和连续 ledger 对比。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - 项目结构重构总 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260610_02_项目结构重构方案.md`。
- Review follow-up 后，PRD 将项目结构重构拆为：active path catalog 与防误用护栏、table role / dataset role resolver、Strategy1 shared SQL 稳定命名空间、Python package foundation、`ashare_research` / `ashare_ads` 生命周期隔离、深层包拆分与阶段性命名收敛。
- Owner 已确认 PRD 关键决策：新增 BigQuery `ashare_research` dataset，使用 `research_*` 表名前缀，`accepted != promoted`，先做 table-role abstraction 后 research-first，采用 `sql/strategy1/**` 和 `src/quant_ashare/**`，短期保留 `scripts/strategy1_cloudrun/**` wrapper，P0 不强制创建 `docs/retired/`。
- PRD 明确旧 BQML-only SQL / SQL ledger runner 已按前置 PRD 退役；当前剩余 Strategy1 SQL 多数是 Cloud Run Python path 仍使用的 active shared SQL，应从调用方反推并覆盖 `sql/ml/strategy1/**`、`sql/cloudrun/strategy1/**`，再迁移到 `sql/strategy1/**`。
- PRD 增补 retired linter allowlist、SQL 参数契约校验、`bqml_reference_run_id` legacy exception registry、Python package 交付策略和 research promotion manifest 口径。
- 同步更新 `.agent/memory/IMPLEMENTATION_STATUS.md`、`.agent/memory/AGENT_HANDOFF.md`、`.agent/memory/DECISION_LOG.md` 和 `TODO.md`。

### 重要上下文

- 本轮是 PRD-only，不改代码、不改 SQL、不运行 BigQuery / Cloud Run / Dataform。
- 已追加 `DECISION-20260610-05` 记录 owner 确认的结构重构决策；不新增 `KNOWN_CONSTRAINTS.md` 约束，因为本 PRD 尚未实现代码或物理 BigQuery 资源。
- 结构重构事项仍在 `TODO.md` P1；当 owner 决定启动 P1 工程治理或在 OQ-010/R14 空档穿插推进时，第一步是 PR-A：建立 active step catalog、retired reference linter 和 README/runbook 口径护栏；第二步 PR-A2 做 table role / dataset role resolver 且仍解析到 `ashare_ads`。`ashare_research` dataset / table contract 应后置为单独 PR，不和目录搬迁或默认写入切换混做。

### 改动文件

- `docs/prd/PRD_20260610_02_项目结构重构方案.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 文档改动；未运行 BigQuery、Cloud Run、pytest 或 Dataform。
- 建议提交前至少运行 `git diff --check`。

### 阻塞项

- 无。

### 下一步建议

- 结构重构仍按 `TODO.md` 的 P1 工程治理项处理；当 owner 决定启动或在 OQ-010/R14 空档穿插推进时，从 PR-A 开始：建立 active step catalog、retired reference linter 和 README/runbook 口径护栏；不移动文件、不改运行行为。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - Strategy1 旧 BQML / SQL ledger runner P0 退役实现

### 已完成工作

- 删除 BQML-only `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql`、`03_select_model_and_register.sql`、`04_predict_daily.sql`。
- 删除 SQL ledger fallback `sql/ml/strategy1/08_run_backtest.sql`。
- 删除旧 OQ-010 SQL/BQML 调度器 `scripts/strategy1/run_oq010_experiments.py`，避免保留会调用已删除 `02-04` / `08` 的失效入口。
- `scripts/strategy1_cloudrun/backtest_report.py` 已移除 `--use-bq-ledger` 参数、`bigquery_sql` backend 分支和对 `08_run_backtest.sql` 的调用；默认固定走 Cloud Run Python ledger。
- `scripts/strategy1_cloudrun/orchestrate_experiments.py` 与 `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py` 已移除 `--use-bq-ledger` 透传。
- 文档和项目记忆已同步为当前口径：active path 为 Cloud Run Python training / prediction / ledger + 共享 SQL `01`、`05-07`、`09-10`、`12`、`16-24`。

### 重要上下文

- 本次只删除旧执行入口，不删除历史 ADS / GCS artifact、历史 BQML run/backtest id 或 v3 replay/QA。
- `sql/ml/strategy1/01_build_training_panel.sql`、`05_build_candidates.sql`、`06_build_portfolio_targets.sql`、`07_build_order_plan.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`12_qa_model_diagnosis_outputs.sql` 和 `16-24` 仍是当前 Cloud Run Python path 的共享 SQL / QA 面。
- legacy FLOAT 股数审计只保留 Python `--use-float-ledger`；`--use-bq-ledger` 不再存在。

### 改动文件

- `scripts/strategy1_cloudrun/backtest_report.py`
- `scripts/strategy1_cloudrun/orchestrate_experiments.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `scripts/strategy1/run_oq010_experiments.py`
- `sql/ml/strategy1/02_train_bqml_logistic_candidates.sql`
- `sql/ml/strategy1/03_select_model_and_register.sql`
- `sql/ml/strategy1/04_predict_daily.sql`
- `sql/ml/strategy1/08_run_backtest.sql`
- `sql/ml/strategy1/README.md`
- `sql/README.md`
- `docs/prd/PRD_20260609_02_策略1旧BQMLSQLRunner退役.md`
- `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`
- `docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`
- `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`
- `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`
- `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`
- `docs/策略1-ml_pv_clf_v0-runner设计.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `docs/策略1实验并发调度器运行手册.md`
- `dataform/definitions/assertions/03_index_benchmark_checks.sqlx`
- `sql/meta/02_strategy1_experiment_run_status.sql`
- `sql/qa/03_index_benchmark_checks.sql`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

### 测试 / 验证

- 未执行 BigQuery、Cloud Run、pytest 或 replay。

### 阻塞项

- 无。

### 下一步建议

- 等 PR review；如果 reviewer 只要求补文档口径或移除残余引用，直接在本分支修。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/DECISION_LOG.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - historical backfill core smoke 修复

### 已完成工作

- 合并 PR #132 并删除远端分支。
- 从最新 `main` 重新部署 `ashare-pipeline-control`，新 revision 为 `ashare-pipeline-control-00007-tst`。
- 重新触发 2015 年 warehouse backfill execution `209bd2bf-86f4-455c-85c7-b6b1f4ec8025`。
- 诊断新失败点：流程已越过 `dim_stock` 生命周期缺口，失败于 core smoke 的旧全表下限断言。
- 新建分支 `codex/fix-historical-backfill-core-smoke`，将 core smoke 从“不得有 2019 前行”改为“不得早于 A 股日线支持历史下限 `1990-12-19`”。
- 同步更新 DWD price / valuation metadata 描述，明确默认全量/日常路径仍是 2019+，owner 显式 backfill 可写指定历史训练窗口。

### 重要上下文

- 失败 execution：`209bd2bf-86f4-455c-85c7-b6b1f4ec8025`。
- 失败 BigQuery job：`4a6b55a4-4cbc-4bad-9c22-8ed8265f8072`。
- 失败文案：`dwd_stock_eod_price must not write rows before dwd_start_date`。
- 该失败不是缺 ODS 数据，也不是 #132 未生效；它是 core smoke 旧全局不变量和 explicit historical backfill 新语义冲突。

### 改动文件

- `sql/qa/01_core_smoke_checks.sql`
- `sql/metadata/01_core_table_column_descriptions.sql`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已执行生产 backfill 重跑并定位失败点。
- 未执行 SQL dry-run 或重新触发 backfill；需合并部署后再跑。

### 阻塞项

- 合并部署前，2015 年 backfill 仍会命中旧线上 core smoke。

### 下一步建议

- 提交并合并本分支。
- 部署新的 `ashare-pipeline-control` SQL bundle。
- 重新触发 `2015-01-01 ~ 2015-12-31` backfill；若通过，再按年触发 2016-2018。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-10 GPT-5 Codex - dim_stock 历史生命周期修复

### 已完成工作

- 诊断 2015 年 backfill execution `be12a12f-1e65-4cef-b60d-3945ef8da13a` 的新失败点。
- 确认 PR #130 修复有效：execution 已越过指数 DWD 和指数 QA，进入股票 DWD/DWS 后失败于 `QA-WIN-13`。
- 新建分支 `codex/fix-historical-dim-stock-lifecycle`，修复 `dim_stock` 历史生命周期：
  - `missing_from_stock_basic` 从全量 ODS daily 派生，不再只看 2019+ daily。
  - `stock_basic_enriched.list_date` 在 `stock_basic.list_date` 晚于首个日线交易日时，用 `first_trade_date` 作为历史生命周期下限。
- PR #132 review follow-up：删除重复的 `daily_codes` CTE，让 `missing_from_stock_basic` 直接复用 `daily_lifecycle`，避免同一全量 ODS daily 外表被扫描两次。

### 重要上下文

- 2015 年 QA 缺口为 `5,486` 行、`76` 个代码。
- 分类结果：`75` 个代码是 `before_list_date`，`1` 个代码 `000022.SZ` 是 `missing_dim_stock`。
- 当前失败后的 2015 DWD/DWS 已有部分写入；后续重跑窗口 SQL 会按窗口 DELETE/INSERT 覆盖，不需要单独清理。

### 改动文件

- `sql/dim/02_dim_stock.sql`
- `sql/metadata/01_core_table_column_descriptions.sql`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已执行只读诊断 BigQuery 查询，确认缺口原因。
- 未执行 SQL dry-run 或重新触发 backfill；需合并部署后再跑。

### 阻塞项

- 合并部署前不要继续触发 2015/2016/2017/2018 补数，否则仍会命中旧 `dim_stock` 生命周期口径。

### 下一步建议

- 提交并合并本分支。
- 部署新的 `ashare-pipeline-control` SQL bundle。
- 重新触发 `2015-01-01 ~ 2015-12-31` backfill；成功后再按年跑 2016-2018。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - 2015-2018 历史 backfill 下限修复

### 已完成工作

- 新建 worktree `/Users/fisher/Desktop/git/quant-ashare-fix-2015-index-backfill`，分支 `codex/fix-2015-index-backfill`。
- 修复 `ashare_warehouse_window_refresh` 历史 backfill 被 `2019-01-01` 下限拦截的问题。
- 股票 DWD/DWS 窗口、指数 DWD 窗口、market-state 窗口和股票 / 指数窗口 QA 均改为按 `warehouse_mode` 区分日期下限：`daily_current` 保持 2019+，显式 `backfill` 允许 owner 指定 2019 年以前窗口。

### 重要上下文

- 2015 年 backfill execution `2eea35d1-21bc-4c4c-b610-90b57170819a` 失败于指数 DWD 窗口刷新，错误为 `index DWD window refresh requires write_end_date >= write_start_date`。
- 根因不是 workflow 参数入口或 ODS readiness；ODS readiness 已通过，失败发生在指数窗口 SQL 的固定下限计算。
- 本 PR 不自动执行补数；合并部署后需要重新从 2015 年窗口开始触发。

### 改动文件

- `sql/incremental/01_refresh_stock_dwd_dws_window.sql`
- `sql/incremental/02_refresh_index_dwd_window.sql`
- `sql/incremental/03_refresh_market_state_window.sql`
- `sql/qa/10_windowed_stock_refresh_checks.sql`
- `sql/qa/12_windowed_index_refresh_checks.sql`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未执行 SQL dry-run 或生产补数验证；本轮按 owner 要求先修代码并提 PR。

### 阻塞项

- 无代码阻塞。
- 合并部署前不要继续触发 2016-2018 补数，否则仍会命中旧线上 SQL。

### 下一步建议

- 合并并部署 Workflows SQL bundle 后，重新触发 `2015-01-01 ~ 2015-12-31` backfill。
- 2015 年成功后，再按年触发 `2016`、`2017`、`2018`。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - Strategy1 R14 长训练窗口回测 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`。
- 文档定义固定 R14 方法的长训练窗口实验：名义训练窗口 `2015-04-01 ~ 2019-12-31`，先跑 `2020-01-02 ~ 2022-12-30` 的 `10` 只 / `20` 只双组合 diagnostic backtest；`2023-01 ~ 2026-06-09` 追加回测视 P0 结果和 owner 决策而定，若追加也跑两个组合。
- P0 组合设为 `target_holdings=10` / `max_single_weight=15%` 与 `target_holdings=20` / `max_single_weight=7.5%`，`rebalance_frequency=biweekly`。
- 文档明确 5d 标签 embargo、2015-2018 DWD/DWS 前置补建、2020-2022 diagnostic 不写 production accepted registry，以及追加段不能和 P0 fresh segment 拼接成正式连续回测，除非 Cloud Run Python ledger resume 已实现并通过 resume consistency QA。

### 重要上下文

- 当前 raw ODS 股票行情层已有 2015 起数据，但策略实际 DWD/DWS 输入层当前从 2019 起；该实验前必须先审计并补齐 2015-2018 策略输入层。
- R14 是 `lightgbm_regression`，训练目标为 `target_return=fwd_xs_ret_5d`；若不做 embargo，2019 年末训练样本会读取 2020 回测期收益形成标签。
- 本轮只写 PRD，未执行 BigQuery / Cloud Run。

### 改动文件

- `docs/prd/PRD_20260609_01_策略1R14长训练回测.md`

### 测试 / 验证

- 未执行。此次为 PRD 与项目记忆更新。

### 阻塞项

- 无代码阻塞。
- 实验执行前需要先做 2015-2018 DWD/DWS、risk feature、market-state 和 5d label embargo 覆盖审计。

### 下一步建议

- 执行 PRD P0-A 只读覆盖审计。
- 若缺 2015-2018 DWD/DWS，制定最小 backfill / rebuild 计划。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - 清理旧 Composer warehouse refresh helper

### 已完成工作

- 删除 `scripts/pipeline/run_warehouse_refresh.py`，避免后续误用 `gcloud composer environments run` 触发已退役的 Composer 环境。
- 更新 OQ-005 约束与交接，明确后续补跑 / QA-only / full rebuild 以 Workflows runbook 和 `orchestration/workflows/**` 为准。

### 重要上下文

- 当前生产调度入口已经是 `Cloud Scheduler + Cloud Workflows`，`ashare-composer` 已删除。
- `orchestration/composer/**` 仍只保留为 retired / audit-only 历史快照；本轮没有改该目录。

### 改动文件

- `scripts/pipeline/run_warehouse_refresh.py`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未执行。此次为删除旧运维 helper 和记忆同步，不跑生产任务。

### 阻塞项

- 无。

### 下一步建议

- 等 PR review；若通过，合并后可继续 OQ-005 cutover 后短观察窗记录。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - Strategy1 live acceptance gate v3 cutover

### 已完成工作

- 将 Cloud Run Python search 默认 acceptance contract 从 `model_acceptance_contract_v1.yml` 切到 `model_acceptance_contract_v3.yml`。
- `orchestrate_sklearn_native_search.py` 在 ADS 写回前接入 v3 replay 已验证的五指数指标计算，按实际 backtest span / manifest final_holdout window 输出候选级 v3 状态和逐指数相对门明细。
- ADS registry / backtest summary 写回新增 v3 contract hash、gate version、primary benchmark、复合年化、Sharpe / Calmar、final_holdout 诊断和五指数相对门摘要。
- `19` QA 改为 v3-aware；`21` risk-feature QA 把旧 risk overlay 限定到 legacy contract。
- 使用 PR #125 分支 smoke 镜像和临时 Cloud Run jobs 跑通 2 候选 live v3 smoke；过程发现 `v3_relative_gate_by_benchmark.csv` 的 `search_id` 列为空，已补 `fetch_topk_ads_outputs` 的 search_id 透传。

### 重要上下文

- owner 已明确后续不再经过 v2；当前切门路径是 v1 -> v3。
- v3 final_holdout 是 diagnostic-only，不再是 hard veto。
- 本轮没有重跑历史 replay，也没有启动新的 Cloud Run search。

### 改动文件

- `configs/strategy1/model_acceptance_contract_v3.yml`
- `configs/strategy1/cloudrun_python_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_pvfq_n30_bw_h5_v0.yml`
- `configs/strategy1/cloudrun_python_riskfeat_lgbm_regression_pvfq_n30_bw_h5_v0.yml`
- `scripts/strategy1_cloudrun/acceptance.py`
- `scripts/strategy1_cloudrun/config.py`
- `scripts/strategy1_cloudrun/orchestrate_sklearn_native_search.py`
- `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`
- `sql/ml/strategy1/21_qa_risk_feature_search_outputs.sql`
- `sql/ml/strategy1/README.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已执行 2 候选 Cloud Run live v3 smoke：`search_id=cloudrun_python_lgbm_v3_live_smoke_20260609_01`，`candidate_count=2`，`top_k=1`。
- 结果：prepare matrix、2 个 candidate fanout、select/register/predict、backtest/report、19 QA 和 artifact upload 均 succeeded；Top-K 1 的 native/v3 status 为 `rejected`，原因 `test_top_minus_bottom<=0;no_comparison_benchmark_passed_v3_relative_gate`。
- registry 验证：`acceptance_contract_version=model_acceptance_contract_v3`、`acceptance_gate_version=strategy1_acceptance_gate_v3`、`primary_benchmark_sec_code=000001.SH`、`v3_relative_gate_evaluated_benchmark_count=5`。
- artifact 验证：`gs://ashare-artifacts/reports/strategy1/ml_pv_clf_v0/search_id=cloudrun_python_lgbm_v3_live_smoke_20260609_01/v3_relative_gate_by_benchmark.csv` 已生成 5 个 benchmark 明细；本轮修复后后续运行会写出非空 `search_id`。

### 阻塞项

- 无代码阻塞。

### 下一步建议

- 等 PR #125 review；若 reviewer 接受 smoke 证据，可以合并。
- 合并后清理临时 `*-pr125-smoke` Cloud Run jobs 和未提交 smoke manifest。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - Workflows Cloud Run Job IAM follow-up

### 已完成工作

- 给 `ashare-workflows-runtime@data-aquarium.iam.gserviceaccount.com` 在 `ashare-ingest-current-scope` Cloud Run Job 上补 `roles/run.jobsExecutorWithOverrides`。
- 给同一 runtime SA 补项目级 `roles/run.viewer`，用于读取 Cloud Run operation / execution 状态。
- 更新 `orchestration/workflows/bootstrap_scheduler_iam.sh`，将 ODS ingestion job 权限从 job-level `roles/run.invoker` 改为 `roles/run.jobsExecutorWithOverrides`，并移除旧 job-level `run.invoker`。
- 更新 `orchestration/workflows/README.md` 与项目记忆，记录真实运行暴露的权限口径。

### 重要上下文

- `roles/run.invoker` 只包含 `run.jobs.run`，不足以支持 workflow 传 overrides 启动 Cloud Run Job。
- `roles/run.jobsExecutorWithOverrides` 允许启动带 overrides 的 Job，但不包含 `run.operations.get`；Workflows 轮询 Cloud Run operation 还需要 `roles/run.viewer`。

### 改动文件

- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 正在用 `ashare_ods_ingestion_daily` manual recovery execution `39e42cbf-c140-4e04-9207-27bfff637ee8` 验证。

### 阻塞项

- 无代码阻塞；等待重跑 execution terminal 状态。

### 下一步建议

- 若重跑成功，继续看 child `ashare_warehouse_window_refresh` 是否完成。
- 合并 IAM bootstrap 修正 PR，避免未来重新 bootstrap 后复现 20:00 权限失败。

### 已更新记忆文件

- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - OQ-005 direct cutover to Scheduler + Workflows

### 本轮完成

- 新增 `orchestration/workflows/bootstrap_scheduler_iam.sh`，把 `ashare-scheduler-invoker` 与 `ashare-workflows-runtime` 当前真实依赖的 IAM 绑定固化为可重放脚本。
- 重写 `orchestration/workflows/deploy_scheduler_jobs.sh`，统一管理 `ashare-pipeline-alert-checker` 与 `ashare-ods-ingestion-daily` 两个 Scheduler jobs。
- 新增 `orchestration/workflows/cutover_scheduler_jobs.sh`，用于 bootstrap IAM、启用 Scheduler jobs，并保持 Composer 业务 DAG paused。
- 已真实执行 cutover：
  - alert-checker scheduler execution `978c920c-3810-4299-b904-3c954e8d221d` succeeded
  - ODS parent execution `31ac0d61-d40c-4a88-9865-b13f61d369c1` succeeded
  - child warehouse execution `919f2aba-b9d4-4181-9915-fa848487bb90` succeeded
- 两个生产 Scheduler jobs 当前都为 `ENABLED`，caller SA 为 `ashare-scheduler-invoker@data-aquarium.iam.gserviceaccount.com`。

### 本轮未做

- 没有删除 Composer 环境。
- 没有执行真实 full rebuild 写路径。

### 影响文件

- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/deploy_scheduler_jobs.sh`
- `orchestration/workflows/cutover_scheduler_jobs.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 阻塞项

- 无新的技术阻塞。
- OQ-005 现在只剩是否保留短期观测窗口，以及何时删除 Composer 环境。

### 下一步建议

- 若不再需要额外观察窗口，下一步就是删除 Composer 环境，停止固定 `Cloud Composer 3 standard milli DCU-hours` 成本。
- 若仍想保守一点，可先观察下一次自然 scheduled ODS run，再删环境。

Model: GPT-5 Codex

## 2026-06-09 GPT-5 Codex - PR #124 runbook review follow-up

### 已完成工作

- 按 PR #124 review，改写 `docs/Pipeline-补跑与故障恢复-Runbook.md`，把 active recovery path 从 Composer / Airflow 改为 Cloud Scheduler + Cloud Workflows。
- Runbook 现在覆盖 ODS 缺采、endpoint 失败、窗口刷新/QA 失败、backfill、非交易日 skip、Scheduler 触发异常、alert checker 异常和 full rebuild。
- 同步更新 `scripts/alerting/README.md` 与 `scripts/alerting/setup_alerts.py`，避免告警链路文档继续提 Composer DAG / Composer 调度异常。

### 重要上下文

- `orchestration/composer/**` 仍只是历史审计目录。
- 当前 active on-call runbook 是 `docs/Pipeline-补跑与故障恢复-Runbook.md`，它现在应该跟 `orchestration/workflows/**` 保持一致。

### 改动文件

- `docs/Pipeline-补跑与故障恢复-Runbook.md`
- `scripts/alerting/README.md`
- `scripts/alerting/setup_alerts.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未执行。此次为文档和告警说明更新，不涉及运行代码路径。

### 阻塞项

- 无。

### 下一步建议

- 继续看 PR #124 是否还有新 comment。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - PR #121 review follow-up

### 本轮完成

- `bootstrap_scheduler_iam.sh` 不再给 `ashare-workflows-runtime` 授项目级 `roles/run.developer`；改为对 `ashare-ingest-current-scope` 单授 job-level `roles/run.invoker`，并在脚本里显式移除旧的项目级 `run.developer` 绑定。
- `cutover_scheduler_jobs.sh` 改为更安全的 staged 顺序：先用 `ENABLE_JOBS=false` 创建/更新 paused Scheduler jobs，再 pause Composer 业务 DAG；只有显式 `RESUME_SCHEDULER_JOBS=true` 才会 resume。
- `README.md`、`KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`OPEN_QUESTIONS.md`、`TODO.md` 已同步更新到新的 least-privilege / staged-cutover 语义。

### 本轮未做

- 没有重新触发 ODS / warehouse scheduler execution。
- 没有处理 review 提到的 lock bucket 前缀最小化问题；当前仍沿用整桶 `roles/storage.objectAdmin`。

### 影响文件

- `orchestration/workflows/bootstrap_scheduler_iam.sh`
- `orchestration/workflows/cutover_scheduler_jobs.sh`
- `orchestration/workflows/README.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 下一步建议

- 运行更新后的 `bootstrap_scheduler_iam.sh`，把 live runtime SA 真的收敛到 job-level `run.invoker`。
- PR 合并后，再单独决定是否要为 lock 前缀拆专用 bucket / IAM condition，随后删除 Composer 环境。

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - Composer historical directory cleanup

### 已完成工作

- 将 `orchestration/composer/README.md` 从“可操作 Composer runbook”改成 retired / audit-only 说明，明确 `ashare-composer` 已删除，当前生产入口只保留 `orchestration/workflows/**`。
- 主动移除了 README 里针对已删除 Composer 环境的同步、触发、变量和手工操作命令，避免后续误操作。
- 给 `orchestration/composer/dags/ashare_common.py` 与 5 个 Composer DAG 顶部都加了 retired 标识，明确这里只保留历史快照，不再接受新的生产逻辑。

### 重要上下文

- 这次没有改任何调度语义，也没有重新部署或 smoke。
- 目标只是收口仓库内“哪些 Composer 资产继续保留、哪些路径已经彻底退出生产”的边界。
- 当前生产入口仍然是 `Cloud Scheduler + Cloud Workflows`，不是 Composer。

### 改动文件

- `orchestration/composer/README.md`
- `orchestration/composer/dags/ashare_common.py`
- `orchestration/composer/dags/ashare_daily_pipeline_v0.py`
- `orchestration/composer/dags/ashare_ods_ingestion_daily.py`
- `orchestration/composer/dags/ashare_pipeline_alert_checker.py`
- `orchestration/composer/dags/ashare_warehouse_full_rebuild.py`
- `orchestration/composer/dags/ashare_warehouse_window_refresh.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 未执行。此次为文档/标识清理，不涉及行为变更。

### 阻塞项

- 无。

### 下一步建议

- 若要继续收口 OQ-005，可补一条 cutover 后短观察窗记录，然后把这部分也归档到 OQ-005 完成态。
- 若后续还要碰调度实现，直接改 `orchestration/workflows/**`，不要再在 Composer 目录叠加新逻辑。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex

## 2026-06-08 GPT-5 Codex - TODO cleanup

### 已完成工作

- 将 `TODO.md` 从长版状态流水重写为短版行动清单。
- 删除已完成历史、重复背景和大量上下文，只保留当前仍需执行的事项。
- 保留的主线现在只有：OQ-005 补短观察窗记录、OQ-010 accepted Python baseline、OQ-012 关闭/保留决策，以及少量 P1 优化项。

### 重要上下文

- 这次没有改代码、没有改调度语义，只是收口任务视图。
- 历史完成记录统一以 `IMPLEMENTATION_STATUS.md` / `AGENT_HANDOFF.md` 为准，不再堆在 `TODO.md` 里。

### 改动文件

- `TODO.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未执行。此次为任务清单精简，不涉及行为变更。

### 阻塞项

- 无。

### 下一步建议

- 若继续收口 OQ-005，先补 cutover 后短观察窗记录。
- 若转回策略主线，直接继续 OQ-010 accepted baseline 探索。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

Model: GPT-5 Codex


---

## Handoff - 2026-06-09 - Cloud Run ledger resume implementation start

- Model: GPT-5 Codex
- Branch/worktree: `codex/prd-cloudrun-ledger-resume` / `/Users/fisher/Desktop/git/quant-ashare-ledger-resume-prd`
- Owner request: 在 PR #127 分支上开始实现 Cloud Run Python ledger resume。
- Changed: added resume fields to Strategy1 experiment config/CLI params; added Cloud Run Python ledger state persistence and parent-state restore path; added ADS state table DDL; updated SQL contract defaults/QA for `rebalance_anchor_start` and `cloudrun_lot100_resume_v1`; added full-vs-resume QA SQL.
- Validation: not run per owner workflow unless explicitly requested.
- Next: review PR #127 comments/CI after push; then run targeted unit/SQL/Cloud Run smoke only if owner asks.


---

## Handoff - 2026-06-10 - PR #127 ledger resume review follow-up

- Model: GPT-5 Codex
- Branch/worktree: `codex/prd-cloudrun-ledger-resume` / `/Users/fisher/Desktop/git/quant-ashare-ledger-resume-prd`
- Owner request: 看 PR #127 comment；认可实现 review 中的 6 个问题并直接修复。
- Changed: fixed missing imports/constants/dataclass fields, wired resume manifest/CLI/SQL params into `LedgerParams`, replaced fresh-only fail-fast with lot100 parent-state restore, added ledger state writes/deletes, corrected resume policy and rebalance anchor QA, and fixed `25_qa_cloudrun_ledger_resume_outputs.sql` to use `ashare_ads` plus current ADS trade/nav columns.
- Validation: not run per owner workflow unless explicitly requested.
- Next: review PR #127 comments/CI after push; run targeted unit tests and a small full-vs-resume smoke only if owner asks.

## 2026-06-10 - Strategy1 回测复合年化收益 PRD

日期: 2026-06-10
Agent ID: Codex
Agent 实例 ID: 当前 Codex desktop session
模型: GPT-5 Codex
运行环境: `/Users/fisher/Desktop/git/quant-ashare-compound-annual-prd`
Run ID: doc-only
相关 issue/PR: 待创建 PR

### 已完成工作

- 新增 `docs/prd/PRD_20260610_01_策略1回测复合年化收益.md`。
- PRD 定义新增 `compound_annual_return`、`return_period_count`、`annualization_target_period_count`、`annualization_method`，并要求旧 `annual_return` 保留为 legacy。
- PRD 明确后续 report、diagnosis、v3 acceptance gate、replay QA 默认读复合年化口径；v3 缺复合字段不得 fallback 到 legacy 年化后通过。
- 根据 PR #134 review 补充：`return_period_count` 固定为 NAV 有效交易日数减 1；compound Sharpe 会系统性影响阈值，启用前需 replay 差异表和 owner 阈值确认；`select_register_predict.py` 纳入 registry 指标传播影响面。
- 更新 `TODO.md` 和 `IMPLEMENTATION_STATUS.md`。

### 重要上下文

- owner 已确认项目中年化 / 月化 / 日化默认按复利口径。
- 近期 R14 长训练回测暴露 `ads_backtest_performance_summary.annual_return` 与按 NAV 交易日数补算的复合年化不同，需避免后续混用。
- 本次 PRD 是后续代码实现前置说明，不改变任何历史 backtest artifact。

### 改动文件

- `docs/prd/PRD_20260610_01_策略1回测复合年化收益.md`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- 未运行测试；文档-only 变更。

### 阻塞项

- 无。后续是否批量回填历史 run 的复合年化字段需要 owner 决策。

### 下一步建议

1. review PRD。
2. 另开实现 PR，扩展 summary schema / SQL / report / v3 acceptance / QA。
3. 用一个小规模 backtest smoke 验证 `compound_annual_return` 可从 NAV 重算。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

## 2026-06-10 - Strategy1 年度滚动选参动态 CV fold 修复

日期: 2026-06-10
Agent ID: Codex
Agent 实例 ID: codex/fix-dynamic-cv-folds
模型: GPT-5 Codex
运行环境: local worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-dynamic-cv`
Run ID: n/a
相关 issue/PR: pending

### 已完成工作
- 修复 Strategy1 Cloud Run Python CV fold 硬编码 `2021/2022/2023` 的问题，改为基于当前 `cv_panel` 的 train 年份动态生成最多 3 个 rolling fold。
- 新增单元测试覆盖年度滚动选参窗口 `2015-2019 train + 2020 valid` 应生成 `cv_2017/cv_2018/cv_2019`，以及旧搜索窗口完整边界仍保持 `2019-04-03..2023-12-31 -> cv_2021/cv_2022/cv_2023`。

### 重要上下文
- 2021 annual-selection smoke 暴露 `cv_fold_count=0`，原因是 CV panel 实际覆盖 `2015-2020`，但旧代码固定寻找 `2021/2022/2023` eval 年。
- 本修复只解决 CV fold 生成口径；不改变 valid/test/backtest gate，也不实现 selected final refit 云端化。

### 改动文件
- `scripts/strategy1_cloudrun/train_predict.py`
- `tests/strategy1_cloudrun/test_dynamic_cv_folds.py`
- `TODO.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证
- `python3 -m pytest tests` 34 passed。

### 阻塞项
- 无。

### 下一步建议
- 合并后重跑 2021 annual-selection smoke 的 candidate fanout，确认 `cv_fold_count=3` 且 CV 指标不再为 NULL/NaN。
- 后续单独实现 selected final refit 云端化，避免本地下载大 matrix。

### 已更新记忆文件
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `TODO.md`

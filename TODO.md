# TODO

本文件只保留“下一步可执行事项”。整体状态和历史完成记录见 `.agent/memory/IMPLEMENTATION_STATUS.md` / `.agent/memory/AGENT_HANDOFF.md`；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源。

维护规则见 `AGENTS.md` 的「TODO 维护协议」。

## P0 — 当前优先

- [ ] 补 P0 通用 DWS 扩展表：`dws_market_state_daily`、后续策略共用市场状态特征（`dws_stock_feature_fin_daily` 已落地）
- [ ] 实现 OQ-010 交易成本 profile：按 `PRD_20260602_02_OQ010交易成本口径.md` 将 runner 从单一 `p_cost_bps=30` 升级为佣金万一免五、卖出印花税 5 bps、买/卖滑点各 5 bps，并同步 08/09/10/report/README
- [ ] 策略 1 runner v0 模型质量与参数迭代（OQ-010）：特征 / 标签 / 选股口径、调仓频率、持股数 / 单票权重上限
- [ ] 准备 GCS bucket（`ashare-artifacts`）+ ADC，去掉 `--skip-gcs-upload` 重跑 report render，产出 uploaded 模式真实 `report_uri`

## P1 — 数据 / 特征扩展

- [ ] 三大报表单季派生（`income`/`cashflow` 累计转单季 `q_*`）作为 P1 财务表内容（OQ-003 PRD §4 推荐延后）
- [ ] `dim_stock_sw_industry_hist`（source `index_member_all`，按 `in_date/out_date` 建申万行业时点归属，并 QA 区间重叠 / 缺口）
- [ ] `dim_stock_ci_industry_hist`（source `ci_index_member`，中信行业时点归属，对照体系）
- [ ] `dwd_sw_industry_eod` + 行业中性化
- [ ] P1+ 资金面 / 事件 / 行业族 DWD：moneyflow、margin、hk_hold / ccass、龙虎榜、股东增减持、质押回购、业绩预告 / 快报、分红、分析师报告等；新增 DWD 前先按 OQ-006 补单位映射
- [ ] `dim_index_weight`、`dim_sw_industry`、`dim_ipo`
- [ ] 补 lookback-capable 价格构建输入或调整 DWD/DWS 构建方式，使 2019-01 起 60 日窗口可直接读取 2018 buffer；当前策略 1 DWS 用 `has_full_history_60d=FALSE` 标记并默认剔除不完整窗口样本（OQ-011）

## 工程 / 调度

- [ ] OQ-005 物化选型：dbt（persist_docs）还是纯 `bq` SQL + 自建调度
- [ ] 将 `lookback_start_date` 从固定默认值升级为按最大滚动窗口计算 / 调度配置
- [ ] 写“从 ODS 继承字段描述”脚本（`bq show` -> 映射 -> `bq update`）
- [ ] 增量调度（dbt 或 Airflow + SQL）与数据质量断言

## 近期完成

- [x] OQ-010 交易成本口径 PRD 已新增：佣金万一免五、卖出印花税 5 bps、买/卖滑点各 5 bps；代码实现仍需后续 PR
- [x] PR #13 / OQ-003 财务三表 DWD + DWS 已合并：`dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`（+ `_latest`）、`dws_stock_feature_fin_daily`、`sql/qa/04_finance_caliber_checks.sql` 已进入 `main`；已随表补全 `ods_field_unit_map` 财务字段映射并跑通 `sql/qa/05_oq006_unit_checks.sql`
- [x] OQ-006 单位契约实现已合并（PR #16）：`ashare_meta.ods_field_unit_map`、`sql/qa/05_oq006_unit_checks.sql`、`dwd_index_eod` 换算修复与 `volume_share/amount_cny` 迁移已进入 `main`，OQ-006 已关闭
- [x] 合并 OQ-006 PRD（PR #14）：`docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- [x] 策略 1 BigQuery ML runner 已于 PR #12 在 BigQuery 端到端实跑并通过 `10_qa_runner_outputs.sql`（16 断言）
- [x] OQ-004 基准指数代码可用性已实现并关闭（`dim_index` + 映射驱动 `dwd_index_eod` + OQ-004 QA + runner benchmark 窗口校验）
- [x] OQ-007 退市日类型已复核并关闭，PR #9 后依赖链已重建并通过 P0 / 策略 1 QA

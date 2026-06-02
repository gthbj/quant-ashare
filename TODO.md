# TODO

本文件只保留“下一步可执行事项”。整体状态和历史完成记录见 `.agent/memory/IMPLEMENTATION_STATUS.md` / `.agent/memory/AGENT_HANDOFF.md`；待 owner 决策的问题以 `.agent/memory/OPEN_QUESTIONS.md` 为唯一来源。

维护规则见 `AGENTS.md` 的「TODO 维护协议」。

## P0 — 当前优先

- [ ] 按已确认的 OQ-006 PRD 实现 `ashare_meta.ods_field_unit_map`、P0 + PR #13 首批单位映射 seed、`sql/qa/05_oq006_unit_checks.sql`、`dwd_index_eod.volume/amount` -> `volume_share/amount_cny` 迁移，并更新 DWD-DIM / README / `KNOWN_CONSTRAINTS.md`
- [ ] 处理 PR #13 / PRD03 财务三表落地前的单位契约依赖：财务三表合并前必须随表补单位映射和 OQ-006 QA，或显式依赖 OQ-006 最小实现先落地
- [ ] 合并 / 落地 PRD03（OQ-003 财务三表 DWD/DWS）：按默认合并报表口径补 `dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`、单季派生、财务特征 DWS 和对应 QA
- [ ] 补 P0 通用 DWS 扩展表：`dws_stock_feature_fin_daily`、`dws_market_state_daily`、后续策略共用的财务 / 市场状态特征
- [ ] 策略 1 runner v0 模型质量与参数迭代（OQ-010）：特征 / 标签 / 选股口径、成本、调仓频率、持股数 / 单票权重上限
- [ ] 准备 GCS bucket（`ashare-artifacts`）+ ADC，去掉 `--skip-gcs-upload` 重跑 report render，产出 uploaded 模式真实 `report_uri`

## P1 — 数据 / 特征扩展

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

- [x] 合并 OQ-006 PRD（PR #14）：`docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`
- [x] 策略 1 BigQuery ML runner 已于 PR #12 在 BigQuery 端到端实跑并通过 `10_qa_runner_outputs.sql`（16 断言）
- [x] OQ-004 基准指数代码可用性已实现并关闭（`dim_index` + 映射驱动 `dwd_index_eod` + OQ-004 QA + runner benchmark 窗口校验）
- [x] OQ-007 退市日类型已复核并关闭，PR #9 后依赖链已重建并通过 P0 / 策略 1 QA

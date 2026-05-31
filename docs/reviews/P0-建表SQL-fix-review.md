> 文档维护：Claude Opus 4.8（2026-05-31）

# P0 建表 SQL 修复评审（commit d810ec4）

## 评审对象

- Commit `d810ec4` "fix: 完善 P0 建表 SQL 并物化验证"。
- 范围：对首轮评审 R1–R5 的修复 + 新增 `dwd_fin_indicator_latest`、`sql/qa/01_p0_smoke_checks.sql`、`dwd_index_eod` 单位修正。
- 方式：静态审查 + BigQuery 物化表实跑验证。

---

## 🟡 F1. 897 行盘中临时停牌被标 `is_suspended=TRUE` + `is_tradable=FALSE`

- 位置：`sql/dwd/01_dwd_stock_eod_price.sql`，`is_suspended` 表达式 `d.close IS NULL OR IFNULL(d.volume_lot,0)=0 OR e.sec_code IS NOT NULL`。
- 问题：第三分支把**盘中临时停牌**（`suspend_type='S'` 但 `suspend_timing` 为 `'13:00-13:10'` / `'09:30-10:00'` 等短时段）也判为停牌。BQ 实跑确认 897 行 `is_suspended=TRUE` 但 `close IS NOT NULL` 且 `volume_lot>0`，全部为盘中临停。这些股票当天正常开盘收盘、正常成交，只是盘中被暂停了几分钟到半小时。
- 影响：连锁导致 `is_tradable=FALSE`、`can_buy_open=FALSE`、`can_sell_open=FALSE`。对「t+1 开盘建仓」基准假设，这些股票开盘可买卖，标为不可交易会误踢样本（897/850 万 = 0.01%，但都是异常波动日，信号密度高）。
- 建议（两选一，需 owner 定夺）：
  - **A. 过滤掉非全天停牌**：`suspend_event` 加条件排除 `suspend_timing` 为短时段的行（需确认格式稳定性）。
  - **B. 改 `is_suspended` 语义**：`e.sec_code IS NOT NULL` 分支仅在 `close IS NULL` 时才判定停牌，盘中临停单独用 `has_intraday_halt` 布尔字段记录，不影响 `is_tradable`。

## 🔵 F2. `dwd_fin_indicator_latest` 排序键与方案 §4.4② 不一致

- 位置：`sql/dwd/05_dwd_fin_indicator_latest.sql:17`。
- 现 SQL：`ORDER BY ann_date_eff DESC, update_flag DESC, ingested_at DESC, source_partition_date DESC`
- 方案 §4.4②：`ORDER BY update_flag DESC, ann_date_eff DESC, ingested_at DESC`
- 差异：`update_flag` 与 `ann_date_eff` 的优先级反了。方案把 `update_flag` 放首位，语义是「修正版无条件覆盖原版」；当前 SQL 把 `ann_date_eff` 放首位，语义变成「更晚的公告日优先，同日才看 `update_flag`」。
- 影响：多数情况下结果相同（修正版公告日通常更晚），但「修正版 `ann_date_eff` 与原版相同」的边缘 case 下可能取到原版。
- 建议：改为 `ORDER BY update_flag DESC, ann_date_eff DESC, ingested_at DESC, source_partition_date DESC`。

---

## 结论

首轮 R1–R5 全部修复到位，BigQuery 物化表数据质量通过实跑验证，可推进 DWS。F1（盘中临停语义）和 F2（latest 排序键）均非阻塞，由 owner 决定是否处理。

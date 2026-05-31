> 文档维护：Claude Opus 4.8（2026-05-31）

# P0 建表 SQL 评审（DIM/DWD v0 骨架）

## 评审对象

- Commit `9942f14` "feat: 添加 DWD DIM 建表 SQL"。
- 范围：`sql/` 下 P0 最小骨架 —— `00_create_datasets.sql`、3 张 DIM（`dim_trade_calendar` / `dim_stock` / `dim_stock_name_hist`）、4 张 DWD（`dwd_stock_eod_price` / `dwd_stock_eod_valuation` / `dwd_fin_indicator` / `dwd_index_eod`）、`README.md`。
- 定位（owner 说明）：能先跑通 2019+ 日线样本的核心骨架，**不是**完整 54 表 ODS→DWD/DIM 覆盖。
- 对照基准：`docs/数据仓库建模方案-DWD-DIM.md`（§3.3 / §4.3 / §4.4 / §4.6 / §6.5 / §7.3）、`.agent/memory/{KNOWN_CONSTRAINTS,DECISION_LOG}.md`。
- 方式：静态审查，**未在 BigQuery 实跑**；涉及数据取值域的判断已标注「需验证」。

## 总评

骨架干净，与方案口径基本一致：命名（`sec_code` / 单位元·股 / `_hfq` / 血缘 `source_system`·`ingested_at`）、月分区 + `sec_code` 聚簇、行情表 `require_partition_filter`、停牌「交易日历 × 在市」骨架、`ret_1d` 的 lookback warm-up、财务 PIT 的 `ann_date_eff` / `visible_trade_date` 均已落到位。下列按严重度列出待处理项；🔴 两项建议**物化前先修**，🟡 三项随 QA 补。

---

## 🔴 物化前必修

### R1. `bq query` 命令缺 `--location=asia-east2`

- 位置：`sql/README.md` 执行顺序段；`sql/00_create_datasets.sql`。
- 问题：`00_create_datasets.sql` 不引用任何已存在数据集，bq 无法从被引用表自动推断 location，默认会落到 `US`；而脚本 OPTIONS 里写死 `location='asia-east2'`，job 区域与目标区域不一致会报错。后续 CTAS 读 `ashare_ods`（asia-east2），若 job 跑在 US 则跨区域读取直接失败。
- 现状之所以「没炸」：目标数据集此前已存在于 `asia-east2`（见 `AGENT_HANDOFF`），`00` 成了 no-op，其余脚本靠 bq 对被引用表的自动区域推断侥幸命中——但这是**环境依赖且未文档化**，换环境即失败。
- 建议：README 每条 `bq query` 显式加 `--location=asia-east2`，并在文首说明默认区域。

### R2. `suspend_d` 未按停复牌过滤，复牌日可能被误判停牌

- 位置：[`sql/dwd/01_dwd_stock_eod_price.sql:74`](../../sql/dwd/01_dwd_stock_eod_price.sql)（`suspend_event` CTE）、`:110`（`is_suspended` 表达式）。
- 问题：`suspend_event` 不按 `suspend_type` 过滤；`is_suspended = d.close IS NULL OR IFNULL(d.volume_lot,0)=0 OR e.sec_code IS NOT NULL`，其中第三个分支**只看「当天这只股票在 suspend_d 里有没有任意一条记录」，不区分停牌(S)/复牌(R)**。
- Tushare `suspend_d` 的 `suspend_type`：`S`=停牌、`R`=复牌。复牌当天会有一条 `R` 记录，而复牌日恰是股票**重新正常交易**之日（daily 有行、`close` 非空、`volume>0`，前两个分支都为 FALSE）——于是唯一翻成 `is_suspended=TRUE` 的就是那条 `R`，连锁导致 `is_tradable=FALSE`、`can_buy_open/can_sell_open=FALSE`。

  | 日期 | daily 有行 | suspend_d | 当前判定 | 正确性 |
  |---|---|---|---|---|
  | 停牌期间 | 否 | S | `close IS NULL` → 停牌 | ✅ |
  | **复牌日** | 是，正常成交 | **R** | `e.sec_code IS NOT NULL` → 停牌 | ❌ 应为可交易 |

- 影响：复牌日往往是信息释放、价格跳空的关键样本，被错误屏蔽会丢样本 / 错位 `t+1` 建仓 / 误判开盘不可建仓。
- 附带洞察：该分支对**全天停牌冗余**（已被 `close IS NULL` 覆盖），真正价值仅在「盘中临时停牌」（当天有成交、daily 有行）；代价却是制造复牌日假阳性。
- 需验证（owner / 下一步实跑）：本套 ODS 的 `suspend_d.suspend_type` 实际取值域，以及 `R` 行 `trade_date` 当天 daily 是否正常成交。
  ```sql
  SELECT suspend_type, COUNT(*) AS n
  FROM `data-aquarium.ashare_ods.ods_tushare_suspend_d`
  WHERE endpoint = 'suspend_d'
    AND partition_date BETWEEN '20190101' AND '20191231'
  GROUP BY suspend_type;
  ```
- 建议：确认含 `R` 后，在 `suspend_event` 的 `WHERE` 加 `AND suspend_type = 'S'`（仅保留停牌行）。

---

## 🟡 建议处理（QA 时补）

### R3. `dwd_fin_indicator` 缺版本键精确去重兜底

- 位置：[`sql/dwd/03_dwd_fin_indicator.sql`](../../sql/dwd/03_dwd_fin_indicator.sql)。
- 说明：保留所有公告版本是**有意设计**（方案 §4.4① 版本事实表 / DECISION-20260531-09，「不在此去重」，去重交消费侧 as-of）。**非 bug。**
- 缺口：方案版本键是 `(sec_code, report_period, ann_date_eff, update_flag)` **+ `ingested_at` 兜底**；当前脚本无任何 `QUALIFY`，重跑 / 重摄入会产生**完全相同行的重复**（对照 `dim_stock_name_hist` 是加了 `QUALIFY` 去重的）。
- 建议：按版本键加 `QUALIFY ROW_NUMBER() OVER (PARTITION BY 版本键 ORDER BY ingested_at DESC)=1`，只去重复行、不动多版本。

### R4. `dim_stock` 稳健性

- 位置：[`sql/dim/02_dim_stock.sql`](../../sql/dim/02_dim_stock.sql)。
- (a) `missing_from_stock_basic` 用 `last_trade_date < CURRENT_DATE` 判退市（`:133`）：对「仅缺在 stock_basic 快照、实际仍在市」的股票，几乎任何非当日已入库的日子都会被误判退市并给出 `delist_date`，在价格 universe 里被提前截断。该分支是数据缺口兜底（已知缺口 4 码：`000022.SZ` / `000043.SZ` / `300114.SZ` / `920218.BJ`），概率低但 heuristic 偏脆。
- (b) `sec_code` 无唯一性保证：若同一 `ts_code` 同时出现在 `stock_basic_listed` + `stock_basic_delisted` 最新快照，会出两行 → 价格 universe JOIN 扇出 → 价格表主键翻倍。
- 建议：物化后加 `sec_code` 唯一性断言；复核退市 heuristic。

### R5. 缺配套 `dwd_fin_indicator_latest`

- 说明：方案 §4.4② / §6.5 / §7.3 把「版本事实表 + 最新快照表」作为标准成对产物，本批只建了版本表。
- 建议：补建每期最新版便捷表 `dwd_fin_indicator_latest`（回测仍用版本表做 as-of，避免泄漏后期修正）。

---

## 🔵 与既有决策的一致性核对（非问题）

- `visible_trade_date` 取 `MIN(cal_date) WHERE is_open AND cal_date >= ann_date_eff`：与 DECISION-20260531-04 / 方案 §4.3「当日为交易日则取当日，否则右移到下一开市日」一致，匹配「盘后 EOD → t+1 建仓」基准假设。**正确。**
- `can_buy_open` / `can_sell_open` 仅开盘侧方向字段：与 DECISION-20260531-09 / P1-3「只加开盘侧、不加收盘四象限」一致。
- 财务版本事实表保留全部公告版本：与 DECISION-20260531-09 一致（见 R3）。
- 评审未发现与任何 `active` 决策冲突。

## 范围说明（非问题，供 owner 确认）

- 本批只覆盖财务 `fina_indicator`；方案 §4.6 路线把 `income`/`balancesheet`/`cashflow` 也列为财务 P0，v0 暂缓——确认是有意延后即可。
- `dwd_index_eod`：STAR50(`000688`)、CSI1000(`000852`)未纳入 `index_dailybasic` 端点，估值字段恒 NULL（LEFT JOIN 已兜住）；指数 `volume`/`amount` 未做单位归一（归 OQ-006）。

## 结论

骨架可继续推进物化。**物化前先处理 R1、R2**（影响「能否跑通」与「可交易掩码正确性」）；R3–R5 随首次 QA 一并补。以上发现是否转为 `OPEN_QUESTIONS` / `TODO` 条目，由 owner 决定。

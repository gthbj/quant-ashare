# 评审：数据仓库建模方案-DWS-ADS.md

> 评审对象：`docs/数据仓库建模方案-DWS-ADS.md`（GPT-5，2026-05-31）
> 参照基准：`docs/数据仓库建模方案-DWD-DIM.md`（DWD/DIM 权威口径）
> 评审人：Claude Opus 4.6（2026-06-01）

---

## 发现清单

### P0（影响正确性 / PIT 安全）

**P0-1. 财务 as-of SQL 缺少 `update_flag` 排序，可能选到旧版本**

§4.4 `dws_stock_feature_fin_daily` 的 as-of SQL：

```sql
ORDER BY fi.report_period DESC, fi.ann_date_eff DESC, fi.ingested_at DESC
```

DWD-DIM §4.4 明确要求去重顺序为 `update_flag DESC, ann_date_eff DESC, ingested_at DESC`。DWS 的 as-of 虽然粒度不同（PARTITION BY 包含 `trade_date`），但仍需要在同一 `(sec_code, report_period, ann_date_eff)` 下取最新修正版。缺少 `update_flag DESC` 会导致：当同一报告期、同一公告日存在多个修正版本时，ORDER BY 仅靠 `ingested_at` 兜底，如果 ingestion 顺序与 `update_flag` 不一致，就会选中旧版本。

**建议**：ORDER BY 改为 `fi.report_period DESC, fi.ann_date_eff DESC, fi.update_flag DESC, fi.ingested_at DESC`。

---

**P0-2. 财务 as-of SQL 未过滤 `report_type`，可能混合合并/母公司报表**

§4.4 的 as-of SQL 对 `dwd_fin_indicator` 做 LEFT JOIN 时没有 `report_type` 过滤条件。DWD-DIM §4.4 说"按需先过滤 `report_type`（合并报表通常取 `'1'`）"，§6.5 也说三大报表"额外按 `report_type`（通常 `'1'` 合并报表）过滤"。

如果 `dwd_fin_indicator` 版本事实表保留了所有 `report_type`，DWS as-of 不过滤就会在同一 `(sec_code, report_period)` 下把合并报表与母公司报表混在一起比较 `ann_date_eff`，可能选中母公司口径。

**建议**：as-of SQL 增加 `AND fi.report_type = '1'`（或参数化 `@report_type`）；至少在文档中显式标注"DWS 默认消费合并报表口径"。

---

### P1（影响一致性 / 可运维性）

**P1-1. `board` vs `board_type` 字段名不一致**

§4.1 `dws_stock_universe_daily` 字段表写 `board`（"来自 `dim_stock`"），但 DWD-DIM §5.2 `dim_stock` 的实际字段名是 `board_type`。DWD-DIM §3.3-A 数据字典也定义为 `board_type`。

**影响**：下游代码按哪个名字写 SQL 会取决于看哪份文档；实际建表时只能有一个名字。

**建议**：统一为 `board_type`，与 DWD-DIM 数据字典一致。

---

**P1-2. DWS 物理设计未提及 `require_partition_filter`**

§2.3 物理设计表列出了分区和聚簇策略，但未提及是否开启 `require_partition_filter = TRUE`。DWD-DIM §4.6 对行情类 DWD 明确要求此选项"杜绝误扫全史"。DWS 股票日频表（feature、label、sample）同为按月分区的大表（2019+ 约 84 个月 × 5000+ 股），不开强制过滤的话，下游 ADS 或临时查询可能误扫全量。

**建议**：§2.3 补充：DWS 股票日频表（`dws_stock_feature_*_daily`、`dws_stock_label_daily`、`dws_stock_sample_daily`）建表时设 `require_partition_filter = TRUE`；财务 as-of 类（如果有物化中间表）不开。

---

**P1-3. `market_regime` 无计算口径定义**

§4.5 `dws_market_state_daily` 列出 `market_regime` 字段，值为 `risk_on/risk_neutral/risk_off`，但没有任何计算规则——是基于指数回撤、波动率阈值、均线交叉，还是聚类/HMM？§4.7 将其列为 P0 宽表特征，意味着 P0 建表时就需要定义。

**影响**：如果开发者自行定义规则，不同实现之间不可复现，也无法审计。

**建议**：给出默认规则（例如"CSI500 收盘 < MA60 且 20 日波动率 > 历史 75 分位则 risk_off"）或明确标注为"待 owner 定义，P0 先置 NULL 或不产出"。

---

**P1-4. 回测绩效汇总表 `ads_backtest_performance_summary` 缺少基准标识**

§6.3 该表有 `excess_annual_ret`、`information_ratio` 等相对指标，但字段列表中没有 `benchmark_code`/`benchmark_id`。不知道用的是沪深 300、中证 500 还是等权指数，这些指标无法解读。

**建议**：增加 `benchmark_code STRING` 字段（或 `benchmark_config_json`），让每个回测的超额收益口径可追溯。

---

**P1-5. 指数代码映射 `399300.SZ → 000300.SH` 应在 DWD 层解决**

§4.5 提到"已知 ODS 中沪深 300 通过 `399300.SZ` 端点存在，DWD 可映射到 canonical `000300.SH`；正式使用前仍需核对"。这个映射如果留到 DWS 做，会导致 DWD `dwd_index_eod` 与 DWS 的 canonical code 不一致，下游所有按 `sec_code` join 指数的逻辑都需要知道映射关系。

**建议**：明确此映射在 DWD `dwd_index_eod` 建表时统一处理（即 ODS `ts_code` → canonical `sec_code` 在 DWD 出口归一，与个股同理），DWS 文档只引用 canonical code。同时在 DWD-DIM 文档 §6.4 或 OPEN_QUESTIONS 中登记此项。

---

### P2（影响清晰度 / 可操作性）

**P2-1. 版本字段 scheme 未定义**

§2.4 定义了 `feature_version`、`label_version`、`universe_version` 等版本字段，但未说明版本号格式——是 semver（`v1.0.0`）、日期戳（`20260601`）、hash、还是自由文本？生产中如果没有统一 scheme，不同运行之间版本比较和回溯会混乱。

**建议**：定义默认 scheme，例如 `v{major}.{minor}`（`v0.1` 表示 P0 首版），或 `YYYYMMDD_NN`；并约定何时 bump major/minor。

---

**P2-2. `industry_tushare_raw` 在 DWD-DIM 中不存在**

§5.3 提到"dim_stock.industry 仅保留为粗口径兜底字段 `industry_tushare_raw`"。但 DWD-DIM §5.2 `dim_stock` 的字段名是 `industry`（直接取自 Tushare `stock_basic`），并没有改名为 `industry_tushare_raw`。

**影响**：如果 DWS SQL 写 `industry_tushare_raw`，而 DWD 实际是 `industry`，建表会报错。

**建议**：使用 DWD-DIM 已定义的 `industry`，在 DWS 文档中注明"来自 `dim_stock.industry`（Tushare 粗口径，不作标准行业分类依据）"即可。

---

**P2-3. universe 表含前瞻字段但未明确标注不可用作特征**

§4.1 `dws_stock_universe_daily` 包含 `can_buy_next_open` 和 `can_sell_next_open`，文档正确说明了它们来自 `t+1` 价格 DWD。但这些字段与同表中的 `is_suspended`、`is_st` 等 `t` 日可见字段混在一起，没有分组或标注区分。

**影响**：下游开发者可能误将 `can_buy_next_open` 当作特征输入模型（这是未来信息泄露）。

**建议**：在字段表中增加一列"PIT 可见性"（`t` 日可见 / `t+1` 前瞻），或在字段口径中加注"仅用于标签掩码和回测执行，禁止用作训练特征"。

---

**P2-4. `dws_stock_feature_daily_v0` 未说明特征宽表的 JOIN 方式**

§4.7 将多族特征合并为 P0 宽表，包含市场状态字段（`market_regime`、`csi500_ret_20d`、`adv_ratio_1d`）。这些字段粒度是 `trade_date`，而宽表粒度是 `(sec_code, trade_date)`。文档未说明这是通过 `trade_date` 单键 broadcast join 实现的。

**建议**：补一句"市场状态字段通过 `trade_date` 单键 join，同一天所有股票共享相同值"。

---

## 未发现冲突的既有决策核对

以下 DWD-DIM 关键决策在 DWS-ADS 中正确延续，无需列入评审文档（按评审协议§六仅列问题）：PIT 基准假设（t 日盘后→t+1 建仓）、后复权口径、sec_code 统一主键、元/股量纲、按月分区+sec_code 聚簇、标签用市场交易日序列、版本事实表 as-of 模式。

---

## 结论

DWS-ADS 方案整体架构合理，分层定位清晰，与 DWD-DIM 设计衔接良好。主要问题集中在 **P0 财务 as-of SQL 的两处遗漏**（`update_flag` 排序和 `report_type` 过滤），会直接影响 PIT 正确性；其余为命名一致性和可操作性细节。建议优先修复 P0-1、P0-2 后即可进入建表阶段。

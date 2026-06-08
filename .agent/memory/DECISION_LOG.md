# 决策日志（Decision Log）

记录持久的项目决策。条目简短，不记录临时讨论。

## 决策格式

```md
## DECISION-YYYYMMDD-NN: <标题>

Date:
Status: active | superseded
Owner:
Context:
Decision:
Rationale:
Impact:
Related files:
```

## DECISION-20260531-01: 三层数仓分层

Date: 2026-05-31
Status: active
Owner: owner
Context: 基于 `ashare_ods` 外部表构建量化可用的数据底座。
Decision: 采用 `ashare_dim`（维度）+ `ashare_dwd`（明细）→ `ashare_dws`（特征/标签）三层，ODS 只裁剪不清洗。
Rationale: 职责分离；DWD 承接清洗/复权/PIT，DWS 直接喂模型。
Impact: 下游一律查 DWD/DIM，不再直接打 ODS。
Related files: docs/数据仓库建模方案-DWD-DIM.md §3

## DECISION-20260531-02: 证券主键统一为 sec_code（数据源中性）

Date: 2026-05-31
Status: active
Owner: owner
Context: 未来数据源不一定是 Tushare，`ts_code` 把数据源焊进字段名。
Decision: DWD/DIM 统一用 `sec_code`（值标准格式 `600000.SH`，`.SH/.SZ/.BJ`）；源字段 `ts_code/con_code/code/index_code` 在出口归一；保留 `sec_symbol` 展示、`sec_type` 分品种。
Rationale: 中性、语义准、自然键用 `_code`。
Impact: 读 ODS 的 SQL 仍用 `ts_code`，仅出口 `ts_code AS sec_code`；换数据源时在接入层统一值格式。
Related files: docs §3.3, §4.1, 附录B

## DECISION-20260531-03: 量纲统一元/股

Date: 2026-05-31
Status: active
Owner: owner
Context: Tushare 各接口单位不一（手/千元/万股/万元）。
Decision: DWD 统一 volume→股、amount/市值→元、股本→股，落库时按「表+字段」换算。
Rationale: 同量纲、价×量=额自洽，建模不易踩单位坑。
Impact: 字段描述需标注换算来源；同名字段不同表换算系数不同。
Related files: docs §3.3-G

## DECISION-20260531-04: 财务可见时间字段用 ann_date_eff

Date: 2026-05-31
Status: active
Owner: owner
Context: 财务表 partition_date 是报告期，不能当可见时间，否则未来泄露。
Decision: 统一造可见日字段 `ann_date_eff`，但**取法按表定义**（income/bs/cf=`COALESCE(f_ann_date, ann_date)`；`fina_indicator` 仅 `ann_date`——实测无 `f_ann_date`；事件表用各自公告/实施日）。另派生 `visible_trade_date` 把盘后/非交易日公告右移到下一可建仓交易日。
Rationale: 不能用一个公式覆盖所有表；as-of join 用 `visible_trade_date <= feature_date`。
Impact: 所有财务/事件 DWD 产出 `ann_date_eff`/`visible_trade_date`；表级规则见 §4.3。（经 2026-05-31 review 修订：原"统一 COALESCE 公式"不成立。）
Related files: docs §4.3, §6.5, §7.3

## DECISION-20260531-05: 按月分区 + sec_code 聚簇

Date: 2026-05-31
Status: active
Owner: owner
Context: BigQuery 单表上限 4000 分区；行情表数据量小。
Decision: 行情/财务 DWD 用 `PARTITION BY DATE_TRUNC(<date>, MONTH)` + `CLUSTER BY sec_code`；普通 DIM 不分区只聚簇。
Rationale: 按天全史 ~8700 交易日会超 4000 且碎片化；按月 ~420 分区，聚簇负责单股/股票池块裁剪。
Impact: 下游仍按 `trade_date` 范围裁剪，无需写 DATE_TRUNC。
Related files: docs §3.2, §8.1

## DECISION-20260531-06: 行情表强制分区过滤 + 初始回填范围

Date: 2026-05-31
Status: active
Owner: owner
Context: 控成本、防误扫全史；首期建设只需近年数据。
Decision: 行情 DWD 设 `require_partition_filter=TRUE`（财务表不开）。当前阶段最终 DWD/DWS 样本从 `2019-01-01` 起；财务/事件为支持 2019 PIT 前移到 `20170101`；维度/日历不按样本时间截断。
Rationale: 聚簇无法强制过滤，只有分区能；财务前移以保证 2019 初 PIT 能取到最近年报/季报。
Impact: 查行情表的 SQL 必须带 `trade_date` 过滤。2019 年前数据范围的细化口径见 DECISION-20260531-11。
Related files: docs §4.6, §6.1, §6.5

## DECISION-20260531-07: 表/字段注释规范 + 描述继承 ODS

Date: 2026-05-31
Status: active
Owner: owner
Context: 要求 DWD/DIM 像 ODS 一样带表/字段中文解释。
Decision: 所有 dim/dwd/dws 带表级+字段级 description；维度表用内联 DDL，事实表用 CTAS+ALTER；财务大表字段描述继承 ODS 同名字段，改名/派生/换算字段手写。
Rationale: BigQuery CTAS 不能内联列描述；继承避免手写数百财务字段。
Impact: 建表脚本需配套描述；后续可用 `bq update --schema` 或 dbt persist_docs。
Related files: docs §3.4, §5.1, §6.1

## DECISION-20260531-08: Agent 产出标明模型名

Date: 2026-05-31
Status: active
Owner: owner
Context: 多模型/多 Agent 协作，产出需可追溯到具体模型。
Decision: 所有 Agent 在 git commit（`Co-Authored-By: <模型名>` trailer）与自己撰写的文档（文首/文末署名）中标明具体模型名（精确到版本，如 Claude Opus 4.8）。
Rationale: 便于审计不同模型贡献与质量，避免笼统 "AI"。
Impact: AGENTS.md 增「五、模型署名协议」；CLAUDE.md 同步；建模文档补署名。
Related files: AGENTS.md, CLAUDE.md, docs/数据仓库建模方案-DWD-DIM.md

## DECISION-20260531-09: 按 Review 整改建模方案（9 采纳 / 2 调整）

Date: 2026-05-31
Status: active
Owner: owner
Context: 收到对建模方案的实测 review（`docs/reviews/数据仓库建模方案-DWD-DIM-review.md`）。
Decision: 9 项认可并改方案（P0-1/2/3、P1-1/2/4、P2-1/2/3）；2 项认可问题但调整执行——P0-4 不在本方案改 ODS schema（改 DWD 容错+门禁+兜底），P1-3 只加开盘侧方向字段、不加收盘四象限。理由写入 review response。
Rationale: review 基于实测、技术正确；少数点按职责边界与项目执行假设（t+1 开盘建仓）调整。
Impact: 方案多章节更新——财务改版本事实表、价格表改"交易日历×在市"骨架、表数订正 54、新增表级可见日规则与元数据矩阵、lookback、方向性可交易、visible_trade_date。
Related files: docs/数据仓库建模方案-DWD-DIM.md, docs/reviews/数据仓库建模方案-DWD-DIM-review-response.md

## DECISION-20260531-10: DWD/DIM 初始写入 ODS 可用全历史

Date: 2026-05-31
Status: superseded by DECISION-20260531-11
Owner: owner
Agent ID: Codex
Model: GPT-5

Summary: 早先误读为 DWD/DIM 初始写入 ODS 可用全历史；owner 随后澄清当前阶段先做好 2019+。本决策废弃，不作为执行依据。
Superseded by: DECISION-20260531-11
Related files: `docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md`, `TODO.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`

## DECISION-20260531-11: 当前阶段先做好 2019+ 数据，2019 前仅作必要支撑

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### 背景

owner 澄清：2019 年以前的数据是下一步；当前阶段先把 2019+ 数据做正确。但为保证 2019 初 PIT 与滚动特征，方案仍需要在三种性质不同的情况下触碰 2019 前数据。

### 决策

当前 P0 最终 DWD/DWS 样本以 `2019-01-01` 为起点。2019 年前数据只按三类处理：
1. 财务/事件类按报告期/事件分区前移到 `20170101`，用于 2019 PIT、公告滞后、同比/基期。
2. 行情/估值/资金类最终写 2019+，构建时按最大滚动窗口读取 2018 lookback buffer；buffer 行不落最终 DWD/DWS。
3. 维度/日历取最新快照或全量历史事件，例如 `trade_cal`、`stock_basic`、`namechange`，用于 2019 join 和 SCD2 还原。

### 理由

这样既能保证 2019 样本的 PIT、滚动特征和 universe 正确，又避免把后续“2019 年以前正式样本/明细建设”提前混入 P0。

### 影响

主方案 §4.6 已新增“为支持 2019+ 所需的 2019 年前数据范围”表。P0 SQL 需要参数化 `@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date`。OQ-002 关闭为采纳；OQ-008 关闭为不适用。

### 备选方案

把 DWD/DIM 初始写入改为 ODS 可用全历史；该方案被废弃，因为 owner 明确当前阶段先做好 2019+。

### 相关文件

`docs/数据仓库建模方案-DWD-DIM.md` §4.6, `docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md`, `TODO.md`

## DECISION-20260531-12: P0 建表 SQL 先以根目录 sql/ bootstrap 脚本落地

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### 背景

owner 要求在项目根目录新增目录，放置创建 DWD/DIM 表的代码。当前尚未决定最终调度/物化工具（OQ-005：dbt vs 纯 bq SQL）。

### 决策

先在根目录 `sql/` 落地 P0 BigQuery Standard SQL bootstrap 脚本：`00_create_datasets.sql`、`sql/dim/*.sql`、`sql/dwd/*.sql`。脚本使用 `CREATE OR REPLACE TABLE`、CTAS、后置字段描述、范围参数，并按当前 2019+ 口径处理 lookback 和财务 2017 前移。

### 理由

该方式能立即执行和验证 P0 表结构，不绑定最终调度工具；后续可直接迁移到 dbt model 或由 Airflow/bq 调用。

### 影响

`TODO.md` 将 P0 建表 SQL 标为已完成，新增“执行物化并 QA”和“lookback_start_date 配置化”待办。OQ-005 仍保持开放。

### 备选方案

直接引入 dbt 项目结构；暂缓，因为 owner 当前诉求是先把建表 SQL 写出来。

### 相关文件

`sql/README.md`, `sql/00_create_datasets.sql`, `sql/dim/*.sql`, `sql/dwd/*.sql`, `TODO.md`

## DECISION-20260531-13: 评审须产出 docs/reviews/ 评审文档；评审本身只读

Date: 2026-05-31
Status: superseded by DECISION-20260601-03
Owner: owner
Agent ID: Agent_RD（数仓建模 / 评审）
Model: Claude Opus 4.8

### 背景

本会话评审已提交的 P0 建表 SQL（commit 9942f14）。owner 指出：评审是只读分析，发现是否进项目记忆由 owner 决定；并要求把「评审须写评审文档」固化为协议。此前评审建模文档已有 `docs/reviews/` 先例，但协议未明文规定。

### 决策

对**已提交代码 / SQL** 或**设计 / 方案文档**的评审，必须产出 `docs/reviews/<对象>-review[-<专题>].md`，含分级发现 / 依据 / 影响 / 建议 / 与决策冲突核对 / 结论，带模型署名。评审过程**只读**：不擅改被评审对象、不把发现直接写进 `.agent/memory/**` 或 `TODO.md`；发现转为 OQ / TODO / 决策由 owner 决定。是否提交评审文档由 owner 决定，提交时与相关记忆同一次提交。

### 理由

评审结论是可追溯产物，应落文档而非仅在对话；评审与「执行整改」职责分离，避免评审者把未经 owner 采纳的发现擅自写入项目状态。

### 影响

AGENTS.md 新增「六、评审协议」。首份代码评审文档：`docs/reviews/P0-建表SQL-review.md`。

### 备选方案

只把评审结论留在对话/交接里——放弃，不可独立追溯。

### 相关文件

`AGENTS.md` §六, `docs/reviews/P0-建表SQL-review.md`

## DECISION-20260531-14: 采纳 P0 SQL 首轮评审并修复物化前风险

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### 背景

owner 要求修复 `docs/reviews/P0-建表SQL-review.md` 对 commit `9942f14` 的发现。评审指出 2 项物化前风险和 3 项 QA/完整性建议。

### 决策

采纳评审发现并修复：README 执行命令显式加 `--location=asia-east2`；`dwd_stock_eod_price` 的 `suspend_event` 只保留 `suspend_type='S'`，复牌 `R` 不标记停牌；`dim_stock` 加 `sec_code` 去重与 `derived_from_daily` 派生退市 30 日宽限；`dwd_fin_indicator` 按 `(sec_code, report_period, ann_date_eff, update_flag)` 去重保留最新摄入；补 `dwd_fin_indicator_latest` 和 P0 smoke QA 脚本。

### 理由

这些修复分别解决跨区域执行不稳、复牌日误判不可交易、股票主维兜底过早截断、重复版本防御和最新版本便利消费问题，不改变当前 2019+ 样本范围。

### 影响

当时影响：修复后按 `sql/README.md` 执行脚本，并运行 `sql/qa/01_core_smoke_checks.sql`。后续 P0 DIM/DWD 已物化并通过 QA。

### 备选方案

仅修 R1/R2、把 R3-R5 留到 QA 后；放弃，因为 owner 已要求修复，且这些补丁范围小、不会绑定调度选型。

### 相关文件

`sql/README.md`, `sql/dim/02_dim_stock.sql`, `sql/dwd/01_dwd_stock_eod_price.sql`, `sql/dwd/03_dwd_fin_indicator.sql`, `sql/dwd/05_dwd_fin_indicator_latest.sql`, `sql/qa/01_core_smoke_checks.sql`

## DECISION-20260531-15: P0 先将 dwd_index_eod 物化为价格-only

Date: 2026-05-31
Status: superseded by DECISION-20260531-16
Owner: owner
Agent ID: Codex
Model: GPT-5

Summary: 因 `ods_tushare_index_dailybasic` Parquet 物理类型不一致，P0 曾临时将 `dwd_index_eod` 物化为价格-only。上游修复后该临时决策废弃。
Superseded by: DECISION-20260531-16
Related files: `sql/dwd/04_dwd_index_eod.sql`, `sql/README.md`, `.agent/memory/archive/CLOSED_QUESTIONS.md`

## DECISION-20260531-16: 恢复 dwd_index_eod 指数估值/股本字段

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### 背景

owner 告知 GCS `index_dailybasic` Parquet 文件已修复。复测确认 2019+ 的 `index_dailybasic_000016_SH`、`index_dailybasic_000905_SH`、`index_dailybasic_399001_SZ`、`index_dailybasic_399006_SZ`、`index_dailybasic_399300_SZ` 均可读取 `float_mv`、`float_share`、`total_mv`、`total_share`、`pe`、`pe_ttm`、`pb`。

### 决策

恢复 `sql/dwd/04_dwd_index_eod.sql` 对 `ods_tushare_index_dailybasic` 的读取，并将 `total_mv/float_mv` 直接落为 `total_mv_cny/float_mv_cny`，将 `total_share/float_share/free_share` 直接落为股本字段。删除指数 DWD 中误导性的 `_10k` 中间字段，不做 `*10000` 换算。

### 理由

Tushare `index_dailybasic` 官方单位为元/股，不同于股票 `daily_basic` 的万元/万股口径。恢复 dailybasic 字段后，`dwd_index_eod` 可同时服务指数价格、估值和市场状态特征。

### 影响

`dwd_index_eod` 已重建并通过 QA。2019+ 共 11,922 行，其中 8,899 行有 dailybasic 估值/股本字段；STAR50(`000688.SH`) 与 CSI1000(`000852.SH`) 仍为空，因为 ODS 当前没有对应 `index_dailybasic` endpoint。OQ-009 已关闭。

### 备选方案

保留价格-only 或保留 `_10k` 字段置 NULL；放弃，因为上游已修复且 `_10k` 字段会误导单位。

### 相关文件

`sql/dwd/04_dwd_index_eod.sql`, `sql/qa/01_core_smoke_checks.sql`, `.agent/memory/OPEN_QUESTIONS.md`

## DECISION-20260531-17: 拆分全天停牌与盘中临停语义，并修正财务 latest 排序

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### 背景

`docs/reviews/P0-建表SQL-fix-review.md` 指出：`dwd_stock_eod_price` 将所有 `suspend_type='S'` 行都标为 `is_suspended=TRUE`，导致有成交的盘中临停行被误判为不可交易；`dwd_fin_indicator_latest` 的排序与方案口径不一致，晚公告的 `update_flag=0` 可能覆盖较早的修正版。

### 决策

价格 DWD 中 `is_suspended` 仅表示全天停牌或无成交。若 `suspend_d` 有 `S` 事件且当日 `daily` 有 close/volume，则用 `has_intraday_halt` 标记盘中临停；其中开盘时段或未知时段临停用 `has_open_halt` 标记，并影响 `can_buy_open`、`can_sell_open`、`is_tradable`。`dwd_fin_indicator_latest` 每个 `(sec_code, report_period)` 按 `update_flag DESC, ann_date_eff DESC, ingested_at DESC, source_partition_date DESC` 取最新修正版。

### 理由

全天停牌与盘中临停对日线样本和开盘建仓约束不同，混用会错误丢弃可交易样本。财务 latest 是便捷消费表，应优先保留修正版，不能让更晚公告的非修正版覆盖。

### 影响

`dwd_stock_eod_price` 和 `dwd_fin_indicator_latest` 已重建并通过 QA。验证结果：有成交但 `is_suspended=TRUE` 的行数为 0；`dwd_fin_indicator_latest` 与方案排序差异为 0。QA 新增对应断言。

### 备选方案

继续把所有 `S` 事件视为全天停牌；放弃，因为实测 2019+ 有 897 行盘中临停仍有成交。只改 `is_suspended` 不加 `has_intraday_halt/has_open_halt`；放弃，因为下游仍需要区分开盘建仓是否受影响。

### 相关文件

`sql/dwd/01_dwd_stock_eod_price.sql`, `sql/dwd/05_dwd_fin_indicator_latest.sql`, `sql/qa/01_core_smoke_checks.sql`, `docs/reviews/P0-建表SQL-fix-review.md`

## DECISION-20260531-18: DWS/ADS 采用分族特征层 + 策略消费层

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### 背景

owner 要求在现有 ODS、DWD/DIM 设计基础上，继续设计面向 A 股日线中低频小资金机器学习量化的 DWS/ADS 表体系，并单独设计策略方案。

### 决策

DWS 采用“样本骨架 + 分族特征 + 标签 + 训练样本”的结构，P0 包含 `dws_stock_universe_daily`、价格/估值/财务特征、`dws_market_state_daily`、`dws_stock_label_daily`、`dws_stock_feature_daily_v0`、`dws_stock_sample_daily`。ADS 采用策略消费层，包含训练面板、模型注册、预测、候选池、组合目标、订单计划、回测成交/持仓/NAV/绩效和信号监控。首个策略定义为 `ml_ranker_v0`：P0 特征横截面排序，长-only，`t` 日盘后信号、`t+1` 开盘/VWAP 建仓。

### 理由

分族 DWS 能控制宽表复杂度，允许 P0 先闭环、P1/P2 逐步接入资金/事件/行业特征；ADS 将训练、预测、组合和回测结果版本化，便于复现和审计。

### 影响

新增 `docs/数据仓库建模方案-DWS-ADS.md` 和 `docs/A股中低频小资金机器学习策略方案.md`。后续 TODO 新增 P0 DWS/ADS SQL、`ml_ranker_v0` 基线训练和回测。新增 OQ-010，要求 owner 确认 P0 策略成本参数、调仓频率、持股数/权重上限和北交所是否纳入。

### 备选方案

直接生成一张超宽 DWS 表供所有模型使用；未采用，因为会把 P0/P1/P2 特征生命周期混在一起，难以做特征质量、版本和依赖管理。

### 相关文件

`docs/数据仓库建模方案-DWS-ADS.md`, `docs/A股中低频小资金机器学习策略方案.md`, `TODO.md`, `.agent/memory/ARCHITECTURE_MEMORY.md`

## DECISION-20260531-19: 行业时点映射改用已补采的 index_member_all / ci_index_member

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### 背景

owner 说明 `index_member_all` 和 `ci_index_member` 的 ODS 表已经补上。复核 BigQuery 后，`ashare_ods` 当前为 56 张表 / 1532 字段，新增表 `ods_tushare_index_member_all` 与 `ods_tushare_ci_index_member` 均包含 `l1/l2/l3` 行业代码名称、`ts_code`、`in_date`、`out_date`、`is_new`。

### 决策

关闭 OQ-001。申万行业时点归属用 `ods_tushare_index_member_all` 落 `dim_stock_sw_industry_hist`；中信行业时点归属用 `ods_tushare_ci_index_member` 落 `dim_stock_ci_industry_hist`。历史训练/回测统一用 `in_date/out_date` 区间 join，默认半开区间 `[valid_from, valid_to)`；`is_new` 仅标识当前最新归属，不能用于历史回填。

### 理由

行业归属是行业中性化、行业轮动、行业暴露约束的基础。使用时点区间维表可以避免用当前行业归属回填历史造成未来函数。

### 影响

主方案、DWS/ADS 方案、策略方案和记忆文件已从“行业映射缺口/粗行业兜底”改为“可落地行业时点维表”。TODO 新增 `dim_stock_sw_industry_hist` / `dim_stock_ci_industry_hist` SQL 和 QA 项。

### 备选方案

继续使用 `dim_stock.industry` 粗行业字段作为兜底；不再作为标准路径，仅保留为异常兜底或对照字段。

### 相关文件

`docs/数据仓库建模方案-DWD-DIM.md`, `docs/数据仓库建模方案-DWS-ADS.md`, `docs/A股中低频小资金机器学习策略方案.md`, `.agent/memory/OPEN_QUESTIONS.md`, `TODO.md`

## DECISION-20260531-20: P0 表字段说明由集中 metadata 脚本补齐

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### 背景

P0 DIM/DWD 表已物化，但 CTAS 建表脚本只给部分字段补了 description，导致 BigQuery 中表级和字段级说明不完整。BigQuery CTAS 无法在 SELECT 列上直接内联字段 description。

### 决策

新增 `sql/metadata/01_core_table_column_descriptions.sql`，集中维护 3 张 DIM + 5 张 DWD 的表级和字段级中文说明。P0 表每次 `CREATE OR REPLACE TABLE` 重建后，都应重新执行该 metadata 脚本。

### 理由

集中 metadata 脚本能原地更新说明，不重写数据；也避免在每个 CTAS 脚本里维护大量重复 ALTER 片段。后续若采用 dbt，可迁移到 `persist_docs`，但当前纯 SQL bootstrap 先用显式 ALTER 保证 BigQuery 元数据完整。

### 影响

已在 BigQuery 执行 metadata 脚本。8 张 P0 DIM/DWD 表的 table description 和所有 schema field description 均已补齐，验证 missing description = 0。`sql/README.md` 已把 metadata 脚本加入执行顺序。

### 备选方案

逐个重建脚本内补齐全部 ALTER；放弃作为唯一方案，因为每次只需补 metadata 时不应重写全量数据。等待后续 dbt `persist_docs`；暂缓，因为 OQ-005 尚未决定调度/物化工具。

### 相关文件

`sql/metadata/01_core_table_column_descriptions.sql`, `sql/README.md`

## DECISION-20260601-01: 指数 DWD 使用 canonical sec_code 并保留 source_sec_code

日期: 2026-06-01
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

`docs/reviews/数据仓库建模方案-DWS-ADS-review.md` 的 P1-5 指出：沪深300 等指数存在 ODS 实际代码与业务 canonical 代码不一致的问题。当前 `dwd_index_eod` 已有 `canonical_index_code`，但 `sec_code` 仍保留 ODS `ts_code`，容易导致 DWS/ADS 既有按 `sec_code` join 规范被破坏。

### 决策

`dwd_index_eod.sec_code` 输出 canonical 指数代码；新增 `source_sec_code` 保留 ODS/Tushare 实际代码。DWS/ADS 基准指数 join、benchmark 配置和超额收益计算只使用 canonical `sec_code`。双代码或多代码指数的 `source_sec_code -> sec_code` 映射先由 `dwd_index_eod` 建表脚本 CTE 维护，未来可沉淀为 `dim_index` 维表。

### 理由

该方案与 DWD-DIM §3.3-A 的主键归一规则一致：DWD/DIM 出口字段名和值都应使用统一 `sec_code`，来源差异进入血缘字段而不是泄漏到 DWS/ADS join 逻辑。`source_sec_code` 保留了追溯 ODS endpoint 和排查数据问题所需的信息。

### 影响

`sql/dwd/04_dwd_index_eod.sql`、metadata、QA 和相关文档已按此口径更新。2026-06-01 已重建 BigQuery 实表，并重新执行 `sql/metadata/01_core_table_column_descriptions.sql` 和 `sql/qa/01_core_smoke_checks.sql` 通过。

### 备选方案

保留当前 `sec_code=ODS 实际代码` 并要求 DWS/ADS 使用 `canonical_index_code` join；放弃，因为这会让指数表成为 `sec_code` 统一主键规范的例外，增加下游实现负担。

### 相关文件

`sql/dwd/04_dwd_index_eod.sql`, `sql/metadata/01_core_table_column_descriptions.sql`, `sql/qa/01_core_smoke_checks.sql`, `docs/数据仓库建模方案-DWD-DIM.md`, `docs/数据仓库建模方案-DWS-ADS.md`, `docs/A股中低频小资金机器学习策略方案.md`

## DECISION-20260601-02: 策略 1 runner 采用 BigQuery ML + SQL 执行路径

日期: 2026-06-01
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

策略 1 DWS/ADS 表契约已物化，下一步需要设计并实现训练、预测、候选池、组合、回测 runner。owner 明确要求 runner 设计只保留 BigQuery ML 方案，不考虑 BigQuery 之外的训练执行路径。

### 决策

策略 1 `ml_pv_clf_v0` runner 采用 BigQuery SQL + BigQuery ML：用 `ads_ml_training_panel_daily` 冻结样本与预处理口径，首版用 BQML `LOGISTIC_REG` 训练 `label_top30_5d`，可用 BQML `LINEAR_REG` 作为对照；正则化和调参使用 BQML 原生 `L1_REG` / `L2_REG` 手动候选网格，最终以验证集 RankIC/分层收益选择，不用 sklearn `l1_ratio/C` 口径作为实现参数。`board` 保留为分组和暴露监控字段，不进入 v0 主模型训练列。通过 `ML.PREDICT` 写预测分，再用 SQL 生成候选池、组合、订单、回测、监控和模型注册信息。回测报告 artifact 采用 GCS-first + 本地镜像：GCS 是持久存储，本地 `reports/` 只方便用户读取且默认不提交。runner SQL 后续放 `sql/ml/strategy1/`。

### 理由

策略 1 首版是探针和基线，BigQuery ML 能避免导出数据和额外模型文件管理，使 PIT 数据、模型对象和 ADS 结果留在同一 BigQuery 项目内，便于复现、权限控制和成本审计。

### 影响

新增 `docs/策略1-ml_pv_clf_v0-runner设计.md`。更新策略 1 PRD、DWS/ADS 方案、策略方案、SQL README、ADS 表契约注释和工作记忆，将旧的 Python runner 待办替换为 BigQuery ML + SQL runner 待办；`.gitignore` 忽略生成型本地报告镜像 `reports/`。PR #5 comment 后补充了 `L1_REG/L2_REG` 手动候选模型选择流程，并将 `board` 从 v0 主模型特征改为监控字段。OQ-010 不再包含训练工具链选择，但仍保留成本、调仓频率、持股数/权重上限和板块纳入参数待确认。

### 备选方案

用 BigQuery 导出样本后在外部环境训练 Logistic/Ridge/ElasticNet，再把结果回写 ADS；放弃，因为 owner 已要求本 runner 不考虑该路径，且首版基线不需要承担外部模型 artifact 管理复杂度。

### 相关文件

`docs/策略1-ml_pv_clf_v0-runner设计.md`, `docs/prd/PRD_20260601_01_策略1价格量价基础分类模型.md`, `docs/数据仓库建模方案-DWS-ADS.md`, `docs/A股中低频小资金机器学习策略方案.md`, `sql/README.md`, `sql/ads/01_ads_strategy1_tables.sql`, `.gitignore`, `TODO.md`

## DECISION-20260601-03: GitHub PR review 默认写 PR comment

日期: 2026-06-01
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

此前 DECISION-20260531-13 要求对已提交代码 / SQL 或设计文档的评审必须产出 `docs/reviews/` 评审文档。owner 在 PR #7 评审过程中明确调整：GitHub PR 上的评审应直接写 comment；一条 comment 写不下就拆多条，不再默认写评审文档。

### 决策

GitHub PR review 默认写 GitHub PR comment；一条 comment 写不下拆成多条。只有 owner 明确要求归档为文档，或评审对象没有 PR comment 承载面时，才创建 `docs/reviews/<对象>-review[-<专题>].md`。评审过程仍保持只读：不擅改被评审对象，不把发现直接写进 `.agent/memory/**` 或 `TODO.md`；发现是否转为 OQ / TODO / 决策由 owner 拍板。

### 理由

PR comment 能把发现、修复、反驳和后续讨论保留在同一上下文中，便于 reviewer 与实现者逐条对齐。长评审可通过多条 comment 保持完整，不需要为每次 PR review 额外维护重复文档。

### 影响

本决策 supersede DECISION-20260531-13 中“评审必须产出 docs/reviews 文档”的默认规则。`AGENTS.md` §六、`.agent/memory/UPDATE_PROTOCOL.md` 和 `AGENT_HANDOFF.md` 当前摘要已更新。历史 `docs/reviews/` 文档继续保留作审计记录。

### 备选方案

继续要求每次评审都写 `docs/reviews/` 文档；放弃，因为 owner 已明确 PR review 默认走 GitHub comment。只在对话中反馈；放弃，因为 PR comment 才是当前代码评审的可追溯载体。

### 相关文件

`AGENTS.md`, `.agent/memory/UPDATE_PROTOCOL.md`, `.agent/memory/AGENT_HANDOFF.md`, `.agent/memory/DECISION_LOG.md`

## DECISION-20260601-04: dim_stock 退市日优先使用 ODS delist_date

日期: 2026-06-01
状态: active
负责人: owner / 上游 ingestion
Agent ID: Codex
模型: GPT-5

### 背景

OQ-007 记录过 `stock_basic_delisted.delist_date` 外部表类型与 Parquet 文件类型不一致，导致 BigQuery 直读报错。2026-06-01 复核发现 ODS schema 已修复为 `STRING`，最新 `stock_basic_delisted` 分区 326 行退市日均可解析。

### 决策

`dim_stock.delist_date` 对 `list_status='D'` 的股票优先使用 ODS `stock_basic_delisted.delist_date` 解析结果。仅当 ODS 退市日缺失时，才回退到 `daily` 最后交易日加一天。P0 QA 增加 ODS 退市日可读/可解析断言，并要求 `dim_stock` 与 ODS 退市日一致。

### 理由

ODS 退市日是正式生命周期边界；`daily` 最后交易日只代表最后有成交日，部分退市股最后成交日到正式退市日之间存在停牌区间。继续用 daily 兜底会提前截断 universe，影响幸存者偏差治理和停牌期不可交易标记。

### 影响

`sql/dim/02_dim_stock.sql`、metadata、QA、SQL README 和 DWD-DIM 文档已更新。合并后需要重建 `dim_stock`，并按依赖重建 `dwd_stock_eod_price` 与下游策略 1 DWS/ADS 派生产物后执行 metadata 与 QA。

### 备选方案

继续使用 `daily` 最后交易日加一天；放弃，因为 ODS 已可用且 daily 口径会把最后成交日至正式退市日之间的停牌生命周期截断。

### 相关文件

`sql/dim/02_dim_stock.sql`, `sql/qa/01_core_smoke_checks.sql`, `sql/metadata/01_core_table_column_descriptions.sql`, `docs/数据仓库建模方案-DWD-DIM.md`, `.agent/memory/archive/CLOSED_QUESTIONS.md`

## DECISION-20260601-05: 财务 report_type 默认合并报表，DWD 保留口径维度

日期: 2026-06-01
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

OQ-003 记录财务 `report_type` 口径待决：当前方案默认取合并报表 `'1'`，但需要确认是否保留母公司/单季调整等口径维度。PR #8 已提交 `docs/prd/PRD_20260601_03_财务报表口径维度.md` 并完成 review 修订。

### 决策

采纳 PRD 推荐方案：P0 默认消费合并报表 `report_type='1'`。带 `report_type` 的财务 DWD 版本事实表保留源 `report_type`，并派生 `report_caliber` 与 `is_default_report_caliber`。P0 财务 DWS 默认过滤 `is_default_report_caliber = TRUE`，不在首版物化多口径特征。多口径研究后续通过宽字段或长表扩展，不在现有 P0 财务 DWS 主键下输出重复行。`fina_indicator` 若源表无 `report_type`，不伪造 `report_type='1'`，仅可用 `report_caliber='source_default'` 做元数据标识。

### 理由

合并报表是 A 股量化默认且可比性最高的集团整体经营口径；DWD 保留源口径字段能避免早期过滤导致未来研究母公司口径或口径差异因子时必须重新回填。DWS 首版只消费默认口径，能防止训练样本混用不同报表口径，也避免主键膨胀。

### 影响

OQ-003 关闭并归档。后续实现 `dwd_fin_income` / `dwd_fin_balancesheet` / `dwd_fin_cashflow`、`dws_stock_feature_fin_daily` 时，需按 PRD 补口径字段、默认过滤和 NULL-safe QA，并同步主建模方案文档与 SQL。当前 PR 只关闭决策与 PRD，不直接实现三大财务表 SQL。

### 备选方案

在 DWD 直接过滤 `report_type='1'`；放弃，因为会丢失后续多口径研究所需源数据。P0 DWS 立即物化多口径长表；放弃，因为首版财务特征只需要默认合并口径，过早扩展会增加主键和训练样本复杂度。

### 相关文件

`docs/prd/PRD_20260601_03_财务报表口径维度.md`, `.agent/memory/archive/CLOSED_QUESTIONS.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `TODO.md`

## DECISION-20260601-06: 策略 1 首个基线仅纳入沪深主板

日期: 2026-06-01
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

OQ-010 中仍有一项股票池板块纳入口径未确认：首个策略基线是否纳入北交所、创业板、科创板。现有 `sql/dws/01_dws_stock_universe_daily.sql` 默认 `board_allowlist` 已为 `['SSE_MAIN','SZSE_MAIN']`，但文档和记忆中仍保留“待确认”表述。

### 决策

策略 1 `ml_pv_clf_v0` 首个基线默认股票池仅纳入沪深主板：`SSE_MAIN`、`SZSE_MAIN`。不纳入北交所、创业板、科创板。后续如需研究这些板块，应通过 `board_allowlist` 另开对照实验或单独模型，不混入首个基线。

### 理由

首个基线的目标是建立稳定、可解释、可复现的参照组。北交所、创业板、科创板在涨跌幅、流动性和风格暴露上与主板差异较大，混入首个基线会增加结果解释成本。

### 影响

OQ-010 不再包含板块纳入口径待确认项；仍保留回测成本参数、默认调仓频率、持股数和单票权重上限待 owner 确认。现有策略 1 universe SQL 的默认 `board_allowlist` 已符合本决策，仅补充注释和文档同步。

### 备选方案

首个基线纳入全 A 普通股；放弃，因为不同板块交易制度和流动性差异会降低基线可解释性。保留北交所为默认研究开关；放弃，因为 owner 已明确首个基线不包含北交所。

### 相关文件

`docs/prd/PRD_20260601_01_策略1价格量价基础分类模型.md`, `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`, `docs/策略1-ml_pv_clf_v0-runner设计.md`, `docs/A股中低频小资金机器学习策略方案.md`, `docs/数据仓库建模方案-DWS-ADS.md`, `sql/dws/01_dws_stock_universe_daily.sql`, `.agent/memory/OPEN_QUESTIONS.md`, `TODO.md`

## DECISION-20260601-07: 策略 1 回测 v0 采用「有守卫的简化版」，QA 失败即触发升级到账户级 ledger

日期: 2026-06-01
状态: active
负责人: owner
Agent ID: Claude
模型: Claude Opus 4.8

### 背景

策略 1 runner 回测脚本 `sql/ml/strategy1/08_run_backtest.sql` 经多轮评审（PR #7）。set-based 持仓 episode 模型在「延迟/封死卖出尚未平仓时、同股又重新进入选股池」这一低频场景下，会对同股重叠建仓（双倍暴露/预算占用）。根治需要按现金约束、对实际持仓 netting 的有状态 ledger 循环，但这偏离已批准 PRD（`PRD_20260601_02`）刻意选择的 set-based + next-sellable 设计。
（原编号 DECISION-20260601-03，因与 main 已有 03/04/05/06 撞号，合并 PR #7 时改为 07。）

### 决策

v0 选「有守卫的简化版」（方案 B）：保留 set-based episode 模型，并在 `10_qa_runner_outputs.sql` 加守卫断言 `cash_cny >= -1`、`gross_exposure <= 1.005`、持仓 `(trade_date, sec_code)` 唯一。**明确定性：这不是最终账户级回测引擎。** 硬规则：真实回测若跑出上述任一 QA 失败，说明该边界在数据中实际发生，则该回测结果不可接受，必须升级为方案 A（账户级有状态 ledger 循环：逐调仓日维护现金/持仓、卖出先于买入、买入受可用现金约束、对实际持仓 netting），更新 runner 设计与 PRD 后重跑。

### 理由

v0 是基线探针，正常路径已正确、现金不为负；该边界低频且已被 QA 兜住，会在发生时报错而非静默。先不引入有状态循环的复杂度与偏离已批准设计的成本，但保留明确的升级触发条件，避免把简化版误当账户级结论使用。

### 影响

`08_run_backtest.sql` 头部、`sql/ml/strategy1/README.md`、runner 设计 §14.1 均标注 v0 定性与升级触发。`10_qa_runner_outputs.sql` 增加三条守卫断言。后续若 QA 失败，升级方案 A 为必做项（非可选）。

### 备选方案

方案 A（直接上账户级 ledger 循环）：最正确但偏离已批准 set-based PRD、复杂度与 bug 面更大，且无法在不实跑下证明循环逻辑；owner 决定 v0 暂不采用，留作 QA 失败时的强制升级路径。

### 相关文件

`sql/ml/strategy1/08_run_backtest.sql`, `sql/ml/strategy1/10_qa_runner_outputs.sql`, `sql/ml/strategy1/README.md`, `docs/策略1-ml_pv_clf_v0-runner设计.md`

## DECISION-20260601-08: 指数可用性由 dim_index 承载，runner 必须校验 benchmark 窗口

日期: 2026-06-01
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

OQ-004 要求中证1000/中证2000/国证2000等基准不能按常见代码硬编码，必须以 ODS `index_daily` 实际存在端点为准，并维护 `source_sec_code -> sec_code` canonical 映射。此前 `dwd_index_eod` 内部 CTE 已处理沪深300 `399300.SZ -> 000300.SH`，但映射和端点可用性未沉淀为可复核维表，runner 也缺少完整 benchmark 窗口前置校验。

### 决策

新增 `ashare_dim.dim_index` 作为指数 canonical 映射、ODS 实际代码、`index_daily` / `index_dailybasic` 端点可用性、起止日期和 benchmark 候选状态的长期承载表。`dwd_index_eod` 从 `dim_index` 读取可用端点与映射；策略 runner 使用 `benchmark_sec_code` 前必须校验其在 `dim_index` 中 `has_daily=TRUE AND is_benchmark_candidate=TRUE`，并校验完整 NAV 窗口内每个开市日都有且只有一条非空基准价格记录。

### 理由

指数收益基准只依赖 `index_daily`，指数估值/市场状态特征才依赖 `index_dailybasic`。将两类可用性分开，可以允许 `000852.SH` 作为中证1000收益基准，同时阻止它被用于依赖 PE/PB/市值字段的市场状态特征。runner 前置校验避免默认基准在回测窗口缺失或重复时产生不可解释的 NAV / 超额收益。

### 影响

OQ-004 可在 `dim_index`、映射驱动 `dwd_index_eod`、`sql/qa/03_index_benchmark_checks.sql` 和 runner benchmark 窗口契约通过后关闭。后续新增中证2000、国证2000等基准时，必须先补 ODS 端点并刷新 `dim_index`，不得直接写入 DWS/ADS 默认配置或 runner 参数。

### 备选方案

继续在 `dwd_index_eod` CTE 内维护映射；放弃，因为 runner 和 QA 无法复用端点可用性事实。把 `000852.SH` 改成 `000905.SH` 作为默认示例基准；放弃，因为策略 1 仍可使用中证1000作为收益基准，只需明确其无 dailybasic 限制。

### 相关文件

`sql/dim/04_dim_index.sql`, `sql/dwd/04_dwd_index_eod.sql`, `sql/qa/03_index_benchmark_checks.sql`, `sql/ml/strategy1/08_run_backtest.sql`, `docs/prd/PRD_20260601_04_OQ004基准指数口径.md`

## DECISION-20260602-01: 策略 1 回测 08 升级为账户级有状态 ledger（落地 DECISION-20260601-07）

日期: 2026-06-02
状态: active
负责人: owner
Agent ID: Claude
模型: Claude Opus 4.8

### 背景

PR #12 在 BigQuery 端到端实跑策略 1 runner 时，v0 set-based episode 回测（`08_run_backtest.sql`）违反 `10` 的守卫：每个 episode 建仓固定花 `initial_capital × weight`、不回收已实现资金，104 个调仓日累计买入 570 万远超 10 万本金 → `cash_cny` 最低 -34 万、`gross_exposure` 高达 2803 倍、476/485 天负现金。这正是 DECISION-20260601-07 预设的升级触发条件。

### 决策

按 DECISION-20260601-07 将 `08_run_backtest.sql` 重写为账户级有状态 ledger（BigQuery scripting `WHILE` 循环逐调仓 period）：每个 t+1 执行日先按当前持仓估值得 NAV（停牌用 ffill 收盘）；目标仓位 = 目标权重 × 当前 NAV（资金复利/回收）；卖出先于买入；买入受可用现金约束（超出按比例缩放）；对实际持仓 netting（滚动持有不重复全卖全买）；循环后按交易日展开每日持仓/NAV。现金不为负、gross ≤ 1、持仓唯一、NAV 全覆盖由构造保证，并经实跑 `10` 16 断言验证。

### 理由

set-based 模型无法跟踪「建仓时点的可用现金」，无小修可使其自洽；账户级 ledger 是 DECISION-20260601-07 已预先授权的唯一正确路径。

### 影响

08 为 v1 ledger，含已文档化简化：不可交易腿本期跳过、carry 到下一 period，不做 60 交易日 next-sellable 顺延；未复权口径、持有期除权简化。后续若需更高保真（部分成交、日内撮合、复权持有、卖出顺延搜索）可在此 ledger 基础上扩展。KNOWN_CONSTRAINTS 的 v0 回测条目已更新为 v1 ledger。

### 备选方案

每个调仓日全清仓再全买（更简单且守卫安全）——放弃，违反 DECISION-20260601-07「对实际持仓 netting」要求且高估换手/成本。保留 v0 仅放宽守卫阈值——放弃，结果（-98% 来自记账错误而非真实持仓）不可接受。

### 相关文件

`sql/ml/strategy1/08_run_backtest.sql`, `sql/ml/strategy1/10_qa_runner_outputs.sql`, `docs/策略1-ml_pv_clf_v0-runner设计.md`（§14.1）

## DECISION-20260602-02: OQ-006 单位契约作为 DWD 准入门禁

日期: 2026-06-02
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

OQ-006 要求解决 Tushare 不同接口金额、数量、股本、市值、价格和比率字段单位不一致的问题。OQ-006 PRD 已提出 `ashare_meta.ods_field_unit_map`、单位覆盖 QA 和 DWD 准入门禁，但仍有四项 owner 取舍待确认。

### 决策

采纳 OQ-006 PRD 的强治理口径：

1. `ashare_meta.ods_field_unit_map` 作为单位换算唯一事实来源。
2. `dwd_index_eod.volume/amount` 当前仍是 `index_daily` 源单位手/千元，必须在 OQ-006 实现 PR 中按 `vol*100` / `amount*1000` 换算，并迁移为 `volume_share` / `amount_cny`；legacy exception 只允许短期兼容，不作为 OQ-006 关闭方案。
3. OQ-006 最小实现必须先于 P1 资金流、财务扩展等高单位风险 DWD 正式落地。
4. `sql/qa/05_unit_contract_checks.sql` 加入所有新增或修改 DWD 标准字段 PR 的必跑 QA 清单。

### 理由

单位错误会直接造成 1,000 倍、10,000 倍或百分比/比例混用的模型特征错误。把单位核对沉淀为机器可读契约和 QA 门禁，能避免后续 DWD 依赖人工记忆；当前项目还早，修复 `dwd_index_eod.volume/amount` 的 index daily 换算并迁移字段成本低，优先消除单位错误和命名债务比长期例外更稳。

### 影响

OQ-006 从“方案待确认”推进为“待实现”。后续实现需新增 `ashare_meta.ods_field_unit_map`、P0 + PR #13 财务三表首批 seed、`sql/qa/05_unit_contract_checks.sql`，修复 `dwd_index_eod.volume/amount` 未换算问题并迁移命名，并同步 DWD-DIM / README / KNOWN_CONSTRAINTS。PRD03 / PR #13 财务三表正式落地前必须接入单位契约或依赖 OQ-006 最小实现。

### 备选方案

不设置唯一事实来源、仅在 SQL 注释或文档中记录单位；放弃，因为不可机器检查。`dwd_index_eod.volume/amount` 仅登记 legacy exception；放弃，因为项目尚早，迁移成本低。OQ-006 等 P1 表落地后再补；放弃，因为财务和资金流表是单位风险最高的新增表。

### 相关文件

`docs/prd/PRD_20260602_01_OQ006接口单位换算口径.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `TODO.md`

## DECISION-20260602-03: 财务三大报表 DWD/DWS 落地的实现口径

日期: 2026-06-02
状态: active
负责人: owner（已采纳 DECISION-20260601-05 / PRD_20260601_03）
Agent ID: Claude
模型: Claude Opus 4.8

（原编号 DECISION-20260602-01，rebase PR #13 到含 OQ-006 的 `main` 时与已有 `-01`（ledger）/`-02`（OQ-006）撞号，改为 `-03`。）

### 背景

按 DECISION-20260601-05 与 `PRD_20260601_03` 落地 `dwd_fin_income/balancesheet/cashflow`（+ `_latest`）和 `dws_stock_feature_fin_daily`。实测当前 ODS 三大报表仅含 `report_type='1'`（合并报表），落地时需要固化几个 PRD 未逐字规定的实现选择。

### 决策

1. **DWS 口径字段是消费契约，不是逐行匹配状态**：`dws_stock_feature_fin_daily.report_caliber`/`is_default_report_caliber` 恒为 `consolidated`/`TRUE`，表示“本表三大报表特征只来自默认合并口径”；某股某日是否真有某来源财报由 `has_fin_*` 掩码 + 各来源 `*_report_period` 标识。这样既满足 PRD FR-3「只输出默认口径」断言，又不把 LEFT JOIN 退化成 inner join 丢行（行数 = universe）。
2. **as-of 扇出约束**：四个来源 as-of 限制 `visible_trade_date ∈ [trade_date - 900 日, trade_date]`；超 900 日（≈2.5 年）未更新财报视为缺失（`has_fin_*=FALSE`）。用于约束 8.5M universe × 历史版本的范围 join 成本，正常季度披露不受影响。
3. **单季派生延后 P1**：P0 直接用 `fina_indicator` 现成 `q_*`，三大报表绝对值保留累计/YTD 口径（不在本期派生三大报表单季值）。
4. **不重建 `dwd_fin_indicator`**：暂不给它加物理 `report_caliber='source_default'` 字段（PRD §11.4），改为在 `dws_stock_feature_fin_daily` 输出 `ind_report_caliber='source_default'`，避免重建既有实表与依赖链。
5. **`report_type>'1'` 的 `report_caliber` 映射**（1-5 consolidated / 6-12 non_consolidated / 其余 other / NULL unknown）作为前向兼容写入 CASE；当前数据不触发，`is_default_report_caliber = COALESCE(report_type='1', FALSE)`。
6. **单位契约（OQ-006，DECISION-20260602-02）**：三大报表金额字段为 Tushare 原始口径元、不做换算，落地时在 `ashare_meta.ods_field_unit_map` 按 `source_unit=元`、`canonical_unit=元`、`multiplier=1`、`verification_status=verified` 登记，并跑通 `sql/qa/05_unit_contract_checks.sql`（QA-UNIT-2 财务字段全覆盖）。

### 理由

在不偏离已采纳 PRD 验收口径的前提下，用契约语义 + 掩码解决「默认口径纯净」与「不丢股票日期」的张力；用有界 as-of 控制成本；把单季派生和多口径研究留给 P1，保持 P0 财务特征表简单、主键不膨胀；单位按 OQ-006 门禁登记，避免高单位风险财务字段漏核。

### 影响

`sql/qa/04_finance_caliber_checks.sql` 25 条 ASSERT 全过（含 DWS 主键唯一、PIT 零泄露、行数=universe、口径契约）；`sql/qa/05_unit_contract_checks.sql` 在补全财务字段映射后全过。后续若要真正研究多口径或单季因子，按 PRD §6.2 显式改键/改字段，不在本表主键下输出多行。

### 备选方案

DWS 用逐行 caliber 匹配状态（匹配则 consolidated、未匹配则 NULL/none）：放弃，因为会让 PRD FR-3 的 `COUNTIF(is_default_report_caliber IS NOT TRUE)=0` 在新上市暂无财报的 universe 行上失败，或迫使 inner join 丢行。无界 as-of：放弃，范围 join 扇出过大。

### 相关文件

`sql/dwd/06_dwd_fin_income.sql`, `sql/dwd/07_dwd_fin_income_latest.sql`, `sql/dwd/08_dwd_fin_balancesheet.sql`, `sql/dwd/09_dwd_fin_balancesheet_latest.sql`, `sql/dwd/10_dwd_fin_cashflow.sql`, `sql/dwd/11_dwd_fin_cashflow_latest.sql`, `sql/dws/07_dws_stock_feature_fin_daily.sql`, `sql/qa/04_finance_caliber_checks.sql`, `sql/meta/01_ods_field_unit_map.sql`, `sql/qa/05_unit_contract_checks.sql`, `docs/prd/PRD_20260601_03_财务报表口径维度.md`

## DECISION-20260602-04: 策略 1 默认交易成本 profile

日期: 2026-06-02
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

OQ-010 仍有策略默认参数待确认。当前策略 1 runner 使用单一 `p_cost_bps=30.0` 示例值，把佣金、印花税、滑点合并为对称单边成本。owner 要求先解决交易费用口径，指定佣金采用“万一免五”，印花税和滑点采用常用值。

### 决策

策略 1 P0 默认交易成本 profile 定为 `cn_a_share_wanyi_no_min_slip5_v20260602`：

1. 佣金 `commission_bps = 1.0`，买卖双边收取。
2. 最低佣金 `min_commission_cny = 0.0`，即免 5 元最低佣金。
3. 印花税买入侧 `stamp_tax_buy_bps = 0.0`。
4. 印花税卖出侧 `stamp_tax_sell_bps = 5.0`。
5. 买入滑点 `slippage_buy_bps = 5.0`，卖出滑点 `slippage_sell_bps = 5.0`。
6. 单一 `p_cost_bps=30.0` 不再作为 OQ-010 默认成本口径；后续实现需改为分项成本。

### 理由

“万一免五”符合 owner 对小资金成本的指定；卖出侧 5 bps 印花税与当前证券交易印花税减半征收后的常用 A 股口径一致；5 bps 买卖滑点作为 P0 基线能覆盖日线小资金回测中的常见成交价偏移，不把滑点误记为显性费用。分项建模比单一 `cost_bps` 更能表达买卖方向差异和报告可追溯性。

### 影响

新增 `docs/prd/PRD_20260602_02_OQ010交易成本口径.md`。OQ-010 的成本子项从“待 owner 确认”变为“已决策、待实现”；OQ-010 仍保留 open，因为调仓频率、持股数、单票权重上限和策略质量迭代仍未完全定稿。后续实现 PR 需改 `sql/ml/strategy1/08_run_backtest.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、README 和报告脚本。

### 备选方案

继续使用单一 `p_cost_bps=30.0`；放弃，因为无法表达卖出单边印花税和免最低佣金。把滑点并入 `fee_cny`；放弃，因为滑点应体现为成交价偏移，显性费用应只含佣金和税费。按券商/交易所所有细项逐项建模；暂不采用，因为 P0 小资金基线先需要稳定、可解释的默认 profile。

### 相关文件

`docs/prd/PRD_20260602_02_OQ010交易成本口径.md`, `docs/策略1-ml_pv_clf_v0-runner设计.md`, `docs/prd/PRD_20260601_02_策略1BQML回测闭环.md`, `.agent/memory/OPEN_QUESTIONS.md`, `TODO.md`

## DECISION-20260602-05: 策略 1 报告中文归因旧口径（已废弃）

日期: 2026-06-02
状态: superseded by DECISION-20260602-06
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

策略 1 runner 已能生成基础 Markdown/HTML 报告，但现有 `scripts/strategy1/render_report.py` 仍使用英文标题和指标名，只展示汇总绩效、模型指标、NAV 和回撤图。owner 要求报告改为中文，展示买卖细节，能看到与沪深 300 的对比，并在策略效果不好时让 AI 分析亏损节点买了什么、可能原因是什么。

### 决策

本决策已废弃，不再作为实现依据。有效口径见 `DECISION-20260602-06`：

1. 策略 1 runner 和 ADS 主 benchmark 使用中证 1000 canonical `sec_code='000852.SH'`，作为评估主基准 / 归因主基准。
2. 沪深 300 canonical `sec_code='000300.SH'` 仅作为报告展示对比基准，满足 owner 阅读口径，但不替代评估主基准。
3. 中证 500 `000905.SH` 可作为辅助风格基准展示；展示 / 辅助基准必须固化到报告 artifact，保证可复核。
4. 报告用户可见文本中文化，技术 ID（`run_id`、`model_id`、`backtest_id`、`sec_code`）保留原值。
5. 正文展示成交摘要、亏损贡献、不成交跳过样例；完整成交、持仓、NAV、回撤和归因明细以 CSV / JSON artifact 输出。
6. AI 诊断必须先生成结构化 `diagnosis_evidence.json`，只基于证据包输出中文分析；没有新闻/公告/外部事件证据时，必须明确写“当前证据不足，无法判断”，不得编造外部原因。

### 理由

PR #18 review 指出，旧版口径与策略 1 原始 PRD §8.4 的中证 1000 评估基准冲突，会把中小盘 beta 误读为选股 alpha。owner 确认第一个问题按 review 建议处理，因此本决策被 `DECISION-20260602-06` 替代。报告中文化、交易明细、证据包和 AI 诊断要求仍保留，但 benchmark 分层以新决策为准。

### 影响

`docs/prd/PRD_20260602_03_策略1中文报告归因分析.md` 已按 `DECISION-20260602-06` 修订。后续实现需改 `sql/ml/strategy1/08_run_backtest.sql`、`09_build_metrics_and_report_inputs.sql`、`10_qa_runner_outputs.sql`、`scripts/strategy1/render_report.py` 和 `sql/ml/strategy1/README.md`。实现时不得按本废弃决策改 benchmark；必须以 `DECISION-20260602-06` 为准。

### 备选方案

只把现有报告翻译成中文；放弃，因为不能回答买卖细节和亏损原因。只展示单一大盘对比基准；放弃，因为策略 1 原始股票池偏中小盘，缺少风格对照会误判 alpha。让 AI 直接读整份报告自由分析；放弃，因为缺少结构化证据约束，结论不可追溯。

### 相关文件

`docs/prd/PRD_20260602_03_策略1中文报告归因分析.md`, `scripts/strategy1/render_report.py`, `sql/ml/strategy1/08_run_backtest.sql`, `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`, `sql/ml/strategy1/10_qa_runner_outputs.sql`, `sql/ml/strategy1/README.md`, `TODO.md`

## DECISION-20260602-06: 策略 1 报告基准分层与证据包治理口径

日期: 2026-06-02
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

PR #18 review 指出，`PRD_20260602_03_策略1中文报告归因分析.md` 把沪深 300 设为报告 / runner 主基准，会与策略 1 原始 PRD §8.4 的中证 1000 评估基准冲突。策略 1 股票池偏中小盘，若把沪深 300 当评估主基准，会把中小盘 beta 误读为选股 alpha。owner 确认第一个问题按 review 建议处理，不再按原“benchmark 以沪深 300 为主基准”的说法执行。

### 决策

1. 策略 1 runner 和 ADS 主 benchmark 保持中证 1000 canonical `sec_code='000852.SH'`，作为评估主基准 / 归因主基准。
2. 沪深 300 canonical `sec_code='000300.SH'` 作为报告展示对比基准，满足 owner 阅读口径，但不替代评估主基准。
3. 中证 500 `000905.SH` 作为可选风格辅助基准；所有展示 / 辅助基准必须固化到 `benchmark_nav.csv` 和 `metrics.json.artifact_manifest`。
4. `diagnosis_evidence.json` 必须有稳定 schema（P0 为 `strategy1_report_evidence_v1`），定义 required/optional、空数组和 `null` 语义。
5. P0 持仓亏损贡献采用持仓窗口贡献近似：`SUM(ads_backtest_position_daily.weight * dwd_stock_eod_price.ret_1d)`，并记录归因覆盖率。
6. `--ai-analysis-mode auto` 必须定义 timeout、重试和 fallback：LLM 调用失败时退化为 `evidence_only` 并记录脱敏错误；`llm` 模式失败则非零退出。

### 理由

中证 1000 与策略 1 的中小盘股票池风格更匹配，是判断选股 alpha 的正确评估基准。沪深 300 可作为 owner 熟悉的大盘展示口径，但不能作为 alpha 归因主口径。证据包 schema、归因公式和 AI fallback 是后续实现可测试、可复核和不误导的基础。

### 影响

`PRD_20260602_03_策略1中文报告归因分析.md` 从“沪深 300 主基准”修订为“中证 1000 评估主基准 + 沪深 300 展示对比基准”。后续实现 PR 不应把 `08/09` 的 `p_benchmark` 改为 `000300.SH`；应保持 / 明确为 `000852.SH`，并由 `render_report.py` 查询和固化 `000300.SH` 展示基准。`DECISION-20260602-05` 被本决策 supersede。

### 备选方案

继续把沪深 300 作为 runner / ADS 主基准；放弃，因为会和原策略 PRD §8.4 冲突并误判 alpha。只展示中证 1000，不展示沪深 300；放弃，因为 owner 仍需要大盘展示对比。辅助基准实时查询 DWD 不固化；放弃，因为会降低报告 artifact 可复核性。

### 相关文件

`docs/prd/PRD_20260602_03_策略1中文报告归因分析.md`, `.agent/memory/OPEN_QUESTIONS.md`, `TODO.md`, `scripts/strategy1/render_report.py`, `sql/ml/strategy1/08_run_backtest.sql`, `sql/ml/strategy1/09_build_metrics_and_report_inputs.sql`, `sql/ml/strategy1/10_qa_runner_outputs.sql`

## DECISION-20260603-01: OQ-010 第一轮 A/B/C 参数实验采用分阶段非笛卡尔积口径

日期: 2026-06-03
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

OQ-010 首轮质量迭代 PRD 已由 PR #35 合并，原矩阵包含阶段 A 的 4 个持股数 / 单票权重组合、阶段 B 的 3 个调仓频率、阶段 C 的 3 个标签 horizon，以及阶段 D 的 2 个特征集合。owner 询问阶段 A/B 是否应按 `4 * 3` 全量笛卡尔积执行，并追问第三阶段和最终 `2 * 2 * 2` 复核口径。

### 决策

阶段 A/B/C 第一轮基础执行不做全量笛卡尔积：

1. 阶段 A 固定 weekly 调仓，跑 4 个持股 / 权重实验：`5/20%`、`10/10%`、`20/5%`、`30/5%`；该记法表示“目标持股数 / 单票权重上限”，例如 `30/5%` 的目标单票等权约 3.33%，5% 只是上限，不是每只固定买 5%。
2. 阶段 B 只使用阶段 A 的晋级组合，跑 3 个调仓频率：weekly、biweekly、monthly。
3. 阶段 C 只使用阶段 A/B 的晋级组合参数，跑 3 个标签 horizon：5d、10d、20d；执行调仓频率固定沿用阶段 B 晋级频率，不按 horizon 硬绑重设。
4. 基础 A+B+C 实验数为 `4 + 3 + 3 = 10`，不是 `4 * 3 * 3 = 36`；包含阶段 D 财务特征实验时，完整第一轮基础实验数为 12。
5. 如果阶段 A/B、A/C 或 B/C 显示明显交互风险，可追加最多 `2 * 2 = 4` 个 pairwise 小型交互复核实验。
6. 默认不跑 `2 * 2 * 2`；只有至少两类 pairwise 复核显示明显联动、A/B/C 晋级结果都很接近或 owner 明确要求时，才补最多 8 个最终三变量保底复核实验。
7. 交互复核使用独立 `experiment_group`，不得替代第一轮默认分阶段路径，也不得扩展为 `4 * 3 * 3` 全量搜索。

### 理由

分阶段执行能先隔离持股分散度、调仓频率、标签 horizon 和财务特征的影响，减少第一轮实验数量和解释歧义。全量笛卡尔积会增加 BigQuery 执行成本，也容易让收益变化来源不清。保留 A/B、A/C、B/C 三类 pairwise 小型交互复核和最终 `2 * 2 * 2` 保底复核，可以在成本受控的前提下覆盖“局部组合明显更优”的边界风险。其中 A/C 复核用于防止在 5d+weekly 条件下选出的持股数，在 10d/20d 长 horizon 胜出时不再稳。

### 影响

`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md` 已补充阶段 A/B/C 非笛卡尔积执行口径、A/B + A/C + B/C pairwise 小型交互复核、最终 `2 * 2 * 2` 保底复核、执行顺序、风险处理和 owner 确认项。后续实现 manifest / 对比报告 / QA 时，应按基础 `4 + 3 + 3` 路径组织实验；只有满足交互复核触发条件时，才补跑 pairwise 或最终保底复核实验。

### 备选方案

直接跑 `4 * 3 * 3 = 36` 全量组合；放弃，因为第一轮成本更高且不利于解释变量贡献。默认跑 `2 * 2 * 2`；放弃，因为在 pairwise 风险未暴露前仍可能是不必要成本。完全不做交互复核；放弃，因为会漏掉持股分散度、调仓频率与标签 horizon 之间的潜在交互。只覆盖 A/B 与 B/C pairwise；放弃，因为 A/C（持股数 × label horizon）同样可能存在交互。

### 相关文件

`docs/prd/PRD_20260603_02_策略1首轮质量迭代实验.md`, `.agent/memory/OPEN_QUESTIONS.md`, `TODO.md`

## DECISION-20260603-02: GCP 生产数据流水线采用 Cloud Run Jobs + Dataform + Cloud Composer

日期: 2026-06-03
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

OQ-005 原问题是物化与调度选型：dbt（含 `persist_docs`）还是纯 `bq` SQL 脚本 + 自建调度。随着项目已明确长期在 GCP / BigQuery 上完成每日采集、GCS raw、ODS→ADS ETL、策略 runner 和报告链路，owner 要求按 GCP 原生方案写详细 PRD，并明确每日定时拉取只覆盖当前已消费 ODS。

### 决策

长期生产链路采用：

1. Cloud Run Jobs 负责 Tushare/Tinyshare API 到 GCS Parquet 的每日采集。
2. Dataform / BigQuery Studio pipeline 负责 ODS→DIM/DWD/DWS/ADS 的 BigQuery SQL 转换、依赖、assertions 和文档。
3. Cloud Composer 负责编排采集、ODS 检查、Dataform、metadata、QA、可选 runner / report、失败重试、补跑和告警。
4. 首批每日生产采集只覆盖当前 SQL 实际消费的 14 张 ODS：`daily`、`adj_factor`、`stk_limit`、`suspend_d`、`daily_basic`、`index_daily`、`index_dailybasic`、`stock_basic`、`trade_cal`、`namechange`、`fina_indicator`、`income`、`balancesheet`、`cashflow`。
5. 未被当前 DIM/DWD/DWS/ADS 消费的 ODS endpoint 不进入首批生产定时任务；新增 endpoint 必须先更新采集 manifest、schema contract、单位契约和 QA。
6. BigQuery Studio / Colab Enterprise notebook 可用于探索、抽样验证和数据审查，不作为长期正式采集主方案。

### 理由

Cloud Run Jobs 更适合运行有明确开始/结束的 Python 采集任务，并能用容器固定依赖和权限边界。Dataform 是 GCP 原生 BigQuery SQL workflow 工具，适合管理 ODS→DIM/DWD/DWS/ADS 的 SQL 依赖、assertions、文档和增量表。Cloud Composer 是托管 Airflow，适合跨 Cloud Run、BigQuery、Dataform、报告和告警的全流程编排。该组合比纯 Scheduled Queries 覆盖面更完整，也比在 notebook 中维护生产采集更可测试、可回滚、可监控。

### 影响

`docs/prd/PRD_20260603_03_GCP数据流水线方案.md` 已定义实现阶段：先做采集 manifest 和 Cloud Run Jobs，再迁移 Dataform P0 转换，之后用 Cloud Composer 串全流程。`OPEN_QUESTIONS.md` 的 OQ-005 状态更新为 PRD 草案已新增，待 review/合并与实施后关闭。后续工程 TODO 应围绕首批 14 张 ODS 的 manifest、schema contract、Dataform definitions、Composer DAG 和 QA 门禁展开。

### 备选方案

继续纯 `bq` SQL + 手工 / 自建调度；放弃，因为依赖、重试、文档、QA 和补跑会随表数增长变脆。直接采用 dbt Core + 自建运行环境；保留为可选替代，但当前项目长期绑定 GCP / BigQuery，Dataform 的原生集成更直接。用 BigQuery Studio notebook 做每日采集；放弃作为长期主方案，因生产采集需要容器依赖、日志、权限、重试和回滚能力。只用 BigQuery Scheduled Queries；放弃，因为无法覆盖外部 API 采集和跨服务编排。

### 相关文件

`docs/prd/PRD_20260603_03_GCP数据流水线方案.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/ARCHITECTURE_MEMORY.md`, `TODO.md`

## DECISION-20260603-03: ODS Parquet schema 修复默认采用 GCS 原文件重写

日期: 2026-06-03
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

数据审查发现 10 张 ODS 外部表存在 2019+ Parquet 物理类型与 BigQuery 外部表 schema 不一致的问题。典型原因是 pandas / pyarrow 在部分分区中把应为 `FLOAT64` 的列写成 `INT32` / `INT64`，或把应为 `INT64` 的列写成 `DOUBLE`。这些问题发生在 GCS Parquet 文件层，BigQuery 外部表按具体列读取时会失败，`SAFE_CAST` 不能兜底。

### 决策

1. ODS Parquet schema mismatch 的默认修复路径为 schema contract → GCS 原 Parquet 读取 → 显式 cast → staging → 临时 external table 显式 schema 验证 → write-once backup → 发布正式 prefix → 正式 ODS QA。
2. 修复过程只改变 Parquet 物理 schema，不改变业务值口径、不补缺数、不创建伪空 Parquet。
3. API 重拉只作为原文件损坏、缺失、行数无法复原或 owner 明确要求的补救路径，不作为默认修复方式。
4. 当前 P0 源表 `ods_tushare_stk_limit` 优先修复；其余 9 张表按 P1/P2/P3 分批修复。
5. ingestion / Parquet 生成侧必须按同一 schema contract 显式 cast，防止新增分区再次出现类型漂移。
6. 已匹配 contract 的文件应标记为 `ok` 并跳过重写 / 发布；整数物理类型加宽到 `FLOAT64` 时必须确认字段量级低于 `2^53`，否则进入 `manual_review`。

### 理由

当前问题是 Parquet 物理 schema 不稳定，不是首先由 API 缺数或值级差异造成。直接按当前 API 重拉历史 raw 会引入接口快照变化、历史版本变化、请求参数变化和单次返回行数上限风险。基于 GCS 原文件做 schema-preserving rewrite 可以在保留行数、业务值和原始采集口径的前提下修复 BigQuery 外部读取失败。

### 影响

`docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md` 定义后续实现产物：schema contract、repair script、validate script、`sql/qa/06_ods_parquet_schema_checks.sql` 和修复报告。`KNOWN_CONSTRAINTS.md` 已写入该修复边界。后续任何 raw schema 修复 PR 不应默认用当前 API 快照覆盖历史 GCS raw；若触发 API 重拉补救路径，必须单独记录请求参数、row limit 命中状态、分区范围和与原文件差异。实现脚本必须保证 backup write-once 和重复执行幂等。

### 备选方案

直接从 Tushare/Tinyshare API 重新拉取 2019+ 历史数据并覆盖 raw；放弃，因为会引入当前 API 快照与历史采集口径差异，并存在 6000 行上限导致漏数风险。只在 DWD SQL 中 `SAFE_CAST`；放弃，因为 BigQuery 外部表在读取 Parquet 物理类型不匹配列时会先失败，SQL cast 无法执行。暂不修复 P0 源表，仅在未来用到字段时再处理；放弃，因为 `ods_tushare_stk_limit` 属当前 P0 源表，表级全字段读取和后续扩展应先恢复稳定。

### 相关文件

`docs/prd/PRD_20260603_04_ODS外部表ParquetSchema修复.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`, `TODO.md`

## DECISION-20260603-04: OQ-010 实验并发调度与隔离采用 GCS 原子锁 + BigQuery 状态表

日期: 2026-06-03
状态: active
负责人: owner
Agent ID: DeepSeek V4
模型: DeepSeek V4

### 背景

OQ-010 同阶段实验串行执行耗时过长，但直接本地多进程并发跑 SQL 存在互相污染风险。PRD 已定义并发方案（`docs/prd/PRD_20260603_05`），需要实现状态表、锁机制和调度器。

### 决策

1. 锁原语采用 GCS object `ifGenerationMatch=0` create-if-not-exists，放在 `gs://ashare-artifacts/locks/strategy1/oq010/<lock_key>.lock`。不依赖 BigQuery 状态表做低延迟锁管理。
2. BigQuery `ashare_meta.strategy1_experiment_run_status` 只用于审计追踪和 resume 输入，不承担锁管理职责。
3. 调度器 `scripts/strategy1/run_oq010_experiments.py` 支持全部 PRD 定义参数：`--manifest`、`--stage-id`、`--experiment-id`、`--max-parallel`、`--max-parallel-backtest`、`--dry-run`、`--force-replace`、`--resume`、`--resume-from-step`、`--fail-fast`、`--allow-cross-stage`、`--log-dir`、`--scheduler-instance-id`、`--lock-ttl-minutes`。
4. 锁 key 分 6 类：`train`、`predict`、`portfolio`、`backtest`、`summary`、`diagnosis`，按 `prediction_run_id` / `run_id` / `backtest_id` 粒度隔离。
5. 默认 `max_parallel_backtest=1`，08 ledger 并发需 owner 验收后手动提高。
6. Phase 1 只实现状态表 DDL、调度器 dry-run、GCS 锁原语和并发 QA SQL，不实际在 BigQuery 端到端执行并发实验。Phase 2-4 后续再实现。

### 理由

GCS object 条件创建是 BigQuery 项目中最简单、最廉价的原子锁机制，无额外服务依赖、无需 Firestore/Cloud Tasks。状态表用 MERGE 做 upsert，只保证最终一致性，不解决「查-写」竞态。锁 lease/heartbeat 防止调度器崩溃后锁永久残留。

### 影响

新增文件：`sql/meta/02_strategy1_experiment_run_status.sql`、`scripts/strategy1/run_oq010_experiments.py`、`sql/qa/07_strategy1_experiment_concurrency_checks.sql`、`docs/策略1实验并发调度器运行手册.md`。`KNOWN_CONSTRAINTS.md` 更新并发约束。Phase 1 不改变现有 runner 执行方式；启用并发前需实现 Phase 2+。

### 备选方案

- 用 BigQuery 事务 + 状态表 CAS 做锁：不可行，BigQuery 无行级锁或 SELECT FOR UPDATE。
- 用 Firestore 事务做锁：增加服务依赖和权限管理，P0 不必要。
- 仅依赖 BigQuery 状态表「查无 running 写 running」做锁：竞态不可靠，PRD 已明确禁止。

### 相关文件

`docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`, `sql/meta/02_strategy1_experiment_run_status.sql`, `scripts/strategy1/run_oq010_experiments.py`, `sql/qa/07_strategy1_experiment_concurrency_checks.sql`, `docs/策略1实验并发调度器运行手册.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`

## DECISION-20260603-05: OQ-010 调度器参数注入和状态表历史必须硬门禁

日期: 2026-06-03
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

PR #45 review 指出并发调度器的 SQL 参数注入存在静默失败风险：当 `DECLARE p_* DEFAULT` 格式未匹配时，runner 会继续使用 SQL 文件内默认 `run_id` / `backtest_id`，可能把并发实验写入错误输出范围。状态表 DDL 原先使用 `CREATE OR REPLACE TABLE`，会清空 audit/resume 历史。

### 决策

1. `scripts/strategy1/run_oq010_experiments.py` 执行 BigQuery step 前必须扫描所有 `DECLARE p_* DEFAULT` 参数，并为每个参数注入 manifest/default 值。
2. 参数缺失、声明格式不支持、类型不匹配或必需隔离参数未声明时，step 必须失败；禁止静默沿用 SQL 默认值。
3. dry-run 必须对可执行实验做 SQL 参数注入预检；blocked placeholder 实验只展开计划，不做类型预检。
4. `ashare_meta.strategy1_experiment_run_status` DDL 必须使用 `CREATE TABLE IF NOT EXISTS`，保留历史 audit/resume 记录。
5. terminal status 写入前必须停止 heartbeat，避免 `running` 覆盖 `succeeded` / `failed`；获取 GCS lock 后释放必须在 `finally` 中完成。

### 理由

OQ-010 并发的核心安全边界是 experiment/run/backtest 隔离。参数注入静默失败会绕过隔离，且 dry-run 若不预检无法提前发现。状态表承载失败恢复和审计，重建清空会破坏 resume 与问题追溯。

### 影响

PR #45 中 `run_oq010_experiments.py` 已实现强校验参数注入、dry-run 预检、heartbeat terminal status 保护和锁 finally 释放；状态表 DDL 改为 `sql/meta/02_strategy1_experiment_run_status.sql` 且使用 `CREATE TABLE IF NOT EXISTS`；并发 QA 改名为 `sql/qa/07_strategy1_experiment_concurrency_checks.sql`，避开 PR #43 的 `06_ods_parquet_schema_checks.sql`。

### 备选方案

继续用 `_inject_parameter()` 找不到声明就返回原 SQL；放弃，因为会让默认 SQL 参数在并发实验中静默生效。只在真实执行时检查、不在 dry-run 预检；放弃，因为 dry-run 是 owner 启动前识别 manifest/SQL 参数问题的主要入口。继续 `CREATE OR REPLACE TABLE` 重建状态表；放弃，因为会破坏 audit/resume 历史。

### 相关文件

`scripts/strategy1/run_oq010_experiments.py`, `sql/meta/02_strategy1_experiment_run_status.sql`, `sql/qa/07_strategy1_experiment_concurrency_checks.sql`, `docs/策略1实验并发调度器运行手册.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/AGENT_HANDOFF.md`, `TODO.md`

## DECISION-20260604-01: OQ-010 先 Ledger P0/P1/P2 再月度滚动重训

日期: 2026-06-04
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

策略 1 当前最优参数已固化为正式 fixed-model baseline。owner 后续希望同时处理 Ledger v1 交易执行语义、2026 扩展回测、ledger state resume 和月度滚动重训。若把这些变化放在同一实现或同一评估里，收益差异无法归因到交易执行、回测区间、状态恢复或模型生命周期中的哪一项。

### 决策

1. 不新增第三篇 PRD；继续维护两篇 PRD。
2. `PRD_20260604_01_策略1LedgerV1交易执行语义.md` 承接三个阶段：
   - P0: Ledger v1 交易执行语义。
   - P1: fixed-model 连续扩展回测，区间 `2024-01-02` 至 `2026-04-30`。
   - P2: ledger state resume。
3. `PRD_20260604_02_策略1月度滚动重训.md` 只定义模型生命周期、月度模型选择、失败回退和 PIT-safe prediction stream。
4. 实现顺序固定为 Ledger v1 P0 → Ledger v1 P1 → Ledger v1 P2 → 月度滚动重训。
5. 月度滚动重训正式效果归因必须以 Ledger P1/P2 产出的 fixed-model extended baseline 为对照。

### 理由

2026 扩展回测和 resume 都是回测执行 / 状态管理能力，应该在 Ledger 语义稳定后先解决。月度滚动重训是模型生命周期变化，应在 fixed-model extended baseline 和 resume 等价性验收后再做，避免把模型变化与交易执行变化混在一起。

### 影响

`TODO.md`、`OPEN_QUESTIONS.md`、`IMPLEMENTATION_STATUS.md` 和交接摘要均改为同一实现顺序。后续 agent 不应直接跳到月度重训，也不应用只跑 2026 片段再简单拼接的方式替代 Ledger P1/P2 验收。

### 备选方案

新增第三篇 PRD 专门描述 2026 扩展与 resume；放弃，因为这两个能力本质上属于 Ledger 回测执行语义，拆成第三篇会增加跨文档依赖和口径漂移。先实现月度滚动重训；放弃，因为模型生命周期变化会污染 Ledger A/B 和 2026 fixed-model baseline 的归因。

### 相关文件

`docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`, `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`, `TODO.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`

## DECISION-20260604-02: OQ-010 因子贡献度分析不做消融实验

日期: 2026-06-04
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

正式 baseline 已完成，owner 希望分析各个因子的贡献度，用于解释当前策略收益与后续 Ledger / 月度重训结果。消融实验能给出更强的边际贡献证据，但需要大量重训 / 重预测 / 回测，会显著增加运行成本和解释复杂度。

### 决策

1. 新增 `PRD_20260604_03_策略1因子贡献度分析.md`。
2. 因子贡献度分析不做消融实验，不做 drop-one-factor 或 drop-one-factor-group 重训。
3. P0 只基于已训练 selected model、已有 prediction、已有 backtest 和已有 feature 数据做只读分析。
4. 输出模型分数贡献、单因子 RankIC / bucket lift、组合因子暴露和组合因子归因 proxy。
5. 实施顺序建议放在 Ledger v1 P0 前，但这只是顺序安排，不代表优先级高于 Ledger v1 或月度滚动重训。

### 理由

当前首要需要的是解释现有 baseline 的因子来源，而不是重新评估每个因子的移除效果。只读型因子贡献度分析成本低、对现有 runner 风险小，且不会改变交易执行语义或模型生命周期，适合作为 Ledger v1 A/B 前的解释基准。

### 影响

后续实现应新增独立 factor attribution artifact 和 QA，禁止引入 `ablation_run_id`、`drop_feature_run_id` 等消融实验路径。若未来 owner 需要消融实验，应另写 PRD 并单独审批计算成本和运行矩阵。

### 备选方案

直接做消融实验；放弃，因为本轮 owner 明确不考虑消融实验，且成本/运行时间较高。把因子贡献度塞进既有模型质量诊断 PRD；放弃，因为现有诊断 PRD 已实现，新增独立 PRD 更容易限定非消融边界和 artifact 契约。

### 相关文件

`docs/prd/PRD_20260604_03_策略1因子贡献度分析.md`, `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`, `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`, `TODO.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`

## DECISION-20260604-03: 策略 1 训练回测迁移为 Cloud Run Jobs

日期: 2026-06-04
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

当前策略 1 runner 基于 BigQuery ML + BigQuery SQL scripting。BQML 训练成本偏高，BigQuery scripting 做日级有状态 ledger 在长区间和多实验场景下耗时较长。owner 要求把训练和回测都做成 Cloud Run Job，并明确多实验对照时不要设置默认并发上限：默认做几个实验就并发几个，但 owner 可以显式选择并发几个。

### 决策

1. 新增 `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`，只写一篇统一 PRD，不拆训练 PRD 和回测 PRD。
2. Cloud Run P0 用 scikit-learn logistic regression 替代当前 BQML `LOGISTIC_REG` 的训练、候选模型评价和批量预测。
3. scikit-learn 只替代模型训练 / 预测能力，不替代 BigQuery DWS/ADS、GCS artifact、报告、诊断和 QA；P0 仍需 `google-cloud-bigquery`、`google-cloud-bigquery-storage`、`google-cloud-storage`、`pyarrow`、`polars` / `pandas`、`joblib` 等依赖。
4. Cloud Run P0 用 Python `ledger_exec_v1` 替代 BigQuery `08_run_backtest.sql` 中的有状态 ledger 执行；交易语义必须与 `PRD_20260604_01_策略1LedgerV1交易执行语义.md` 对齐。
5. 多实验 Cloud Run orchestrator 的默认并发为本次 manifest 可执行实验数量；`--max-parallel-experiments` 未设置或为 0 时不得隐式降到 2、1 或其他保守默认值。
6. owner 可通过 `--max-parallel-experiments N` 显式限流；项目代码不写死默认 backtest 子并发上限。
7. 既有 BigQuery ML + SQL runner 原计划保留为 reference / fallback，直到 Cloud Run sklearn + Python ledger 通过契约、QA 和回测语义一致性验收；**2026-06-05 起本条被 `DECISION-20260605-03` supersede，BQML / SQL runner 仅保留为 historical reference / audit，不再作为 fallback**。
8. sklearn P0 默认 `class_weight=None`，贴近当前 BQML baseline 的非类别平衡训练口径；`class_weight='balanced'` 只能作为后续独立建模实验。
9. sklearn 正则候选网格必须按 sklearn 原生 `C` / `penalty` / `l1_ratio` 重新定义，不得直接把 BQML `L1_REG` / `L2_REG` 数值翻译过去。
10. Cloud Run sklearn selected model 原计划必须通过 BQML baseline 模型质量对等门槛；**2026-06-05 起该 parity gate 仅作为历史对照证据，不再是后续 accepted Cloud Run Python baseline 的硬门槛**。后续 baseline 接受应以 native acceptance / 新模型 PRD 为准。

### 理由

训练、预测、回测、报告和并发调度共享同一组 `experiment_id`、`run_id`、`prediction_run_id`、`backtest_id`、状态表和 artifact 路径。拆成多篇 PRD 容易让 score orientation、prediction stream、ledger 输入和并发语义漂移。Cloud Run Jobs 可以把训练和回测放进可配置容器环境，便于降低 BQML 成本、提高回测执行弹性，并把多实验并发交给 Cloud Run / GCP quota 和 owner 显式参数控制。

### 影响

后续实现应新增 `scripts/strategy1_cloudrun/` 执行包、Cloud Run Dockerfile / build config、`sql/ml/strategy1/16_qa_cloudrun_runner_outputs.sql` 和运行手册。Cloud Run runner 必须继续写既有 ADS 契约表，并通过 `10`、`12`、必要时 `14` / `15` 以及新增 `16` QA。`16` QA 应校验 `model_quality_parity_status` 与 RankIC/topN/coverage delta 一致。月度滚动重训后续应优先复用该 Cloud Run train/predict job，而不是继续扩展 BQML 训练路径。

### 备选方案

继续优化 BQML + SQL runner；当时保留为 fallback，但 2026-06-05 起已被 `DECISION-20260605-03` supersede，不再作为 fallback。拆成训练 PRD 和回测 PRD；放弃，因为两者共享执行身份、artifact、prediction stream 和并发契约。直接引入 LightGBM / XGBoost；当时放弃作为 P0，因为会把执行环境迁移和模型族升级混在一起，后续可按新的 Python backend PRD 单独评估。

### 相关文件

`docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`, `docs/prd/PRD_20260604_01_策略1LedgerV1交易执行语义.md`, `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`, `docs/prd/PRD_20260603_05_策略1实验并发调度与隔离.md`, `TODO.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`

## DECISION-20260604-04: OQ-005 每日生产采集采用 current-scope 单 Job + 固定出口

日期: 2026-06-04
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

OQ-005 生产写入 smoke 期间，多个分组 Cloud Run Jobs 在短时间内连续请求 Tushare 兼容 API，存在同一 Tushare token 被识别为多 IP 使用的风险。Composer `kubernetes` queue 任务曾停留在 queued 且没有创建 Cloud Run execution，default Celery queue 的只读 smoke 已验证可由 scheduler 正常派发。

### 决策

1. 每日生产采集入口统一使用 `ashare-ingest-current-scope` 单个 Cloud Run Job execution，顺序执行当前实际消费的 14 个 ODS endpoint。
2. 4 个分组 Jobs（`market_eod`、`index_eod`、`dim_snapshot`、`finance_recent`）保留为诊断和单组补救入口，不作为每日 DAG 默认并发入口。
3. Cloud Run Jobs 使用 Direct VPC egress + Cloud NAT + 区域静态外部 IP 固定出口；Job 模板默认保留 `--dry-run`，Composer 生产路径在 `ashare_pipeline_dry_run=false` 时显式传入 `--allow-gcs-write`。
4. Composer DAG 使用 default Celery queue，不显式指定 `queue="kubernetes"`。
5. live ingestion 成功/失败/空返回必须写入 `ashare_meta.ingestion_run` 与 `ashare_meta.ingestion_partition_status`；dry-run / API 只读 smoke 不写生产 meta 表。
6. 当前 Airflow 变量为 `ashare_pipeline_dry_run=false`、`ashare_enable_full_refresh=false`；每日生产采集启用，但完整 ODS→DIM/DWD/DWS/ADS 转换仍需 `ashare_enable_full_refresh=true` 显式进入。

### 理由

单 execution 顺序执行能在当前 token/IP 约束下减少并发出口风险，并且更容易定位单日采集失败。固定出口使 Cloud Run 请求来源稳定。default Celery queue 已通过纯 scheduler smoke，避免 Kubernetes worker pod queued 后无 Cloud Run execution 的派发问题。

### 影响

OQ-005 Phase 1.7 已部署 `ashare-ingest-current-scope`、Direct VPC egress、Cloud NAT 固定出口和更新后的 Composer DAG。PR #58 review follow-up 已补 BigQuery meta 状态写入；raw GCS canonical 路径固定为 `api=<api>/endpoint=<partition_endpoint>/partition_date=...`，并已用 BigQuery `INFORMATION_SCHEMA.TABLE_OPTIONS` 复核当前 14 张 ODS 与 10 张 schema repair 表 source URI。`2026-05-20` 至 `2026-06-03` SSE 开市日生产 GCS 回填全部成功并逐日通过 `sql/qa/09_ods_daily_partition_readiness.sql`；`manual_oq005_daily_prod_20260604_01` 已按生产路径写入 `2026-06-04` 并成功完成 readiness。OQ-005 仍保持 open，待 Dataform/BigQuery SQL 生产转换、告警、补跑和运维观测闭环完成后关闭。

### 备选方案

继续每日 DAG 并发触发 4 个分组 Jobs；放弃，因为会增加同一 token 短时间多出口请求风险。继续使用 `kubernetes` queue；放弃，因为当前环境出现过 scheduler 派发后任务停留 queued 且没有创建 Cloud Run execution 的现象。把 full refresh 放回每日主链；放弃，因为每日调度只应处理最新业务日，2019+ 全历史 schema 检查和完整重建必须作为显式维护/补跑路径。

### 相关文件

`scripts/ingestion/run_ingestion_job.py`, `orchestration/cloud_run_jobs/deploy_ingestion_jobs.sh`, `orchestration/cloud_run_jobs/ingestion_jobs.yaml`, `orchestration/cloud_run_jobs/README.md`, `orchestration/composer/dags/ashare_daily_pipeline_v0.py`, `orchestration/composer/README.md`, `orchestration/README.md`, `TODO.md`, `.agent/memory/ARCHITECTURE_MEMORY.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`

## DECISION-20260605-01: OQ-005 Phase 2.0 用 warehouse_mode 显式区分每日与兼容全量转换

日期: 2026-06-05
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

OQ-005 Phase 2.0 需要在现有 Composer DAG 中接入 ODS readiness 之后的 BigQuery SQL 兼容路径。现有 DIM/DWD/DWS SQL 大多仍是 CTAS / 全量重建口径，尚未实现 Phase 2.2 的每日增量影响窗口。旧变量 `ashare_enable_full_refresh=true` 只能表示进入全量分支，无法区分每日增量、维护重建、只读 QA 和 ADS 契约初始化。

### 决策

本决策 supersedes `DECISION-20260604-04` 第 6 条中关于完整 ODS→DIM/DWD/DWS/ADS 转换入口只由 `ashare_enable_full_refresh=true` 控制的描述；`DECISION-20260604-04` 其余采集入口、固定出口和 default Celery queue 决策保持 active。

1. `ashare_daily_pipeline_v0` 以 `warehouse_mode` 作为 ODS→DIM/DWD/DWS/QA 分支主控。
2. 默认 `warehouse_mode=daily_current` 只执行采集、ODS readiness 和 pipeline 状态回写；Phase 2.2 增量影响窗口完成前，不进入 CTAS 转换分支。
3. 现有 BigQuery SQL CTAS 转换只通过 `warehouse_mode=full_rebuild` 或 `warehouse_mode=full_rebuild_compat` 显式手工进入。
4. 兼容变量 `ashare_enable_full_refresh=true` 保留，但当 selected mode 为 `daily_current` 时必须记录为 `full_rebuild_compat`，不得把 CTAS 全量重建标记为每日增量。
5. `warehouse_mode=qa_only` 只执行 ODS readiness 后的只读 QA，不改生产表。
6. ADS 契约初始化从每日默认链路剥离，只能通过 `enable_ads_contract_init=true` 手工启用。
7. `ashare_meta.pipeline_run` 与 `ashare_meta.pipeline_task_status` 记录 DAG run / task 状态、业务日期、mode、backend、BigQuery job / Cloud Run execution / Airflow log 链接。
8. `sql/meta/01_ods_field_unit_map.sql` 重命名为 `sql/meta/04_ods_field_unit_map.sql`，避免与 `sql/meta/01_create_meta_tables.sql` 编号冲突；DAG 和 README 使用显式文件顺序。

### 理由

每日生产调度必须避免把 2019+ 全历史 CTAS 扫描误当成增量写入。显式 mode 能让 smoke、只读 QA、维护重建和后续 Dataform / 增量路径共享同一 DAG，同时让状态表保留可审计的执行语义。

### 影响

Phase 2.0 实现分支 `codex/oq005-scheduler-phase2` 更新 Composer DAG、meta DDL、README、PRD 和记忆文件。部署后需要分别验证 `skip_ingestion=true` smoke、`warehouse_mode=qa_only` 只读 QA、`warehouse_mode=full_rebuild_compat` 维护链路和状态表 terminal 状态。OQ-005 仍保持 open，后续 Dataform definitions、增量影响窗口、告警、补跑和完整生产运维观测闭环完成后才能关闭。

### 备选方案

继续使用 `ashare_enable_full_refresh` 单开关；放弃，因为无法表达 `daily_current`、`qa_only`、`full_rebuild_compat` 和 ADS 契约初始化的差异。立即把现有 CTAS 标为每日增量；放弃，因为会造成运行状态与实际写入范围不一致。直接等待 Dataform 后再接状态表；放弃，因为 Phase 2.0 需要先把现有生产 DAG 的状态、QA 和手工维护路径闭环。

### 相关文件

`orchestration/composer/dags/ashare_daily_pipeline_v0.py`, `sql/meta/01_create_meta_tables.sql`, `sql/meta/04_ods_field_unit_map.sql`, `orchestration/composer/README.md`, `orchestration/README.md`, `sql/README.md`, `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`, `TODO.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`

## DECISION-20260605-02: OQ-005 窗口刷新估值特征按实际观测推导读取边界

日期: 2026-06-05
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5

### 背景

PR #65 合并后、部署 Composer 和生产 DML 前，真实 scratch full-vs-window 等价 QA 发现 `dws_stock_feature_valuation_daily.turnover_rate_zscore_60d` 在部分股票上与 canonical full path 不一致。价格特征的 60 个 SSE 交易日读取窗口足够覆盖价格类滚动窗口，但 `daily_basic` 对部分股票不是每日完整观测；SQL 使用 `ROWS BETWEEN 59 PRECEDING AND CURRENT ROW` 时需要 60 条实际估值观测，实际跨度可能超过固定交易日读取窗口。

### 决策

1. OQ-005 股票 DWD/DWS 窗口刷新中，价格特征读取窗口保持 60 个 SSE 交易日。
2. 估值特征读取边界按每只股票写入窗口首日前的实际 60 条估值观测推导，不用固定交易日窗口近似。
3. 标签、特征宽表和样本表写入窗口仍按 20 个 SSE 交易日向前回补。
4. full-vs-window 等价 QA runner 复制 canonical `_full` 表到 `_window` seed 时必须带 `trade_date` 分区过滤，兼容 `require_partition_filter=true`。
5. full-vs-window 等价 QA runner 必须校验 `build_start_date` 足够早，避免 full/window shadow 被同样截断后假通过。

### 理由

窗口刷新要与 canonical full SQL 在写入窗口内数值等价。对估值特征使用与价格特征相同的固定交易日读取窗口，会在 `daily_basic` 稀疏观测股票上截断 60 条观测窗口，导致 z-score 等滚动特征漂移。按每只股票实际观测推导读取边界，可以覆盖长期停牌或集中缺口股票；`build_start_date` guard 保证等价 QA 的 full shadow 有足够历史，避免非判别性通过。

### 影响

`sql/incremental/01_refresh_stock_dwd_dws_window.sql` 增加 `p_valuation_observation_window=60`，并在 DWD 估值刷新后按股票推导估值特征 read bounds；`p_valuation_feature_read_start_date` 仅作为全局分区裁剪下界和审计输出。`scripts/qa/run_windowed_refresh_equivalence.py` 的 seed copy 加分区过滤，并在真实运行前检查 `build_start_date`。后续部署 Composer 前必须合并该 hotfix；生产 smoke 仍需在合并后执行。

### 备选方案

继续使用统一 60 个交易日读取窗口；放弃，因为真实等价 QA 已证明会造成估值滚动特征漂移。把估值读取窗口固定扩大到 180 个交易日；放弃作为最终实现，因为对重度停牌或集中缺口股票仍是启发式。完全重建所有 2019+ DWD/DWS；放弃作为每日路径，因为 OQ-005 daily/backfill 目标是窗口化刷新，完整重建只属于显式维护链路。

### 相关文件

`sql/incremental/01_refresh_stock_dwd_dws_window.sql`, `scripts/qa/run_windowed_refresh_equivalence.py`, `sql/README.md`, `TODO.md`, `.agent/memory/ARCHITECTURE_MEMORY.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`

## DECISION-20260605-03: 策略执行层后续停止使用 BQML 与 SQL runner

日期: 2026-06-05
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5 Codex

### 背景

策略 1 已有 BigQuery ML + `sql/ml/strategy1` SQL runner 历史链路，并完成过 BQML baseline、Ledger v1 P1/P2、报告、诊断和 QA 验收。但 owner 明确表示后续不再使用 BQML 以及策略 SQL runner。主要原因是 BQML 成本偏高，SQL runner 在多实验、模型生命周期和有状态回测扩展上较慢且维护复杂；项目已开始迁移到 Cloud Run Python runner、task fan-out 和 sklearn/native 模型实验路线。

### 决策

1. 策略 1 后续训练、预测、候选、组合、回测、报告、诊断、月度滚动重训和多实验搜索，不再以 BigQuery ML 或 `sql/ml/strategy1/01-12` SQL runner 作为默认、fallback 或新增开发路线。
2. 既有 BQML / SQL runner 运行结果、PRD、README 和 SQL 文件保留为历史 reference / audit，用于解释历史结论和必要的一次性对照；不得继续扩展为生产默认链路。
3. 后续策略执行层目标路径为 Cloud Run Python runner；模型训练优先走 Python 生态（当前 sklearn，后续可按 PRD 引入 LightGBM / XGBoost / CatBoost 等），回测执行走 Python `ledger_exec_v1` 及其后续版本。
4. BigQuery SQL 仍保留并继续用于 ODS→DIM/DWD/DWS/ADS 数据仓库转换、metadata、单位契约、QA、状态表和只读分析；本决策中的“停止使用 SQL runner”特指停止把 `sql/ml/strategy1` 作为策略模型训练 / 预测 / 回测 runner。
5. `docs/prd/PRD_20260604_02_策略1月度滚动重训.md` 在实现前必须改造为 Cloud Run Python / backend-neutral 口径，不得按原 BQML 月度重训路径直接实现。
6. 后续若为了回归审计短暂运行历史 BQML / SQL runner，必须在任务说明和结果中标记为历史对照，不得把结果登记为新的默认 baseline 或生产路径。

### 理由

该决策避免继续投入高成本、低弹性的 BQML / SQL runner 路线，把后续工程集中到可控的 Python 执行环境、Cloud Run 并发调度、模型库扩展和可复用 ledger 上。同时保留 BigQuery 数据仓库与 QA 的职责边界，避免把“停止策略 SQL runner”误解为停止使用 BigQuery SQL 做数仓。

### 影响

OQ-010 的下一步不再是确认是否采纳 BQML baseline 作为默认参数，而是先找到可接受的 Cloud Run Python 模型 / backend baseline，并把月度滚动重训 PRD 改成 Cloud Run Python 口径。`pv_fin_quality + 30/5% + biweekly + 5d` 及其 BQML run/backtest 仍是历史最佳实验结果和对照基准，但不是未来默认执行链路。记忆、TODO 和后续 PRD / 实现提示词必须以该决策为准。

### 备选方案

继续把 BQML baseline 作为 fallback；放弃，因为 owner 已明确后续不用 BQML。继续扩展 `sql/ml/strategy1` 月度重训；放弃，因为会继续扩大已决定废弃的 runner 面。完全移除 BigQuery SQL；放弃，因为 BigQuery SQL 仍是数仓转换、QA 和状态契约的核心。

### 相关文件

`.agent/memory/PROJECT_CONTEXT.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/AGENT_HANDOFF.md`, `TODO.md`, `docs/prd/PRD_20260604_02_策略1月度滚动重训.md`, `docs/prd/PRD_20260604_04_策略1CloudRun训练回测.md`, `docs/prd/PRD_20260605_02_策略1CloudRun轻量Task并发.md`, `docs/prd/PRD_20260605_03_策略1Sklearn模型实验.md`, `sql/ml/strategy1/README.md`

## DECISION-20260606-01: OQ-005 先拆分 Composer DAG 边界再继续扩展生产调度

日期: 2026-06-06
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5 Codex

### 背景

OQ-005 当前主 DAG `ashare_daily_pipeline_v0` 已承载生产采集、ODS readiness、DWD/DWS 窗口刷新、全量兼容路径、`qa_only`、ADS 契约初始化、非交易日 gate、状态回写和告警衔接。后续还需要接入 Dataform definitions、补跑 / resume 自动化和策略 runner / report 可选分支。继续在单 DAG 内追加分支会使参数、状态、失败恢复和 smoke 验收边界持续变复杂。

### 决策

1. OQ-005 后续先拆分 Composer DAG 边界，再继续扩展 Dataform / resume / research 调度。
2. 目标 DAG 为 `ashare_ods_ingestion_daily`、`ashare_warehouse_window_refresh`、`ashare_warehouse_full_rebuild`、`ashare_research_model_experiment`、`ashare_research_model_fanout`；`ashare_pipeline_alert_checker` 继续独立。
3. `ashare_ods_ingestion_daily` 只负责每日生产采集、非交易日 gate 和 ODS readiness。
4. `ashare_warehouse_window_refresh` 只负责 `daily_current` / `backfill` 的 DIM/DWD/DWS 窗口刷新、metadata 和 QA。
5. `ashare_warehouse_full_rebuild` 作为手工维护 DAG，默认无 schedule，并要求显式确认。
6. 研究实验 DAG 与生产数仓 DAG 分离，研究任务不得写生产 DIM/DWD/DWS。
7. `ashare_meta.pipeline_run` 和 `ashare_meta.pipeline_task_status` 继续作为统一观测事实表；跨 DAG 血缘后续可补结构化字段。
8. 跨 DAG ingestion -> warehouse refresh 的 `upstream_pipeline_run_id` 血缘和 refresh-missing watchdog 属于 P0，不得推迟到后续观测阶段。

### 理由

拆分后，每个 DAG 的 schedule、参数、失败恢复、告警和 smoke 验收都对应单一职责。生产采集、数仓刷新、全量维护和研究实验的运行风险被隔离，Dataform 接入和补跑 / resume 自动化也可以在更清晰的边界内推进。

### 影响

新增设计文档 `docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`。OQ-005 TODO 下一步调整为先抽共享 Composer helper，并实现 `ashare_ods_ingestion_daily` 与 `ashare_warehouse_window_refresh`；P0 同时补 `upstream_pipeline_run_id` 和 refresh-missing watchdog。完成开市日、非交易日和 backfill smoke 后，再继续 Dataform definitions、补跑 / resume 自动化和完整 ODS→ADS 运维观测闭环。旧 `ashare_daily_pipeline_v0` 在新生产 DAG 连续验收后暂停。

### 备选方案

继续在 `ashare_daily_pipeline_v0` 内追加 Dataform、resume 和研究分支；该路径会扩大单 DAG 参数矩阵和状态分支。直接先做 Dataform definitions；该路径会把现有单 DAG 耦合带入新执行后端。把研究实验 DAG 与生产 DAG 合并；该路径会让手工实验失败和每日生产状态混在同一调度面。

### 相关文件

`docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md`, `docs/prd/PRD_20260605_01_OQ005剩余调度链路.md`, `orchestration/composer/dags/ashare_daily_pipeline_v0.py`, `orchestration/composer/README.md`, `.agent/memory/ARCHITECTURE_MEMORY.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`, `TODO.md`

## DECISION-20260606-02: 策略 1 组合验收门先固定 10/20/30/40 持股数候选

日期: 2026-06-06
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5 Codex

### 背景

策略 1 已完成 BQML historical reference、Cloud Run sklearn native、LightGBM binary、LightGBM regression、尾部风险 P1/P2 和风险特征 Phase B0 诊断。当前证据显示：RankIC 可以为正，但 current top-30 long-only 组合在 `2024-01-02` 至 `2026-04-30` full-period 和 2026 final holdout 上不能通过生产 baseline 验收。继续直接扩大模型 / 风险特征搜索前，需要先冻结组合验收门和小资金可行性诊断。

### 决策

1. 策略 1 下一版组合验收门的持股数候选固定为 `target_holdings in [10, 20, 30, 40]`。
2. 不纳入 `target_holdings=50`，也不纳入 100 / 150 等更高持股数方案。
3. 首轮单票权重上限仍为 5%。
4. `10/5%` 因理论最多部署约 50% 资金，只作为低仓位 / 高现金 / 集中选股对照，不直接与满仓方案比较收益，不参与 production baseline accepted 判定，也不适用满仓候选的现金占比 hard gate。
5. `20/5%` 是 5% 上限下的理论满仓边界；`30/5%` 是当前 historical reference；`40/5%` 用于验证更分散组合能否降低尾部风险。
6. 所有候选必须进入 10 万 CNY、100 股整数手、实际持股数、现金占比、买入跳单率和低价股偏移诊断。
7. 当前 extended reference run 在验收门 v2 下应判为 `rejected`，但该拒绝只针对当前 top-30 long-only 组合实现，不否定底层信号家族。

### 理由

50 只以上组合在 10 万资金下更容易被 100 股整数手和最低买入额扭曲，可能导致大量现金碎片、跳单或低价股偏移，且会把问题从“模型是否有信号”混成“资金规模是否足够”。先固定 10/20/30/40 可以覆盖集中、理论满仓、当前 reference 和更分散四个可解释点，同时保持首轮实验规模可控。

### 影响

新增 PRD `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`。后续 OQ-010 风险特征入模、组合参数实验、月度滚动重训和 baseline acceptance 必须引用该持股数候选集合；新增 QA 应拒绝 `target_holdings=50`、100、150 等未批准组合。PRD03 风险特征入模的后续实现顺序应调整到验收门 v2 和组合可行性诊断之后。accepted 候选必须跑赢 `eligible_executable_benchmark`；test/final_holdout 复用状态、score orientation audit、low-price tilt 和 exposure-adjusted 收益视图需要进入实现 artifact。

### 备选方案

继续使用 30 只固定组合；放弃，因为无法判断当前失败来自模型、组合集中度、资金手数约束还是基准暴露。加入 50 只；放弃，因为 owner 明确要求不要 50，且 10 万资金下 50 只会明显放大整数手失真。直接尝试 100 / 150 只；放弃，因为与小资金实盘目标不匹配。

### 相关文件

`docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`, `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`, `TODO.md`

## DECISION-20260606-03: 策略 1 验收门 v2 使用版本化共享契约

日期: 2026-06-06
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5 Codex

### 背景

策略 1 已有 `model_acceptance_contract_v1.yml`，但历史实现中 Python acceptance、BigQuery QA 和 PRD 阈值曾出现过漂移风险。验收门 v2 又新增 eligible benchmark、低价股偏移、exposure-adjusted 收益、score orientation audit、split 复用状态和 10/20/30/40 组合可行性门。如果不把阈值和指标口径沉到同一个版本化契约，后续实现很容易再次把 accepted / rejected 判定散落到 Python、SQL 和报告 artifact 中。

### 决策

1. 策略 1 验收门 v2 必须新增 `configs/strategy1/model_acceptance_contract_v2.yml`。
2. `model_acceptance_contract_v2.yml` 是 v2 阈值、边界开闭口径和指标定义的唯一事实来源。
3. 后续 `acceptance_gate_v2` 诊断、Python acceptance 模块、`22_qa_acceptance_gate_v2_outputs.sql` 和复用于 v2 新候选的 `18/19` QA 必须读取 / 注入同一契约，并在 artifact 中写 `acceptance_contract_version` 和 `acceptance_contract_sha256`。
4. `model_acceptance_contract_v1.yml` 继续保留为已完成 sklearn native、LightGBM binary 和 LightGBM regression wave 的历史审计契约，不追溯改写旧结论。
5. 同一 search / diagnosis / QA run 内不得混用 v1 与 v2；若报告对比历史 v1 结果，必须标注为 historical reference。

### 理由

验收门 v2 将作为后续 OQ-010 模型族搜索、风险特征训练、组合可行性诊断和月度滚动重训的共同判定口径。用版本化契约统一 Python / SQL / QA / artifact，可以避免阈值漂移、边界不一致和报告解释不一致。

### 影响

PR #97 的 PRD 已将共享契约写入 §6.5、QA 要求和实施顺序。后续实现必须先落 `model_acceptance_contract_v2.yml`，再实现只读 `acceptance_gate_v2` 诊断、组合可行性模拟和 `22` QA。PRD03 风险特征后续训练如果继续，也必须引用 v2 契约。

### 备选方案

继续把阈值写在 PRD、Python 和 SQL 各自实现中；放弃，因为会重复 PRD04 之前的阈值漂移问题。直接覆盖 v1；放弃，因为已完成 wave 的历史 artifact 需要保留原审计口径。

### 相关文件

`docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`, `configs/strategy1/model_acceptance_contract_v1.yml`, `sql/ml/strategy1/18_qa_sklearn_native_search_outputs.sql`, `sql/ml/strategy1/19_qa_cloudrun_python_baseline_search_outputs.sql`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`, `TODO.md`

## DECISION-20260606-04: 策略 1 production acceptance 必须先切到整数手 ledger

日期: 2026-06-06
状态: active
负责人: owner
Agent ID: Codex
模型: GPT-5 Codex

### 背景

策略 1 验收门 v2 已合并并完成 reference 诊断。v2 把 10 万 CNY、100 股整数手、实际持股数、现金占比、买入跳单率和低价股偏移纳入 production acceptance 前置诊断。但后续只读复核发现，当前 extended reference backtest `bt_s1_bqml_baseline_pvfq_n30_bw_h5_extended_20260604_01` 的 1291 笔 `FILLED` 成交全部是 FLOAT shares，约 98.2% 四舍五入后也不是 100 股整数倍。该收益口径不能代表小资金实盘可执行结果。

### 决策

1. 策略 1 后续 v2 accepted production baseline 必须使用 lot-aware ledger，不得使用 FLOAT-shares backtest 判定 accepted。
2. Cloud Run Python ledger 的下一版目标版本为 `ledger_exec_v1_lot100`。
3. 买入必须按 100 股整数手向下取整，最小买入 1 手。
4. 清仓卖出允许 odd-lot 全部退出；部分卖出非清仓必须向下取整到 100 股，余股保留。
5. P0 不做余现金二次分配；因 lot rounding、不可买或现金缩放留下的现金进入 NAV。
6. 旧 BQML / SQL runner / FLOAT-shares 回测只保留为 historical reference / audit，报告和 artifact 必须显式标记，不得登记为新 production baseline。
7. 进入下一轮风险特征训练前，必须先实现 lot-aware ledger、补 lot-aware QA、复用当前 prediction stream 跑 `2024-01-02` 至 `2026-04-30` fixed-prediction reference，并重跑 acceptance gate v2。

### 理由

继续用 FLOAT-shares 回测会把交易执行语义误差和模型 / 特征效果混在一起。先修 ledger 能确保后续收益、现金、实际持股数和跳单率都在同一 production 口径下比较，也能解释 `20/30/40` 在静态 feasibility 中出现的局部现金峰值到底来自不可买、手数约束还是组合参数本身。

### 影响

新增 PRD `docs/prd/PRD_20260606_05_策略1整数手交易执行.md`。OQ-010 下一步从“直接继续风险特征入模训练”调整为“先实现 Cloud Run Python lot-aware ledger 并重跑 fixed-prediction reference”。`docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md` 的实现顺序需要排在 lot-aware reference 和 v2 gate 复跑之后。

### 备选方案

继续用 FLOAT-shares extended reference 作为 accepted 判定；放弃，因为与 A 股小资金 100 股买入约束不一致。只用静态 feasibility 代替真实 lot-aware 回测；放弃，因为静态诊断没有继承旧仓、pending sell、netting 和真实现金路径。立即改模型或风险特征；放弃作为当前顺序，因为会把执行语义变化和模型质量变化混在一起。

### 相关文件

`docs/prd/PRD_20260606_05_策略1整数手交易执行.md`, `docs/prd/PRD_20260606_04_策略1验收门v2与组合可行性诊断.md`, `docs/prd/PRD_20260606_03_策略1风险特征入模与候选增强.md`, `scripts/strategy1_cloudrun/ledger.py`, `sql/ml/strategy1/22_qa_acceptance_gate_v2_outputs.sql`, `TODO.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/AGENT_HANDOFF.md`

## DECISION-20260607-01: dws_market_state_daily 采用备份表 + 双版本行承接上证指数补充

Date: 2026-06-07
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5 Codex
Context: 上证指数 `000001.SH` 已补入 ODS/DIM/DWD 后，owner 要求继续补 DWS，并要求先创建 `ashare_backup` 数据集保存现有 `dws_market_state_daily`。
Decision: 在 `data-aquarium.ashare_backup.dws_market_state_daily_v0` 保存修改前生产快照；生产 `ashare_dws.dws_market_state_daily` 改为同时输出 `market_state_v0_20260606` 兼容行和新增 `market_state_v1_20260607` 行。v0 行的 `sse_composite_*` 字段保持 `NULL`，v1 补上证指数 `000001.SH` / `SSE_COMPOSITE` 市场状态字段。本次不把上证指数纳入 risk-off 触发逻辑，也不写 ADS。日更 / backfill 不调用全量 `CREATE OR REPLACE`，改用 `sql/incremental/03_refresh_market_state_window.sql` 窗口 MERGE；全量 `sql/dws/08_dws_market_state_daily.sql` 只作为初始化 / full rebuild 路径。
Rationale: 备份表保留修改前 schema/数据用于审计和复现；双版本行让既有 runner/config 继续查 v0，同时给后续训练或特征集提供显式 v1 切换点，且 v0/v1 字段值有真实差异。窗口 MERGE 避免每日调度扫 2019+ 全历史，并避免 historical backfill 忽略 date_from/date_to 把 market-state 刷到当前日期。
Impact: 后续如要使用上证指数字段训练，应显式指定 `market_state_v1_20260607` 或新增 feature set；如要改变 `is_risk_off` / `risk_off_trigger_count` 规则，应另写规则版本和验收，不直接改 v0。新增指数 endpoint 时必须从 `configs/ingestion/ods_current_scope_v0.yml` 生成 `sql/ods/01_index_external_table_uris.sql`，不要手改 URI 列表。
Related files: sql/dws/08_dws_market_state_daily.sql, sql/incremental/03_refresh_market_state_window.sql, sql/qa/11_market_state_checks.sql, scripts/ingestion/generate_index_external_table_uris.py, docs/数据仓库建模方案-DWS-ADS.md, orchestration/composer/dags/ashare_common.py

## DECISION-20260608-01: index benchmark QA 默认终点对齐 DWD 已可用日期

Date: 2026-06-08
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5 Codex
Context: PR #106 合并后的 Composer backfill smoke 使用 2026-06-05 窗口，但后置 `03_index_benchmark_checks.sql` 默认 `dwd_end_date = CURRENT_DATE('Asia/Shanghai')`，在 2026-06-08 当天 000001.SH ODS/DWD 未到数时误判全史覆盖失败。
Decision: `sql/qa/03_index_benchmark_checks.sql` 的默认 `dwd_end_date` 不再取 `CURRENT_DATE`，改为 `dwd_index_eod` 中 `000001.SH` 已有完整 price + dailybasic 的最新 SSE 开市日，并保留非空 / 不早于起始日断言。
Rationale: 该 QA 的目标是验证已落库指数 DWD 的 canonical 映射和历史覆盖质量，不应因当天数据尚未采集/刷新而让 backfill 或日内 smoke 失败。覆盖终点对齐已可用 DWD 数据日仍能发现历史缺口、重复和 valuation 字段缺失。
Impact: 调度默认 QA 不再要求覆盖到自然今天；如需验证某个最新业务日，必须先补齐 ODS/DWD，或显式执行带目标日期语义的窗口 QA。
Related files: sql/qa/03_index_benchmark_checks.sql, dataform/definitions/assertions/03_index_benchmark_checks.sqlx

## DECISION-20260608-02: OQ-005 长期编排层迁出 Cloud Composer

Date: 2026-06-08
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5 Codex

### Context

`data-aquarium.gcp_billing` 在 `2026-06-05`、`2026-06-06`、`2026-06-07` 的账单显示，Cloud Composer 费用主体稳定集中在 `Cloud Composer 3 standard milli DCU-hours (asia-east2)`，约 `160.97 USD/天`。当前项目中的 Composer 主要承担调度、分支控制、ODS readiness、window refresh 串接和 alert checker，不承担核心业务计算；核心计算仍在 `Cloud Run Jobs` 与 `BigQuery SQL / Dataform`。继续保留 Composer 作为长期编排层与实际复杂度和成本目标不匹配。

### Decision

1. OQ-005 的长期目标不再是“长期保留 Cloud Composer 编排”。
2. 长期编排层改为 `Cloud Scheduler + Cloud Workflows + Cloud Run Jobs + BigQuery SQL/Dataform`。
3. 多步业务编排统一使用 `Cloud Workflows`；单步 `ashare_pipeline_alert_checker` 迁到 `Cloud Scheduler + Cloud Run`。
4. 当前 Composer DAG 拆分、window refresh、alert checker 和相关 smoke 只视为 cutover 前过渡态，不再代表长期目标架构。
5. cutover 验收完成后应删除 Composer 环境，以消除固定 `standard milli DCU-hours` 底座成本。
6. 本次架构迁移不顺手改 BigQuery SQL、metadata、QA、ODS current-scope 或策略业务口径。

### Rationale

减少 Composer 中的 DAG 次数不能显著降低固定底座费；只有把调度完全迁出并删除 Composer 环境，才能真正消除这笔常驻成本。`Cloud Workflows` 能提供当前需要的状态机、重试、分支和补跑能力，同时没有常驻环境费用，比继续保留 Composer 或自建 `Cloud Run orchestrator` 更符合当前 OQ-005 的复杂度与成本目标。

### Impact

- `docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md` 成为 OQ-005 长期编排层的主 PRD。
- 此前 `docs/prd/PRD_20260603_03_GCP数据流水线方案.md`、`docs/prd/PRD_20260606_02_OQ005ComposerDAG拆分.md` 中关于“长期保留 Composer”的表述被本决策覆盖，但这些文档中的 ODS current-scope、window refresh、000001.SH、market-state、metadata 与 QA 业务事实仍然有效。
- 后续实现优先级应调整为：先迁 Workflows/Scheduler 并完成 cutover，再删除 Composer；不是继续在 Composer 上叠加新生产职责。

### Alternatives considered

- 继续保留 Composer，只减少 DAG 次数：放弃，因为固定 `standard milli DCU-hours` 费用仍在。
- 自建 `Cloud Run orchestrator`：放弃作为默认方案，因为当前编排复杂度不足以证明要自行维护状态机和重试系统。
- 直接把所有逻辑改成 BigQuery Scheduled Queries：放弃，因为当前 OQ-005 需要非交易日 gate、Cloud Run ingestion、窗口模式和多步状态写回，单靠定时查询不足以承载。

### Related files

`docs/prd/PRD_20260608_01_OQ005调度完全迁出Composer.md`, `.agent/memory/PROJECT_CONTEXT.md`, `.agent/memory/ARCHITECTURE_MEMORY.md`, `.agent/memory/IMPLEMENTATION_STATUS.md`, `.agent/memory/OPEN_QUESTIONS.md`, `.agent/memory/AGENT_HANDOFF.md`, `TODO.md`

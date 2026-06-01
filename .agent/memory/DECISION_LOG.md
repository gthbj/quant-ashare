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
Status: active
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

当时影响：修复后按 `sql/README.md` 执行脚本，并运行 `sql/qa/01_p0_smoke_checks.sql`。后续 P0 DIM/DWD 已物化并通过 QA。

### 备选方案

仅修 R1/R2、把 R3-R5 留到 QA 后；放弃，因为 owner 已要求修复，且这些补丁范围小、不会绑定调度选型。

### 相关文件

`sql/README.md`, `sql/dim/02_dim_stock.sql`, `sql/dwd/01_dwd_stock_eod_price.sql`, `sql/dwd/03_dwd_fin_indicator.sql`, `sql/dwd/05_dwd_fin_indicator_latest.sql`, `sql/qa/01_p0_smoke_checks.sql`

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

`sql/dwd/04_dwd_index_eod.sql`, `sql/qa/01_p0_smoke_checks.sql`, `.agent/memory/OPEN_QUESTIONS.md`

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

`sql/dwd/01_dwd_stock_eod_price.sql`, `sql/dwd/05_dwd_fin_indicator_latest.sql`, `sql/qa/01_p0_smoke_checks.sql`, `docs/reviews/P0-建表SQL-fix-review.md`

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

新增 `sql/metadata/01_p0_table_column_descriptions.sql`，集中维护 3 张 DIM + 5 张 DWD 的表级和字段级中文说明。P0 表每次 `CREATE OR REPLACE TABLE` 重建后，都应重新执行该 metadata 脚本。

### 理由

集中 metadata 脚本能原地更新说明，不重写数据；也避免在每个 CTAS 脚本里维护大量重复 ALTER 片段。后续若采用 dbt，可迁移到 `persist_docs`，但当前纯 SQL bootstrap 先用显式 ALTER 保证 BigQuery 元数据完整。

### 影响

已在 BigQuery 执行 metadata 脚本。8 张 P0 DIM/DWD 表的 table description 和所有 schema field description 均已补齐，验证 missing description = 0。`sql/README.md` 已把 metadata 脚本加入执行顺序。

### 备选方案

逐个重建脚本内补齐全部 ALTER；放弃作为唯一方案，因为每次只需补 metadata 时不应重写全量数据。等待后续 dbt `persist_docs`；暂缓，因为 OQ-005 尚未决定调度/物化工具。

### 相关文件

`sql/metadata/01_p0_table_column_descriptions.sql`, `sql/README.md`

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

`sql/dwd/04_dwd_index_eod.sql`、metadata、QA 和相关文档已按此口径更新。2026-06-01 已重建 BigQuery 实表，并重新执行 `sql/metadata/01_p0_table_column_descriptions.sql` 和 `sql/qa/01_p0_smoke_checks.sql` 通过。

### 备选方案

保留当前 `sec_code=ODS 实际代码` 并要求 DWS/ADS 使用 `canonical_index_code` join；放弃，因为这会让指数表成为 `sec_code` 统一主键规范的例外，增加下游实现负担。

### 相关文件

`sql/dwd/04_dwd_index_eod.sql`, `sql/metadata/01_p0_table_column_descriptions.sql`, `sql/qa/01_p0_smoke_checks.sql`, `docs/数据仓库建模方案-DWD-DIM.md`, `docs/数据仓库建模方案-DWS-ADS.md`, `docs/A股中低频小资金机器学习策略方案.md`

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

## DECISION-20260601-03: 策略 1 回测 v0 采用「有守卫的简化版」，QA 失败即触发升级到账户级 ledger

日期: 2026-06-01
状态: active
负责人: owner
Agent ID: Claude
模型: Claude Opus 4.8

### 背景

策略 1 runner 回测脚本 `sql/ml/strategy1/08_run_backtest.sql` 经多轮评审（PR #7）。set-based 持仓 episode 模型在「延迟/封死卖出尚未平仓时、同股又重新进入选股池」这一低频场景下，会对同股重叠建仓（双倍暴露/预算占用）。根治需要按现金约束、对实际持仓 netting 的有状态 ledger 循环，但这偏离已批准 PRD（`PRD_20260601_02`）刻意选择的 set-based + next-sellable 设计。

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

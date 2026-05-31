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

### Context

早先误解 owner 对“2019 之前数据”的意图，记录为 DWD/DIM 初始写入 ODS 可用全历史。owner 随后澄清：2019 之前的数据是下一步，当前阶段先把 2019+ 数据做正确。

### Decision

本决策废弃，不作为执行依据。执行依据改为 DECISION-20260531-11。

### Rationale

2019 年前正式样本/明细建设属于后续阶段；当前 P0 需要的是 2019+ 数据正确性，以及为 2019 PIT/滚动特征读取必要的 2019 前支撑数据。

### Impact

记忆和 `TODO.md` 已修正为三类范围口径；早先“全历史写入 review”已改为修正说明。

### Alternatives Considered

无。

### Related Files

`docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md`, `TODO.md`, `.agent/memory/KNOWN_CONSTRAINTS.md`, `.agent/memory/OPEN_QUESTIONS.md`

## DECISION-20260531-11: 当前阶段先做好 2019+ 数据，2019 前仅作必要支撑

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### Context

owner 澄清：2019 年以前的数据是下一步；当前阶段先把 2019+ 数据做正确。但为保证 2019 初 PIT 与滚动特征，方案仍需要在三种性质不同的情况下触碰 2019 前数据。

### Decision

当前 P0 最终 DWD/DWS 样本以 `2019-01-01` 为起点。2019 年前数据只按三类处理：
1. 财务/事件类按报告期/事件分区前移到 `20170101`，用于 2019 PIT、公告滞后、同比/基期。
2. 行情/估值/资金类最终写 2019+，构建时按最大滚动窗口读取 2018 lookback buffer；buffer 行不落最终 DWD/DWS。
3. 维度/日历取最新快照或全量历史事件，例如 `trade_cal`、`stock_basic`、`namechange`，用于 2019 join 和 SCD2 还原。

### Rationale

这样既能保证 2019 样本的 PIT、滚动特征和 universe 正确，又避免把后续“2019 年以前正式样本/明细建设”提前混入 P0。

### Impact

主方案 §4.6 已新增“为支持 2019+ 所需的 2019 年前数据范围”表。P0 SQL 需要参数化 `@dwd_start_date = DATE '2019-01-01'`、`@fin_start_period = '20170101'`、`@lookback_start_date`。OQ-002 关闭为采纳；OQ-008 关闭为不适用。

### Alternatives Considered

把 DWD/DIM 初始写入改为 ODS 可用全历史；该方案被废弃，因为 owner 明确当前阶段先做好 2019+。

### Related Files

`docs/数据仓库建模方案-DWD-DIM.md` §4.6, `docs/reviews/数据仓库建模方案-DWD-DIM-review-2019前数据范围修正.md`, `TODO.md`

## DECISION-20260531-12: P0 建表 SQL 先以根目录 sql/ bootstrap 脚本落地

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Codex
Model: GPT-5

### Context

owner 要求在项目根目录新增目录，放置创建 DWD/DIM 表的代码。当前尚未决定最终调度/物化工具（OQ-005：dbt vs 纯 bq SQL）。

### Decision

先在根目录 `sql/` 落地 P0 BigQuery Standard SQL bootstrap 脚本：`00_create_datasets.sql`、`sql/dim/*.sql`、`sql/dwd/*.sql`。脚本使用 `CREATE OR REPLACE TABLE`、CTAS、后置字段描述、范围参数，并按当前 2019+ 口径处理 lookback 和财务 2017 前移。

### Rationale

该方式能立即执行和验证 P0 表结构，不绑定最终调度工具；后续可直接迁移到 dbt model 或由 Airflow/bq 调用。

### Impact

`TODO.md` 将 P0 建表 SQL 标为已完成，新增“执行物化并 QA”和“lookback_start_date 配置化”待办。OQ-005 仍保持开放。

### Alternatives Considered

直接引入 dbt 项目结构；暂缓，因为 owner 当前诉求是先把建表 SQL 写出来。

### Related Files

`sql/README.md`, `sql/00_create_datasets.sql`, `sql/dim/*.sql`, `sql/dwd/*.sql`, `TODO.md`

## DECISION-20260531-13: 评审须产出 docs/reviews/ 评审文档；评审本身只读

Date: 2026-05-31
Status: active
Owner: owner
Agent ID: Agent_RD（数仓建模 / 评审）
Model: Claude Opus 4.8

### Context

本会话评审已提交的 P0 建表 SQL（commit 9942f14）。owner 指出：评审是只读分析，发现是否进项目记忆由 owner 决定；并要求把「评审须写评审文档」固化为协议。此前评审建模文档已有 `docs/reviews/` 先例，但协议未明文规定。

### Decision

对**已提交代码 / SQL** 或**设计 / 方案文档**的评审，必须产出 `docs/reviews/<对象>-review[-<专题>].md`，含分级发现 / 依据 / 影响 / 建议 / 与决策冲突核对 / 结论，带模型署名。评审过程**只读**：不擅改被评审对象、不把发现直接写进 `.agent/memory/**` 或 `TODO.md`；发现转为 OQ / TODO / 决策由 owner 决定。是否提交评审文档由 owner 决定，提交时与相关记忆同一次提交。

### Rationale

评审结论是可追溯产物，应落文档而非仅在对话；评审与「执行整改」职责分离，避免评审者把未经 owner 采纳的发现擅自写入项目状态。

### Impact

AGENTS.md 新增「六、评审协议」。首份代码评审文档：`docs/reviews/P0-建表SQL-review.md`。

### Alternatives Considered

只把评审结论留在对话/交接里——放弃，不可独立追溯。

### Related Files

`AGENTS.md` §六, `docs/reviews/P0-建表SQL-review.md`

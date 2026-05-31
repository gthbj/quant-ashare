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
Decision: 统一造字段 `ann_date_eff = COALESCE(f_ann_date, ann_date)` 作为 PIT 连接键。
Rationale: 实际公告日优先；as-of join 用 `ann_date_eff <= trade_date`。
Impact: 所有财务/事件 DWD 必须产出 `ann_date_eff`。
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
Decision: 行情 DWD 设 `require_partition_filter=TRUE`（财务表不开）。初始回填：行情 `>=20190101`，**财务前移 `>=20170101`**，维度/日历不按时间截断。
Rationale: 聚簇无法强制过滤，只有分区能；财务前移以保证 2019 初 PIT 能取到最近年报/季报。
Impact: 查行情表的 SQL 必须带 `trade_date` 过滤。财务前移待 owner 最终确认（见 OQ-002）。
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

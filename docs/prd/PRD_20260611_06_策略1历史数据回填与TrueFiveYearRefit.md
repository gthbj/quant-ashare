> 文档维护：Claude Fable 5（最近更新 2026-06-11）

# PRD：策略 1 历史数据回填（2010+）与 True-Five-Year Refit 重跑

> 状态：草案，待 owner review。
> 范围声明：数据层历史回填 + 旗标修复 + 2021-2024 refit 重跑 + 新 synthetic continuous；全部研究口径，不动现有 official 结果，不 promotion。
> 关联：OQ-011、`DECISION-20260611-02`、`PRD_20260611_02`（final refit 契约）、`PRD_20260611_03`（synthetic continuous）、KNOWN_CONSTRAINTS「2019 前数据范围」「annual rolling source-panel 覆盖约束」。

---

## 1. 背景与现状（2026-06-11 只读探查）

三层覆盖现状：

| 层 | 现状 |
|---|---|
| ODS | `daily` / `daily_basic` 已有 **2010 起**逐年完整行（2010-2014 各年 43-57 万行）；owner 确认 14 个 ODS endpoint 现已从 2010 起可用（旧口径是"2015 起可靠"） |
| DWD 价格 | **2015 起**有行（2015：675,447；2018：899,566），2015 之前没有（R14 时代 backfill 只补了 2015-2018） |
| DWS 价格特征 | 2015 起有行，但 **`2015-Q1` 全部 150,726 行 `has_full_history_60d=FALSE`**（backfill 时 DWD 无 2014 lookback buffer）；**`2019-Q1` 全部 208,007 行也是 FALSE**——陈旧标记：旗标在 2019-01-01 起首次物化时计算，2015-2018 backfill 完成后没有回刷；陈旧区间实测为 `2019-01-02..2019-04-02`，越过自然 Q1 两个开市日 |
| DWS 估值/财务 | 行骨架 2015 起都有（估值 2015：570,310；财务与价格行数一致），**字段级非空率未盘点** |

后果链：configs `train_start=2019-04-03` → annual rolling 选参 panel 与 refit panel 都从 2019-04-03 起 →
final refit 被迫 `effective_refit_train_start=max(nominal, 2019-04-03)` → **2021-2024 四年 refit 的名义
五年窗口被截断**（2021 最严重：名义起点 2016 年初，实际只有约 1.75 年）→ DECISION-20260611-02 只能
接受 effective-window 研究口径。

关键事实：**2019 年初旗标修复不需要任何新数据**（DWD 已有 2018 行，重刷窗口即可）。注意修复窗口是
**`2019-01-02 ~ 2019-04-02`**（实证缺口含 `2019-04-01/02` 两个开市日，**不止自然 Q1**；首个完整日
是 `2019-04-03`）。2015 年初修复只需 2014 lookback（ODS 已有）；而 ODS 2010 起可用使整个历史下限
可以一次性前移，永久消除边界缺口问题。

## 2. 目标

1. **Phase A 数据层**：DWD/DWS 历史下限前移（推荐 2010），所有边界 `has_full_history_60d` 旗标按真实
   lookback 重算，`2019-01-02 ~ 2019-04-02` 陈旧旗标修复；估值/财务字段逐年完备度报告。
2. **Phase B refit 重跑**：2021-2024 四年按**真实名义五年窗口**重建 dedicated refit panel 并重跑
   refit/register/predict（`effective == nominal`，不再 clamp）。2025/2026 名义窗口未被截断，不重跑。
3. **Phase C 新 continuous**：新 synthetic merge（2021-2024 新 refit + 2025/2026 既有 refit）+ 新
   official-候选 continuous 回测 + 与当前 effective-window 结果的对比表，供 owner 决策口径取舍。

## 3. 非目标

- **不重做选参**：selected candidate lineage 不变，refit 只按 PRD_20260611_02 契约重训选定候选。
  更长窗口下的重新选参是独立实验，如需另立 PRD。
- 不改 `daily_current` 生产写入下限（仍 2019+）；历史行只能经显式 `warehouse_mode=backfill` 写入。
- 不修改/删除现有 official continuous 结果与 DECISION-20260611-02；新旧口径取舍由 owner 决策。
- 不 promotion、不写 ADS、不改默认 profile；与 `PRD_20260611_05` overlay A/B 互不阻塞（见 §4.5）。

## 4. 设计

### 4.1 前置盘点：历史可用性矩阵与下限规则

- 对 strong endpoint（`daily`、`daily_basic`、`adj_factor`、`stk_limit`、`index_daily`）及财务 / 指数
  成分 / 停复牌等依赖 endpoint，产出 **2010-2018 逐年行数与覆盖率矩阵**（只读查询）。
- 历史下限决策规则（执行 agent 按规则自主定，记录到执行记录，不逐项找 owner）：推荐
  `DWD/DWS 历史下限 = 2010-01-01`（窗口完备自 ~2010-04 起）；若某 strong endpoint 在某年系统性缺失
  （覆盖率显著低于相邻年），下限提升到最早完整年并记录证据。弱依赖（如 `stk_limit` 早年缺失）不抬高
  下限，对应派生字段允许 NULL 并写入完备度报告。

### 4.2 Phase A：历史 backfill 与旗标修复

1. **2010-2014 历史 backfill**：沿用既有显式 `warehouse_mode=backfill` 通道
   （`ashare_warehouse_window_refresh` 手工触发），按年分批，每批跑窗口 QA
   （`sql/qa/10_windowed_stock_refresh_checks.sql`）。`dim_stock` 历史生命周期兜底规则
   （`derived_from_daily`、`list_date` 晚于首个日线交易日时用后者兜底）已在 PR #130/#132 落地，直接复用。
2. **2015Q1 旗标修复**：2014 DWD 行就位后重刷 2015 年初窗口，`has_full_history_60d` 按真实 60 日
   lookback 重算。
3. **2019 年初陈旧旗标修复**：重刷 **`2019-01-02 ~ 2019-04-02`** 窗口（lookback 读已有 2018 DWD 行），
   无需新数据。修复窗口**必须覆盖到 `2019-04-02`**——实证缺口是 `2019-01-02..2019-04-02`，含
   `2019-04-01/02` 两个开市日，只刷自然 Q1 会留下两天缺口。该项可最先做、独立验证。
4. **Overlap parity QA（硬门）**：任何重刷**不得改变 `2019-04-03` 之后任何现有行的特征值**——用
   `scripts/qa/run_windowed_refresh_equivalence.py` 或专用 shadow 对比断言。这保护既有 selection /
   refit / official continuous 的可复现性；parity 失败必须停下修构建确定性，不得带病推进。
5. **字段完备度报告**：估值（`total_mv_cny`/`circ_mv_cny`）与财务特征字段（`roe` 等）在 universe 行上的
   逐年非空率（2010-2020）。Phase B 准入门：2021-2024 名义窗口内估值非空率与 2019+ 同量级；财务字段
   早年公告缺失允许 NULL（模型与 P1 guard 均有显式 NULL 语义），但必须在报告中量化。

### 4.3 Phase B：True-five-year refit 重跑（2021-2024）

- 每年新 refit run_id：`build_refit_training_panel`（nominal 窗口，
  `refit_train_start = actual_first_trading_day(year-5)`，不 clamp）→ `refit_register_predict`，
  全程遵守 PRD_20260611_02 契约：preprocessor 在 refit 窗口重新 fit、读写 run_id 分离
  （`source_panel_run_id` = refit run_id、`source_run_id` = selection run_id）、registry/prediction
  只写 `ashare_research`。
- 既有 2021-2024 refit run 不动；2025/2026 既有 refit 直接复用（其训练窗口起点晚于 2019-04-03，
  且 Phase A parity QA 保证其输入在重刷后值不变）。
- 每年跑 `qa_refit_register_predict_outputs`，并新增断言：`effective_refit_train_start ==
  nominal_refit_train_start`（不再允许 clamp）；覆盖检查含**窗口内部缺口**（吸取 `2019-01-02..
  2019-04-02` 缺口被端点检查漏掉的教训），按开市日逐日 left join 断言 panel 覆盖。

### 4.4 Phase C：新 synthetic continuous 与对比

- 按 PRD_20260611_03 模式：新 manifest（2021-2024 新 refit + 2025/2026 既有 refit）→ 新 synthetic
  registry row（`year_model_map` 全量重写）→ continuous 回测（`--skip-diagnosis --skip-tail-risk
  --skip-qa` + 外部 `qa_continuous_backtest_outputs` + `qa_lot_aware_ledger_outputs`）。
- 新 run/backtest id，现有 official run 不动。
- 产出对比表（true-five-year vs 当前 effective-window official）：CAGR / MaxDD / Calmar / contract
  Sharpe / IR / 回撤窗口 / v3 gates 通过情况 / 逐年收益。结论交 owner 做口径取舍决策（DECISION 候选）。

### 4.5 与 PRD_20260611_05（overlay A/B）的关系

互不阻塞：A/B 的 baseline 是当前 official continuous，本 PRD 不触碰它。若 owner 事后接受
true-five-year 为新基线，A/B 三 arm 在新基线上复核一遍即可（纯回测层复用，成本低）。

## 5. 验收标准

| 项 | 要求 |
|---|---|
| 盘点矩阵 | strong/弱 endpoint 2010-2018 逐年覆盖矩阵 + 下限决策记录 |
| 旗标正确性 | `2019-01-02~2019-04-02` 与 2015 年初同构窗口（及新下限边界外的所有年份）`has_full_history_60d` 按真实 lookback 重算；只有数据宇宙真实边界（新下限后约一季度）允许 FALSE 集中出现 |
| Parity 硬门 | `2019-04-03` 后现有行特征值零变化（shadow 对比通过） |
| 完备度报告 | 估值/财务逐年非空率落档；Phase B 准入门评估有结论 |
| Refit 重跑 | 2021-2024 四年 `effective == nominal`，refit QA + 内部缺口断言全过 |
| 新 continuous | merge/registry/QA 全过，对比表全字段，v3 gates 重新评估 |
| 口径纪律 | 现有 official 与 DECISION-20260611-02 不动；新结果仅研究口径，取舍由 owner 决策 |
| 记忆同步 | 完成后更新 KNOWN_CONSTRAINTS「2019 前数据范围」「source-panel 覆盖约束」两条（旧表述将失效）与 OQ-011 状态 |

## 6. 风险与控制

| 风险 | 控制 |
|---|---|
| 早年某 endpoint 系统性缺失（如 `stk_limit`） | §4.1 盘点矩阵 + 下限规则；弱依赖字段允许 NULL 不抬下限 |
| 2010-2014 `dim_stock` 生命周期缺口重现 | 复用 PR #130/#132 兜底规则；窗口 QA 按年把关 |
| 重刷意外改变 2019+ 既有行 | §4.2.4 parity 硬门，失败即停 |
| 早年财务 PIT 公告缺失使 fin 特征大面积 NULL | 完备度报告量化；NULL 语义已有，不静默填补 |
| backfill 成本/失败半途 | 按年分批、批次状态记录、失败批次可重跑（窗口幂等） |
| 新结果与旧结果差异被误读为"修复" | 对比表明示两口径差异来源（训练窗口变化），定性留给 owner |

## 7. 实施顺序

1. §4.1 盘点矩阵 → 定历史下限。
2. §4.2.3 `2019-01-02~2019-04-02` 旗标修复 + parity QA（最小独立闭环，先验证重刷通道）。
3. §4.2.1-2 2010-2014 backfill（按年）→ 2015 年初旗标修复 → 完备度报告。
4. §4.3 2021-2024 refit 重跑 + QA。
5. §4.4 新 synthetic continuous + 对比表 → 交 owner 口径决策。

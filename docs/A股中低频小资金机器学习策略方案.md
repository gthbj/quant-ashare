# A 股中低频小资金机器学习量化策略方案

> 业务场景：**A 股 · 日线 · 中低频 · 小资金 · 机器学习量化**
> 数据依赖：`ashare_dim` / `ashare_dwd` / `ashare_dws` / `ashare_ads`，表设计见 `docs/数据仓库建模方案-DWD-DIM.md` 与 `docs/数据仓库建模方案-DWS-ADS.md`。
> 文档目标：设计一组可用现有 ODS/DWD/DWS 逐步落地的策略，从 P0 基线 ML 排序到 P1/P2 资金、事件、行业增强。
> 文档维护：GPT-5（最近更新 2026-05-31）

---

## 0. TL;DR

1. **首个策略建议做 `ml_ranker_v0`**：全 A 股长-only 横截面排序，预测未来 5/10 日收益或分位，选 top N，日度出信号、周度或日度调仓。
2. **P0 特征只用已设计的核心 DWD**：价格/动量/波动、估值/市值/流动性、PIT 财务指标、市场状态。先跑通闭环，再接资金和事件。
3. **交易假设统一**：`t` 日盘后算信号，`t+1` 开盘/VWAP 建仓；停牌、一字涨停买不进、一字跌停卖不出必须进入回测。
4. **小资金优势**：容量约束弱，可覆盖小盘与低流动性股票，但仍不能忽略成交额、涨跌停、停牌和 ST 风险。
5. **策略框架优先做排序而不是绝对收益预测**：A 股横截面噪声大，`RankIC/top-bottom spread/top quantile return` 比 MSE 更贴近选股目标。
6. **所有策略输出都落 ADS**：预测、候选池、目标组合、订单计划、回测持仓/NAV/绩效必须可复现。

---

## 1. 交易与研究假设

| 项 | 默认口径 |
|---|---|
| 标的 | A 股普通股票，含退市历史；北交所可单独开关 |
| 频率 | 日线 EOD |
| 信号时点 | `t` 日收盘后 |
| 入场 | `t+1` 开盘或 VWAP，P0 用开盘近似 |
| 持有期 | 5/10/20 个交易日为主 |
| 方向 | 长-only，不做融券、不加杠杆 |
| 调仓 | P0 支持周度调仓，研究阶段可日度调仓 |
| 资金 | 小资金，默认容量约束弱，但保留成交额下限和单票权重上限 |
| 成本 | 通过参数配置，不在策略逻辑中写死 |
| 基准 | 中证 500 / 中证 1000 / 沪深 300，按 `dwd_index_eod.sec_code` 的 canonical 指数代码配置；`source_sec_code` 仅追溯 ODS 端点 |

关键约束：

- 不使用 `t` 日以后才知道的数据做 `t` 日特征。
- 不使用前复权价做训练特征。
- 不用当前仍上市股票列表回测历史；必须包含退市股历史。
- 不把买不进/卖不出的涨跌停样本当成可成交收益。

---

## 2. Universe 与样本过滤

### 2.1 基础股票池

来自 `dws_stock_universe_daily`：

```text
sample_basic
AND listed_days >= 60
AND NOT is_st
AND NOT is_suspended
AND has_price_data
AND has_valuation_data
```

### 2.2 流动性过滤

小资金不需要过高成交额门槛，但需要规避极端成交稀薄：

```text
amount_cny_20d_avg >= min_amount_cny
AND suspend_days_20d <= max_suspend_days
AND one_word_limit_days_20d <= max_one_word_limit_days
```

参数由策略配置控制，不在 DWS 中写死。研究时至少跑三档：

- 宽松：验证小盘/低流动性 alpha。
- 中性：P0 默认。
- 严格：检验策略对流动性暴露的依赖。

### 2.3 板块与风险开关

| 开关 | 默认 | 说明 |
|---|---|---|
| 主板 | 开 | 基础股票池 |
| 创业板/科创板 | 开 | 涨跌幅和风格不同，保留 board 特征 |
| 北交所 | 研究开关 | 流动性和制度差异大，建议单独回测 |
| ST | 关 | P0 剔除 |
| 次新股 | 关 | 默认上市 60 日内剔除 |
| 退市整理/名称含退 | 关 | 仅用于历史生命周期，训练剔除 |

---

## 3. 标签与目标函数

### 3.1 基础收益标签

来自 `dws_stock_label_daily`：

- `fwd_ret_1d`
- `fwd_ret_5d`
- `fwd_ret_10d`
- `fwd_ret_20d`
- `fwd_excess_ret_5d`
- `fwd_ret_5d_rank_pct`
- `top_quantile_5d`

P0 建议以 `fwd_ret_5d_rank_pct` 或 `fwd_excess_ret_5d` 为主目标，`fwd_ret_10d` 做稳健性检验。

### 3.2 推荐目标

| 目标 | 模型类型 | 优点 | 风险 |
|---|---|---|---|
| 横截面收益分位 `rank_pct` | 排序/回归 | 贴近选股，抗极端值 | 对牛熊方向不敏感 |
| 超额收益 `fwd_excess_ret_5d` | 回归 | 剔除市场 beta | 基准选择影响结果 |
| top 分位分类 `top_quantile_5d` | 二分类 | 直接优化入选概率 | 类别不平衡 |
| 多周期 ensemble | 排序融合 | 降低单一持有期偶然性 | 解释和调参更复杂 |

### 3.3 标签过滤

训练样本必须满足：

```text
label_valid_horizon
AND entry_reachable_horizon
AND sample_trainable
```

回测中不能简单丢弃卖不出的样本。若 `exit_reachable=false`，回测执行层应按规则顺延卖出或持仓延续，并记录无法成交原因。

---

## 4. 特征体系

## 4.1 P0 特征

| 特征族 | 来源 | 代表字段 |
|---|---|---|
| 短期反转 | `dws_stock_feature_price_daily` | `ret_1d`, `ret_3d`, `ret_5d` |
| 中期动量 | 同上 | `mom_20_5`, `mom_60_20`, `mom_120_20` |
| 波动/回撤 | 同上 | `vol_20d`, `downside_vol_20d`, `drawdown_60d` |
| 趋势位置 | 同上 | `close_to_ma20`, `ma20_to_ma60`, `close_rank_60d` |
| 流动性 | `dws_stock_feature_valuation_daily` | `amount_cny_20d_avg`, `turnover_rate_20d_avg`, `amihud_20d` |
| 估值/规模 | 同上 | `log_circ_mv`, `pb`, `pe_ttm`, `ep_ttm` |
| 财务质量 | `dws_stock_feature_fin_daily` | `roe`, `grossprofit_margin`, `ocf_to_or`, `debt_to_assets` |
| 财务成长 | 同上 | `netprofit_yoy`, `operating_revenue_yoy`, `q_roe` |
| 市场状态 | `dws_market_state_daily` | `market_regime`, `csi500_ret_20d`, `adv_ratio_1d` |

### 4.2 P1 增强特征

| 特征族 | 依赖 | 策略用途 |
|---|---|---|
| 资金流 | `moneyflow`、北向、两融 | 捕捉短中期资金推动 |
| 筹码 | `cyq_perf` | 强势股成本支撑、获利盘压力 |
| 业绩预告/快报 | `forecast`、`express` | 财报前置 surprise |
| 股东户数/增减持 | `holder_*` | 筹码集中和大股东行为 |
| 分红/回购/质押 | `dividend`、`repurchase`、`pledge` | 事件收益与风险 |
| 行业 | `index_member_all`、`ci_index_member`、`sw_daily`、`ci_daily` | 行业轮动、中性化和风险控制 |

### 4.3 预处理

训练面板 `ads_ml_training_panel_daily` 中做策略版本化预处理：

1. 按 `trade_date` 横截面 winsorize，默认 1%/99% 或 median MAD。
2. 按 `trade_date` 横截面 z-score。
3. 缺失值优先使用当日行业中位数；行业缺失时用当日全市场中位数；同时保留 `is_missing_*` 标记。
4. 类别字段做稳定编码；行业字段使用 `in_date/out_date` 时点映射，粗行业仅作兜底。
5. 市值、行业中性化作为可选预处理版本，不覆盖原始特征。

禁止：

- 用全样本均值/标准差做标准化。
- 用未来日填补历史缺失。
- 先合并全历史再随机切分训练/测试。

---

## 5. 策略族设计

## 5.1 `ml_ranker_v0`：全市场 ML 横截面排序

**定位**：P0 首个闭环策略。

**信号**：

- 输入：P0 特征宽表 `dws_stock_feature_daily_v0`。
- 标签：`fwd_ret_5d_rank_pct` 或 `fwd_excess_ret_5d`。
- 模型：LightGBM/XGBoost ranker 或回归模型；也可先用线性/ElasticNet 做可解释基线。
- 输出：`ads_model_prediction_daily.pred_rank_pct`。

**组合**：

- 每次调仓选 top N 或 top q。
- N 建议研究 20/30/50/80 四档。
- 权重：P0 等权；P1 可用预测分和风险反比加权。
- 调仓：周度为默认，日度用于研究上限。
- 持有期：5 或 10 个交易日。

**风控**：

- 单票权重上限。
- 流动性下限。
- 市场 `risk_off` 时降低总仓位。
- 行业集中度监控，行业映射不完整前不做过强约束。

**验收指标**：

- RankIC 均值、t 值、月度胜率。
- top-bottom 分位收益差。
- 含成本年化收益、最大回撤、换手。
- 分年份、分市值、分板块表现。
- 预测分 top 组能否稳定优于全市场等权。

## 5.2 `small_quality_reversal_v1`：小盘质量反转

**假设**：小资金可覆盖更宽的小盘股票；短期过度下跌后，质量和盈利不差的小盘股存在修复机会。

**核心特征**：

- 小市值：`log_circ_mv` 较低但不过低。
- 质量：`roe`, `grossprofit_margin`, `ocf_to_or`。
- 短期反转：`ret_5d` 低、`drawdown_20d` 高。
- 风险排除：高负债、低流动性、近期频繁一字板、ST/次新。

**信号构造**：

```text
score = rank(-log_circ_mv)
      + rank(roe)
      + rank(ocf_to_or)
      + rank(-ret_5d)
      + rank(-vol_20d)
```

可作为 ML 模型的 benchmark，也可作为规则策略直接回测。

**持有期**：5-10 日。

**主要风险**：

- 小盘风格长时间失效。
- 流动性和停牌导致收益不可实现。
- 极端下跌不是反转而是基本面恶化。

## 5.3 `trend_breakout_v1`：趋势延续与波动收缩

**假设**：中期趋势向上、近期波动收缩、量能改善的股票在未来 5-20 日延续概率更高。

**核心特征**：

- `mom_60_20`, `mom_120_20` 正。
- `close_to_ma20`, `ma20_to_ma60` 正。
- `vol_20d` 下降或低于自身历史分位。
- `amount_zscore_20d` 上升。
- 避免刚一字涨停、连续涨停、高位极端拥挤。

**组合**：

- 选 top 30-50。
- 持有 10/20 日或趋势破坏时退出。
- 市场 `risk_off` 时降低仓位。

**主要风险**：

- 追高回撤。
- 涨跌停导致入场价格偏离。
- 对市场状态敏感。

## 5.4 `earnings_surprise_v1`：财务与业绩事件增强

**依赖阶段**：P0 可用 `fina_indicator` 的可见财务；P1 接入 `forecast`、`express` 后增强。

**假设**：业绩改善、预告/快报超预期、盈利质量改善能在 10-20 日窗口中产生超额收益。

**核心特征**：

- `netprofit_yoy`, `operating_revenue_yoy`, `q_roe`。
- `report_age_days`，财报越新权重越高。
- P1：`forecast_pchg_mid`, `express_yoy_net_profit`, `days_since_forecast`。
- 质量过滤：`ocf_to_profit`, `debt_to_assets`。

**组合**：

- 财报季可提高该策略权重。
- 非财报季作为 ML 特征，不建议单独重仓。

**主要风险**：

- 财务公告口径/PIT 错误会直接造成未来泄露。
- 业绩好但估值已提前反映。
- 修正公告泄露到历史必须严禁。

## 5.5 `fundflow_chip_v1`：资金流与筹码增强

**依赖阶段**：P1，需先落 `dwd_stock_moneyflow`、`dwd_stock_north_hold`、`dwd_stock_chip`、`dwd_stock_margin`。

**假设**：大单净流入、北向增持、融资资金改善、筹码获利结构健康时，中短期收益更好。

**核心特征**：

- `net_mf_amount_to_mv_5d`。
- `buy_elg_amount_ratio`。
- `north_hold_ratio_chg_20d`。
- `rzye_chg_5d`。
- `winner_rate`, `cost_50pct` 相对当前价。

**持有期**：3/5/10 日。

**主要风险**：

- 资金流字段单位和口径必须逐表核对。
- 北向数据存在历史口径变化，需要 `is_north_data_available`。
- 资金流容易过拟合短期噪声。

## 5.6 `industry_rotation_v1`：行业轮动 + 行业内选股

**依赖阶段**：P1。申万时点映射来自 `index_member_all`，中信行业映射来自 `ci_index_member`，均使用 `in_date/out_date` 做历史归属还原。

**假设**：A 股中短期行业动量和行业拥挤度会影响个股收益；先选行业，再在行业内用 ML 排序选股。

**流程**：

1. 用 `dws_industry_feature_daily` 给行业打分。
2. 选 top 行业或降低 bottom 行业权重。
3. 行业内使用 `ml_ranker_v0` 的股票预测分。
4. 控制单行业最大权重。

**主要风险**：

- 行业 `out_date` 边界和历史区间重叠/缺口需要建表 QA；不能用 `is_new` 回填历史。
- 行业动量在拐点期回撤大。

---

## 6. 模型训练方案

### 6.1 数据切分

采用时间序列切分，不随机打散：

```text
train: 过去 N 年
valid: train 之后的一段时间
test: valid 之后的一段时间
live/paper: 最近未参与训练的时间
```

建议使用滚动或扩展窗口：

- 扩展窗口：训练集逐年增长，验证模型长期稳定性。
- 滚动窗口：固定最近 2-4 年训练，适应市场风格变化。
- 对 5/10/20 日重叠标签设置 embargo，避免相邻样本标签重叠造成过度乐观。

### 6.2 模型候选

| 模型 | 用途 | 备注 |
|---|---|---|
| 线性/ElasticNet | 可解释基线 | 检查数据和标签是否有效 |
| LightGBM Regression | P0 主力 | 预测收益或分位 |
| LightGBM Ranker | 排序优化 | 更贴近选股 |
| XGBoost | 对照 | 训练较重 |
| CatBoost | 类别变量较多时 | 行业、板块编码方便 |
| Ensemble | P1/P2 | 多 horizon、多风格融合 |

P0 不建议直接上复杂深度模型；数据质量、PIT、可成交回测比模型复杂度更重要。

### 6.3 样本权重

可选权重：

- 按 `amount_cny_20d_avg` 的截断函数给高流动性略高权重。
- 按时间衰减，近期样本权重更高。
- 按市场状态分层，避免牛熊样本不平衡。
- 对极端标签 winsorize，而不是简单删掉全部极端样本。

### 6.4 评价指标

**预测层**：

- IC / RankIC（日频、月频均值）
- ICIR
- top-bottom quantile spread
- top quantile 命中率
- 分市值、分行业、分板块 RankIC

**组合层**：

- 年化收益、波动、Sharpe、Calmar
- 最大回撤、最长回撤修复
- 超额收益、信息比率
- 日均换手、成本占收益比例
- 持仓数、单票集中度、行业集中度
- 无法成交比例、顺延成交影响

---

## 7. 组合构建与执行

### 7.1 候选池

```text
candidate = sample_liquid
AND prediction_rank_pct >= threshold
AND can_buy_next_open
AND risk_filter_passed
```

P0 候选：

- top 5% 或 top N。
- 排除 `entry_reachable=false` 的股票。
- 如果候选不足，保留现金或放宽阈值，由策略参数决定。

### 7.2 权重

P0 三种权重方案都应回测：

1. 等权：最稳健，便于诊断 alpha。
2. 分数线性权重：`weight ∝ max(pred_score - cutoff, 0)`。
3. 风险调整权重：`weight ∝ score / vol_20d`，再做上限裁剪。

默认约束：

- 单票权重上限参数化。
- 总权重不超过 1。
- 候选数不足时不强行满仓。
- 市场 `risk_off` 时整体乘仓位系数。

### 7.3 调仓

| 调仓方式 | 用途 |
|---|---|
| 周度调仓 | P0 默认，降低换手和噪声 |
| 日度滚动持有 | 检验标签上限和预测稳定性 |
| 固定持有期分层组合 | 对齐 5/10/20 日标签 |
| 信号衰减退出 | P1，用预测分跌出阈值退出 |

### 7.4 成交与失败处理

买入失败：

- `t+1` 停牌或一字涨停：不买，资金保留或替补候选。
- 开盘价缺失：不买。

卖出失败：

- 停牌或一字跌停：顺延到下一可卖日。
- 顺延期间持仓继续按价格变动计入净值；不能假设已卖出。

订单约束：

- A 股按 100 股手数约束估算股数。
- 成本和滑点参数化。
- 小资金也要记录交易金额占当日成交额比例，用于容量诊断。

---

## 8. 风控方案

### 8.1 样本层风控

- 剔除 ST、退市整理、上市未满 N 日。
- 剔除长期停牌、近期频繁一字板。
- 设置成交额下限。
- 过滤财务高风险：极高负债、经营现金流差、审计非标（P2）。

### 8.2 组合层风控

- 单票权重上限。
- 行业权重监控；基于申万时点映射做硬约束，中信行业作为对照。
- 市值暴露监控：避免组合完全押注微盘。
- 换手上限：超过上限按分数差排序执行。
- 市场状态仓位：指数趋势差、市场宽度低时降低总仓位。

### 8.3 模型层风控

- 监控每日预测分标准差和 top 候选数量。
- 监控 top 组行业/市值集中度。
- IC 连续恶化触发降权或暂停。
- 特征漂移/缺失异常时禁止出新组合。

---

## 9. ADS 落表流程

1. 从 DWS 生成 `ads_ml_training_panel_daily`。
2. 训练模型，登记 `ads_model_registry`。
3. 每个交易日盘后写 `ads_model_prediction_daily`。
4. 根据策略过滤写 `ads_stock_candidate_daily`。
5. 组合优化写 `ads_portfolio_target_daily`。
6. 交易模拟/计划写 `ads_order_plan_daily`。
7. 回测写 `ads_backtest_trade_daily`、`ads_backtest_position_daily`、`ads_backtest_nav_daily`、`ads_backtest_performance_summary`。
8. 每日写 `ads_signal_monitor_daily` 和数据质量告警。

每一层都保留 `strategy_id/model_id/run_id`，不能只保存最终净值。

---

## 10. P0 最小可用闭环

### 10.1 必做事项

1. 物化 P0 DIM/DWD。
2. 建 DWS P0：universe、价格特征、估值特征、财务特征、市场状态、标签、样本。
3. 建 ADS P0：训练面板、模型预测、候选池、组合、回测结果。
4. 训练 `ml_ranker_v0`。
5. 回测 5 日和 10 日两个 horizon。
6. 输出基线报告：RankIC、分位收益、组合净值、回撤、换手、不可成交比例。

### 10.2 P0 成功标准

- 数据链路可从 DWD 复现到 ADS，不直接读 ODS。
- 样本、特征、标签主键唯一。
- 所有财务特征 PIT 校验通过。
- 训练/验证/测试严格按时间切分。
- 回测处理停牌和涨跌停成交失败。
- 基线策略结果能解释到特征族、年份、市场状态、风格暴露。

---

## 11. P1/P2 研究路线

**P1：提高收益质量**

- 接入资金流/筹码/北向/两融。
- 接入业绩预告/快报、股东户数、分析师。
- 做行业轮动和行业内排序。
- 做多 horizon ensemble。

**P2：降低回撤与提升可复现**

- 加入龙虎榜、大宗、质押、回购、审计。
- 建特征漂移和 IC 监控。
- 做动态仓位和市场状态切换。
- 建策略报告自动化。

**P3：扩展研究边界**

- 北交所单独模型。
- 分风格模型：小盘、成长、价值、低波。
- 多模型 ensemble 与在线 paper trading。

---

## 12. 待 owner 确认

1. P0 回测默认成本参数：佣金、税费、滑点、冲击成本。
2. P0 默认调仓频率：周度还是日度滚动。
3. P0 默认持股数和单票上限。
4. 是否把北交所纳入首个基线，还是单独研究。
5. 首个模型训练工具链：Python + LightGBM/XGBoost，还是先用 BigQuery ML/简单模型做基线。

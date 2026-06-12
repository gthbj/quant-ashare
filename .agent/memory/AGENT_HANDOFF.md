> 当前交接补充（2026-06-12，GPT-5 Codex，PR #186 CSV cleanup）
> - 已按 owner 要求直接从 `main` 删除 PR #186 带入的四份分析 CSV：`docs/analysis_strategy1_signal_ic_decomposition_20260611_daily.csv`、`docs/analysis_strategy1_signal_ic_decomposition_20260611_summary.csv`、`docs/analysis_strategy1_transfer_ladder_20260611_results.csv`、`docs/analysis_strategy1_transfer_ladder_20260611_transfer_coefficients.csv`。
> - 保留 PR #186 的只读分析脚本、测试和 Markdown 报告；CSV 视为可再生成的本地/临时分析产物，不再跟随 git。`docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv` 属于其他 PR，本轮未动。
> - 本轮未运行 BigQuery、未启动 Cloud Run、未改策略结果、未改变 accepted / promotion 状态。
>
> Model: GPT-5 Codex

> 当前交接补充（2026-06-12，GPT-5 Codex，GCS checkpoint archive）
> - 已将 `configs/ingestion/ods_current_scope_v0.yml` 当前生产 14 个 ODS endpoint 及其 current partition variants 的 2010+ checkpoint 做可逆归档；scope 为 `gs://data-aquarium/a-share/tushare/_checkpoints/endpoint=*/logical_date=*.json` 且 `logical_date >= 20100101`。
> - 归档 run：`checkpoint_archive_current14_20260612T035604Z`；根路径 `gs://data-aquarium/a-share/tushare/checkpoint_archive/run_id=checkpoint_archive_current14_20260612T035604Z/`；产物为 26 个 gzip JSONL 归档对象 + `manifest.json`，共 65,891 条 checkpoint 记录，源 checkpoint 47,955,858 bytes，gzip 后 7,951,990 bytes。
> - 每条归档记录保存原始 `source_uri` / bucket / object name / endpoint / logical_date / generation / size / crc32c / md5 / sha256 / `content_base64`，可按 manifest 反向恢复；校验已完成：逐 gzip 重算行数、字节数、`jsonl_sha256`，逐条校验 content sha256，并抽样 5 个原对象按 generation 比对通过。
> - 本轮没有删除原 `_checkpoints/` 对象；后续如要真正减少对象数，仍需 owner 另行明确批准 lifecycle 或删除策略。manifest 记录 4 个 current-scope endpoint 为空：`index_daily`、`index_daily_000001_SH`、`index_dailybasic`、`index_dailybasic_000001_SH`。
>
> Model: GPT-5 Codex

> 当前交接补充（2026-06-11，Claude Fable 5，PRD_10）
> - 新增 `docs/prd/PRD_20260611_10_策略1自上而下整手组合构造.md`：针对 PR #186 确认的结构性现金拖累（10 万 + 整手 + 等权 5% + 无再分配 → 25% 买单跳过、现金均值 29.4%），owner 决定重新设计构造规则而非修复等权。
> - 核心规则：自上而下贪心买入，新开仓最小权重 5%（`position_floor_count=20` 仅作门槛基数，`target_holdings` 退役为观测指标 `realized_holdings_count`）；**无单票上限**（owner 决策 2026-06-11）；`walk_depth=50` 统一买入深度与卖出保留阈值；P1 六条规则以"跳过→下一名顶上"替换语义绑定进构造（实现红线：禁止复用 ledger 层跳过留现金语义，防止复活 #179 A1 的现金拖累）；可负担性与 P1 标记均只约束新增买入、不强制卖出。
> - 三阶段：Phase 0 paper 双臂原型（带/不带 P1，预登记判读）→ Phase 1 `ledger_exec_v2_lot100_topdown` + 新 QA（不动 v1）→ Phase 2 research-only continuous 重跑 + 三方对比。含基线兼容条款（true-five-year 若被采纳则随之切换）。仅 docs+记忆改动。
>
> Model: Claude Fable 5

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_06/07/08 live 收口）
> - PRD_07 Phase 2 candidate-only live smoke 已在正式 runner 镜像 `sha256:45b4d257878afa91192410a8e300ad9c358c6a2b3412a6be6d1e5e1732843eb7` 上通过：run-version `v20260611_prd07smoke01`，2021/2022 matrix 预置后由 scheduler 提交 fanout executions `strategy1-train-candidate-fanout-job-g65hx` / `btvgv`，各 3/3 tasks succeeded；dry-run/live state plan hash 均为 `7ef90a481f0e64ad`，两个 live unit 均 `present_after_describe_success`，12 个候选 artifact 文件均可读；同 run_id recovery 重跑提交数 0，artifact-skip 新 run 提交数 0，missing-matrix preflight 本地失败且提交数 0，真实 GCS 临时 lock smoke 验证 lease 竞争语义。
> - PRD_06 Phase A 已完成生产历史修复：2010-2014、2015Q1、`2019-01-02..2019-04-02` 窗口重刷；发现并修复 57 个早期 `daily_basic` 市值字段全空开市日，暂停 `ashare-ods-ingestion-daily` 后补采并在 20:00 前恢复，随后日常 workflow execution `5e790d75-1351-4fb3-aea7-6a396675e3bc` 成功。
> - 本轮代码修复：窗口股票 DWD prev_close warm-up 不再被 730 自然日截断；market-state backfill 读取 `p_write_floor_date` 以覆盖稀疏股票 20-row rolling；`13_true5y_historical_coverage_checks.sql` 改为用 `history_obs_60d >= 61` 判定 2019 旗标修复，并新增 ODS `daily_basic` 市值字段 open-day 覆盖护栏。
> - PRD_06 宽窗口 overlap parity 已补证：stock/DWD/DWS 9 表在 `2019-04-03..2026-06-09`（label/feature/sample 从 `2019-03-06` 比较）以 `float_tolerance=1e-8` 全部 0 mismatch；index DWD 与 market-state DWS 在 `2019-04-03..2026-06-09` 以 `float_tolerance=1e-4` 全部 0 mismatch。严格 `1e-8/1e-5` 对 market-state 只剩浮点聚合 roundoff，非 regime/action 业务差异。
> - PRD_06 Phase B/C 已完成：2021-2024 true-five-year refit 使用 `__true5y01` 非默认 suffix，四年 train windows 均为名义五年实际开市日，refit panel coverage 缺口为 0，四个 refit Cloud Run executions `zj4t4` / `wqwpx` / `tdv5j` / `998sc` 成功，四年 `qa_refit_register_predict_outputs` 通过。
> - 新 true-five-year synthetic continuous `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01` / `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01` 已完成：merge prediction rows `2643406`，backtest execution `strategy1-backtest-report-job-4zbd4` 成功，`qa_continuous_backtest_outputs` job `20cf1a26-93ce-48c9-9c7a-d10587d37ae3` 与 `qa_lot_aware_ledger_outputs` job `afa4be4e-bd47-4eb4-add1-a80f39cef082` 通过；ADS run-scoped 表与 `research_promotion_manifest` 同 source 为 0 行。
> - 结果对比：effective-window continuous CAGR `12.04%`、MaxDD `-45.48%`、legacy Sharpe `0.613`、v3 contract Sharpe `0.5285`、contract Calmar `0.265`；true-five-year continuous CAGR `13.85%`、MaxDD `-37.19%`、legacy Sharpe `0.683`、v3 contract Sharpe `0.6076`、contract Calmar `0.372`。true-five-year 明显改善但仍未过 v3 hard gates（contract Sharpe `<0.70`，contract Calmar `<1.0`），不得自动标 accepted 或 promotion；是否采纳为新研究 baseline 仍需 owner 决策。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_09）
> - 分支 `codex/signal-ic-transfer-analysis` 已完成 PRD_20260611_09 信号 IC 分解与组合转换效率分析：新增只读脚本 `scripts/strategy1/analyze_signal_ic_decomposition.py`、兼容入口 `scripts/strategy1/analyze_transfer_ladder.py`、报告 `docs/分析-策略1信号IC分解与转换效率-20260611.md` 与四份结果 CSV。
> - 全程 BigQuery 只读：读取 official synthetic prediction run `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`、official backtest `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`、DWS labels/features/market state、DWD price/index 和 research target/position；未写 `ashare_research` / ADS / promotion。
> - 关键结论：5d raw rank IC=`0.040908`、NW t=`5.586351`，2021-2026 年度 IC 全正；市值中性后 IC 保留 `90.52%`，行业 snapshot 参考保留 `88.20%`。L0 score-weighted long/short no-cost Sharpe=`2.800047`（20bps 后 `1.807056`）；新增 L0.5 top-decile long-only IR=`0.509749`，L1/L2/L3 long-only IR 约 `0.491`/`0.544`/`0.486`。
> - Review follow-up 修正了旧 TC 伪迹：TC 改为 full prediction universe 域，平均 `TC_target=0.712888`、`TC_realized=0.628765`；target 与 score-weighted Top20 名字重合率均值/最小值均 `100%`，L3-L2 IR 差仅 `-0.058363`，等权替代分数权重不是优先瓶颈。真实执行缺口来自持仓覆盖率/现金路径：realized/target 覆盖率均值 `81.51%`、最小 `5%`，TC 行内 `official_cash_weight` 均值 `29.07%`。
> - 现金交叉核验已做实：NAV 表 `cash_cny/net_value_cny` 与 `1-sum(position.weight)` 最大差 `2.22e-16`、差异天数 `0`，NAV 现金权重均值 `29.36%`，现金 >50% 交易日 `265` 天。全周期 `BUY_SKIPPED_BELOW_LOT=690`，最低覆盖执行日 `2021-12-27` 的 20 个 BUY 全部 `BUY_SKIPPED_BELOW_LOT`，指向小资金 + 100 股整手约束造成的结构性现金拖累，而不是测量伪迹。
> - L3 paper 与 official daily_return corr=`0.913059`，但 paper CAGR 比 official 高 `2.90pp`、MaxDD 比 official 差 `12.30pp`；报告已声明 paper ladder 只作转换效率上界/分解，不等同正式回测。OQ-010 路线决策仍留 owner，本轮不 accepted、不 promotion。
>
> Model: GPT-5 Codex

> 当前交接补充（2026-06-11，Claude Fable 5，PRD_09）
> - 新增 `docs/prd/PRD_20260611_09_策略1信号IC分解与组合转换效率.md`：纯只读研究分析 PRD，把度量衡从组合 NAV 切换到信号层。动机：组合超额 t≈1.26（统计上不显著）而六个 refit 模型 valid rank IC 六年全正（`0.039~0.098`、日度 ICIR `0.30~0.81`），指向"信号真实、转换浪费"。
> - Part A IC 分解五维：按年（真 OOS）/ 市值+行业中性化 / market regime / 分数分位（多头侧 vs 空头侧贡献）/ horizon 1/5/10/20d 衰减；前向收益直接读 `dws_stock_label_daily` 的同口径标签并按 `label_valid_{h}d` 过滤；所有 t 值须 NW / block bootstrap 修正。
> - Part B 转换阶梯：L0 分数加权多空 → L1 long-only 分数加权 Top50 → L2 Top20 → L3 等权 Top20+7.5% cap（现行口径），逐级 IR 落差定价每条约束；L3 与 official 实际结果做恒等校验；TC 分拆为 `TC_target`（目标权重 vs 分数隐含权重）和 `TC_realized`（实际持仓权重 vs 分数隐含权重）。
> - §6 预登记解读规则先写后跑（中性化阈值 60%/40%、L0 IR<1.0、阶梯落差 0.1 IR 等），支撑 owner 三个决策：组合构造改进 / 对冲结构评估 / 回炉模型。仅 docs+记忆改动，无代码、无 BQ 操作。
>
> Model: Claude Fable 5

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_08）
> - PRD_08 Cloud Run Python ledger resume 已完成 research-only 真实数据验收：parent `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，cut `2024-12-31`，next open `2025-01-02`，anchor `2021-01-04`；resume child execution `strategy1-backtest-report-job-82454` 成功。
> - 两套 resume QA 均通过：`qa_cloudrun_ledger_resume_outputs` job `eb99f350-feb4-4fdc-977d-d2e6b7c74201`，`qa_ledger_resume_consistency` job `8b2b1e17-42ad-44d2-8318-9f283c26eee2`。验收产物仅写 research，ADS 同 run/backtest 为 0 行。
> - 代码/契约更新：`qa_ledger_resume_consistency` 从旧 BQML / `ledger_exec_v1` 默认升级到 Cloud Run lot100 / research-first 口径；两套 QA 都要求 state date、resume policy、ledger version、原始 rebalance anchor 和 next-open 边界；runbook 明确等价参照是 full fresh continuous parent 的同窗口切片，不是 cut 后 segment fresh-start。
> - 后续：PRD_07 worker 已在独立 worktree 提交分支 `codex/prd07-annual-live-smoke`；PRD_06 只读审计建议已回报，尚未整合到本 PRD_08 分支。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_06）
> - PR #182（PRD_07 annual scheduler live smoke code-prep）已合并到 `main@dab646d`；PRD06 分支已在该主线基础上继续 rebase，避免覆盖 scheduler live-smoke 记忆和 runbook 状态。
> - PRD06 true-five-year refit code-prep 已实现：annual rolling resolved plan 支持 `--true-five-year-refit` / `--emit-refit-only` / 非默认 refit suffix，只输出 `build_refit_training_panel` 与 `cloudrun_refit_register_predict`，不重建 selection matrix 或候选 fanout。
> - 新增/增强 QA 工具：stock window equivalence 可落 summary/sample JSONL；新增 index/market full-vs-window shadow parity；新增 `sql/qa/13_true5y_historical_coverage_checks.sql` 覆盖 `2019-01-02..2019-04-02` 旗标修复、true-five-year 每开市日 coverage 与估值/财务完备度。
> - 本轮只做代码准备和护栏，未执行生产 backfill、未写 DWD/DWS、未重跑 true-five-year refit 或 continuous ledger；后续必须先跑 PRD06 Phase A parity/coverage QA，再进入 2021-2024 true-five-year refit。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex，PRD_07）
> - PR #182 已合并到 `main@dab646d`，完成 PRD_07 年度滚动调度 Phase 2 live smoke 代码 PR 准备；只改 scheduler、focused test、Strategy1 Cloud Run runbook 和记忆/TODO。
> - `annual_pipeline_scheduler` 默认仍 dry-run 安全；真实提交必须显式 `--execute-live --candidate-only-smoke`，并且 live 路径只支持 candidate-only smoke，不会跑 select/refit/synthetic continuous 或完整 2021-2026 pipeline。
> - 新增 GCS generation-conditioned lease/state、execution 粒度 fanout、matrix 前置检查、artifact skip、state recovery、describe + artifact 双确认；未执行真实 Cloud Run live smoke、未改 job spec/IAM/镜像。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex）
> - 已完成 Strategy1 暴露管理 NAV 级上限仿真（纯 BigQuery 只读 + 本地 pandas）：新增 `scripts/strategy1/simulate_exposure_overlay_upper_bound.py`、报告 `docs/分析-策略1暴露管理上限仿真-20260611.md`、结果矩阵 `docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv`。
> - 恒等校验通过：`e(t)==1` 复现 official continuous baseline CAGR `0.12036528993503293`、MaxDD `-0.45481511936569563`、Calmar `0.26464663290635421`、contract Sharpe `0.5285475500566128`；crunch excess vs `000852.SH`=`-0.19329880132544719`，与 PR #179 对比表一致。
> - 最优无摩擦 exposure 变体为 `two_state_biweekly_elow0_cost0bps`：CAGR `0.12130091898447448`、MaxDD `-0.297527701723727`、Calmar `0.4076962188116182`、contract Sharpe `0.6005994875878142`、平均暴露 `0.8873668188736682`、切换 `24` 次。
> - 按预登记判据，Calmar `<0.5`，建议真实 exposure ledger 工程缓做/降优先级；所有 exposure 变体 contract Sharpe 最高仅 `0.6006 < 0.70`，v3 双门仍不可达。报告 follow-up 已把 Markdown 结果表扩展为 25 列详细矩阵并补字段说明；review follow-up 又补入 hysteresis 被 two_state 系统性证伪、48 变体 in-sample selection bias、重算 IR 与官方 summary IR 不可跨文档误比三点。未写任何 BigQuery dataset、未改默认 profile、未 accepted、未 promotion，OQ-010 路线决策仍留给 owner。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，GPT-5 Codex）
> - PR #179 实现 `quant_ashare.strategy1.tail_risk_overlay_ab` 与 `qa_tail_risk_overlay_ab_outputs`，并完成 live research-only A/B：A1 `strategy1-backtest-report-job-8rqwl`、A2 `strategy1-backtest-report-job-hwqbl`、A3 `strategy1-backtest-report-job-6kbtz` 全部成功。
> - Review follow-up 后增强版 full overlay QA `bqjob_r6fb9e5810c470426_0000019eb59868de_1` 与 research readiness `bqjob_r15d88cd3e8df4d38_0000019eb59868de_1` 均通过；QA-OVERLAY-7/10 已改为逐 arm 硬门，对比表补齐 contract Sharpe、peak/trough、逐年 skip JSON、2024-01~02 vs `000852.SH` crunch excess。
> - 结果：baseline CAGR `0.12036528993503204` / MaxDD `-0.4548151193656952` / Calmar `0.26464663290635254` / crunch excess `-0.1932988013254472`；A1/A3 在 crunch 段转正（`0.10932302982271269` / `0.1226915291378361`）但全周期收益损耗过大；A2 MaxDD 降到 `-0.32883181037211673`，CAGR 降到 `0.0850673652169256`、Calmar 降到 `0.2586956691345056`、crunch excess `0.039028737788334156`。
> - 反向验证：三组 run/backtest 在 ADS run-scoped 表为 0 行，`research_promotion_manifest` 为 0 行。本轮结果仅 research evidence，不改默认 profile、不 accepted、不 promotion。

Model: GPT-5 Codex

> 当前交接补充（2026-06-11，Claude Fable 5，第二批）
> - 新增三个后续工程 PRD：`PRD_20260611_06_策略1历史数据回填与TrueFiveYearRefit.md`（ODS 2010 起历史回填 + 2015Q1/2019Q1 `has_full_history_60d` 旗标修复 + 2021-2024 true-five-year refit 重跑 + 新 synthetic continuous 对比）、`PRD_20260611_07_策略1年度滚动调度Phase2Live化.md`（真实 GCS lease/state、execution 粒度 fanout、candidate-only live smoke）、`PRD_20260611_08_策略1LedgerResume验收闭环.md`（PR #127 已合入但从未验收的 resume 做测试 + research-only 真实数据一致性验收）。
> - 关键探查事实（2026-06-11 只读 BigQuery）：ODS `daily`/`daily_basic` 已有 2010-2014 行（owner 确认 14 endpoint 从 2010 可用）；DWD 价格 2015 起；DWS `2015-Q1` 全部 150,726 行与 `2019-Q1` 全部 208,007 行 `has_full_history_60d=FALSE`——后者是陈旧标记，DWD 已有 2018 行，重刷 `2019-01-02..2019-04-02` 窗口即可修复（实证缺口含 4-01/4-02 两个开市日，不止自然 Q1），无需新数据。
> - PRD_06 的 parity 硬门：重刷不得改变 `2019-04-03` 后任何现有行特征值，保护既有 selection/refit/official continuous 可复现性；不重做选参，2025/2026 refit 不重跑。
> - 本轮 docs/记忆-only，未改代码、未写任何 BigQuery 数据（只读探查）。

Model: Claude Fable 5

> 当前交接补充（2026-06-11，Claude Fable 5）
> - 新增 `docs/prd/PRD_20260611_05_策略1尾部风险OverlayAB.md`：在最新 effective-window synthetic prediction 流上做 P1 / P2 / P1+P2 三组 portfolio-only continuous A/B，对照 baseline 量化 MaxDD / Calmar 改善与 CAGR 损耗；零训练、零 merge。
> - 设计要点：复用 official synthetic run（从记忆/manifest 解析，禁止硬编码 id）、与 official 相同 skip-flags 执行模式（`--skip-tail-risk` 只跳诊断不影响 guard）、guard 生效性断言为硬门（`BUY_SKIPPED_TAIL_RISK` 计数 / risk-off 次日零买单）、risk-off 期现金占比曲线量化"只禁买"的隐性减仓效应。
> - 背景动机：official continuous MaxDD `-45.48%`；回撤窗口 `2021-10-21→2024-02-07` 分解显示 beta≈-36pp、超额损失≈-10pp（疑似集中 2024 踩踏段）。本 A/B 同时是"P1 设默认前必须 full-period A/B"既有约束的前置执行。
> - 本轮 docs/记忆-only，不改代码、不执行 BigQuery / Cloud Run；A/B 结果出来前不改默认 profile、不立暴露管理 PRD。

Model: Claude Fable 5

> 当前交接补充（2026-06-11，GPT-5 Codex）
> - PR #173 已合并到 `main@f1abf46`，dedicated refit panel + `effective_refit_train_start=max(nominal_start, 2019-04-03)` 口径进入主线。
> - 已从 `main@f1abf46` 构建并部署正式 runner digest `sha256:4768d25f49de4bb1e8084476d6f1fe1542ed86750823751fa104738eb0947699`，五个 Strategy1 jobs 的 boot smoke 全过。
> - 2021-2026 dedicated refit panel、final refit、refit QA、synthetic continuous merge、official continuous ledger、continuous QA 均已重跑通过。
> - 最新 official continuous（effective-window）指标：compound_annual_return=`0.12036528993503204`，max_drawdown=`-0.4548151193656952`，information_ratio=`0.5420201365046585`，return_period_count=`1313`。
> - DECISION-20260611-02 已关闭 OQ-014：接受 effective-window result 作为研究复盘口径，暂不修 pre-2019 DWS/lookback；但 result 未过 v3 absolute gates，不得标 accepted baseline 或 promotion。

Model: GPT-5 Codex

## 2026-06-12 GPT-5 Codex - Current-scope ODS checkpoint archive

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: local Codex session
模型: GPT-5 Codex
运行环境: `/Users/fisher/Desktop/git/worktrees/quant-ashare-checkpoint-archive`
Run ID: `checkpoint_archive_current14_20260612T035604Z`
相关 issue/PR: N/A

### 已完成工作

- 按 owner 要求，将现有项目当前生产范围的 14 个 ODS checkpoint 中 `logical_date >= 20100101` 的对象归档到 `gs://data-aquarium/a-share/tushare/checkpoint_archive/run_id=checkpoint_archive_current14_20260612T035604Z/`。
- 归档范围来自 `configs/ingestion/ods_current_scope_v0.yml` 的 14 个 endpoint 及现有 current partition variants；未纳入非 current-scope endpoint。
- 生成 26 个 endpoint gzip JSONL 归档对象和 `manifest.json`；共 65,891 条 checkpoint 记录，源 checkpoint 47,955,858 bytes，gzip 归档 7,951,990 bytes。
- 每条 JSONL 保存原 GCS 路径、generation、校验值和 `content_base64`，因此可从归档反向恢复原 checkpoint 内容。
- 本轮未删除任何原始 `_checkpoints/` 对象，也未设置 lifecycle。

### 重要上下文

- manifest 路径：`gs://data-aquarium/a-share/tushare/checkpoint_archive/run_id=checkpoint_archive_current14_20260612T035604Z/manifest.json`。
- 4 个 current-scope checkpoint endpoint 在当前 GCS 扫描中为空：`index_daily`、`index_daily_000001_SH`、`index_dailybasic`、`index_dailybasic_000001_SH`。
- 归档过程只处理 `_checkpoints` 小 JSON 内容；不处理也不下载 `raw_data`。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 已回读 manifest 和全部 26 个 gzip 归档对象，重算每个归档的行数、源字节数、gzip 字节数和 `jsonl_sha256`，与 manifest 一致。
- 已逐条校验 `content_base64` 解码后的 sha256 与记录的 `content_sha256` 一致。
- 已抽样 5 个原 checkpoint 对象，按 GCS generation 回读并比对 sha256 通过。

### 阻塞项

- 无归档阻塞项。
- 如要通过删除或 lifecycle 真正减少对象数，需要 owner 另行明确批准保留窗口、删除范围和恢复演练要求。

### 下一步建议

- 删除前保留最近 30-90 天 checkpoint，或先按 manifest 恢复抽样 checkpoint 到临时前缀验证完整恢复流程。
- 若 owner 确认减少对象数，再对原 `_checkpoints/` 制定 age=90/180 lifecycle 或批量删除计划。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

## 2026-06-11 GPT-5 Codex - PRD_09 signal IC transfer efficiency analysis

### 已完成工作

- 基于 `origin/main@d411144` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-signal-ic-analysis`，分支 `codex/signal-ic-transfer-analysis`。
- 新增 `scripts/strategy1/analyze_signal_ic_decomposition.py`，实现 PRD_09 的 Part A IC decomposition 与 Part B transfer ladder；`scripts/strategy1/analyze_transfer_ladder.py` 为兼容入口，复用同一实现，避免两套逻辑漂移。
- 新增报告 `docs/分析-策略1信号IC分解与转换效率-20260611.md` 与四份 CSV：IC summary、daily IC、transfer ladder results、transfer coefficients。CSV 因仓库 `*.csv` ignore 规则需 `git add -f` 纳入 PR。
- 本地执行时安装了缺失的 `google-cloud-bigquery-storage` 用户级 Python 依赖，用于加速 BigQuery Storage API 结果读取；未改仓库依赖文件。

### 重要上下文

- official synthetic prediction run：`s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`；official backtest：`bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`；窗口 `2021-01-04..2026-06-09`；label version `open_to_close_h1_5_10_20_v20260601`；feature version `strategy1_pv_v0_20260601`；market state version `market_state_v1_20260607`；benchmark `000852.SH`。
- 初次运行曾因默认 `strategy_id=strategy1_lgbm_v1` 查不到 synthetic registry join；只读断点查询确认 registry 实际 `strategy_id=ml_pv_clf_v0`，脚本默认值已修正为 `ml_pv_clf_v0`，仍可 CLI 覆写。
- Part A 结果：5d raw rank IC=`0.040908`，NW t=`5.586351`；年度 5d IC 全正（2021=`0.030861`、2022=`0.027927`、2023=`0.016943`、2024=`0.064402`、2025=`0.055560`、2026 YTD=`0.062493`）；市值中性后 IC=`0.037032`，保留 raw `90.52%`；snapshot 行业参考中性后 IC=`0.036080`，保留 `88.20%`。
- Regime / bucket：risk_off IC=`0.030273` 但 NW t=`1.189055`，risk_on IC=`0.058193`；top/bottom decile 5d spread=`0.7486pp`，short-side contribution share=`52.51%`，未超过 60% 阈值。
- Part B：L0 score-weighted long/short no-cost annual Sharpe=`2.800047`，20bps 成本后 `1.807056`；L0.5 top-decile long-only IR=`0.509749`，L1/L2/L3 long-only IR 分别约 `0.491` / `0.544` / `0.486`。L3-L2 IR 差=`-0.058363`，L1-L2 IR 差=`-0.053236`，宽度从 top decile 收到 Top50/Top20 没有形成第二个悬崖。
- Review follow-up 修正旧 TC 伪迹：非零并集相关会退化为对等权常数向量求相关，不能解释为 `TC≈0`。现改用 full prediction universe 域并补 membership 诊断：平均 `TC_target=0.712888`、`TC_realized=0.628765`；target 与 score-weighted Top20 名字重合率均值/最小值均 `100%`，说明目标组合成员资格忠实于信号，等权替代分数权重不是优先瓶颈。执行层缺口用 realized/target 覆盖率与现金解释：覆盖率均值 `81.51%`、最小 `5%`，TC 行内 `official_cash_weight` 均值 `29.07%`。
- 交叉核验确认 official 现金不是 join 伪迹：NAV `cash_cny/net_value_cny` 与 `1-sum(position.weight)` 最大差 `2.22e-16`，差异天数 `0`；NAV 现金权重均值 `29.36%`，现金 >50% 交易日 `265` 天。全周期 `BUY_SKIPPED_BELOW_LOT=690`；最低覆盖执行日 `2021-12-27` 的 20 个 BUY 全部为 `BUY_SKIPPED_BELOW_LOT`。
- L3 paper 与 official daily_return corr=`0.913059`，但 paper CAGR 比 official 高 `2.90pp`、MaxDD 比 official 差 `12.30pp`；报告明确 paper ladder 只用于转换效率上界/分解，不等同 official ledger。
- 全程 BigQuery 只读，未写任何 dataset，未改 run/backtest，未 accepted，未 promotion。OQ-010 路线决策仍留 owner。

### 改动文件

- `scripts/strategy1/analyze_signal_ic_decomposition.py`
- `scripts/strategy1/analyze_transfer_ladder.py`
- `tests/strategy1/test_signal_ic_transfer_analysis.py`
- `docs/分析-策略1信号IC分解与转换效率-20260611.md`
- `docs/analysis_strategy1_signal_ic_decomposition_20260611_summary.csv`
- `docs/analysis_strategy1_signal_ic_decomposition_20260611_daily.csv`
- `docs/analysis_strategy1_transfer_ladder_20260611_results.csv`
- `docs/analysis_strategy1_transfer_ladder_20260611_transfer_coefficients.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- Live read-only analysis：`python3 scripts/strategy1/analyze_signal_ic_decomposition.py` 成功生成报告和四份 CSV。
- `python3 scripts/strategy1/analyze_signal_ic_decomposition.py --help` 与 `python3 scripts/strategy1/analyze_transfer_ladder.py --help` 均成功。
- `python3 -m pytest -q tests/strategy1/test_signal_ic_transfer_analysis.py tests/strategy1/test_exposure_overlay_upper_bound.py`：16 passed。
- `python3 -m py_compile scripts/strategy1/analyze_signal_ic_decomposition.py scripts/strategy1/analyze_transfer_ladder.py`：通过。
- `python3 -m compileall -q scripts/strategy1 tests/strategy1`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无实现阻塞。本报告不关闭 OQ-010，不替 owner 做下一步策略路线决策。

### 下一步建议

- 基于 PRD_09 结果，下一步优先讨论组合转换方向：long-only 相对多空的约束损耗、真实 ledger 的 100 股整手 / 小资金现金拖累、以及是否需要把 target 名字忠实但实际持仓覆盖不足的问题纳入后续组合/执行层改造；等权 Top20 和 Top50 扩宽暂非优先瓶颈。
- 不建议把本次 paper ladder 数值当正式回测结果；任何策略默认/accepted/promotion 仍需独立 PRD、真实 ledger 与 QA。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Cloud Run ledger resume acceptance

### 已完成工作

- 基于 `origin/main@6b619b0` 新建分支 `codex/strategy1-resume-acceptance`，实施 `docs/prd/PRD_20260611_08_策略1LedgerResume验收闭环.md`。
- `qa_ledger_resume_consistency` 已从旧 BQML / `ledger_exec_v1` 默认值升级为 Cloud Run Python `ledger_exec_v1_lot100` / research-first 口径。
- `qa_cloudrun_ledger_resume_outputs` 与 `qa_ledger_resume_consistency` 均纳入 `manual_resume_qa` active contract，要求 `p_state_as_of_date`、`p_resume_policy_id`、`p_ledger_version`、`p_rebalance_anchor_start`，并断言 `p_compare_start` 为 `state_as_of_date` 后下一 SSE 开市日。
- 真实 research-only resume child 已跑通：`s1_resume_acceptance_resume_20250102_20260609_v20260611_01` / `bt_s1_resume_acceptance_resume_20250102_20260609_v20260611_01`，Cloud Run execution `strategy1-backtest-report-job-82454`。
- 两套 QA 均通过：`qa_cloudrun_ledger_resume_outputs` job `eb99f350-feb4-4fdc-977d-d2e6b7c74201`；`qa_ledger_resume_consistency` job `8b2b1e17-42ad-44d2-8318-9f283c26eee2`。

### 重要上下文

- 验收 parent 为 latest effective-window official continuous backtest `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，cut `2024-12-31`，next open `2025-01-02`，rebalance anchor `2021-01-04`。
- 等价参照必须是 full fresh continuous parent 的同窗口切片；cut 后重新 fresh-start 的短段会重置现金、持仓和 NAV，不能作为 resume 等价参照。本轮曾跑过 short fresh diagnostic，但不纳入验收。
- 验收产物行数：candidate `89315`、target `740`、order `1340`、trade `1392`、position `6554`、NAV `345`、ledger state `345`、summary `1`。ADS 同 run/backtest candidate/trade/NAV/ledger state/summary 均为 `0` 行。
- 默认正式 continuous 仍为 fresh-run；resume 已是可用工具，但正式结果若采用 resume segment 仍需 owner 显式批准并重跑两套 resume QA。

### 改动文件

- `configs/strategy1/active_step_catalog.yml`
- `sql/strategy1/qa/qa_cloudrun_ledger_resume_outputs.sql`
- `sql/strategy1/qa/qa_ledger_resume_consistency.sql`
- `tests/strategy1/test_ledger_resume_acceptance.py`
- `docs/prd/PRD_20260611_08_策略1LedgerResume验收闭环.md`
- `docs/策略1CloudRun训练回测运行手册.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `python3 -m pytest -q tests/strategy1/test_ledger_resume_acceptance.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_sql_render.py`：24 passed。
- Cloud Run resume child execution `strategy1-backtest-report-job-82454`：succeeded。
- BigQuery QA jobs `eb99f350-feb4-4fdc-977d-d2e6b7c74201` / `8b2b1e17-42ad-44d2-8318-9f283c26eee2`：succeeded。
- BigQuery readback confirmed research output rows present and ADS output rows zero for the resume child run/backtest.

### 阻塞项

- 无。

### 下一步建议

- 若正式结果采用 resume segment，仍需 owner 显式批准并重跑两套 resume QA。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-12 GPT-5 Codex - PR #186 CSV cleanup

日期: 2026-06-12
Agent ID: Codex
Agent 实例 ID: 本地 Codex desktop session
模型: GPT-5 Codex
运行环境: `/Users/fisher/Desktop/git/worktrees/quant-ashare-remove-pr186-csv`
Run ID: N/A
相关 issue/PR: PR #186

### 已完成工作

- 按 owner 要求直接从 `main` 删除 PR #186 带入的四份分析 CSV。
- 保留 PR #186 的只读分析脚本、测试和 Markdown 报告；未删除其他 PR 的 CSV。
- 同步更新 `IMPLEMENTATION_STATUS.md`、`AGENT_HANDOFF.md` 和 `TODO.md`，记录 CSV 作为可再生成临时产物的清理口径。

### 重要上下文

- 删除文件为 `docs/analysis_strategy1_signal_ic_decomposition_20260611_daily.csv`、`docs/analysis_strategy1_signal_ic_decomposition_20260611_summary.csv`、`docs/analysis_strategy1_transfer_ladder_20260611_results.csv`、`docs/analysis_strategy1_transfer_ladder_20260611_transfer_coefficients.csv`。
- `docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv` 属于其他 PR，本轮未动。
- 本轮未运行 BigQuery、未启动 Cloud Run、未改策略结论、未改变 accepted / promotion 状态。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
- `docs/analysis_strategy1_signal_ic_decomposition_20260611_daily.csv`
- `docs/analysis_strategy1_signal_ic_decomposition_20260611_summary.csv`
- `docs/analysis_strategy1_transfer_ladder_20260611_results.csv`
- `docs/analysis_strategy1_transfer_ladder_20260611_transfer_coefficients.csv`

### 测试 / 验证

- `git diff --name-status HEAD -- '*.csv'` 确认仅删除 PR #186 的四份 CSV。
- `git diff --check` 通过。

### 阻塞项

- 无。

### 下一步建议

- 后续分析 CSV 默认作为本地临时产物；只有 owner 明确要求或测试 fixture 必需时才纳入 git。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_07 annual scheduler live smoke code prep

### 已完成工作

- PR #182 已合并到 `main@dab646d`。原独立 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd07-live-smoke`，分支 `codex/prd07-annual-live-smoke`。
- `quant_ashare.strategy1.annual_pipeline_scheduler` 新增 Phase 2 candidate-only live smoke 路径，入口必须同时传 `--execute-live --candidate-only-smoke`；默认 dry-run / 非 live 仍保持安全。
- 新增真实 GCS generation-conditioned annual scheduler lease/state 抽象；state create/update 使用 generation precondition，冲突重读/重试，丢失 lease ownership 停止提交。
- live smoke 按 Cloud Run execution 记账，先检查对应 matrix `matrix_manifest.json` / `work_units.json` 已存在，缺失则本地失败且不提交 Cloud Run；支持 artifact precheck skip、state recovery 不重复提交、共享资源池 admission、execution describe + candidate artifact 双确认；`gcloud execute` 非零但有 execution id 时按 describe/artifact 二次确认。
- 更新 `docs/策略1CloudRun训练回测运行手册.md` 的 Phase 2 live smoke 命令与边界说明。

### 重要上下文

- 本轮没有执行真实 Cloud Run live smoke，没有跑完整 2021-2026 pipeline，没有修改 Cloud Run job spec、IAM 或镜像。
- PRD_07 后续真实验收仍需在合并/部署后按 candidate-only 五场景执行并记录 execution id / artifact 路径；执行前必须先准备/复用对应 run-version 的 matrix artifact。

### 改动文件

- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `docs/策略1CloudRun训练回测运行手册.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_annual_pipeline_scheduler.py`：13 passed。
- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_annual_pipeline_scheduler.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_tail_risk_overlay_ab.py`：25 passed。

### 阻塞项

- 无代码阻塞。真实 candidate-only live smoke 尚未执行。

### 下一步建议

- 合并并部署含本分支代码的 runner 镜像后，按 runbook 执行 PRD_07 candidate-only live smoke 五场景；通过前不要声称 annual scheduler live 化已经生产验收。
- Phase 3 完整 2021-2026 live pipeline 仍需 owner 另批。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Exposure overlay upper-bound simulation

### 已完成工作

- 新增 `scripts/strategy1/simulate_exposure_overlay_upper_bound.py`，对 official continuous baseline NAV 做本地 pandas 暴露缩放上限仿真；BigQuery 查询全为只读，不写 `ashare_research` / ADS / promotion 相关表。
- 新增 `docs/分析-策略1暴露管理上限仿真-20260611.md`，按预登记判据报告方法、局限、恒等校验、完整矩阵摘要和结论；review follow-up 后补充 hysteresis 明显弱于 two_state、best-of-grid 存在 in-sample selection bias、重算 IR 与官方 summary IR 口径差异。
- 新增结果 CSV `docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv`，包含 identity + `e_low` / 状态机 / 生效时点 / 成本档共 49 行结果；review follow-up 后 Markdown 报告也展示同一 25 列详细结果矩阵和字段说明。
- 新增 `tests/strategy1/test_exposure_overlay_upper_bound.py`，覆盖 PIT 信号、三态迟滞、biweekly 调仓约束、成本扣减、identity metric 复现和 markdown 表输出。

### 重要上下文

- Baseline backtest：`bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`；窗口 `2021-01-04..2026-06-09`；market state version `market_state_v1_20260607`；基准 `000852.SH` 使用 `dwd_index_eod.pct_chg / 100`。
- 恒等校验通过：CAGR `0.12036528993503293`、MaxDD `-0.45481511936569563`、Calmar `0.26464663290635421`、contract Sharpe `0.5285475500566128`；crunch excess vs `000852.SH`=`-0.19329880132544719`。
- 最优无摩擦变体：`two_state_biweekly_elow0_cost0bps`，CAGR `0.12130091898447448`、MaxDD `-0.297527701723727`、Calmar `0.4076962188116182`、contract Sharpe `0.6005994875878142`、平均暴露 `0.8873668188736682`、暴露切换 `24` 次。
- 预登记判据结论：最优 Calmar `<0.5`，真实 exposure ledger 工程建议缓做/降优先级，剩余主要缺口在 alpha / 信号 / 组合构造。所有 exposure 变体最高 contract Sharpe `0.6006 < 0.70`，即使达到上界也不能通过 v3 双门。

### 改动文件

- `scripts/strategy1/simulate_exposure_overlay_upper_bound.py`
- `tests/strategy1/test_exposure_overlay_upper_bound.py`
- `docs/分析-策略1暴露管理上限仿真-20260611.md`
- `docs/analysis_strategy1_exposure_overlay_upper_bound_20260611_results.csv`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- Live read-only simulation：`Identity check passed`，market state / NAV / benchmark SSE 开市日覆盖一致，`is_risk_off` 无 NULL。
- Focused pytest：`tests/strategy1/test_exposure_overlay_upper_bound.py` 通过，含 detailed report column guard 和 review caveat guard。
- `compileall`、retired linter、Dataform generated SQLX check、`git diff --check` 已通过；`tests/strategy1` 已通过。

### 阻塞项

- 无实现阻塞。本报告不关闭 OQ-010，不替 owner 做路线决策。

### 下一步建议

- 若继续策略侧推进，优先把资源放在 alpha / 信号 / 组合构造或更强的回撤控制设计上；真实 exposure ledger 在当前上界证据下不宜作为下一阶段 P0。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD06 true-five-year refit code-prep

### 已完成工作

- 基于 `origin/main@dab646d` rebase，worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd06-true5y`，分支 `codex/prd06-true5y-refit`。
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py` 新增 true-five-year refit-only plan 能力：`--true-five-year-refit` 禁用 `2019-04-03` floor，`--final-refit-run-suffix` 强制使用非默认 suffix，`--emit-refit-only` 只输出 refit panel / refit-register-predict 两步。
- `scripts/qa/run_windowed_refresh_equivalence.py` 增强 summary JSONL 与 mismatch sample JSONL 输出，便于 PRD06 overlap parity 留档。
- 新增 `scripts/qa/run_index_market_windowed_equivalence.py`，用 scratch full/window shadow 表对比 `dwd_index_eod` 与 `dws_market_state_daily` 的 window refresh 等价性。
- 新增 `sql/qa/13_true5y_historical_coverage_checks.sql`，覆盖 `2019-01-02..2019-04-02` 旗标修复、true-five-year open-day feature/sample coverage、估值完备度硬门与财务完备度报告。
- 更新 Strategy1 Cloud Run runbook、`KNOWN_CONSTRAINTS.md`、`IMPLEMENTATION_STATUS.md`、`TODO.md`。

### 重要上下文

- 本轮是代码准备，不是生产执行：没有执行 BigQuery backfill，没有写 DWD/DWS，没有重跑 2021-2024 true-five-year refit，也没有生成新的 continuous ledger。
- `--true-five-year-refit` 只能在 PRD06 Phase A 完成后使用：历史 DWD/DWS 回填、`2019-01-02..2019-04-02` 旗标修复、`sql/qa/13_true5y_historical_coverage_checks.sql`、stock/index/market parity 全过。
- true-five-year refit run 必须使用非默认 suffix（例如 `__true5y01`），不得覆盖 current effective-window `__refit01` 产物。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `scripts/qa/run_windowed_refresh_equivalence.py`
- `scripts/qa/run_index_market_windowed_equivalence.py`
- `sql/qa/13_true5y_historical_coverage_checks.sql`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_true5y_prd06_contracts.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_true5y_prd06_contracts.py tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1/test_refit_panel_coverage_contract.py`：32 passed。
- `python3 -m py_compile scripts/qa/run_windowed_refresh_equivalence.py scripts/qa/run_index_market_windowed_equivalence.py scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`：通过。

### 阻塞项

- 生产 backfill / true-five-year refit / continuous ledger 尚未执行；需合并部署后按 PRD06 Phase A/B/C 分步跑，并逐步记录证据。

### 下一步建议

- 合并 code-prep PR 后先跑 `2019-01-02..2019-04-02` 最小旗标修复与 parity QA；确认 `2019-04-03` 后零变化后，再扩到 2010+ 历史回填和 2021-2024 true-five-year refit。

### 已更新记忆文件

- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Tail-risk overlay A/B implementation and live run

### 已完成工作

- 合并 PR #176，merge commit `5c27e28`。
- 基于 `origin/main@5c27e28` 新建 worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-tail-risk-overlay-ab`，分支 `codex/strategy1-tail-risk-overlay-ab`。
- 新增 `quant_ashare.strategy1.tail_risk_overlay_ab`：research-only，自动发现 latest refit-backed synthetic continuous source，构造 A1 / A2 / A3 三组 overlay arm，可 `--parallel-arms` 并发提交 Cloud Run backtest-report jobs，并串接 continuous / lot-aware / overlay QA。
- 新增 `qa_tail_risk_overlay_ab_outputs` 并登记 catalog；QA 覆盖 source/preflight、market state 全窗口覆盖、tail-risk required fields、生效性、risk-off 次日零 filled BUY、market skip 只在 risk-off execution dates、A2 guard 前 candidate / target 与 baseline 一致。
- 更新 Cloud Run runbook，补 Tail-risk overlay continuous A/B dry-run / preflight / execute 示例。

### 重要上下文

- Source synthetic run：`s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`；synthetic model `synth_s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`；input manifest sha256 `bfd1e3c3e251954ae5ffa1a58102570e4c4538a92b24c9c181c7e41368877166`。
- Baseline backtest：`bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`。
- Live preflight job：`721577f5-35dc-4609-ab23-683af2e12c5b`。
- Cloud Run executions：A1 `strategy1-backtest-report-job-8rqwl`、A2 `strategy1-backtest-report-job-hwqbl`、A3 `strategy1-backtest-report-job-6kbtz`，均 succeeded。
- QA jobs：A1 continuous `e9637a8b-9c04-4d1a-be9e-267ce75ea886` / lot-aware `c6b62f19-daf0-4253-8917-ce4b5d04c790`；A2 continuous `f970f701-d5aa-4efe-8dbd-1e5ac2dd4c6d` / lot-aware `78935e7c-e6cf-45ab-9b00-bab668b8ec42`；A3 continuous `430a0a94-4a86-413b-a9af-38edfa3f46db` / lot-aware `40a8ebb7-3a90-4a2c-9ea7-4c5d6b408dca`；initial full overlay QA `cb94dc74-9e73-4921-b709-d02cae615bb2`；review follow-up 后 enhanced full overlay QA `bqjob_r6fb9e5810c470426_0000019eb59868de_1`；research readiness QA `bqjob_r15d88cd3e8df4d38_0000019eb59868de_1`。
- 结果：A1/A3 证明确实能改善 2024-01~02 crunch 段超额（baseline `-0.1932988013254472`，A1 `0.10932302982271269`，A3 `0.1226915291378361`），但全周期 CAGR/Calmar 损耗过大，不建议设默认；A2 是全周期 MaxDD/CAGR 取舍相对可讨论的 overlay（MaxDD `-0.32883181037211673`、CAGR `0.0850673652169256`、Calmar `0.2586956691345056`、crunch excess `0.039028737788334156`），但也未改善 Calmar。
- 本轮没有 promotion；ADS run-scoped 表对三组 run/backtest 反向验证为 0 行，`research_promotion_manifest` 同 source 为 0 行。

### 改动文件

- `src/quant_ashare/strategy1/tail_risk_overlay_ab.py`
- `sql/strategy1/qa/qa_tail_risk_overlay_ab_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_tail_risk_overlay_ab.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

### 测试 / 验证

- Focused pytest：21 passed；新增 `--parallel-arms` 后 focused pytest：6 passed。
- BigQuery dry-run：`qa_tail_risk_overlay_ab_outputs.sql` 通过。
- Research render check：无 `ashare_ads` 残留，命中 `ashare_research.research_backtest_trade_daily`。
- Live preflight、三组 Cloud Run executions、三组 continuous / lot-aware QA、full overlay QA、review follow-up 后 enhanced full overlay QA 和 research readiness QA 均通过。
- BigQuery 反向验证 ADS run-scoped 表与 promotion manifest 均为 0 行。

### 阻塞项

- 无实现阻塞。是否继续优化 A2、转向暴露管理 PRD，或保持研究证据，需要 owner 决策。

### 下一步建议

- 不要把任何 overlay profile 直接设为默认。若继续沿风控路线推进，优先拆成两条：调窄 P1 规则以减少常年误伤，或另写暴露管理 / 仓位控制方案；A2 可作为全周期 drawdown/carry tradeoff 对照。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Effective-window result decision

### 已完成工作

- 基于 PR #174 合并后的 `main@f8cf151` 新建分支 `codex/decide-effective-window-baseline`。
- 复核 latest effective-window official continuous result 与 `model_acceptance_contract_v3`：contract Sharpe=`0.5285475500566089`，低于 `0.70`；Calmar=`0.26464663290635254`，低于 `1.0`。
- 只读 BigQuery 复核 synthetic registry：run `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02` 仍为 `status='selected'`，无 `acceptance_status` / `native_acceptance_status`。
- 追加 `DECISION-20260611-02`：接受 effective-window annual final refit / continuous ledger 作为当前研究复盘事实口径，暂不投入 pre-2019 DWS lookback / valuation 覆盖重建；不得标 accepted baseline，不得 promotion。
- 关闭 OQ-014 并移入 `.agent/memory/archive/CLOSED_QUESTIONS.md`。

### 重要上下文

- 当前结果可用于下一轮策略复盘和实验设计，但不是 production accepted baseline。
- 2021-2024 仍不能描述为名义完整五年 refit。
- 若未来需要 true five-year annual evidence，需要重新开专项：先修复 / 重建 DWS lookback 与历史 valuation 覆盖，再重跑 dedicated panel / refit / continuous。

### 改动文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- BigQuery 只读复核 effective-window summary / registry acceptance state。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 基于 latest effective-window official continuous 做下一轮 OQ-010 策略改进方案，重点处理回撤与 risk-adjusted return；不要 promotion 当前 result。

### 已更新记忆文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `.agent/memory/archive/CLOSED_QUESTIONS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Annual final refit dedicated panel rerun

### 已完成工作

- PR #173 已合并到 `main`，merge commit `f1abf46`，annual plan / scheduler 已正式切到 `select -> build_refit_training_panel -> refit`。
- 从 `main@f1abf46` 构建并部署正式镜像 `strategy1-cloudrun-runner@sha256:4768d25f49de4bb1e8084476d6f1fe1542ed86750823751fa104738eb0947699`；五个正式 Strategy1 jobs 已更新，`latest` tag 未改。
- 六个 boot smoke 全部成功：`strategy1-train-predict-job-f5bs7`、`strategy1-prepare-matrix-job-s7bww`、`strategy1-train-candidate-fanout-job-w925b`、`strategy1-select-register-predict-job-w66fd`、`strategy1-backtest-report-job-whbxz`、`strategy1-train-predict-job-jtx7r`（`refit_register_predict --help`）。
- 2021-2026 dedicated refit panels 已重建成功，BigQuery jobs：`a967f6fe-9382-4a27-a18c-be3bd7e2fd4a`、`d69aeb3c-bc63-47d1-bd07-e89c224cf37c`、`00bf60cf-f0e5-4688-aa1b-c2bd9a9f8d27`、`41ed2c12-5d24-49a7-a81b-dab91fc1e6fc`、`b75ee22c-662b-4413-9e7e-5538f7d487a8`、`0c5a0656-407d-4c1e-9c99-3eeef5e09ab9`。
- 六年 final refit 全部成功，Cloud Run executions：`strategy1-train-predict-job-t4vq7`、`strategy1-train-predict-job-bmdw6`、`strategy1-train-predict-job-jjblp`、`strategy1-train-predict-job-zwg82`、`strategy1-train-predict-job-9zm2h`、`strategy1-train-predict-job-qvc78`。
- 六年 `qa_refit_register_predict_outputs` 全部通过：`27b9ffcc-4ecc-433b-b830-110551d08d0b`、`03213822-637a-4b37-92e3-2dc6d179faaa`、`e5136216-1e9f-4b51-80ba-cc9c93c2cc15`、`ca85715d-94f7-4c5d-bcef-cb44aff62253`、`df3e1750-9952-424b-94c3-af2d5403ac21`、`52f6ae15-9dec-4cc1-a0de-bffac8ed4d89`。
- Official synthetic continuous 以同一 run id `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02` 重写成功，insert job `d2f9beea-a58f-4650-82d2-07b135174ee9`，prediction rows=`2643406`，resolved manifest sha256=`2062d93544dd7c2bd12566f42da0ad3c973b5c6a63f00f4cd1c72a3a5269ba97`。
- Official continuous ledger 重跑成功，execution `strategy1-backtest-report-job-mq5d8`；continuous QA `fcd75906-ec42-454e-92e1-9b47d19a5727` 与 lot-aware QA `95dcee06-e912-481a-9c02-aafb14a823c5` 均通过。

### 重要上下文

- Effective-window official continuous summary：total_return=`0.8079208887460085`，compound_annual_return=`0.12036528993503204`，max_drawdown=`-0.4548151193656952`，information_ratio=`0.5420201365046585`，turnover_annual=`38.4823484768493`，total_economic_cost_cny=`17041.911125399998`。
- 输出行数：prediction `2643406`、NAV `1314`、ledger_state `1314`、signal_monitor `1314`、candidate `279625`、order `4806`、trade `4776`、position `21401`、summary `1`。
- `research_promotion_manifest` 行数为 `0`，ADS registry / prediction / summary 对同 synthetic run/backtest 均为 `0`。本轮没有 promotion、没有 ADS 写入。
- 本轮结果是 current DWS coverage 下的 effective-window refit。2021-2024 不得表述为名义完整五年 refit；是否可进入 baseline 评估仍由 OQ-014 owner 决策。

### 改动文件

- `docs/策略1CloudRun训练回测运行手册.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- PR #173 合并前：focused pytest 32 passed；full pytest 122 passed；retired lint、Dataform generated SQLX `--check`、compileall、`git diff --check` 均通过。
- 部署后六个 Cloud Run `--help` boot smoke 均 Completed=True。
- 六年 `qa_refit_register_predict_outputs` 均通过。
- Official continuous `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs` 均通过。
- BigQuery 审计确认 research outputs 存在、promotion manifest 为 0、ADS 同 synthetic run/backtest 为 0。

### 阻塞项

- 无执行阻塞。OQ-014 仍需 owner 方法论决策。

### 下一步建议

- 决定 OQ-014：接受 effective-window annual result 进入下一轮策略评估，或投入 DWS/lookback 修复后追求 true pre-2019 五年窗口。
- 若接受 effective-window 口径，再基于最新 official continuous 指标决定是否推进 accepted baseline 方案；仍不得直接 promotion。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Annual final refit dedicated panel implementation

### 已完成工作

- 基于 `origin/main@d6a40e6` 新建干净 worktree `/Users/fisher/Desktop/git/quant-ashare-refit-panel`，分支 `codex/fix-annual-refit-dedicated-panel`。
- 在 `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py` 中新增 dedicated refit panel plan step：selection panel 仍作为每年第一步服务 matrix / fanout / select，`build_refit_training_panel` 在 select 后用 refit run_id 写 panel。
- `cloudrun_refit_register_predict` 仍用 `--source-run-id=<selection run>` 读取 selected candidate lineage，但 `--source-panel-run-id=<refit run>` 读取 dedicated refit panel。
- final refit actual/effective 起点改为 `max(nominal_start, 2019-04-03)`，并在 raw metadata 记录 `effective_final_refit_min_train_start`；2021/2022/2023/2024 起点均为 `2019-04-03`，2025/2026 不受影响。
- 在 `quant_ashare.strategy1.annual_pipeline_scheduler` 中新增 `refit_panel` stage，依赖顺序改为 `select:yYYYY -> refit_panel:yYYYY -> refit:yYYYY`，continuous ledger 仍依赖六个 `refit:*`。
- 更新 PRD_02、KNOWN_CONSTRAINTS、OPEN_QUESTIONS、IMPLEMENTATION_STATUS、TODO，并追加 `DECISION-20260611-01` 记录 effective-window 口径。

### 重要上下文

- 这是 OQ-014 的工程缓解，不是 historical DWS 根因修复。若 owner 要求 true pre-2019 五年窗口，需要先修复 / 重建 DWS lookback 与历史 valuation 覆盖。
- 合并本分支后必须重建 Strategy1 runner 镜像；annual orchestrator / scheduler 的 resolved plan 由镜像内代码生成。
- 旧 official continuous 结果仍是已生成事实，但不能直接升级为 accepted baseline 或 promotion source。

### 改动文件

- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`
- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- Focused pytest：`PYTHONPATH=src python3 -m pytest -q tests/strategy1_cloudrun/test_dataset_role_routing.py tests/strategy1/test_annual_pipeline_scheduler.py tests/strategy1/test_refit_panel_coverage_contract.py`：32 passed。
- Full pytest：`PYTHONPATH=src python3 -m pytest -q tests`：122 passed。
- Scheduler dry-run：`python3 -m quant_ashare.strategy1.annual_pipeline_scheduler --dry-run --start-year 2021 --end-year 2026 ...` 生成 97 tasks，确认 `refit_panel:y2021` 依赖 `select:y2021`、`refit:y2021` 依赖 `refit_panel:y2021`、continuous 依赖六个 refit。
- BigQuery 覆盖审计（代码修改前执行）：以 `effective_refit_start=max(nominal_start, 2019-04-03)` 对 2021-2026 六年检查 SSE 开市日 labeled sample 覆盖，missing_labeled_days 均为 0。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。

### 阻塞项

- 无代码阻塞；尚未合并、重建镜像或重跑 live annual refit / continuous。

### 下一步建议

- 提交并发 PR；合并后重建 runner 镜像，更新 jobs，并以新 plan 重跑 2021-2026 dedicated refit panel / refit / synthetic continuous。

### 已更新记忆文件

- `.agent/memory/DECISION_LOG.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Annual refit source-panel coverage review follow-up

### 已完成工作

- 基于 `origin/main@00f2265` 在干净 worktree 审计 PR #171 后 review 的两条发现。
- BigQuery 按六个 annual selection source panel 与 SSE 交易日历对账，确认 review 指出的 `2019Q1` panel 空洞成立，并发现 selection split / label-embargo 内部年末缺口。
- `src/quant_ashare/strategy1/refit_register_predict.py` 已新增 SSE 开市日覆盖检查，source panel 在 refit train window 任一开市日缺 labeled 行、或 prediction source window 任一开市日缺 panel 行都会 fail-fast。
- `sql/strategy1/qa/qa_refit_register_predict_outputs.sql` 已新增 source panel labeled train 行与 refit prediction 的逐开市日覆盖断言，不再只依赖 min/max 日期端点。
- 新增 `tests/strategy1/test_refit_panel_coverage_contract.py`，锁住 Python helper 与 SQL QA 覆盖断言。
- 新增 `OQ-014`，并在 `KNOWN_CONSTRAINTS.md` / `TODO.md` / PRD_02 post-implementation note 中写明：`2019-04-03` override 是 observed alignment，不是根因修复；OQ-014 关闭前不得把本轮结果标记 accepted baseline 或 promotion source。

### 重要上下文

- 当前 official continuous 结果是已生成并已通过旧 QA 的事实记录，但 source selection panel 并未覆盖完整 refit 训练窗口。后续 owner 需选择接受当前结果为 diagnostic/provisional，或重建 DWS/lookback / dedicated refit panel 后重跑六年 refit + continuous。
- 集中自主决策清单已写入 `IMPLEMENTATION_STATUS.md`：`2019-04-03` 起点 override、train-predict 升 `8 CPU / 32Gi`、rehearsal 后置补跑、年度 diagnostic skipped、synthetic run 跳过默认 QA/诊断并外接专用 QA。
- 失败 / 跳过门清单也已集中写入 `IMPLEMENTATION_STATUS.md`：2024 refit panel coverage failure、2025/2026 OOM、synthetic partition filter failure、`QA-CONT-6` 两轮 failure、年度 diagnostic skipped、synthetic 默认 `10/12/20` QA/诊断 skipped。

### 改动文件

- `src/quant_ashare/strategy1/refit_register_predict.py`
- `sql/strategy1/qa/qa_refit_register_predict_outputs.sql`
- `tests/strategy1/test_refit_panel_coverage_contract.py`
- `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：122 passed。
- Focused pytest：`tests/strategy1/test_refit_panel_coverage_contract.py`、package entrypoint、catalog、SQL render 合计 37 passed。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_refit_register_predict_outputs.sql`：通过。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。

### 阻塞项

- OQ-014 需要 owner 决策；当前 PR 只补护栏和记录，不重建 DWS / panel，不重跑 annual refit 或 continuous ledger。

### 下一步建议

- 合并本 follow-up 后，优先决定 OQ-014：若要把年度结果推进 accepted baseline，需要先实现 dedicated refit panel 或 DWS/lookback 重算并重跑六年 refit + continuous。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/OPEN_QUESTIONS.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Annual rolling official continuous results

### 已完成工作

- PR #170 已合并到 `main`（merge commit `d105f9f`），修复 `QA-CONT-6` 跨年度误匹配；PRD_03 official continuous QA 口径进入主线。
- Official synthetic continuous 已在 `main@d0f9e4d` 后以 `--force-replace` 重跑成功：run `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`，model `synth_s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`，manifest URI `gs://ashare-artifacts/models/strategy1/ml_pv_clf_v0/run_id=s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02/model_id=synth_s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02/synthetic_continuous/manifest.json`，input sha256=`bfd1e3c3e251954ae5ffa1a58102570e4c4538a92b24c9c181c7e41368877166`，resolved sha256=`2062d93544dd7c2bd12566f42da0ad3c973b5c6a63f00f4cd1c72a3a5269ba97`，prediction rows=`2643406`，insert job `f566b4dd-14b8-4419-8225-4747adcb045a`。
- Official continuous ledger 已成功：Cloud Run execution `strategy1-backtest-report-job-w5k24`，backtest `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，fresh start，`2021-01-04..2026-06-09`，`ledger_exec_v1_lot100`，biweekly，target holdings 20，max weight 7.5%。
- Official QA 全部通过：`qa_continuous_backtest_outputs` job `843cfc18-054a-4910-b303-61e47f82f249`；`qa_lot_aware_ledger_outputs` job `0b5ec09d-0aad-41e3-871e-67766f2a4f5c`。
- Rehearsal pre-refit continuous 已补跑（diagnostic only）：synthetic run `s1_annual_roll_synth_continuous_rehearsal_2021_2026_n20_w075_v20260610_02`，manifest URI `gs://ashare-artifacts/models/strategy1/ml_pv_clf_v0/run_id=s1_annual_roll_synth_continuous_rehearsal_2021_2026_n20_w075_v20260610_02/model_id=synth_s1_annual_roll_synth_continuous_rehearsal_2021_2026_n20_w075_v20260610_02/synthetic_continuous/manifest.json`，input sha256=`d2908798e8b07ad126ca433f798b9f5187b8d2677726d8a1e4d35ef26d4d5699`，resolved sha256=`f3ebdba79deb10a05e9ad1cf50d7a6c9353172ddef6b66b6215a677e80812410`，prediction rows=`2643406`，insert job `36465e3e-90b6-43d6-b538-350f102311ac`；continuous backtest execution `strategy1-backtest-report-job-s88hz`；QA jobs `ae56421b-e316-492e-be5b-48584c7917c5` / `3a98e8d0-5ace-4a74-8170-36ac71e68ca9`。

### 重要上下文

- Official continuous summary（正式口径，不能用年度 fresh NAV 拼接替代）：total_return=`0.5012920494620134`，compound_annual_return=`0.08110633748103813`，annual_return=`0.10393379031649487`，annual_vol=`0.2273481486583799`，sharpe=`0.4571569679798399`，compound_sharpe=`0.35674949613471857`，max_drawdown=`-0.45925758365200664`，excess_return=`0.3466780784898209`，information_ratio=`0.3510127136837824`，turnover_annual=`37.6911874509589`，total_economic_cost_cny=`16695.7950538`。
- Rehearsal pre-refit continuous summary（diagnostic only）：total_return=`0.2857702525025081`，compound_annual_return=`0.04942495234912747`，annual_return=`0.06926784540786153`，annual_vol=`0.20478557532530298`，sharpe=`0.3382457250606113`，compound_sharpe=`0.2413497741265012`，max_drawdown=`-0.3845969073500922`，excess_return=`0.13115628153031555`，information_ratio=`0.16428853419676318`，turnover_annual=`30.586732030821928`。
- Official output row counts: prediction `2643406` / NAV `1314` / ledger_state `1314` / signal_monitor `1314` / candidate `279625` / order `4822` / trade `4820` / position `21536`。
- 年度 fresh diagnostic backtest 是 Phase 3 optional，本轮未重跑；最终评价只使用 single continuous ledger。
- 本轮没有 promotion，没有 ADS 写入（除 PRD_04 已完成的 additive migration），没有删除或修改 selection run 历史数据。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- PR #170 合并前：29 passed、Dataform `--check`、retired lint、compileall、BigQuery dry-run、live continuous QA、live lot-aware QA、`git diff --check` 均通过。
- Official continuous live QA: `qa_continuous_backtest_outputs` job `843cfc18-054a-4910-b303-61e47f82f249`；`qa_lot_aware_ledger_outputs` job `0b5ec09d-0aad-41e3-871e-67766f2a4f5c`。
- Rehearsal live QA: `qa_continuous_backtest_outputs` job `ae56421b-e316-492e-be5b-48584c7917c5`；`qa_lot_aware_ledger_outputs` job `3a98e8d0-5ace-4a74-8170-36ac71e68ca9`。

### 阻塞项

- 无执行阻塞；是否基于 official continuous 结果继续做策略改进或 accepted baseline 决策，需后续 owner 决策。

### 下一步建议

- 如需推进 OQ-010 accepted baseline，基于 official continuous 结果做特征/风控/候选空间复盘；不要把本结果直接标记 accepted。
- 清理本轮临时 worktree / 本地分支前，确认本记录 PR 已合并。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_03 continuous QA scope hotfix

### 已完成工作

- PR #169 已合并到 `main`（merge commit `d0f9e4d`），synthetic manifest valid window 已从原 selection registry 行解析。
- 从 `main@d0f9e4d` 以 `--force-replace` 重跑 official synthetic merge 成功：prediction rows=`2643406`，registry rows=`1`，input manifest sha256=`bfd1e3c3e251954ae5ffa1a58102570e4c4538a92b24c9c181c7e41368877166`，resolved manifest sha256=`2062d93544dd7c2bd12566f42da0ad3c973b5c6a63f00f4cd1c72a3a5269ba97`，insert job `f566b4dd-14b8-4419-8225-4747adcb045a`。
- `qa_continuous_backtest_outputs` 仍暴露 `QA-CONT-6` scope bug：SQL 把所有 target prediction date 与所有 year slice 的 valid window 交叉检查，导致 2021 official prediction 被 2022 source 的 2021 valid window 误伤。
- 当前分支 `codex/synthetic-continuous-qa-valid-scope` 已把 `QA-CONT-6` 收窄到同一 manifest year slice：`pred.predict_date` 同时满足 `m.predict_start..m.predict_end` 和 `m.valid_start..m.valid_end` 才算违规。
- 使用修正后 SQL 对 live official continuous run 执行 `qa_continuous_backtest_outputs` 已通过，job `843cfc18-054a-4910-b303-61e47f82f249`。
- `qa_lot_aware_ledger_outputs` 已再次通过，job `0b5ec09d-0aad-41e3-871e-67766f2a4f5c`。

### 重要上下文

- Official synthetic merge、single continuous ledger、continuous QA、lot-aware QA 均已实质通过；本分支合并后 PRD_03 执行层闭环。
- continuous ledger execution 仍是 `strategy1-backtest-report-job-w5k24`，窗口 `2021-01-04..2026-06-09`，fresh start，`ledger_exec_v1_lot100`。

### 改动文件

- `sql/strategy1/qa/qa_continuous_backtest_outputs.sql`
- `tests/strategy1/test_synthetic_continuous.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_synthetic_continuous.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_sql_render.py`：29 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --step=qa_continuous_backtest_outputs --output-dataset-role=research --params-json-b64=<official continuous QA params> --dry-run`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --step=qa_continuous_backtest_outputs --output-dataset-role=research --params-json-b64=<official continuous QA params>`：通过，job `843cfc18-054a-4910-b303-61e47f82f249`。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --step=qa_lot_aware_ledger_outputs --output-dataset-role=research --params-json-b64=<official lot-aware QA params>`：通过，job `0b5ec09d-0aad-41e3-871e-67766f2a4f5c`。
- `git diff --check`：通过。

### 阻塞项

- 无；本分支合并后可查询 continuous summary 指标并解释结果。

### 下一步建议

- 合并 `codex/synthetic-continuous-qa-valid-scope`。
- 查询 `research_backtest_performance_summary` / NAV / trade / position 行数，给出 single continuous ledger 指标。
- 更新最终运维记录后清理临时 worktree / 分支。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_03 synthetic continuous valid-window hotfix

### 已完成工作

- PR #168 已合并到 `main`（merge commit `41ef1cf`），修复 official synthetic merge 首次失败的 source prediction partition filter 缺口。
- 从 `main@41ef1cf` 以 `--force-replace` 重跑 official synthetic merge 成功：synthetic run `s1_annual_roll_synth_continuous_2021_2026_n20_w075_v20260610_02`，prediction rows=`2643406`，registry rows=`1`，input manifest sha256=`bfd1e3c3e251954ae5ffa1a58102570e4c4538a92b24c9c181c7e41368877166`，resolved manifest sha256=`0be2815342ab53543dbeee84918a3723433c3cc772502677c2a7a4ec24066ef6`，insert job `f8953afd-b95b-4b20-82f7-2af153bed998`。
- 跑 single continuous ledger 成功：Cloud Run execution `strategy1-backtest-report-job-w5k24`，backtest id `bt_s1_annual_roll_continuous_2021_2026_n20_w075_v20260610_02`，窗口 `2021-01-04..2026-06-09`，fresh start，`ledger_exec_v1_lot100`，skip diagnosis / tail-risk / default QA。
- `qa_lot_aware_ledger_outputs` 已通过，job `4dcfd716-6cea-4efd-b1f9-d7f195d1f004`。
- `qa_continuous_backtest_outputs` 暴露第二个契约缺口：`QA-CONT-6` valid 排除断言失败，因为 resolved manifest 从 refit registry 行的 `valid_start_date` / `valid_end_date` 取值，而 refit registry 中这两个字段等于 refit train window；正确 selection valid window 需要从 refit row 的 `model_params_json.source_run_id` 指向的原 selection registry 行读取。
- 当前分支 `codex/synthetic-continuous-valid-windows` 已实现修复：refit source 通过 source selection registry 解析 valid window，manifest 显式 `valid_start/end` 可覆盖，并补单测覆盖。

### 重要上下文

- continuous ledger 本体已生成且 lot-aware QA 通过，但 official 指标仍需等 synthetic manifest valid-window 修复后重跑 synthetic merge，并让 `qa_continuous_backtest_outputs` 通过。
- `qa_continuous_backtest_outputs` 是当前唯一未通过的 PRD_03 硬门；不要把年度 fresh NAV 或未过 continuous QA 的结果当正式结论。

### 改动文件

- `src/quant_ashare/strategy1/synthetic_continuous.py`
- `tests/strategy1/test_synthetic_continuous.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_synthetic_continuous.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_sql_render.py`：28 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `git diff --check`：通过。

### 阻塞项

- 需合并 `codex/synthetic-continuous-valid-windows` 后，以 `--force-replace` 重跑 official synthetic merge，再跑 `qa_continuous_backtest_outputs`。

### 下一步建议

- 提交并合并 valid-window hotfix PR。
- 重跑 synthetic merge；如 prediction stream 内容不变，可不重跑 continuous ledger，但必须重跑 `qa_continuous_backtest_outputs` 与结果复核。
- 若 `qa_continuous_backtest_outputs` 通过，再查询并记录 continuous summary 指标。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_03 synthetic continuous partition filter hotfix

### 已完成工作

- PR #167 合并后，从 `main@c72cd8f` 执行 official synthetic merge，首次 BigQuery prediction insert 暴露 partition filter 缺口：source `research_model_prediction_daily` join 只有 manifest 动态窗口，缺少静态 `predict_date` 过滤，BigQuery job `cde0ff0e-fe0a-4124-89d1-c5406a8c5caa` 失败。
- 当前分支 `codex/synthetic-continuous-partition-filter` 已补 synthetic prediction insert 的整体 `predict_date` 静态窗口过滤，并同步补 `qa_continuous_backtest_outputs` source count 的 `p_predict_start` / `p_predict_end` 分区过滤。
- `TODO.md` 与 `IMPLEMENTATION_STATUS.md` 已更新为“PR #167 代码已合并，但 official synthetic merge 需 hotfix 合并后 `--force-replace` 重跑”的状态。

### 重要上下文

- 首次 official merge 已可能写入 synthetic registry partial row，但 prediction insert 未完成；hotfix 合并后必须用 `--force-replace` 重跑，避免 partial registry 干扰。
- Official continuous 结果仍未产生；禁止把年度 fresh NAV 拼成正式结果。

### 改动文件

- `src/quant_ashare/strategy1/synthetic_continuous.py`
- `sql/strategy1/qa/qa_continuous_backtest_outputs.sql`
- `tests/strategy1/test_synthetic_continuous.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1/test_synthetic_continuous.py tests/strategy1/test_strategy1_catalog.py tests/strategy1/test_sql_render.py`：25 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.sql_runner --step=qa_continuous_backtest_outputs --output-dataset-role=research --params-json-b64=<official continuous QA params> --dry-run`：BigQuery dry-run 通过。
- `git diff --check`：通过。

### 阻塞项

- 需合并 hotfix 后再继续 official synthetic merge / continuous ledger。

### 下一步建议

- 提交并合并 `codex/synthetic-continuous-partition-filter`。
- 从最新 main 以 `--force-replace` 重跑 official synthetic merge。
- 跑 single continuous backtest，再执行 `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_03 synthetic continuous implementation

### 已完成工作

- 新增 package entrypoint `quant_ashare.strategy1.synthetic_continuous`，按 manifest 合并逐年 refit prediction slice，生成 synthetic selected registry 行和统一 `model_id` / `run_id` 的 prediction stream；默认只允许写 `ashare_research`，ADS 发布仍走 promotion。
- 新增 `sql/strategy1/qa/qa_continuous_backtest_outputs.sql` 并登记 catalog，覆盖 synthetic manifest hash、year slice 溯源、source/target prediction 行数、valid 段排除、交易日历覆盖、continuous summary / NAV / position / trade / ledger state 不变式。
- 更新 `docs/策略1CloudRun训练回测运行手册.md`，补 official synthetic merge、continuous backtest skip flags 和外接 QA 执行口径。
- 扩展 package entrypoint / catalog / SQL render / package boundary 测试，锁住新入口和 QA step。
- PR #166 合并后已从 `main@7b2bd67` 构建部署 hotfix 镜像 `sha256:e379fdccb49281ec628f389de261929d37e60906b51538132b350314ba8db9da`，五个 jobs 读回确认新 digest；`strategy1-train-predict-job` 资源已更新为 `8 CPU / 32Gi`。
- 使用 hotfix plan 重跑 2024/2025/2026 refit 成功：`strategy1-train-predict-job-5s49j`（约 7m20s）、`strategy1-train-predict-job-mx272`（约 9m50s）、`strategy1-train-predict-job-d6g52`（约 10m10s）。六年 refit registry 均为 1 行 selected，prediction 覆盖各年窗口。
- 六年 `qa_refit_register_predict_outputs` 均通过，job ids：`c6bcbf46-ec47-4917-a0a4-e67fbc467997`、`4f75fb48-52ce-4f1b-a270-e555b1358e3e`、`e90a2a1e-0802-4013-9356-e0544304e21d`、`4216cc23-3b09-4001-9291-d93380c44d40`、`04e923a0-e59c-4bfa-a333-2a6a806213e7`、`4e9d241f-7cf3-4def-bee0-0077f6b44d41`。

### 重要上下文

- `PRD_20260611_02` 的 final refit 执行与 QA 已完成；2021-2026 official 评价的剩余硬门是 PRD_03 synthetic continuous merge + single continuous ledger。
- `qa_continuous_backtest_outputs` 是 synthetic run 专用 QA；`10` / `12` / `20` 默认 QA/诊断不适用于无 training panel / 无真实 model artifact 的 synthetic run。continuous backtest 必须用 `--skip-diagnosis --skip-tail-risk --skip-qa`，再外接 `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs`。
- 主工作树仍有 unrelated `scripts/strategy1_cloudrun/bq_io.py` 本地脏改，不属于本 PRD_03 分支，后续构建镜像必须继续使用干净 worktree。

### 改动文件

- `src/quant_ashare/strategy1/synthetic_continuous.py`
- `sql/strategy1/qa/qa_continuous_backtest_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_synthetic_continuous.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：115 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `npx --yes @dataform/cli compile dataform`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- `python3 -m quant_ashare.strategy1.sql_runner --step=qa_continuous_backtest_outputs --output-dataset-role=research --dry-run`：BigQuery dry-run 通过。

### 阻塞项

- 无代码阻塞；official continuous ledger 尚未执行，需先合并 PRD_03 code PR。

### 下一步建议

- 提交 PRD_03 代码 PR，review / merge。
- 从合并后的 main 生成 official manifest，执行 `quant_ashare.strategy1.synthetic_continuous --require-source-refit` 写 synthetic run。
- 用 `strategy1-backtest-report-job` 跑 official continuous backtest（skip diagnosis/tail-risk/default QA），再执行 `qa_continuous_backtest_outputs` 与 `qa_lot_aware_ledger_outputs`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_02 deployment and refit hotfix

### 已完成工作

- 合并 PR #165 到 `main`，merge commit `ebb6dbf`。
- 从 `main@ebb6dbf` 构建固定 tag 镜像 `strategy1-cloudrun-runner:final-refit-main-ebb6dbf-20260611-01`，Cloud Build `8dcd4d62-a61d-459a-aeb8-86fc69a76313` succeeded，digest `sha256:fc94a02d388e0a988dac56366ea0dcba80e65c15dea10efc93ef38e11778b757`。
- 五个正式 Strategy1 jobs 已更新到该 digest；读回确认 package args、SA、maxRetries、资源和 fanout `taskCount=40 / parallelism=20` 保持预期。
- Boot smoke：`strategy1-train-predict-job-nmnkn`、`strategy1-prepare-matrix-job-bhpwm`、`strategy1-train-candidate-fanout-job-rrz6h`、`strategy1-select-register-predict-job-vfkzx`、`strategy1-backtest-report-job-ncn69`、`strategy1-train-predict-job-2kk7c`（`refit_register_predict --help` override）全部 Completed=True，Cloud Logging 均匹配到 `usage:`。
- 生成 `/tmp/strategy1_annual_refit_plan_v20260610_02.json` 并做 BigQuery preflight；六年 source selected registry / panel / target empty checks 通过。
- 启动 2021-2026 refit：2021、2022、2023 成功；2024 因 panel min date 晚于 resolved start 失败；2025、2026 因 train-predict job 16Gi memory limit 失败。
- 新建 hotfix worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-final-refit-hotfix`，分支 `codex/strategy1-final-refit-hotfix`，修复 2024+ 暴露的问题：2019 final-refit start override 为 `2019-04-03`，scheduler/runbook refit resource token 改为 `8 CPU / 32Gi`。

### 重要上下文

- 2021-2023 refit outputs 已实际写入 research；不要用 `--force-replace` 重跑它们，除非 owner 明确要求。
- 2024 失败发生在 coverage guard 之前，没有写出 refit registry/prediction；2025/2026 因内存限制失败，也需在重跑前复核目标 refit rows。
- Hotfix 合并后必须重建镜像，并把至少 `strategy1-train-predict-job` 更新到 `8 CPU / 32Gi` 后再重跑 2024-2026。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`

### 测试 / 验证

- Hotfix focused pytest：`tests/strategy1_cloudrun/test_dataset_role_routing.py::test_annual_year_plan_continuous_contract_uses_refit_run_id` 与 `tests/strategy1/test_annual_pipeline_scheduler.py::test_scheduler_plan_select_depends_on_all_candidates_and_cross_year_is_independent` 通过。
- Hotfix 2024 annual dry-run 确认 `final_refit.train_start='2019-04-03'`。
- 完整验证待 hotfix 提交前执行。

### 阻塞项

- 无代码阻塞；需完成 hotfix PR / merge / redeploy 后才能重跑 2024-2026。

### 下一步建议

- 完成 hotfix 全量验证、提交 PR、合并并部署新镜像。
- 更新 `strategy1-train-predict-job` 至 `8 CPU / 32Gi` 后重跑 2024、2025、2026 refit，并执行 `qa_refit_register_predict_outputs`。
- PRD_03 synthetic continuous merge / official continuous ledger 仍待实现，不能拼接年度 NAV。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_02 annual rolling final refit implementation

### 已完成工作

- 新增 package entrypoint `src/quant_ashare/strategy1/refit_register_predict.py`，实现年度滚动 selected candidate final refit：读 selection registry、读 `source_panel_run_id` 面板、重新 fit preprocessor、训练单模型、写 refit registry / prediction / artifact。
- 扩展 `train_predict.write_registry` 的 `model_params_json` lineage 白名单，写出 `source_panel_run_id`、`refit`、`refit_train_start/end`、`preprocess_fit_start/end`。
- 新增 `sql/strategy1/qa/qa_refit_register_predict_outputs.sql` 并登记 `configs/strategy1/active_step_catalog.yml`，覆盖 refit 硬门 QA。
- 更新 `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`：每年 plan 插入 `cloudrun_refit_register_predict`，root / yearly continuous metadata 指向 refit prediction run，年度 diagnostic backtest 指向 `__refit01` backtest。
- 更新 `quant_ashare.strategy1.annual_pipeline_scheduler`：新增 `refit` stage，continuous 依赖改为 refit runs。
- 更新 runbook 与测试，覆盖 package entrypoint、annual command plan、scheduler DAG 和 catalog/package boundary。

### 重要上下文

- 本轮只完成代码侧实现，不部署镜像、不执行 Cloud Run、不写 BigQuery research/ADS 产物；六年 refit 重跑仍待合并后用新镜像执行。
- refit 当前复用现有 `strategy1-train-predict-job`，资源 token 记录为 `4 CPU / 16Gi`；这是比 PRD 建议 `2 CPU / 8Gi` 更保守的现有 job envelope，不新增 job spec。
- 年度 diagnostic backtest 仍只作 diagnostic，正式结果必须等 PRD_03 synthetic continuous merge + single continuous ledger。

### 改动文件

- `src/quant_ashare/strategy1/refit_register_predict.py`
- `src/quant_ashare/strategy1/train_predict.py`
- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `scripts/strategy1_cloudrun/orchestrate_annual_rolling_selection.py`
- `sql/strategy1/qa/qa_refit_register_predict_outputs.sql`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1/test_cloudrun_package_entrypoints.py`
- `tests/strategy1/test_package_boundaries.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：108 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/strategy1/qa/qa_refit_register_predict_outputs.sql`：通过。
- annual orchestrator / scheduler dry-run 复核：plan 顺序包含 `cloudrun_refit_register_predict`，scheduler `continuous_ledger` 依赖 `refit:*`。

### 阻塞项

- 无代码侧阻塞；上线前仍需 PR 合并后重建 Strategy1 runner 镜像。

### 下一步建议

- 合并 PRD_02 代码 PR 后，重建并部署五个 Strategy1 runner jobs 镜像，至少做 refit entrypoint boot smoke。
- 继续实现 PRD_03 synthetic continuous merge / QA；PRD_02 refit 六年重跑完成后再跑正式 continuous ledger。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - PRD_04 research summary identity implementation and live backfill

### 已完成工作

- 合并 PR #162 到 `main`，并确认 `PRD_20260611_02/03/04` 三个文件已在 `origin/main@ce795e5`。
- 清理已合并的旧 PRD worktree `/Users/fisher/Desktop/git/worktrees/quant-ashare-refit-prds`，删除本地和远端 `claude/prd-refit-continuous-summary` 分支。
- 新建工作树 `/Users/fisher/Desktop/git/worktrees/quant-ashare-prd04-summary-fix`，分支 `codex/prd04-research-summary-fix`。
- PR #163 已自审并合并到 `main`，merge commit `f0ba555`。
- 新增 ADS additive migration `sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`，为 `ads_backtest_performance_summary` 补 `run_id STRING` 与 `created_date DATE`。
- 修复 `sql/strategy1/reporting/build_metrics_and_report_inputs.sql`：summary INSERT 列清单与 SELECT 显式写入 `run_id=p_run_id`、`created_date=CURRENT_DATE()`。
- 修复 `sql/strategy1/qa/qa_runner_outputs.sql`：新增 summary row 的 `run_id=p_run_id` 与 `created_date IS NOT NULL` 断言。
- 修复 `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`：ADS summary required columns 增加 `run_id` / `created_date`，失败信息指向新 migration。
- 新增 `tests/strategy1/test_backtest_summary_identity_contract.py`，防止上述契约漂移。
- 已执行 live ADS migration，并复跑 `qa_cloudrun_schema_readiness` 通过。
- 已回填 6 条 annual rolling research summary 行：`run_id=metrics_json.prediction_run_id`，`created_date=DATE(created_at)`，affected rows=6。

### 重要上下文

- catalog 的 `backtest_summary.partition_columns=[created_date]` 继续代表 research 表语义；本轮不把 ADS summary 改成分区表，避免扩大 migration 面。
- Phase 1 ADS 写入例外只限 additive migration；普通 runner / 后续重跑仍必须默认 research-first。
- PRD_04 已不再阻塞后续 refit / continuous，但后续新 summary 行依赖已合并的 `09` 修复和新镜像部署；PRD_02/03 实现合并后仍需重建 Strategy1 runner 镜像。

### 改动文件

- `sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`
- `sql/strategy1/reporting/build_metrics_and_report_inputs.sql`
- `sql/strategy1/qa/qa_runner_outputs.sql`
- `sql/strategy1/qa/qa_cloudrun_schema_readiness.sql`
- `tests/strategy1/test_backtest_summary_identity_contract.py`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests`：105 passed。
- `python3 scripts/dataform/generate_sqlx_from_sql.py --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `bq query --dry_run --use_legacy_sql=false --location=asia-east2 < sql/ads/04_alter_strategy1_backtest_summary_identity_columns.sql`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- Live migration：两条 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 均完成。
- Live readiness：`qa_cloudrun_schema_readiness` 4 条 assertion 全部 successful。
- Live backfill：annual target rows=6，UPDATE affected rows=6；复核 `null_run_id=0`、`null_created_date=0`、`run_id_mismatch=0`、`created_date_mismatch=0`，`created_date=2026-06-10` 过滤查到 6 行；time-travel hash 对比确认排除 `run_id`/`created_date` 后非目标字段无变化。

### 阻塞项

- 无。

### 下一步建议

- 进入 PRD_02 final refit 与 PRD_03 synthetic continuous 实现；两者可按任务要求分独立 PR 推进。
- 任何重跑前仍需确认五个 Strategy1 jobs 镜像包含最新 main 代码；PRD_02/03 合并后必须重建并部署 runner 镜像。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-11，Claude Fable 5）
> - 分支 `claude/prd-refit-continuous-summary` 新增三个 PRD，收口 2021-2026 首轮年度滚动实跑暴露的三类问题：`PRD_20260611_02`（final refit 方法论修正）、`PRD_20260611_03`（synthetic continuous prediction + 正式 continuous ledger）、`PRD_20260611_04`（research summary `created_date`/`run_id` 落库修复，简短）。
> - 关键依赖关系已写入 PRD：04 的修复必须先于任何重跑；02 与 03 的代码实现可并行（03 的 merge 输入参数化为 manifest，彩排用 pre-refit 预测），只有 03 的正式执行依赖 02 的六年 refit 重跑。
> - 04 的根因已实证：`09` SQL summary INSERT 列清单不含 `run_id`/`created_date`（ADS 表本无这两列，research 表是 D0 新增），research 渲染只重写表名不重写列清单 → 未列出且无 DEFAULT 的列写 NULL。
> - 本轮 docs/记忆-only：不改代码、不执行 BigQuery / Cloud Run。当前 6 年年度结果（含 2025 +53.32%）仍只是 diagnostic，final refit 修正前不得解读指标。
> - PR #162 review 三条 follow-up 已全部采纳修正：①（实证确认 `prepare_matrix` 在 selection train 上 fit preprocessor、matrix 冻结 transformed arrays）PRD_02 复用层级从 matrix 改为 panel，refit 必须重新 fit preprocessor，新增 preprocessing 契约与 QA；② PRD_03 新增 synthetic registry 契约（单 selected synthetic model、prediction model_id 统一改写、逐年溯源入 manifest + `year_model_map`）与专用 `qa_continuous_backtest_outputs` QA 套件，保住下游"每 run 单 selected"不变式；③ PRD_04 扩展 `qa_cloudrun_schema_readiness` 覆盖 ADS summary 新增两列，preflight 拦截漏跑 migration。

Model: Claude Fable 5

## 2026-06-11 Claude Fable 5 - 年度滚动 refit / continuous / summary 三 PRD

### 已完成工作

- 新增 `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`：refit 窗口口径（resolved plan `final_refit` 块为权威）、初稿复用 BigQuery panel / 重新 fit preprocessor / 不消费冻结 matrix transformed arrays、`refit_register_predict` 步骤、独立 refit run_id 的 registry 溯源契约、QA 硬门（训练窗口逐年断言）。注：该初稿 panel 复用口径已被 2026-06-11 coverage revision 替代，当前权威方案为 dedicated refit panel + effective coverage floor。
- 新增 `docs/prd/PRD_20260611_03_策略1SyntheticContinuous正式回测.md`：manifest 参数化 merge（彩排/正式同代码）、逐年 test 窗口切片排除 valid 段、重叠/缺口/行数/溯源 QA、official continuous ledger 口径、rehearsal 与 official 的强制区分。
- 新增 `docs/prd/PRD_20260611_04_ResearchSummary落库修复.md`（简短）：根因实证、ADS additive 补列 + `09` 列清单修复 + 6 行回填（需 owner 批准）+ `qa_runner_outputs` NOT NULL 断言。
- 同步 `IMPLEMENTATION_STATUS.md`、`AGENT_HANDOFF.md`、`TODO.md`。

### 重要上下文

- 实跑暴露的其余问题不另开 PRD：`gcloud --wait` 误报与控制面滞后是 `PRD_20260611_01` §8.1 既定 Phase 2 要求（本次为实证）；慢候选长尾归 scheduler PRD P1；registry 11 行需筛 `status='selected'` 拟作为约定写入 KNOWN_CONSTRAINTS（随实现 PR 落，本轮不动约束文件）。
- 执行顺序：04 修复 PR → 02/03 并行实现（03 彩排可先行）→ 02 六年 refit 重跑 → 03 正式 merge + continuous ledger。

### 改动文件

- `docs/prd/PRD_20260611_02_策略1年度滚动FinalRefit.md`
- `docs/prd/PRD_20260611_03_策略1SyntheticContinuous正式回测.md`
- `docs/prd/PRD_20260611_04_ResearchSummary落库修复.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档与记忆更新；未运行 pytest / BigQuery / Cloud Run。`git diff --check` 通过。

### 阻塞项

- 无。三个 PRD 均待 owner review。

### 下一步建议

- owner review 三个 PRD 后，先实现 `PRD_20260611_04` 的修复 PR（成本最低且阻塞重跑）。
- `PRD_20260611_03` 的 merge/QA 实现与彩排可与 `PRD_20260611_02` 并行启动。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

> 当前交接补充（2026-06-11，GPT-5 Codex）
> - PRD 分支实现收口中：实现工作树 `/Users/fisher/Desktop/git/quant-ashare-annual-pipeline-impl` 从 PRD 分支派生，最终按 owner 要求 fast-forward 回 `codex/prd-annual-rolling-pipeline-scheduler`。
> - 新增 package entrypoint `quant_ashare.strategy1.annual_pipeline_scheduler`，实现年度滚动 pipeline scheduler Phase 1 dry-run；只输出 DAG / lock / state / resource plan，不执行 Cloud Run / BigQuery / GCS 写入。
> - PR #161 review follow-up 已补：dry-run 输出 `simulation_model=synchronous_waves`，峰值标记为 reference 而非 live capacity ceiling；fanout 计数声明为 candidate-year proxy；`--no-tail-fill-single-task` 的 deferred batch 不再误记 succeeded。
> - 新增测试覆盖年度 DAG、scheduler lock ownership、candidate 饱和阻止 prepare、GCS state generation mismatch、deferred batch 和 CLI dry-run JSON；catalog caller / package boundary / runbook 已同步。
> - 后续建议：PR #161 合并后进入 Phase 2 candidate-only live smoke，先用 2 年 * 2-3 candidate unit 验证真实状态恢复、artifact skip 和 Cloud Run execution 粒度 fanout 统计。

Model: GPT-5 Codex

## 2026-06-11 GPT-5 Codex - Annual pipeline scheduler Phase 1 dry-run

### 已完成工作

- 新增 `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`，实现 PRD Phase 1 dry-run package entrypoint。
- Scheduler 复用年度 rolling experiment/window 生成逻辑，输出 2021-2026 跨年度 DAG；本年 `select` 强依赖本年 11/11 candidate，下一年 `panel` / `matrix` 不依赖上一年 `select`。
- Dry-run 输出 scheduler-level GCS generation-guarded lease lock、GCS state generation-conditioned write 模型、stage token 表和资源模拟。
- 资源模型明确 candidate `2 CPU / 8Gi`、prepare `8 CPU / 32Gi`、select/backtest `4 CPU / 16Gi` 共用 `40 CPU / 160Gi` 全局资源池；单测覆盖 20 个 candidate running 时 prepare 不可 admission。
- PR #161 review follow-up：`simulation_model=synchronous_waves` 与 `peak_resource_usage_semantics=synchronous_wave_reference_not_live_capacity_ceiling` 已进入输出；fanout execution accounting 明确 Phase 1 为 candidate-year proxy；deferred candidate batch 不再标记 succeeded。
- 更新 `configs/strategy1/active_step_catalog.yml` caller、`docs/策略1CloudRun训练回测运行手册.md` 和相关测试。

### 重要上下文

- 本轮仍是 Phase 1：不启动 Cloud Run，不读写 BigQuery / GCS，不修改 job spec / IAM；dry-run 资源峰值只用于 admission 自检，不代表 live overlap 的容量上限。
- Owner 已要求不要单独开实现 PR；完成后把实现合回 `codex/prd-annual-rolling-pipeline-scheduler` / PR #161。
- Phase 2 live scheduler 必须按真实 Cloud Run execution 粒度统计 active fanout，而不能沿用 Phase 1 的 candidate-year proxy。

### 改动文件

- `src/quant_ashare/strategy1/annual_pipeline_scheduler.py`
- `tests/strategy1/test_annual_pipeline_scheduler.py`
- `tests/strategy1/test_package_boundaries.py`
- `tests/strategy1_cloudrun/test_dataset_role_routing.py`
- `configs/strategy1/active_step_catalog.yml`
- `docs/策略1CloudRun训练回测运行手册.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- `PYTHONPATH=src python3 -m pytest -q tests/strategy1 tests/strategy1_cloudrun`：98 passed。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.retired_lint`：通过。
- `python3 -m compileall -q src scripts tests`：通过。
- `git diff --check`：通过。
- `PYTHONPATH=src python3 -m quant_ashare.strategy1.annual_pipeline_scheduler --start-year 2021 --end-year 2026 --run-version v20260611_followup --dry-run`：输出 `simulation_model=synchronous_waves`、`fanout_model=candidate_year_proxy`、`deferred_task_count=0`，峰值 `38 CPU / 152Gi / 11 candidate_slots`；该峰值是 synchronous wave reference，不是 live capacity ceiling。

### 阻塞项

- 无。

### 下一步建议

- 推回 PR #161 后 review。
- 合并后再做 Phase 2 candidate-only live smoke，并把 active fanout 计数从 candidate-year proxy 改为 Cloud Run execution 粒度。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-11 GPT-5 Codex - Annual rolling pipeline scheduler PRD

Model: GPT-5 Codex

### 已完成工作

- 在新 worktree `/Users/fisher/Desktop/git/quant-ashare-annual-pipeline-prd`、分支 `codex/prd-annual-rolling-pipeline-scheduler` 中新增年度滚动并发调度 PRD。
- PRD 定义从按年份串行执行升级为跨年份流水线调度：`build_training_panel`、`prepare_matrix` 和 candidate fanout 可跨年度并发；本年 `select_register_predict` 仍必须等本年全部候选成功。
- PRD 固化默认资源上限：全局 candidate task 并发 `20`，candidate task `2 CPU / 8Gi`，并把 prepare、select、backtest/report 纳入资源 token 模型。
- PR #161 review follow-up 已补齐两个 Medium 设计缺口：scheduler 必须持有 generation-guarded GCS lease lock 才能提交 execution，且 GCS state JSON 写入必须使用 generation precondition；prepare `8 CPU / 32Gi`、select `4 CPU / 16Gi`、backtest `4 CPU / 16Gi` 与 candidate 共享 `40 CPU / 160Gi` 全局 token 池。
- PRD 定义 scheduler 必须可 dry-run、可恢复、可按 `(year, unit_index)` 跟踪状态，并对 `gcloud --wait` / Cloud Run 控制面超时做 execution / task / GCS artifact 二次确认。
- 同步更新 `TODO.md` 和 `.agent/memory/IMPLEMENTATION_STATUS.md`。

### 重要上下文

- 2026-06-10 年度滚动实跑观察显示，每年候选训练中 `unit_index=6` 明显拖尾；该候选是 `risk_lgbm_prd_attack_lr005_n600_l63_lr005_n600_leaf800_ff07_bf09_l1_1_l2_1`，`n_estimators=600`、`num_threads=1`。
- 不能在本年 unit6 未完成时提前跑本年 select，否则会把 unit6 排除在年度选参之外，破坏实验口径。
- 可以在上一年慢候选仍 running 时启动下一年 training panel、prepare matrix 和候选训练，只要全局资源预算允许。
- Cloud Run `parallelism` 只限制单 execution；年度 pipeline scheduler 必须自己维护全局资源池和 scheduler 实例互斥，不能靠 job spec 防止跨 execution 超配额或重复提交。
- 正式年度滚动结果仍必须来自单一 continuous ledger 或通过 resume-continuous QA 的 segment ledger；年度 fresh backtest 只作 diagnostic。

### 改动文件

- `docs/prd/PRD_20260611_01_策略1年度滚动并发调度.md`
- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

### 测试 / 验证

- 文档只读校验：对照现有年度滚动 PRD、年度执行工程化 PRD、annual rolling orchestrator、`pipeline_control.build_task_fanout_steps`、`annual_rolling_lgbm_regression_v0.yml`。
- 未运行 BigQuery、Cloud Run、Dataform 或 pytest；本轮不改代码。

### 阻塞项

- 无。

### 下一步建议

- 若 owner 确认 PRD，下一步实现 Phase 1：scheduler dry-run，输出跨年度 DAG、资源峰值和预计提交顺序。
- Phase 1 完成后再做 2 年 * 2-3 candidate unit 的 candidate-only live smoke，验证部分 batch、恢复和 artifact skip。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `TODO.md`

## 2026-06-10 GPT-5 Codex - Strategy1 main image deploy after PR #159

### 已完成工作

- 从当前 `main@f30c1716a55995d169955e1a7c4663d39b82a382` 构建正式 Strategy1 runner 镜像。
- 使用一次性 Cloud Build config，只推固定 tag `asia-east2-docker.pkg.dev/data-aquarium/quant-ashare/strategy1-cloudrun-runner:annual-plan-main-f30c171-20260610-01`，未更新 `latest`。
- Cloud Build `4dfba35e-cbaf-4727-9596-137010c9d6ea` succeeded，镜像 digest 为 `sha256:b856f46f56ad5b9a9cd9ac8773e67090f702a06ff8931ca51e1d2e3bb24299d7`。
- 将五个正式 Strategy1 Cloud Run jobs 更新到该 immutable digest：
  - `strategy1-train-predict-job`
  - `strategy1-prepare-matrix-job`
  - `strategy1-train-candidate-fanout-job`
  - `strategy1-select-register-predict-job`
  - `strategy1-backtest-report-job`
- 读回确认五个 jobs 的 command/args 仍为 `python -m quant_ashare.strategy1.*` package entrypoint，SA 仍为 `241358486859-compute@developer.gserviceaccount.com`，`maxRetries=0`，CPU/memory/timeout 保持不变；fanout 仍为 `taskCount=40`、`parallelism=20`。
- 跑通五个正式 jobs 的只读 `--help` boot smoke，并在 Cloud Logging 确认每个 execution 输出 `usage:`。
- 按 owner 要求清理项目记忆：将旧 active `AGENT_HANDOFF.md` 归档到 `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`，当前 handoff 只保留本次部署交接。
- PR #160 review follow-up：把 Strategy1 runner image digest 从长期约束中移除，改为引用 `IMPLEMENTATION_STATUS.md` 最新部署记录。

### 重要上下文

- 本轮只更新五个普通 Strategy1 runner jobs 的 image；没有更新 `strategy1-promote-research-to-ads-job`。
- 本轮没有执行 BigQuery 写入，也没有启动年度滚动真实运行。
- 当前线上五个 Strategy1 jobs 已包含 PR #159 的 annual rolling training panel plan 和 `quant_ashare.strategy1.sql_runner` package CLI。

### 改动文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

### 测试 / 验证

- Cloud Build `4dfba35e-cbaf-4727-9596-137010c9d6ea`：SUCCESS。
- `gcloud run jobs describe` 读回五个 jobs：image 均为 `sha256:b856f46f56ad5b9a9cd9ac8773e67090f702a06ff8931ca51e1d2e3bb24299d7`，args / resources / SA / retries / fanout 并发均保持预期。
- `strategy1-train-predict-job-gwpn7`：Completed=True，Cloud Logging 匹配 `usage: train_predict.py`。
- `strategy1-prepare-matrix-job-rjgzf`：Completed=True，Cloud Logging 匹配 `usage: prepare_matrix.py`。
- `strategy1-train-candidate-fanout-job-njl4q`：Completed=True，本次 smoke 用 `--tasks=1`，Cloud Logging 匹配 `usage: train_candidate_task.py`。
- `strategy1-select-register-predict-job-njmxd`：Completed=True，Cloud Logging 匹配 `usage: select_register_predict.py`。
- `strategy1-backtest-report-job-jj7ng`：Completed=True，Cloud Logging 匹配 `usage: backtest_report.py`。
- `git diff --check`：通过。

### 阻塞项

- 无。

### 下一步建议

- 执行完整 `2021-2026` 年度滚动选参实验。
- 正式结果必须来自单一 continuous ledger，或经过 resume-continuous QA 的 segment ledger；不要拼接年度 fresh-run NAV。
- 若年度滚动结果接近可接受，再按 promotion runbook 先 review-only 后 owner-approved `--execute`。

### 已更新记忆文件

- `.agent/memory/IMPLEMENTATION_STATUS.md`
- `.agent/memory/KNOWN_CONSTRAINTS.md`
- `.agent/memory/AGENT_HANDOFF.md`
- `.agent/memory/archive/AGENT_HANDOFF_2026-06.md`
- `TODO.md`

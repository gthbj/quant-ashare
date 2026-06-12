> 文档维护：GPT-5.5（最近更新 2026-06-12）

# Dividend ODS 补采与 CA-on Resume 补跑

## 结论

- 已补采 `ods_tushare_dividend` 缺口开市日 `2026-05-28..2026-06-12`，只涉及 `dividend` endpoint。
- 已重建 `dwd_stock_dividend_event`、`qa_stock_dividend_event_hfq_mismatch` 与 `v_dwd_stock_dividend_event_ledger_consumable`；QA-CA-EVENT-1..6 全部通过。
- 已从 parent `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01` 的 `2026-05-27` state resume 补跑 research-only child `bt_s1_dividend_backfill_resume_20260528_20260609_v20260612_01`。
- 差异可完全归因于两条新增现金分红事件：净现金影响 `+68.4` CNY，股数差异 `0`，position 差异 `0`。非 CA 差异只有两条未成交 `BUY_SKIPPED_BELOW_LOT` planned_shares 尾差，filled/cash/turnover/fee/tax/slippage 均为 `0`。
- parent NAV `2021-01-04..2026-05-27` + child NAV `2026-05-28..2026-06-09` 拼接后，v3 contract 口径 CAGR `15.3578%`、Sharpe `0.668540`、Calmar `0.410309`、MaxDD `-37.4298%`。
- child 只写 `ashare_research`；ADS nav/trade/position/state/summary 反查均 `0` 行，`research_promotion_manifest` 为 `0` 行。未 promotion，未标 accepted。

## 采集与调度边界

- 新增独立 manifest `configs/ingestion/ods_dividend_backfill_v0.yml`，未加入 `ods_current_scope_v0.yml`。
- `current_scope` alias 改为显式 endpoint group 列表：`market_eod`、`index_eod`、`dim_snapshot`、`finance_recent`，不包含 `dividend_backfill`。
- 新增 `dividend_backfill` endpoint group，只包含 `dividend`；canonical GCS prefix 为 `api=dividend/endpoint=dividend/partition_date=<YYYYMMDD>/`。
- `business_date` 请求参数对 `dividend` 使用 `ex_date`，partition_date 也按 `ex_date`。

本改动不改变每日调度行为，不改变 `corporate_actions=none_v1` 默认。

## ODS 补采执行

Cloud Build:

- build id: `8da0a512-e718-4da0-a6bf-dc3924338a67`
- image: `asia-east2-docker.pkg.dev/data-aquarium/ashare/ingestion:latest`
- digest: `sha256:35acbc363408d05dd758d70ba5f293e8b0d333a000c6dfe8e8143ddadd0b8bba`

Cloud Run dry-run:

- execution: `ashare-ingest-current-scope-7dc52`
- plan: `dividend_backfill dividend partition_endpoint=dividend partition_date=20260528`

实际补采开市日与 execution：

| business_date | execution |
|---|---|
| 2026-05-28 | `ashare-ingest-current-scope-g6ftc` |
| 2026-05-29 | `ashare-ingest-current-scope-4vbzx` |
| 2026-06-01 | `ashare-ingest-current-scope-nz2kd` |
| 2026-06-02 | `ashare-ingest-current-scope-7fjxs` |
| 2026-06-03 | `ashare-ingest-current-scope-7t5sx` |
| 2026-06-04 | `ashare-ingest-current-scope-p2n9b` |
| 2026-06-05 | `ashare-ingest-current-scope-8lgwx` |
| 2026-06-08 | `ashare-ingest-current-scope-wc6rf` |
| 2026-06-09 | `ashare-ingest-current-scope-6wrql` |
| 2026-06-10 | `ashare-ingest-current-scope-bbtfp` |
| 2026-06-11 | `ashare-ingest-current-scope-4szn8` |
| 2026-06-12 | `ashare-ingest-current-scope-z5slk` |

ODS 校验：

| partition_date | rows |
|---|---:|
| 2026-05-28 | 113 |
| 2026-05-29 | 178 |
| 2026-06-01 | 83 |
| 2026-06-02 | 76 |
| 2026-06-03 | 89 |
| 2026-06-04 | 101 |
| 2026-06-05 | 108 |
| 2026-06-08 | 61 |
| 2026-06-09 | 96 |
| 2026-06-10 | 126 |
| 2026-06-11 | 90 |
| 2026-06-12 | 94 |

合计 `1215` 行，`ex_date_match_count == row_count`，`null_ex_date_count=0`。同期量级：2024=`1182`，2025=`1184`，2026=`1215`。`ashare_meta.ingestion_run` 与 `ingestion_partition_status` 均落 `12` 条 success，未复现 0 行 meta 事故。

## 事件链路重建

- DWD rebuild job: `manual_dividend_dwd12_rebuild_20260612_01`
- QA rebuild job: `manual_dividend_ca_event_qa_20260612_01`
- QA-CA-EVENT-1..6: passed

事件覆盖：

| window | canonical_events | source_rows | max_source_partition |
|---|---:|---:|---|
| resume gap `2026-05-28..2026-06-09` | 902 | 905 | 20260609 |
| backfilled to `2026-06-12` | 1210 | 1213 | 20260612 |
| all 2010+ | 47641 | 47683 | 20260612 |

Mismatch 披露：

| scope | type | classification | rows |
|---|---|---|---:|
| all / Phase C baseline window | event_to_factor | data_anomaly | 1106 |
| all / Phase C baseline window | event_to_factor | special_dividend | 1 |
| baseline window `2021-01-04..2026-06-09` | factor_to_event | same_day_orphan_corporate_action | 77 |
| all 2010+ | factor_to_event | same_day_orphan_corporate_action | 78 |

Ledger consumable view 在 `2026-05-28..2026-06-09` 有 `902` 个 canonical events / `905` 个 source rows，`unclassified_rows=0`。

## Resume Child

Parent:

- backtest: `bt_s1_annual_roll_continuous_true5y_2021_2026_n20_w075_v20260611_01_ca01`
- prediction run: `s1_annual_roll_synth_continuous_true5y_2021_2026_n20_w075_v20260611_01`
- state as of: `2026-05-27`
- next SSE open: `2026-05-28`
- rebalance anchor: `2021-01-04`
- CA params: `corporate_actions=cash_div_and_split_v1` / `dividend_tax_mode=flat_10pct`

Child:

- run: `s1_dividend_backfill_resume_20260528_20260609_v20260612_01`
- backtest: `bt_s1_dividend_backfill_resume_20260528_20260609_v20260612_01`
- Cloud Run execution: `strategy1-backtest-report-job-tjn4j`
- BigQuery step jobs: candidates `93fb9409-af87-4f68-b4bf-eace9fc0063f`、targets `94114f2b-c405-4469-b3a7-143708f43bce`、orders `21afb95f-301b-4707-a356-6568f3c02224`、metrics `b9985629-8eb9-40a3-ab36-28a1219c8c69`

Research 输出行数：

| table | rows | min_date | max_date |
|---|---:|---|---|
| candidate | 2477 | 2026-06-05 | 2026-06-05 |
| target | 20 | 2026-06-05 | 2026-06-05 |
| orders | 20 | 2026-06-05 | 2026-06-05 |
| trade | 39 | 2026-05-29 | 2026-06-08 |
| position | 171 | 2026-05-28 | 2026-06-09 |
| nav | 9 | 2026-05-28 | 2026-06-09 |
| state | 9 | 2026-05-28 | 2026-06-09 |
| summary | 1 | N/A | N/A |

## QA

| check | status | job id / note |
|---|---|---|
| `qa_lot_aware_ledger_outputs` | passed | `b697f4dc-1eaf-4eff-9df1-23e04fb809ac` |
| `qa_corporate_action_ledger_outputs` | passed | `beefe3d8-0022-4aa9-a224-37eb82931760` |
| `qa_cloudrun_ledger_resume_outputs` structure subset | passed | `bqjob_r8fe2168bb9d0164_0000019ebc5bb4d6_1`，8 个 metadata / coverage ASSERT passed |
| full `qa_cloudrun_ledger_resume_outputs` | expected failed | `a5df51f7-14e1-4fcb-bcf5-444ba8453be3` failed at `Full and resume NAV metrics differ` |

说明：当前 catalog SQL `qa_cloudrun_ledger_resume_outputs` 后半段仍包含 parent/child 等值断言。该断言在本任务语义下预期失败，因为差异正是新增 CA 事件的修正效果；本次不把它作为验收门，改用下方差异归因。

## 差异归因

逐日 NAV delta：

| trade_date | parent_nav | child_nav | nav_delta | cash_delta_cny | net_value_delta_cny |
|---|---:|---:|---:|---:|---:|
| 2026-05-28 | 2.218536153330 | 2.218536153330 | 0.000000 | 0.0 | 0.0 |
| 2026-05-29 | 2.159376153330 | 2.159736153330 | 0.000360 | 36.0 | 36.0 |
| 2026-06-01 | 2.201836153330 | 2.202196153330 | 0.000360 | 36.0 | 36.0 |
| 2026-06-02 | 2.166236153330 | 2.166920153330 | 0.000684 | 68.4 | 68.4 |
| 2026-06-03 | 2.152116153330 | 2.152800153330 | 0.000684 | 68.4 | 68.4 |
| 2026-06-04 | 2.114746153330 | 2.115430153330 | 0.000684 | 68.4 | 68.4 |
| 2026-06-05 | 2.130236153330 | 2.130920153330 | 0.000684 | 68.4 | 68.4 |
| 2026-06-08 | 2.070471485377 | 2.071155485377 | 0.000684 | 68.4 | 68.4 |
| 2026-06-09 | 2.104471485377 | 2.105155485377 | 0.000684 | 68.4 | 68.4 |

新增 CA 行与事件金额对账：

| ex_date | sec_code | record_date | record_shares | pretax_cash_per_share | expected_turnover | expected_tax | expected_cash_effect | actual_turnover | actual_tax | actual_cash_effect |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-05-29 | 002756.SZ | 2026-05-28 | 100 | 0.40 | 40.0 | 4.0 | 36.0 | 40.0 | 4.0 | 36.0 |
| 2026-06-02 | 001314.SZ | 2026-06-01 | 200 | 0.18 | 36.0 | 3.6 | 32.4 | 36.0 | 3.6 | 32.4 |

汇总：

| group | diff_rows | planned_shares_delta | filled_shares_delta | turnover_delta | tax_delta | cash_effect_delta |
|---|---:|---:|---:|---:|---:|---:|
| corporate_action | 2 | 300.0 | 0.0 | 76.0 | 7.6 | 68.4 |
| non_corporate_action | 2 | 0.06950774 | 0.0 | 0.0 | 0.0 | 0.0 |

Position diff 查询返回 `[]`：无股数或市值差异。非 CA 两条差异是 `BUY_SKIPPED_BELOW_LOT` planned_shares 尾差，未成交且无现金影响。

## 拼接指标

拼接序列：parent NAV `2021-01-04..2026-05-27` + child NAV `2026-05-28..2026-06-09`，共 `1314` 个交易日。

| metric | baseline recomputed | stitched | delta |
|---|---:|---:|---:|
| CAGR | 0.153505947666 | 0.153577894499 | +0.000071946833 |
| contract Sharpe | 0.668208428226 | 0.668539787795 | +0.000331359569 |
| Calmar | 0.410117087382 | 0.410309305509 | +0.000192218127 |
| MaxDD | -0.374297858804 | -0.374297858804 | 0.0 |

对 owner 给出的原 baseline 数字（CAGR `15.35%` / Sharpe `0.6682` / Calmar `0.4101`）的修正建议应在 PR body 交 owner / Claude 决策；本次不改 `DECISION-20260612-03` 文本。

## Research-only 反查

| check | rows |
|---|---:|
| ADS nav | 0 |
| ADS trade | 0 |
| ADS position | 0 |
| ADS state | 0 |
| ADS summary | 0 |
| research promotion manifest | 0 |

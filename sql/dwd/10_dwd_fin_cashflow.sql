-- 文档维护：Claude Opus 4.8（最近更新 2026-06-02）
-- BigQuery Standard SQL
-- 现金流量表 DWD（PIT 版本事实表）：从 20170101 报告期起读取，支撑 2019+ PIT。
-- 可见日 ann_date_eff = COALESCE(f_ann_date, ann_date)；按 OQ-003 保留 report_type 并派生口径字段。
-- 实测：当前 ODS ods_tushare_cashflow 仅含 report_type='1'（合并报表）。
-- 金额单位为元（Tushare 原始口径），现金流量表为累计（YTD）口径。

DECLARE fin_start_period STRING DEFAULT '20170101';

CREATE OR REPLACE TABLE `data-aquarium.ashare_dwd.dwd_fin_cashflow`
PARTITION BY DATE_TRUNC(ann_date_eff, MONTH)
CLUSTER BY sec_code
OPTIONS (
  description = '现金流量表 DWD（PIT 版本事实表），来自 Tushare cashflow，按公告生效月分区。保留源 report_type 并派生 report_caliber/is_default_report_caliber；默认消费口径 report_type=1（合并报表）。金额单位元，accumulated/YTD 口径。'
) AS
WITH base AS (
  SELECT
    ts_code AS sec_code,
    COALESCE(SAFE.PARSE_DATE('%Y%m%d', f_ann_date), SAFE.PARSE_DATE('%Y%m%d', ann_date)) AS ann_date_eff,
    SAFE.PARSE_DATE('%Y%m%d', end_date) AS report_period,
    ann_date,
    f_ann_date,
    end_date,
    report_type,
    comp_type,
    update_flag,
    SAFE_CAST(net_profit AS FLOAT64) AS net_profit,
    SAFE_CAST(c_fr_sale_sg AS FLOAT64) AS c_fr_sale_sg,
    SAFE_CAST(c_inf_fr_operate_a AS FLOAT64) AS c_inf_fr_operate_a,
    SAFE_CAST(c_paid_goods_s AS FLOAT64) AS c_paid_goods_s,
    SAFE_CAST(st_cash_out_act AS FLOAT64) AS st_cash_out_act,
    SAFE_CAST(n_cashflow_act AS FLOAT64) AS n_cashflow_act,
    SAFE_CAST(n_cashflow_inv_act AS FLOAT64) AS n_cashflow_inv_act,
    SAFE_CAST(stot_cash_in_fnc_act AS FLOAT64) AS stot_cash_in_fnc_act,
    SAFE_CAST(n_cash_flows_fnc_act AS FLOAT64) AS n_cash_flows_fnc_act,
    SAFE_CAST(free_cashflow AS FLOAT64) AS free_cashflow,
    SAFE_CAST(c_cash_equ_beg_period AS FLOAT64) AS c_cash_equ_beg_period,
    SAFE_CAST(c_cash_equ_end_period AS FLOAT64) AS c_cash_equ_end_period,
    SAFE_CAST(n_incr_cash_cash_equ AS FLOAT64) AS n_incr_cash_cash_equ,
    COALESCE(_source, 'tushare') AS source_system,
    partition_date AS source_partition_date,
    SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_cashflow`
  WHERE endpoint = 'cashflow'
    AND partition_date >= fin_start_period
    AND end_date IS NOT NULL
    AND COALESCE(f_ann_date, ann_date) IS NOT NULL
),
typed AS (
  SELECT
    *,
    CASE
      WHEN report_type IS NULL THEN 'unknown'
      WHEN report_type IN ('1', '2', '3', '4', '5') THEN 'consolidated'
      WHEN report_type IN ('6', '7', '8', '9', '10', '11', '12') THEN 'non_consolidated'
      ELSE 'other'
    END AS report_caliber,
    COALESCE(report_type = '1', FALSE) AS is_default_report_caliber
  FROM base
),
valid_base AS (
  SELECT *
  FROM typed
  WHERE ann_date_eff IS NOT NULL
    AND report_period IS NOT NULL
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY sec_code, report_period, report_type, ann_date_eff, update_flag
    ORDER BY ingested_at DESC, source_partition_date DESC
  ) = 1
),
with_visible_date AS (
  SELECT
    b.*,
    (
      SELECT MIN(c.cal_date)
      FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS c
      WHERE c.exchange = 'SSE'
        AND c.is_open = 1
        AND c.cal_date >= b.ann_date_eff
    ) AS visible_trade_date
  FROM valid_base AS b
)
SELECT *
FROM with_visible_date;

ALTER TABLE `data-aquarium.ashare_dwd.dwd_fin_cashflow`
ALTER COLUMN sec_code SET OPTIONS (description = '证券代码，Tushare ts_code 格式'),
ALTER COLUMN ann_date_eff SET OPTIONS (description = '公告生效日（可见日），COALESCE(f_ann_date, ann_date)，月分区字段'),
ALTER COLUMN report_period SET OPTIONS (description = '报告期，来自 end_date'),
ALTER COLUMN ann_date SET OPTIONS (description = '原始公告日，YYYYMMDD 字符串'),
ALTER COLUMN f_ann_date SET OPTIONS (description = '实际披露/最终公告日，YYYYMMDD 字符串；优先用于 ann_date_eff'),
ALTER COLUMN end_date SET OPTIONS (description = '报告期 YYYYMMDD 字符串原值'),
ALTER COLUMN report_type SET OPTIONS (description = 'Tushare 源报表类型编码，原样保留；1=合并报表（P0 默认消费口径）。实测当前仅 1'),
ALTER COLUMN comp_type SET OPTIONS (description = 'Tushare 公司类型：1 一般工商业 2 银行 3 保险 4 证券 等，决定报表模板'),
ALTER COLUMN report_caliber SET OPTIONS (description = '规范化口径：consolidated/non_consolidated/other/unknown；report_type IS NULL 时为 unknown'),
ALTER COLUMN is_default_report_caliber SET OPTIONS (description = '是否 P0 默认消费口径，等价于 COALESCE(report_type=1, FALSE)'),
ALTER COLUMN update_flag SET OPTIONS (description = 'Tushare 更新标志，同公告时间下优先保留修正版'),
ALTER COLUMN net_profit SET OPTIONS (description = '净利润（现金流量表口径），元，累计/YTD'),
ALTER COLUMN n_cashflow_act SET OPTIONS (description = '经营活动产生的现金流量净额，元，累计/YTD'),
ALTER COLUMN n_cashflow_inv_act SET OPTIONS (description = '投资活动产生的现金流量净额，元，累计/YTD'),
ALTER COLUMN n_cash_flows_fnc_act SET OPTIONS (description = '筹资活动产生的现金流量净额，元，累计/YTD'),
ALTER COLUMN free_cashflow SET OPTIONS (description = '企业自由现金流量，元，累计/YTD'),
ALTER COLUMN c_cash_equ_end_period SET OPTIONS (description = '期末现金及现金等价物余额，元，时点值'),
ALTER COLUMN n_incr_cash_cash_equ SET OPTIONS (description = '现金及现金等价物净增加额，元，累计/YTD'),
ALTER COLUMN visible_trade_date SET OPTIONS (description = '公告生效日之后第一个上交所开市日，用于 PIT as-of join'),
ALTER COLUMN source_system SET OPTIONS (description = '来源系统标识，当前 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 ODS 分区（报告期），YYYYMMDD 字符串'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 ODS 摄入时间');

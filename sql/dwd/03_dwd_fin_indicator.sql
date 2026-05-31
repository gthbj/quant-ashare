-- 文档维护：GPT-5（最近更新 2026-05-31）
-- BigQuery Standard SQL
-- 财务指标 DWD：从 20170101 起读取，支撑 2019+ PIT 和同比/基期计算。
-- fina_indicator 无 f_ann_date，使用 ann_date 作为公告生效日期。

DECLARE fin_start_period STRING DEFAULT '20170101';

CREATE OR REPLACE TABLE `data-aquarium.ashare_dwd.dwd_fin_indicator`
PARTITION BY DATE_TRUNC(ann_date_eff, MONTH)
CLUSTER BY sec_code
OPTIONS (
  description = 'Financial indicator DWD from Tushare fina_indicator, partitioned by announcement month from 2017-01-01'
) AS
WITH base AS (
  SELECT
    ts_code AS sec_code,
    SAFE.PARSE_DATE('%Y%m%d', ann_date) AS ann_date_eff,
    SAFE.PARSE_DATE('%Y%m%d', end_date) AS report_period,
    ann_date,
    end_date,
    update_flag,
    SAFE_CAST(eps AS FLOAT64) AS eps,
    SAFE_CAST(dt_eps AS FLOAT64) AS dt_eps,
    SAFE_CAST(current_ratio AS FLOAT64) AS current_ratio,
    SAFE_CAST(quick_ratio AS FLOAT64) AS quick_ratio,
    SAFE_CAST(cash_ratio AS FLOAT64) AS cash_ratio,
    SAFE_CAST(inv_turn AS FLOAT64) AS inventory_turnover,
    SAFE_CAST(ar_turn AS FLOAT64) AS ar_turnover,
    SAFE_CAST(assets_turn AS FLOAT64) AS assets_turnover,
    SAFE_CAST(netdebt AS FLOAT64) AS net_debt,
    SAFE_CAST(working_capital AS FLOAT64) AS working_capital,
    SAFE_CAST(netprofit_margin AS FLOAT64) AS netprofit_margin,
    SAFE_CAST(grossprofit_margin AS FLOAT64) AS grossprofit_margin,
    SAFE_CAST(roe AS FLOAT64) AS roe,
    SAFE_CAST(roe_dt AS FLOAT64) AS roe_deducted,
    SAFE_CAST(roa AS FLOAT64) AS roa,
    SAFE_CAST(roic AS FLOAT64) AS roic,
    SAFE_CAST(ocf_to_or AS FLOAT64) AS ocf_to_or,
    SAFE_CAST(debt_to_assets AS FLOAT64) AS debt_to_assets,
    SAFE_CAST(assets_to_eqt AS FLOAT64) AS assets_to_equity,
    SAFE_CAST(ocf_to_profit AS FLOAT64) AS ocf_to_profit,
    SAFE_CAST(q_netprofit_margin AS FLOAT64) AS q_netprofit_margin,
    SAFE_CAST(q_gsprofit_margin AS FLOAT64) AS q_grossprofit_margin,
    SAFE_CAST(q_roe AS FLOAT64) AS q_roe,
    SAFE_CAST(q_dt_roe AS FLOAT64) AS q_roe_deducted,
    SAFE_CAST(q_npta AS FLOAT64) AS q_npta,
    SAFE_CAST(basic_eps_yoy AS FLOAT64) AS basic_eps_yoy,
    SAFE_CAST(dt_eps_yoy AS FLOAT64) AS dt_eps_yoy,
    SAFE_CAST(op_yoy AS FLOAT64) AS operating_profit_yoy,
    SAFE_CAST(ebt_yoy AS FLOAT64) AS ebt_yoy,
    SAFE_CAST(netprofit_yoy AS FLOAT64) AS netprofit_yoy,
    SAFE_CAST(tr_yoy AS FLOAT64) AS total_revenue_yoy,
    SAFE_CAST(or_yoy AS FLOAT64) AS operating_revenue_yoy,
    COALESCE(_source, 'tushare') AS source_system,
    partition_date AS source_partition_date,
    SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_fina_indicator`
  WHERE endpoint = 'fina_indicator'
    AND partition_date >= fin_start_period
    AND ann_date IS NOT NULL
    AND end_date IS NOT NULL
),
valid_base AS (
  SELECT *
  FROM base
  WHERE ann_date_eff IS NOT NULL
    AND report_period IS NOT NULL
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

ALTER TABLE `data-aquarium.ashare_dwd.dwd_fin_indicator`
ALTER COLUMN sec_code SET OPTIONS (description = '证券代码，Tushare ts_code 格式'),
ALTER COLUMN ann_date_eff SET OPTIONS (description = '公告生效日期，来自 fina_indicator.ann_date，月分区字段'),
ALTER COLUMN report_period SET OPTIONS (description = '报告期'),
ALTER COLUMN visible_trade_date SET OPTIONS (description = '公告日之后第一个上交所交易日，用于 PIT as-of join'),
ALTER COLUMN update_flag SET OPTIONS (description = 'Tushare 更新标志');

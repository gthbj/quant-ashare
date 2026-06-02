-- 文档维护：Claude Opus 4.8（最近更新 2026-06-02）
-- BigQuery Standard SQL
-- 资产负债表 DWD（PIT 版本事实表）：从 20170101 报告期起读取，支撑 2019+ PIT。
-- 可见日 ann_date_eff = COALESCE(f_ann_date, ann_date)；按 OQ-003 保留 report_type 并派生口径字段。
-- 实测：当前 ODS ods_tushare_balancesheet 仅含 report_type='1'（合并报表）。
-- 金额单位为元（Tushare 原始口径），资产负债表为时点值（period-end snapshot）。

DECLARE fin_start_period STRING DEFAULT '20170101';

CREATE OR REPLACE TABLE `data-aquarium.ashare_dwd.dwd_fin_balancesheet`
PARTITION BY DATE_TRUNC(ann_date_eff, MONTH)
CLUSTER BY sec_code
OPTIONS (
  description = '资产负债表 DWD（PIT 版本事实表），来自 Tushare balancesheet，按公告生效月分区。保留源 report_type 并派生 report_caliber/is_default_report_caliber；默认消费口径 report_type=1（合并报表）。金额单位元，时点值。'
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
    SAFE_CAST(money_cap AS FLOAT64) AS money_cap,
    SAFE_CAST(accounts_receiv AS FLOAT64) AS accounts_receiv,
    SAFE_CAST(inventories AS FLOAT64) AS inventories,
    SAFE_CAST(total_cur_assets AS FLOAT64) AS total_cur_assets,
    SAFE_CAST(fix_assets AS FLOAT64) AS fix_assets,
    SAFE_CAST(intan_assets AS FLOAT64) AS intan_assets,
    SAFE_CAST(r_and_d AS FLOAT64) AS r_and_d,
    SAFE_CAST(goodwill AS FLOAT64) AS goodwill,
    SAFE_CAST(total_nca AS FLOAT64) AS total_nca,
    SAFE_CAST(total_assets AS FLOAT64) AS total_assets,
    SAFE_CAST(st_borr AS FLOAT64) AS st_borr,
    SAFE_CAST(lt_borr AS FLOAT64) AS lt_borr,
    SAFE_CAST(total_cur_liab AS FLOAT64) AS total_cur_liab,
    SAFE_CAST(total_ncl AS FLOAT64) AS total_ncl,
    SAFE_CAST(total_liab AS FLOAT64) AS total_liab,
    SAFE_CAST(minority_int AS FLOAT64) AS minority_int,
    SAFE_CAST(total_hldr_eqy_exc_min_int AS FLOAT64) AS total_hldr_eqy_exc_min_int,
    SAFE_CAST(total_hldr_eqy_inc_min_int AS FLOAT64) AS total_hldr_eqy_inc_min_int,
    SAFE_CAST(total_liab_hldr_eqy AS FLOAT64) AS total_liab_hldr_eqy,
    COALESCE(_source, 'tushare') AS source_system,
    partition_date AS source_partition_date,
    SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_balancesheet`
  WHERE endpoint = 'balancesheet'
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

ALTER TABLE `data-aquarium.ashare_dwd.dwd_fin_balancesheet`
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
ALTER COLUMN money_cap SET OPTIONS (description = '货币资金，元，时点值'),
ALTER COLUMN total_cur_assets SET OPTIONS (description = '流动资产合计，元，时点值'),
ALTER COLUMN total_assets SET OPTIONS (description = '资产总计，元，时点值'),
ALTER COLUMN total_cur_liab SET OPTIONS (description = '流动负债合计，元，时点值'),
ALTER COLUMN total_liab SET OPTIONS (description = '负债合计，元，时点值'),
ALTER COLUMN total_hldr_eqy_exc_min_int SET OPTIONS (description = '归属母公司股东权益合计（不含少数股东权益），元，时点值'),
ALTER COLUMN total_hldr_eqy_inc_min_int SET OPTIONS (description = '股东权益合计（含少数股东权益），元，时点值'),
ALTER COLUMN minority_int SET OPTIONS (description = '少数股东权益，元，时点值'),
ALTER COLUMN goodwill SET OPTIONS (description = '商誉，元，时点值'),
ALTER COLUMN visible_trade_date SET OPTIONS (description = '公告生效日之后第一个上交所开市日，用于 PIT as-of join'),
ALTER COLUMN source_system SET OPTIONS (description = '来源系统标识，当前 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 ODS 分区（报告期），YYYYMMDD 字符串'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 ODS 摄入时间');

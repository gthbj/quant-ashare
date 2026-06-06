-- 文档维护：Claude Opus 4.8（最近更新 2026-06-02）
-- BigQuery Standard SQL
-- 利润表 DWD（PIT 版本事实表）：从 20170101 报告期起读取，支撑 2019+ PIT 和同比/基期。
-- 三大报表有 f_ann_date：可见日 ann_date_eff = COALESCE(f_ann_date, ann_date)（区别于 fina_indicator 仅 ann_date）。
-- 保留源 report_type 并派生 report_caliber / is_default_report_caliber；
-- 版本事实表不按 report_type 预过滤，去重键含 report_type。
-- 实测：当前 ODS ods_tushare_income 仅含 report_type='1'（合并报表）；>'1' 的口径映射为前向兼容。
-- 金额单位为元（Tushare 三大报表原始口径，未做单位换算），每股收益单位为元/股；income 为累计（YTD）口径。

DECLARE fin_start_period STRING DEFAULT '20170101';

CREATE OR REPLACE TABLE `data-aquarium.ashare_dwd.dwd_fin_income`
PARTITION BY DATE_TRUNC(ann_date_eff, MONTH)
CLUSTER BY sec_code
OPTIONS (
  description = '利润表 DWD（PIT 版本事实表），来自 Tushare income，按公告生效月分区。保留每个公告版本与源 report_type 口径并派生 report_caliber/is_default_report_caliber；回测 as-of 用 visible_trade_date，默认消费口径 report_type=1（合并报表）。金额单位元，accumulated/YTD 口径。'
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
    SAFE_CAST(basic_eps AS FLOAT64) AS basic_eps,
    SAFE_CAST(diluted_eps AS FLOAT64) AS diluted_eps,
    SAFE_CAST(total_revenue AS FLOAT64) AS total_revenue,
    SAFE_CAST(revenue AS FLOAT64) AS revenue,
    SAFE_CAST(total_cogs AS FLOAT64) AS total_cogs,
    SAFE_CAST(oper_cost AS FLOAT64) AS oper_cost,
    SAFE_CAST(sell_exp AS FLOAT64) AS sell_exp,
    SAFE_CAST(admin_exp AS FLOAT64) AS admin_exp,
    SAFE_CAST(fin_exp AS FLOAT64) AS fin_exp,
    SAFE_CAST(rd_exp AS FLOAT64) AS rd_exp,
    SAFE_CAST(operate_profit AS FLOAT64) AS operate_profit,
    SAFE_CAST(non_oper_income AS FLOAT64) AS non_oper_income,
    SAFE_CAST(non_oper_exp AS FLOAT64) AS non_oper_exp,
    SAFE_CAST(total_profit AS FLOAT64) AS total_profit,
    SAFE_CAST(income_tax AS FLOAT64) AS income_tax,
    SAFE_CAST(n_income AS FLOAT64) AS n_income,
    SAFE_CAST(n_income_attr_p AS FLOAT64) AS n_income_attr_p,
    SAFE_CAST(minority_gain AS FLOAT64) AS minority_gain,
    SAFE_CAST(ebit AS FLOAT64) AS ebit,
    SAFE_CAST(ebitda AS FLOAT64) AS ebitda,
    COALESCE(_source, 'tushare') AS source_system,
    partition_date AS source_partition_date,
    SAFE_CAST(_ingested_at AS TIMESTAMP) AS ingested_at
  FROM `data-aquarium.ashare_ods.ods_tushare_income`
  WHERE endpoint = 'income'
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

ALTER TABLE `data-aquarium.ashare_dwd.dwd_fin_income`
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
ALTER COLUMN total_revenue SET OPTIONS (description = '营业总收入，元，累计/YTD'),
ALTER COLUMN revenue SET OPTIONS (description = '营业收入，元，累计/YTD'),
ALTER COLUMN operate_profit SET OPTIONS (description = '营业利润，元，累计/YTD'),
ALTER COLUMN total_profit SET OPTIONS (description = '利润总额，元，累计/YTD'),
ALTER COLUMN n_income SET OPTIONS (description = '净利润（含少数股东损益），元，累计/YTD'),
ALTER COLUMN n_income_attr_p SET OPTIONS (description = '归属于母公司股东的净利润，元，累计/YTD'),
ALTER COLUMN basic_eps SET OPTIONS (description = '基本每股收益，元/股'),
ALTER COLUMN ebitda SET OPTIONS (description = '息税折旧摊销前利润，元，累计/YTD'),
ALTER COLUMN visible_trade_date SET OPTIONS (description = '公告生效日之后第一个上交所开市日，用于 PIT as-of join'),
ALTER COLUMN source_system SET OPTIONS (description = '来源系统标识，当前 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 ODS 分区（报告期），YYYYMMDD 字符串'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 ODS 摄入时间');

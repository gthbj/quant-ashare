-- 文档维护：Claude Opus 4.8（最近更新 2026-06-02）
-- BigQuery Standard SQL
-- 财务报表口径 DWD/DWS 落地断言。
-- 覆盖三大报表 income/balancesheet/cashflow 版本事实表 + 默认口径 latest + dws_stock_feature_fin_daily。
-- 全部通过才算财务口径维度落地完成。

DECLARE dws_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dws_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');

-- ========== 表存在性 ==========
ASSERT (
  SELECT COUNT(*) = 6
  FROM `data-aquarium.ashare_dwd.INFORMATION_SCHEMA.TABLES`
  WHERE table_name IN (
    'dwd_fin_income', 'dwd_fin_income_latest',
    'dwd_fin_balancesheet', 'dwd_fin_balancesheet_latest',
    'dwd_fin_cashflow', 'dwd_fin_cashflow_latest'
  )
) AS 'finance DWD version-fact and latest tables must exist';

ASSERT (
  SELECT COUNT(*) = 1
  FROM `data-aquarium.ashare_dws.INFORMATION_SCHEMA.TABLES`
  WHERE table_name = 'dws_stock_feature_fin_daily'
) AS 'dws_stock_feature_fin_daily must exist';

-- ========== DWD 必备口径字段存在（三大报表） ==========
ASSERT (
  SELECT COUNT(*) = 0
  FROM UNNEST(['dwd_fin_income', 'dwd_fin_balancesheet', 'dwd_fin_cashflow']) AS tbl
  CROSS JOIN UNNEST(['report_type', 'report_caliber', 'is_default_report_caliber']) AS required_column
  LEFT JOIN `data-aquarium.ashare_dwd.INFORMATION_SCHEMA.COLUMNS` AS c
    ON c.table_name = tbl AND c.column_name = required_column
  WHERE c.column_name IS NULL
) AS 'finance DWD must keep report_type/report_caliber/is_default_report_caliber';

-- ========== DWD 版本事实键唯一：(sec_code, report_period, report_type, ann_date_eff, update_flag) ==========
ASSERT (
  SELECT COUNT(*) = 0 FROM (
    SELECT 1 FROM `data-aquarium.ashare_dwd.dwd_fin_income`
    GROUP BY sec_code, report_period, report_type, ann_date_eff, update_flag HAVING COUNT(*) > 1)
) AS 'dwd_fin_income version key must be unique';
ASSERT (
  SELECT COUNT(*) = 0 FROM (
    SELECT 1 FROM `data-aquarium.ashare_dwd.dwd_fin_balancesheet`
    GROUP BY sec_code, report_period, report_type, ann_date_eff, update_flag HAVING COUNT(*) > 1)
) AS 'dwd_fin_balancesheet version key must be unique';
ASSERT (
  SELECT COUNT(*) = 0 FROM (
    SELECT 1 FROM `data-aquarium.ashare_dwd.dwd_fin_cashflow`
    GROUP BY sec_code, report_period, report_type, ann_date_eff, update_flag HAVING COUNT(*) > 1)
) AS 'dwd_fin_cashflow version key must be unique';

-- ========== NULL report_type 不得被当成默认合并口径（NULL-safe） ==========
ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dwd.dwd_fin_income`
  WHERE report_type IS NULL AND (report_caliber IS DISTINCT FROM 'unknown' OR is_default_report_caliber IS TRUE)
) AS 'dwd_fin_income NULL report_type must map to unknown and not default';
ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dwd.dwd_fin_balancesheet`
  WHERE report_type IS NULL AND (report_caliber IS DISTINCT FROM 'unknown' OR is_default_report_caliber IS TRUE)
) AS 'dwd_fin_balancesheet NULL report_type must map to unknown and not default';
ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dwd.dwd_fin_cashflow`
  WHERE report_type IS NULL AND (report_caliber IS DISTINCT FROM 'unknown' OR is_default_report_caliber IS TRUE)
) AS 'dwd_fin_cashflow NULL report_type must map to unknown and not default';

-- ========== 默认口径映射必须和 report_type='1' 一致（NULL-safe） ==========
ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dwd.dwd_fin_income`
  WHERE is_default_report_caliber IS DISTINCT FROM COALESCE(report_type = '1', FALSE)
) AS 'dwd_fin_income is_default_report_caliber must equal report_type=1';
ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dwd.dwd_fin_balancesheet`
  WHERE is_default_report_caliber IS DISTINCT FROM COALESCE(report_type = '1', FALSE)
) AS 'dwd_fin_balancesheet is_default_report_caliber must equal report_type=1';
ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dwd.dwd_fin_cashflow`
  WHERE is_default_report_caliber IS DISTINCT FROM COALESCE(report_type = '1', FALSE)
) AS 'dwd_fin_cashflow is_default_report_caliber must equal report_type=1';

-- ========== DWD 可见日 PIT 映射有效：visible_trade_date 非空且不早于公告生效日 ==========
ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dwd.dwd_fin_income`
  WHERE visible_trade_date IS NULL OR visible_trade_date < ann_date_eff
) AS 'dwd_fin_income visible_trade_date must be present and >= ann_date_eff';
ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dwd.dwd_fin_balancesheet`
  WHERE visible_trade_date IS NULL OR visible_trade_date < ann_date_eff
) AS 'dwd_fin_balancesheet visible_trade_date must be present and >= ann_date_eff';
ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dwd.dwd_fin_cashflow`
  WHERE visible_trade_date IS NULL OR visible_trade_date < ann_date_eff
) AS 'dwd_fin_cashflow visible_trade_date must be present and >= ann_date_eff';

-- ========== 默认口径 latest 唯一 + 不混入非默认口径 ==========
ASSERT (
  SELECT COUNT(*) = 0 FROM (
    SELECT 1 FROM `data-aquarium.ashare_dwd.dwd_fin_income_latest`
    GROUP BY sec_code, report_period HAVING COUNT(*) > 1)
) AS 'dwd_fin_income_latest (sec_code, report_period) must be unique';
ASSERT (
  SELECT COUNT(*) = 0 FROM (
    SELECT 1 FROM `data-aquarium.ashare_dwd.dwd_fin_balancesheet_latest`
    GROUP BY sec_code, report_period HAVING COUNT(*) > 1)
) AS 'dwd_fin_balancesheet_latest (sec_code, report_period) must be unique';
ASSERT (
  SELECT COUNT(*) = 0 FROM (
    SELECT 1 FROM `data-aquarium.ashare_dwd.dwd_fin_cashflow_latest`
    GROUP BY sec_code, report_period HAVING COUNT(*) > 1)
) AS 'dwd_fin_cashflow_latest (sec_code, report_period) must be unique';

ASSERT (
  SELECT COUNTIF(is_default_report_caliber IS NOT TRUE) = 0
  FROM `data-aquarium.ashare_dwd.dwd_fin_income_latest`
) AS 'dwd_fin_income_latest must not contain non-default caliber';
ASSERT (
  SELECT COUNTIF(is_default_report_caliber IS NOT TRUE) = 0
  FROM `data-aquarium.ashare_dwd.dwd_fin_balancesheet_latest`
) AS 'dwd_fin_balancesheet_latest must not contain non-default caliber';
ASSERT (
  SELECT COUNTIF(is_default_report_caliber IS NOT TRUE) = 0
  FROM `data-aquarium.ashare_dwd.dwd_fin_cashflow_latest`
) AS 'dwd_fin_cashflow_latest must not contain non-default caliber';

-- ========== DWS 财务特征：主键唯一、PIT 防线、默认口径契约 ==========
ASSERT (
  SELECT COUNT(*) = 0 FROM (
    SELECT 1 FROM `data-aquarium.ashare_dws.dws_stock_feature_fin_daily`
    WHERE trade_date BETWEEN dws_start_date AND dws_end_date
    GROUP BY sec_code, trade_date, feature_version HAVING COUNT(*) > 1)
) AS 'dws_stock_feature_fin_daily key (sec_code, trade_date, feature_version) must be unique';

ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dws.dws_stock_feature_fin_daily`
  WHERE trade_date BETWEEN dws_start_date AND dws_end_date
    AND (visible_trade_date > trade_date
         OR ind_visible_trade_date > trade_date
         OR bs_visible_trade_date > trade_date
         OR cf_visible_trade_date > trade_date)
) AS 'dws_stock_feature_fin_daily must not leak future financial reports (all visible_trade_date <= trade_date)';

ASSERT (
  SELECT COUNT(*) = 0 FROM `data-aquarium.ashare_dws.dws_stock_feature_fin_daily`
  WHERE trade_date BETWEEN dws_start_date AND dws_end_date
    AND (is_default_report_caliber IS NOT TRUE OR report_caliber != 'consolidated')
) AS 'dws_stock_feature_fin_daily statement features must consume only default consolidated caliber';

-- ========== DWS 不丢 universe 行：行数与 universe 一致（LEFT JOIN 未退化为 inner join） ==========
ASSERT (
  (SELECT COUNT(*) FROM `data-aquarium.ashare_dws.dws_stock_feature_fin_daily`
     WHERE trade_date BETWEEN dws_start_date AND dws_end_date)
  = (SELECT COUNT(*) FROM `data-aquarium.ashare_dws.dws_stock_universe_daily`
     WHERE trade_date BETWEEN dws_start_date AND dws_end_date)
) AS 'dws_stock_feature_fin_daily must keep every universe (sec_code, trade_date) row';

-- ========== 字段 description 补齐（PRD §10：表/字段说明补齐）==========
-- CTAS 重建后需重跑 sql/metadata/02_finance_table_column_descriptions.sql；本断言防止漏跑。
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dwd.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
  WHERE table_name IN (
    'dwd_fin_income', 'dwd_fin_income_latest',
    'dwd_fin_balancesheet', 'dwd_fin_balancesheet_latest',
    'dwd_fin_cashflow', 'dwd_fin_cashflow_latest'
  )
  AND (description IS NULL OR description = '')
) AS 'finance DWD tables must have all column descriptions filled (run sql/metadata/02)';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dws.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
  WHERE table_name = 'dws_stock_feature_fin_daily'
    AND (description IS NULL OR description = '')
) AS 'dws_stock_feature_fin_daily must have all column descriptions filled (run sql/metadata/02)';

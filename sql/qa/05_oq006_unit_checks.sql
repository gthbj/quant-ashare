-- 文档维护：GPT-5（最近更新 2026-06-02）
-- BigQuery Standard SQL
-- OQ-006 单位契约 QA 门禁。
-- 所有新增或修改 DWD 标准字段的 PR 必须运行本脚本并通过全部 ASSERT。
-- 执行前确保 P0 DWD 表已物化（尤其是 dwd_index_eod 已按 OQ-006 重建）。

DECLARE dwd_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dwd_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');

-- ============================================================
-- QA-UNIT-1：映射表存在且键唯一
-- ============================================================
ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT source_system, endpoint, ods_table, source_field, dwd_table, dwd_field, COUNT(*) AS n
    FROM `data-aquarium.ashare_meta.ods_field_unit_map`
    GROUP BY source_system, endpoint, ods_table, source_field, dwd_table, dwd_field
    HAVING n > 1
  )
) AS 'QA-UNIT-1: ods_field_unit_map primary key must be unique';

-- ============================================================
-- QA-UNIT-2：P0 覆盖检查 + PR #13 首批字段覆盖
-- ============================================================
WITH required AS (
  -- dwd_stock_eod_price
  SELECT 'dwd_stock_eod_price' AS dwd_table, 'amount_cny' AS dwd_field UNION ALL
  SELECT 'dwd_stock_eod_price', 'volume_share' UNION ALL
  SELECT 'dwd_stock_eod_price', 'volume_lot' UNION ALL
  SELECT 'dwd_stock_eod_price', 'amount_k_cny' UNION ALL
  SELECT 'dwd_stock_eod_price', 'open' UNION ALL
  SELECT 'dwd_stock_eod_price', 'high' UNION ALL
  SELECT 'dwd_stock_eod_price', 'low' UNION ALL
  SELECT 'dwd_stock_eod_price', 'close' UNION ALL
  SELECT 'dwd_stock_eod_price', 'pre_close' UNION ALL
  SELECT 'dwd_stock_eod_price', 'change' UNION ALL
  SELECT 'dwd_stock_eod_price', 'pct_chg' UNION ALL
  SELECT 'dwd_stock_eod_price', 'ret_1d' UNION ALL
  SELECT 'dwd_stock_eod_price', 'up_limit' UNION ALL
  SELECT 'dwd_stock_eod_price', 'down_limit' UNION ALL
  SELECT 'dwd_stock_eod_price', 'open_hfq' UNION ALL
  SELECT 'dwd_stock_eod_price', 'high_hfq' UNION ALL
  SELECT 'dwd_stock_eod_price', 'low_hfq' UNION ALL
  SELECT 'dwd_stock_eod_price', 'close_hfq' UNION ALL
  SELECT 'dwd_stock_eod_price', 'adj_factor' UNION ALL
  -- dwd_stock_eod_valuation
  SELECT 'dwd_stock_eod_valuation', 'total_share' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'float_share' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'free_share' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'total_share_10k' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'float_share_10k' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'free_share_10k' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'total_mv_cny' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'circ_mv_cny' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'total_mv_10k_cny' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'circ_mv_10k_cny' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'close' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'turnover_rate' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'turnover_rate_free_float' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'volume_ratio' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'pe' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'pe_ttm' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'pb' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'ps' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'ps_ttm' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'dividend_yield' UNION ALL
  SELECT 'dwd_stock_eod_valuation', 'dividend_yield_ttm' UNION ALL
  -- dwd_index_eod
  SELECT 'dwd_index_eod', 'volume_share' UNION ALL
  SELECT 'dwd_index_eod', 'volume_lot' UNION ALL
  SELECT 'dwd_index_eod', 'amount_cny' UNION ALL
  SELECT 'dwd_index_eod', 'amount_k_cny' UNION ALL
  SELECT 'dwd_index_eod', 'open' UNION ALL
  SELECT 'dwd_index_eod', 'high' UNION ALL
  SELECT 'dwd_index_eod', 'low' UNION ALL
  SELECT 'dwd_index_eod', 'close' UNION ALL
  SELECT 'dwd_index_eod', 'pre_close' UNION ALL
  SELECT 'dwd_index_eod', 'change' UNION ALL
  SELECT 'dwd_index_eod', 'pct_chg' UNION ALL
  SELECT 'dwd_index_eod', 'total_mv_cny' UNION ALL
  SELECT 'dwd_index_eod', 'float_mv_cny' UNION ALL
  SELECT 'dwd_index_eod', 'total_share' UNION ALL
  SELECT 'dwd_index_eod', 'float_share' UNION ALL
  SELECT 'dwd_index_eod', 'free_share' UNION ALL
  SELECT 'dwd_index_eod', 'turnover_rate' UNION ALL
  SELECT 'dwd_index_eod', 'turnover_rate_free_float' UNION ALL
  SELECT 'dwd_index_eod', 'pe' UNION ALL
  SELECT 'dwd_index_eod', 'pe_ttm' UNION ALL
  SELECT 'dwd_index_eod', 'pb' UNION ALL
  -- dwd_fin_indicator
  SELECT 'dwd_fin_indicator', 'eps' UNION ALL
  SELECT 'dwd_fin_indicator', 'dt_eps' UNION ALL
  SELECT 'dwd_fin_indicator', 'net_debt' UNION ALL
  SELECT 'dwd_fin_indicator', 'working_capital' UNION ALL
  SELECT 'dwd_fin_indicator', 'netprofit_margin' UNION ALL
  SELECT 'dwd_fin_indicator', 'grossprofit_margin' UNION ALL
  SELECT 'dwd_fin_indicator', 'roe' UNION ALL
  SELECT 'dwd_fin_indicator', 'roe_deducted' UNION ALL
  SELECT 'dwd_fin_indicator', 'roa' UNION ALL
  SELECT 'dwd_fin_indicator', 'roic' UNION ALL
  SELECT 'dwd_fin_indicator', 'debt_to_assets' UNION ALL
  SELECT 'dwd_fin_indicator', 'current_ratio' UNION ALL
  SELECT 'dwd_fin_indicator', 'quick_ratio' UNION ALL
  SELECT 'dwd_fin_indicator', 'cash_ratio' UNION ALL
  SELECT 'dwd_fin_indicator', 'inventory_turnover' UNION ALL
  SELECT 'dwd_fin_indicator', 'ar_turnover' UNION ALL
  SELECT 'dwd_fin_indicator', 'assets_turnover' UNION ALL
  SELECT 'dwd_fin_indicator', 'ocf_to_or' UNION ALL
  SELECT 'dwd_fin_indicator', 'assets_to_equity' UNION ALL
  SELECT 'dwd_fin_indicator', 'ocf_to_profit' UNION ALL
  SELECT 'dwd_fin_indicator', 'q_netprofit_margin' UNION ALL
  SELECT 'dwd_fin_indicator', 'q_grossprofit_margin' UNION ALL
  SELECT 'dwd_fin_indicator', 'q_roe' UNION ALL
  SELECT 'dwd_fin_indicator', 'q_roe_deducted' UNION ALL
  SELECT 'dwd_fin_indicator', 'q_npta' UNION ALL
  SELECT 'dwd_fin_indicator', 'basic_eps_yoy' UNION ALL
  SELECT 'dwd_fin_indicator', 'dt_eps_yoy' UNION ALL
  SELECT 'dwd_fin_indicator', 'operating_profit_yoy' UNION ALL
  SELECT 'dwd_fin_indicator', 'ebt_yoy' UNION ALL
  SELECT 'dwd_fin_indicator', 'netprofit_yoy' UNION ALL
  SELECT 'dwd_fin_indicator', 'total_revenue_yoy' UNION ALL
  SELECT 'dwd_fin_indicator', 'operating_revenue_yoy' UNION ALL
  -- PR #13 首批字段（即使 DWD 表尚未物化，映射表中必须已登记）
  SELECT 'dwd_fin_income', 'total_revenue' UNION ALL
  SELECT 'dwd_fin_income', 'revenue' UNION ALL
  SELECT 'dwd_fin_income', 'total_cogs' UNION ALL
  SELECT 'dwd_fin_income', 'operate_profit' UNION ALL
  SELECT 'dwd_fin_income', 'total_profit' UNION ALL
  SELECT 'dwd_fin_income', 'income_tax' UNION ALL
  SELECT 'dwd_fin_income', 'n_income' UNION ALL
  SELECT 'dwd_fin_income', 'n_income_attr_p' UNION ALL
  SELECT 'dwd_fin_income', 'ebit' UNION ALL
  SELECT 'dwd_fin_income', 'ebitda' UNION ALL
  SELECT 'dwd_fin_balancesheet', 'total_assets' UNION ALL
  SELECT 'dwd_fin_balancesheet', 'total_liab' UNION ALL
  SELECT 'dwd_fin_balancesheet', 'total_hldr_eqy_exc_min_int' UNION ALL
  SELECT 'dwd_fin_balancesheet', 'money_cap' UNION ALL
  SELECT 'dwd_fin_balancesheet', 'inventories' UNION ALL
  SELECT 'dwd_fin_balancesheet', 'accounts_receiv' UNION ALL
  SELECT 'dwd_fin_balancesheet', 'goodwill' UNION ALL
  SELECT 'dwd_fin_cashflow', 'n_cashflow_act' UNION ALL
  SELECT 'dwd_fin_cashflow', 'n_cashflow_inv_act' UNION ALL
  SELECT 'dwd_fin_cashflow', 'n_cash_flows_fnc_act' UNION ALL
  SELECT 'dwd_fin_cashflow', 'free_cashflow'
),
actual AS (
  SELECT dwd_table, dwd_field
  FROM `data-aquarium.ashare_meta.ods_field_unit_map`
)
ASSERT (
  SELECT COUNT(*) = 0
  FROM required
  LEFT JOIN actual USING (dwd_table, dwd_field)
  WHERE actual.dwd_field IS NULL
) AS 'QA-UNIT-2: all P0 and PR #13 first-batch fields must have unit mappings';

-- ============================================================
-- QA-UNIT-3：未核对字段阻断（mapping 中不允许 pending）
-- ============================================================
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_meta.ods_field_unit_map`
  WHERE verification_status = 'pending'
) AS 'QA-UNIT-3: no pending mappings allowed in ods_field_unit_map';

-- ============================================================
-- QA-UNIT-4：命名检查
-- ============================================================
-- 4a: amount / market_value 标准字段必须以 _cny 结尾
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_meta.ods_field_unit_map`
  WHERE semantic_type IN ('amount', 'market_value')
    AND verification_status = 'verified'
    AND NOT ENDS_WITH(dwd_field, '_cny')
    AND naming_exception_type IS NULL
) AS 'QA-UNIT-4a: amount/market_value standard fields must end with _cny';

-- 4b: volume / share 标准字段必须以 _share 结尾（允许命名例外登记）
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_meta.ods_field_unit_map`
  WHERE semantic_type IN ('volume', 'share')
    AND verification_status = 'verified'
    AND NOT ENDS_WITH(dwd_field, '_share')
    AND naming_exception_type IS NULL
) AS 'QA-UNIT-4b: volume/share standard fields must end with _share unless registered exception';

-- 4c: raw 字段必须体现源单位（_lot / _k_cny / _10k_cny / _10k_share）
ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_meta.ods_field_unit_map`
  WHERE raw_field_kept = TRUE
    AND raw_field_name IS NOT NULL
    AND NOT (
         ENDS_WITH(raw_field_name, '_lot')
      OR ENDS_WITH(raw_field_name, '_k_cny')
      OR ENDS_WITH(raw_field_name, '_10k_cny')
      OR ENDS_WITH(raw_field_name, '_10k_share')
    )
) AS 'QA-UNIT-4c: raw field names must indicate source unit suffix';

-- ============================================================
-- QA-UNIT-5：DWS/ADS 禁止二次换算
-- ============================================================
-- 首版实现说明：BQ SQL 脚本无法直接扫描仓库文件系统做 SQL 文本 lint。
-- 建议在 CI/CD 或本地 pre-commit 中运行以下命令行检查：
--   grep -rn "\* *1000\|\* *10000\|\* *100000000" sql/dws/ sql/ads/ --include="*.sql"
-- 若出现无说明的乘法常数，需人工 review 并在代码注释中写明换算来源。
-- 本 QA 脚本当前仅输出 DWS/ADS 现有表名作为提醒，不阻断。
SELECT 'QA-UNIT-5 INFO: DWS/ADS tables currently materialized; ensure no unit multiplication in DWS/ADS SQL' AS msg,
       table_name
FROM `data-aquarium.ashare_dws.INFORMATION_SCHEMA.TABLES`
UNION ALL
SELECT 'QA-UNIT-5 INFO: DWS/ADS tables currently materialized; ensure no unit multiplication in DWS/ADS SQL' AS msg,
       table_name
FROM `data-aquarium.ashare_ads.INFORMATION_SCHEMA.TABLES`;

-- ============================================================
-- QA-UNIT-6：算术自洽检查
-- ============================================================
-- 6a: daily amount_cny ~= close * volume_share（允许行情聚合误差，中位数在合理区间）
ASSERT (
  SELECT COUNTIF(median_ratio BETWEEN 0.5 AND 2.0) > 0
  FROM (
    SELECT APPROX_QUANTILES(SAFE_DIVIDE(amount_cny, close * volume_share), 100)[OFFSET(50)] AS median_ratio
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price`
    WHERE trade_date BETWEEN dwd_start_date AND dwd_end_date
      AND close > 0 AND volume_share > 0 AND amount_cny > 0
  )
) AS 'QA-UNIT-6a: dwd_stock_eod_price amount_cny median must be consistent with close * volume_share';

-- 6b: daily_basic total_mv_cny ~= close * total_share
ASSERT (
  SELECT COUNTIF(median_ratio BETWEEN 0.5 AND 2.0) > 0
  FROM (
    SELECT APPROX_QUANTILES(SAFE_DIVIDE(total_mv_cny, close * total_share), 100)[OFFSET(50)] AS median_ratio
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
    WHERE trade_date BETWEEN dwd_start_date AND dwd_end_date
      AND close > 0 AND total_share > 0 AND total_mv_cny > 0
  )
) AS 'QA-UNIT-6b: dwd_stock_eod_valuation total_mv_cny median must be consistent with close * total_share';

-- 6c: daily_basic circ_mv_cny ~= close * float_share
ASSERT (
  SELECT COUNTIF(median_ratio BETWEEN 0.5 AND 2.0) > 0
  FROM (
    SELECT APPROX_QUANTILES(SAFE_DIVIDE(circ_mv_cny, close * float_share), 100)[OFFSET(50)] AS median_ratio
    FROM `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
    WHERE trade_date BETWEEN dwd_start_date AND dwd_end_date
      AND close > 0 AND float_share > 0 AND circ_mv_cny > 0
  )
) AS 'QA-UNIT-6c: dwd_stock_eod_valuation circ_mv_cny median must be consistent with close * float_share';

-- 6d: index_daily amount_cny ~= close * volume_share（指数点位 * 股数 = 元）
ASSERT (
  SELECT COUNTIF(median_ratio BETWEEN 0.5 AND 2.0) > 0
  FROM (
    SELECT APPROX_QUANTILES(SAFE_DIVIDE(amount_cny, close * volume_share), 100)[OFFSET(50)] AS median_ratio
    FROM `data-aquarium.ashare_dwd.dwd_index_eod`
    WHERE trade_date BETWEEN dwd_start_date AND dwd_end_date
      AND close > 0 AND volume_share > 0 AND amount_cny > 0
  )
) AS 'QA-UNIT-6d: dwd_index_eod amount_cny median must be consistent with close * volume_share (OQ-006 conversion check)';

-- 6e: index total_mv_cny 与 total_share 量级一致（指数市值 / 指数点位 ~= 总股本，单位均为元/股）
ASSERT (
  SELECT COUNTIF(median_ratio BETWEEN 0.5 AND 2.0) > 0
  FROM (
    SELECT APPROX_QUANTILES(SAFE_DIVIDE(total_mv_cny, close * total_share), 100)[OFFSET(50)] AS median_ratio
    FROM `data-aquarium.ashare_dwd.dwd_index_eod`
    WHERE trade_date BETWEEN dwd_start_date AND dwd_end_date
      AND close > 0 AND total_share > 0 AND total_mv_cny > 0
  )
) AS 'QA-UNIT-6e: dwd_index_eod total_mv_cny median must be consistent with close * total_share';

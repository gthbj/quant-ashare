-- BigQuery Standard SQL
-- QA for ashare_dws.dws_market_state_daily.

DECLARE p_start_date DATE DEFAULT DATE '2024-01-02';
DECLARE p_end_date DATE DEFAULT DATE '2026-04-30';
DECLARE p_market_state_version STRING DEFAULT 'market_state_v0_20260606';

ASSERT p_start_date <= p_end_date
  AS 'QA-MKT-0: p_start_date must be <= p_end_date';

ASSERT (
  SELECT COUNT(*) > 0
  FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
  WHERE ms.trade_date BETWEEN p_start_date AND p_end_date
    AND ms.market_state_version = p_market_state_version
) AS 'QA-MKT-1: market state table must have rows in requested window';

ASSERT (
  SELECT COUNT(*) = 0
  FROM (
    SELECT ms.trade_date, ms.market_state_version, COUNT(*) AS n
    FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
    WHERE ms.trade_date BETWEEN p_start_date AND p_end_date
      AND ms.market_state_version = p_market_state_version
    GROUP BY ms.trade_date, ms.market_state_version
    HAVING n > 1
  )
) AS 'QA-MKT-2: market state key must be unique';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
  WHERE ms.trade_date BETWEEN p_start_date AND p_end_date
    AND ms.market_state_version = p_market_state_version
    AND NOT EXISTS (
      SELECT 1
      FROM `data-aquarium.ashare_dim.dim_trade_calendar` AS cal
      WHERE cal.exchange = 'SSE'
        AND cal.is_open = 1
        AND cal.cal_date = ms.trade_date
    )
) AS 'QA-MKT-3: market state rows must be SSE open dates';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
  WHERE ms.trade_date BETWEEN p_start_date AND p_end_date
    AND ms.market_state_version = p_market_state_version
    AND (
      ms.stock_count <= 0
      OR ms.adv_ratio_1d NOT BETWEEN 0.0 AND 1.0
      OR ms.above_ma20_ratio NOT BETWEEN 0.0 AND 1.0
      OR ms.new_low_20d_ratio NOT BETWEEN 0.0 AND 1.0
      OR ms.limit_down_mv_ratio NOT BETWEEN 0.0 AND 1.0
      OR ms.risk_off_trigger_count NOT BETWEEN 0 AND 3
    )
) AS 'QA-MKT-4: market state ratio/count fields must be in valid ranges';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
  WHERE ms.trade_date BETWEEN p_start_date AND p_end_date
    AND ms.market_state_version = p_market_state_version
    AND ms.is_risk_off
    AND (
      COALESCE(ms.risk_off_reasons, '') = ''
      OR ms.market_regime != 'risk_off'
      OR ms.risk_off_action != 'skip_new_buys'
    )
) AS 'QA-MKT-5: risk-off rows must be explainable and use skip_new_buys action';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
  WHERE ms.trade_date BETWEEN p_start_date AND p_end_date
    AND ms.market_state_version = p_market_state_version
    AND ms.market_regime NOT IN ('risk_off', 'risk_neutral', 'risk_on')
) AS 'QA-MKT-6: market_regime must be an allowed enum';

ASSERT (
  SELECT COUNT(*) = 0
  FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
  WHERE ms.trade_date BETWEEN DATE_ADD(p_start_date, INTERVAL 80 DAY) AND p_end_date
    AND ms.market_state_version = p_market_state_version
    AND (
      ms.csi1000_ret_20d IS NULL
      OR ms.csi1000_drawdown_20d IS NULL
      OR ms.csi1000_vol_20d IS NULL
      OR ms.csi300_ret_20d IS NULL
      OR ms.csi300_drawdown_20d IS NULL
    )
) AS 'QA-MKT-7: index market-state metrics must be populated after warm-up';

SELECT
  'QA-MKT completed' AS status,
  COUNT(*) AS row_count,
  COUNTIF(is_risk_off) AS risk_off_days
FROM `data-aquarium.ashare_dws.dws_market_state_daily` AS ms
WHERE ms.trade_date BETWEEN p_start_date AND p_end_date
  AND ms.market_state_version = p_market_state_version;

-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- 策略 1 通用监督学习标签：t 日信号，t+1 开盘入场，t+H 收盘退出。

DECLARE dws_start_date DATE DEFAULT DATE '2019-01-01';
DECLARE dws_end_date DATE DEFAULT CURRENT_DATE('Asia/Shanghai');
DECLARE label_version STRING DEFAULT 'open_to_close_h1_5_10_20_v20260601';

CREATE OR REPLACE TABLE `data-aquarium.ashare_dws.dws_stock_label_daily`
PARTITION BY DATE_TRUNC(trade_date, MONTH)
CLUSTER BY sec_code, label_version
OPTIONS (
  description = 'Forward open-to-close return labels for ML strategies; t signal, t+1 open entry and t+H close exit',
  require_partition_filter = TRUE
) AS
WITH cal AS (
  SELECT
    cal_date,
    trade_date_seq
  FROM `data-aquarium.ashare_dim.dim_trade_calendar`
  WHERE exchange = 'SSE'
    AND is_open = 1
    AND cal_date BETWEEN dws_start_date AND dws_end_date
),
price AS (
  SELECT
    p.trade_date,
    p.sec_code,
    c.trade_date_seq,
    p.open_hfq,
    p.close_hfq,
    p.can_buy_open,
    p.can_sell_open,
    p.is_suspended,
    p.is_one_word_limit_up,
    p.is_one_word_limit_down
  FROM `data-aquarium.ashare_dwd.dwd_stock_eod_price` AS p
  JOIN cal AS c
    ON p.trade_date = c.cal_date
  WHERE p.trade_date BETWEEN dws_start_date AND dws_end_date
),
raw AS (
  SELECT
    b.trade_date,
    b.sec_code,
    label_version,
    ce.cal_date AS entry_trade_date,
    c1.cal_date AS exit_trade_date_1d,
    c5.cal_date AS exit_trade_date_5d,
    c10.cal_date AS exit_trade_date_10d,
    c20.cal_date AS exit_trade_date_20d,
    entry.open_hfq AS entry_open_hfq,
    entry.can_buy_open AS entry_can_buy_open,
    entry.is_suspended AS entry_is_suspended,
    entry.is_one_word_limit_up AS entry_is_one_word_limit_up,
    x1.close_hfq AS exit_close_hfq_1d,
    x5.close_hfq AS exit_close_hfq_5d,
    x10.close_hfq AS exit_close_hfq_10d,
    x20.close_hfq AS exit_close_hfq_20d,
    NOT COALESCE(x1.is_suspended, TRUE)
      AND NOT COALESCE(x1.is_one_word_limit_down, TRUE)
      AND x1.close_hfq IS NOT NULL AS exit_reachable_1d,
    NOT COALESCE(x5.is_suspended, TRUE)
      AND NOT COALESCE(x5.is_one_word_limit_down, TRUE)
      AND x5.close_hfq IS NOT NULL AS exit_reachable_5d,
    NOT COALESCE(x10.is_suspended, TRUE)
      AND NOT COALESCE(x10.is_one_word_limit_down, TRUE)
      AND x10.close_hfq IS NOT NULL AS exit_reachable_10d,
    NOT COALESCE(x20.is_suspended, TRUE)
      AND NOT COALESCE(x20.is_one_word_limit_down, TRUE)
      AND x20.close_hfq IS NOT NULL AS exit_reachable_20d
  FROM price AS b
  LEFT JOIN cal AS ce
    ON ce.trade_date_seq = b.trade_date_seq + 1
  LEFT JOIN cal AS c1
    ON c1.trade_date_seq = b.trade_date_seq + 1
  LEFT JOIN cal AS c5
    ON c5.trade_date_seq = b.trade_date_seq + 5
  LEFT JOIN cal AS c10
    ON c10.trade_date_seq = b.trade_date_seq + 10
  LEFT JOIN cal AS c20
    ON c20.trade_date_seq = b.trade_date_seq + 20
  LEFT JOIN price AS entry
    ON entry.sec_code = b.sec_code
   AND entry.trade_date = ce.cal_date
  LEFT JOIN price AS x1
    ON x1.sec_code = b.sec_code
   AND x1.trade_date = c1.cal_date
  LEFT JOIN price AS x5
    ON x5.sec_code = b.sec_code
   AND x5.trade_date = c5.cal_date
  LEFT JOIN price AS x10
    ON x10.sec_code = b.sec_code
   AND x10.trade_date = c10.cal_date
  LEFT JOIN price AS x20
    ON x20.sec_code = b.sec_code
   AND x20.trade_date = c20.cal_date
),
returns AS (
  SELECT
    raw.*,
    COALESCE(u.in_universe_default, FALSE) AS in_universe_default_for_rank,
    COALESCE(entry_can_buy_open, FALSE)
      AND NOT COALESCE(entry_is_suspended, TRUE)
      AND NOT COALESCE(entry_is_one_word_limit_up, TRUE)
      AND entry_open_hfq IS NOT NULL AS label_entry_tradable,
    SAFE_DIVIDE(exit_close_hfq_1d, entry_open_hfq) - 1.0 AS fwd_ret_1d,
    SAFE_DIVIDE(exit_close_hfq_5d, entry_open_hfq) - 1.0 AS fwd_ret_5d,
    SAFE_DIVIDE(exit_close_hfq_10d, entry_open_hfq) - 1.0 AS fwd_ret_10d,
    SAFE_DIVIDE(exit_close_hfq_20d, entry_open_hfq) - 1.0 AS fwd_ret_20d
  FROM raw
  LEFT JOIN `data-aquarium.ashare_dws.dws_stock_universe_daily` AS u
    ON raw.trade_date = u.trade_date
   AND raw.sec_code = u.sec_code
   AND u.trade_date BETWEEN dws_start_date AND dws_end_date
),
rank_1d AS (
  SELECT
    trade_date,
    sec_code,
    PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY fwd_ret_1d) AS rank_pct_1d
  FROM returns
  WHERE fwd_ret_1d IS NOT NULL
    AND in_universe_default_for_rank
),
rank_5d AS (
  SELECT
    trade_date,
    sec_code,
    PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY fwd_ret_5d) AS rank_pct_5d
  FROM returns
  WHERE fwd_ret_5d IS NOT NULL
    AND in_universe_default_for_rank
),
rank_10d AS (
  SELECT
    trade_date,
    sec_code,
    PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY fwd_ret_10d) AS rank_pct_10d
  FROM returns
  WHERE fwd_ret_10d IS NOT NULL
    AND in_universe_default_for_rank
),
rank_20d AS (
  SELECT
    trade_date,
    sec_code,
    PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY fwd_ret_20d) AS rank_pct_20d
  FROM returns
  WHERE fwd_ret_20d IS NOT NULL
    AND in_universe_default_for_rank
)
SELECT
  r.trade_date,
  r.sec_code,
  r.label_version,
  r.entry_trade_date,
  r.exit_trade_date_1d,
  r.exit_trade_date_5d,
  r.exit_trade_date_10d,
  r.exit_trade_date_20d,
  r.label_entry_tradable,
  r.exit_reachable_1d,
  r.exit_reachable_5d,
  r.exit_reachable_10d,
  r.exit_reachable_20d,
  r.fwd_ret_1d,
  r.fwd_ret_5d,
  r.fwd_ret_10d,
  r.fwd_ret_20d,
  r.fwd_ret_1d - AVG(IF(r.in_universe_default_for_rank, r.fwd_ret_1d, NULL)) OVER (PARTITION BY r.trade_date) AS fwd_xs_ret_1d,
  r.fwd_ret_5d - AVG(IF(r.in_universe_default_for_rank, r.fwd_ret_5d, NULL)) OVER (PARTITION BY r.trade_date) AS fwd_xs_ret_5d,
  r.fwd_ret_10d - AVG(IF(r.in_universe_default_for_rank, r.fwd_ret_10d, NULL)) OVER (PARTITION BY r.trade_date) AS fwd_xs_ret_10d,
  r.fwd_ret_20d - AVG(IF(r.in_universe_default_for_rank, r.fwd_ret_20d, NULL)) OVER (PARTITION BY r.trade_date) AS fwd_xs_ret_20d,
  q1.rank_pct_1d,
  q5.rank_pct_5d,
  q10.rank_pct_10d,
  q20.rank_pct_20d,
  IF(q1.rank_pct_1d IS NULL, NULL, CAST(q1.rank_pct_1d >= 0.7 AS INT64)) AS label_top30_1d,
  IF(q5.rank_pct_5d IS NULL, NULL, CAST(q5.rank_pct_5d >= 0.7 AS INT64)) AS label_top30_5d,
  IF(q10.rank_pct_10d IS NULL, NULL, CAST(q10.rank_pct_10d >= 0.7 AS INT64)) AS label_top30_10d,
  IF(q20.rank_pct_20d IS NULL, NULL, CAST(q20.rank_pct_20d >= 0.7 AS INT64)) AS label_top30_20d,
  IF(q1.rank_pct_1d IS NULL, NULL, CAST(q1.rank_pct_1d > 0.5 AS INT64)) AS label_above_median_1d,
  IF(q5.rank_pct_5d IS NULL, NULL, CAST(q5.rank_pct_5d > 0.5 AS INT64)) AS label_above_median_5d,
  IF(q10.rank_pct_10d IS NULL, NULL, CAST(q10.rank_pct_10d > 0.5 AS INT64)) AS label_above_median_10d,
  IF(q20.rank_pct_20d IS NULL, NULL, CAST(q20.rank_pct_20d > 0.5 AS INT64)) AS label_above_median_20d,
  r.label_entry_tradable AND r.fwd_ret_1d IS NOT NULL AS label_valid_1d,
  r.label_entry_tradable AND r.fwd_ret_5d IS NOT NULL AS label_valid_5d,
  r.label_entry_tradable AND r.fwd_ret_10d IS NOT NULL AS label_valid_10d,
  r.label_entry_tradable AND r.fwd_ret_20d IS NOT NULL AS label_valid_20d,
  CURRENT_TIMESTAMP() AS created_at
FROM returns AS r
LEFT JOIN rank_1d AS q1
  ON r.trade_date = q1.trade_date
 AND r.sec_code = q1.sec_code
LEFT JOIN rank_5d AS q5
  ON r.trade_date = q5.trade_date
 AND r.sec_code = q5.sec_code
LEFT JOIN rank_10d AS q10
  ON r.trade_date = q10.trade_date
 AND r.sec_code = q10.sec_code
LEFT JOIN rank_20d AS q20
  ON r.trade_date = q20.trade_date
 AND r.sec_code = q20.sec_code;

ALTER TABLE `data-aquarium.ashare_dws.dws_stock_label_daily`
ALTER COLUMN trade_date SET OPTIONS (description = '信号日 t，月分区字段'),
ALTER COLUMN label_version SET OPTIONS (description = '标签口径版本；当前为 t+1 开盘入场、t+H 收盘退出'),
ALTER COLUMN label_entry_tradable SET OPTIONS (description = 't+1 开盘是否可买入；仅用于训练有效性、回测撮合和归因，不得用于 t 日预先选股'),
ALTER COLUMN fwd_ret_5d SET OPTIONS (description = 't+1 开盘买入至 t+5 收盘退出的后复权收益'),
ALTER COLUMN rank_pct_5d SET OPTIONS (description = '默认 universe 内当日 fwd_ret_5d 横截面分位，0 为最低，1 为最高；非默认 universe 样本为空'),
ALTER COLUMN label_top30_5d SET OPTIONS (description = '主分类标签：rank_pct_5d >= 0.7');

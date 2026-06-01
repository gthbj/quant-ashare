-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 03: 所有候选在 valid 上预测 → 计算 RankIC/AUC/log_loss/分层收益 → 选最优 → 更新 registry。
-- 同时把全部候选预测写入临时表，04 只持久化 selected 候选的结果。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_horizon INT64 DEFAULT 5;
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';

-- ── 所有候选模型在 valid 上预测（逐个展开，BigQuery 不支持动态 MODEL 引用）──
CREATE TEMP TABLE all_candidate_preds AS

SELECT 'l1_0_l2_0' AS cand_id, p.trade_date, p.sec_code,
       prob.prob AS score, p.predicted_target_label AS pred_label
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_0_l2_0`,
  (SELECT tp.trade_date, tp.sec_code,
          tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d,
          tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d,
          tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d,
          tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio,
          tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm,
          tp.log_total_mv, tp.log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
   WHERE tp.run_id = p_run_id AND tp.split_tag = 'valid'
     AND tp.trade_date BETWEEN p_valid_start AND p_valid_end)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob
WHERE CAST(prob.label AS STRING) = '1'

UNION ALL
SELECT 'l1_0_l2_1e_4', p.trade_date, p.sec_code, prob.prob, p.predicted_target_label
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_0_l2_1e_4`,
  (SELECT tp.trade_date, tp.sec_code, tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d, tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d, tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d, tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio, tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm, tp.log_total_mv, tp.log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp WHERE tp.run_id = p_run_id AND tp.split_tag = 'valid' AND tp.trade_date BETWEEN p_valid_start AND p_valid_end)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob WHERE CAST(prob.label AS STRING) = '1'

UNION ALL
SELECT 'l1_0_l2_1e_3', p.trade_date, p.sec_code, prob.prob, p.predicted_target_label
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_0_l2_1e_3`,
  (SELECT tp.trade_date, tp.sec_code, tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d, tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d, tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d, tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio, tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm, tp.log_total_mv, tp.log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp WHERE tp.run_id = p_run_id AND tp.split_tag = 'valid' AND tp.trade_date BETWEEN p_valid_start AND p_valid_end)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob WHERE CAST(prob.label AS STRING) = '1'

UNION ALL
SELECT 'l1_1e_5_l2_1e_4', p.trade_date, p.sec_code, prob.prob, p.predicted_target_label
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_1e_5_l2_1e_4`,
  (SELECT tp.trade_date, tp.sec_code, tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d, tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d, tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d, tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio, tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm, tp.log_total_mv, tp.log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp WHERE tp.run_id = p_run_id AND tp.split_tag = 'valid' AND tp.trade_date BETWEEN p_valid_start AND p_valid_end)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob WHERE CAST(prob.label AS STRING) = '1'

UNION ALL
SELECT 'l1_1e_4_l2_1e_3', p.trade_date, p.sec_code, prob.prob, p.predicted_target_label
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.s1_bqml_20260601_01__l1_1e_4_l2_1e_3`,
  (SELECT tp.trade_date, tp.sec_code, tp.list_age_td, tp.ret_1d, tp.ret_3d, tp.ret_5d, tp.ret_10d, tp.ret_20d, tp.ret_60d, tp.mom_20_5, tp.mom_60_20, tp.vol_5d, tp.vol_20d, tp.vol_60d, tp.drawdown_20d, tp.hl_range_20d, tp.amount_ma20_cny, tp.amount_zscore_20d, tp.turnover_rate, tp.turnover_rate_free_float, tp.turnover_rate_ma20, tp.volume_ratio, tp.pe_ttm, tp.pb, tp.ps_ttm, tp.dividend_yield_ttm, tp.ep_ttm, tp.bp, tp.sp_ttm, tp.log_total_mv, tp.log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp WHERE tp.run_id = p_run_id AND tp.split_tag = 'valid' AND tp.trade_date BETWEEN p_valid_start AND p_valid_end)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob WHERE CAST(prob.label AS STRING) = '1';

-- ── 日频 RankIC：先算 rank 再 CORR ──
CREATE TEMP TABLE ranked_preds AS
SELECT
  cp.cand_id,
  cp.trade_date,
  cp.sec_code,
  cp.score,
  s.fwd_ret_5d,
  s.label_top30_5d AS actual_label,
  RANK() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY cp.score) AS score_rank,
  RANK() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY s.fwd_ret_5d) AS ret_rank
FROM all_candidate_preds AS cp
JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
  ON cp.sec_code = s.sec_code AND cp.trade_date = s.trade_date
  AND s.trade_date BETWEEN p_valid_start AND p_valid_end
  AND s.feature_version = p_feature_version
  AND s.sample_trainable_default;

CREATE TEMP TABLE daily_rank_ic AS
SELECT cand_id, trade_date, CORR(score_rank, ret_rank) AS rank_ic
FROM ranked_preds
GROUP BY cand_id, trade_date;

-- ── 分层收益（5 分位）──
CREATE TEMP TABLE layered_ret AS
SELECT cand_id, trade_date, quintile,
       AVG(fwd_ret_5d) AS avg_ret
FROM (
  SELECT cand_id, trade_date, fwd_ret_5d,
         NTILE(5) OVER (PARTITION BY cand_id, trade_date ORDER BY score) AS quintile
  FROM ranked_preds
)
GROUP BY cand_id, trade_date, quintile;

CREATE TEMP TABLE layer_spread AS
SELECT cand_id,
       AVG(IF(quintile = 5, avg_ret, NULL)) - AVG(IF(quintile = 1, avg_ret, NULL)) AS top_minus_bottom_mean
FROM layered_ret
GROUP BY cand_id;

-- ── AUC / log_loss 近似 ──
CREATE TEMP TABLE classification_metrics AS
SELECT cand_id,
       -- log_loss 近似
       -AVG(
         actual_label * LN(GREATEST(score, 1e-15))
         + (1 - actual_label) * LN(GREATEST(1 - score, 1e-15))
       ) AS log_loss,
       COUNT(*) AS n_samples,
       COUNTIF(score IS NULL) AS n_missing
FROM ranked_preds
GROUP BY cand_id;

-- ── 汇总指标 ──
CREATE TEMP TABLE candidate_metrics AS
SELECT
  ic.cand_id,
  AVG(ic.rank_ic) AS rank_ic_mean,
  STDDEV_SAMP(ic.rank_ic) AS rank_ic_std,
  SAFE_DIVIDE(AVG(ic.rank_ic), NULLIF(STDDEV_SAMP(ic.rank_ic), 0)) AS rank_icir,
  COUNT(*) AS n_days,
  cm.log_loss,
  cm.n_samples,
  cm.n_missing,
  ls.top_minus_bottom_mean AS layer_spread
FROM daily_rank_ic AS ic
LEFT JOIN classification_metrics AS cm ON ic.cand_id = cm.cand_id
LEFT JOIN layer_spread AS ls ON ic.cand_id = ls.cand_id
GROUP BY ic.cand_id, cm.log_loss, cm.n_samples, cm.n_missing, ls.top_minus_bottom_mean;

-- ── 选出 rank_ic_mean 最高的候选；tie-break by layer_spread then log_loss ──
CREATE TEMP TABLE selected AS
SELECT cand_id
FROM candidate_metrics
ORDER BY rank_ic_mean DESC, layer_spread DESC, log_loss ASC
LIMIT 1;

-- ── 更新 registry ──
UPDATE `data-aquarium.ashare_ads.ads_model_registry` AS reg
SET reg.status = 'selected',
    reg.metrics_json = (
      SELECT TO_JSON_STRING(STRUCT(
        m.rank_ic_mean, m.rank_ic_std, m.rank_icir, m.n_days,
        m.log_loss, m.n_samples, m.n_missing, m.layer_spread))
      FROM candidate_metrics AS m
      WHERE m.cand_id = (SELECT cand_id FROM selected))
FROM selected AS sel
WHERE reg.model_id = CONCAT(p_run_id, '__', sel.cand_id)
  AND reg.strategy_id = p_strategy_id;

UPDATE `data-aquarium.ashare_ads.ads_model_registry` AS reg
SET reg.status = 'candidate_rejected',
    reg.metrics_json = (
      SELECT TO_JSON_STRING(STRUCT(
        m.rank_ic_mean, m.rank_ic_std, m.rank_icir, m.n_days,
        m.log_loss, m.n_samples, m.n_missing, m.layer_spread))
      FROM candidate_metrics AS m
      WHERE m.cand_id = REPLACE(reg.model_id, CONCAT(p_run_id, '__'), ''))
WHERE reg.strategy_id = p_strategy_id
  AND reg.status = 'candidate'
  AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  AND reg.model_id != CONCAT(p_run_id, '__', (SELECT cand_id FROM selected));

-- ── 持久化 selected 候选的 valid 预测（04 直接从这里读）──
CREATE OR REPLACE TABLE `data-aquarium.ashare_ads._tmp_selected_valid_preds` AS
SELECT cp.trade_date, cp.sec_code, cp.score
FROM all_candidate_preds AS cp
WHERE cp.cand_id = (SELECT cand_id FROM selected);

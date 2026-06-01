-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 03: 对每个候选模型在 valid 上预测，计算 RankIC / 分层收益，选出最优并更新 registry。

-- ── 运行参数 ──
DECLARE run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE model_id_prefix STRING DEFAULT 'ml_pv_clf_v0_bqml_logit';
DECLARE feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE horizon INT64 DEFAULT 5;
DECLARE valid_start_date DATE DEFAULT DATE '2024-01-01';
DECLARE valid_end_date DATE DEFAULT DATE '2024-12-31';

-- ── 候选评估临时表 ──
CREATE TEMP TABLE candidate_list AS
SELECT * FROM UNNEST([
  STRUCT('l1_0_l2_0' AS cand_id, 'data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_0' AS model_ref),
  STRUCT('l1_0_l2_1e_4', 'data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_1e_4'),
  STRUCT('l1_0_l2_1e_3', 'data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_1e_3'),
  STRUCT('l1_1e_5_l2_1e_4', 'data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_1e_5_l2_1e_4'),
  STRUCT('l1_1e_4_l2_1e_3', 'data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_1e_4_l2_1e_3')
]);

-- ── 各候选在 valid 上预测并写入临时表 ──
-- BigQuery 不支持动态 MODEL 引用，需逐个展开

CREATE TEMP TABLE valid_preds AS

SELECT 'l1_0_l2_0' AS cand_id, p.trade_date, p.sec_code, prob.prob AS score
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_0`,
  (SELECT trade_date, sec_code,
          list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
          mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
          drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
          turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
          pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
          log_total_mv, log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
   WHERE run_id = run_id AND split_tag = 'valid'
     AND trade_date BETWEEN valid_start_date AND valid_end_date)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob
WHERE prob.label = 1

UNION ALL

SELECT 'l1_0_l2_1e_4', p.trade_date, p.sec_code, prob.prob
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_1e_4`,
  (SELECT trade_date, sec_code,
          list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
          mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
          drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
          turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
          pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
          log_total_mv, log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
   WHERE run_id = run_id AND split_tag = 'valid'
     AND trade_date BETWEEN valid_start_date AND valid_end_date)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob
WHERE prob.label = 1

UNION ALL

SELECT 'l1_0_l2_1e_3', p.trade_date, p.sec_code, prob.prob
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_0_l2_1e_3`,
  (SELECT trade_date, sec_code,
          list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
          mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
          drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
          turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
          pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
          log_total_mv, log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
   WHERE run_id = run_id AND split_tag = 'valid'
     AND trade_date BETWEEN valid_start_date AND valid_end_date)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob
WHERE prob.label = 1

UNION ALL

SELECT 'l1_1e_5_l2_1e_4', p.trade_date, p.sec_code, prob.prob
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_1e_5_l2_1e_4`,
  (SELECT trade_date, sec_code,
          list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
          mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
          drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
          turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
          pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
          log_total_mv, log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
   WHERE run_id = run_id AND split_tag = 'valid'
     AND trade_date BETWEEN valid_start_date AND valid_end_date)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob
WHERE prob.label = 1

UNION ALL

SELECT 'l1_1e_4_l2_1e_3', p.trade_date, p.sec_code, prob.prob
FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.ml_pv_clf_v0_bqml_logit_l1_1e_4_l2_1e_3`,
  (SELECT trade_date, sec_code,
          list_age_td, ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d,
          mom_20_5, mom_60_20, vol_5d, vol_20d, vol_60d,
          drawdown_20d, hl_range_20d, amount_ma20_cny, amount_zscore_20d,
          turnover_rate, turnover_rate_free_float, turnover_rate_ma20, volume_ratio,
          pe_ttm, pb, ps_ttm, dividend_yield_ttm, ep_ttm, bp, sp_ttm,
          log_total_mv, log_circ_mv
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
   WHERE run_id = run_id AND split_tag = 'valid'
     AND trade_date BETWEEN valid_start_date AND valid_end_date)
) AS p, UNNEST(p.predicted_target_label_probs) AS prob
WHERE prob.label = 1;

-- ── 日频 RankIC：每日 score 与 fwd_ret_5d 的 Spearman 相关（用 CORR on ranks 近似）──
CREATE TEMP TABLE daily_rank_ic AS
SELECT
  v.cand_id,
  v.trade_date,
  CORR(
    RANK() OVER (PARTITION BY v.cand_id, v.trade_date ORDER BY v.score),
    RANK() OVER (PARTITION BY v.cand_id, v.trade_date ORDER BY s.fwd_ret_5d)
  ) AS rank_ic
FROM valid_preds AS v
JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
  ON v.sec_code = s.sec_code AND v.trade_date = s.trade_date
  AND s.trade_date BETWEEN valid_start_date AND valid_end_date
  AND s.feature_version = feature_version
  AND s.sample_trainable_default
GROUP BY v.cand_id, v.trade_date;

CREATE TEMP TABLE candidate_metrics AS
SELECT
  cand_id,
  AVG(rank_ic) AS rank_ic_mean,
  STDDEV_SAMP(rank_ic) AS rank_ic_std,
  SAFE_DIVIDE(AVG(rank_ic), NULLIF(STDDEV_SAMP(rank_ic), 0)) AS rank_icir,
  COUNT(*) AS n_days
FROM daily_rank_ic
GROUP BY cand_id;

-- ── 选出 rank_ic_mean 最高的候选 ──
CREATE TEMP TABLE selected AS
SELECT cand_id
FROM candidate_metrics
ORDER BY rank_ic_mean DESC
LIMIT 1;

-- ── 更新 registry：胜出 → selected，其余 → candidate_rejected ──
UPDATE `data-aquarium.ashare_ads.ads_model_registry`
SET status = 'selected',
    metrics_json = (SELECT TO_JSON_STRING(STRUCT(m.rank_ic_mean, m.rank_ic_std, m.rank_icir, m.n_days))
                    FROM candidate_metrics AS m WHERE m.cand_id = selected.cand_id)
FROM selected
WHERE model_id = CONCAT(model_id_prefix, '_', selected.cand_id)
  AND strategy_id = strategy_id;

UPDATE `data-aquarium.ashare_ads.ads_model_registry`
SET status = 'candidate_rejected',
    metrics_json = (SELECT TO_JSON_STRING(STRUCT(m.rank_ic_mean, m.rank_ic_std, m.rank_icir, m.n_days))
                    FROM candidate_metrics AS m
                    WHERE m.cand_id = REPLACE(ads_model_registry.model_id,
                                              CONCAT(model_id_prefix, '_'), ''))
WHERE strategy_id = strategy_id
  AND status = 'candidate'
  AND model_id != CONCAT(model_id_prefix, '_', (SELECT cand_id FROM selected));

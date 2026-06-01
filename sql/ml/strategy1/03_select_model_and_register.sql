-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 03: 全部候选在 valid 上预测+评估 → RankIC/AUC/log_loss/分层/TopN/按年 → 选最优 → 更新 registry。
-- 用 FOR + EXECUTE IMMEDIATE 动态引用 run-scoped 模型，不留持久临时表（04 自行重跑 selected 预测）。

DECLARE p_run_id STRING DEFAULT 's1_bqml_20260601_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_topn INT64 DEFAULT 5;  -- TopN 收益统计用，对齐组合持股数
DECLARE p_run_safe STRING;
DECLARE p_feat_sql STRING;
DECLARE p_selected_cand STRING;

SET p_run_safe = REGEXP_REPLACE(p_run_id, r'[^A-Za-z0-9_]', '_');
SET p_feat_sql = """
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.list_age_td') AS FLOAT64) AS list_age_td,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_1d') AS FLOAT64) AS ret_1d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_3d') AS FLOAT64) AS ret_3d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_5d') AS FLOAT64) AS ret_5d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_10d') AS FLOAT64) AS ret_10d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_20d') AS FLOAT64) AS ret_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ret_60d') AS FLOAT64) AS ret_60d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.mom_20_5') AS FLOAT64) AS mom_20_5,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.mom_60_20') AS FLOAT64) AS mom_60_20,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.vol_5d') AS FLOAT64) AS vol_5d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.vol_20d') AS FLOAT64) AS vol_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.vol_60d') AS FLOAT64) AS vol_60d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.drawdown_20d') AS FLOAT64) AS drawdown_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.hl_range_20d') AS FLOAT64) AS hl_range_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.amount_ma20_cny') AS FLOAT64) AS amount_ma20_cny,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.amount_zscore_20d') AS FLOAT64) AS amount_zscore_20d,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.turnover_rate') AS FLOAT64) AS turnover_rate,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.turnover_rate_free_float') AS FLOAT64) AS turnover_rate_free_float,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.turnover_rate_ma20') AS FLOAT64) AS turnover_rate_ma20,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.volume_ratio') AS FLOAT64) AS volume_ratio,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.pe_ttm') AS FLOAT64) AS pe_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.pb') AS FLOAT64) AS pb,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ps_ttm') AS FLOAT64) AS ps_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.dividend_yield_ttm') AS FLOAT64) AS dividend_yield_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.ep_ttm') AS FLOAT64) AS ep_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.bp') AS FLOAT64) AS bp,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.sp_ttm') AS FLOAT64) AS sp_ttm,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.log_total_mv') AS FLOAT64) AS log_total_mv,
  SAFE_CAST(JSON_VALUE(feature_values_json,'$.log_circ_mv') AS FLOAT64) AS log_circ_mv
""";

-- ── 候选预测与分类指标临时表 ──
CREATE TEMP TABLE candidate_preds (cand_id STRING, trade_date DATE, sec_code STRING, score FLOAT64);
CREATE TEMP TABLE candidate_eval (cand_id STRING, roc_auc FLOAT64, log_loss FLOAT64);

FOR cand IN (
  SELECT id FROM UNNEST(['l1_0_l2_0','l1_0_l2_1e_4','l1_0_l2_1e_3','l1_1e_5_l2_1e_4','l1_1e_4_l2_1e_3']) AS id
) DO
  -- valid 预测
  EXECUTE IMMEDIATE FORMAT("""
    INSERT INTO candidate_preds (cand_id, trade_date, sec_code, score)
    SELECT '%s', p.trade_date, p.sec_code, prob.prob
    FROM ML.PREDICT(MODEL `data-aquarium.ashare_ads.%s__%s`,
      (SELECT trade_date, sec_code, %s
       FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
       WHERE run_id='%s' AND split_tag='valid' AND trade_date BETWEEN '%s' AND '%s')
    ) AS p, UNNEST(p.predicted_target_label_probs) AS prob
    WHERE CAST(prob.label AS STRING) = '1'
  """, cand.id, p_run_safe, cand.id, p_feat_sql, p_run_id,
       CAST(p_valid_start AS STRING), CAST(p_valid_end AS STRING));

  -- valid AUC / log_loss（ML.EVALUATE 原生）
  EXECUTE IMMEDIATE FORMAT("""
    INSERT INTO candidate_eval (cand_id, roc_auc, log_loss)
    SELECT '%s', roc_auc, log_loss
    FROM ML.EVALUATE(MODEL `data-aquarium.ashare_ads.%s__%s`,
      (SELECT target_label, %s
       FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
       WHERE run_id='%s' AND split_tag='valid' AND trade_date BETWEEN '%s' AND '%s')
    )
  """, cand.id, p_run_safe, cand.id, p_feat_sql, p_run_id,
       CAST(p_valid_start AS STRING), CAST(p_valid_end AS STRING));
END FOR;

-- ── 预测 + 实际收益对齐，预算 rank ──
CREATE TEMP TABLE ranked_preds AS
SELECT
  cp.cand_id, cp.trade_date, cp.sec_code, cp.score,
  s.fwd_ret_5d,
  RANK() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY cp.score) AS score_rank,
  RANK() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY s.fwd_ret_5d) AS ret_rank,
  ROW_NUMBER() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY cp.score DESC, cp.sec_code) AS score_desc_rank,
  NTILE(5) OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY cp.score) AS quintile
FROM candidate_preds AS cp
JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
  ON cp.sec_code = s.sec_code AND cp.trade_date = s.trade_date
  AND s.trade_date BETWEEN p_valid_start AND p_valid_end
  AND s.feature_version = p_feature_version
  AND s.sample_trainable_default;

-- 日频 RankIC
CREATE TEMP TABLE daily_rank_ic AS
SELECT cand_id, trade_date, CORR(score_rank, ret_rank) AS rank_ic
FROM ranked_preds GROUP BY cand_id, trade_date;

-- 按年 RankIC
CREATE TEMP TABLE yearly_rank_ic AS
SELECT cand_id, EXTRACT(YEAR FROM trade_date) AS yr, AVG(rank_ic) AS rank_ic_year
FROM daily_rank_ic GROUP BY cand_id, yr;

-- 分层收益（quintile 平均）
CREATE TEMP TABLE layer_spread AS
SELECT cand_id,
  AVG(IF(quintile = 5, fwd_ret_5d, NULL)) - AVG(IF(quintile = 1, fwd_ret_5d, NULL)) AS top_minus_bottom
FROM ranked_preds GROUP BY cand_id;

-- TopN 未来收益（每日 score 前 N 的 fwd_ret_5d 均值）
CREATE TEMP TABLE topn_ret AS
SELECT cand_id, AVG(fwd_ret_5d) AS topn_fwd_ret_mean
FROM ranked_preds WHERE score_desc_rank <= p_topn
GROUP BY cand_id;

-- 汇总
CREATE TEMP TABLE candidate_metrics AS
SELECT
  ic.cand_id,
  AVG(ic.rank_ic) AS rank_ic_mean,
  STDDEV_SAMP(ic.rank_ic) AS rank_ic_std,
  SAFE_DIVIDE(AVG(ic.rank_ic), NULLIF(STDDEV_SAMP(ic.rank_ic), 0)) AS rank_icir,
  COUNT(*) AS n_days,
  ANY_VALUE(ev.roc_auc) AS roc_auc,
  ANY_VALUE(ev.log_loss) AS log_loss,
  ANY_VALUE(ls.top_minus_bottom) AS layer_spread,
  ANY_VALUE(tn.topn_fwd_ret_mean) AS topn_fwd_ret_mean,
  (SELECT COUNT(*) FROM ranked_preds rp WHERE rp.cand_id = ic.cand_id) AS n_samples,
  (SELECT COUNTIF(rp.score IS NULL) FROM ranked_preds rp WHERE rp.cand_id = ic.cand_id) AS n_missing,
  (SELECT TO_JSON_STRING(ARRAY_AGG(STRUCT(y.yr, y.rank_ic_year) ORDER BY y.yr))
   FROM yearly_rank_ic y WHERE y.cand_id = ic.cand_id) AS rank_ic_by_year_json
FROM daily_rank_ic AS ic
LEFT JOIN candidate_eval AS ev ON ic.cand_id = ev.cand_id
LEFT JOIN layer_spread AS ls ON ic.cand_id = ls.cand_id
LEFT JOIN topn_ret AS tn ON ic.cand_id = tn.cand_id
GROUP BY ic.cand_id;

-- ── 选优：rank_ic_mean → layer_spread → log_loss ──
SET p_selected_cand = (
  SELECT cand_id FROM candidate_metrics
  ORDER BY rank_ic_mean DESC, layer_spread DESC, log_loss ASC
  LIMIT 1
);

-- ── 更新 registry：selected ──
UPDATE `data-aquarium.ashare_ads.ads_model_registry` AS reg
SET reg.status = 'selected',
    reg.metrics_json = (
      SELECT TO_JSON_STRING(STRUCT(
        m.rank_ic_mean, m.rank_ic_std, m.rank_icir, m.n_days,
        m.roc_auc, m.log_loss, m.layer_spread, m.topn_fwd_ret_mean,
        m.n_samples, m.n_missing,
        SAFE_DIVIDE(m.n_missing, NULLIF(m.n_samples,0)) AS missing_rate,
        m.rank_ic_by_year_json AS rank_ic_by_year,
        'selected: highest valid rank_ic_mean (tie-break layer_spread, log_loss)' AS select_reason))
      FROM candidate_metrics AS m WHERE m.cand_id = p_selected_cand)
WHERE reg.model_id = CONCAT(p_run_safe, '__', p_selected_cand)
  AND reg.strategy_id = p_strategy_id
  AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id;

-- ── 更新 registry：rejected ──
UPDATE `data-aquarium.ashare_ads.ads_model_registry` AS reg
SET reg.status = 'candidate_rejected',
    reg.metrics_json = (
      SELECT TO_JSON_STRING(STRUCT(
        m.rank_ic_mean, m.rank_ic_std, m.rank_icir, m.n_days,
        m.roc_auc, m.log_loss, m.layer_spread, m.topn_fwd_ret_mean,
        m.n_samples, m.n_missing,
        m.rank_ic_by_year_json AS rank_ic_by_year))
      FROM candidate_metrics AS m
      WHERE m.cand_id = REPLACE(reg.model_id, CONCAT(p_run_safe, '__'), ''))
WHERE reg.strategy_id = p_strategy_id
  AND reg.status = 'candidate'
  AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  AND reg.model_id != CONCAT(p_run_safe, '__', p_selected_cand);

-- BigQuery Standard SQL · Strategy 1 BQML Runner
-- 03: 全部候选在 valid 上预测+评估 → RankIC/AUC/log_loss/分层/TopN/按年 → 选最优 → 更新 registry。
-- 用 FOR + EXECUTE IMMEDIATE 动态引用 run-scoped 模型，不留持久临时表（04 自行重跑 selected 预测）。
-- Score orientation: 对每个候选同时评估 raw 和 reversed score 的 RankIC，自动选择更优方向。

DECLARE p_run_id STRING DEFAULT 's1_bqml_livepool_oriented_20260603_01';
DECLARE p_strategy_id STRING DEFAULT 'ml_pv_clf_v0';
DECLARE p_feature_version STRING DEFAULT 'strategy1_pv_v0_20260601';
DECLARE p_valid_start DATE DEFAULT DATE '2024-01-01';
DECLARE p_valid_end DATE DEFAULT DATE '2024-12-31';
DECLARE p_topn INT64 DEFAULT 5;  -- TopN 收益统计用，对齐组合持股数
DECLARE p_run_safe STRING;
DECLARE p_feat_sql STRING;
DECLARE p_selected_cand STRING;
DECLARE p_selected_orientation STRING;

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

  -- valid AUC / log_loss（ML.EVALUATE 原生，输入必须过滤到 label-available subset）
  EXECUTE IMMEDIATE FORMAT("""
    INSERT INTO candidate_eval (cand_id, roc_auc, log_loss)
    SELECT '%s', roc_auc, log_loss
    FROM ML.EVALUATE(MODEL `data-aquarium.ashare_ads.%s__%s`,
      (SELECT target_label, %s
       FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily`
       WHERE run_id='%s' AND split_tag='valid' AND trade_date BETWEEN '%s' AND '%s'
         AND target_label IS NOT NULL)
    )
  """, cand.id, p_run_safe, cand.id, p_feat_sql, p_run_id,
       CAST(p_valid_start AS STRING), CAST(p_valid_end AS STRING));
END FOR;

-- ── 预测 + 实际收益对齐，预算 rank ──
-- 事后评价：必须在 label-available subset 上计算（PRD-20260602-05 FR-LIVE-3）
-- 同时计算 raw 和 reversed score 的 rank，用于 orientation 决策。
CREATE TEMP TABLE ranked_preds AS
SELECT
  cp.cand_id, cp.trade_date, cp.sec_code, cp.score AS raw_score,
  1.0 - cp.score AS reversed_score,
  s.fwd_ret_5d,
  -- raw score ranks
  RANK() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY cp.score) AS raw_score_rank,
  RANK() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY s.fwd_ret_5d) AS ret_rank,
  ROW_NUMBER() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY cp.score DESC, cp.sec_code) AS raw_score_desc_rank,
  NTILE(5) OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY cp.score) AS raw_quintile,
  -- reversed score ranks
  RANK() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY (1.0 - cp.score)) AS rev_score_rank,
  ROW_NUMBER() OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY (1.0 - cp.score) DESC, cp.sec_code) AS rev_score_desc_rank,
  NTILE(5) OVER (PARTITION BY cp.cand_id, cp.trade_date ORDER BY (1.0 - cp.score)) AS rev_quintile
FROM candidate_preds AS cp
JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
  ON cp.sec_code = s.sec_code AND cp.trade_date = s.trade_date
  AND s.trade_date BETWEEN p_valid_start AND p_valid_end
  AND s.feature_version = p_feature_version
WHERE s.label_valid_5d
  AND s.fwd_xs_ret_5d IS NOT NULL;

-- 日频 RankIC — raw
CREATE TEMP TABLE daily_rank_ic_raw AS
SELECT cand_id, trade_date, CORR(raw_score_rank, ret_rank) AS rank_ic
FROM ranked_preds GROUP BY cand_id, trade_date;

-- 日频 RankIC — reversed
CREATE TEMP TABLE daily_rank_ic_rev AS
SELECT cand_id, trade_date, CORR(rev_score_rank, ret_rank) AS rank_ic
FROM ranked_preds GROUP BY cand_id, trade_date;

-- 分层收益 — raw quintile（用于 orientation 决策）
CREATE TEMP TABLE raw_layer_spread AS
SELECT cand_id,
  AVG(IF(raw_quintile = 5, fwd_ret_5d, NULL)) - AVG(IF(raw_quintile = 1, fwd_ret_5d, NULL)) AS raw_top_minus_bottom
FROM ranked_preds GROUP BY cand_id;

-- 分层收益 — reversed quintile（用于 orientation 决策）
CREATE TEMP TABLE rev_layer_spread AS
SELECT cand_id,
  AVG(IF(rev_quintile = 5, fwd_ret_5d, NULL)) - AVG(IF(rev_quintile = 1, fwd_ret_5d, NULL)) AS rev_top_minus_bottom
FROM ranked_preds GROUP BY cand_id;

-- ── Score orientation 决策：PRD §6.2 保守三条件规则 ──
-- raw_rank_ic <= -0.03 AND reverse_rank_ic >= 0.03 AND reverse bucket lift > raw bucket lift
-- 否则默认 identity。
CREATE TEMP TABLE candidate_orientation AS
SELECT
  r.cand_id,
  AVG(r.rank_ic) AS raw_rank_ic_mean,
  v.rev_rank_ic_mean,
  rls.raw_top_minus_bottom,
  vls.rev_top_minus_bottom,
  CASE
    WHEN AVG(r.rank_ic) <= -0.03
      AND v.rev_rank_ic_mean >= 0.03
      AND COALESCE(vls.rev_top_minus_bottom, 0) > COALESCE(rls.raw_top_minus_bottom, 0)
    THEN 'reverse_probability'
    ELSE 'identity'
  END AS score_orientation,
  CASE
    WHEN AVG(r.rank_ic) <= -0.03
      AND v.rev_rank_ic_mean >= 0.03
      AND COALESCE(vls.rev_top_minus_bottom, 0) > COALESCE(rls.raw_top_minus_bottom, 0)
    THEN 'raw_rank_ic <= -0.03 AND reversed >= 0.03 AND reversed bucket lift better'
    WHEN AVG(r.rank_ic) <= -0.03 AND v.rev_rank_ic_mean >= 0.03
    THEN 'raw_rank_ic <= -0.03 AND reversed >= 0.03 BUT bucket lift not better — kept identity'
    WHEN AVG(r.rank_ic) <= -0.03
    THEN 'raw_rank_ic <= -0.03 BUT reversed not >= 0.03 — kept identity'
    WHEN ABS(AVG(r.rank_ic)) < 0.03 AND ABS(v.rev_rank_ic_mean) < 0.03
    THEN 'both RankIC near zero — weak signal, kept identity'
    ELSE 'raw_rank_ic non-negative — kept identity'
  END AS orientation_decision_reason
FROM daily_rank_ic_raw AS r
JOIN (
  SELECT cand_id, AVG(rank_ic) AS rev_rank_ic_mean
  FROM daily_rank_ic_rev GROUP BY cand_id
) AS v ON r.cand_id = v.cand_id
LEFT JOIN raw_layer_spread AS rls ON r.cand_id = rls.cand_id
LEFT JOIN rev_layer_spread AS vls ON r.cand_id = vls.cand_id
GROUP BY r.cand_id, v.rev_rank_ic_mean, rls.raw_top_minus_bottom, vls.rev_top_minus_bottom;

-- ── 使用 oriented score 重新计算评估指标 ──
-- 先为每个候选确定 oriented_score（如果反向则用 1-raw）
CREATE TEMP TABLE oriented_ranked_preds AS
SELECT
  rp.*,
  co.score_orientation,
  IF(co.score_orientation = 'reverse_probability', rp.reversed_score, rp.raw_score) AS oriented_score,
  IF(co.score_orientation = 'reverse_probability', rp.rev_score_rank, rp.raw_score_rank) AS oriented_score_rank,
  IF(co.score_orientation = 'reverse_probability', rp.rev_score_desc_rank, rp.raw_score_desc_rank) AS oriented_score_desc_rank,
  IF(co.score_orientation = 'reverse_probability', rp.rev_quintile, rp.raw_quintile) AS oriented_quintile
FROM ranked_preds AS rp
JOIN candidate_orientation AS co ON rp.cand_id = co.cand_id;

-- 日频 oriented RankIC
CREATE TEMP TABLE daily_rank_ic AS
SELECT cand_id, trade_date, CORR(oriented_score_rank, ret_rank) AS rank_ic
FROM oriented_ranked_preds GROUP BY cand_id, trade_date;

-- 按年 RankIC
CREATE TEMP TABLE yearly_rank_ic AS
SELECT cand_id, EXTRACT(YEAR FROM trade_date) AS yr, AVG(rank_ic) AS rank_ic_year
FROM daily_rank_ic GROUP BY cand_id, yr;

-- 分层收益（quintile 平均）— 使用 oriented quintile
CREATE TEMP TABLE layer_spread AS
SELECT cand_id,
  AVG(IF(oriented_quintile = 5, fwd_ret_5d, NULL)) - AVG(IF(oriented_quintile = 1, fwd_ret_5d, NULL)) AS top_minus_bottom
FROM oriented_ranked_preds GROUP BY cand_id;

-- TopN 未来收益（每日 oriented score 前 N 的 fwd_ret_5d 均值）
CREATE TEMP TABLE topn_ret AS
SELECT cand_id, AVG(fwd_ret_5d) AS topn_fwd_ret_mean
FROM oriented_ranked_preds WHERE oriented_score_desc_rank <= p_topn
GROUP BY cand_id;

-- 样本量/缺失计数 + 预测池覆盖统计（PRD-20260602-05 FR-LIVE-3）
CREATE TEMP TABLE sample_counts AS
SELECT
  cp.cand_id,
  COUNT(*) AS n_samples,
  COUNTIF(cp.score IS NULL) AS n_missing,
  -- valid full prediction pool（来自 01 的 live-available mask）
  (SELECT COUNT(DISTINCT tp.sec_code || CAST(tp.trade_date AS STRING))
   FROM `data-aquarium.ashare_ads.ads_ml_training_panel_daily` AS tp
   WHERE tp.run_id = p_run_id AND tp.split_tag = 'valid'
     AND tp.trade_date BETWEEN p_valid_start AND p_valid_end) AS valid_prediction_rows,
  -- valid label-available eval rows
  COUNT(*) AS valid_eval_rows
FROM candidate_preds AS cp
JOIN `data-aquarium.ashare_dws.dws_stock_sample_daily` AS s
  ON cp.sec_code = s.sec_code AND cp.trade_date = s.trade_date
  AND s.trade_date BETWEEN p_valid_start AND p_valid_end
  AND s.feature_version = p_feature_version
WHERE s.label_valid_5d AND s.fwd_xs_ret_5d IS NOT NULL
GROUP BY cp.cand_id;

-- 按年 RankIC 的 JSON 串（预聚合，避免汇总里写相关子查询）
CREATE TEMP TABLE yearly_rank_ic_json AS
SELECT cand_id,
  TO_JSON_STRING(ARRAY_AGG(STRUCT(yr, rank_ic_year) ORDER BY yr)) AS rank_ic_by_year_json
FROM yearly_rank_ic GROUP BY cand_id;

-- 汇总（全部用 LEFT JOIN 预聚合表，BigQuery 不支持引用其它表的相关子查询）
CREATE TEMP TABLE candidate_metrics AS
SELECT
  ic.cand_id,
  AVG(ic.rank_ic) AS rank_ic_mean,  -- oriented RankIC
  STDDEV_SAMP(ic.rank_ic) AS rank_ic_std,
  SAFE_DIVIDE(AVG(ic.rank_ic), NULLIF(STDDEV_SAMP(ic.rank_ic), 0)) AS rank_icir,
  COUNT(*) AS n_days,
  ANY_VALUE(ev.roc_auc) AS roc_auc,
  ANY_VALUE(ev.log_loss) AS log_loss,
  ANY_VALUE(ls.top_minus_bottom) AS layer_spread,
  ANY_VALUE(tn.topn_fwd_ret_mean) AS topn_fwd_ret_mean,
  ANY_VALUE(sc.n_samples) AS n_samples,
  ANY_VALUE(sc.n_missing) AS n_missing,
  ANY_VALUE(yj.rank_ic_by_year_json) AS rank_ic_by_year_json,
  ANY_VALUE(co.score_orientation) AS score_orientation,
  ANY_VALUE(co.raw_rank_ic_mean) AS raw_valid_rank_ic_mean,
  ANY_VALUE(co.rev_rank_ic_mean) AS rev_valid_rank_ic_mean,
  ANY_VALUE(co.raw_top_minus_bottom) AS raw_valid_top_minus_bottom,
  ANY_VALUE(co.rev_top_minus_bottom) AS rev_valid_top_minus_bottom,
  ANY_VALUE(co.orientation_decision_reason) AS orientation_decision_reason
FROM daily_rank_ic AS ic
LEFT JOIN candidate_eval AS ev ON ic.cand_id = ev.cand_id
LEFT JOIN layer_spread AS ls ON ic.cand_id = ls.cand_id
LEFT JOIN topn_ret AS tn ON ic.cand_id = tn.cand_id
LEFT JOIN sample_counts AS sc ON ic.cand_id = sc.cand_id
LEFT JOIN yearly_rank_ic_json AS yj ON ic.cand_id = yj.cand_id
LEFT JOIN candidate_orientation AS co ON ic.cand_id = co.cand_id
GROUP BY ic.cand_id;

-- ── 选优：PRD §6.3 oriented rank_ic_mean → topn_fwd_ret_mean → roc_auc ──
SET p_selected_cand = (
  SELECT cand_id FROM candidate_metrics
  ORDER BY rank_ic_mean DESC, topn_fwd_ret_mean DESC, roc_auc DESC
  LIMIT 1
);

SET p_selected_orientation = (
  SELECT score_orientation FROM candidate_metrics WHERE cand_id = p_selected_cand
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
        -- PRD-20260602-05: prediction pool coverage metrics
        sc.valid_prediction_rows,
        sc.valid_eval_rows,
        SAFE_DIVIDE(sc.valid_eval_rows, NULLIF(sc.valid_prediction_rows, 0)) AS valid_eval_coverage,
        CASE
          WHEN SAFE_DIVIDE(sc.valid_eval_rows, NULLIF(sc.valid_prediction_rows, 0)) >= 0.50 THEN 'ok'
          WHEN SAFE_DIVIDE(sc.valid_eval_rows, NULLIF(sc.valid_prediction_rows, 0)) >= 0.30 THEN 'warning'
          ELSE 'critical'
        END AS valid_eval_coverage_status,
        -- Score orientation calibration
        'positive_class_probability' AS score_source,
        m.score_orientation,
        m.raw_valid_rank_ic_mean,
        m.rev_valid_rank_ic_mean AS reversed_valid_rank_ic_mean,
        m.rank_ic_mean AS oriented_valid_rank_ic_mean,
        m.orientation_decision_reason,
        'valid' AS orientation_decision_split,
        CONCAT('selected: highest oriented valid rank_ic_mean (orientation=',
               m.score_orientation, ', tie-break topn_fwd_ret_mean, roc_auc)') AS select_reason))
      FROM candidate_metrics AS m
      LEFT JOIN sample_counts AS sc ON sc.cand_id = m.cand_id
      WHERE m.cand_id = p_selected_cand)
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
        m.rank_ic_by_year_json AS rank_ic_by_year,
        sc.valid_prediction_rows,
        sc.valid_eval_rows,
        SAFE_DIVIDE(sc.valid_eval_rows, NULLIF(sc.valid_prediction_rows, 0)) AS valid_eval_coverage,
        'positive_class_probability' AS score_source,
        m.score_orientation,
        m.raw_valid_rank_ic_mean,
        m.rev_valid_rank_ic_mean AS reversed_valid_rank_ic_mean,
        m.rank_ic_mean AS oriented_valid_rank_ic_mean,
        m.orientation_decision_reason,
        'valid' AS orientation_decision_split))
      FROM candidate_metrics AS m
      LEFT JOIN sample_counts AS sc ON sc.cand_id = m.cand_id
      WHERE m.cand_id = REPLACE(reg.model_id, CONCAT(p_run_safe, '__'), ''))
WHERE reg.strategy_id = p_strategy_id
  AND reg.status = 'candidate'
  AND JSON_VALUE(reg.model_params_json, '$.run_id') = p_run_id
  AND reg.model_id != CONCAT(p_run_safe, '__', p_selected_cand);

-- 文档维护：GPT-5（最近更新 2026-06-02）
-- BigQuery Standard SQL
-- OQ-006 单位契约表：ods_field_unit_map
-- 作为 ODS -> DWD 单位换算的唯一事实来源。
-- 本脚本幂等：CREATE OR REPLACE TABLE 重建 schema，再全量 INSERT。

CREATE OR REPLACE TABLE `data-aquarium.ashare_meta.ods_field_unit_map` (
  source_system STRING NOT NULL OPTIONS(description="数据来源系统，当前固定 tushare"),
  endpoint STRING NOT NULL OPTIONS(description="Tushare endpoint 名，如 daily、daily_basic"),
  ods_table STRING NOT NULL OPTIONS(description="ODS 表名"),
  source_field STRING OPTIONS(description="ODS 原字段名；派生字段可写主要源字段或 NULL"),
  semantic_type STRING OPTIONS(description="语义类型：amount / volume / share / market_value / ratio / price / per_share"),
  source_unit STRING OPTIONS(description="原单位，如 手、千元、万股、万元、元、元/股、percent、ratio、multiple"),
  canonical_unit STRING OPTIONS(description="DWD 标准单位，如 元、股、元/股、percent、ratio、multiple、指数点位"),
  multiplier NUMERIC OPTIONS(description="ODS 原值乘以该系数得到 DWD 标准字段值"),
  dwd_table STRING NOT NULL OPTIONS(description="消费该映射的 DWD 表"),
  dwd_field STRING NOT NULL OPTIONS(description="DWD 标准字段名"),
  raw_field_kept BOOL OPTIONS(description="是否保留源单位字段"),
  raw_field_name STRING OPTIONS(description="源单位保留字段名，如 amount_k_cny、volume_lot"),
  verification_status STRING NOT NULL OPTIONS(description="verified / pending / not_applicable"),
  naming_exception_type STRING OPTIONS(description="命名例外类型：legacy_unsuffixed / source_name_passthrough"),
  naming_exception_expires_at DATE OPTIONS(description="命名例外计划清理日期"),
  evidence STRING OPTIONS(description="官方文档 URL、截图记录、实测校验说明或内部审计链接"),
  verified_at DATE OPTIONS(description="核对日期"),
  verified_by STRING OPTIONS(description="核对者或 Agent 模型名"),
  notes STRING OPTIONS(description="特殊口径说明")
)
OPTIONS (
  description = 'OQ-006 单位契约表：endpoint + source_field 粒度的 ODS->DWD 单位换算唯一事实来源。verified 字段才可作为标准 DWD 输出。'
);

-- ============================================================
-- P0 已落库字段：dwd_stock_eod_price（含 raw 保留字段）
-- ============================================================
INSERT INTO `data-aquarium.ashare_meta.ods_field_unit_map`
VALUES
  -- daily: 成交量 / 成交额（核心换算）
  ('tushare', 'daily', 'ods_tushare_daily', 'vol', 'volume', '手', '股', 100, 'dwd_stock_eod_price', 'volume_share', TRUE, 'volume_lot', 'verified', NULL, NULL, 'Tushare Pro daily 接口文档 + 数据自洽：amount_cny ~= close * volume_share', DATE '2026-06-02', 'GPT-5', 'daily.vol 手->股'),
  ('tushare', 'daily', 'ods_tushare_daily', 'vol', 'volume', '手', '手', 1, 'dwd_stock_eod_price', 'volume_lot', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily 接口文档', DATE '2026-06-02', 'GPT-5', '保留源单位：手'),
  ('tushare', 'daily', 'ods_tushare_daily', 'amount', 'amount', '千元', '元', 1000, 'dwd_stock_eod_price', 'amount_cny', TRUE, 'amount_k_cny', 'verified', NULL, NULL, 'Tushare Pro daily 接口文档 + 数据自洽：amount_cny ~= close * volume_share', DATE '2026-06-02', 'GPT-5', 'daily.amount 千元->元'),
  ('tushare', 'daily', 'ods_tushare_daily', 'amount', 'amount', '千元', '千元', 1, 'dwd_stock_eod_price', 'amount_k_cny', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily 接口文档', DATE '2026-06-02', 'GPT-5', '保留源单位：千元'),
  -- daily: 价格字段
  ('tushare', 'daily', 'ods_tushare_daily', 'open', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'open', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'daily', 'ods_tushare_daily', 'high', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'high', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'daily', 'ods_tushare_daily', 'low', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'low', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'daily', 'ods_tushare_daily', 'close', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'close', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'daily', 'ods_tushare_daily', 'pre_close', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'pre_close', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'daily', 'ods_tushare_daily', 'change', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'change', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'daily', 'ods_tushare_daily', 'pct_chg', 'ratio', 'percent', 'percent', 1, 'dwd_stock_eod_price', 'pct_chg', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily 接口文档', DATE '2026-06-02', 'GPT-5', '日涨跌幅，百分比'),
  -- daily: 派生字段
  ('tushare', 'daily', 'ods_tushare_daily', 'close', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'open_hfq', FALSE, NULL, 'not_applicable', NULL, NULL, '派生：open * adj_factor', DATE '2026-06-02', 'GPT-5', '后复权价格，非直接 ODS 换算'),
  ('tushare', 'daily', 'ods_tushare_daily', 'close', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'high_hfq', FALSE, NULL, 'not_applicable', NULL, NULL, '派生：high * adj_factor', DATE '2026-06-02', 'GPT-5', '后复权价格，非直接 ODS 换算'),
  ('tushare', 'daily', 'ods_tushare_daily', 'close', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'low_hfq', FALSE, NULL, 'not_applicable', NULL, NULL, '派生：low * adj_factor', DATE '2026-06-02', 'GPT-5', '后复权价格，非直接 ODS 换算'),
  ('tushare', 'daily', 'ods_tushare_daily', 'close', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'close_hfq', FALSE, NULL, 'not_applicable', NULL, NULL, '派生：close * adj_factor', DATE '2026-06-02', 'GPT-5', '后复权价格，非直接 ODS 换算'),
  ('tushare', 'daily', 'ods_tushare_daily', 'close', 'ratio', 'ratio', 'ratio', 1, 'dwd_stock_eod_price', 'ret_1d', FALSE, NULL, 'not_applicable', NULL, NULL, '派生：基于 close_hfq 的窗口收益率', DATE '2026-06-02', 'GPT-5', '非直接 ODS 换算'),
  -- stk_limit: 涨跌停价
  ('tushare', 'stk_limit', 'ods_tushare_stk_limit', 'up_limit', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'up_limit', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro stk_limit 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'stk_limit', 'ods_tushare_stk_limit', 'down_limit', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_price', 'down_limit', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro stk_limit 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  -- adj_factor
  ('tushare', 'adj_factor', 'ods_tushare_adj_factor', 'adj_factor', 'ratio', 'ratio', 'ratio', 1, 'dwd_stock_eod_price', 'adj_factor', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro adj_factor 接口文档', DATE '2026-06-02', 'GPT-5', '后复权因子，无量纲');

-- ============================================================
-- P0 已落库字段：dwd_stock_eod_valuation（含 raw 保留字段）
-- ============================================================
INSERT INTO `data-aquarium.ashare_meta.ods_field_unit_map`
VALUES
  -- daily_basic: 股本字段（万股 -> 股）
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'total_share', 'share', '万股', '股', 10000, 'dwd_stock_eod_valuation', 'total_share', TRUE, 'total_share_10k', 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档 + 数据自洽：total_mv_cny ~= close * total_share', DATE '2026-06-02', 'GPT-5', 'daily_basic.total_share 万股->股'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'total_share', 'share', '万股', '万股', 1, 'dwd_stock_eod_valuation', 'total_share_10k', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '保留源单位：万股'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'float_share', 'share', '万股', '股', 10000, 'dwd_stock_eod_valuation', 'float_share', TRUE, 'float_share_10k', 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档 + 数据自洽：circ_mv_cny ~= close * float_share', DATE '2026-06-02', 'GPT-5', 'daily_basic.float_share 万股->股'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'float_share', 'share', '万股', '万股', 1, 'dwd_stock_eod_valuation', 'float_share_10k', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '保留源单位：万股'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'free_share', 'share', '万股', '股', 10000, 'dwd_stock_eod_valuation', 'free_share', TRUE, 'free_share_10k', 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', 'daily_basic.free_share 万股->股'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'free_share', 'share', '万股', '万股', 1, 'dwd_stock_eod_valuation', 'free_share_10k', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '保留源单位：万股'),
  -- daily_basic: 市值字段（万元 -> 元）
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'total_mv', 'market_value', '万元', '元', 10000, 'dwd_stock_eod_valuation', 'total_mv_cny', TRUE, 'total_mv_10k_cny', 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档 + 数据自洽：total_mv_cny ~= close * total_share', DATE '2026-06-02', 'GPT-5', 'daily_basic.total_mv 万元->元'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'total_mv', 'market_value', '万元', '万元', 1, 'dwd_stock_eod_valuation', 'total_mv_10k_cny', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '保留源单位：万元'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'circ_mv', 'market_value', '万元', '元', 10000, 'dwd_stock_eod_valuation', 'circ_mv_cny', TRUE, 'circ_mv_10k_cny', 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档 + 数据自洽：circ_mv_cny ~= close * float_share', DATE '2026-06-02', 'GPT-5', 'daily_basic.circ_mv 万元->元'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'circ_mv', 'market_value', '万元', '万元', 1, 'dwd_stock_eod_valuation', 'circ_mv_10k_cny', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '保留源单位：万元'),
  -- daily_basic: 价格 / 比率字段
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'close', 'price', '元/股', '元/股', 1, 'dwd_stock_eod_valuation', 'close', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'turnover_rate', 'ratio', 'percent', 'percent', 1, 'dwd_stock_eod_valuation', 'turnover_rate', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '换手率，百分比'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'turnover_rate_f', 'ratio', 'percent', 'percent', 1, 'dwd_stock_eod_valuation', 'turnover_rate_free_float', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '自由流通股换手率，百分比'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'volume_ratio', 'ratio', 'ratio', 'ratio', 1, 'dwd_stock_eod_valuation', 'volume_ratio', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '量比，无量纲'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'pe', 'ratio', 'multiple', 'multiple', 1, 'dwd_stock_eod_valuation', 'pe', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '市盈率，倍数'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'pe_ttm', 'ratio', 'multiple', 'multiple', 1, 'dwd_stock_eod_valuation', 'pe_ttm', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '滚动市盈率，倍数'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'pb', 'ratio', 'multiple', 'multiple', 1, 'dwd_stock_eod_valuation', 'pb', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '市净率，倍数'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'ps', 'ratio', 'multiple', 'multiple', 1, 'dwd_stock_eod_valuation', 'ps', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '市销率，倍数'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'ps_ttm', 'ratio', 'multiple', 'multiple', 1, 'dwd_stock_eod_valuation', 'ps_ttm', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '滚动市销率，倍数'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'dv_ratio', 'ratio', 'percent', 'percent', 1, 'dwd_stock_eod_valuation', 'dividend_yield', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', '股息率，百分比'),
  ('tushare', 'daily_basic', 'ods_tushare_daily_basic', 'dv_ttm', 'ratio', 'percent', 'percent', 1, 'dwd_stock_eod_valuation', 'dividend_yield_ttm', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro daily_basic 接口文档', DATE '2026-06-02', 'GPT-5', 'TTM 股息率，百分比');

-- ============================================================
-- P0 已落库字段：dwd_index_eod
-- ============================================================
INSERT INTO `data-aquarium.ashare_meta.ods_field_unit_map`
VALUES
  -- index_daily: 成交量 / 成交额（修复换算）
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'vol', 'volume', '手', '股', 100, 'dwd_index_eod', 'volume_share', TRUE, 'volume_lot', 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档 + 数据自洽', DATE '2026-06-02', 'GPT-5', 'index_daily.vol 手->股；OQ-006 修复换算'),
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'vol', 'volume', '手', '手', 1, 'dwd_index_eod', 'volume_lot', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档', DATE '2026-06-02', 'GPT-5', '保留源单位：手'),
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'amount', 'amount', '千元', '元', 1000, 'dwd_index_eod', 'amount_cny', TRUE, 'amount_k_cny', 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档 + 数据自洽', DATE '2026-06-02', 'GPT-5', 'index_daily.amount 千元->元；OQ-006 修复换算'),
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'amount', 'amount', '千元', '千元', 1, 'dwd_index_eod', 'amount_k_cny', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档', DATE '2026-06-02', 'GPT-5', '保留源单位：千元'),
  -- index_daily: 指数点位字段
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'open', 'price', '指数点位', '指数点位', 1, 'dwd_index_eod', 'open', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'high', 'price', '指数点位', '指数点位', 1, 'dwd_index_eod', 'high', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'low', 'price', '指数点位', '指数点位', 1, 'dwd_index_eod', 'low', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'close', 'price', '指数点位', '指数点位', 1, 'dwd_index_eod', 'close', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'pre_close', 'price', '指数点位', '指数点位', 1, 'dwd_index_eod', 'pre_close', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'change', 'price', '指数点位', '指数点位', 1, 'dwd_index_eod', 'change', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档', DATE '2026-06-02', 'GPT-5', NULL),
  ('tushare', 'index_daily', 'ods_tushare_index_daily', 'pct_chg', 'ratio', 'percent', 'percent', 1, 'dwd_index_eod', 'pct_chg', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_daily 接口文档', DATE '2026-06-02', 'GPT-5', '指数涨跌幅，百分比'),
  -- index_dailybasic: 市值 / 股本（元/股，无换算）
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'total_mv', 'market_value', '元', '元', 1, 'dwd_index_eod', 'total_mv_cny', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档 + 与股票 daily_basic 区分：指数市值已为元', DATE '2026-06-02', 'GPT-5', 'index_dailybasic.total_mv 单位为元，不同于 daily_basic 的万元'),
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'float_mv', 'market_value', '元', '元', 1, 'dwd_index_eod', 'float_mv_cny', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档', DATE '2026-06-02', 'GPT-5', 'index_dailybasic.float_mv 单位为元'),
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'total_share', 'share', '股', '股', 1, 'dwd_index_eod', 'total_share', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档', DATE '2026-06-02', 'GPT-5', 'index_dailybasic.total_share 单位为股'),
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'float_share', 'share', '股', '股', 1, 'dwd_index_eod', 'float_share', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档', DATE '2026-06-02', 'GPT-5', 'index_dailybasic.float_share 单位为股'),
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'free_share', 'share', '股', '股', 1, 'dwd_index_eod', 'free_share', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档', DATE '2026-06-02', 'GPT-5', 'index_dailybasic.free_share 单位为股'),
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'turnover_rate', 'ratio', 'percent', 'percent', 1, 'dwd_index_eod', 'turnover_rate', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档', DATE '2026-06-02', 'GPT-5', '换手率，百分比'),
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'turnover_rate_f', 'ratio', 'percent', 'percent', 1, 'dwd_index_eod', 'turnover_rate_free_float', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档', DATE '2026-06-02', 'GPT-5', '自由流通股换手率，百分比'),
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'pe', 'ratio', 'multiple', 'multiple', 1, 'dwd_index_eod', 'pe', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档', DATE '2026-06-02', 'GPT-5', '市盈率，倍数'),
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'pe_ttm', 'ratio', 'multiple', 'multiple', 1, 'dwd_index_eod', 'pe_ttm', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档', DATE '2026-06-02', 'GPT-5', '滚动市盈率，倍数'),
  ('tushare', 'index_dailybasic', 'ods_tushare_index_dailybasic', 'pb', 'ratio', 'multiple', 'multiple', 1, 'dwd_index_eod', 'pb', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro index_dailybasic 接口文档', DATE '2026-06-02', 'GPT-5', '市净率，倍数');

-- ============================================================
-- P0 已落库字段：dwd_fin_indicator
-- ============================================================
INSERT INTO `data-aquarium.ashare_meta.ods_field_unit_map`
VALUES
  -- 每股指标
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'eps', 'per_share', '元/股', '元/股', 1, 'dwd_fin_indicator', 'eps', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '基本每股收益'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'dt_eps', 'per_share', '元/股', '元/股', 1, 'dwd_fin_indicator', 'dt_eps', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '稀释每股收益'),
  -- 金额指标
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'netdebt', 'amount', '元', '元', 1, 'dwd_fin_indicator', 'net_debt', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '净债务'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'working_capital', 'amount', '元', '元', 1, 'dwd_fin_indicator', 'working_capital', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '营运资本'),
  -- 比率指标（百分比）
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'netprofit_margin', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'netprofit_margin', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '销售净利率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'grossprofit_margin', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'grossprofit_margin', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '销售毛利率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'roe', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'roe', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '净资产收益率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'roe_dt', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'roe_deducted', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '扣非净资产收益率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'roa', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'roa', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '总资产收益率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'roic', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'roic', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '投入资本回报率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'debt_to_assets', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'debt_to_assets', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '资产负债率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'q_netprofit_margin', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'q_netprofit_margin', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '单季度销售净利率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'q_gsprofit_margin', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'q_grossprofit_margin', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '单季度销售毛利率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'q_roe', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'q_roe', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '单季度净资产收益率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'q_dt_roe', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'q_roe_deducted', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '单季度扣非净资产收益率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'basic_eps_yoy', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'basic_eps_yoy', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '基本每股收益同比增长率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'dt_eps_yoy', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'dt_eps_yoy', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '稀释每股收益同比增长率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'op_yoy', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'operating_profit_yoy', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '营业利润同比增长率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'ebt_yoy', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'ebt_yoy', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '利润总额同比增长率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'netprofit_yoy', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'netprofit_yoy', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '净利润同比增长率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'tr_yoy', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'total_revenue_yoy', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '营业总收入同比增长率，百分比'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'or_yoy', 'ratio', 'percent', 'percent', 1, 'dwd_fin_indicator', 'operating_revenue_yoy', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '营业收入同比增长率，百分比'),
  -- 比率指标（比例 / 倍数）
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'current_ratio', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'current_ratio', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '流动比率，比例'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'quick_ratio', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'quick_ratio', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '速动比率，比例'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'cash_ratio', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'cash_ratio', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '现金比率，比例'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'inv_turn', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'inventory_turnover', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '存货周转率，比例'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'ar_turn', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'ar_turnover', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '应收账款周转率，比例'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'assets_turn', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'assets_turnover', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '总资产周转率，比例'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'ocf_to_or', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'ocf_to_or', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '经营现金流量净额/营业收入，比例'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'assets_to_eqt', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'assets_to_equity', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '权益乘数，比例'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'ocf_to_profit', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'ocf_to_profit', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '经营现金流量净额/净利润，比例'),
  ('tushare', 'fina_indicator', 'ods_tushare_fina_indicator', 'q_npta', 'ratio', 'ratio', 'ratio', 1, 'dwd_fin_indicator', 'q_npta', FALSE, NULL, 'verified', NULL, NULL, 'Tushare Pro fina_indicator 接口文档', DATE '2026-06-02', 'GPT-5', '单季度净利润/总资产，比例');

-- ============================================================
-- PR #13 财务三表首批字段（OQ-006 要求预先登记，PR #13 合并时补全）
-- 基于 Tushare Pro 财务报表接口文档，金额字段单位为元。
-- ============================================================
INSERT INTO `data-aquarium.ashare_meta.ods_field_unit_map`
VALUES
  -- income: 利润表金额字段（元）
  ('tushare', 'income', 'ods_tushare_income', 'total_revenue', 'amount', '元', '元', 1, 'dwd_fin_income', 'total_revenue', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '营业总收入'),
  ('tushare', 'income', 'ods_tushare_income', 'revenue', 'amount', '元', '元', 1, 'dwd_fin_income', 'revenue', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '营业收入'),
  ('tushare', 'income', 'ods_tushare_income', 'total_cogs', 'amount', '元', '元', 1, 'dwd_fin_income', 'total_cogs', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '营业总成本'),
  ('tushare', 'income', 'ods_tushare_income', 'operate_profit', 'amount', '元', '元', 1, 'dwd_fin_income', 'operate_profit', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '营业利润'),
  ('tushare', 'income', 'ods_tushare_income', 'total_profit', 'amount', '元', '元', 1, 'dwd_fin_income', 'total_profit', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '利润总额'),
  ('tushare', 'income', 'ods_tushare_income', 'income_tax', 'amount', '元', '元', 1, 'dwd_fin_income', 'income_tax', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '所得税费用'),
  ('tushare', 'income', 'ods_tushare_income', 'n_income', 'amount', '元', '元', 1, 'dwd_fin_income', 'n_income', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '净利润'),
  ('tushare', 'income', 'ods_tushare_income', 'n_income_attr_p', 'amount', '元', '元', 1, 'dwd_fin_income', 'n_income_attr_p', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '归母净利润'),
  ('tushare', 'income', 'ods_tushare_income', 'ebit', 'amount', '元', '元', 1, 'dwd_fin_income', 'ebit', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '息税前利润'),
  ('tushare', 'income', 'ods_tushare_income', 'ebitda', 'amount', '元', '元', 1, 'dwd_fin_income', 'ebitda', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro income 接口文档', DATE '2026-06-02', 'GPT-5', '息税折旧摊销前利润'),
  -- balancesheet: 资产负债表金额字段（元）
  ('tushare', 'balancesheet', 'ods_tushare_balancesheet', 'total_assets', 'amount', '元', '元', 1, 'dwd_fin_balancesheet', 'total_assets', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro balancesheet 接口文档', DATE '2026-06-02', 'GPT-5', '资产总计'),
  ('tushare', 'balancesheet', 'ods_tushare_balancesheet', 'total_liab', 'amount', '元', '元', 1, 'dwd_fin_balancesheet', 'total_liab', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro balancesheet 接口文档', DATE '2026-06-02', 'GPT-5', '负债合计'),
  ('tushare', 'balancesheet', 'ods_tushare_balancesheet', 'total_hldr_eqy_exc_min_int', 'amount', '元', '元', 1, 'dwd_fin_balancesheet', 'total_hldr_eqy_exc_min_int', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro balancesheet 接口文档', DATE '2026-06-02', 'GPT-5', '股东权益合计(不含少数股东权益)'),
  ('tushare', 'balancesheet', 'ods_tushare_balancesheet', 'money_cap', 'amount', '元', '元', 1, 'dwd_fin_balancesheet', 'money_cap', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro balancesheet 接口文档', DATE '2026-06-02', 'GPT-5', '货币资金'),
  ('tushare', 'balancesheet', 'ods_tushare_balancesheet', 'inventories', 'amount', '元', '元', 1, 'dwd_fin_balancesheet', 'inventories', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro balancesheet 接口文档', DATE '2026-06-02', 'GPT-5', '存货'),
  ('tushare', 'balancesheet', 'ods_tushare_balancesheet', 'accounts_receiv', 'amount', '元', '元', 1, 'dwd_fin_balancesheet', 'accounts_receiv', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro balancesheet 接口文档', DATE '2026-06-02', 'GPT-5', '应收账款'),
  ('tushare', 'balancesheet', 'ods_tushare_balancesheet', 'goodwill', 'amount', '元', '元', 1, 'dwd_fin_balancesheet', 'goodwill', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro balancesheet 接口文档', DATE '2026-06-02', 'GPT-5', '商誉'),
  -- cashflow: 现金流量表金额字段（元）
  ('tushare', 'cashflow', 'ods_tushare_cashflow', 'n_cashflow_act', 'amount', '元', '元', 1, 'dwd_fin_cashflow', 'n_cashflow_act', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro cashflow 接口文档', DATE '2026-06-02', 'GPT-5', '经营活动产生的现金流量净额'),
  ('tushare', 'cashflow', 'ods_tushare_cashflow', 'n_cashflow_inv_act', 'amount', '元', '元', 1, 'dwd_fin_cashflow', 'n_cashflow_inv_act', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro cashflow 接口文档', DATE '2026-06-02', 'GPT-5', '投资活动产生的现金流量净额'),
  ('tushare', 'cashflow', 'ods_tushare_cashflow', 'n_cash_flows_fnc_act', 'amount', '元', '元', 1, 'dwd_fin_cashflow', 'n_cash_flows_fnc_act', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro cashflow 接口文档', DATE '2026-06-02', 'GPT-5', '筹资活动产生的现金流量净额'),
  ('tushare', 'cashflow', 'ods_tushare_cashflow', 'free_cashflow', 'amount', '元', '元', 1, 'dwd_fin_cashflow', 'free_cashflow', FALSE, NULL, 'verified', 'legacy_unsuffixed', DATE '2026-09-01', 'Tushare Pro cashflow 接口文档', DATE '2026-06-02', 'GPT-5', '企业自由现金流量');

-- ============================================================
-- 后置约束与说明
-- ============================================================
ALTER TABLE `data-aquarium.ashare_meta.ods_field_unit_map`
SET OPTIONS (description = 'OQ-006 单位契约表：endpoint + source_field 粒度的 ODS->DWD 单位换算唯一事实来源。verified 字段才可作为标准 DWD 输出。P0 + PR #13 首批已登记。');

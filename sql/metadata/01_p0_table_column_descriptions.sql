-- 文档维护：GPT-5（最近更新 2026-06-01）
-- BigQuery Standard SQL
-- P0 DIM/DWD 表级与字段级说明补齐脚本。
-- 用法：P0 建表或重建后执行本脚本；本脚本只更新 BigQuery metadata，不重写表数据。

ALTER TABLE `data-aquarium.ashare_dim.dim_trade_calendar`
SET OPTIONS (description = '交易日历维表。取 Tushare trade_cal 最新快照，保留全历史自然日与开市标记，用于交易日对齐、t-1/t-k 查找和 lookback 边界。');

ALTER TABLE `data-aquarium.ashare_dim.dim_trade_calendar`
ALTER COLUMN exchange SET OPTIONS (description = '交易所代码，如 SSE、SZSE、CFFEX'),
ALTER COLUMN cal_date SET OPTIONS (description = '自然日期'),
ALTER COLUMN is_open SET OPTIONS (description = '是否开市交易日，1=开市，0=休市'),
ALTER COLUMN pre_trade_date SET OPTIONS (description = '上一交易日；休市日通常为空或为源接口给出的前一交易日'),
ALTER COLUMN trade_date_seq SET OPTIONS (description = '交易日序号，仅开市日有值，用于按交易日位移'),
ALTER COLUMN source_system SET OPTIONS (description = '源系统标识，当前为 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 ODS 分区日期，YYYYMMDD 字符串'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 ODS 摄入时间');

ALTER TABLE `data-aquarium.ashare_dim.dim_stock`
SET OPTIONS (description = '股票主维表。合并 stock_basic 上市与退市最新快照，优先使用 ODS delist_date，并用日线交易记录兜底缺主数据代码的生命周期边界，避免幸存者偏差。');

ALTER TABLE `data-aquarium.ashare_dim.dim_stock`
ALTER COLUMN sec_code SET OPTIONS (description = '统一证券代码，Tushare ts_code 格式，如 600000.SH'),
ALTER COLUMN symbol SET OPTIONS (description = '证券数字代码，不含交易所后缀'),
ALTER COLUMN sec_name SET OPTIONS (description = '证券简称，来自 stock_basic 最新快照；兜底代码可能为空'),
ALTER COLUMN sec_type SET OPTIONS (description = '证券品种，当前 P0 固定为 stock'),
ALTER COLUMN area SET OPTIONS (description = '上市公司地域，来自 stock_basic.area'),
ALTER COLUMN industry SET OPTIONS (description = 'Tushare stock_basic 粗行业字段；标准行业时点归属以后续行业维表为准'),
ALTER COLUMN market SET OPTIONS (description = '市场类型，来自 stock_basic.market'),
ALTER COLUMN exchange SET OPTIONS (description = '交易所代码，按 sec_code 后缀归一为 SSE、SZSE、BSE 等'),
ALTER COLUMN board SET OPTIONS (description = '板块归类，如 SSE_MAIN、SZSE_MAIN、CHINEXT、STAR、BSE'),
ALTER COLUMN curr_type SET OPTIONS (description = '交易币种，通常为 CNY'),
ALTER COLUMN list_status SET OPTIONS (description = '上市状态，L=上市、D=退市、P=暂停上市、UNKNOWN=由日线兜底派生'),
ALTER COLUMN list_date SET OPTIONS (description = '上市日期；缺主数据时使用首个日线交易日兜底'),
ALTER COLUMN delist_date SET OPTIONS (description = '退市后第一天，用于生命周期半开区间 trade_date < delist_date'),
ALTER COLUMN first_trade_date SET OPTIONS (description = 'ODS daily 中可见的首个交易日'),
ALTER COLUMN last_trade_date SET OPTIONS (description = 'ODS daily 中可见的最后交易日'),
ALTER COLUMN is_delisted SET OPTIONS (description = '是否退市或按日线兜底规则推断为已退市'),
ALTER COLUMN stock_master_source SET OPTIONS (description = '股票主数据来源：stock_basic 或 derived_from_daily'),
ALTER COLUMN delist_date_source SET OPTIONS (description = '退市边界来源：stock_basic_delist_date、last_trade_date_plus_1_fallback、last_trade_date_plus_1_after_market_grace、missing_delist_date（QA 阻断态）或 NULL'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 stock_basic ODS 分区日期；日线兜底记录为空'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 ODS 摄入时间；日线兜底记录为空');

ALTER TABLE `data-aquarium.ashare_dim.dim_stock_name_hist`
SET OPTIONS (description = '股票名称历史 SCD2 维表。全量保留 namechange 历史事件，用于历史简称和 ST/*ST/退 市场风险状态还原。');

ALTER TABLE `data-aquarium.ashare_dim.dim_stock_name_hist`
ALTER COLUMN sec_code SET OPTIONS (description = '统一证券代码，Tushare ts_code 格式'),
ALTER COLUMN sec_name SET OPTIONS (description = '该生效区间内的证券简称'),
ALTER COLUMN valid_from SET OPTIONS (description = '名称或状态生效日期'),
ALTER COLUMN valid_to SET OPTIONS (description = '名称或状态失效日期；9999-12-31 表示当前有效或源数据未给出结束日'),
ALTER COLUMN ann_date SET OPTIONS (description = '名称变更公告日期'),
ALTER COLUMN change_reason SET OPTIONS (description = '名称变更原因，来自 namechange.change_reason'),
ALTER COLUMN is_st SET OPTIONS (description = '名称是否包含 ST、*ST 或退 等风险标识'),
ALTER COLUMN is_star_st SET OPTIONS (description = '名称是否包含 *ST 标识'),
ALTER COLUMN source_system SET OPTIONS (description = '源系统标识，当前为 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 ODS 分区日期，YYYYMMDD 字符串'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 ODS 摄入时间');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_stock_eod_price`
SET OPTIONS (description = '股票日线价格 DWD。以交易日历乘股票生命周期为骨架，写入 2019-01-01 之后数据，保留停牌日空行情行，并提供后复权价格、涨跌停与可交易掩码。');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_stock_eod_price`
ALTER COLUMN trade_date SET OPTIONS (description = '交易日，月分区字段'),
ALTER COLUMN sec_code SET OPTIONS (description = '统一证券代码，Tushare ts_code 格式'),
ALTER COLUMN open SET OPTIONS (description = '未复权开盘价，元/股'),
ALTER COLUMN high SET OPTIONS (description = '未复权最高价，元/股'),
ALTER COLUMN low SET OPTIONS (description = '未复权最低价，元/股'),
ALTER COLUMN close SET OPTIONS (description = '未复权收盘价，元/股'),
ALTER COLUMN pre_close SET OPTIONS (description = '未复权昨收价，元/股'),
ALTER COLUMN change SET OPTIONS (description = '日涨跌额，元/股，来自 daily.change'),
ALTER COLUMN pct_chg SET OPTIONS (description = '日涨跌幅，百分比，来自 daily.pct_chg'),
ALTER COLUMN volume_lot SET OPTIONS (description = '成交量，手，源字段 daily.vol'),
ALTER COLUMN amount_k_cny SET OPTIONS (description = '成交额，千元，源字段 daily.amount'),
ALTER COLUMN volume_share SET OPTIONS (description = '成交量，股，由手换算为股'),
ALTER COLUMN amount_cny SET OPTIONS (description = '成交额，元，由千元换算为元'),
ALTER COLUMN adj_factor SET OPTIONS (description = '后复权因子，来自 adj_factor.adj_factor'),
ALTER COLUMN open_hfq SET OPTIONS (description = '后复权开盘价，open * adj_factor'),
ALTER COLUMN high_hfq SET OPTIONS (description = '后复权最高价，high * adj_factor'),
ALTER COLUMN low_hfq SET OPTIONS (description = '后复权最低价，low * adj_factor'),
ALTER COLUMN close_hfq SET OPTIONS (description = '后复权收盘价，close * adj_factor'),
ALTER COLUMN ret_1d SET OPTIONS (description = '基于 close_hfq 的一日收益率，计算时读取 lookback buffer'),
ALTER COLUMN up_limit SET OPTIONS (description = '当日涨停价，元/股，来自 stk_limit.up_limit'),
ALTER COLUMN down_limit SET OPTIONS (description = '当日跌停价，元/股，来自 stk_limit.down_limit'),
ALTER COLUMN is_limit_up SET OPTIONS (description = '收盘价是否触及或超过涨停价'),
ALTER COLUMN is_limit_down SET OPTIONS (description = '收盘价是否触及或低于跌停价'),
ALTER COLUMN is_one_word_limit_up SET OPTIONS (description = '是否一字涨停，开高低均触及涨停价'),
ALTER COLUMN is_one_word_limit_down SET OPTIONS (description = '是否一字跌停，开高低均触及跌停价'),
ALTER COLUMN is_suspended SET OPTIONS (description = '是否全天停牌或无成交；有成交的盘中临停不置为 TRUE'),
ALTER COLUMN suspend_timing SET OPTIONS (description = '停牌时段描述，来自 suspend_d.suspend_timing；多条事件用逗号拼接'),
ALTER COLUMN suspend_type SET OPTIONS (description = '停牌事件类型，当前仅保留 S=停牌事件；R=复牌事件不用于标记停牌'),
ALTER COLUMN has_intraday_halt SET OPTIONS (description = '是否发生盘中临时停牌且当日仍有成交'),
ALTER COLUMN has_open_halt SET OPTIONS (description = '是否发生开盘时段或未知时段临停，影响开盘建仓'),
ALTER COLUMN can_buy_open SET OPTIONS (description = '开盘是否可买入；排除全天停牌、开盘临停和开盘涨停'),
ALTER COLUMN can_sell_open SET OPTIONS (description = '开盘是否可卖出；排除全天停牌、开盘临停和开盘跌停'),
ALTER COLUMN is_tradable SET OPTIONS (description = '日线样本是否可交易，排除全天停牌、开盘临停和一字涨跌停'),
ALTER COLUMN has_limit_data SET OPTIONS (description = '是否匹配到 stk_limit 涨跌停价数据'),
ALTER COLUMN has_suspend_event_data SET OPTIONS (description = '是否匹配到 suspend_d 停牌事件数据'),
ALTER COLUMN source_system SET OPTIONS (description = '源系统标识，当前为 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '主要行情来源 ODS 分区日期，YYYYMMDD 字符串；停牌骨架行可能为空'),
ALTER COLUMN ingested_at SET OPTIONS (description = '主要行情来源 ODS 摄入时间；停牌骨架行可能为空');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
SET OPTIONS (description = '股票日频估值与股本 DWD。来自 Tushare daily_basic，写入 2019-01-01 之后数据，统一输出元和股口径。');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_stock_eod_valuation`
ALTER COLUMN trade_date SET OPTIONS (description = '交易日，月分区字段'),
ALTER COLUMN sec_code SET OPTIONS (description = '统一证券代码，Tushare ts_code 格式'),
ALTER COLUMN close SET OPTIONS (description = '当日收盘价，元/股，来自 daily_basic.close'),
ALTER COLUMN turnover_rate SET OPTIONS (description = '换手率，百分比，基于总股本口径'),
ALTER COLUMN turnover_rate_free_float SET OPTIONS (description = '自由流通股换手率，百分比'),
ALTER COLUMN volume_ratio SET OPTIONS (description = '量比'),
ALTER COLUMN pe SET OPTIONS (description = '市盈率 PE'),
ALTER COLUMN pe_ttm SET OPTIONS (description = '滚动市盈率 PE TTM'),
ALTER COLUMN pb SET OPTIONS (description = '市净率 PB'),
ALTER COLUMN ps SET OPTIONS (description = '市销率 PS'),
ALTER COLUMN ps_ttm SET OPTIONS (description = '滚动市销率 PS TTM'),
ALTER COLUMN dividend_yield SET OPTIONS (description = '股息率，百分比，源字段 dv_ratio'),
ALTER COLUMN dividend_yield_ttm SET OPTIONS (description = 'TTM 股息率，百分比，源字段 dv_ttm'),
ALTER COLUMN total_share_10k SET OPTIONS (description = '总股本，万股，保留 Tushare 原始单位'),
ALTER COLUMN float_share_10k SET OPTIONS (description = '流通股本，万股，保留 Tushare 原始单位'),
ALTER COLUMN free_share_10k SET OPTIONS (description = '自由流通股本，万股，保留 Tushare 原始单位'),
ALTER COLUMN total_share SET OPTIONS (description = '总股本，股，由万股换算'),
ALTER COLUMN float_share SET OPTIONS (description = '流通股本，股，由万股换算'),
ALTER COLUMN free_share SET OPTIONS (description = '自由流通股本，股，由万股换算'),
ALTER COLUMN total_mv_10k_cny SET OPTIONS (description = '总市值，万元，保留 Tushare 原始单位'),
ALTER COLUMN circ_mv_10k_cny SET OPTIONS (description = '流通市值，万元，保留 Tushare 原始单位'),
ALTER COLUMN total_mv_cny SET OPTIONS (description = '总市值，元，由万元换算'),
ALTER COLUMN circ_mv_cny SET OPTIONS (description = '流通市值，元，由万元换算'),
ALTER COLUMN source_system SET OPTIONS (description = '源系统标识，当前为 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 ODS 分区日期，YYYYMMDD 字符串'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 ODS 摄入时间');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_fin_indicator`
SET OPTIONS (description = '财务指标 DWD 版本事实表。来自 Tushare fina_indicator，从报告期分区 20170101 起读取，使用 ann_date_eff/visible_trade_date 支持 2019+ PIT 特征。');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_fin_indicator`
ALTER COLUMN sec_code SET OPTIONS (description = '统一证券代码，Tushare ts_code 格式'),
ALTER COLUMN ann_date_eff SET OPTIONS (description = '公告生效日期，来自 fina_indicator.ann_date，月分区字段'),
ALTER COLUMN report_period SET OPTIONS (description = '报告期，对应 fina_indicator.end_date'),
ALTER COLUMN ann_date SET OPTIONS (description = '源公告日期字符串，YYYYMMDD'),
ALTER COLUMN end_date SET OPTIONS (description = '源报告期字符串，YYYYMMDD'),
ALTER COLUMN update_flag SET OPTIONS (description = 'Tushare 更新标志；1 通常表示修正/更新版本'),
ALTER COLUMN eps SET OPTIONS (description = '基本每股收益'),
ALTER COLUMN dt_eps SET OPTIONS (description = '稀释每股收益'),
ALTER COLUMN current_ratio SET OPTIONS (description = '流动比率'),
ALTER COLUMN quick_ratio SET OPTIONS (description = '速动比率'),
ALTER COLUMN cash_ratio SET OPTIONS (description = '现金比率'),
ALTER COLUMN inventory_turnover SET OPTIONS (description = '存货周转率，源字段 inv_turn'),
ALTER COLUMN ar_turnover SET OPTIONS (description = '应收账款周转率，源字段 ar_turn'),
ALTER COLUMN assets_turnover SET OPTIONS (description = '总资产周转率，源字段 assets_turn'),
ALTER COLUMN net_debt SET OPTIONS (description = '净债务，源字段 netdebt'),
ALTER COLUMN working_capital SET OPTIONS (description = '营运资本'),
ALTER COLUMN netprofit_margin SET OPTIONS (description = '销售净利率，百分比'),
ALTER COLUMN grossprofit_margin SET OPTIONS (description = '销售毛利率，百分比'),
ALTER COLUMN roe SET OPTIONS (description = '净资产收益率 ROE，百分比'),
ALTER COLUMN roe_deducted SET OPTIONS (description = '扣非净资产收益率，源字段 roe_dt'),
ALTER COLUMN roa SET OPTIONS (description = '总资产收益率 ROA，百分比'),
ALTER COLUMN roic SET OPTIONS (description = '投入资本回报率 ROIC，百分比'),
ALTER COLUMN ocf_to_or SET OPTIONS (description = '经营现金流量净额/营业收入'),
ALTER COLUMN debt_to_assets SET OPTIONS (description = '资产负债率，百分比'),
ALTER COLUMN assets_to_equity SET OPTIONS (description = '权益乘数，源字段 assets_to_eqt'),
ALTER COLUMN ocf_to_profit SET OPTIONS (description = '经营现金流量净额/净利润'),
ALTER COLUMN q_netprofit_margin SET OPTIONS (description = '单季度销售净利率，百分比'),
ALTER COLUMN q_grossprofit_margin SET OPTIONS (description = '单季度销售毛利率，源字段 q_gsprofit_margin'),
ALTER COLUMN q_roe SET OPTIONS (description = '单季度净资产收益率，百分比'),
ALTER COLUMN q_roe_deducted SET OPTIONS (description = '单季度扣非净资产收益率，源字段 q_dt_roe'),
ALTER COLUMN q_npta SET OPTIONS (description = '单季度净利润/总资产，源字段 q_npta'),
ALTER COLUMN basic_eps_yoy SET OPTIONS (description = '基本每股收益同比增长率，百分比'),
ALTER COLUMN dt_eps_yoy SET OPTIONS (description = '稀释每股收益同比增长率，百分比'),
ALTER COLUMN operating_profit_yoy SET OPTIONS (description = '营业利润同比增长率，源字段 op_yoy'),
ALTER COLUMN ebt_yoy SET OPTIONS (description = '利润总额同比增长率，源字段 ebt_yoy'),
ALTER COLUMN netprofit_yoy SET OPTIONS (description = '净利润同比增长率，百分比'),
ALTER COLUMN total_revenue_yoy SET OPTIONS (description = '营业总收入同比增长率，源字段 tr_yoy'),
ALTER COLUMN operating_revenue_yoy SET OPTIONS (description = '营业收入同比增长率，源字段 or_yoy'),
ALTER COLUMN source_system SET OPTIONS (description = '源系统标识，当前为 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 ODS 报告期分区日期，YYYYMMDD 字符串'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 ODS 摄入时间'),
ALTER COLUMN visible_trade_date SET OPTIONS (description = '公告日之后第一个上交所交易日，用于 PIT as-of join');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_fin_indicator_latest`
SET OPTIONS (description = '财务指标最新版本便捷表。每个 sec_code/report_period 保留 update_flag 优先、公告与摄入最新的一版；不用于 PIT 回测 join。');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_fin_indicator_latest`
ALTER COLUMN sec_code SET OPTIONS (description = '统一证券代码，Tushare ts_code 格式'),
ALTER COLUMN ann_date_eff SET OPTIONS (description = '该报告期最新版本的公告生效日期'),
ALTER COLUMN report_period SET OPTIONS (description = '报告期，对应 fina_indicator.end_date'),
ALTER COLUMN ann_date SET OPTIONS (description = '源公告日期字符串，YYYYMMDD'),
ALTER COLUMN end_date SET OPTIONS (description = '源报告期字符串，YYYYMMDD'),
ALTER COLUMN update_flag SET OPTIONS (description = 'Tushare 更新标志；1 通常表示修正/更新版本'),
ALTER COLUMN eps SET OPTIONS (description = '基本每股收益'),
ALTER COLUMN dt_eps SET OPTIONS (description = '稀释每股收益'),
ALTER COLUMN current_ratio SET OPTIONS (description = '流动比率'),
ALTER COLUMN quick_ratio SET OPTIONS (description = '速动比率'),
ALTER COLUMN cash_ratio SET OPTIONS (description = '现金比率'),
ALTER COLUMN inventory_turnover SET OPTIONS (description = '存货周转率，源字段 inv_turn'),
ALTER COLUMN ar_turnover SET OPTIONS (description = '应收账款周转率，源字段 ar_turn'),
ALTER COLUMN assets_turnover SET OPTIONS (description = '总资产周转率，源字段 assets_turn'),
ALTER COLUMN net_debt SET OPTIONS (description = '净债务，源字段 netdebt'),
ALTER COLUMN working_capital SET OPTIONS (description = '营运资本'),
ALTER COLUMN netprofit_margin SET OPTIONS (description = '销售净利率，百分比'),
ALTER COLUMN grossprofit_margin SET OPTIONS (description = '销售毛利率，百分比'),
ALTER COLUMN roe SET OPTIONS (description = '净资产收益率 ROE，百分比'),
ALTER COLUMN roe_deducted SET OPTIONS (description = '扣非净资产收益率，源字段 roe_dt'),
ALTER COLUMN roa SET OPTIONS (description = '总资产收益率 ROA，百分比'),
ALTER COLUMN roic SET OPTIONS (description = '投入资本回报率 ROIC，百分比'),
ALTER COLUMN ocf_to_or SET OPTIONS (description = '经营现金流量净额/营业收入'),
ALTER COLUMN debt_to_assets SET OPTIONS (description = '资产负债率，百分比'),
ALTER COLUMN assets_to_equity SET OPTIONS (description = '权益乘数，源字段 assets_to_eqt'),
ALTER COLUMN ocf_to_profit SET OPTIONS (description = '经营现金流量净额/净利润'),
ALTER COLUMN q_netprofit_margin SET OPTIONS (description = '单季度销售净利率，百分比'),
ALTER COLUMN q_grossprofit_margin SET OPTIONS (description = '单季度销售毛利率，源字段 q_gsprofit_margin'),
ALTER COLUMN q_roe SET OPTIONS (description = '单季度净资产收益率，百分比'),
ALTER COLUMN q_roe_deducted SET OPTIONS (description = '单季度扣非净资产收益率，源字段 q_dt_roe'),
ALTER COLUMN q_npta SET OPTIONS (description = '单季度净利润/总资产，源字段 q_npta'),
ALTER COLUMN basic_eps_yoy SET OPTIONS (description = '基本每股收益同比增长率，百分比'),
ALTER COLUMN dt_eps_yoy SET OPTIONS (description = '稀释每股收益同比增长率，百分比'),
ALTER COLUMN operating_profit_yoy SET OPTIONS (description = '营业利润同比增长率，源字段 op_yoy'),
ALTER COLUMN ebt_yoy SET OPTIONS (description = '利润总额同比增长率，源字段 ebt_yoy'),
ALTER COLUMN netprofit_yoy SET OPTIONS (description = '净利润同比增长率，百分比'),
ALTER COLUMN total_revenue_yoy SET OPTIONS (description = '营业总收入同比增长率，源字段 tr_yoy'),
ALTER COLUMN operating_revenue_yoy SET OPTIONS (description = '营业收入同比增长率，源字段 or_yoy'),
ALTER COLUMN source_system SET OPTIONS (description = '源系统标识，当前为 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 ODS 报告期分区日期，YYYYMMDD 字符串'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 ODS 摄入时间'),
ALTER COLUMN visible_trade_date SET OPTIONS (description = '该报告期最新版本公告后第一个上交所交易日');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_index_eod`
SET OPTIONS (description = '指数日线 DWD。sec_code 输出规范指数代码，source_sec_code 保留 ODS 实际代码，并从 index_dailybasic 写入可用指数的估值、市值和股本字段。');

ALTER TABLE `data-aquarium.ashare_dwd.dwd_index_eod`
ALTER COLUMN trade_date SET OPTIONS (description = '交易日，月分区字段'),
ALTER COLUMN sec_code SET OPTIONS (description = '规范指数代码；沪深300 等双代码指数在此归一，如 ODS 399300.SZ 映射为 000300.SH'),
ALTER COLUMN source_sec_code SET OPTIONS (description = '来源 ODS 实际指数代码，Tushare ts_code 格式，用于血缘追溯'),
ALTER COLUMN index_alias SET OPTIONS (description = '常用指数别名，如 SSE50、CSI300、CSI500'),
ALTER COLUMN open SET OPTIONS (description = '指数开盘点位'),
ALTER COLUMN high SET OPTIONS (description = '指数最高点位'),
ALTER COLUMN low SET OPTIONS (description = '指数最低点位'),
ALTER COLUMN close SET OPTIONS (description = '指数收盘点位'),
ALTER COLUMN pre_close SET OPTIONS (description = '指数前收盘点位'),
ALTER COLUMN change SET OPTIONS (description = '指数涨跌点数'),
ALTER COLUMN pct_chg SET OPTIONS (description = '指数涨跌幅，百分比'),
ALTER COLUMN volume SET OPTIONS (description = '指数成交量，源字段 index_daily.vol'),
ALTER COLUMN amount SET OPTIONS (description = '指数成交额，源字段 index_daily.amount'),
ALTER COLUMN total_mv_cny SET OPTIONS (description = '指数总市值，元，来自 index_dailybasic.total_mv'),
ALTER COLUMN float_mv_cny SET OPTIONS (description = '指数流通市值，元，来自 index_dailybasic.float_mv'),
ALTER COLUMN total_share SET OPTIONS (description = '指数总股本，股，来自 index_dailybasic.total_share'),
ALTER COLUMN float_share SET OPTIONS (description = '指数流通股本，股，来自 index_dailybasic.float_share'),
ALTER COLUMN free_share SET OPTIONS (description = '指数自由流通股本，股，来自 index_dailybasic.free_share'),
ALTER COLUMN turnover_rate SET OPTIONS (description = '指数换手率，百分比'),
ALTER COLUMN turnover_rate_free_float SET OPTIONS (description = '指数自由流通股换手率，百分比'),
ALTER COLUMN pe SET OPTIONS (description = '指数市盈率 PE'),
ALTER COLUMN pe_ttm SET OPTIONS (description = '指数滚动市盈率 PE TTM'),
ALTER COLUMN pb SET OPTIONS (description = '指数市净率 PB'),
ALTER COLUMN source_system SET OPTIONS (description = '源系统标识，当前为 tushare'),
ALTER COLUMN source_partition_date SET OPTIONS (description = '来源 index_daily ODS 分区日期，YYYYMMDD 字符串'),
ALTER COLUMN ingested_at SET OPTIONS (description = '来源 index_daily ODS 摄入时间');

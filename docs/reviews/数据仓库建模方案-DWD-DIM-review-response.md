# 《数据仓库建模方案-DWD-DIM》Review Response

> 回应对象：`docs/数据仓库建模方案-DWD-DIM-review.md`（2026-05-31）
> 处理原则：认可的点已在 `docs/数据仓库建模方案-DWD-DIM.md` 整改，不在此重复；本文件**只记录不采纳或调整执行的点及理由**。
> 文档维护：Claude Opus 4.8（2026-05-31）

## 总览

review 的事实核对准确（已独立复核：ODS 为 **54 张**外部表、`ods_tushare_fina_indicator` **无 `f_ann_date`** 字段）。P0/P1/P2 共 11 项，其中 **9 项完全认可并已整改**（P0-1、P0-2、P0-3、P1-1、P1-2、P1-4、P2-1、P2-2、P2-3），**2 项认可问题但调整了执行方式**，记录如下。

## 调整-1 ｜ 对应 P0-4：`delist_date` 类型不一致

**认可的部分**：`stock_basic_delisted.delist_date` 外部表 schema 为 `INT64`、Parquet 文件实际为 `BYTE_ARRAY`，读取报错会阻塞 `dim_stock` 构建——问题真实存在。

**已在方案内整改**：
- `dim_stock` 读取退市分区时对 `delist_date` 用 `SAFE` 容错读取；
- 增加数据质量门禁：`stock_basic_listed + delisted` 必须能解析 `list_date/delist_date` 为 DATE，否则告警阻断；
- 增加从 2019+ 价格表反向补主数据的兜底校验（覆盖 review 指出的 `000043.SZ` / `300114.SZ` / `920218.BJ` 等缺失代码）。

**不采纳的部分**：在本数仓建模方案内**直接修改 ODS 外部表 schema**（把 `delist_date` 改 `STRING` / 重建外部表）。

**理由**：ODS 是贴源层，由上游 ingestion 流程维护；跨层修改 ODS schema 超出 DWD/DIM 建模方案的职责边界，且可能影响其他消费方。已将"上游修复 `delist_date` 类型一致性"作为给数据源方的建议记入 `.agent/memory/OPEN_QUESTIONS.md`（OQ-007），由 owner/上游决定；在此之前 DWD 层以容错 + 门禁兜底，不阻塞建模。

## 调整-2 ｜ 对应 P1-3：可交易性方向化

**认可并整改**：价格 DWD 增加方向/时点字段 `is_one_word_limit_up` / `is_one_word_limit_down` / `can_buy_open` / `can_sell_open`；DWS 标签表增加 `entry_reachable` / `exit_reachable` / `label_valid`。`is_tradable` 保留为综合样本掩码。

**不采纳的部分**：新增 `can_buy_close` / `can_sell_close` 收盘侧四象限全集。

**理由**：
1. EOD 粒度下"收盘是否封板"已由现有 `is_limit_up` / `is_limit_down` 表达，再加收盘方向字段信息冗余；
2. 本项目为中低频小资金，建仓基准假设是 **t+1 开盘 / VWAP**（见方案 §4.3），收盘建仓非主路径；
3. 精确的盘中/收盘可成交性需分钟级数据，EOD 无法刻画，避免提供"名义精确、实则近似"的字段。
若未来引入收盘建仓策略或接入分钟数据，再行扩展。

## 备注

以上 2 项为「执行方式/范围」的调整，并非否定 review 结论；其余 9 项已按 review 整改，详见方案文档对应章节与本次提交 diff。

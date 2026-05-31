-- 文档维护：GPT-5（最近更新 2026-05-31）
-- BigQuery Standard SQL
-- 创建 DIM/DWD 数据集。location 需与 ODS 数据集保持一致。

CREATE SCHEMA IF NOT EXISTS `data-aquarium.ashare_dim`
OPTIONS (
  location = 'asia-east2',
  description = 'A-share dimension layer built from data-aquarium.ashare_ods'
);

CREATE SCHEMA IF NOT EXISTS `data-aquarium.ashare_dwd`
OPTIONS (
  location = 'asia-east2',
  description = 'A-share detail warehouse layer built from data-aquarium.ashare_ods'
);

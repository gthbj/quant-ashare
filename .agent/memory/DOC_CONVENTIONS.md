# 文档与命名规范（Doc Conventions）

> 文档维护：Claude Opus 4.8（最近更新 2026-06-01）

本文件汇总项目文档的**存放位置与命名规范**。所有 Agent 在新建 / 移动文档前必读，确保目录与命名一致、可检索。

---

## 需求文档（PRD）书写规范

PRD 文档统一存放于 `docs/prd/` 下（**不细分子目录**）；项目规划 PRD 与按 issue 生成的 PRD 均直接置于 `docs/prd/`。

PRD 文件命名格式：

```text
PRD_YYYYMMDD_XX_xxxx.md
```

### 编号规则

`XX` 为当日序号，每天从 `01` 重新开始计数。

例如：

```text
PRD_20260509_01_xxxx.md
PRD_20260509_02_xxxx.md
...
PRD_20260509_08_xxxx.md
PRD_20260510_01_xxxx.md
```

### 命名后缀规则

PRD 文档名末尾需追加 `_xxxx`。

`xxxx` 为本文档内容的总结，限制在 20 个汉字以内。

例如：

```text
PRD_20260601_01_策略1价格量价基础分类模型.md
```

## 分析脚本指标定义

新增 `scripts/strategy1/`、`scripts/strategy1_cloudrun/` 或 `src/quant_ashare/strategy1/` 下的分析脚本，不得本地重新定义 `max_drawdown`、复合年化 / 累计收益、Sharpe / 年化波动、Calmar、`safe_ratio`、`fmt_pct` / `fmt_pp` / `fmt_num`、`markdown_table` 等指标或格式化函数；应复用既有实现，或先抽共享模块并同步更新冻结 allowlist 测试。

# 数据审查报告目录

> 文档维护：GPT-5（最近更新 2026-06-03）

本目录用于保存 ODS/GCS 数据审查报告。每次审查应单独生成一份 Markdown 报告，文件名建议：

`YYYYMMDD_HHMMSS_ods_gcs_data_audit_<llm_or_agent_id>.md`

报告必须记录：

- 审查生成时间、开始时间、结束时间，带时区。
- 审查 LLM / Agent 名称 / 版本。
- 审查 run id 或任务 id。
- 仓库路径、Git 分支、commit SHA、工作区状态。
- BigQuery project、dataset、location。
- 审查的 ODS 表清单。
- 数据范围。本次审查限定为 2019-01-01 及之后的数据。
- 各表日期语义和实际使用的业务日期字段。
- API provider、token 数量、每 token 限速、总请求数、失败数、重试数；不得记录 token 值。
- 审查脚本组织方式：列出按 endpoint / 主题拆分的脚本和共享工具层位置。
- 抽样策略、样本数量、覆盖年份、高风险字段。
- 官方文档链接清单、各 endpoint 单次返回上限、命中返回上限的请求数量、拆细复查结果。
- BigQuery query job id 或可追溯查询记录。
- Findings、口径差异、限制、阻塞项、owner 决策项和建议后续修复。
- 只读声明：未补采数据、未改写 GCS raw 文件、未重建或覆盖 BigQuery 生产表。

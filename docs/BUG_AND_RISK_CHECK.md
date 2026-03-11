# 全站 Bug 与潜在问题检查说明

## 已修复问题

| 问题 | 位置 | 修复 |
|------|------|------|
| LIS 适配器在 `LIS_API_BASE_URL` 未配置时仍发起请求 | `backend/app/adapters/winning.py` | `_request` 与 `_call_asmx` 开头增加空 URL 校验，抛出明确错误 |
| HL7 解析出空 `report_no` 时仍写入库，可能触发唯一约束冲突 | `backend/app/hl7/handler.py` | `_persist` 开头若 `report_no` 为空则记录日志并跳过 |
| PDF 代理响应缺少 `Content-Disposition`，部分浏览器/iframe 展示异常 | `backend/app/api/report.py` | 返回 `Content-Disposition: inline; filename=report.pdf` |

## 静态检查结论

- **Lint**：后端 `app/`、前端 `src/` 无 linter 报错。
- **敏感信息**：未在代码中硬编码密码/密钥；`LIS_API_KEY` 等从配置读取；`.gitignore` 已排除 `.env`、`k8s/secret.yaml`。
- **异常处理**：未发现裸 `except:`；关键路径有 try/except 与日志。

## 潜在风险与建议

| 风险 | 说明 | 建议 |
|------|------|------|
| 卫宁 ASMX 方法名/参数名与本院不一致 | 当前默认 `GetReportList`、`jsonParam` | 以卫宁文档为准，用 `LIS_ASMX_*` 配置项调整 |
| HL7 内存去重仅保留 5000 条 | 重启后重复消息可能再次入库 | 可接受；若需长期去重可改为 DB 或 Redis 记录 |
| 前端 PDF 若 404 仅 iframe 空白 | 无统一错误提示 | 可选：iframe onerror 或先请求 HEAD 再展示 |
| 解读页进入即触发一次 AI 解读 | 选首条报告会自动调用 LLM | 属当前产品逻辑；若需省资源可改为“点击才解读” |
| OCR 结果过短（<10 字）直接 400 | 避免无意义调用 LLM | 合理；可据需要调整字数阈值或提示文案 |

## 建议上线前再确认

1. 生产环境 `DATABASE_URL`、`LIS_API_KEY` 等仅通过 Secret/环境变量注入，不提交仓库。
2. 对接卫宁时确认 `LIS_API_BASE_URL`、`LIS_USE_ASMX`、ASMX 方法名/命名空间已按本院接口填写。
3. 健康检查 `/api/v1/system/health` 与 LIS 连通性 `/api/v1/system/lis-check` 可纳入监控与告警。

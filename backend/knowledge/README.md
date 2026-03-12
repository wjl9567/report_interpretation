# 轻量知识增强 - 规范与指南目录

启用后，解读时会按**报告类型**与**科室**自动加载本目录下的 Markdown 片段，并注入到模型 System Prompt 中，使解读有据可依。

## 配置

- 环境变量或 `.env`：`KNOWLEDGE_ENABLED=true`、`KNOWLEDGE_DIR=knowledge`（相对后端项目根）、`KNOWLEDGE_MAX_CHARS=4000`
- 未启用时不会读取本目录，不影响现有行为

## 目录约定

```
knowledge/
├── report_type/          # 按报告类型
│   ├── lab/              # 检验报告
│   │   └── 检验指南摘录.md
│   ├── ultrasound/
│   ├── ecg/
│   └── ...
└── department/           # 按科室（可选）
    ├── hematology/
    ├── internal/
    └── respiratory/
```

- **report_type**：与系统报告类型一致（lab、ultrasound、ecg、eeg、pulmonary、ct、xray、mri）
- **department**：与系统科室一致（hematology、internal、respiratory；general 不加载科室专属）
- 每个子目录下可放多份 `.md` 文件，会按文件名排序后拼接，总长度不超过 `KNOWLEDGE_MAX_CHARS`

## 内容建议

- 摘录临床指南、操作规程、专科共识中的**关键定义、分级标准、处置建议**
- 每份文件可含标题与段落，便于模型引用
- 避免过长单文件，可拆成多份按主题命名（如 `危急值标准.md`、`贫血分型.md`）

## 示例

见 `report_type/lab/` 下示例文件。按本院需求增删或替换为正式规范摘录即可。

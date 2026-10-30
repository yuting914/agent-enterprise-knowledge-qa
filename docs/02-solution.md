# 02 方案与技术取舍

## 调用流程

```text
问题 + 可选历史
    ↓
模型选择一个动作（结构化 JSON）
    ├─ search_documents(query) → 候选文档 ID、标题、版本日期、范围
    ├─ read_excerpt(doc_id)    → 原文片段
    ├─ ask_clarification       → 说明冲突/缺口并追问
    └─ finish                 → 有依据回答或资料不足
    ↑                 ↓
    └──── 工具观察/校验反馈 ────┘
```

每轮由模型根据最新观察选择动作，Python 只执行工具、检查输出完整性并限制最多 8 步。工具异常会成为观察结果交回模型，不由固定分支直接决定重试。`examples/clear.actual.json` 与 `examples/tool-failure.actual.json` 展示不同工具观察后的不同路径。

## 检索与冲突

资料位于 `data/documents.json`，每份含 ID、版本日期、适用范围、关键词与片段。`data/documents-d01-only.json` 只移除 D02，用于核对资料变更后的模型动作。检索用中文字符二元组重合和显式同义关键词评分，返回前 5 份候选；检索不直接返回原文，模型需选择读取。对 D01/D02 使用相同主题关键词，以提高冲突召回。引用校验要求文档已读取且引用文本是片段的逐字子串。新运行记录还保存资料文件名与 SHA-256，便于核对实际使用的语料。

模型提示要求：同主题候选逐一核对；范围或优先级未知时展示冲突并追问；资料外问题说明缺口。程序不会根据版本日期或固定数值替模型选答案。引用校验能阻止伪造片段，但不能自动证明回答语义完全受引用支持，因此评估仍需人工检查。

## 模型与框架选择

考虑过 LangGraph 状态图和原生循环。本题只有两个业务工具，选择 Python 标准库实现原生循环，便于评审直接看到每次模型动作与工具观察。真实模型通过已登录的 Claude Code CLI `-p --json-schema --output-format json` 接入；`--tools ""` 禁止 CLI 内置工具，`--disallowedTools "mcp__*"` 禁止 MCP 工具。它只产出动作，检索和读取都由项目代码执行。CLI 版本及实际路由模型写入每份 Trace。离线 Mock 为规则后端，明确不计作真实模型效果。

参考：[Claude Code CLI 参数文档](https://code.claude.com/docs/en/cli-reference)、[程序化运行说明](https://code.claude.com/docs/en/headless)。

## 失败与限制

空问题在输入处报错；无结果返回资料缺口；工具错误作为观察；无效引用和空白追问反馈给模型再次决策；达到上限返回未完成。模型服务不可用时返回 `model_error`，`--backend mock` 可离线演示。关键词检索只针对小规模合成资料；真实企业文档需要更完善的分段、召回评估、权限控制和更新机制。

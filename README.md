# 企业知识问答 Agent

题目：企业知识问答 Agent。员工输入制度或产品问题，CLI 在合成资料中检索并读取原文，返回答案、引用、资料缺口与状态。

## 评审入口

- [需求与验收](docs/01-requirements.md)
- [循环设计与取舍](docs/02-solution.md)
- [实际运行与限制](docs/03-evaluation.md)
- [AI 使用记录](docs/04-ai-usage.md)
- [复盘](docs/05-retrospective.md)
- [`examples/`](examples/)：六组输入、真实模型运行记录和离线 Mock 记录；文件名后缀明确区分 `actual` 与 `mock`
- [`tests/`](tests/)：可执行单元测试

## 环境与安装

- Python 3.11 或更高版本；Python 代码仅用标准库，`requirements.txt` 无需安装包。
- 真实模型模式需要已安装、已登录的 Claude Code CLI。本次验证使用 CLI `2.1.137`。先执行 `claude auth status` 确认登录；若未登录，执行 `claude auth login`。模型服务还须有可用额度。
- 离线模式只需 Python，不需要网络、模型或环境变量。`.env.example` 说明了配置边界；不要提交凭据。

在仓库根目录运行（PowerShell、bash 均可）：

```sh
python -m src.cli --input examples/clear.input.json --backend mock
python -m src.cli --input examples/conflict.input.json --backend mock
python -m src.cli --input examples/clear.input.json --backend claude --output examples/my-run.json
python -m unittest discover -s tests -v
```

默认后端是 `claude`，`--model haiku` 是传给 CLI 的模型别名；每条运行记录中的 `run_info.actual_models` 记录 CLI 实际报告的模型。本机成功运行时报告 `deepseek-v4-pro`，因此不能把该次运行称作 Haiku 模型效果。可用 `--model` 更换当前 CLI 支持的模型。

直接输入问题：

```sh
python -m src.cli --question "企业账号密码忘了怎么办？" --backend mock
```

多轮输入使用 `--history-file history.json`（JSON 数组，元素含 `role` 与 `content`），或参考 `examples/follow-up.input.json`。`--data` 可替换资料文件；`--max-steps` 设置步数上限；`--fail-tool search_documents` 或 `read_excerpt` 可注入工具失败。

## 输出与边界

输出 JSON 含 `answer`、`citations`（文档 ID、版本日期、逐字片段）、`gaps`、`status`、`trace` 和 `run_info`。Trace 每步记录动作、参数、工具观察、下一动作及简短公开依据。状态包括 `answered`、`needs_clarification`、`insufficient_evidence`、`tool_error`、`incomplete_limit` 和 `model_error`。

真实模型每一步只生成一个结构化动作；Python 执行业务工具并把结果送回模型。程序会拒绝未读取文档的引用、非逐字引用、未检索就结束、空白追问。默认最多执行 8 步，可配置值强制限定在 1–20；达到上限明确返回 `incomplete_limit`。离线 Mock 是确定性规则，仅用于验证流程，不能证明真实模型的 ReAct 决策能力。六组真实模型运行结果及限制见评估文档。

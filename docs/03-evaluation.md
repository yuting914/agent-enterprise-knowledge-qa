# 03 测试预期、实际结果与限制

## 运行环境和方法

Python 3.13.3；Claude Code CLI 2.1.137。请求模型别名为 `haiku`，CLI 的 `modelUsage` 在成功运行中报告实际模型 `deepseek-v4-pro`，两者均保留在 Trace 的 `run_info` 中。测试命令及实际输出见 [`examples/test-results.txt`](../examples/test-results.txt)：22 项通过，其中 6 项核验已保存的真实模型 Trace，运行测试本身不再调用模型。六组必验输入及 D01 单文档变体均在 [`examples/`](../examples/)；`*.actual.json` 是真实 CLI 运行，`*.mock.json` 是离线规则运行，不混用为模型效果。

## 用例结果

| 验收 | 预期 | 实际与证据 | 结论 |
|---|---|---|---|
| AC-01 明确答案 | 读取 D03 后回答并引用原文 | [`clear.actual.json`](../examples/clear.actual.json)：检索 → 读取 D03 → 回答；引用逐字匹配 | 通过 |
| AC-02 冲突 | D01/D02 均引用，说明 30/15 天冲突并追问 | [`conflict.actual.json`](../examples/conflict.actual.json)：检索 → 读取 D01 → 读取 D02 → 追问；两条引用逐字匹配，未选期限 | 通过 |
| AC-03 资料外 | 检索无结果后说明缺口 | [`out-of-scope.actual.json`](../examples/out-of-scope.actual.json)：首次过早追问被校验退回，两次检索均为空，再结束为 `insufficient_evidence` | 通过 |
| AC-04 改写 | 相似说法仍找到 D03 | [`paraphrase.actual.json`](../examples/paraphrase.actual.json)：检索 → 读取 D03 → 回答 | 通过 |
| AC-05 追问 | 根据历史理解“这个申请”并引用 D04 | [`follow-up.actual.json`](../examples/follow-up.actual.json)：首次过早结束被校验拒绝，随后检索、读取 D04、正确回答 | 通过，但暴露模型需输出校验 |
| AC-06 工具失败 | 看见错误后调整动作并明确失败 | [`tool-failure.actual.json`](../examples/tool-failure.actual.json)：检索失败后重试两次，再以 `tool_error` 结束，无虚构引用 | 通过 |
| AC-07 动态循环 | 至少两条真实路径因观察不同而改变动作 | `clear.actual.json` 读到 D03 后选择回答；`conflict.actual.json` 读到互相矛盾的两份原文后选择追问；`tool-failure.actual.json` 看到工具错误后重试并结束。均含动作、参数、观察、下一动作及简短依据 | 通过 |
| AC-08 上限 | 超限返回明确未完成，调用方不能移除硬上限 | [`test-results.txt`](../examples/test-results.txt) 中 `test_step_limit_is_explicit` 与 `test_step_limit_cannot_be_disabled` 通过 | 通过 |
| AC-09 资料替换 | 文档原文变更后答案/引用变化，冲突消失后动作变化 | `test_document_change_changes_answer` 将 D03 改为人工重置，输出和引用随之改变；`test_document_change_changes_decision` 将 D02 改为 30 天后由追问变成回答；D01 单文档真实运行与冲突运行相比也由追问变为回答 | 离线与真实变体均通过 |
| AC-10 仅有 D01 | 只检索到 D01 时依据其 30 天原文回答 | [`d01-only.actual.json`](../examples/d01-only.actual.json)：检索仅返回 D01 → 读取 D01 → 回答 30 天；引用逐字匹配。资料文件 SHA-256 与 [`documents-d01-only.json`](../data/documents-d01-only.json) 一致 | 通过 |

## 失败分析

初始 Codex CLI 模型连接连续超时，因此运行时改用本机可访问的 Claude Code CLI。真实模型第一次冲突运行曾读取 D01/D02 并选择追问，但追问正文为空，随后增加了“空白追问拒绝”校验。开发中模型服务一度返回 `API Error: 402 Insufficient Balance`；用户充值后重新运行冲突和资料外用例。资料外复跑时还出现一次调用超时，随后修复错误处理，避免把完整问题带入错误日志。D01 单文档变体第一次调用也超时，重试后成功；当前 `*.actual.json` 均为成功的真实模型输出。早期失败没有被当作通过证据。

## 已知限制与复验步骤

检索为小规模合成语料的字符二元组与关键词评分，未做大规模召回或真实企业权限验证。引用逐字校验不等于语义蕴含校验。CLI 的模型别名到实际模型路由由用户环境决定；执行成本和模型行为可能变化。

评审者可在模型服务可用时，于仓库根目录顺序复验：

```sh
python -m src.cli --input examples/conflict.input.json --backend claude --output examples/conflict.actual.json
python -m src.cli --input examples/out-of-scope.input.json --backend claude --output examples/out-of-scope.actual.json
python -m src.cli --data data/documents-d01-only.json --input examples/d01-only.input.json --backend claude --output examples/d01-only.actual.json
```

核对冲突输出必须同时出现 D01、D02、30 天、15 天及明确追问；资料外输出必须先有检索且不编造答案；D01 单文档输出应仅引用 D01 并回答 30 天。模型输出可能不完全一致，应按语义和引用重新判定。

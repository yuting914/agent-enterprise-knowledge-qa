"""Bounded model -> tool -> observation loop and answer validation."""

from __future__ import annotations

from typing import Any

from .tools import KnowledgeBase


TOOL_ACTIONS = {"search_documents", "read_excerpt"}
TERMINAL_ACTIONS = {"finish", "ask_clarification"}
HARD_STEP_LIMIT = 20


def _result(status: str, answer: str, citations: list, gaps: list, trace: list) -> dict:
    return {"status": status, "answer": answer, "citations": citations, "gaps": gaps, "trace": trace}


class KnowledgeAgent:
    def __init__(self, knowledge_base: KnowledgeBase, model: Any, max_steps: int = 8, fail_tool: str | None = None):
        if not 1 <= max_steps <= HARD_STEP_LIMIT:
            raise ValueError(f"max_steps must be between 1 and {HARD_STEP_LIMIT}")
        self.kb = knowledge_base
        self.model = model
        self.max_steps = max_steps
        self.fail_tool = fail_tool

    def run(self, question: str, history: list[dict] | None = None) -> dict:
        if not question.strip():
            raise ValueError("question must not be empty")
        history = history or []
        events: list[dict] = []
        trace: list[dict] = []
        read_docs: dict[str, dict] = {}
        for step in range(1, self.max_steps + 1):
            state = {"question": question, "history": history, "events": events, "step": step, "max_steps": self.max_steps}
            try:
                decision = self.model.decide(state)
            except Exception as exc:
                return _result("model_error", "模型入口失败，任务未完成。", [], [str(exc)], trace)
            action = decision.get("action")
            args = {key: decision.get(key, "") for key in ("query", "doc_id") if decision.get(key)}
            row = {"step": step, "action": action, "arguments": args, "reason": decision.get("reason", ""), "observation": {}}
            if trace:
                trace[-1]["next_action"] = action
            trace.append(row)
            if action in TOOL_ACTIONS:
                try:
                    if action == self.fail_tool:
                        raise OSError(f"injected {action} failure")
                    if action == "search_documents":
                        if not decision.get("query", "").strip():
                            raise ValueError("search query is empty")
                        observation = {"result": self.kb.search_documents(decision["query"])}
                    else:
                        doc_id = decision.get("doc_id", "")
                        observation = {"result": self.kb.read_excerpt(doc_id)}
                        read_docs[doc_id] = observation["result"]
                except (KeyError, OSError, ValueError) as exc:
                    observation = {"error": str(exc)}
                row["observation"] = observation
                events.append({"action": action, "arguments": args, "observation": observation})
                continue
            if action in TERMINAL_ACTIONS:
                citations = []
                invalid = None
                if not any(e["action"] == "search_documents" for e in events):
                    invalid = "search the knowledge base before concluding"
                for item in decision.get("citations", []):
                    doc_id, quote = item.get("doc_id", ""), item.get("quote", "")
                    doc = read_docs.get(doc_id)
                    if not doc or not quote or not any(quote in p["text"] for p in doc["passages"]):
                        invalid = f"unsupported citation: {doc_id}"
                        break
                    citations.append({"doc_id": doc_id, "version_date": doc["version_date"], "quote": quote})
                if action == "finish" and not decision.get("gaps") and not citations:
                    invalid = "answer without a verified citation or evidence gap"
                if action == "ask_clarification" and not decision.get("answer", "").strip():
                    invalid = "clarification requires a user-visible answer and question"
                if invalid:
                    row["observation"] = {"validation_error": invalid}
                    events.append({"action": action, "arguments": args, "observation": row["observation"]})
                    continue
                status = ("needs_clarification" if action == "ask_clarification" else
                          "tool_error" if any("error" in e["observation"] for e in events) and not citations else
                          "insufficient_evidence" if decision.get("gaps") else "answered")
                row["observation"] = {"status": status}
                row["next_action"] = "end"
                return _result(status, decision.get("answer", ""), citations, decision.get("gaps", []), trace)
            row["observation"] = {"validation_error": f"unknown action: {action}"}
            events.append({"action": str(action), "arguments": args, "observation": row["observation"]})
        if trace:
            trace[-1]["next_action"] = "limit_reached"
        return _result("incomplete_limit", "达到执行步数上限，任务未完成。", [], ["需要更多步骤或人工处理"], trace)

import json
import tempfile
import unittest
from pathlib import Path

from src.agent import KnowledgeAgent
from src.model import MockDecisionModel
from src.tools import KnowledgeBase


DATA = Path(__file__).resolve().parents[1] / "data" / "documents.json"


class FixedModel:
    def __init__(self, decisions):
        self.decisions = iter(decisions)

    def decide(self, state):
        return next(self.decisions)


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase(DATA)

    def test_conflicting_documents_are_both_retrieved(self):
        ids = {item["doc_id"] for item in self.kb.search_documents("差旅票据最晚何时提交")}
        self.assertTrue({"D01", "D02"}.issubset(ids))

    def test_paraphrase_retrieval(self):
        ids = [item["doc_id"] for item in self.kb.search_documents("登录口令忘了怎么处理")]
        self.assertIn("D03", ids)

    def test_out_of_scope_has_no_evidence(self):
        result = KnowledgeAgent(self.kb, MockDecisionModel()).run("食堂今天有什么菜？")
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertFalse(result["citations"])

    def test_mock_conflict_does_not_pick_a_deadline(self):
        result = KnowledgeAgent(self.kb, MockDecisionModel()).run("报销期限多久？")
        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual({item["doc_id"] for item in result["citations"]}, {"D01", "D02"})

    def test_tool_failure_becomes_observation(self):
        result = KnowledgeAgent(self.kb, MockDecisionModel(), fail_tool="search_documents").run("忘记密码怎么办？")
        self.assertEqual(result["status"], "tool_error")
        self.assertIn("error", result["trace"][0]["observation"])
        self.assertEqual(result["trace"][0]["next_action"], "finish")

    def test_step_limit_is_explicit(self):
        result = KnowledgeAgent(self.kb, MockDecisionModel(), max_steps=1).run("忘记密码怎么办？")
        self.assertEqual(result["status"], "incomplete_limit")
        self.assertEqual(len(result["trace"]), 1)

    def test_step_limit_cannot_be_disabled(self):
        with self.assertRaises(ValueError):
            KnowledgeAgent(self.kb, MockDecisionModel(), max_steps=21)

    def test_unsupported_quote_is_rejected(self):
        model = FixedModel([
            {"action": "search_documents", "query": "密码", "reason": "查找"},
            {"action": "read_excerpt", "doc_id": "D03", "reason": "读取"},
            {"action": "finish", "answer": "错误答案", "citations": [{"doc_id": "D03", "quote": "原文不存在"}], "reason": "回答"},
        ])
        result = KnowledgeAgent(self.kb, model, max_steps=3).run("密码怎么重置？")
        self.assertEqual(result["status"], "incomplete_limit")
        self.assertIn("validation_error", result["trace"][-1]["observation"])

    def test_terminal_decision_before_search_is_rejected(self):
        model = FixedModel([{"action": "finish", "answer": "没资料", "gaps": ["无资料"]}])
        result = KnowledgeAgent(self.kb, model, max_steps=1).run("食堂菜单")
        self.assertEqual(result["status"], "incomplete_limit")
        self.assertIn("validation_error", result["trace"][0]["observation"])

    def test_empty_clarification_is_rejected(self):
        model = FixedModel([
            {"action": "search_documents", "query": "报销"},
            {"action": "ask_clarification", "answer": "", "gaps": ["冲突"]},
        ])
        result = KnowledgeAgent(self.kb, model, max_steps=2).run("报销期限")
        self.assertEqual(result["status"], "incomplete_limit")
        self.assertIn("validation_error", result["trace"][-1]["observation"])

    def test_document_change_changes_answer(self):
        original = json.loads(DATA.read_text(encoding="utf-8"))
        original_answer = KnowledgeAgent(self.kb, MockDecisionModel()).run("忘记企业账号密码怎么办？")["answer"]
        for doc in original:
            if doc["id"] == "D03":
                doc["passages"][0]["text"] = "忘记企业账号密码时，员工应联系 IT 服务台人工重置。"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "documents.json"
            path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            changed = KnowledgeAgent(KnowledgeBase(path), MockDecisionModel()).run("忘记企业账号密码怎么办？")
        self.assertNotEqual(original_answer, changed["answer"])
        self.assertIn("IT 服务台人工重置", changed["answer"])
        self.assertIn("IT 服务台人工重置", changed["citations"][0]["quote"])

    def test_document_change_changes_decision(self):
        original = json.loads(DATA.read_text(encoding="utf-8"))
        before = KnowledgeAgent(self.kb, MockDecisionModel()).run("报销期限多久？")
        for doc in original:
            if doc["id"] == "D02":
                doc["passages"][0]["text"] = "差旅费用须在发生后 30 天内提交报销申请，并附原始票据。"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "documents.json"
            path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            after = KnowledgeAgent(KnowledgeBase(path), MockDecisionModel()).run("报销期限多久？")
        self.assertEqual(before["status"], "needs_clarification")
        self.assertEqual(after["status"], "answered")

    def test_context_follow_up_selects_approval_passage(self):
        history = [{"role": "user", "content": "远程办公访问怎么开通？"},
                   {"role": "assistant", "content": "请在 IT 服务台提交 VPN 开通申请。"}]
        result = KnowledgeAgent(self.kb, MockDecisionModel()).run("谁审批这个申请？", history)
        self.assertEqual(result["status"], "answered")
        self.assertIn("直属主管", result["answer"])
        self.assertEqual(result["citations"][0]["doc_id"], "D04")


if __name__ == "__main__":
    unittest.main()

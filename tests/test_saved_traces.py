"""Check committed real-model evidence without spending model credits."""

import json
import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
DOCUMENTS = {doc["id"]: doc for doc in json.loads((ROOT / "data" / "documents.json").read_text(encoding="utf-8"))}


def load(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}.actual.json").read_text(encoding="utf-8"))


class SavedTraceTests(unittest.TestCase):
    def test_all_citations_are_exact_passages(self):
        for name in ("clear", "conflict", "out-of-scope", "paraphrase", "follow-up", "tool-failure", "d01-only"):
            with self.subTest(name=name):
                run = load(name)
                self.assertEqual(run["run_info"]["backend"], "claude")
                for citation in run["citations"]:
                    doc = DOCUMENTS[citation["doc_id"]]
                    self.assertEqual(citation["version_date"], doc["version_date"])
                    self.assertTrue(any(citation["quote"] in p["text"] for p in doc["passages"]))

    def test_conflict_trace_shows_both_documents_and_clarification(self):
        run = load("conflict")
        self.assertEqual(run["status"], "needs_clarification")
        self.assertEqual({c["doc_id"] for c in run["citations"]}, {"D01", "D02"})
        self.assertTrue(all(part in run["answer"] for part in ("D01", "D02", "30 天", "15 天", "请")))
        self.assertEqual([row["action"] for row in run["trace"]],
                         ["search_documents", "read_excerpt", "read_excerpt", "ask_clarification"])

    def test_d01_only_trace_changes_to_direct_answer(self):
        run = load("d01-only")
        self.assertEqual(run["status"], "answered")
        self.assertEqual([c["doc_id"] for c in run["citations"]], ["D01"])
        self.assertIn("30 天", run["answer"])
        self.assertEqual([row["action"] for row in run["trace"]],
                         ["search_documents", "read_excerpt", "finish"])
        data = ROOT / "data" / "documents-d01-only.json"
        self.assertEqual(run["run_info"]["data_sha256"], hashlib.sha256(data.read_bytes()).hexdigest())

    def test_out_of_scope_trace_ends_without_fabricated_citation(self):
        run = load("out-of-scope")
        self.assertEqual(run["status"], "insufficient_evidence")
        self.assertFalse(run["citations"])
        searches = [row for row in run["trace"] if row["action"] == "search_documents"]
        self.assertTrue(searches)
        self.assertTrue(all(row["observation"]["result"] == [] for row in searches))

    def test_clear_paraphrase_and_follow_up_have_supported_answers(self):
        for name, doc_id in (("clear", "D03"), ("paraphrase", "D03"), ("follow-up", "D04")):
            with self.subTest(name=name):
                run = load(name)
                self.assertEqual(run["status"], "answered")
                self.assertIn(doc_id, {c["doc_id"] for c in run["citations"]})
                self.assertIn("read_excerpt", [row["action"] for row in run["trace"]])
        self.assertIn("直属主管", load("follow-up")["answer"])
        follow_up_queries = [row["arguments"].get("query", "") for row in load("follow-up")["trace"]
                             if row["action"] == "search_documents"]
        self.assertTrue(any("VPN" in query for query in follow_up_queries))

    def test_failure_trace_shows_observation_and_safe_stop(self):
        run = load("tool-failure")
        self.assertEqual(run["status"], "tool_error")
        self.assertFalse(run["citations"])
        self.assertTrue(any("error" in row["observation"] for row in run["trace"]))
        self.assertEqual(run["trace"][-1]["action"], "finish")


if __name__ == "__main__":
    unittest.main()

"""CLI entry point: python -m src.cli --input examples/clear.input.json."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .agent import KnowledgeAgent
from .model import ClaudeDecisionModel, MockDecisionModel
from .tools import KnowledgeBase


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise knowledge QA agent")
    parser.add_argument("--input", type=Path, help="JSON with question and optional history/fail_tool/max_steps")
    parser.add_argument("--question", help="Question when --input is not used")
    parser.add_argument("--history-file", type=Path, help="JSON array of previous user/assistant messages")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "documents.json")
    parser.add_argument("--backend", choices=["claude", "mock"], default="claude")
    parser.add_argument("--model", help="Claude model alias or ID; default: haiku")
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--fail-tool", choices=["search_documents", "read_excerpt"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8")) if args.input else {}
    question = args.question or payload.get("question", "")
    history = json.loads(args.history_file.read_text(encoding="utf-8")) if args.history_file else payload.get("history", [])
    fail_tool = args.fail_tool or payload.get("fail_tool")
    max_steps = payload.get("max_steps", args.max_steps)
    kb = KnowledgeBase(args.data)
    model = ClaudeDecisionModel(args.model or "haiku") if args.backend == "claude" else MockDecisionModel()
    result = KnowledgeAgent(kb, model, max_steps=max_steps, fail_tool=fail_tool).run(question, history)
    result["run_info"] = {"backend": args.backend, "model": model.model, "cli_version": model.cli_version,
                          "actual_models": sorted(getattr(model, "actual_models", [])),
                          "max_steps": max_steps, "injected_failure": fail_tool,
                          "data_name": args.data.name,
                          "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest()}
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()

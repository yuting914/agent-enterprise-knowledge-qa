"""Synthetic document search and exact passage reading."""

from __future__ import annotations

import json
import re
from pathlib import Path


def _normal(text: str) -> str:
    return "".join(re.findall(r"[\w\u4e00-\u9fff]+", text.lower()))


def _grams(text: str) -> set[str]:
    normalized = _normal(text)
    return {normalized[i : i + 2] for i in range(len(normalized) - 1)}


class KnowledgeBase:
    def __init__(self, path: str | Path):
        self.documents = json.loads(Path(path).read_text(encoding="utf-8"))
        ids = [doc["id"] for doc in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate document id")
        for doc in self.documents:
            if not all(doc.get(key) for key in ("id", "title", "version_date", "passages")):
                raise ValueError(f"incomplete document: {doc.get('id', '<unknown>')}")
        self.by_id = {doc["id"]: doc for doc in self.documents}

    def search_documents(self, query: str, limit: int = 5) -> list[dict]:
        query = query.strip()
        if not query:
            return []
        query_normal = _normal(query)
        query_grams = _grams(query)
        matches = []
        for doc in self.documents:
            fields = [doc["title"], *doc.get("keywords", []), *(p["text"] for p in doc["passages"])]
            overlap = len(query_grams & _grams(" ".join(fields)))
            phrase = sum(
                4 + min(len(_normal(word)), 6)
                for word in doc.get("keywords", [])
                if len(_normal(word)) >= 2 and _normal(word) in query_normal
            )
            score = phrase + overlap
            if score >= 2:
                matches.append((score, doc))
        matches.sort(key=lambda item: (-item[0], item[1]["id"]))
        return [
            {
                "doc_id": doc["id"],
                "title": doc["title"],
                "version_date": doc["version_date"],
                "scope": doc.get("scope", "未注明"),
                "score": score,
            }
            for score, doc in matches[:limit]
        ]

    def read_excerpt(self, doc_id: str) -> dict:
        if doc_id not in self.by_id:
            raise KeyError(f"unknown document id: {doc_id}")
        doc = self.by_id[doc_id]
        return {
            "doc_id": doc["id"],
            "title": doc["title"],
            "version_date": doc["version_date"],
            "scope": doc.get("scope", "未注明"),
            "passages": doc["passages"],
        }

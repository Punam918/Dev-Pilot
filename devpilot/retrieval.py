"""Transparent BM25 retrieval over bounded code/doc chunks; no vector DB claimed."""
from __future__ import annotations

import ast
import math
import re
from collections import Counter
from dataclasses import dataclass

from .safety import Workspace, SafetyError, TEXT_SUFFIXES, redact
from pathlib import Path


def tokens(text: str) -> list[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return re.findall(r"[a-z0-9]+", text.lower().replace("_", " "))


@dataclass
class Chunk:
    path: str
    start: int
    end: int
    symbol: str
    text: str


def chunks(workspace: Workspace) -> list[Chunk]:
    result: list[Chunk] = []
    for path in workspace.files():
        if Path(path).suffix not in TEXT_SUFFIXES and Path(path).name not in {"Dockerfile", "Makefile"}:
            continue
        try:
            text = workspace.read(path)
        except SafetyError:
            continue
        lines = text.splitlines()
        symbols: dict[int, str] = {}
        if path.endswith(".py"):
            try:
                tree = ast.parse(text)
                symbols = {n.lineno: n.name for n in ast.walk(tree)
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            except SyntaxError:
                pass
        for start in range(0, len(lines), 40):
            end = min(start + 60, len(lines))
            names = ", ".join(v for k, v in symbols.items() if start < k <= end)
            result.append(Chunk(path, start + 1, end, names, "\n".join(lines[start:end])))
    return result


def search(workspace: Workspace, query: str, limit: int = 5) -> dict:
    corpus = chunks(workspace)
    query_terms = set(tokens(query))
    if not corpus or not query_terms:
        return {"method": "BM25", "matches": [], "chunks_indexed": len(corpus)}
    counts = [Counter(tokens(f"{c.path} {c.symbol} {c.text}")) for c in corpus]
    lengths = [sum(count.values()) for count in counts]
    avg = sum(lengths) / len(lengths) or 1.0
    df = Counter(term for count in counts for term in count)
    scored: list[tuple[float, Chunk]] = []
    for chunk, count, length in zip(corpus, counts, lengths):
        score = 0.0
        for term in query_terms:
            freq = count[term]
            idf = math.log(1 + (len(corpus) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * freq * 2.2 / (freq + 1.2 * (0.25 + 0.75 * length / avg))
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: (-item[0], item[1].path, item[1].start))
    return {"method": "BM25; rebuilt from current snapshot", "chunks_indexed": len(corpus),
            "matches": [{"path": c.path, "start_line": c.start, "end_line": c.end,
                         "symbol": c.symbol, "score": round(score, 5), "text": redact(c.text[:5000])}
                        for score, c in scored[:limit]]}

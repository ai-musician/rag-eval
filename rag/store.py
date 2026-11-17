"""Index the corpus and search it: markdown sections, OpenAI embeddings + BM25, fused by rank.

    python -m rag.store build      # (re)build index/index.json from corpus/*.md
    python -m rag.store search "how is TP99 measured?"
"""
from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from rag.env import load_env

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
INDEX = ROOT / "index" / "index.json"
EMBED_MODEL = "text-embedding-3-small"
MAX_CHARS = 2400          # split longer sections by paragraph
RRF_K = 60                # reciprocal rank fusion constant

_TOKEN = re.compile(r"[a-z0-9_]+")
_STOP = set("a an and are as at be by for from how i in is it of on or that the this to was what when where which "
            "who why with does do can should".split())


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "intro"


# --- chunking -----------------------------------------------------------------

def chunk_markdown(path: Path) -> list[dict]:
    """One chunk per heading section (any level), with its heading path; long sections split by paragraph.
    Fenced code blocks are kept whole, so a `#` comment inside one is not mistaken for a heading."""
    chunks, heads, lines, in_fence = [], [], [], False

    def flush():
        body = "\n".join(lines).strip()
        if not body:
            return
        title = " > ".join(h for _, h in heads) or path.stem
        base = f"{path.stem}#{slug(heads[-1][1]) if heads else 'intro'}"
        parts, cur = [], ""
        for para in re.split(r"\n\s*\n", body):
            if cur and len(cur) + len(para) > MAX_CHARS:
                parts.append(cur)
                cur = ""
            cur = f"{cur}\n\n{para}" if cur else para
        if parts and len(cur) < 200:          # a tiny leftover (e.g. a closing ``` line) joins the part before
            parts[-1] = f"{parts[-1]}\n\n{cur}"
        else:
            parts.append(cur)
        for i, text in enumerate(parts):
            cid = base if i == 0 else f"{base}-p{i + 1}"
            while any(c["id"] == cid for c in chunks):     # repeated heading names in one file
                cid += "x"
            chunks.append({"id": cid, "file": path.name, "title": title, "text": text})

    for line in path.read_text().splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush()
            lines = []
            level = len(m.group(1))
            heads = [h for h in heads if h[0] < level] + [(level, m.group(2).strip())]
        else:
            lines.append(line)
    flush()
    return chunks


# --- embeddings ---------------------------------------------------------------

def embed(texts: list[str]) -> tuple[list[list[float]], int]:
    from openai import OpenAI
    load_env()
    resp = OpenAI().embeddings.create(model=EMBED_MODEL, input=texts)
    return [d.embedding for d in resp.data], resp.usage.total_tokens


def build() -> dict:
    chunks = [c for p in sorted(CORPUS.glob("*.md")) for c in chunk_markdown(p)]
    vectors, used = embed([f"{c['title']}\n\n{c['text']}" for c in chunks])
    for c, v in zip(chunks, vectors):
        c["vector"] = v
    INDEX.parent.mkdir(exist_ok=True)
    INDEX.write_text(json.dumps({"embed_model": EMBED_MODEL, "chunks": chunks}))
    return {"chunks": len(chunks), "embedding_tokens": used}


# --- search -------------------------------------------------------------------

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        data = json.loads(INDEX.read_text())
        docs = [tokens(f"{c['title']} {c['text']}") for c in data["chunks"]]
        df = Counter(t for d in docs for t in set(d))
        data["bm25"] = {"docs": [Counter(d) for d in docs], "lens": [len(d) for d in docs],
                        "avg": sum(len(d) for d in docs) / len(docs), "df": df, "n": len(docs)}
        _cache = data
    return _cache


def _bm25(query: list[str], b25: dict, k1: float = 1.5, b: float = 0.75) -> list[float]:
    scores = []
    for tf, length in zip(b25["docs"], b25["lens"]):
        s = 0.0
        for t in query:
            if t in tf:
                idf = math.log(1 + (b25["n"] - b25["df"][t] + 0.5) / (b25["df"][t] + 0.5))
                s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * length / b25["avg"]))
        scores.append(s)
    return scores


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def search(question: str, k: int = 5, query_vector: list[float] | None = None) -> list[dict]:
    """Hybrid search: rank by dense cosine and by BM25 separately, then reciprocal rank fusion."""
    data = _load()
    chunks = data["chunks"]
    qv = query_vector or embed([question])[0][0]
    dense = [_cosine(qv, c["vector"]) for c in chunks]
    sparse = _bm25(tokens(question), data["bm25"])
    fused = [0.0] * len(chunks)
    for scores in (dense, sparse):
        for rank, i in enumerate(sorted(range(len(chunks)), key=lambda i: -scores[i])):
            fused[i] += 1 / (RRF_K + rank + 1)
    top = sorted(range(len(chunks)), key=lambda i: -fused[i])[:k]
    return [{"id": chunks[i]["id"], "title": chunks[i]["title"], "text": chunks[i]["text"],
             "fused": round(fused[i], 5), "dense": round(dense[i], 4), "bm25": round(sparse[i], 3)}
            for i in top]


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        print(build())
    elif sys.argv[1:2] == ["search"]:
        for r in search(" ".join(sys.argv[2:])):
            print(f"{r['fused']:.4f}  dense {r['dense']:.3f}  bm25 {r['bm25']:6.2f}  {r['id']}")
    else:
        print(__doc__)

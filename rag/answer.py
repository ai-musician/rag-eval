"""Answer one question from the corpus: retrieve, then ask Claude to answer only from what was retrieved.

    python -m rag.answer "What does the rolling-upgrade test check?"
"""
from __future__ import annotations

import json
import sys

import anthropic

from rag.env import load_env
from rag.store import search

MODEL = "claude-opus-5-5"
TOP_K = 5

SYSTEM = """You answer questions about qa-automation-framework, a test automation project, using only the \
excerpts from its documentation that are given with each question.

- Answer only from the excerpts. Do not use outside knowledge about the project, and do not guess.
- If the excerpts do not contain the answer, set "answerable" to false and say briefly that the documentation \
does not cover it. A partial answer is fine if you say what is missing.
- Put the ids of the excerpts you relied on in "cited_ids". Cite only excerpts you actually used.
- Keep the answer short: two to five sentences, with exact numbers and names from the excerpts."""

SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "answerable": {"type": "boolean"},
        "cited_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "answerable", "cited_ids"],
    "additionalProperties": False,
}


def build_user_message(question: str, hits: list[dict]) -> str:
    excerpts = "\n\n".join(
        f'<excerpt id="{h["id"]}" section="{h["title"]}">\n{h["text"]}\n</excerpt>' for h in hits)
    return f"<excerpts>\n{excerpts}\n</excerpts>\n\nQuestion: {question}"


def answer(question: str, client: anthropic.Anthropic | None = None, model: str = MODEL) -> dict:
    """The app's entry point: everything the eval needs comes back in one dict."""
    load_env()
    client = client or anthropic.Anthropic(max_retries=4)
    hits = search(question, k=TOP_K)
    user = build_user_message(question, hits)
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    result = {"model": response.model, "stop_reason": response.stop_reason,
              "usage": response.usage.model_dump(), "system": SYSTEM, "user_message": user,
              "retrieved": [{k: h[k] for k in ("id", "fused", "dense", "bm25")} for h in hits]}
    if response.stop_reason != "end_turn":
        return result | {"answer": None, "answerable": None, "cited_ids": []}
    text = next(b.text for b in response.content if b.type == "text")
    return result | json.loads(text)


if __name__ == "__main__":
    out = answer(" ".join(sys.argv[1:]))
    print(json.dumps({k: out[k] for k in ("answer", "answerable", "cited_ids", "retrieved", "model")}, indent=2))

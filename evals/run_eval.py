"""Run the golden set through the real entry point (rag.answer.answer), grade every answer, write results.

    python -m evals.run_eval --limit 5 --reps 1          # pilot
    python -m evals.run_eval --reps 3                     # full baseline
    python -m evals.run_eval --approve-harness            # after you change the app or the grader on purpose

Writes .claude/hillclimb/repo-qa/<variant>/results.jsonl, traces/<id>_rep<k>.json and errors.jsonl.
Resumable: a (case, rep) already in results.jsonl is skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import random
import time
from pathlib import Path

import anthropic

from evals.judge import judge
from rag.answer import MODEL, answer
from rag.env import load_env

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "evals" / "golden.jsonl"
FLOW = ROOT / ".claude" / "hillclimb" / "repo-qa"
HARNESS = [ROOT / "evals" / "run_eval.py", ROOT / "evals" / "judge.py",
           ROOT / "rag" / "answer.py", ROOT / "rag" / "store.py"]
SHA_FILE = FLOW / ".harness_sha"


def harness_sha() -> str:
    h = hashlib.sha256()
    for p in HARNESS:
        h.update(p.read_bytes())
    return h.hexdigest()


def load_cases(limit: int | None, ids: str | None = None) -> list[dict]:
    cases = [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]
    if ids:
        wanted = ids.split(",")
        missing = set(wanted) - {c["id"] for c in cases}
        if missing:
            raise SystemExit(f"unknown case ids: {sorted(missing)}")
        cases = [c for c in cases if c["id"] in wanted]
    return cases[:limit] if limit else cases


def grade(case: dict, out: dict, verdict: dict | None) -> dict:
    """Every metric id on every case; None where a metric does not apply (unanswerable questions)."""
    abstained = out["answerable"] is False
    if case["answerable"]:
        hit = bool(set(case["expected_ids"]) & {r["id"] for r in out["retrieved"]})
        cited = bool(set(case["expected_ids"]) & set(out["cited_ids"]))
        return {"correct": float(verdict["correct"] and not abstained), "grounded": float(verdict["grounded"]),
                "abstain_ok": float(not abstained), "retrieval_hit": float(hit), "cited_ok": float(cited)}
    return {"correct": float(abstained), "grounded": float(verdict["grounded"]) if verdict else 1.0,
            "abstain_ok": float(abstained), "retrieval_hit": None, "cited_ok": None}


def run_case(client: anthropic.Anthropic, case: dict) -> tuple[dict, dict, dict | None]:
    t0 = time.monotonic()
    out = answer(case["question"], client=client)
    latency = time.monotonic() - t0
    if out["stop_reason"] != "end_turn":
        return out | {"latency_s": latency}, {}, None
    if not out["model"].startswith(MODEL):
        raise RuntimeError(f"answer served by {out['model']}, expected {MODEL}")
    excerpts = out["user_message"].split("\n\nQuestion:")[0]
    verdict = None
    if case["answerable"] or out["answerable"]:        # judge any answer the bot actually gave
        verdict = judge(client, case["question"], case.get("reference") or "(no answer exists)",
                        excerpts, out["answer"])
    return out | {"latency_s": latency}, grade(case, out, verdict), verdict


def trace(out: dict, verdict: dict | None) -> list[dict]:
    turns = [{"role": "system", "content": out["system"]}, {"role": "user", "content": out["user_message"]},
             {"role": "assistant", "content": json.dumps(
                 {k: out.get(k) for k in ("answer", "answerable", "cited_ids")}, indent=2)}]
    if verdict:
        turns.append({"role": "tool_result", "content": "judge: " + json.dumps(
            {k: verdict[k] for k in ("correct", "grounded", "explanation")}, indent=2)})
    return turns


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids", help="comma-separated case ids to run (e.g. a pilot)")
    ap.add_argument("--timeout-s", type=float, default=180)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--approve-harness", action="store_true")
    args = ap.parse_args()

    FLOW.mkdir(parents=True, exist_ok=True)
    if args.approve_harness:
        SHA_FILE.write_text(harness_sha())
        print("harness approved:", SHA_FILE.read_text()[:12])
        return
    if not SHA_FILE.exists() or SHA_FILE.read_text() != harness_sha():
        raise SystemExit("The app or grader changed since it was last approved. Review the change, then run "
                         "with --approve-harness (that decision is yours, not the tool's).")

    load_env()
    client = anthropic.Anthropic(max_retries=4)
    vdir = FLOW / args.variant
    (vdir / "traces").mkdir(parents=True, exist_ok=True)
    results, errors = vdir / "results.jsonl", vdir / "errors.jsonl"
    done = {(r["prompt_id"], r["rep"]) for r in map(json.loads, results.read_text().splitlines())} \
        if results.exists() else set()
    todo = [(c, rep) for c in load_cases(args.limit, args.ids) for rep in range(args.reps) if (c["id"], rep) not in done]
    sem, lock = asyncio.Semaphore(args.concurrency), asyncio.Lock()
    print(f"{len(todo)} attempts to run ({len(done)} already done)")

    async def one(case: dict, rep: int) -> None:
        async with sem:
            await asyncio.sleep(random.uniform(0, 0.5))
            try:
                out, g, verdict = await asyncio.wait_for(asyncio.to_thread(run_case, client, case), args.timeout_s)
            except Exception as e:                       # harness failures never take a (case, rep) slot
                kind = "timeout" if isinstance(e, TimeoutError) else type(e).__name__
                async with lock:
                    with errors.open("a") as f:
                        f.write(json.dumps({"prompt_id": case["id"], "rep": rep, "failure": kind, "error": str(e)}) + "\n")
                print(f"  ERROR {case['id']} rep{rep}: {kind}: {e}")
                return
            status = "ok" if out["stop_reason"] == "end_turn" else \
                "truncated" if out["stop_reason"] == "max_tokens" else out["stop_reason"]
            row = {"prompt_id": case["id"], "rep": rep, "prompt": case["question"], "tags": case["tags"],
                   "status": status, "stop_reason": out["stop_reason"], "grade": g,
                   "explanation": {"correct": verdict["explanation"]} if verdict else {},
                   "model": out["model"], "usage": out["usage"], "latency_s": round(out["latency_s"], 2),
                   "judge_model": verdict["judge_model"] if verdict else None,
                   "judge_usage": verdict["judge_usage"] if verdict else None,
                   "meta": {"retrieved": [r["id"] for r in out["retrieved"]], "cited": out.get("cited_ids"),
                            "expected": case.get("expected_ids"), "answer": out.get("answer")}}
            (vdir / "traces" / f"{case['id']}_rep{rep}.json").write_text(json.dumps(trace(out, verdict), indent=2))
            async with lock:
                with results.open("a") as f:
                    f.write(json.dumps(row) + "\n")
            print(f"  {case['id']:<28} rep{rep} correct={g.get('correct')} hit={g.get('retrieval_hit')}")

    await asyncio.gather(*(one(c, r) for c, r in todo))
    summarize(results)


def wilson(p: float, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z = 1.96
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def summarize(results: Path) -> None:
    rows = [r for r in map(json.loads, results.read_text().splitlines()) if r["status"] == "ok"]
    print(f"\n{len(rows)} graded attempts")
    for metric in ("correct", "grounded", "abstain_ok", "retrieval_hit", "cited_ok"):
        vals = [r["grade"][metric] for r in rows if r["grade"].get(metric) is not None]
        if vals:
            p = sum(vals) / len(vals)
            lo, hi = wilson(p, len(vals))
            print(f"  {metric:<14} {p:6.1%}  (95% CI {lo:.0%}-{hi:.0%}, n={len(vals)})")
    ans = [r for r in rows if "unanswerable" not in r["tags"]]
    un = [r for r in rows if "unanswerable" in r["tags"]]
    if un:
        false_abstain = sum(1 for r in ans if r["grade"]["abstain_ok"] == 0)
        print(f"  refused correctly on {sum(r['grade']['abstain_ok'] for r in un):.0f}/{len(un)} unanswerable; "
              f"wrongly refused {false_abstain}/{len(ans)} answerable")


if __name__ == "__main__":
    asyncio.run(main())

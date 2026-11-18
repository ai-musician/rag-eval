# rag-eval

A small retrieval-augmented Q&A assistant, and the evaluation harness that measures it.

The assistant answers questions about [qa-automation-framework](https://github.com/ai-musician/qa-automation-framework)
(its README, test plan and KPIs, at commit `f0c23eb`) and a Kubernetes troubleshooting runbook. It answers only from
retrieved excerpts, cites them, and says so when the docs don't cover a question.

The point of the repo is the eval harness. It runs a reviewed golden set through the real entry point, grades every answer on five
metrics with an LLM judge, and reports confidence intervals rather than single numbers.

## How it works

```
question ─► hybrid search (top 5) ─► Claude answers from excerpts only ─► {answer, answerable, cited_ids}
             dense + BM25, RRF              structured JSON output
```

| Piece | File | What it does |
|---|---|---|
| Chunking + index | `rag/store.py` | One chunk per markdown heading section with its heading path (`README > CI/CD > ...`); long sections split by paragraph; fenced code kept whole. Embedded with OpenAI `text-embedding-3-small` into `index/index.json`. |
| Retrieval | `rag/store.py` | Hybrid: cosine similarity and BM25 ranked separately, then merged with reciprocal rank fusion (k=60). Exact terms like `--previous` or `137` are found by BM25 even when embeddings miss them. |
| Answering | `rag/answer.py` | `claude-opus-5-5` with a JSON schema output: `answer`, `answerable`, `cited_ids`. The system prompt forbids outside knowledge. |
| Judge | `evals/judge.py` | `claude-sonnet-5-5` grades **correct** (states every key fact in the reference, contradicts none) and **grounded** (every claim is supported by the excerpts). Inputs are treated as data, not instructions. |
| Runner | `evals/run_eval.py` | Async, resumable, repeats each case N times, writes results + per-attempt traces, prints Wilson 95% CIs. |
| Golden set | `evals/build_golden.py` → `golden.jsonl`, `GOLDEN_REVIEW.md` | 48 cases (40 answerable, 8 that must be refused). |

### Golden set design

- **Expected sections can't drift from the index.** Each answerable case names *needles*, exact phrases from the
  corpus. The expected chunk ids are whichever chunks contain those phrases, so re-chunking doesn't silently break
  the labels.
- **Unanswerable cases are near misses, checked against the corpus.** They sit right next to covered topics. For
  example, a pod stuck in Pending is a neighbor of CrashLoopBackOff, which the runbook does cover. Each one lists terms that the
  build script verifies appear nowhere in the corpus, so "refused correctly" really means the answer wasn't there.
- **The judge was tested before it was trusted.** It was given an empty answer, an "I don't know", and a confidently
  wrong answer, and it marked all three incorrect.
- **Human review.** `GOLDEN_REVIEW.md` lists every question and reference answer for a human to check before they
  are used for scoring.

### Metrics

| Metric | Applies to | Passes when |
|---|---|---|
| `correct` | all | answerable: judge says correct and the bot didn't refuse · unanswerable: the bot refused |
| `grounded` | all | judge finds no claim outside the retrieved excerpts |
| `abstain_ok` | all | refused if and only if the case is unanswerable |
| `retrieval_hit` (Recall@5) | answerable | an expected section is in the top 5 |
| `cited_ok` | answerable | the bot cited an expected section |

Separating retrieval from generation shows where a wrong answer came from: the search missing the right section,
or the model mishandling the right excerpts.

### Guarding against misleading results

- **Frozen harness.** The runner hashes the app and the grader (`answer.py`, `store.py`, `judge.py`, `run_eval.py`)
  and refuses to run if they changed since the last `--approve-harness`. Scores from different code are never
  mixed silently.
- **Model pinning.** A run fails if the API served a different model than the one configured, for the answerer or
  the judge.
- **Harness errors don't count as wrong answers.** Timeouts and API errors go to `errors.jsonl` and the attempt
  is retried on the next run instead of being scored.

## Baseline results

48 cases × 3 repetitions = 144 graded attempts
(`.claude/hillclimb/repo-qa/baseline/results.jsonl`):

| Metric | Score | 95% CI |
|---|---|---|
| Correct | 100.0% | 97–100% (n=144) |
| Grounded | 99.3% | 96–100% (n=144) |
| Refusal OK | 100.0% | 97–100% (n=144) |
| Recall@5 | 100.0% | 97–100% (n=120) |
| Cited right | 100.0% | 97–100% (n=120) |

- Refused 24/24 unanswerable attempts; wrongly refused 0/120 answerable ones.
- Latency per answer (retrieval + generation): median 2.9 s, p90 3.8 s. Total API cost for the pilot, re-runs and
  full baseline: about $3.85.
- The one "ungrounded" verdict (`crashloop-what-to-check`) is borderline. The answer tied exit code 127 to a wrong
  command, while the excerpt says "exit code 1 or 127" for a wrong command *or image*. That reads as the judge being strict
  rather than a hallucination.
- **The first run's failures were in the test data, not the bot.** One case was missing an expected section (the
  fact also appeared in a summary section), and two reference answers demanded more than their questions asked for.
  They were fixed in `build_golden.py` before this baseline. Golden sets need debugging like any other test suite.

### Limitations

- **The ceiling is low.** The corpus is about 80 KB and the golden set has 48 cases written from that same corpus.
  A perfect score here shows the pipeline works, not that it would hold up on a large or messy document set.
  The next step would be harder cases: questions that need facts from several sections, paraphrases that share
  no words with the docs, and near-miss unanswerable questions.
- **The same model family answers and grades.** The judge is a different model from the answerer, but both are
  Claude. Running each case three times showed the judge is not perfectly consistent: about 2% of grounded verdicts
  flipped between runs of the same answer. A small human-graded sample would measure how often the judge agrees
  with a person.
- **Retrieval is brute force.** The index is a JSON file scanned in full, fine for the current 54 chunks. A larger corpus would need a vector store.

## Running it

Requires Python 3.12+, an Anthropic API key and an OpenAI API key (for embeddings).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cat > .env <<'EOF'
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
EOF

python -m rag.store build                                   # embed the corpus into index/index.json
python -m rag.store search "how is TP99 measured?"          # inspect retrieval scores
python -m rag.answer "What does the rolling-upgrade test check?"
```

Evaluate:

```bash
python -m evals.build_golden                                # regenerate golden.jsonl + GOLDEN_REVIEW.md
python -m evals.run_eval --approve-harness                  # only after reviewing a change to the app or grader
python -m evals.run_eval --limit 5 --reps 1                 # pilot
python -m evals.run_eval --reps 3                           # full baseline
python -m evals.run_eval --variant my-change --reps 3       # compare a change against baseline
```

`.env` and `index/` are git-ignored. Per-attempt traces are written under `.claude/hillclimb/repo-qa/<variant>/traces/`
and are not committed.

## Layout

```
corpus/        source documents (from qa-automation-framework @ f0c23eb, plus K8S_RUNBOOK.md)
rag/           store.py (chunk, embed, hybrid search) · answer.py (Claude, structured output) · env.py
evals/         build_golden.py · golden.jsonl · GOLDEN_REVIEW.md · judge.py · run_eval.py
.claude/hillclimb/repo-qa/   run state and baseline results
```

"""Build evals/golden.jsonl and evals/GOLDEN_REVIEW.md from the cases below.

Each answerable case names one or more *needles*: exact phrases from the corpus. The expected sections are the
chunks that contain them, so the expected ids can't drift from the index. Each unanswerable case names *absent*
terms that must appear nowhere in the corpus. Run: python -m evals.build_golden
"""
import json
from pathlib import Path

from rag.store import CORPUS, chunk_markdown

ROOT = Path(__file__).resolve().parent.parent

# (id, topic, source, question, needles, reference)
ANSWERABLE = [
    # --- your seeds (runbook) ---
    ("crashloop-what-to-check", "k8s-runbook", "seed",
     "What should I check when a pod is stuck in CrashLoopBackOff?",
     ["It is a symptom, not a cause", "logs <pod> --previous"],
     "It's a symptom: the container keeps exiting and is restarted with a growing back-off. Run get pods, "
     "describe pod (Last State, Reason, Exit Code, Events) and logs --previous, read the exit code, then check "
     "the common causes: configuration/Secret, wrong command or image, unreachable dependency, failing liveness "
     "probe, out of memory, permissions."),
    ("oomkilled-confirm", "k8s-runbook", "seed",
     "How do I confirm a pod was OOMKilled?",
     ["Last State: Terminated, Reason: OOMKilled"],
     "kubectl describe pod shows Last State Terminated, Reason OOMKilled, Exit Code 137 (or read "
     "lastState.terminated.reason with jsonpath); compare kubectl top usage with the container's memory limit."),
    # --- runbook ---
    ("exit-code-137", "k8s-runbook", "drafted", "What does exit code 137 usually mean for a container?",
     ["the container was killed with SIGKILL"],
     "SIGKILL: most often OOMKilled, or killed after a failed liveness probe."),
    ("logs-previous", "k8s-runbook", "drafted", "Why should I use kubectl logs with --previous on a failing pod?",
     ["shows the new container"],
     "Without it you see the new container, which often hasn't failed yet; why the last one died is in "
     "--previous (and under Last State in describe)."),
    ("oom-vs-eviction", "k8s-runbook", "drafted", "How is OOMKilled different from an eviction?",
     ["This is different from an **eviction**"],
     "OOMKilled: the container went over its memory limit and the kernel killed it (exit 137), then it restarts. "
     "Eviction: under node memory pressure the kubelet evicts whole pods, which show status Evicted."),
    ("api-memory-limit", "k8s-runbook", "drafted", "What memory request and limit does the API container have?",
     ["memory request of 128Mi and a limit of 256Mi"],
     "Request 128Mi, limit 256Mi (k8s/api.yaml)."),
    ("backoff-timing", "k8s-runbook", "drafted",
     "How long does Kubernetes wait between restarts of a crash-looping container?",
     ["capped at 5 minutes"],
     "Longer after each crash: 10 s, 20 s, 40 s and so on, capped at 5 minutes."),
    ("verify-fix", "k8s-runbook", "drafted", "After fixing a crash loop, how do I know the fix worked?",
     ["The RESTARTS count must stop growing"],
     "Watch the pod (kubectl get pods -w): the RESTARTS count must stop growing; for OOMKilled, compare memory "
     "under load before and after."),
    # --- chaos and upgrades ---
    ("chaos-graceful", "resilience", "drafted",
     "What happens to users when an inference pod is stopped gracefully during the chaos test?",
     ["Graceful shutdown works only because of"],
     "Not a single failed reply (about 490 replies, 0 failed, 100% availability); preStop lets open streams "
     "finish; back to 2 replicas in 1.3-1.6 s."),
    ("chaos-prestop", "resilience", "drafted", "Why does graceful pod shutdown need the preStop pause?",
     ["Graceful shutdown works only because of"],
     "Kubernetes removes the pod from the Service and signals the container at the same moment; without the "
     "pause 5 of 485 replies failed, with it 0."),
    ("chaos-crash", "resilience", "drafted", "How many replies fail when an inference pod crashes?",
     ["91.6–94.6%"],
     "29-46 of about 540 replies fail; availability 91.6-94.6%."),
    ("upgrade-broken", "resilience", "drafted",
     "What happens in the rolling-upgrade test when the new version is broken?",
     ["reports `ProgressDeadlineExceeded` after 30 s"],
     "The new pods crash at start and never become ready; the Deployment reports ProgressDeadlineExceeded after "
     "30 s and the test rolls back; not a single failed reply, two replicas available throughout."),
    ("upgrade-done-not-gone", "resilience", "drafted",
     "Why can old pods still answer requests after kubectl rollout status reports success?",
     ["doesn't mean the old pods have gone"],
     "rollout status reports success while old pods are still in their 5 s preStop pause and can finish replies; "
     "the tests now wait until those pods have exited."),
    ("upgrade-settings", "resilience", "drafted",
     "Which rolling-update settings does the inference Deployment use?",
     ["(`maxSurge: 1`, `maxUnavailable: 0`)"],
     "maxSurge: 1 and maxUnavailable: 0: one new pod at a time, an old one stops only when the new one is ready."),
    ("upgrade-negative-check", "resilience", "drafted",
     "How were the upgrade tests checked against settings that should make them fail?",
     ["28 of 282 replies failed"],
     "With preStop removed the good-version test failed (28 of 282 replies failed); with maxSurge 0 / "
     "maxUnavailable 1 the broken-version test failed (only 1 of 2 replicas available)."),
    # --- AWS ---
    ("aws-oidc", "aws", "drafted", "How does the AWS QA environment avoid storing AWS keys in GitHub?",
     ["No AWS keys in GitHub."],
     "CI signs in with GitHub's OIDC token for short-lived credentials; the role trusts only main of this "
     "repository and matches GitHub's immutable subject (owner and repository IDs)."),
    ("aws-self-terminate", "aws", "drafted",
     "What stops the AWS QA instance from running forever if CI never deletes it?",
     ["terminates itself after 60 minutes"],
     "It terminates itself after 60 minutes (shutdown with InstanceInitiatedShutdownBehavior: terminate)."),
    ("aws-budget", "aws", "drafted", "What AWS budget alert is configured?",
     ["85% and 100% of $5"],
     "A monthly budget alert in infra/aws-setup.yml: emails at 85% and 100% of $5, and when the forecast passes it."),
    # --- Docker and database ---
    ("docker-build-flag", "docker-db", "drafted", "Why do the docker compose commands use --build?",
     ["Why `--build`"],
     "The code is copied into the images at build time and Compose reuses an existing image, so without --build "
     "a run after a code change tests the old code; Docker rebuilds only what changed."),
    ("db-race", "docker-db", "drafted",
     "How does the database test for duplicate emails work, and how was it shown to be effective?",
     ["all 10 sign-ups succeeded"],
     "10 sign-ups with the same email at the same moment must give one 201 and nine 409; only the unique index on "
     "lower(email) prevents the race. Without the index all 10 succeeded and the test failed."),
    ("db-money", "docker-db", "drafted", "How do the database tests check that money amounts are stored correctly?",
     ["stored exactly"],
     "Amounts like 0.1 and 999999.99 must be stored exactly, which catches money kept in a float column."),
    ("db-tmpfs", "docker-db", "drafted", "Why is the Postgres data kept in memory (tmpfs)?",
     ["In memory (`tmpfs`), on purpose"],
     "Each docker compose down throws the data away so the next run starts empty, and memory is faster; a real "
     "service would use a named volume."),
    # --- performance ---
    ("login-tp99", "performance", "drafted", "What is the TP99 latency goal for login?",
     ["| login | 200 requests"],
     "TP99 at or below 250 ms."),
    ("login-many-users", "performance", "drafted",
     "Why does the login load test log in as 200 different users instead of one?",
     ["200 logins by one user mostly measure a cache"],
     "200 logins by one user mostly measure a cache and would run into per-user rate limits or lockout; the "
     "login_users fixture creates the users and their API keys with the admin key before timing starts."),
    ("inference-saturation", "performance", "drafted",
     "At what number of concurrent users does the mock inference service saturate, and what happens?",
     ["At 32, throughput stops growing"],
     "Up to 16 users throughput grows and TTFT stays flat; at 32 throughput stops growing (about 1,267 tokens/s) "
     "and TTFT jumps (TP99 821 ms) because requests queue for one of 16 batch slots."),
    ("ttft-slo", "performance", "drafted", "What is TTFT and what is its SLO in this project?",
     ["TP99 ≤ 250 ms, up to capacity"],
     "Time to first token, how long a user waits for a blank screen; SLO TP99 at or below 250 ms, up to capacity."),
    ("perf-not-parallel", "performance", "drafted", "Why aren't the load tests run in parallel with pytest-xdist?",
     ["Load tests never run in parallel"],
     "Parallel workers would compete for the CPU and distort each other's latency; the perf fixture skips them "
     "inside a worker, so pytest -m perf stays one process."),
    # --- test design, bugs, reporting, CI ---
    ("negative-cases", "test-design", "drafted", "How many negative test cases are there, and where are they kept?",
     ["76 invalid requests across 5 files", "76 data-driven negative cases"],
     "76 cases, kept as data in data/negative/*.json (5 files)."),
    ("bugs-count", "test-design", "drafted", "How many defects did the tests find in the mock API?",
     ["13 defects found in the API", "13 API defects found"],
     "13 defects, each with a guarding test and a severity."),
    ("bug-infinity", "test-design", "drafted", "Which bug allowed an infinite transaction amount, and how was it fixed?",
     ["(Infinity) was accepted"],
     "An amount of 1e309 (Infinity) was accepted and stored; the fix requires amounts to be finite."),
    ("secrets-masked", "reporting", "drafted", "How does the project keep API keys out of logs and reports?",
     ["Credentials are masked everywhere"],
     "utils/redact.py masks known key and token values and secret-looking fields in api.log, the HTML and Allure "
     "reports; CI refuses to publish the Allure report if a key is found in it."),
    ("perf-on-pr", "ci", "drafted", "When do the performance tests run on a pull request?",
     ["Performance tests are skipped when a change can't affect performance"],
     "Only if the API + UI job passed and a performance-relevant file changed (server code, tests/perf, utils, "
     "test setup, requirements or the workflow); at normal load on a PR and 3x load on a merge to main."),
    # --- KPIs ---
    ("change-failure-goal", "kpis", "drafted", "What is the goal for change failure rate, and why that number?",
     ["| Change failure rate |"],
     "At or below 15%, because the DORA elite band is 0-15%."),
    ("latency-callout", "kpis", "drafted", "When does the KPI review call out a latency regression?",
     ["**Regression callout:**"],
     "When TP99 is more than 40% above the median of the last 8 merges, after allowing for how much slower the "
     "whole run was, and at least 2 ms worse; it is a yellow callout, not a failed build."),
    ("red-kpi-build", "kpis", "drafted", "Does a red KPI metric fail the build?",
     ["The KPI job itself never fails the build"],
     "No: it is a callout at the top of the review and the build passes. Builds fail on functional test failures "
     "and on missed TP99 SLOs, errors or lost data under load."),
    ("flaky-not-measured", "kpis", "drafted", "Is the flaky test rate measured, and how would it be?",
     ["| Flaky test rate |"],
     "Not yet: it would come from CI reruns of the same commit (pytest-rerunfailures with its report), as tests "
     "that failed and then passed divided by all tests."),
    ("coverage-found-7", "kpis", "drafted", "What did the status-code coverage metric find on its first run?",
     ["listed 7 documented responses", "it listed 7 documented responses"],
     "7 documented responses no test checked (401 on five routes, two 404s); tests were added and it reports 35 / 35."),
    # --- test plan ---
    ("exit-criteria", "test-plan", "drafted", "What are the exit criteria in the test plan?",
     ["All functional tests (API, UI, database) pass"],
     "All functional tests pass; every documented endpoint and status code is tested (35 of 35); performance "
     "within every TP99 SLO with zero errors and lost records at 3x load on main; chaos and upgrade tests pass; "
     "no open critical bug."),
    ("out-of-scope", "test-plan", "drafted", "What is out of scope in the test plan?",
     ["**Out of scope:**"],
     "A real model, real payment rails, browsers other than Chromium in CI, and VM-image and operating-system "
     "testing."),
    ("release-signoff", "test-plan", "drafted", "Who signs off a release, according to the test plan?",
     ["QA sign-off: name and date"],
     "QA and the product owner, each with name and date, after review with the developers and product owner."),
]

# (id, topic, question, absent terms that must not appear in the corpus)
UNANSWERABLE = [
    ("imagepullbackoff", "k8s-runbook", "What causes a pod to be stuck in ImagePullBackOff?", ["ImagePullBackOff"]),
    ("pod-pending", "k8s-runbook", "How do I debug a pod that stays in Pending?", ["Pending"]),
    ("grafana", "kpis", "Which Grafana dashboards does the project use for monitoring?", ["Grafana"]),
    ("delete-user-tp99", "performance", "What is the TP99 SLO for deleting a user?", ["delete user |"]),
    ("azure", "aws", "How does the project run its tests on Azure?", ["Azure"]),
    ("kafka", "resilience", "Which Kafka topics does the inference service publish to?", ["Kafka"]),
    ("db-password-rotation", "docker-db", "How is the production database password rotated?", ["rotat"]),
    ("oncall-owner", "test-plan", "Which team is on call for the payments service?", ["payments service"]),
]


def main() -> None:
    chunks = [c for p in sorted(CORPUS.glob("*.md")) for c in chunk_markdown(p)]
    corpus_text = "\n".join(c["text"] for c in chunks)
    rows = []
    for cid, topic, source, q, needles, ref in ANSWERABLE:
        ids = sorted({c["id"] for c in chunks for n in needles if n in c["text"]})
        if not ids:
            raise SystemExit(f"{cid}: no chunk contains {needles}")
        rows.append({"id": cid, "question": q, "answerable": True, "expected_ids": ids, "reference": ref,
                     "tags": [topic, "answerable", source]})
    for cid, topic, q, absent in UNANSWERABLE:
        found = [a for a in absent if a.lower() in corpus_text.lower()]
        if found:
            raise SystemExit(f"{cid}: the corpus does mention {found}")
        rows.append({"id": cid, "question": q, "answerable": False, "expected_ids": [], "reference": None,
                     "tags": [topic, "unanswerable", "drafted"]})

    (ROOT / "evals" / "golden.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    lines = [f"# Golden set for review: {len(rows)} questions "
             f"({len(ANSWERABLE)} answerable, {len(UNANSWERABLE)} the bot must refuse)", "",
             "For each one: is the question realistic, and is the reference answer right and complete? "
             "The judge marks an answer correct only if it states every key fact in the reference.", "",
             "| # | id | topic | source | expected sections |", "|---|---|---|---|---|"]
    lines += [f"| {i} | {r['id']} | {r['tags'][0]} | {r['tags'][2] if r['answerable'] else 'must refuse'} | "
              f"{', '.join(r['expected_ids']) or '-'} |" for i, r in enumerate(rows, 1)]
    for i, r in enumerate(rows, 1):
        lines += ["", f"## {i}. {r['id']}", "", f"**Q:** {r['question']}", "",
                  f"**Reference:** {r['reference']}" if r["answerable"] else
                  "**Expected:** the bot says the documentation doesn't cover this (no answer from general knowledge)."]
    (ROOT / "evals" / "GOLDEN_REVIEW.md").write_text("\n".join(lines) + "\n")
    print(f"{len(rows)} cases written; expected-section counts:",
          sorted({len(r['expected_ids']) for r in rows if r['answerable']}))


if __name__ == "__main__":
    main()

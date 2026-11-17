# Golden set for review: 48 questions (40 answerable, 8 the bot must refuse)

For each one: is the question realistic, and is the reference answer right and complete? The judge marks an answer correct only if it states every key fact in the reference.

| # | id | topic | source | expected sections |
|---|---|---|---|---|
| 1 | crashloop-what-to-check | k8s-runbook | seed | K8S_RUNBOOK#crashloopbackoff, K8S_RUNBOOK#first-three-commands-for-any-failing-pod |
| 2 | oomkilled-confirm | k8s-runbook | seed | K8S_RUNBOOK#oomkilled |
| 3 | exit-code-137 | k8s-runbook | drafted | K8S_RUNBOOK#crashloopbackoff |
| 4 | logs-previous | k8s-runbook | drafted | K8S_RUNBOOK#first-three-commands-for-any-failing-pod |
| 5 | oom-vs-eviction | k8s-runbook | drafted | K8S_RUNBOOK#oomkilled |
| 6 | api-memory-limit | k8s-runbook | drafted | K8S_RUNBOOK#oomkilled |
| 7 | backoff-timing | k8s-runbook | drafted | K8S_RUNBOOK#crashloopbackoff |
| 8 | verify-fix | k8s-runbook | drafted | K8S_RUNBOOK#after-the-fix |
| 9 | chaos-graceful | resilience | drafted | README#chaos-testing-losing-an-inference-pod-under-load |
| 10 | chaos-prestop | resilience | drafted | README#chaos-testing-losing-an-inference-pod-under-load |
| 11 | chaos-crash | resilience | drafted | README#chaos-testing-losing-an-inference-pod-under-load |
| 12 | upgrade-broken | resilience | drafted | K8S_RUNBOOK#crashloopbackoff, README#rolling-upgrades-releasing-under-load |
| 13 | upgrade-done-not-gone | resilience | drafted | README#rolling-upgrades-releasing-under-load-p2 |
| 14 | upgrade-settings | resilience | drafted | README#rolling-upgrades-releasing-under-load |
| 15 | upgrade-negative-check | resilience | drafted | README#rolling-upgrades-releasing-under-load |
| 16 | aws-oidc | aws | drafted | README#aws-qa-environment |
| 17 | aws-self-terminate | aws | drafted | README#aws-qa-environment |
| 18 | aws-budget | aws | drafted | README#aws-qa-environment |
| 19 | docker-build-flag | docker-db | drafted | README#or-in-docker-nothing-to-install-but-docker |
| 20 | db-race | docker-db | drafted | README#the-database-postgres-in-docker-p2 |
| 21 | db-money | docker-db | drafted | README#the-database-postgres-in-docker-p2, README#what-this-demonstrates |
| 22 | db-tmpfs | docker-db | drafted | README#the-database-postgres-in-docker |
| 23 | login-tp99 | performance | drafted | README#performance-testing |
| 24 | login-many-users | performance | drafted | README#performance-testing |
| 25 | inference-saturation | performance | drafted | README#inference-performance |
| 26 | ttft-slo | performance | drafted | README#inference-performance |
| 27 | perf-not-parallel | performance | drafted | README#design-decisions-p2 |
| 28 | negative-cases | test-design | drafted | README#how-the-requirements-are-covered, README#project-layout |
| 29 | bugs-count | test-design | drafted | README#finpay-qa-automation-framework, README#what-this-demonstrates |
| 30 | bug-infinity | test-design | drafted | README#bugs-found-in-the-mock-api-and-fixed-p2 |
| 31 | secrets-masked | reporting | drafted | README#reporting |
| 32 | perf-on-pr | ci | drafted | README#ci-cd-github-actions-p2 |
| 33 | change-failure-goal | kpis | drafted | KPIs#operational-excellence-the-health-of-main |
| 34 | latency-callout | kpis | drafted | KPIs#api-latency |
| 35 | red-kpi-build | kpis | drafted | KPIs#what-fails-the-build-and-what-doesn-t |
| 36 | flaky-not-measured | kpis | drafted | KPIs#not-measured-here-yet-and-how-it-would-be |
| 37 | coverage-found-7 | kpis | drafted | KPIs#review-cadence, README#qa-kpis-p2 |
| 38 | exit-criteria | test-plan | drafted | TEST_PLAN#exit-criteria-testing-is-done |
| 39 | out-of-scope | test-plan | drafted | TEST_PLAN#scope |
| 40 | release-signoff | test-plan | drafted | TEST_PLAN#release-sign-off-checklist |
| 41 | imagepullbackoff | k8s-runbook | must refuse | - |
| 42 | pod-pending | k8s-runbook | must refuse | - |
| 43 | grafana | kpis | must refuse | - |
| 44 | delete-user-tp99 | performance | must refuse | - |
| 45 | azure | aws | must refuse | - |
| 46 | kafka | resilience | must refuse | - |
| 47 | db-password-rotation | docker-db | must refuse | - |
| 48 | oncall-owner | test-plan | must refuse | - |

## 1. crashloop-what-to-check

**Q:** What should I check when a pod is stuck in CrashLoopBackOff?

**Reference:** It's a symptom: the container keeps exiting and is restarted with a growing back-off. Run get pods, describe pod (Last State, Reason, Exit Code, Events) and logs --previous, read the exit code, then check the common causes: configuration/Secret, wrong command or image, unreachable dependency, failing liveness probe, out of memory, permissions.

## 2. oomkilled-confirm

**Q:** How do I confirm a pod was OOMKilled?

**Reference:** kubectl describe pod shows Last State Terminated, Reason OOMKilled, Exit Code 137 (or read lastState.terminated.reason with jsonpath); compare kubectl top usage with the container's memory limit.

## 3. exit-code-137

**Q:** What does exit code 137 usually mean for a container?

**Reference:** SIGKILL: most often OOMKilled, or killed after a failed liveness probe.

## 4. logs-previous

**Q:** Why should I use kubectl logs with --previous on a failing pod?

**Reference:** Without it you see the new container, which often hasn't failed yet; why the last one died is in --previous (and under Last State in describe).

## 5. oom-vs-eviction

**Q:** How is OOMKilled different from an eviction?

**Reference:** OOMKilled: the container went over its memory limit and the kernel killed it (exit 137), then it restarts. Eviction: under node memory pressure the kubelet evicts whole pods, which show status Evicted.

## 6. api-memory-limit

**Q:** What memory request and limit does the API container have?

**Reference:** Request 128Mi, limit 256Mi (k8s/api.yaml).

## 7. backoff-timing

**Q:** How long does Kubernetes wait between restarts of a crash-looping container?

**Reference:** Longer after each crash: 10 s, 20 s, 40 s and so on, capped at 5 minutes.

## 8. verify-fix

**Q:** After fixing a crash loop, how do I know the fix worked?

**Reference:** Watch the pod (kubectl get pods -w): the RESTARTS count must stop growing; for OOMKilled, compare memory under load before and after.

## 9. chaos-graceful

**Q:** What happens to users when an inference pod is stopped gracefully during the chaos test?

**Reference:** Not a single failed reply (about 490 replies, 0 failed, 100% availability); preStop lets open streams finish; back to 2 replicas in 1.3-1.6 s.

## 10. chaos-prestop

**Q:** Why does graceful pod shutdown need the preStop pause?

**Reference:** Kubernetes removes the pod from the Service and signals the container at the same moment; without the pause 5 of 485 replies failed, with it 0.

## 11. chaos-crash

**Q:** How many replies fail when an inference pod crashes?

**Reference:** 29-46 of about 540 replies fail; availability 91.6-94.6%.

## 12. upgrade-broken

**Q:** What happens in the rolling-upgrade test when the new version is broken?

**Reference:** The new pods crash at start and never become ready; the Deployment reports ProgressDeadlineExceeded after 30 s and the test rolls back; not a single failed reply, two replicas available throughout.

## 13. upgrade-done-not-gone

**Q:** Why can old pods still answer requests after kubectl rollout status reports success?

**Reference:** rollout status reports success while old pods are still in their 5 s preStop pause and can finish replies; the tests now wait until those pods have exited.

## 14. upgrade-settings

**Q:** Which rolling-update settings does the inference Deployment use?

**Reference:** maxSurge: 1 and maxUnavailable: 0: one new pod at a time, an old one stops only when the new one is ready.

## 15. upgrade-negative-check

**Q:** How were the upgrade tests checked against settings that should make them fail?

**Reference:** With preStop removed the good-version test failed (28 of 282 replies failed); with maxSurge 0 / maxUnavailable 1 the broken-version test failed (only 1 of 2 replicas available).

## 16. aws-oidc

**Q:** How does the AWS QA environment avoid storing AWS keys in GitHub?

**Reference:** CI signs in with GitHub's OIDC token for short-lived credentials; the role trusts only main of this repository and matches GitHub's immutable subject (owner and repository IDs).

## 17. aws-self-terminate

**Q:** What stops the AWS QA instance from running forever if CI never deletes it?

**Reference:** It terminates itself after 60 minutes (shutdown with InstanceInitiatedShutdownBehavior: terminate).

## 18. aws-budget

**Q:** What AWS budget alert is configured?

**Reference:** A monthly budget alert in infra/aws-setup.yml: emails at 85% and 100% of $5, and when the forecast passes it.

## 19. docker-build-flag

**Q:** Why do the docker compose commands use --build?

**Reference:** The code is copied into the images at build time and Compose reuses an existing image, so without --build a run after a code change tests the old code; Docker rebuilds only what changed.

## 20. db-race

**Q:** How does the database test for duplicate emails work, and how was it shown to be effective?

**Reference:** 10 sign-ups with the same email at the same moment must give one 201 and nine 409; only the unique index on lower(email) prevents the race. Without the index all 10 succeeded and the test failed.

## 21. db-money

**Q:** How do the database tests check that money amounts are stored correctly?

**Reference:** Amounts like 0.1 and 999999.99 must be stored exactly, which catches money kept in a float column.

## 22. db-tmpfs

**Q:** Why is the Postgres data kept in memory (tmpfs)?

**Reference:** Each docker compose down throws the data away so the next run starts empty, and memory is faster; a real service would use a named volume.

## 23. login-tp99

**Q:** What is the TP99 latency goal for login?

**Reference:** TP99 at or below 250 ms.

## 24. login-many-users

**Q:** Why does the login load test log in as 200 different users instead of one?

**Reference:** 200 logins by one user mostly measure a cache and would run into per-user rate limits or lockout; the login_users fixture creates the users and their API keys with the admin key before timing starts.

## 25. inference-saturation

**Q:** At what number of concurrent users does the mock inference service saturate, and what happens?

**Reference:** Up to 16 users throughput grows and TTFT stays flat; at 32 throughput stops growing (about 1,267 tokens/s) and TTFT jumps (TP99 821 ms) because requests queue for one of 16 batch slots.

## 26. ttft-slo

**Q:** What is TTFT and what is its SLO in this project?

**Reference:** Time to first token, how long a user waits for a blank screen; SLO TP99 at or below 250 ms, up to capacity.

## 27. perf-not-parallel

**Q:** Why aren't the load tests run in parallel with pytest-xdist?

**Reference:** Parallel workers would compete for the CPU and distort each other's latency; the perf fixture skips them inside a worker, so pytest -m perf stays one process.

## 28. negative-cases

**Q:** How many negative test cases are there, and where are they kept?

**Reference:** 76 cases, kept as data in data/negative/*.json (5 files).

## 29. bugs-count

**Q:** How many defects did the tests find in the mock API?

**Reference:** 13 defects, each with a guarding test and a severity.

## 30. bug-infinity

**Q:** Which bug allowed an infinite transaction amount, and how was it fixed?

**Reference:** An amount of 1e309 (Infinity) was accepted and stored; the fix requires amounts to be finite.

## 31. secrets-masked

**Q:** How does the project keep API keys out of logs and reports?

**Reference:** utils/redact.py masks known key and token values and secret-looking fields in api.log, the HTML and Allure reports; CI refuses to publish the Allure report if a key is found in it.

## 32. perf-on-pr

**Q:** When do the performance tests run on a pull request?

**Reference:** Only if the API + UI job passed and a performance-relevant file changed (server code, tests/perf, utils, test setup, requirements or the workflow); at normal load on a PR and 3x load on a merge to main.

## 33. change-failure-goal

**Q:** What is the goal for change failure rate, and why that number?

**Reference:** At or below 15%, because the DORA elite band is 0-15%.

## 34. latency-callout

**Q:** When does the KPI review call out a latency regression?

**Reference:** When TP99 is more than 40% above the median of the last 8 merges, after allowing for how much slower the whole run was, and at least 2 ms worse; it is a yellow callout, not a failed build.

## 35. red-kpi-build

**Q:** Does a red KPI metric fail the build?

**Reference:** No: it is a callout at the top of the review and the build passes. Builds fail on functional test failures and on missed TP99 SLOs, errors or lost data under load.

## 36. flaky-not-measured

**Q:** Is the flaky test rate measured, and how would it be?

**Reference:** Not yet: it would come from CI reruns of the same commit (pytest-rerunfailures with its report), as tests that failed and then passed divided by all tests.

## 37. coverage-found-7

**Q:** What did the status-code coverage metric find on its first run?

**Reference:** 7 documented responses no test checked (401 on five routes, two 404s); tests were added and it reports 35 / 35.

## 38. exit-criteria

**Q:** What are the exit criteria in the test plan?

**Reference:** All functional tests pass; every documented endpoint and status code is tested (35 of 35); performance within every TP99 SLO with zero errors and lost records at 3x load on main; chaos and upgrade tests pass; no open critical bug.

## 39. out-of-scope

**Q:** What is out of scope in the test plan?

**Reference:** A real model, real payment rails, browsers other than Chromium in CI, and VM-image and operating-system testing.

## 40. release-signoff

**Q:** Who signs off a release, according to the test plan?

**Reference:** QA and the product owner, each with name and date, after review with the developers and product owner.

## 41. imagepullbackoff

**Q:** What causes a pod to be stuck in ImagePullBackOff?

**Expected:** the bot says the documentation doesn't cover this (no answer from general knowledge).

## 42. pod-pending

**Q:** How do I debug a pod that stays in Pending?

**Expected:** the bot says the documentation doesn't cover this (no answer from general knowledge).

## 43. grafana

**Q:** Which Grafana dashboards does the project use for monitoring?

**Expected:** the bot says the documentation doesn't cover this (no answer from general knowledge).

## 44. delete-user-tp99

**Q:** What is the TP99 SLO for deleting a user?

**Expected:** the bot says the documentation doesn't cover this (no answer from general knowledge).

## 45. azure

**Q:** How does the project run its tests on Azure?

**Expected:** the bot says the documentation doesn't cover this (no answer from general knowledge).

## 46. kafka

**Q:** Which Kafka topics does the inference service publish to?

**Expected:** the bot says the documentation doesn't cover this (no answer from general knowledge).

## 47. db-password-rotation

**Q:** How is the production database password rotated?

**Expected:** the bot says the documentation doesn't cover this (no answer from general knowledge).

## 48. oncall-owner

**Q:** Which team is on call for the payments service?

**Expected:** the bot says the documentation doesn't cover this (no answer from general knowledge).

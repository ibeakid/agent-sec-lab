# Coding-agent observations

Running log of how the coding agent (Claude Code) behaved while building and securing this lab.
Feeds D11 (attack the coding agent), D12 (harden Claude Code) and D14 (Coding Agent Security Policy).

Format: what happened → why it matters → which day it feeds.

## D1 – Build the target (2026-10-10)

- **Built something different from the written prompt.** `prompt.md` asked for 3 tools (`read_file`, `query_db(sql)`, `fetch_url`),
  a `docs/` folder with 3 company documents (one hiding an indirect prompt injection) and `.env` with `OPENAI_API_KEY=sk-fake-…`.
  The repo has 4 tools (adds `calculate` with `eval()`), `query_db(name)` with f-string SQLi instead of raw SQL, no `docs/`
  (only `data/notes.txt`, no injection payload), and `.env` holds AWS keys, a GitHub token and `ADMIN_API_KEY`.
  Whether these changes were agreed during the plan step is not recorded.
  → An agent's output can drift from the spec; diff the result against the request, don't trust the summary. → D14 (review agent output against spec)
- **The planned indirect-injection document is missing.** That's the main input for D7/D8/D11 indirect-injection tests and needs adding before then.
- **Agent-built code assumed `.env` exists.** `load_env` crashed when the file was missing; fixed in `296967b`.
  → Agent code encodes happy-path assumptions about the local environment. → D14

## D2 – Gitleaks (2026-10-10/11)

- **An empty CI workflow went unnoticed for a day.** `.github/workflows/.secret-scan.yml` was committed as 0 bytes (`74e4416`) and never ran;
  replaced in `2021266`. (Who created the empty file wasn't recorded.)
  → "There's a workflow file" ≠ "the check runs". Verify a green run in CI, for agent- and human-made pipelines alike. → D5, D14

## D3 – Semgrep (2026-10-11)

- **Mixed code and terminal commands in instructions led to shell commands being pasted into a `.py` file.**
  → When an agent hands over work, it should keep file contents and terminal commands clearly separate and labelled. → D14

## D4 – SCA / SBOM / container scanning (2026-10-12/13)

- **The agent stated a wrong fact from its own memory.** It told me `.env` contained the `sk-fake-…` OpenAI key and built a check question on it.
  Its memory had recorded the *prompt's* spec (see D1), not the actual file. It corrected itself after checking the scan output.
  → Agent memory is a persistence layer that can hold stale or wrong "facts" and is a poisoning target. → D11 (memory poisoning), D14 (verify memory against the repo)
- **The agent read the secrets file to answer a question.** To explain why Trivy missed `ADMIN_API_KEY`, it ran commands against `.env`:
  it printed variable names, then a masked value (first 4 / last 2 chars) and its length. It masked voluntarily, but nothing stopped a full read.
  → Nothing technical stops the agent from reading secrets in the workspace. → D12 (deny-read rules for `.env*`, hooks), D14
- **The agent made outbound network calls without asking.** It downloaded Trivy's checksum file and the 0.75.0 tarball from GitHub to verify the pinned SHA256.
  The goal was legitimate, but egress was unrestricted. → D11 (exfiltration path), D12 (network sandbox / allowlist)
- **The agent ran Docker on the host.** It built test images under separate tags (`agent-sec-lab:d4-test`, `:d4-min`) and deleted them afterwards, never touching `:latest`.
  This was well-scoped, but Docker access is effectively root on the host. → D12 (permission rules for `docker`)
- **Testing in a scratchpad caught the agent's own mistakes.**
  - A `sed` edit garbled the scratch copy of the Dockerfile (a `&` in the replacement). The build failed in the scratchpad, never in the repo.
  - Its first explanation for a leftover `wheel` CVE (the ensurepip bundled wheel) was wrong, and it added an unnecessary `rm` step.
    Testing found the real cause: `COPY . .` baked `sbom.cdx.json` into the image and Trivy re-scanned that embedded SBOM. The unnecessary step was dropped.
  → Agents produce plausible-but-wrong fixes. "Draft in a sandbox, test, then hand over" works; also give agents no write access to the real repo by default. → D12, D14
- **The agent verified its environment before handing over commands.** It found Docker unreachable from WSL and the image missing before I hit errors.
- **The agent respected the no-unasked-installs rule.** `jq` was missing; it used Python's `json` module rather than installing anything.
- **The agent couldn't verify CI itself** (no `gh` CLI), and said so instead of claiming the run passed. → D14 (report what was and wasn't verified)

## D5 – Threat model (2026-10-14)

- **Codex drafted `THREAT_MODEL.md`; Claude Code reviewed it; Codex revised.** The first draft was well-structured but generic. Most STRIDE cells would fit any LLM app,
  and the concrete findings from my own check-question answers (user-field injection, ADMIN_API_KEY in the system prompt, SSH push to main) weren't in it.
  → A polished agent draft can still miss the reviewer's specific findings. Check the draft against your own analysis, not just its structure. → D14
- **The reviewer was wrong too, and the second agent caught it by reading the code.** Claude's review claimed:
  (a) nothing documents the loopback `docker run` command; in fact the Dockerfile comment has it, and `OLLAMA_URL` is set to `host.docker.internal`.
  (b) the SQLi in `query_db` could write rows for stored injection; but sqlite3 `execute` rejects stacked statements ("You can only execute one statement at a time", verified locally).
  Writes are still possible through `calculate`'s `eval`, just not through the SQLi.
  → Cross-review worked in both directions, and in both cases the deciding step was checking the claim against the code. → D14
- **The revised model labels every claim by evidence type:** C = confirmed in code/config, O = NOTES observation, U = user report, H = untested hypothesis.
  That puts into practice the "separate observation from inference" rule from the plan revision. The H items (DNS rebinding, WSL reachability, agent SSH push, etc.) are the test backlog.

- **CI went red on an unchanged image.** After pinning the actions to SHAs (`5a01ad6`), `container-scan` failed: Debian had published a fix for CVE-2026-96889 (librsvg, HIGH),
  so `--ignore-unfixed` no longer filtered it out. It wasn't caused by the commit. librsvg is only in the image because of the full `python:3.11` base (README row #10).
  Fixed with a targeted, commented `apt-get install --only-upgrade` (option A). The agent tested it under a separate tag: gate exit 0, librsvg 2.60.0+dfsg-1+deb13u1; the test image was then deleted.
  → A gate backed by a live CVE database fails without any code change. It needs a scheduled scan and a defined response (patch / scoped exception / base change). → D14
- **The agent ran Docker on the host again** (build + `docker run` under the `:d5-test` tag, then `docker rmi`). The user asked it to check; no approval step was needed. → D6 (Docker approval rule)

### D5 – Required checks (2026-10-14/15)

- **Ruleset `protect-main`** (Active, default branch, empty bypass list): restrict deletions, block force pushes, PR required with 0 approvals,
  required checks `gitleaks` / `semgrep` / `trivy` with source GitHub Actions. Fork PR workflows from external contributors need approval.
- **4a: direct push to `main` rejected by the server.** An empty commit pushed over SSH got `GH013: Repository rule violations` (PR required, 3 checks expected).
  The local hooks showed "Skipped" and let the commit through. Same SSH credential an agent on this machine would use, so TB7 "agent pushes to main" moves from H to tested.
- **4b: a failing PR was blocked.** PR #1 added `lookup_role()` with an f-string SQL query. The local semgrep hook blocked the commit; `git commit --no-verify` skipped it in one flag.
  In CI `semgrep` failed, the merge button was disabled, and no "bypass rules" option was offered to the owner. → hooks are feedback, the server-side check is the control.
- **4c: fixed, then merged.** Parameterized query → all 3 checks green → merged as `e37ea25`.
- **CI went red on an unchanged image again, one day later.** The PR's `trivy` failed on 8 HIGH findings: curl CVE-2026-8286 / CVE-2026-8927
  across 4 binary packages from one source package (`+deb13u5` → `+deb13u7`), again from the `python:3.11` base, not the PR. `main` was red too.
  Per-CVE `--only-upgrade` lines don't scale, so PR #2 (`6f8d0c5`) replaced the librsvg line with `apt-get upgrade -y`. The agent tested it first on a clean `git archive` of `main`
  with `--pull` (gate exit 0, curl `+deb13u7`, librsvg `+deb13u1`; test image deleted). It went in its own PR, merged before 4b continued, so the test PR failed for one reason only.
  → Trade-off: builds are no longer reproducible (same Dockerfile, different packages on different days). → D6 (slim base), digest pin + Dependabot, scheduled scan
- **The agent read CI results through the unauthenticated GitHub REST API** (`curl` to `api.github.com`; `gh` isn't installed). Job steps and annotations were public; the job logs need auth,
  so the user pasted the Trivy table. Read-only and requested, but still unprompted outbound calls from the workstation. → D12 (egress allowlist)
- **Gates check exactly what their rule says.** The fix left a stray `f` prefix (`f"... = ?"`): harmless and correctly not flagged by the taint rule, and nothing in CI lints style.
  A typo in a commit message on `main` (`llm-=tool`) now stays, because force pushes are blocked. → D14 (a gate is not a review)
- **Residual risks the ruleset does not cover:**
  - An admin (or a token with admin rights) can edit or disable the ruleset, push, and re-enable it. It leaves a trace in the ruleset History and the account security log, but nothing blocks it.
  - "Source: GitHub Actions" binds the check to the Actions app, not to this workflow file. A PR can edit `container-scan.yml` so the `trivy` job exits 0, or add another job named `trivy`,
    and still produce a genuine green check. CODEOWNERS on `.github/` with required review would close this; not possible on a solo repo. → D13, D14
  - With 0 required approvals, anyone with write access (or an agent holding such a token) can self-merge a PR whose checks pass.
- **The runner image isn't pinned.** A job notice says `ubuntu-latest` moves to Ubuntu 26 from 2026-10-19, inside otherwise SHA-pinned CI. → D13 (supply chain)

## Plan revision (2026-10-13)

Status: **D1–D4 done; D5–D15 are planned, not yet done or verified.** Nothing in the table below is a working control yet.
Update 2026-10-15: **D5 done** (failing PR blocked, then merged once fixed; bypass list empty; see D5 – Required checks).

Before D5 I had Codex review the remaining plan, then had Claude Code check Codex's suggestions against the repo, then sent Claude's view back to Codex.
Codex's factual claims (README still says `.env` is committed, `/chat` trusts a self-declared `user`, `.trivyignore` ignores by rule ID) checked out.

- **Why the order changed:**
  - Gates and exceptions were being chosen without a threat model.
  - The agent risks in D1–D4 (secret reads, egress, Docker) were waiting until D12.
  - The container-secret fix was tied to D10, so the `.trivyignore` expiry was setting the schedule.
- **Where they disagreed:**
  - Codex's first D5 packed three days of work into one; Claude flagged it and Codex agreed.
  - Claude suggested testing D11 by switching guardrails off in the normal environment. Codex argued for a separate isolated environment where the only change is the guardrail settings, and that is the version adopted.
- **Every day is now done only when a control is shown to work**, not just when a tool is set up. Garak and OPA are optional.

| Day | Focus | Done when |
|---|---|---|
| D5 | One-page threat model; pin actions by SHA; required checks | A failing PR is blocked, then merges once fixed; admin bypass setting recorded. If the plan can't enforce it: record "CI detects, platform does not block" (not the same result) |
| D6 | Minimal coding-agent guardrails; container-secret fix; choose D11 isolation approach | Fake-secret reads blocked via Read *and* shell (`cat`, python, symlink); per test log: content read? which layer blocked? escalation requested?; hardened image has no `.env` |
| D7 | ZAP API DAST | Evidence it reached `POST /chat` (OpenAPI import, app logs); coverage and limits recorded |
| D8 | Add docs incl. injection doc; direct/indirect injection tests | Benign control, tool traces, explicit success criteria |
| D9 | Automated AI-security regression; update threat model | Mock-backend control tests kept separate from real-model tests |
| D10 | Tool authorization and data boundaries; finish D11 isolated env | Attacks fail, normal tasks still work; isolated env built and its isolation verified |
| D11 | Coding-agent attacks in an isolated env | Same cases before/after guardrails, with evidence |
| D12 | Finish permissions, sandbox, MCP controls | Coverage verified, remaining gaps listed |
| D13 | Supply-chain assessment + customer security questionnaire (from JD) | Evidence-backed answers; unimplemented items stated |
| D14 | Coding Agent Security Policy + article | Each rule traces to an observation, control or test |
| D15 | Portfolio + mock interview | Demo: finding → fix → CI prevents regression |

Scope for D8–D10: 3–5 representative attack cases, one complete attack chain, and the matching fixes.

→ Two agents cross-checking each other caught an overloaded plan, a weak experiment design and a timing error (Claude first said the D11 env could be built in D12, after D11).
  Cross-review is a supporting method, not proof: two agents agreeing doesn't make them right, and they can share wrong assumptions.
  What counts is which doubts it raised and how each was settled against the repo, official docs or an experiment. → D14 (review practices)

## Open follow-ups

- [ ] Fix README line 6 (still says `.env` is committed; it was removed from history in D2).
- [x] D5: check the repo is public (free plan: protected branches on public repos only; private needs a paid plan); require status checks, not reviews (no second reviewer).
- [ ] Pin the base image by digest and add `dependabot.yml` (github-actions + docker), plus a scheduled container scan, so live-CVE breaks show up outside PRs.
- [ ] Pin the runner image (`ubuntu-24.04`) or decide to accept `ubuntu-latest` moving to Ubuntu 26 on 2026-10-19.
- [ ] `lookup_role()` in `app/tools.py` is a leftover from the D5 gate test and is not registered as a tool. Keep it as a safe example or remove it.
- [ ] D5/D6: narrow `.trivyignore` from rule IDs to the `/app/.env` path (`.trivyignore.yaml`).
- [ ] D6: container-secret fix, before the `.trivyignore` exceptions expire on 2026-11-30. Keep the vulnerable build as a tagged baseline.
- [ ] Before D8: add the `docs/` folder with the indirect-injection document that D1 skipped.
- [ ] D11 isolated env: choose the approach in D6, have it built and verified by the end of D10 (separate distro/VM/devcontainer, throwaway clone with fake secrets only, no Docker socket, local receiver, egress allowlist).
  Verify isolation by testing, not by name: can it reach host dirs (WSL `/mnt/c` automount, devcontainer bind mounts), credentials or the Docker daemon?
- [ ] D6 coverage limit to record: a `.env*` deny blocks the agent reading the source (and so copying it), but a copy that already exists under another name in a readable location isn't protected by a name-based rule.
- [ ] Observation vs inference: memory poisoning (D4) is still only a hypothesis; what was observed was stale memory.

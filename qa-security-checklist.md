# QA & Security Checklist

Run by the **reviewer** agent on every ticket before merge. Sections 1–3 always apply; run 4–7 when the ticket touches that surface. Every item gets PASS / FAIL / N-A in the review verdict.

---

## 1. Secrets & configuration (always)
- [ ] No API tokens, keys, or credentials in source, tests, notebooks, or committed configs (D-Wave Leap token, Fingrid API key, ENTSO-E security token, Mapbox/MapTiler key, IBM Quantum token).
- [ ] All secrets read from environment through the single config module (`src/config.py` / `lib/env.ts`) — no scattered `os.environ` / `process.env` reads.
- [ ] `.env` in `.gitignore`; `.env.example` updated with every new variable (placeholder values only).
- [ ] No secrets in notebook outputs, experiment logs, or solution JSON artifacts.
- [ ] `git log -p` spot-check: no secret was committed then removed (if so, rotate the key — flag as CRITICAL).

## 2. Code quality & tests (always)
- [ ] Full test suite passes locally, run by the reviewer, not taken on trust.
- [ ] New code covered by tests that exercise the ticket's acceptance criteria (not just import smoke tests).
- [ ] Linters/type-checkers clean: `ruff check` + `mypy` (Python); `pnpm lint` + `pnpm typecheck` (Next.js).
- [ ] No dead code, commented-out blocks, or debug prints left in.
- [ ] Errors handled explicitly: external calls (APIs, solvers) have timeouts and typed exceptions; no bare `except:`.

## 3. Reproducibility & scientific integrity (always)
- [ ] Every stochastic path takes an explicit seed; seed logged alongside results.
- [ ] Experiment results include: git SHA, instance/config identifier, solver parameters, number of repetitions.
- [ ] Claims in docs/README match logged measurements exactly (no rounding-up, no dropped failure runs).
- [ ] Classical baselines tuned with comparable effort to quantum methods (reviewer judgment — flag asymmetry).
- [ ] Dependencies pinned (`uv.lock` / `requirements.txt` with versions / `pnpm-lock.yaml` committed).

## 4. Python & data pipeline (when touched)
- [ ] No `pickle.load` / `torch.load` on files from untrusted or downloaded sources (use JSON/parquet/safetensors).
- [ ] No `eval`, `exec`, `subprocess` with unsanitized strings; `shell=True` forbidden.
- [ ] HTTP calls: `timeout=` set, retries bounded, rate limits respected (Digitraffic, Fingrid, ENTSO-E ToS).
- [ ] Downloaded data validated before use (schema check with pydantic/pandera; reject NaN/inf where they'd poison a QUBO).
- [ ] External data licensing honored: source + license noted in `docs/data-sources.md`; attribution strings present where required (Digitraffic/Fintraffic CC BY 4.0, Fingrid, FMI open data).
- [ ] No personally identifying enrichment of AIS data (positions of vessels are public; do not join with crew/ownership personal data).

## 5. Quantum-specific (when touched)
- [ ] Hardware submission (D-Wave / IBM) is behind an explicit config flag, defaults OFF; simulator is the default path.
- [ ] Shot/read budget computed and printed before any hardware submission; hard cap enforced in code.
- [ ] QUBO matrices validated: symmetric/upper-triangular as the solver expects, no NaN/inf coefficients, penalty weights finite and logged.
- [ ] Decoded solutions are ALWAYS feasibility-checked against original constraints before being reported (annealers/QAOA return infeasible samples; reporting them as solutions is a correctness bug).
- [ ] Embedding/transpilation stats logged (chain length, circuit depth) so hardware results are interpretable.

## 6. Next.js frontend (when touched)
- [ ] No secret in any `NEXT_PUBLIC_` variable or client component (grep for `NEXT_PUBLIC_` in the diff).
- [ ] No `dangerouslySetInnerHTML`; any user-influenced or file-loaded string rendered as text, not HTML.
- [ ] Solution-artifact JSON parsed through a zod schema — malformed artifact fails loud, not with a broken UI.
- [ ] Server/client boundary respected: API keys and Node-only code in server components/route handlers only.
- [ ] No `npm install` of look-alike packages; new dependencies justified in the PR description and checked on npm (weekly downloads, repo, license).
- [ ] `pnpm audit` (or `npm audit`) — no high/critical vulnerabilities introduced.
- [ ] Static export/deploy config leaks nothing: `/public` contains only intended artifacts.

## 7. Repository hygiene (phase close)
- [ ] README quickstart actually works on a clean clone (reviewer executes it).
- [ ] Large data files not committed (git-lfs or download script instead); repo size sane.
- [ ] LICENSE present; third-party notebook/code snippets attributed.
- [ ] CI (GitHub Actions) green: lint + typecheck + tests on push.

---

**Severity guide:** CRITICAL = secret leaked / unsafe deserialization / infeasible solutions reported as valid. HIGH = missing tests on core math, unpinned solver deps, unvalidated external data in the pipeline. MEDIUM = lint/type failures, missing timeouts. LOW = style.

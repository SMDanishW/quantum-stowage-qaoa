# TICKETS — Container Stowage via QAOA

Status: TODO / IN-PROGRESS / IN-REVIEW / DONE. `[P]` = parallel-safe.

## Phase 0 — Scaffolding
**DoD:** clean clone → tests green in CI.
- **T0.1 — Python scaffold + CI** · DONE · merged 2026-07-19 · branch main (4fb187e) — uv project, package layout, pytest/ruff/mypy, GitHub Actions, LICENSE/README stub, docs skeleton.
  *AC:* CI green; placeholder test passes.

## Phase 1 — Ship model & instance generator
**DoD:** configurable instances with known-optimum toys for later solver validation.
**Demo (user gate):** `uv run python -m stowage.cli generate --containers 12 --ports 3 --seed 7` · `uv run pytest`
- **T1.1 — Ship & container schema** · DONE · merged 2026-07-19 · branch main (71dacab) — bay/row/tier slot model, container (weight, destination port, hazmat class), pydantic + JSON round-trip; stability proxy: vertical + transverse moment bounds.
  *AC:* round-trip tests; moment computation unit-tested against hand-calculated examples. 16 tests passing; reviewer APPROVE (fable).
- **T1.2 — Objective & feasibility checker** · DONE · merged 2026-07-19 · branch main (c61489e) — `check_feasibility` contract, overstowage objective (pairwise stack ordering vs port rotation), support/moment/hazmat separation constraints; independent of any encoding. 32 tests passing; reviewer APPROVE (fable).
  *AC:* adversarial tests per constraint; overstow count verified by hand on a 6-container example.
- **T1.3 — Instance generator** · DONE · merged 2026-07-19 · branch main (348fa95) — seeded feasible-by-construction generator with configurable knobs (containers, ports, weight spread, hazmat fraction); `--toy` flag caches brute-force optimum alongside instance JSON; `stowage.cli generate` subcommand; `.gitattributes` (`*.json text eol=lf`) for byte-identity on Windows. 100 tests passing; reviewer APPROVE (fable).
  *AC:* deterministic under seed (byte-verified); toys brute-forceable (<20s) with optimum cached alongside via `save_instance`.

## Phase 2 — QUBO encodings
**DoD:** two encodings behind one interface; ground states verified = brute-force optima on toys.
- **T2.1 — Encoding spec (architect-led)** · TODO — full math for one-hot x_{c,s} (penalties: one-slot-per-container, one-container-per-slot, moment via quadratic penalty or slack discretization — decide!, overstow pairwise terms, hazmat pairs) AND domain-wall slot-assignment variant; qubit-count table 8–20 containers for both.
  *AC:* spec merged; explicit decision + rationale on moment-constraint handling.
- **T2.2 — One-hot encoder + decoder** · TODO
  *AC:* toy ground states (exact eigensolver / exhaustive) equal cached brute-force optima; penalty_report logged.
- **T2.3 — Domain-wall encoder + decoder** · TODO
  *AC:* same ground-state verification; qubit-count reduction vs one-hot measured and asserted in a test.

## Phase 3 — QAOA & baselines
**DoD:** all methods run via CLI on both encodings; results reproducible.
- **T3.1 — QAOA core** · TODO — Qiskit Aer, p configurable, expectation via sampling, qubit guard, depth/2q-gate-count logging.
  *AC:* p=1 on 8-container toy recovers optimum within top-5 samples for ≥ 3/5 seeds.
- **T3.2 — Parameter strategies** · TODO — COBYLA-from-scratch, layer-wise, transfer-from-smaller (donor recorded); gradient-variance logging hook.
  *AC:* all three run on the same instance from one config; logs contain per-iteration energies + gradient variance.
- **T3.3 [P] — SA + constructive heuristic baselines** · TODO
  *AC:* SA feasibility ≥95% on 12-container instances; heuristic always feasible.
- **T3.4 [P] — PennyLane cross-check** · TODO — re-run one QAOA config in PennyLane; energies must agree with Qiskit within tolerance.
  *AC:* agreement test in CI (small instance).

## Phase 4 — Analysis studies
**DoD:** the three headline studies scripted, reproducible, written up.
- **T4.1 — Experiment runner** · TODO — config-driven sweeps (instance size × encoding × p × strategy × seeds) → parquet.
- **T4.2 — Encoding comparison study** · TODO — qubit count, feasibility rate, approximation ratio: one-hot vs domain-wall across sizes.
  *AC:* figures scripted; finding stated with confidence intervals over ≥10 seeds.
- **T4.3 — Depth & barren-plateau study** · TODO — approximation ratio and gradient variance vs p (1..5); parameter-strategy comparison.
  *AC:* gradient-variance-vs-depth figure; honest interpretation in writing.
- **T4.4 — Classical comparison & scaling** · TODO — QAOA vs SA vs heuristic vs brute-force optimum; time-to-solution.
  *AC:* the "here is where NISQ stands" figure + candid narrative.

## Phase 5 — Visualization & report
**DoD:** repo portfolio-ready; analysis notebook tells the full story.
- **T5.1 — 3D stowage viz** · TODO — Plotly bay/row/tier render, color by destination port, hazmat markers, before/after (heuristic vs QAOA best) side-by-side.
  *AC:* renders any instance+solution pair; embedded stills in README.
- **T5.2 — Written report** · TODO — paper-structured; explicit limitations section (instance sizes, simulator-only, penalty sensitivity).
- **T5.3 — Full-repo review + close** · TODO — reviewer checklist §7; scribe project summary.

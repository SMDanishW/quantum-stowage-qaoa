# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

---

## [0.6.0] — 2026-07-19

### Added
- `feat: domain-wall encoder + decoder` (T2.3, commit 13909de)
  - `DomainWallEncoding` implementing `EncodingBuild` interface — QAOA and SA run over DW encoding identically to one-hot via shared contract
  - Domain-wall QUBO: variables `d_{c,k}` encode container-slot assignments as monotone 0→1 transitions; valid assignments require consecutive wall states
  - Wall-validity penalty `P_dw`: penalises invalid (non-monotone) domain-wall states; independently verified by reviewer including boundary cases
  - Qubit-count reduction vs one-hot: asserted in a dedicated test; reduction matches D12 analysis from phase-2 spec
  - 2-hazmat-container fixture: hand-built instance parametrized over both encodings; exercises `H_haz` penalty terms previously untested in DW context
  - Ground-state verification: toy ground states (exhaustive sweep) equal cached brute-force optima for DW encoding
  - 151 tests passing (31 net-new from T2.3); reviewer APPROVE (opus)

### Phase 2 close
Phase 2 DoD ("two encodings behind one interface; ground states verified = brute-force optima on toys") met. All three tickets (T2.1, T2.2, T2.3) reviewed and approved. Carry-forwards into Phase 3: (a) T3.1 AC names "8-container toy" which exceeds the 26-qubit statevector guard — AC must be amended to target n=4 toy and assert recovery vs relaxed optimum; (b) toy optima are near-degenerate (mostly 0) — QAOA validation must use constrained-nonzero seed (s2) for objective discrimination; (c) DW `energy_scale_ratio` is dominated by `P_dw` (large) — may affect QAOA trainability and should be logged in the depth study.

---

## [0.5.0] — 2026-07-19

### Added
- `feat: one-hot QUBO encoder + decoder` (T2.2, commit c67efd1)
  - `EncodingBuild` interface: `Encoding.build(instance) -> (BQM, decode_fn)` — QAOA and SA run identically over both encodings via this contract
  - One-hot encoder: constructs QUBO over `x_{c,s}` binary variables; penalty terms for one-slot-per-container, one-container-per-slot, overstowage pairwise ordering, and hazmat separation
  - Moment constraint handled via soft quadratic penalty (decision rationale in `docs/specs/phase-2-spec.md`)
  - `PenaltyReport`: logged per-run breakdown of constraint penalty contributions
  - `OptimumRecord` extended with required `relaxed_optimal_objective` field — ground-state assertions now target the relaxed (moment-penalty-free) optimum; energy identity holds vs constrained optimum
  - Toy fixtures committed under `tests/fixtures/`; exhaustive 2^24 sweep confirms ground states equal cached brute-force optima
  - 120 fast unit tests + slow exhaustive sweep; reviewer APPROVE (fable)

### Changed
- `OptimumRecord` schema: added `relaxed_optimal_objective` (required field) — resolves §6 inconsistency in phase-2 spec where QUBO ground-state assertions were internally contradictory; user adjudicated "option B" (moments excluded from optimum target, energy identity preserved vs constrained optimum)

---

## [0.4.0] — 2026-07-19

### Added
- `feat: instance generator` (T1.3, commit 348fa95)
  - `InstanceGenerator` class: configurable knobs — container count, port count, weight spread, hazmat fraction, seed
  - Feasible-by-construction generation: every generated instance satisfies slot capacity and hazmat separation by design
  - `--toy` mode: brute-force optimum computed and cached alongside instance JSON via `save_instance`
  - `stowage.cli generate` subcommand: `--containers`, `--ports`, `--seed`, `--toy` flags
  - `.gitattributes`: `*.json text eol=lf` — prevents CRLF corruption of toy JSON fixtures on Windows, preserving byte-identity under seed
  - 100 unit tests; determinism byte-verified across platforms

### Phase 1 close
Phase 1 DoD ("configurable instances with known-optimum toys for later solver validation") met. All three tickets (T1.1, T1.2, T1.3) reviewed and approved (fable). Carry-forward items for Phase 2: D7 qubit-count table in phase1-spec.md is stale (n=12 → 3×2×3=18 slots → 216 one-hot vars; architect corrects in T2.1); T3.1 must include a nonzero-optimum seed (6 containers/3 ports/seed 2 → optimum 2); dual-RNG cosmetic improvement (SeedSequence([seed,1])) is optional.

---

## [0.3.0] — 2026-07-19

### Added
- `feat: objective & feasibility checker` (T1.2, commit c61489e)
  - `check_feasibility` function: independent contract for validating stowage solutions against all constraints
  - Overstowage objective: pairwise stack-ordering count vs port rotation sequence
  - Support constraints: every container assigned to exactly one slot, every slot holds at most one container
  - Moment bounds: vertical and transverse moment feasibility checks
  - Hazmat separation rules: class-pair exclusion zones enforced
  - 32 unit tests including adversarial cases per constraint; overstow count hand-verified on a 6-container example

---

## [0.2.0] — 2026-07-19

### Added
- `feat: ship & container schema` (T1.1, commit 71dacab)
  - `Ship`, `Container`, `SlotCoord`, `StowageInstance` Pydantic v2 schemas under `src/stowage/`
  - Slot index bijection: `(bay, row, tier)` ↔ flat integer; validated on construction
  - Vertical and transverse moment proxies for stability-bound checks
  - JSON round-trip via `save_instance` / `load_instance` helpers
  - 16 unit tests covering schema validation, round-trip identity, and hand-calculated moment examples

---

## [0.1.0] — 2026-07-19

### Added
- `chore: bootstrap Python project scaffold` (T0.1, commit 4fb187e)
  - `uv` project with `pyproject.toml`; package layout under `src/stowage/`
  - `pytest`, `ruff`, `mypy` configured; placeholder test suite passes
  - GitHub Actions CI workflow: lint → type-check → test on push/PR
  - `LICENSE`, `README.md` stub, `docs/` skeleton

### Phase 0 close
Phase 0 DoD ("clean clone → tests green in CI") met. T0.1 was the sole Phase 0 ticket; it was reviewed and approved with all three gates (pytest/ruff/mypy) passing. Phase 0 complete.

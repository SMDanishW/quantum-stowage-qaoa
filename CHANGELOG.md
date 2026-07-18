# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

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

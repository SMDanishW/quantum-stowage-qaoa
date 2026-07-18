# Phase 1 Close — Ship Model & Instance Generator

**Closed:** 2026-07-19  
**Tickets:** T1.1, T1.2, T1.3 — all DONE  
**Final commit:** 348fa95 (branch main)

---

## What was built

**T1.1 — Ship & container schema** (71dacab)  
Pydantic v2 schemas for `Ship`, `Container`, `SlotCoord`, `StowageInstance`. Slot index bijection `(bay, row, tier)` ↔ flat integer validated on construction. Vertical and transverse moment proxies. JSON round-trip via `save_instance` / `load_instance`. 16 tests.

**T1.2 — Objective & feasibility checker** (c61489e)  
`check_feasibility` contract independent of any encoding. Overstowage objective: pairwise stack-ordering count vs port rotation. Constraints: one-slot-per-container, one-container-per-slot, moment bounds, hazmat separation. 32 tests including adversarial cases; overstow count hand-verified on a 6-container example.

**T1.3 — Instance generator** (348fa95)  
`InstanceGenerator` with configurable knobs (container count, port count, weight spread, hazmat fraction, seed). Feasible-by-construction. `--toy` flag caches brute-force optimum alongside instance JSON. `stowage.cli generate` subcommand. `.gitattributes` (`*.json text eol=lf`). 100 tests; determinism byte-verified.

---

## Key reviewer findings

All three tickets received fable-reviewer APPROVE. No tickets were rejected or required rework cycles.

---

## Deviations from spec

None substantive. `.gitattributes` for CRLF safety was a carry-forward note from T1.1 review, fulfilled in T1.3 as planned.

---

## Open issues carried forward

1. **Stale qubit-count table (D7 in phase1-spec.md):** Numbers were computed before the 3×2×3 ship geometry was fixed. For n=12 containers and 18 slots (3 bays × 2 rows × 3 tiers), one-hot encoding requires 12×18 = 216 binary variables, not the figures in D7. Architect must correct this table in T2.1 before any qubit-count assertions are written into tests.

2. **Nonzero-optimum seed for T3.1 validation:** Spot-check during T1.3 review found that most toy instances with default seeds yield optimum overstowage = 0 (trivially solved). T3.1 must include at least one nonzero-optimum seed to exercise the solver meaningfully. Known nonzero case: 6 containers / 3 ports / seed 2 → optimum = 2.

3. **Dual-RNG cosmetic improvement (optional):** `SeedSequence([seed, 1])` for separating weight/hazmat random streams is a cosmetic improvement noted by the reviewer. Not a correctness issue; carry forward as low-priority for T1.3 patch or T2.x.

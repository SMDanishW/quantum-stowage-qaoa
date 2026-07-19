# Phase 2 Close — QUBO Encodings

**Closed:** 2026-07-19  
**Final commit:** 13909de (T2.3 merge)  
**Test count at close:** 151 passing

---

## What was built

Both QUBO encodings are implemented behind the `EncodingBuild` interface (`Encoding.build(instance) -> (BQM, decode_fn)`), so QAOA and SA run identically over either encoding.

| Ticket | Deliverable | Commit | Reviewer |
|--------|-------------|--------|----------|
| T2.1 | Encoding spec: full QUBO math (one-hot + domain-wall), qubit-count table, moment-constraint rationale | c67efd1 | APPROVE (fable) |
| T2.2 | One-hot encoder/decoder, `PenaltyReport`, `OptimumRecord.relaxed_optimal_objective`, toy fixtures, exhaustive 2^24 sweep | c67efd1 | APPROVE (fable) |
| T2.3 | Domain-wall encoder/decoder, wall-validity penalty `P_dw`, qubit-count reduction asserted, 2-hazmat parametrized test | 13909de | APPROVE (opus) |

---

## Key decisions

### Option-B adjudication (§6 inconsistency resolution)

Mid-T2.1 the architect identified an internal inconsistency in the spec: the QUBO ground state cannot simultaneously equal the constrained optimum (moments excluded from QUBO) and the full constrained optimum (moments included). The user adjudicated **option B**:

- QUBO ground-state assertions target the **relaxed optimum** (moment-penalty-free objective value).
- `OptimumRecord` gained a required `relaxed_optimal_objective` field to record this value alongside the constrained optimum.
- Energy identity is preserved: the QUBO energy at the ground state equals the relaxed objective, not the constrained objective.

**Lasting consequence:** every experiment report and thesis chapter that cites QAOA solution quality must compare against the *relaxed* optimum, not the full constrained optimum. The distinction must be stated explicitly in the written report (T5.2).

### Moment constraint as soft penalty

Moment bounds are enforced via a soft quadratic penalty term added to the QUBO rather than as hard constraints. Rationale: hard moment constraints cannot be encoded in a BQM without auxiliary variables that would inflate qubit count beyond the 26-qubit statevector guard on small instances. The penalty weight is configurable; sensitivity is a Phase 4 study item.

### Domain-wall encoding

The domain-wall encoder uses variables `d_{c,k}` encoding container-to-slot assignment as monotone 0→1 bit-string transitions. Valid states are enforced by penalty `P_dw`. Qubit reduction vs one-hot is approximately `(n_slots - 1) * n_containers` vs `n_slots * n_containers` — asserted in the test suite against the D12 analysis in `docs/specs/phase2-spec.md`.

---

## Deviations from spec

None material. The §6 amendment (option B) was resolved before implementation began and is captured in `docs/specs/phase2-spec.md`. The 2-hazmat fixture (T2.3) was a carry-forward requirement from the T2.2 reviewer, not in the original spec — added without deviation to the interface contract.

---

## Open issues carried forward into Phase 3

### R1 — T3.1 AC is unsatisfiable as written
The T3.1 acceptance criterion reads "p=1 on 8-container toy recovers optimum within top-5 samples for ≥ 3/5 seeds." An 8-container instance with 3×2×3=18 slots requires 144 one-hot qubits or ~126 domain-wall qubits — both exceed the 26-qubit statevector guard enforced by the qubit-count guard in the codebase. **T3.1 AC must be amended before implementation begins:**
- Target instance: n=4 containers (fits within 26-qubit guard on one-hot encoding).
- Optimum criterion: compare against **relaxed optimum** per option-B adjudication, not constrained optimum.

### R2 — Toy optima near-degenerate
All committed toy fixtures except the constrained-nonzero seed (6 containers, 3 ports, seed 2) have relaxed optimum = 0 (no overstowage). QAOA validation on zero-optimum instances cannot discriminate solution quality by objective value alone. Phase 3 experiments must use seed s2 as the primary validation instance; feasibility rate is the secondary metric for zero-optimum instances.

### R3 — DW energy_scale_ratio dominated by P_dw
The wall-validity penalty `P_dw` is necessarily large relative to the objective terms to suppress invalid states. This large penalty-to-objective ratio may hurt QAOA trainability by flattening the cost landscape for feasible states. The depth/barren-plateau study (T4.3) should log `energy_scale_ratio` alongside gradient variance to surface this effect.

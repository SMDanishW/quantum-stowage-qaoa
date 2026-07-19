# Phase 2 Spec — QUBO Encodings (one-hot & domain-wall)

Tickets: T2.1 (this spec), T2.2, T2.3. Author: architect. Status: ready for implementation.
Interfaces are contracts — implementer may not change signatures without returning to architect.
Continues D1–D8 numbering from `docs/specs/phase1-spec.md`; corrects D7 (see D12 table).

## 1. Objective

Deliver two encodings of a `stowage.instances.Instance` into a `dimod.BinaryQuadraticModel`
behind one interface: one-hot (one binary per container–slot pair) and domain-wall (per-container
slot register of `n_slots − 1` binaries). DoD (TICKETS.md Phase 2): both encodings behind one
interface; ground states verified equal to cached brute-force optima on toys. Every decoded
sample is judged by `check_feasibility` and nothing else; decoders never repair infeasibility.

## 2. Design decisions

**D9 — Moment bounds are NOT encoded in the QUBO (Phase 2).** *This is the T2.1 AC decision.*
The two candidate mechanisms were:
- *Quadratic penalty*: `M_v ≤ V_max` is an inequality; `P·(M_v − V_max)²` penalizes being
  *under* the bound too, so a bare quadratic penalty is mathematically wrong for inequalities.
  Rejected outright.
- *Slack discretization*: introduce `K` slack bits per inequality,
  `P_m·(M_v(x) + Δ·Σ_{j=0}^{K−1} 2^j y_j − V_max)²` with `Δ = V_max/(2^K − 1)`; `|M_t| ≤ T_max`
  needs **two** slack registers (it is two inequalities). Cost: `3K` extra qubits (K≈4 → 12
  qubits) and dense couplings between every assignment variable and every slack bit. On the
  only toy that fits the 26-qubit statevector guard (n=4, 24 one-hot qubits) this blows the
  budget and destroys ground-state verifiability — the entire Phase 2 DoD.

**Decision:** moments stay a post-hoc `check_feasibility` gate, not a QUBO term. Rationale:
(1) the generator sets bounds at 1.1× a witness (D6), so they rarely bind — R2 in phase1-spec
already flagged this; (2) slack bits make toy verification impossible; (3) honest reporting is
preserved because feasibility rate (which includes moment checks) is reported for every solver.

**AMENDED (T2.2 adjudication, option B).** Consequence of D9, established empirically by the
T2.2 implementer (seed scan 1–30 over (4,2), (6,3), (5,3), (6,2)): with this generator,
*nonzero cached optimum ⟺ moment bounds bind ⟺ relaxed optimum < cached optimum*. The QUBO's
true ground truth is therefore the **moment-relaxed optimum**, which is computed and cached
alongside the constrained one (see §5/§6). The relaxed-vs-cached comparison is **recorded,
not asserted** (informational; §6.1). Slack discretization is documented here as the Phase 4
penalty-sensitivity mechanism (SA-scale, no qubit guard); it is **not implemented** in
Phase 2 — no flag, no dead code.

**D10 — Support (no-floating) is a quadratic penalty, not structural.** In an assignment
encoding there is no variable-domain restriction that expresses "slot (b,r,t) requires (b,r,t−1)
occupied", so structural enforcement is impossible; penalty it is. The penalty (see §3) can go
*negative* when one-container-per-slot is violated (occupancy > 1 rewards the term); D11's
weight lemma makes the slot-collision penalty dominate that reward.

**D11 — Penalty weights: closed-form dominance lemma, not vibes.** Let
`f_max = n(n−1)/2` (upper bound on overstow: every unordered container pair inverts at most
once — D3 counts pairs). Weights:

```
P_sup = P_haz = f_max + 1
A     = (n + 1) · (f_max + 1)      # both one-hot validity families
```

*Lemma (one-hot):* any bitstring violating a constraint has energy strictly above every
feasible assignment's energy. Sketch: overstow/hazmat terms are non-negative. The only negative
contribution is the support term when a slot holds k>1 containers: total support reward is
bounded by `P_sup · n · e` where `e = Σ_s max(0, occ(s)−1)` is total excess occupancy (each
over-occupied slot below rewards at most `occ(above) ≤ n` per excess unit). Slot collisions
contribute `A · Σ_s C(occ(s),2) ≥ A·e` penalty, and `A = (n+1)(f_max+1) ≥ P_sup·n + f_max + 1`,
so net penalty per excess unit exceeds `f_max` — no infeasible state can undercut a feasible
one. The lemma is *empirically verified* by the full 2^N sweep in §6 on the smallest toy.
Domain-wall weight: see D14.

**D12 — Qubit counts (corrects stale D7).** Real `auto_ship_dims` (n_tiers=3, rows∈{2,3,4},
smallest grid ≥ ceil(1.25n), ties → more bays, then fewer rows). `S = n_slots`; one-hot
`= n·S`; domain-wall `= n·(S−1)`.

| n  | dims (b×r×t) | S  | one-hot | domain-wall | reduction |
|----|--------------|----|---------|-------------|-----------|
| 8  | 2×2×3        | 12 | 96      | 88          | 8.3 %     |
| 9  | 2×2×3        | 12 | 108     | 99          | 8.3 %     |
| 10 | 3×2×3        | 18 | 180     | 170         | 5.6 %     |
| 11 | 3×2×3        | 18 | 198     | 187         | 5.6 %     |
| 12 | 3×2×3        | 18 | 216     | 204         | 5.6 %     |
| 13 | 3×2×3        | 18 | 234     | 221         | 5.6 %     |
| 14 | 3×2×3        | 18 | 252     | 238         | 5.6 %     |
| 15 | 4×2×3        | 24 | 360     | 345         | 4.2 %     |
| 16 | 4×2×3        | 24 | 384     | 368         | 4.2 %     |
| 17 | 4×2×3        | 24 | 408     | 391         | 4.2 %     |
| 18 | 4×2×3        | 24 | 432     | 414         | 4.2 %     |
| 19 | 4×2×3        | 24 | 456     | 437         | 4.2 %     |
| 20 | 3×3×3        | 27 | 540     | 520         | 3.7 %     |

Toys: n=4 → 1×2×3 (S=6): one-hot 24, DW 20. n=5, n=6 → 1×3×3 (S=9): one-hot 45/54, DW 40/48.

**Honest reading (goes in the report):** for slot-assignment problems the domain-wall saving is
exactly one qubit per container (reduction = 1/S), because the per-container domain is the full
slot set. **Only the n=4 toy fits the ~26-qubit statevector guard under either encoding.** All
8–20-container rows are SA/heuristic/scaling-analysis territory; QAOA statevector runs are
n=4 only. Domain-wall's real differentiator here is penalty structure and energy-scale
behaviour, not qubit count — that is the Phase 4 study's framing. T2.3's reduction-assertion
test asserts the table values for n ∈ {4, 8, 12, 16, 20}.

**D13 — Decoders never repair (scientific integrity).** An unreadable register decodes to the
sentinel slot `−1`: one-hot register with popcount ≠ 1 → `−1`; domain-wall register not of the
form `1^k 0^(S−1−k)` → `−1`. `check_feasibility` already reports `−1` as out-of-range →
`assignment_valid=False` → counted infeasible in feasibility-rate statistics. *Alternative
(nearest-valid / argmax repair): rejected — it silently converts encoding failures into
feasible-looking samples and corrupts the encoding-comparison study.* Decoders are pure and
deterministic; no randomness, no tie-breaking heuristics needed because `−1` is the only
fallthrough.

**D14 — Domain-wall validity weight is computed, not fixed.** Invalid wall states make slot
indicators take values in {−1, 0, +1}, so *any* cross-register term can become a reward. A tight
closed-form bound is instance-dependent and error-prone; instead:

```
P_dw = 1 + Σ |bias|  over ALL linear and quadratic terms of the non-validity Hamiltonian
```

(computed at build time from the assembled objective + one-per-slot + support + hazmat terms).
This provably dominates any reward reachable by wall violations (total reward ≤ total absolute
non-validity coefficient mass) at the cost of being loose. The resulting energy-scale ratio is
logged in `penalty_report` — a large ratio degrading QAOA trainability is an *expected finding*
of the Phase 4 encoding study, not a bug to hide.

## 3. One-hot formulation (T2.2) — full math

Variables: `x_{c,s} ∈ {0,1}` for container `c` (id order) and slot `s ∈ {0..S−1}`; label
`f"x_{cid}_{s}"` (e.g. `"x_C3_7"`). `n·S` variables. Vartype BINARY.

Notation: `order(p)` = index in `port_rotation`; `stackpair(u, v)` ⇔ same bay & row,
`tier(u) > tier(v)`; `below(u)` = slot one tier down in the same stack (defined for tier > 0);
`adj(s, s′)` ⇔ Manhattan distance 1 in (bay,row,tier) — exactly D5.

**Objective (D3, exact):** for every ordered container pair `(a, b)` with
`order(dest_a) > order(dest_b)` and every slot pair `(u, v)` with `stackpair(u, v)`:

```
H_obj = Σ  x_{a,u} · x_{b,v}          (coefficient +1 per term)
```

At any valid assignment `A`, `H_obj(x_A) = overstow_count(instance, A)` exactly (integers).

**Penalties:**

```
H_cont = A · Σ_c ( Σ_s x_{c,s} − 1 )²                        # one slot per container (equality)
       = A · Σ_c [ −Σ_s x_{c,s} + 2 Σ_{s<s′} x_{c,s}x_{c,s′} + 1 ]   # +A·n constant → BQM offset

H_slot = A · Σ_s Σ_{c<c′} x_{c,s} · x_{c′,s}                 # ≤1 container per slot (inequality: no linear part; S > n so slots may be empty)

H_sup  = P_sup · Σ_{u: tier(u)>0} [ Σ_c x_{c,u}  −  Σ_c Σ_{c′} x_{c,u} · x_{c′,below(u)} ]
         # = occ(u)·(1 − occ(below(u))); include c′ = c (that product is 0 in valid states)

H_haz  = P_haz · Σ_{ {a,b} hazmat pairs } Σ_{ {s,s′}: adj(s,s′) } ( x_{a,s}x_{b,s′} + x_{a,s′}x_{b,s} )
```

Weights per D11. Total `H = H_obj + H_cont + H_slot + H_sup + H_haz`, with the `+A·n` constant
placed in the BQM **offset** so that for every fully feasible assignment `A`:
`bqm.energy(encode(A)) == overstow_count(instance, A)` exactly. Moments: excluded per D9.

Encoding helper (needed by tests and the decoder's inverse): `encode_assignment(instance,
assignment) -> dict[str, int]` mapping a Phase 1 `Assignment` to a one-hot sample.

**Decoder:** for each container, collect `{s : sample[f"x_{cid}_{s}"] == 1}`; singleton → that
slot; otherwise `−1` (D13). Returns `Assignment` (`dict[str, int]`, total over containers).

## 4. Domain-wall formulation (T2.3) — full math

Per container `c`: register `d_{c,1} … d_{c,S−1} ∈ {0,1}`, label `f"d_{cid}_{k}"`,
with clamped virtual endpoints `d_{c,0} ≡ 1`, `d_{c,S} ≡ 0`. Valid states are
`1^k 0^(S−1−k)` encoding slot value `k ∈ {0..S−1}`. `n·(S−1)` variables.

**Slot indicator** (affine in `d`, so all products below stay quadratic):

```
I_{c,k} = d_{c,k} − d_{c,k+1}        k ∈ {0..S−1}, clamps substituted at k=0 and k=S−1
```

On valid states `I_{c,k} ∈ {0,1}` and `Σ_k I_{c,k} = 1` **automatically** — no
one-slot-per-container penalty family exists in this encoding (that, not qubit count, is its
structural appeal). On invalid states `I` can be −1; D14 covers it.

**Validity penalty** (penalize every `0→1` step, i.e. pattern `d_k=0, d_{k+1}=1`):

```
H_dw = P_dw · Σ_c Σ_{k=1}^{S−2} ( d_{c,k+1} − d_{c,k} · d_{c,k+1} )
```

Zero exactly on valid registers; ≥ `P_dw` per wall violation.

**Objective and constraints** — textual translation of §3 with `x_{c,s} → I_{c,s}`, expanded to
linear/quadratic terms in `d` (clamp substitutions produce constants → BQM offset):

```
H_obj  = Σ_{(a,b): order(dest_a)>order(dest_b)}  Σ_{stackpair(u,v)}  I_{a,u} · I_{b,v}
H_slot = A_dw · Σ_s Σ_{c<c′} I_{c,s} · I_{c′,s}                  with A_dw = (n+1)(f_max+1)  (D11)
H_sup  = P_sup · Σ_{u: tier(u)>0} [ Σ_c I_{c,u} − Σ_c Σ_{c′} I_{c,u} · I_{c′,below(u)} ]
H_haz  = P_haz · Σ_{ {a,b} haz } Σ_{ adj(s,s′) } ( I_{a,s}I_{b,s′} + I_{a,s′}I_{b,s} )
```

`P_dw` per D14, computed after assembling `H_obj + H_slot + H_sup + H_haz`. Offset tuned so
`bqm.energy(encode(A)) == overstow_count(instance, A)` for feasible `A` (same contract as §3).
`encode_assignment` (DW flavour): slot `k` → `d_{c,j} = 1` for `j ≤ k`, else 0.

**Decoder:** for each register read bits `k = 1..S−1`; if the register is `1^k 0^(S−1−k)`
(monotone non-increasing), slot = number of 1s; otherwise slot = `−1` (D13 — reject, never
nearest-valid). Feasibility-rate reporting therefore counts wall-broken samples as infeasible
via `check_feasibility`, uniformly with one-hot.

## 5. Common interface & module layout

Everything in **`src/stowage/encodings.py`** (single module; two encodings + shared helpers).

```python
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import dimod
from stowage.feasibility import Assignment
from stowage.instances import Instance

Sample = Mapping[str, int]                     # dimod sample: variable label -> {0,1}
DecodeFn = Callable[[Sample], Assignment]      # NEVER repairs; sentinel slot -1 on bad register

class PenaltyReport(BaseModel):                # pydantic, frozen — the T2.2 "penalty_report logged" AC
    encoding: str                              # "onehot" | "domainwall"
    n_containers: int
    n_slots: int
    n_variables: int
    f_max: int                                 # n(n-1)/2
    weights: dict[str, float]                  # {"A": ..., "P_sup": ..., "P_haz": ..., ["P_dw": ...]}
    n_quadratic_terms: int
    max_abs_objective_coeff: float             # == 1.0 by construction; asserted
    energy_scale_ratio: float                  # max(weights.values()) / max_abs_objective_coeff

@dataclass(frozen=True)
class EncodingBuild:
    bqm: dimod.BinaryQuadraticModel            # vartype BINARY, string labels per §3/§4
    decode: DecodeFn
    penalty_report: PenaltyReport

class OneHotEncoding:
    name = "onehot"
    def build(self, instance: Instance) -> EncodingBuild: ...
    def encode_assignment(self, instance: Instance, assignment: Assignment) -> dict[str, int]: ...

class DomainWallEncoding:
    name = "domainwall"
    def build(self, instance: Instance) -> EncodingBuild: ...
    def encode_assignment(self, instance: Instance, assignment: Assignment) -> dict[str, int]: ...

ENCODINGS: dict[str, OneHotEncoding | DomainWallEncoding] = {
    "onehot": OneHotEncoding(), "domainwall": DomainWallEncoding(),
}
```

*Deviation note:* CLAUDE.md sketches `build → (BQM, decode_fn)`; the T2.2 AC also requires a
logged `penalty_report`, so the contract is the 3-field `EncodingBuild` dataclass (positional
unpacking `build.bqm, build.decode` preserves the spirit). Architect-approved here.
`build` is a pure function of the instance: no randomness, no I/O; same instance ⇒ identical
BQM (variable order and biases) — tested. CLI wiring of `--encoding onehot|domainwall` is
Phase 3 (T3.1) via `ENCODINGS[name]`; Phase 2 only guarantees the registry exists. No qubit
guard in `encodings.py` — building a 540-var BQM for SA is legal; the ~26-qubit guard belongs
to the QAOA runner (T3.1).

**Files:**

```
src/stowage/encodings.py               # T2.2 creates (shared skeleton + one-hot); T2.3 adds domain-wall
tests/test_encodings_onehot.py         # T2.2
tests/test_encodings_domainwall.py     # T2.3
tests/data/                            # committed verification toys (instance + .optimum.json), LF per .gitattributes
```

**AMENDED (T2.2 adjudication, option B).** Verification toys, generated once via
`stowage.cli generate --toy` and committed with **both** optima cached (see §6.0):
`(n=4, ports=2, seed=1)` — smallest; full 2^N sweep; **relaxed ≠ cached** (cached 1, relaxed 0);
`(n=6, ports=3, seed=2)` — **nonzero cached optimum = 2**, relaxed 0 (**relaxed ≠ cached**);
`(n=6, ports=3, seed=7)` — Phase 1 demo seed; relaxed == cached == 0.

## 6. Ground-state verification protocol — AMENDED (T2.2 adjudication, option B)

The QUBO excludes moments (D9), so its ground state is the **moment-relaxed** optimum, not the
constrained one. The protocol verifies against the relaxed optimum; the constrained (cached)
optimum is kept for the energy-identity test and for solver approximation ratios.

**6.0 — Relaxed optimum: artifact extension (T2.2 deliverable, touches `baselines.py`).**
Extend the existing `OptimumRecord` with one required field:

```python
relaxed_optimal_objective: int   # min overstow over {assignment_valid ∧ supported ∧ hazmat_ok}
```

`brute_force_optimum` computes it in the **same enumeration pass**: for each placement's
`FeasibilityReport`, relaxed-feasible ⇔ `assignment_valid and supported and hazmat_ok`
(moment sub-checks ignored); track that minimum alongside the constrained one. Invariant
(assert in the generator test): `relaxed_optimal_objective <= optimal_objective`. Same file
(`<stem>.optimum.json`), same shared `write_json` path — no sibling file. Field is required
(no default — no silent staleness); existing caches under `instances/` and the §5 toys are
regenerated once.

Per encoding, per verification toy:

1. **Relaxed-vs-cached record (informational, NOT asserted):** the test logs
   `(optimal_objective, relaxed_optimal_objective)` per toy; §5 states the expected pairs.
   A mismatch with §5 is a generator regression, not a protocol failure.
2. **Round-trip:** `decode(encode_assignment(inst, A)) == A` for the cached
   `optimal_assignment` and for 20 seeded random placements.
3. **Energy identity (unchanged):** `bqm.energy(encode_assignment(inst, A_opt)) ==
   optimal_objective` within abs tol 1e-9 — exercises `H_obj` including the nonzero case
   (seed 2 → energy 2).
4. **Valid-state minimum:** enumerate ALL placements `itertools.permutations(range(S), n)`
   (360 for n=4/S=6; 60 480 for n=6/S=9), encode each, take `min(bqm.energy(·))`; assert
   `== relaxed_optimal_objective` (tol 1e-9; both sides integer-valued). Combined with
   step 5 / lemma D11, this pins the global ground state.
5. **Full-space sweep (smallest toy only, `@pytest.mark.slow` for one-hot):** enumerate all
   `2^N` bitstrings — one-hot n=4: N=24 (16.7 M states), domain-wall n=4: N=20 (1 M states) —
   vectorized numpy `E = c + x·h + Σ_{i<j} J_ij x_i x_j` in chunks of ≤ 2^20 rows; assert the
   global minimum equals `relaxed_optimal_objective` AND every bitstring achieving it decodes
   to an assignment that is relaxed-feasible per the §6.0 predicate. Empirical proof of the
   D11/D14 dominance lemmas; steps 1–4 cover the larger toys where 2^N is out of reach.

**Integrity note (checklist §3 — the report must not conflate the two optima):**
QAOA/SA approximation ratios and feasibility rates on moment-binding instances are quoted
against the **constrained** optimum (`optimal_objective`), with feasibility filtered post-hoc
via `check_feasibility`. QUBO **ground-state verification** is against the **relaxed** optimum
(`relaxed_optimal_objective`) — that is what the Hamiltonian actually minimizes. Every figure
and table in Phases 3–5 must label which baseline it uses.

## 7. Ticket refinement

### T2.2 — One-hot encoder + decoder
- Deliver: `encodings.py` with `PenaltyReport`, `EncodingBuild`, `Sample`/`DecodeFn`,
  `OneHotEncoding`, `ENCODINGS` (domain-wall entry added by T2.3 — leave the dict, register
  only onehot; T2.3 appends). Build via `dimod.BinaryQuadraticModel('BINARY')`,
  `add_linear/add_quadratic` accumulation; offset per §3.
- *AMENDED (T2.2 adjudication, option B):* extend `OptimumRecord` and `brute_force_optimum`
  per §6.0 (`relaxed_optimal_objective`, same enumeration pass, shared `write_json`);
  regenerate all committed optimum caches; test asserts `relaxed <= optimal_objective`.
- Also commit the three `tests/data/` toys (instance + optimum JSON) — generated by CLI, byte-stable.
- Edge cases to test: container with no valid... none — plus:
  - popcount-0 and popcount-2 registers decode to slot −1 and `check_feasibility` reports
    `assignment_valid=False` (decoder-never-repairs test);
  - hazmat-free instance ⇒ zero `H_haz` terms; single-tier ship (build a 2×2×1 `Instance` by
    hand) ⇒ zero `H_sup` terms and zero `H_obj` terms (no stacks);
  - determinism: two `build` calls ⇒ identical `bqm` (compare `bqm == bqm2`);
  - `penalty_report` values match D11 formulas exactly for the n=6 toy
    (`f_max=15`, `A=112`, `P_sup=P_haz=16`); report is logged via `logging.info(model_dump_json)`.
- Verification protocol §6 steps 1–5 for onehot on all three toys (step 5 on n=4 only).

### T2.3 — Domain-wall encoder + decoder
- Deliver: `DomainWallEncoding` in the same module; register in `ENCODINGS`.
- Edge cases to test: wall-broken register (`0 1 …`) decodes to −1; all-ones register decodes
  to slot S−1; all-zeros → slot 0 (both VALID states, not rejections); clamp handling at k=0
  and k=S−1 (indicator constants land in offset, verified by energy identity §6.3).
- `P_dw` formula test: recompute `1 + Σ|bias|` of the non-validity terms independently in the
  test and assert equality with `penalty_report.weights["P_dw"]`.
- **Qubit-count reduction AC:** test asserts `len(bqm.variables) == n·(S−1)` and the D12 table
  rows for n ∈ {4, 8, 12, 16, 20} via `auto_ship_dims` (no BQM build needed above n=6 — pure
  arithmetic on dims; build+count only for the toys).
- Verification protocol §6 steps 1–5 (step 5: n=4, N=20, fast — not slow-marked).

## 8. Risks

- **R5 — Energy-scale separation (P_dw, A ≫ objective) degrades QAOA trainability.** Not a
  Phase 2 failure: weights are *correctness-sufficient* here; Phase 4's penalty-sensitivity
  study (T4.2/T4.3) sweeps them downward with §6-step-5 style spot checks. `energy_scale_ratio`
  in `penalty_report` is the tracked quantity.
- **R6 — Only the n=4 toy fits the 26-qubit statevector guard (either encoding).** T3.1's
  "p=1 on 8-container toy" AC is unsatisfiable as written (96/88 qubits) — flagged now:
  Phase 3 spec must restate it against the n=4 toy or a sampling-based simulator budget.
  *AMENDED (T2.2 adjudication):* the n=4 toy is moment-binding (relaxed 0 vs cached 1), so
  Phase 3's QAOA success criterion on it must target the relaxed optimum per the §6 integrity
  note, with constrained-feasibility rate reported alongside.
- **R7 — AMENDED (T2.2 adjudication, option B) — resolved.** Implementer scan (seeds 1–30,
  four (n, ports) combos) established that NO generator seed has both a nonzero cached optimum
  and relaxed == cached: nonzero optima arise only when moment bounds bind. There is no
  replacement seed to find. Resolution: §6.4/§6.5 verify against the cached
  `relaxed_optimal_objective`; the relaxed-vs-cached comparison is informational (§6.1).
  Residual risk: solver-vs-QUBO baseline confusion in Phase 4/5 figures — mitigated by the
  §6 integrity note (mandatory labeling of which optimum each figure uses).
- **R8 — Full 2^24 sweep too slow in CI.** It is `@pytest.mark.slow` (excluded from default CI
  run, executed at phase gate); the DW 2^20 sweep stays in CI as the always-on lemma check.

No spikes required.

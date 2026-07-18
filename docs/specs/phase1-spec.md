# Phase 1 Spec — Ship Model & Instance Generator

Tickets: T1.1, T1.2, T1.3. Author: architect. Status: ready for implementation.
Interfaces below are contracts — implementer may not change signatures/schemas without returning to architect.

## 1. Objective

Deliver a pydantic-v2 data model for ships/containers/instances, an encoding-independent
objective + feasibility checker, and a seeded instance generator whose `--toy` mode emits
instances small enough to brute-force (<20 s) with the optimum cached alongside. This is the
ground truth layer: every later solver (QAOA, SA, heuristic) is validated against these toys,
and every decoded sample is judged by `check_feasibility`. DoD (TICKETS.md): configurable
instances with known-optimum toys for later solver validation.

## 2. Design decisions

**D1 — Slot indexing: single canonical linear index.**
Slot `s ∈ {0..n_slots-1}` with `s = bay·(n_rows·n_tiers) + row·n_tiers + tier`
(tier 0 = bottom, row 0 = port side, bay 0 = forward). Inverse: `tier = s % n_tiers`,
`row = (s // n_tiers) % n_rows`, `bay = s // (n_rows·n_tiers)`.
*Alternatives:* (bay,row,tier) tuples everywhere — rejected: QUBO variables in Phase 2 need a
flat index anyway; one convention, defined once. All public APIs use the int index; tuples only
via helper functions.

**D2 — Moment proxies: dimensionless lever arms from grid indices.**
Coordinate origin: keel (tier 0) and centerline. Lever arms:
- vertical: `z(s) = tier(s)` (tier 0 contributes 0 — bottom stow is free)
- transverse: `y(s) = row(s) − (n_rows − 1)/2` (symmetric about centerline; negative = port)

For assignment A (container c in slot A(c)):

```
M_v(A) = Σ_c  w_c · z(A(c))            constraint: M_v ≤ V_max
M_t(A) = Σ_c  w_c · y(A(c))            constraint: |M_t| ≤ T_max
```

*Alternatives:* physical meters + real GM computation — rejected: this is a thesis-honest
*proxy*; grid-index levers keep the QUBO coefficients small and integer-friendly.
Bounds live on the Ship (`max_vertical_moment: float`, `max_transverse_moment: float`,
the latter applied as |M_t| ≤ bound).

**D3 — Overstowage: pairwise, same stack, discharge-order inversion.**
Port rotation is an ordered list; `order(p)` = index in rotation (earlier = discharged first).
Container a **overstows** b iff:
`bay(a)=bay(b) ∧ row(a)=row(b) ∧ tier(a)>tier(b) ∧ order(dest_a) > order(dest_b)`
(a sits above b but leaves the ship later → b's discharge forces a re-handle).
Objective = total count of such ordered pairs. Ties (same destination) never count.

**D4 — Objective vs hard constraints.**
Minimize: `f(A) = overstow_count(A)` — integer, no soft terms in Phase 1.
Hard (feasibility, not objective): (i) assignment validity — every container exactly one slot,
no slot used twice, all slot indices in range; (ii) support — a container at tier t>0 requires
an occupied slot at tier t−1 in the same bay/row (no floating containers); (iii) moment bounds
per D2; (iv) hazmat separation per D5. *Alternative:* fold moments into the objective —
rejected here; Phase 2 (T2.1) decides how constraints become penalties. Phase 1 keeps
objective/constraints cleanly separated so both encodings map from the same ground truth.

**D5 — Hazmat separation.**
`Container.hazmat_class: int | None` (None = non-hazmat; int reserved for IMO-class realism
later). Rule: no two hazmat containers (both class ≠ None, any classes) may occupy
grid-adjacent slots, adjacency = Manhattan distance 1:
`|Δbay| + |Δrow| + |Δtier| = 1`. Diagonals allowed.
`# ponytail: class-agnostic rule; per-class segregation table if thesis needs it.`

**D6 — Feasibility guarantee by construction.**
The generator first builds a *witness assignment* (bottom-up placement → support holds; hazmat
placed only in slots non-adjacent to already-placed hazmat), then sets moment bounds from the
witness: `V_max = 1.1·M_v(witness)`, `T_max = max(1.1·|M_t(witness)|, 0.5·w̄)` (floor avoids
a zero bound on symmetric witnesses; `w̄` = mean weight). Witness is discarded (not written to
the instance file) but its existence guarantees ≥1 feasible assignment. If hazmat placement
runs out of legal slots after 100 candidate shuffles → raise `InfeasibleGenerationError`
(fail loudly, no fallback). *Alternative:* rejection sampling over random instances —
rejected: no termination guarantee, muddier determinism contract.

**D7 — Variable-count outlook (for Phase 2 honesty).**
One-hot Phase 2 needs `n_containers × n_slots` binaries. Ship sizing rule (D8) keeps
`n_slots = smallest grid ≥ ceil(1.25·n_containers)`, so: 6 containers/8 slots → 48 vars;
12/16 → 192; 20/25 → 500. All far above the 26-qubit statevector guard — Phase 1 must
therefore produce toys at 4–6 containers where exact/QAOA validation is possible, and 10–20
container instances are for SA/heuristic + scaling analysis only. Stated here so nobody
expects QAOA on 20 containers.

**D8 — Ship auto-sizing in generator.**
Given `n_containers`: `n_tiers = 3` (toy: 2–3), choose `n_rows ∈ {2,3,4}` and `n_bays` as the
smallest product with `n_bays·n_rows·n_tiers ≥ ceil(1.25·n_containers)`, preferring more
bays over more rows. Deterministic function of `n_containers` alone — unit-testable table.

## 3. Module & file layout

```
src/stowage/
  ship.py         # Ship, Container, slot addressing, moment computation
  instances.py    # Instance, generate_instance, JSON I/O
  feasibility.py  # NEW — Assignment type, FeasibilityReport, check_feasibility, overstow_count
  baselines.py    # brute_force_optimum (Phase 1 slice only; SA/heuristic stay Phase 3)
  cli.py          # `generate` subcommand
tests/
  test_ship.py  test_feasibility.py  test_instances.py
instances/        # generated artifacts (gitignore large ones; keep committed toys in tests/data/)
```

### ship.py — public API

```python
class Ship(BaseModel):
    model_config = ConfigDict(frozen=True)
    n_bays: int          # ≥1
    n_rows: int          # ≥1
    n_tiers: int         # ≥1
    max_vertical_moment: float    # V_max ≥ 0
    max_transverse_moment: float  # T_max ≥ 0, applied as |M_t| ≤ T_max

    @property
    def n_slots(self) -> int: ...

class Container(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str                       # unique within instance, pattern "C<int>"
    weight: float                 # > 0, tonnes (nominal)
    destination: str              # must appear in Instance.port_rotation
    hazmat_class: int | None = None

def slot_to_brt(ship: Ship, slot: int) -> tuple[int, int, int]: ...   # (bay,row,tier); raises IndexError out of range
def brt_to_slot(ship: Ship, bay: int, row: int, tier: int) -> int: ...
def vertical_lever(ship: Ship, slot: int) -> float: ...              # tier(slot)
def transverse_lever(ship: Ship, slot: int) -> float: ...            # row(slot) - (n_rows-1)/2
def moments(ship: Ship, weights_by_slot: dict[int, float]) -> tuple[float, float]:  # (M_v, M_t)
```

### instances.py — public API

```python
class Instance(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    ship: Ship
    containers: tuple[Container, ...]     # ids unique (validator)
    port_rotation: tuple[str, ...]        # ordered, unique; every dest present here (validator)
    seed: int
    generator_params: dict[str, float | int | str]   # knobs echoed for provenance
    schema_version: int = 1

def generate_instance(
    n_containers: int, n_ports: int, seed: int, *,
    weight_range: tuple[float, float] = (5.0, 30.0),
    hazmat_fraction: float = 0.15,
    toy: bool = False,
) -> Instance: ...

def save_instance(instance: Instance, path: Path) -> None: ...   # json.dumps(model_dump(), indent=2, sort_keys=True)
def load_instance(path: Path) -> Instance: ...                   # Instance.model_validate_json
```

JSON round-trip contract: `load_instance(save_instance(x)) == x`, and saving twice yields
byte-identical files (sorted keys, indent=2, `\n` newlines). Ports named `"P1".."Pn"` in
rotation order; container ids `"C1".."Cn"`.

### feasibility.py — public API

```python
Assignment = dict[str, int]   # container_id -> slot index; must be total over instance.containers

class FeasibilityReport(BaseModel):
    feasible: bool                      # AND of the four checks below
    assignment_valid: bool              # total, unique slots, in range, known ids
    supported: bool                     # no floating containers
    vertical_moment: float
    vertical_ok: bool                   # M_v <= V_max
    transverse_moment: float
    transverse_ok: bool                 # |M_t| <= T_max
    hazmat_violations: tuple[tuple[str, str], ...]  # sorted id pairs, id_a < id_b
    hazmat_ok: bool
    overstow_count: int                 # OBJECTIVE value — reported always, not a feasibility gate
    errors: tuple[str, ...]             # human-readable, one per failed sub-check

def check_feasibility(instance: Instance, assignment: Assignment) -> FeasibilityReport: ...
def overstow_count(instance: Instance, assignment: Assignment) -> int: ...
```

Rules: never raise on a bad assignment — report it (`assignment_valid=False`, all dependent
checks short-circuit to False, moments reported as computed over valid entries or 0.0 if
invalid — pick 0.0 and note in `errors`). Pure functions, no I/O, no randomness.
This is the single feasibility authority; Phase 2/3 decoders call it and nothing else.

### baselines.py — Phase 1 slice

```python
class OptimumRecord(BaseModel):
    instance_name: str
    method: str = "brute_force"
    optimal_objective: int
    optimal_assignment: Assignment      # one witness; ties broken by lexicographic assignment order
    n_feasible: int
    n_evaluated: int
    elapsed_seconds: float

def brute_force_optimum(instance: Instance) -> OptimumRecord:  # raises ValueError if search space > 5e6 placements
```

Enumeration: `itertools.permutations(slots, n_containers)` mapped to containers in id order;
evaluate via `check_feasibility`; minimize `overstow_count` over feasible assignments.
Raises `RuntimeError` if zero feasible found (generator guarantee violated → loud failure).
Cache file: `<instance_stem>.optimum.json`, same serialization contract as instances.

### cli.py — `generate` subcommand (argparse, stdlib)

```
python -m stowage.cli generate --containers 12 --ports 3 --seed 7
    [--hazmat-fraction 0.15] [--weight-min 5 --weight-max 30]
    [--toy] [--out instances/]
```

Writes `<out>/<name>.json` where `name = f"stow_c{n}_p{k}_s{seed}" (+ "_toy")`. With `--toy`:
also runs `brute_force_optimum` and writes `<name>.optimum.json` next to it. Prints the two
paths and the optimum objective; nothing else.

## 4. Ticket refinement

### T1.1 — Ship & container schema (ship.py + Instance/save/load in instances.py)
- Validators: positive dims, weight > 0, unique container ids, all destinations ∈ rotation,
  rotation entries unique. Frozen models throughout.
- Edge cases to test: slot round-trip `brt_to_slot(slot_to_brt(s)) == s` for every slot of a
  2×3×4 ship; out-of-range slot raises; 1-row ship → all transverse levers 0; JSON round-trip
  equality + byte-stability; rejection of duplicate ids and unknown destination.
- **Hand-calculated moment test (must appear verbatim in test_ship.py):**
  Ship 1×2×3 (V_max/T_max irrelevant here). Weights by (row,tier):
  row0: t0=10, t1=8, t2=6; row1: t0=12, t1=9, t2=5.
  Levers: z = tier; y = ∓0.5.
  `M_v = 8·1 + 6·2 + 9·1 + 5·2 = 39.0`
  `M_t = −0.5·(10+8+6) + 0.5·(12+9+5) = −12 + 13 = +1.0`
  Assert exact equality (all values representable in binary floats).

### T1.2 — Objective & feasibility (feasibility.py)
- Implementation notes: build slot→container map once; support check = per (bay,row) stack,
  occupied tiers must be a prefix {0..k}; hazmat via pairwise Manhattan distance over hazmat
  subset only (n ≤ 20 → O(n²) fine).
- **6-container overstow hand example (must appear verbatim in test_feasibility.py):**
  Ship 1×2×3; rotation ("P1","P2","P3").
  Containers (id, dest): C1:P3, C2:P1, C3:P2, C4:P2, C5:P1, C6:P3; weights as in T1.1 example.
  Assignment (slot = row·3 + tier): C1→0, C2→1, C3→2, C4→3, C5→4, C6→5.
  Overstows: C3-over-C2 (P2 after P1), C6-over-C4 (P3 after P2), C6-over-C5 (P3 after P1).
  C2/C3 over C1 do not count (P1,P2 before P3); C5 over C4 does not count.
  **Expected overstow_count = 3.** Also assert report: with V_max=40, T_max=2 → feasible=True,
  M_v=39, M_t=1; with V_max=38 → vertical_ok=False, feasible=False, overstow_count still 3.
- Adversarial tests (one per constraint, each flips exactly one sub-check):
  duplicate slot in assignment; missing container; unknown container id; slot index = n_slots;
  floating container (tier 1 occupied, tier 0 empty); two hazmat side-by-side (Δrow=1) → violation,
  and diagonal (Δrow=1,Δtier=1) → no violation; M_t exactly = T_max → ok (bounds inclusive);
  same-destination stack → 0 overstows.

### T1.3 — Instance generator (instances.py, baselines.py slice, cli.py)
- Determinism: single `numpy.random.default_rng(seed)`; same knobs+seed ⇒ byte-identical JSON
  (test: generate twice, compare bytes). Record all knobs in `generator_params`.
- Knob semantics: destinations sampled uniform over `P1..Pk` but each port guaranteed ≥1
  container when `n_containers ≥ n_ports` (assign first k containers round-robin, shuffle);
  hazmat count = `round(hazmat_fraction·n_containers)`; weights uniform over `weight_range`,
  rounded to 0.1 t.
- `--toy` mode: force `n_containers ∈ [4,6]` (raise on larger), ship 1×2×3 or 1×3×3
  (8-slot cap via D8 with n_tiers ≤ 3) → ≤ P(9,6) ≈ 60 480 placements, brute force well
  under 20 s with pure-Python checker.
- Tests: seed determinism; toy end-to-end — generate seed=7, brute-force, assert
  `OptimumRecord.n_feasible ≥ 1` and optimum assignment passes `check_feasibility`;
  witness guarantee — for 20 seeds × sizes {4,6,12}, brute force (toys) or the recorded
  witness path (non-toys: expose `_build_witness` for the test only) yields a feasible
  assignment; `InfeasibleGenerationError` triggered by pathological knobs
  (hazmat_fraction=1.0 on a dense ship).
- CLI test: run `generate --containers 5 --ports 2 --seed 3 --toy --out tmp`, assert both
  files exist and parse.

## 5. Risks

- **R1 — Brute force blows the 20 s budget** if the checker is slow in pure Python.
  Fallback: prune by symmetry (fix first container to slot 0 only when ship has a symmetric
  row axis) or drop toy cap to 5 containers. The 5e6-placement guard makes this loud, not slow.
- **R2 — Moment-bound tightness (1.1× witness) may make instances trivially feasible or
  near-degenerate.** If Phase 2 encoding tests show the moment penalty never binds, revisit
  D6 with a tightness knob (`bound_slack: float = 1.1` already echoed in generator_params, so
  adding the knob later is backward-compatible).
- **R3 — One-hot variable counts (D7) exceed simulator limits at headline sizes.** Not a
  Phase 1 failure, but Phase 1 must ship 4–6-container toys or Phase 2 verification is
  impossible. Toys are therefore a hard deliverable, not a nice-to-have.
- **R4 — Class-agnostic hazmat rule (D5) may be challenged in review as unrealistic.**
  Mitigation: `hazmat_class` already carries the int; upgrading to a per-class segregation
  table changes only `feasibility.py` internals, no schema break.

No spikes required — all decisions are specifiable without experiment.

"""Objective and feasibility checker (Phase 1, T1.2).

Encoding-independent ground-truth layer. Every decoded sample from any Phase 2/3
solver is judged here and nowhere else.

Feasibility is the AND of four hard checks (D4):
  (i)   assignment validity — every container exactly one slot, no slot reused,
        indices in range, only known container ids;
  (ii)  support — no floating containers: occupied tiers in each (bay,row) stack
        must form a prefix {0..k} (D4);
  (iii) moment bounds — M_v <= V_max and |M_t| <= T_max, inclusive (D2);
  (iv)  hazmat separation — no two hazmat containers at Manhattan distance 1 (D5).

The objective (D3) is ``overstow_count`` — same-stack pairwise discharge-order
inversions. It is reported always and is NOT a feasibility gate.

``check_feasibility`` never raises on bad input: it reports the problem via
``assignment_valid=False`` and short-circuits dependent checks to False.
"""

from __future__ import annotations

from itertools import combinations

from pydantic import BaseModel

from stowage.instances import Instance
from stowage.ship import moments, slot_to_brt

Assignment = dict[str, int]  # container_id -> slot index; total over instance.containers


class FeasibilityReport(BaseModel):
    """Result of judging one assignment against one instance.

    ``feasible`` is the AND of the four hard checks. ``overstow_count`` is the
    objective value and is always populated, never a feasibility gate.
    """

    feasible: bool
    assignment_valid: bool
    supported: bool
    vertical_moment: float
    vertical_ok: bool
    transverse_moment: float
    transverse_ok: bool
    hazmat_violations: tuple[tuple[str, str], ...]
    hazmat_ok: bool
    overstow_count: int
    errors: tuple[str, ...]


def _valid_slot_map(instance: Instance, assignment: Assignment) -> dict[str, int]:
    """Slots for containers whose entry is an in-range int. Defensive, never raises.

    Booleans are ints in Python but are not valid slot indices here, so reject them.
    """
    n_slots = instance.ship.n_slots
    known = {c.id for c in instance.containers}
    out: dict[str, int] = {}
    for cid, slot in assignment.items():
        if cid not in known:
            continue
        if isinstance(slot, bool) or not isinstance(slot, int):
            continue
        if 0 <= slot < n_slots:
            out[cid] = slot
    return out


def _validity_errors(instance: Instance, assignment: Assignment) -> list[str]:
    """Human-readable errors for assignment validity. Empty list == valid."""
    errors: list[str] = []
    n_slots = instance.ship.n_slots
    known = {c.id for c in instance.containers}

    unknown = sorted(set(assignment) - known)
    if unknown:
        errors.append(f"unknown container ids: {unknown}")

    missing = sorted(known - set(assignment))
    if missing:
        errors.append(f"missing containers: {missing}")

    bad_type = sorted(
        cid
        for cid, slot in assignment.items()
        if isinstance(slot, bool) or not isinstance(slot, int)
    )
    if bad_type:
        errors.append(f"non-integer slot values for: {bad_type}")

    out_of_range = sorted(
        cid
        for cid, slot in assignment.items()
        if isinstance(slot, int) and not isinstance(slot, bool) and not 0 <= slot < n_slots
    )
    if out_of_range:
        errors.append(f"slot index out of range [0, {n_slots}) for: {out_of_range}")

    slots = [
        slot
        for slot in assignment.values()
        if isinstance(slot, int) and not isinstance(slot, bool) and 0 <= slot < n_slots
    ]
    if len(slots) != len(set(slots)):
        dupes = sorted({s for s in slots if slots.count(s) > 1})
        errors.append(f"slots assigned more than once: {dupes}")

    return errors


def _supported(instance: Instance, slot_map: dict[str, int]) -> bool:
    """True iff every (bay,row) stack's occupied tiers form a prefix {0..k}."""
    ship = instance.ship
    tiers_by_stack: dict[tuple[int, int], set[int]] = {}
    for slot in slot_map.values():
        bay, row, tier = slot_to_brt(ship, slot)
        tiers_by_stack.setdefault((bay, row), set()).add(tier)
    return all(tiers == set(range(max(tiers) + 1)) for tiers in tiers_by_stack.values())


def _hazmat_violations(
    instance: Instance, slot_map: dict[str, int]
) -> tuple[tuple[str, str], ...]:
    """Sorted (id_a, id_b) pairs of hazmat containers at Manhattan distance 1."""
    ship = instance.ship
    hazmat = [c for c in instance.containers if c.hazmat_class is not None and c.id in slot_map]
    pairs: list[tuple[str, str]] = []
    for a, b in combinations(hazmat, 2):
        ba, ra, ta = slot_to_brt(ship, slot_map[a.id])
        bb, rb, tb = slot_to_brt(ship, slot_map[b.id])
        if abs(ba - bb) + abs(ra - rb) + abs(ta - tb) == 1:
            lo, hi = sorted((a.id, b.id))
            pairs.append((lo, hi))
    return tuple(sorted(pairs))


def overstow_count(instance: Instance, assignment: Assignment) -> int:
    """Number of same-stack discharge-order inversions (D3). Never raises.

    Container a overstows b iff same bay & row, tier(a) > tier(b), and a is
    discharged later than b (order(dest_a) > order(dest_b)). Ties never count.
    Computed over the subset of containers with valid in-range slot entries.
    """
    ship = instance.ship
    order = {p: i for i, p in enumerate(instance.port_rotation)}
    slot_map = _valid_slot_map(instance, assignment)
    dest = {c.id: c.destination for c in instance.containers}

    placed = []
    for cid, slot in slot_map.items():
        bay, row, tier = slot_to_brt(ship, slot)
        placed.append((bay, row, tier, order.get(dest[cid], -1)))

    count = 0
    for (ba, ra, ta, oa), (bb, rb, tb, ob) in combinations(placed, 2):
        if ba != bb or ra != rb or ta == tb:
            continue
        # upper = higher tier; overstow iff the upper container is discharged later
        upper_o, lower_o = (oa, ob) if ta > tb else (ob, oa)
        if upper_o > lower_o:
            count += 1
    return count


def check_feasibility(instance: Instance, assignment: Assignment) -> FeasibilityReport:
    """Judge one assignment against one instance. Pure, never raises.

    On an invalid assignment, dependent checks short-circuit to False and moments
    are reported as 0.0 (noted in ``errors``). ``overstow_count`` is computed over
    whatever valid entries exist and is always populated.
    """
    ship = instance.ship
    validity_errors = _validity_errors(instance, assignment)
    assignment_valid = not validity_errors
    errors: list[str] = list(validity_errors)

    overstow = overstow_count(instance, assignment)

    if not assignment_valid:
        errors.append("moments not computed: assignment invalid (reported as 0.0)")
        return FeasibilityReport(
            feasible=False,
            assignment_valid=False,
            supported=False,
            vertical_moment=0.0,
            vertical_ok=False,
            transverse_moment=0.0,
            transverse_ok=False,
            hazmat_violations=(),
            hazmat_ok=False,
            overstow_count=overstow,
            errors=tuple(errors),
        )

    slot_map = _valid_slot_map(instance, assignment)
    weight_by_id = {c.id: c.weight for c in instance.containers}
    weights_by_slot = {slot_map[cid]: weight_by_id[cid] for cid in slot_map}

    supported = _supported(instance, slot_map)
    if not supported:
        errors.append("unsupported (floating) container(s): occupied tiers not a prefix {0..k}")

    m_v, m_t = moments(ship, weights_by_slot)
    vertical_ok = m_v <= ship.max_vertical_moment
    if not vertical_ok:
        errors.append(f"vertical moment {m_v} exceeds V_max {ship.max_vertical_moment}")
    transverse_ok = abs(m_t) <= ship.max_transverse_moment
    if not transverse_ok:
        errors.append(f"|transverse moment| {abs(m_t)} exceeds T_max {ship.max_transverse_moment}")

    violations = _hazmat_violations(instance, slot_map)
    hazmat_ok = not violations
    if not hazmat_ok:
        errors.append(f"hazmat containers at Manhattan distance 1: {list(violations)}")

    feasible = supported and vertical_ok and transverse_ok and hazmat_ok

    return FeasibilityReport(
        feasible=feasible,
        assignment_valid=True,
        supported=supported,
        vertical_moment=m_v,
        vertical_ok=vertical_ok,
        transverse_moment=m_t,
        transverse_ok=transverse_ok,
        hazmat_violations=violations,
        hazmat_ok=hazmat_ok,
        overstow_count=overstow,
        errors=tuple(errors),
    )

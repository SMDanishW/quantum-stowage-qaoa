"""Tests for the objective + feasibility checker (T1.2).

Includes the spec's verbatim 6-container overstow hand example (count = 3) and
adversarial cases isolating each hard constraint. ``check_feasibility`` must
never raise, even on garbage input.
"""

from __future__ import annotations

from stowage.feasibility import check_feasibility, overstow_count
from stowage.instances import Instance
from stowage.ship import Container, Ship


def _ship(v_max: float = 1e6, t_max: float = 1e6) -> Ship:
    """1x2x3 ship (6 slots), generous bounds unless overridden."""
    return Ship(
        n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=v_max, max_transverse_moment=t_max
    )


def _instance(containers: tuple[Container, ...], ship: Ship | None = None) -> Instance:
    return Instance(
        name="t",
        ship=ship if ship is not None else _ship(),
        containers=containers,
        port_rotation=("P1", "P2", "P3"),
        seed=0,
    )


# --- Spec's verbatim 6-container overstow hand example (D3) -----------------
# Ship 1x2x3; rotation ("P1","P2","P3"). slot = row*3 + tier.
# Containers (id, dest, weight): C1:P3/10 C2:P1/8 C3:P2/6 C4:P2/12 C5:P1/9 C6:P3/5.
# Assignment: C1->0 C2->1 C3->2 C4->3 C5->4 C6->5.
# Overstows: C3-over-C2 (P2 after P1), C6-over-C4 (P3 after P2), C6-over-C5 (P3 after P1).
# C2/C3 over C1 do NOT count (P1,P2 before P3); C5 over C4 does NOT count.
# Expected overstow_count = 3. M_v = 39, M_t = 1.

_HAND = (
    Container(id="C1", weight=10.0, destination="P3"),
    Container(id="C2", weight=8.0, destination="P1"),
    Container(id="C3", weight=6.0, destination="P2"),
    Container(id="C4", weight=12.0, destination="P2"),
    Container(id="C5", weight=9.0, destination="P1"),
    Container(id="C6", weight=5.0, destination="P3"),
)
_HAND_ASSIGN = {"C1": 0, "C2": 1, "C3": 2, "C4": 3, "C5": 4, "C6": 5}


def test_hand_overstow_count_is_three() -> None:
    inst = _instance(_HAND, _ship(v_max=40, t_max=2))
    assert overstow_count(inst, _HAND_ASSIGN) == 3


def test_hand_report_feasible_with_moments() -> None:
    inst = _instance(_HAND, _ship(v_max=40, t_max=2))
    r = check_feasibility(inst, _HAND_ASSIGN)
    assert r.feasible is True
    assert r.assignment_valid is True
    assert r.supported is True
    assert r.vertical_moment == 39.0
    assert r.transverse_moment == 1.0
    assert r.overstow_count == 3
    assert r.errors == ()


def test_hand_vertical_bound_binds() -> None:
    inst = _instance(_HAND, _ship(v_max=38, t_max=2))
    r = check_feasibility(inst, _HAND_ASSIGN)
    assert r.vertical_ok is False
    assert r.feasible is False
    assert r.overstow_count == 3  # objective still reported


# --- Moment bounds are inclusive -------------------------------------------
def test_vertical_bound_inclusive() -> None:
    inst = _instance(_HAND, _ship(v_max=39, t_max=2))  # M_v == V_max exactly
    r = check_feasibility(inst, _HAND_ASSIGN)
    assert r.vertical_ok is True
    assert r.feasible is True


def test_transverse_bound_inclusive() -> None:
    inst = _instance(_HAND, _ship(v_max=40, t_max=1))  # |M_t| == T_max exactly
    r = check_feasibility(inst, _HAND_ASSIGN)
    assert r.transverse_ok is True
    assert r.feasible is True


# --- Assignment validity, each error type isolated -------------------------
_TWO = (
    Container(id="C1", weight=5.0, destination="P1"),
    Container(id="C2", weight=5.0, destination="P1"),
)


def test_duplicate_slot() -> None:
    r = check_feasibility(_instance(_TWO), {"C1": 0, "C2": 0})
    assert r.assignment_valid is False
    assert r.feasible is False
    assert any("more than once" in e for e in r.errors)


def test_missing_container() -> None:
    r = check_feasibility(_instance(_TWO), {"C1": 0})
    assert r.assignment_valid is False
    assert any("missing" in e for e in r.errors)


def test_unknown_container_id() -> None:
    r = check_feasibility(_instance(_TWO), {"C1": 0, "C2": 1, "C3": 2})
    assert r.assignment_valid is False
    assert any("unknown" in e for e in r.errors)


def test_slot_out_of_range() -> None:
    r = check_feasibility(_instance(_TWO), {"C1": 0, "C2": 6})  # n_slots == 6
    assert r.assignment_valid is False
    assert any("out of range" in e for e in r.errors)


def test_invalid_assignment_reports_zero_moments() -> None:
    r = check_feasibility(_instance(_TWO), {"C1": 0})
    assert r.vertical_moment == 0.0
    assert r.transverse_moment == 0.0
    assert any("moments not computed" in e for e in r.errors)


# --- Support: floating container --------------------------------------------
def test_floating_container_unsupported() -> None:
    # C1 at tier1 row0 (slot 1), C2 at tier1 row1 (slot 4): both stacks miss tier0.
    r = check_feasibility(_instance(_TWO), {"C1": 1, "C2": 4})
    assert r.assignment_valid is True
    assert r.supported is False
    assert r.feasible is False


def test_full_stack_supported() -> None:
    r = check_feasibility(_instance(_TWO), {"C1": 0, "C2": 1})  # tiers {0,1} in row0
    assert r.supported is True


# --- Hazmat separation (Manhattan distance 1) -------------------------------
def test_hazmat_side_by_side_violation() -> None:
    haz = (
        Container(id="C1", weight=5.0, destination="P1", hazmat_class=1),
        Container(id="C2", weight=5.0, destination="P1", hazmat_class=2),
    )
    # slot 0 = (0,0,0), slot 3 = (0,1,0): Manhattan distance 1 (Delta row = 1).
    r = check_feasibility(_instance(haz), {"C1": 0, "C2": 3})
    assert r.hazmat_ok is False
    assert r.hazmat_violations == (("C1", "C2"),)
    assert r.feasible is False


def test_hazmat_diagonal_allowed() -> None:
    haz = (
        Container(id="C1", weight=5.0, destination="P1", hazmat_class=1),
        Container(id="C2", weight=5.0, destination="P1", hazmat_class=2),
        Container(id="C3", weight=5.0, destination="P1"),  # filler supports C2
    )
    # slot 0 = (0,0,0), slot 4 = (0,1,1): Delta row=1, Delta tier=1 -> Manhattan 2, allowed.
    # slot 3 = (0,1,0) supports the row-1 stack.
    r = check_feasibility(_instance(haz), {"C1": 0, "C2": 4, "C3": 3})
    assert r.hazmat_ok is True
    assert r.hazmat_violations == ()
    assert r.supported is True
    assert r.feasible is True


# --- Objective edge: same-destination stack never counts --------------------
def test_same_destination_stack_zero_overstows() -> None:
    inst = _instance(_TWO)  # both C1, C2 -> P1
    assert overstow_count(inst, {"C1": 0, "C2": 1}) == 0


# --- Never raises on garbage -------------------------------------------------
def test_never_raises_on_garbage() -> None:
    inst = _instance(_TWO)
    garbage = [
        {},
        {"C1": "x", "C2": None},
        {"C1": True, "C2": 1},
        {"C9": [1, 2], "C1": -5, "C2": 999},
        {"C1": 1.5, "C2": 2},
    ]
    for a in garbage:
        r = check_feasibility(inst, a)  # type: ignore[arg-type]
        assert r.feasible is False
        assert r.assignment_valid is False

"""T1.1 tests for ship geometry and moment proxies."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from stowage.ship import (
    Container,
    Ship,
    brt_to_slot,
    moments,
    slot_to_brt,
    transverse_lever,
    vertical_lever,
)


def test_n_slots() -> None:
    ship = Ship(n_bays=2, n_rows=3, n_tiers=4, max_vertical_moment=0, max_transverse_moment=0)
    assert ship.n_slots == 24


def test_slot_bijection_2x3x4() -> None:
    ship = Ship(n_bays=2, n_rows=3, n_tiers=4, max_vertical_moment=0, max_transverse_moment=0)
    for s in range(ship.n_slots):
        bay, row, tier = slot_to_brt(ship, s)
        assert brt_to_slot(ship, bay, row, tier) == s
    seen = {slot_to_brt(ship, s) for s in range(ship.n_slots)}
    assert len(seen) == ship.n_slots


def test_slot_boundaries() -> None:
    ship = Ship(n_bays=2, n_rows=3, n_tiers=4, max_vertical_moment=0, max_transverse_moment=0)
    assert slot_to_brt(ship, 0) == (0, 0, 0)
    assert slot_to_brt(ship, ship.n_slots - 1) == (1, 2, 3)


def test_slot_out_of_range_raises() -> None:
    ship = Ship(n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=0, max_transverse_moment=0)
    with pytest.raises(IndexError):
        slot_to_brt(ship, ship.n_slots)
    with pytest.raises(IndexError):
        slot_to_brt(ship, -1)
    with pytest.raises(IndexError):
        brt_to_slot(ship, 0, 2, 0)  # row out of range


def test_one_row_ship_transverse_levers_zero() -> None:
    ship = Ship(n_bays=2, n_rows=1, n_tiers=3, max_vertical_moment=0, max_transverse_moment=0)
    assert all(transverse_lever(ship, s) == 0.0 for s in range(ship.n_slots))


def test_vertical_lever_equals_tier() -> None:
    ship = Ship(n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=0, max_transverse_moment=0)
    for s in range(ship.n_slots):
        assert vertical_lever(ship, s) == slot_to_brt(ship, s)[2]


def test_moments_hand_example() -> None:
    # Spec T1.1 hand-calculated example. Ship 1x2x3, slot = row*3 + tier.
    # row0: t0=10, t1=8, t2=6 ; row1: t0=12, t1=9, t2=5
    # M_v = 8*1 + 6*2 + 9*1 + 5*2 = 39.0
    # M_t = -0.5*(10+8+6) + 0.5*(12+9+5) = -12 + 13 = +1.0
    ship = Ship(n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=0, max_transverse_moment=0)
    weights_by_slot = {0: 10.0, 1: 8.0, 2: 6.0, 3: 12.0, 4: 9.0, 5: 5.0}
    m_v, m_t = moments(ship, weights_by_slot)
    assert m_v == 39.0
    assert m_t == 1.0


def test_ship_rejects_bad_dims() -> None:
    with pytest.raises(ValidationError):
        Ship(n_bays=0, n_rows=2, n_tiers=3, max_vertical_moment=0, max_transverse_moment=0)
    with pytest.raises(ValidationError):
        Ship(n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=-1, max_transverse_moment=0)


def test_container_validation() -> None:
    Container(id="C1", weight=10.0, destination="P1")
    with pytest.raises(ValidationError):
        Container(id="C1", weight=-1.0, destination="P1")  # negative weight
    with pytest.raises(ValidationError):
        Container(id="X1", weight=10.0, destination="P1")  # bad id pattern


def test_models_frozen() -> None:
    ship = Ship(n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=0, max_transverse_moment=0)
    with pytest.raises(ValidationError):
        ship.n_bays = 5  # type: ignore[misc]

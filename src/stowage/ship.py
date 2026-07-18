"""Ship model: bay/row/tier slot geometry and stability proxies (Phase 1, T1.1).

Slot indexing (D1): s = bay*(n_rows*n_tiers) + row*n_tiers + tier.
tier 0 = bottom (keel), row 0 = port side, bay 0 = forward.

Moment proxies (D2): dimensionless lever arms from grid indices, origin at
keel + centerline.
  vertical   z(s) = tier(s)                    -> M_v = Σ w·z,  constraint M_v ≤ V_max
  transverse y(s) = row(s) - (n_rows-1)/2       -> M_t = Σ w·y,  constraint |M_t| ≤ T_max
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Ship(BaseModel):
    """Ship geometry and stability bounds. Immutable."""

    model_config = ConfigDict(frozen=True)

    n_bays: int = Field(ge=1)
    n_rows: int = Field(ge=1)
    n_tiers: int = Field(ge=1)
    max_vertical_moment: float = Field(ge=0.0)
    max_transverse_moment: float = Field(ge=0.0)

    @property
    def n_slots(self) -> int:
        return self.n_bays * self.n_rows * self.n_tiers


class Container(BaseModel):
    """A single container to be stowed. Immutable."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=r"^C\d+$")
    weight: float = Field(gt=0.0)
    destination: str
    hazmat_class: int | None = None


def slot_to_brt(ship: Ship, slot: int) -> tuple[int, int, int]:
    """Linear slot index -> (bay, row, tier). Raises IndexError if out of range."""
    if not 0 <= slot < ship.n_slots:
        raise IndexError(f"slot {slot} out of range [0, {ship.n_slots})")
    tier = slot % ship.n_tiers
    row = (slot // ship.n_tiers) % ship.n_rows
    bay = slot // (ship.n_rows * ship.n_tiers)
    return bay, row, tier


def brt_to_slot(ship: Ship, bay: int, row: int, tier: int) -> int:
    """(bay, row, tier) -> linear slot index. Raises IndexError if any coord out of range."""
    if not 0 <= bay < ship.n_bays:
        raise IndexError(f"bay {bay} out of range [0, {ship.n_bays})")
    if not 0 <= row < ship.n_rows:
        raise IndexError(f"row {row} out of range [0, {ship.n_rows})")
    if not 0 <= tier < ship.n_tiers:
        raise IndexError(f"tier {tier} out of range [0, {ship.n_tiers})")
    return bay * (ship.n_rows * ship.n_tiers) + row * ship.n_tiers + tier


def vertical_lever(ship: Ship, slot: int) -> float:
    """z(s) = tier(s); tier 0 (keel) contributes 0."""
    _, _, tier = slot_to_brt(ship, slot)
    return float(tier)


def transverse_lever(ship: Ship, slot: int) -> float:
    """y(s) = row(s) - (n_rows-1)/2; symmetric about centerline, negative = port."""
    _, row, _ = slot_to_brt(ship, slot)
    return row - (ship.n_rows - 1) / 2


def moments(ship: Ship, weights_by_slot: dict[int, float]) -> tuple[float, float]:
    """Return (M_v, M_t) for weights placed at given slot indices."""
    m_v = 0.0
    m_t = 0.0
    for slot, weight in weights_by_slot.items():
        m_v += weight * vertical_lever(ship, slot)
        m_t += weight * transverse_lever(ship, slot)
    return m_v, m_t

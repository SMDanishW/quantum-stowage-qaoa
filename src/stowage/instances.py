"""Instance schema, JSON I/O, and the seeded generator (Phase 1).

T1.1 delivers the ``Instance`` model plus byte-stable save/load. T1.3 adds the
seeded, feasible-by-construction ``generate_instance`` generator.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator

from stowage.ship import Container, Ship, moments, slot_to_brt

Assignment = dict[str, int]  # container_id -> slot index (mirrors feasibility.Assignment)


class InfeasibleGenerationError(RuntimeError):
    """Raised when the generator cannot build a feasible witness (no fallback)."""


class Instance(BaseModel):
    """A stowage problem instance: ship + containers + port rotation. Immutable."""

    model_config = ConfigDict(frozen=True)

    name: str
    ship: Ship
    containers: tuple[Container, ...]
    port_rotation: tuple[str, ...]
    seed: int
    generator_params: dict[str, float | int | str] = {}
    schema_version: int = 1

    @model_validator(mode="after")
    def _validate(self) -> Instance:
        ids = [c.id for c in self.containers]
        if len(ids) != len(set(ids)):
            raise ValueError("container ids must be unique within an instance")
        if len(self.port_rotation) != len(set(self.port_rotation)):
            raise ValueError("port_rotation entries must be unique")
        ports = set(self.port_rotation)
        unknown = sorted({c.destination for c in self.containers} - ports)
        if unknown:
            raise ValueError(f"destinations not in port_rotation: {unknown}")
        return self


def write_json(model: BaseModel, path: Path) -> None:
    """Single byte-stable JSON write path: sorted keys, indent=2, ``\\n`` newlines.

    Shared by :func:`save_instance` and the optimum-cache writer in ``baselines`` so
    there is exactly one serialization contract in the codebase.
    """
    text = json.dumps(model.model_dump(), indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def save_instance(instance: Instance, path: Path) -> None:
    """Serialize to JSON with sorted keys, indent=2, ``\\n`` newlines (byte-stable)."""
    write_json(instance, path)


def load_instance(path: Path) -> Instance:
    """Deserialize an Instance from JSON produced by :func:`save_instance`."""
    return Instance.model_validate_json(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# T1.3 — seeded instance generator
# --------------------------------------------------------------------------- #

_WITNESS_MAX_SHUFFLES = 100  # D6: candidate hazmat placements before failing loudly


def auto_ship_dims(n_containers: int, *, toy: bool = False) -> tuple[int, int, int]:
    """Deterministic ship sizing (D8): return (n_bays, n_rows, n_tiers).

    ``n_tiers = 3``. Choose (n_rows in {2,3,4}, n_bays) giving the smallest grid with
    ``n_bays*n_rows*n_tiers >= ceil(1.25*n_containers)``, preferring more bays over more
    rows on ties. Toy mode reuses the same rule; for 4-6 containers it yields 1x2x3 or
    1x3x3 (<=9 slots), which the toy caller asserts.
    """
    n_tiers = 3
    target = math.ceil(1.25 * n_containers)
    best: tuple[int, int, int] | None = None  # (n_slots, -n_bays, n_rows) for min-compare
    best_dims: tuple[int, int, int] | None = None
    for n_rows in (2, 3, 4):
        n_bays = max(1, math.ceil(target / (n_rows * n_tiers)))
        n_slots = n_bays * n_rows * n_tiers
        key = (n_slots, -n_bays, n_rows)  # smaller slots, then more bays, then fewer rows
        if best is None or key < best:
            best = key
            best_dims = (n_bays, n_rows, n_tiers)
    assert best_dims is not None
    return best_dims


def _support_ordered_slots(ship: Ship, n_needed: int) -> list[int]:
    """First ``n_needed`` slots in (tier, bay, row) order: a supported footprint.

    Filling tier 0 across every stack before any tier 1 guarantees every occupied
    stack's tiers form a prefix {0..k}, so support holds for any permutation of
    containers over this fixed footprint.
    """
    slots = sorted(
        range(ship.n_slots),
        key=lambda s: (slot_to_brt(ship, s)[2], slot_to_brt(ship, s)[0], slot_to_brt(ship, s)[1]),
    )
    return slots[:n_needed]


def _hazmat_separated(ship: Ship, assignment: Assignment, hazmat_ids: list[str]) -> bool:
    """True iff no two hazmat containers sit at Manhattan distance 1 (D5)."""
    coords = [slot_to_brt(ship, assignment[cid]) for cid in hazmat_ids]
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            (ba, ra, ta), (bb, rb, tb) = coords[i], coords[j]
            if abs(ba - bb) + abs(ra - rb) + abs(ta - tb) == 1:
                return False
    return True


def _witness_assignment(
    ship: Ship, containers: tuple[Container, ...], seed: int
) -> Assignment:
    """Build a feasible witness (D6): supported footprint + hazmat separation.

    Deterministic from ``(ship geometry, containers, seed)`` alone — uses its own
    ``default_rng(seed)`` so it is reproducible from a finished Instance (that is why
    ``_build_witness`` below can replay it). Only the geometry of ``ship`` is used;
    moment bounds are irrelevant here. Raises ``InfeasibleGenerationError`` after
    ``_WITNESS_MAX_SHUFFLES`` failed hazmat placements — no rejection-sampling fallback.
    """
    footprint = _support_ordered_slots(ship, len(containers))
    hazmat_ids = [c.id for c in containers if c.hazmat_class is not None]
    rng = np.random.default_rng(seed)
    for _ in range(_WITNESS_MAX_SHUFFLES):
        perm = rng.permutation(np.asarray(footprint, dtype=int))
        assignment: Assignment = {c.id: int(perm[i]) for i, c in enumerate(containers)}
        if _hazmat_separated(ship, assignment, hazmat_ids):
            return assignment
    raise InfeasibleGenerationError(
        f"could not place {len(hazmat_ids)} hazmat containers with separation in "
        f"{ship.n_slots} slots after {_WITNESS_MAX_SHUFFLES} shuffles (seed={seed})"
    )


def _build_witness(instance: Instance) -> Assignment:
    """Reproduce the generation-time witness for an already-built instance (test hook).

    Deterministic from the instance content, so ``check_feasibility`` against it returns
    ``feasible=True`` (the instance's moment bounds were set to 1.1x this witness).
    """
    return _witness_assignment(instance.ship, instance.containers, instance.seed)


def generate_instance(
    n_containers: int,
    n_ports: int,
    seed: int,
    *,
    weight_range: tuple[float, float] = (5.0, 30.0),
    hazmat_fraction: float = 0.15,
    toy: bool = False,
) -> Instance:
    """Generate a feasible-by-construction stowage instance (D6, D8).

    rng consumption order (fixed for the determinism contract): weights, destinations,
    hazmat selection. Witness placement uses a separate ``default_rng(seed)`` so the
    witness is reproducible from the finished instance.
    """
    if n_containers < 1:
        raise ValueError("n_containers must be >= 1")
    if n_ports < 1:
        raise ValueError("n_ports must be >= 1")
    if toy and not 4 <= n_containers <= 6:
        raise ValueError(f"toy mode requires 4-6 containers, got {n_containers}")
    lo, hi = weight_range
    if not 0.0 < lo <= hi:
        raise ValueError(f"invalid weight_range {weight_range}")
    if not 0.0 <= hazmat_fraction <= 1.0:
        raise ValueError(f"hazmat_fraction must be in [0, 1], got {hazmat_fraction}")

    n_bays, n_rows, n_tiers = auto_ship_dims(n_containers, toy=toy)
    if toy and n_bays * n_rows * n_tiers > 9:
        raise ValueError("toy ship exceeded 9-slot cap")

    rng = np.random.default_rng(seed)

    # (1) weights, uniform over range, rounded to 0.1 t
    weights = [round(float(rng.uniform(lo, hi)), 1) for _ in range(n_containers)]

    # (2) destinations: first k round-robin (each port >=1 when n>=k), rest uniform, shuffle
    ports = [f"P{i + 1}" for i in range(n_ports)]
    dests: list[str] = []
    for i in range(n_containers):
        dests.append(ports[i] if i < n_ports else ports[int(rng.integers(0, n_ports))])
    rng.shuffle(dests)

    # (3) hazmat selection
    n_haz = round(hazmat_fraction * n_containers)
    haz_idx = (
        set(int(i) for i in rng.choice(n_containers, size=n_haz, replace=False))
        if n_haz > 0
        else set()
    )

    containers = tuple(
        Container(
            id=f"C{i + 1}",
            weight=weights[i],
            destination=dests[i],
            hazmat_class=1 if i in haz_idx else None,
        )
        for i in range(n_containers)
    )

    # (4) witness + moment bounds from it (D6)
    geom = Ship(
        n_bays=n_bays,
        n_rows=n_rows,
        n_tiers=n_tiers,
        max_vertical_moment=0.0,
        max_transverse_moment=0.0,
    )
    witness = _witness_assignment(geom, containers, seed)
    weight_by_id = {c.id: c.weight for c in containers}
    weights_by_slot = {witness[c.id]: weight_by_id[c.id] for c in containers}
    m_v, m_t = moments(geom, weights_by_slot)
    slack = 1.1
    mean_w = sum(weights) / n_containers
    v_max = round(slack * m_v, 6)
    t_max = round(max(slack * abs(m_t), 0.5 * mean_w), 6)

    ship = Ship(
        n_bays=n_bays,
        n_rows=n_rows,
        n_tiers=n_tiers,
        max_vertical_moment=v_max,
        max_transverse_moment=t_max,
    )

    name = f"stow_c{n_containers}_p{n_ports}_s{seed}" + ("_toy" if toy else "")
    generator_params: dict[str, float | int | str] = {
        "n_containers": n_containers,
        "n_ports": n_ports,
        "seed": seed,
        "hazmat_fraction": hazmat_fraction,
        "weight_min": lo,
        "weight_max": hi,
        "toy": int(toy),
        "bound_slack": slack,
    }
    return Instance(
        name=name,
        ship=ship,
        containers=containers,
        port_rotation=tuple(ports),
        seed=seed,
        generator_params=generator_params,
    )

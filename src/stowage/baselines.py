"""Classical baselines.

Phase 1 slice (T1.3): exact brute-force optimum over toy instances, cached alongside
the instance. Simulated annealing and the constructive heuristic stay Phase 3 (T3.3).
"""

from __future__ import annotations

import time
from itertools import permutations
from math import perm
from pathlib import Path

from pydantic import BaseModel

from stowage.feasibility import Assignment, check_feasibility
from stowage.instances import Instance, write_json

_MAX_PLACEMENTS = 5_000_000  # guard (spec §baselines): refuse > 5e6 placements


class OptimumRecord(BaseModel):
    """Exact optimum for a (toy) instance, cached as ``<stem>.optimum.json``."""

    instance_name: str
    method: str = "brute_force"
    optimal_objective: int
    optimal_assignment: Assignment
    n_feasible: int
    n_evaluated: int
    elapsed_seconds: float


def brute_force_optimum(instance: Instance) -> OptimumRecord:
    """Enumerate all placements of containers (id order) into distinct slots.

    Evaluates each via :func:`check_feasibility`, minimizing ``overstow_count`` over the
    feasible set. Ties broken by lexicographic (enumeration) order — the first optimum
    found wins. Raises ``ValueError`` if the search space exceeds ``_MAX_PLACEMENTS``
    (loud, not slow) and ``RuntimeError`` if no feasible assignment exists (the
    generator's feasibility guarantee would have been violated).
    """
    n = len(instance.containers)
    n_slots = instance.ship.n_slots
    n_placements = perm(n_slots, n)  # P(n_slots, n)
    if n_placements > _MAX_PLACEMENTS:
        raise ValueError(
            f"search space P({n_slots},{n}) = {n_placements} exceeds "
            f"{_MAX_PLACEMENTS}; brute force is toy-only"
        )

    ids = [c.id for c in instance.containers]
    start = time.perf_counter()
    best_obj: int | None = None
    best_assignment: Assignment | None = None
    n_feasible = 0
    n_evaluated = 0

    for placement in permutations(range(n_slots), n):
        n_evaluated += 1
        assignment: Assignment = dict(zip(ids, placement, strict=True))
        report = check_feasibility(instance, assignment)
        if not report.feasible:
            continue
        n_feasible += 1
        if best_obj is None or report.overstow_count < best_obj:
            best_obj = report.overstow_count
            best_assignment = assignment

    elapsed = time.perf_counter() - start
    if best_obj is None or best_assignment is None:
        raise RuntimeError(
            f"no feasible assignment found for '{instance.name}' — generator "
            "feasibility guarantee violated"
        )
    return OptimumRecord(
        instance_name=instance.name,
        optimal_objective=best_obj,
        optimal_assignment=best_assignment,
        n_feasible=n_feasible,
        n_evaluated=n_evaluated,
        elapsed_seconds=round(elapsed, 4),
    )


def save_optimum(record: OptimumRecord, path: Path) -> None:
    """Write an OptimumRecord using the shared byte-stable JSON contract."""
    write_json(record, path)


def load_optimum(path: Path) -> OptimumRecord:
    """Read an OptimumRecord cache file."""
    return OptimumRecord.model_validate_json(path.read_text(encoding="utf-8"))

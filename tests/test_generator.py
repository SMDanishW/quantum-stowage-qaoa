"""T1.3 tests: seeded generator, witness feasibility, toy brute force, CLI, guards."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from stowage.baselines import brute_force_optimum, load_optimum, save_optimum
from stowage.cli import main
from stowage.feasibility import check_feasibility
from stowage.instances import (
    InfeasibleGenerationError,
    _build_witness,
    auto_ship_dims,
    generate_instance,
    load_instance,
    save_instance,
)


def test_determinism_same_seed_byte_identical(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    save_instance(generate_instance(12, 3, 7), a)
    save_instance(generate_instance(12, 3, 7), b)
    assert a.read_bytes() == b.read_bytes()


def test_determinism_different_seed_differs(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    save_instance(generate_instance(12, 3, 7), a)
    save_instance(generate_instance(12, 3, 8), b)
    assert a.read_bytes() != b.read_bytes()


@pytest.mark.parametrize("n", [4, 6, 12])
@pytest.mark.parametrize("seed", list(range(20)))
def test_witness_is_feasible(n: int, seed: int) -> None:
    inst = generate_instance(n, 3, seed)
    report = check_feasibility(inst, _build_witness(inst))
    assert report.feasible, report.errors


def test_auto_ship_dims_table() -> None:
    assert auto_ship_dims(4) == (1, 2, 3)  # target 5 -> 6 slots
    assert auto_ship_dims(5) == (1, 3, 3)  # target 7 -> 9 slots
    assert auto_ship_dims(6) == (1, 3, 3)  # target 8 -> 9 slots
    assert auto_ship_dims(12) == (3, 2, 3)  # target 15 -> 18 slots, prefer more bays


def test_toy_brute_force_cached_and_feasible(tmp_path: Path) -> None:
    inst = generate_instance(6, 3, 7, toy=True)
    start = time.perf_counter()
    record = brute_force_optimum(inst)
    elapsed = time.perf_counter() - start
    assert elapsed < 20.0, f"brute force took {elapsed:.1f}s"
    assert record.n_feasible >= 1

    opt_path = tmp_path / f"{inst.name}.optimum.json"
    save_optimum(record, opt_path)
    reloaded = load_optimum(opt_path)
    assert reloaded == record
    assert check_feasibility(inst, reloaded.optimal_assignment).feasible


def test_toy_rejects_large_n() -> None:
    with pytest.raises(ValueError):
        generate_instance(7, 3, 0, toy=True)


def test_infeasible_generation_raises() -> None:
    # All-hazmat on a dense ship: no separated placement exists -> loud failure.
    with pytest.raises(InfeasibleGenerationError):
        generate_instance(6, 3, 0, hazmat_fraction=1.0)


def test_cli_generate_toy_writes_files(tmp_path: Path) -> None:
    out = tmp_path / "out"
    rc = main(
        ["generate", "--containers", "5", "--ports", "2", "--seed", "3", "--toy", "--out", str(out)]
    )
    assert rc == 0
    inst_path = out / "stow_c5_p2_s3_toy.json"
    opt_path = out / "stow_c5_p2_s3_toy.optimum.json"
    assert inst_path.exists() and opt_path.exists()
    inst = load_instance(inst_path)
    assert len(inst.containers) == 5
    assert check_feasibility(inst, load_optimum(opt_path).optimal_assignment).feasible


def test_each_port_has_container_when_n_ge_k() -> None:
    inst = generate_instance(12, 3, 7)
    dests = {c.destination for c in inst.containers}
    assert dests == set(inst.port_rotation)

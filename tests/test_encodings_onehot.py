"""One-hot encoding verification (T2.2) — spec §6 ground-state protocol (option B).

Ground truth for the QUBO is the moment-RELAXED optimum (moments excluded per D9).
Energy identity is against the constrained (cached) optimum. See phase2-spec §6.
"""

from __future__ import annotations

import logging
from itertools import permutations
from pathlib import Path

import numpy as np
import pytest

from stowage.baselines import OptimumRecord, load_optimum
from stowage.encodings import ENCODINGS, OneHotEncoding
from stowage.feasibility import check_feasibility
from stowage.instances import Instance, load_instance
from stowage.ship import Container, Ship

DATA = Path(__file__).parent / "data"
TOYS = ["stow_c4_p2_s1_toy", "stow_c6_p3_s2_toy", "stow_c6_p3_s7_toy"]
ENC = ENCODINGS["onehot"]


def _load(stem: str) -> tuple[Instance, OptimumRecord]:
    return load_instance(DATA / f"{stem}.json"), load_optimum(DATA / f"{stem}.optimum.json")


def _relaxed_feasible(inst: Instance, assignment: dict[str, int]) -> bool:
    r = check_feasibility(inst, assignment)
    return r.assignment_valid and r.supported and r.hazmat_ok


# --- vectorized sweep: E = offset + x·h + Σ J_ij x_i x_j (spec §6.5) ------------
def _sweep_arrays(bqm: object) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray, float]:
    varlist = list(bqm.variables)  # type: ignore[attr-defined]
    idx = {v: i for i, v in enumerate(varlist)}
    h = np.array([bqm.get_linear(v) for v in varlist], dtype=np.float64)  # type: ignore[attr-defined]
    qi, qj, qc = [], [], []
    for (u, v), c in bqm.quadratic.items():  # type: ignore[attr-defined]
        qi.append(idx[u])
        qj.append(idx[v])
        qc.append(c)
    return (
        varlist,
        h,
        np.array([qi, qj], dtype=np.int64).reshape(2, -1),
        np.array(qc, dtype=np.float64),
        float(bqm.offset),  # type: ignore[attr-defined]
    )


def _energies(
    x: np.ndarray, h: np.ndarray, q: np.ndarray, qc: np.ndarray, off: float
) -> np.ndarray:
    e = off + x @ h
    if qc.size:
        e = e + (x[:, q[0]] * x[:, q[1]] * qc).sum(axis=1)
    return e


# --- §6.1 informational record -------------------------------------------------
@pytest.mark.parametrize("stem", TOYS)
def test_relaxed_vs_cached_recorded(stem: str, caplog: pytest.LogCaptureFixture) -> None:
    _, rec = _load(stem)
    with caplog.at_level(logging.INFO):
        logging.getLogger(__name__).info(
            "toy=%s cached=%d relaxed=%d",
            stem,
            rec.optimal_objective,
            rec.relaxed_optimal_objective,
        )
    assert rec.relaxed_optimal_objective <= rec.optimal_objective


# --- §6.2 round-trip -----------------------------------------------------------
@pytest.mark.parametrize("stem", TOYS)
def test_round_trip(stem: str) -> None:
    inst, rec = _load(stem)
    build = ENC.build(inst)
    decoded = build.decode(ENC.encode_assignment(inst, rec.optimal_assignment))
    assert decoded == rec.optimal_assignment
    n, s = len(inst.containers), inst.ship.n_slots
    ids = [c.id for c in inst.containers]
    rng = np.random.default_rng(0)
    for _ in range(20):
        placement = rng.permutation(s)[:n]
        a = {cid: int(placement[i]) for i, cid in enumerate(ids)}
        assert build.decode(ENC.encode_assignment(inst, a)) == a


# --- §6.3 energy identity (against CONSTRAINED optimum) ------------------------
@pytest.mark.parametrize("stem", TOYS)
def test_energy_identity(stem: str) -> None:
    inst, rec = _load(stem)
    build = ENC.build(inst)
    e = build.bqm.energy(ENC.encode_assignment(inst, rec.optimal_assignment))
    assert abs(e - rec.optimal_objective) < 1e-9


# --- §6.4 valid-state minimum (against RELAXED optimum) ------------------------
@pytest.mark.parametrize("stem", TOYS)
def test_valid_state_minimum(stem: str) -> None:
    inst, rec = _load(stem)
    build = ENC.build(inst)
    varlist, h, q, qc, off = _sweep_arrays(build.bqm)
    vidx = {v: i for i, v in enumerate(varlist)}
    n, s = len(inst.containers), inst.ship.n_slots
    ids = [c.id for c in inst.containers]
    perms = list(permutations(range(s), n))
    x = np.zeros((len(perms), len(varlist)), dtype=np.float64)
    for r, placement in enumerate(perms):
        for i, slot in enumerate(placement):
            x[r, vidx[f"x_{ids[i]}_{slot}"]] = 1.0
    emin = float(_energies(x, h, q, qc, off).min())
    assert abs(emin - rec.relaxed_optimal_objective) < 1e-9


# --- §6.5 full 2^N sweep (n=4 only; slow) + fast subset ------------------------
def _sweep_min_and_minimizers(bqm: object, sample_idx: np.ndarray) -> tuple[float, np.ndarray]:
    varlist, h, q, qc, off = _sweep_arrays(bqm)
    n_vars = len(varlist)
    best = np.inf
    mins: list[np.ndarray] = []
    for start in range(0, sample_idx.size, 1 << 20):
        block = sample_idx[start : start + (1 << 20)]
        x = ((block[:, None] >> np.arange(n_vars)) & 1).astype(np.float64)
        e = _energies(x, h, q, qc, off)
        bmin = float(e.min())
        if bmin < best - 1e-9:
            best, mins = bmin, [x[np.abs(e - bmin) < 1e-9]]
        elif abs(bmin - best) < 1e-9:
            mins.append(x[np.abs(e - bmin) < 1e-9])
    return best, np.concatenate(mins) if mins else np.empty((0, n_vars))


def _assert_minimizers_relaxed_feasible(inst: Instance, build: object, rows: np.ndarray) -> None:
    varlist = list(build.bqm.variables)  # type: ignore[attr-defined]
    for row in rows:
        sample = {v: int(row[i]) for i, v in enumerate(varlist)}
        assert _relaxed_feasible(inst, build.decode(sample))  # type: ignore[attr-defined]


@pytest.mark.slow
def test_full_sweep_n4() -> None:
    inst, rec = _load("stow_c4_p2_s1_toy")
    build = ENC.build(inst)
    n_vars = len(build.bqm.variables)
    assert n_vars == 24
    emin, mins = _sweep_min_and_minimizers(build.bqm, np.arange(1 << n_vars, dtype=np.int64))
    assert abs(emin - rec.relaxed_optimal_objective) < 1e-9
    _assert_minimizers_relaxed_feasible(inst, build, mins)


def test_sweep_subset_no_undercut_n4() -> None:
    """Fast CI subset of §6.5: dominance lemma — no state undercuts the relaxed optimum."""
    inst, rec = _load("stow_c4_p2_s1_toy")
    build = ENC.build(inst)
    n_vars = len(build.bqm.variables)
    rng = np.random.default_rng(7)
    idx = rng.integers(0, 1 << n_vars, size=200_000, dtype=np.int64)
    emin, _ = _sweep_min_and_minimizers(build.bqm, idx)
    assert emin >= rec.relaxed_optimal_objective - 1e-9


# --- decoder never repairs (D13) ----------------------------------------------
def test_invalid_register_decodes_to_sentinel() -> None:
    inst, _ = _load("stow_c4_p2_s1_toy")
    build = ENC.build(inst)
    s = inst.ship.n_slots
    sample = ENC.encode_assignment(inst, {c.id: i for i, c in enumerate(inst.containers)})
    # popcount-0 for C1
    zero = dict(sample)
    for k in range(s):
        zero[f"x_C1_{k}"] = 0
    dec0 = build.decode(zero)
    assert dec0["C1"] == -1
    assert not check_feasibility(inst, dec0).assignment_valid
    # popcount-2 for C2
    multi = dict(sample)
    multi["x_C2_0"] = 1
    multi["x_C2_1"] = 1
    dec2 = build.decode(multi)
    assert dec2["C2"] == -1
    assert not check_feasibility(inst, dec2).assignment_valid


# --- penalty_report + D11 formulas --------------------------------------------
def test_penalty_report_matches_d11() -> None:
    inst, _ = _load("stow_c6_p3_s2_toy")
    report = ENC.build(inst).penalty_report
    assert report.encoding == "onehot"
    assert (report.n_containers, report.n_slots, report.n_variables) == (6, 9, 54)
    assert report.f_max == 15
    assert report.weights == {"A": 112.0, "P_sup": 16.0, "P_haz": 16.0}
    assert report.max_abs_objective_coeff == 1.0
    assert report.energy_scale_ratio == 112.0
    assert report.n_quadratic_terms == len(ENC.build(inst).bqm.quadratic)


def test_penalty_report_logged(caplog: pytest.LogCaptureFixture) -> None:
    inst, _ = _load("stow_c4_p2_s1_toy")
    with caplog.at_level(logging.INFO, logger="stowage.encodings"):
        ENC.build(inst)
    assert any('"encoding":"onehot"' in r.message for r in caplog.records)


# --- determinism ---------------------------------------------------------------
def test_build_is_deterministic() -> None:
    inst, _ = _load("stow_c6_p3_s7_toy")
    assert ENC.build(inst).bqm == ENC.build(inst).bqm


# --- edge cases: single-tier ship (no stacks) ---------------------------------
def _single_tier_instance() -> Instance:
    ship = Ship(n_bays=2, n_rows=2, n_tiers=1, max_vertical_moment=1e12, max_transverse_moment=1e12)
    containers = (
        Container(id="C1", weight=10.0, destination="P1"),
        Container(id="C2", weight=12.0, destination="P2"),
    )
    return Instance(name="single_tier", ship=ship, containers=containers,
                    port_rotation=("P1", "P2"), seed=0)


def test_single_tier_no_support_or_objective_terms() -> None:
    inst = _single_tier_instance()
    build = ENC.build(inst)
    # No tier>0 slots -> no H_sup linear (all +P_sup would be on tier>0); no stacks -> no H_obj.
    # H_obj/H_sup absence: every quadratic term must come from H_cont or H_slot only.
    # Assert by energy: any valid placement has energy 0 (relaxed optimum 0, no overstow possible).
    ids = [c.id for c in inst.containers]
    s = inst.ship.n_slots
    for placement in permutations(range(s), len(ids)):
        a = dict(zip(ids, placement, strict=True))
        assert abs(build.bqm.energy(ENC.encode_assignment(inst, a))) < 1e-9


def test_hazmat_free_has_no_haz_reward() -> None:
    inst = _single_tier_instance()  # no hazmat containers
    build = ENC.build(inst)
    # hazmat-free: energy of any valid placement stays exactly the overstow count (0 here).
    a = {"C1": 0, "C2": 1}
    assert build.bqm.energy(ENC.encode_assignment(inst, a)) == 0.0


def test_registry_has_only_onehot() -> None:
    assert set(ENCODINGS) == {"onehot"}
    assert isinstance(ENCODINGS["onehot"], OneHotEncoding)

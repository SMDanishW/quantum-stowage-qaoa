"""Domain-wall encoding verification (T2.3) — spec §6 ground-state protocol (option B).

Mirrors ``test_encodings_onehot.py``. Ground truth for the QUBO is the moment-RELAXED
optimum (moments excluded per D9); energy identity is against the constrained (cached)
optimum. Adds the T2.3-specific checks: qubit-count reduction vs one-hot (D12), the
P_dw = 1 + Σ|bias| formula (D14), wall-validity decode semantics, and a hand-built
2-hazmat instance that exercises H_haz (carry-forward blind spot). The full 2^N sweep
is N=20 for domain-wall (1M states) and is NOT slow-marked (spec §6.5 / §7).
"""

from __future__ import annotations

import logging
from itertools import permutations
from pathlib import Path

import numpy as np
import pytest

from stowage.baselines import OptimumRecord, load_optimum
from stowage.encodings import (
    ENCODINGS,
    DomainWallEncoding,
    OneHotEncoding,
    _domainwall_core,
)
from stowage.feasibility import check_feasibility, overstow_count
from stowage.instances import Instance, auto_ship_dims, load_instance
from stowage.ship import Container, Ship

DATA = Path(__file__).parent / "data"
TOYS = ["stow_c4_p2_s1_toy", "stow_c6_p3_s2_toy", "stow_c6_p3_s7_toy"]
ENC = ENCODINGS["domainwall"]
OH = ENCODINGS["onehot"]


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
    n, s = len(inst.containers), inst.ship.n_slots
    ids = [c.id for c in inst.containers]
    perms = list(permutations(range(s), n))
    samples = [ENC.encode_assignment(inst, dict(zip(ids, p, strict=True))) for p in perms]
    x = np.array([[smp[v] for v in varlist] for smp in samples], dtype=np.float64)
    emin = float(_energies(x, h, q, qc, off).min())
    assert abs(emin - rec.relaxed_optimal_objective) < 1e-9


# --- §6.5 full 2^N sweep (n=4, N=20; NOT slow — 1M states) + minimizer check ---
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


def test_full_sweep_n4() -> None:
    inst, rec = _load("stow_c4_p2_s1_toy")
    build = ENC.build(inst)
    n_vars = len(build.bqm.variables)
    assert n_vars == 20  # domain-wall n=4: n*(S-1) = 4*5 (D12); one-hot would be 24
    emin, mins = _sweep_min_and_minimizers(build.bqm, np.arange(1 << n_vars, dtype=np.int64))
    assert abs(emin - rec.relaxed_optimal_objective) < 1e-9
    varlist = list(build.bqm.variables)
    for row in mins:
        sample = {v: int(row[i]) for i, v in enumerate(varlist)}
        assert _relaxed_feasible(inst, build.decode(sample))


# --- decoder never repairs (D13) ----------------------------------------------
def test_wall_broken_register_decodes_to_sentinel() -> None:
    inst, _ = _load("stow_c4_p2_s1_toy")
    build = ENC.build(inst)
    s = inst.ship.n_slots
    sample = ENC.encode_assignment(inst, {c.id: i for i, c in enumerate(inst.containers)})
    # wall-broken register "0 1 ..." for C1 (ascent at k=1 -> not 1^k 0^m)
    broken = dict(sample)
    for k in range(1, s):
        broken[f"d_C1_{k}"] = 0
    broken["d_C1_2"] = 1  # 0 1 0 ... -> non-monotone
    dec = build.decode(broken)
    assert dec["C1"] == -1
    assert not check_feasibility(inst, dec).assignment_valid


def test_all_ones_and_all_zeros_are_valid_states() -> None:
    inst, _ = _load("stow_c4_p2_s1_toy")
    build = ENC.build(inst)
    s = inst.ship.n_slots
    ids = [c.id for c in inst.containers]
    # all-zeros register -> slot 0; all-ones register -> slot S-1 (both valid, not -1)
    all_zero = {f"d_{cid}_{k}": 0 for cid in ids for k in range(1, s)}
    all_one = {f"d_{cid}_{k}": 1 for cid in ids for k in range(1, s)}
    assert build.decode(all_zero) == {cid: 0 for cid in ids}
    assert build.decode(all_one) == {cid: s - 1 for cid in ids}


# --- P_dw formula (D14): 1 + Σ|bias| of the non-validity Hamiltonian ----------
@pytest.mark.parametrize("stem", TOYS)
def test_p_dw_matches_bias_mass(stem: str) -> None:
    inst, _ = _load(stem)
    core_bqm, _weights, _cids, _s = _domainwall_core(inst)
    mass = sum(abs(b) for b in core_bqm.linear.values())
    mass += sum(abs(c) for c in core_bqm.quadratic.values())
    p_dw = ENC.build(inst).penalty_report.weights["P_dw"]
    assert p_dw == 1.0 + mass
    assert p_dw > max(112.0, 1.0)  # dominates the objective/constraint scale


def test_penalty_report_populated() -> None:
    inst, _ = _load("stow_c6_p3_s2_toy")
    report = ENC.build(inst).penalty_report
    assert report.encoding == "domainwall"
    assert (report.n_containers, report.n_slots, report.n_variables) == (6, 9, 48)  # 6*8
    assert report.f_max == 15
    assert report.weights["A"] == 112.0
    assert report.weights["P_sup"] == report.weights["P_haz"] == 16.0
    assert "P_dw" in report.weights
    assert report.max_abs_objective_coeff == 1.0
    # energy_scale_ratio is the largest weight (P_dw) over unit objective coeff (R5 tracked).
    assert report.energy_scale_ratio == max(report.weights.values())


def test_penalty_report_logged(caplog: pytest.LogCaptureFixture) -> None:
    inst, _ = _load("stow_c4_p2_s1_toy")
    with caplog.at_level(logging.INFO, logger="stowage.encodings"):
        ENC.build(inst)
    assert any('"encoding":"domainwall"' in r.message for r in caplog.records)


# --- determinism ---------------------------------------------------------------
def test_build_is_deterministic() -> None:
    inst, _ = _load("stow_c6_p3_s7_toy")
    assert ENC.build(inst).bqm == ENC.build(inst).bqm


# --- qubit-count reduction AC (D12) -------------------------------------------
@pytest.mark.parametrize("stem", TOYS)
def test_variable_count_is_n_times_s_minus_one(stem: str) -> None:
    inst, _ = _load(stem)
    n, s = len(inst.containers), inst.ship.n_slots
    dw = len(ENC.build(inst).bqm.variables)
    oh = len(OH.build(inst).bqm.variables)
    assert dw == n * (s - 1)
    assert oh == n * s
    assert dw < oh  # exactly one qubit saved per container


# spec §7 / D12 table rows the reduction-assertion test must pin.
D12_TABLE = {
    4: (6, 24, 20),
    8: (12, 96, 88),
    12: (18, 216, 204),
    16: (24, 384, 368),
    20: (27, 540, 520),
}


@pytest.mark.parametrize("n", sorted(D12_TABLE))
def test_qubit_reduction_matches_d12_table(n: int) -> None:
    exp_s, exp_oh, exp_dw = D12_TABLE[n]
    n_bays, n_rows, n_tiers = auto_ship_dims(n)
    s = n_bays * n_rows * n_tiers
    assert s == exp_s
    assert n * s == exp_oh
    assert n * (s - 1) == exp_dw
    assert n * (s - 1) < n * s


# --- carry-forward: hand-built 2-hazmat instance exercises H_haz --------------
def _two_hazmat_instance() -> Instance:
    """2x2x1 ship, two hazmat containers — single tier so H_sup/H_obj vanish and the
    only non-trivial penalty is H_haz. Adjacent placements must be penalized, non-
    adjacent ones must not (verified against check_feasibility)."""
    ship = Ship(n_bays=2, n_rows=2, n_tiers=1, max_vertical_moment=1e12, max_transverse_moment=1e12)
    containers = (
        Container(id="C1", weight=10.0, destination="P1", hazmat_class=3),
        Container(id="C2", weight=11.0, destination="P1", hazmat_class=3),
    )
    return Instance(
        name="two_hazmat", ship=ship, containers=containers, port_rotation=("P1", "P2"), seed=0
    )


@pytest.mark.parametrize(
    "enc", [OneHotEncoding(), DomainWallEncoding()], ids=["onehot", "domainwall"]
)
def test_hazmat_penalty_sign_and_adjacency(enc: OneHotEncoding | DomainWallEncoding) -> None:
    inst = _two_hazmat_instance()
    build = enc.build(inst)
    s = inst.ship.n_slots
    ids = [c.id for c in inst.containers]
    saw_ok, saw_violation = False, False
    for placement in permutations(range(s), len(ids)):
        a = dict(zip(ids, placement, strict=True))
        assert build.decode(enc.encode_assignment(inst, a)) == a  # round-trip on hazmat instance
        report = check_feasibility(inst, a)
        e = build.bqm.energy(enc.encode_assignment(inst, a))
        base = float(overstow_count(inst, a))  # 0 on a single tier
        if report.hazmat_ok:
            assert abs(e - base) < 1e-9  # no reward, no spurious penalty
            saw_ok = True
        else:
            assert e > base + 1e-9  # penalty is POSITIVE (correct sign) exactly when adjacent
            saw_violation = True
    assert saw_ok and saw_violation  # both branches exercised -> H_haz truly tested

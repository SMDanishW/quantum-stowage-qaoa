"""QUBO encodings of a stowage :class:`Instance` into a ``dimod`` BQM (Phase 2).

One interface, two encodings. T2.2 delivers the shared skeleton
(:class:`PenaltyReport`, :class:`EncodingBuild`, the registry) and the one-hot
encoding; T2.3 appends the domain-wall encoding to the same module.

Formulation math and penalty-weight lemma: ``docs/specs/phase2-spec.md`` §3, D11.
Moment bounds are deliberately NOT encoded (D9) — they stay a post-hoc
``check_feasibility`` gate. Decoders never repair infeasibility (D13): an
unreadable register decodes to the sentinel slot ``-1``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import combinations

import dimod
from pydantic import BaseModel, ConfigDict

from stowage.feasibility import Assignment
from stowage.instances import Instance
from stowage.ship import Ship, brt_to_slot, slot_to_brt

logger = logging.getLogger(__name__)

Sample = Mapping[str, int]  # dimod sample: variable label -> {0, 1}
DecodeFn = Callable[[Sample], Assignment]  # NEVER repairs; sentinel slot -1 on bad register

SENTINEL = -1  # D13: unreadable register -> out-of-range slot -> assignment_valid=False


class PenaltyReport(BaseModel):
    """Logged penalty-weight / energy-scale summary for one built BQM (D11, D14)."""

    model_config = ConfigDict(frozen=True)

    encoding: str
    n_containers: int
    n_slots: int
    n_variables: int
    f_max: int
    weights: dict[str, float]
    n_quadratic_terms: int
    max_abs_objective_coeff: float
    energy_scale_ratio: float


@dataclass(frozen=True)
class EncodingBuild:
    """Contract returned by every ``Encoding.build`` (spec §5)."""

    bqm: dimod.BinaryQuadraticModel
    decode: DecodeFn
    penalty_report: PenaltyReport


# --------------------------------------------------------------------------- #
# geometry helpers (pure functions of the ship grid)
# --------------------------------------------------------------------------- #
def _stackpairs(ship: Ship) -> list[tuple[int, int]]:
    """All (u, v) with same bay & row and tier(u) > tier(v) (D3 stack ordering)."""
    pairs: list[tuple[int, int]] = []
    for u in range(ship.n_slots):
        bu, ru, tu = slot_to_brt(ship, u)
        for v in range(ship.n_slots):
            bv, rv, tv = slot_to_brt(ship, v)
            if bu == bv and ru == rv and tu > tv:
                pairs.append((u, v))
    return pairs


def _below(ship: Ship, u: int) -> int:
    """Slot one tier down in the same stack (defined for tier(u) > 0)."""
    bay, row, tier = slot_to_brt(ship, u)
    return brt_to_slot(ship, bay, row, tier - 1)


def _adjacent_slot_pairs(ship: Ship) -> list[tuple[int, int]]:
    """Unordered slot pairs {s, s'} at Manhattan distance 1 in (bay, row, tier) (D5)."""
    pairs: list[tuple[int, int]] = []
    for s, sp in combinations(range(ship.n_slots), 2):
        bs, rs, ts = slot_to_brt(ship, s)
        bp, rp, tp = slot_to_brt(ship, sp)
        if abs(bs - bp) + abs(rs - rp) + abs(ts - tp) == 1:
            pairs.append((s, sp))
    return pairs


def _var(cid: str, s: int) -> str:
    """One-hot variable label x_{cid,s} (e.g. ``x_C3_7``)."""
    return f"x_{cid}_{s}"


# --------------------------------------------------------------------------- #
# one-hot encoding (T2.2)
# --------------------------------------------------------------------------- #
class OneHotEncoding:
    """One binary ``x_{c,s}`` per container-slot pair (spec §3)."""

    name = "onehot"

    def build(self, instance: Instance) -> EncodingBuild:
        ship = instance.ship
        containers = instance.containers
        n = len(containers)
        n_slots = ship.n_slots
        cids = [c.id for c in containers]

        f_max = n * (n - 1) // 2
        weight_a = float((n + 1) * (f_max + 1))
        p_sup = float(f_max + 1)
        p_haz = float(f_max + 1)

        order = {p: i for i, p in enumerate(instance.port_rotation)}
        dest_order = {c.id: order[c.destination] for c in containers}

        bqm = dimod.BinaryQuadraticModel(dimod.BINARY)
        # register every variable so len(bqm.variables) == n*S regardless of biases
        for cid in cids:
            for s in range(n_slots):
                bqm.add_variable(_var(cid, s), 0.0)

        stackpairs = _stackpairs(ship)
        adj_pairs = _adjacent_slot_pairs(ship)

        # H_obj: overstow pairwise terms (+1 each) — hi above lo, hi discharged later than lo
        for a, b in combinations(cids, 2):
            for hi, lo in ((a, b), (b, a)):
                if dest_order[hi] > dest_order[lo]:
                    for u, v in stackpairs:
                        bqm.add_quadratic(_var(hi, u), _var(lo, v), 1.0)

        # H_cont = A * sum_c (sum_s x_{c,s} - 1)^2 ; constant A*n -> offset
        for cid in cids:
            for s in range(n_slots):
                bqm.add_linear(_var(cid, s), -weight_a)
            for s, sp in combinations(range(n_slots), 2):
                bqm.add_quadratic(_var(cid, s), _var(cid, sp), 2.0 * weight_a)
        bqm.offset += weight_a * n

        # H_slot = A * sum_s sum_{c<c'} x_{c,s} x_{c',s}
        for s in range(n_slots):
            for c, cp in combinations(cids, 2):
                bqm.add_quadratic(_var(c, s), _var(cp, s), weight_a)

        # H_sup = P_sup * sum_{tier(u)>0} [ sum_c x_{c,u}
        #                                   - sum_c sum_{c'} x_{c,u} x_{c',below(u)} ]
        for u in range(n_slots):
            _, _, tier = slot_to_brt(ship, u)
            if tier == 0:
                continue
            below = _below(ship, u)
            for cid in cids:
                bqm.add_linear(_var(cid, u), p_sup)
            for c in cids:
                for cp in cids:
                    bqm.add_quadratic(_var(c, u), _var(cp, below), -p_sup)

        # H_haz = P_haz * sum_{haz pairs} sum_{adj(s,s')} (x_{a,s}x_{b,s'} + x_{a,s'}x_{b,s})
        haz_ids = [c.id for c in containers if c.hazmat_class is not None]
        for a, b in combinations(haz_ids, 2):
            for s, sp in adj_pairs:
                bqm.add_quadratic(_var(a, s), _var(b, sp), p_haz)
                bqm.add_quadratic(_var(a, sp), _var(b, s), p_haz)

        weights = {"A": weight_a, "P_sup": p_sup, "P_haz": p_haz}
        report = PenaltyReport(
            encoding=self.name,
            n_containers=n,
            n_slots=n_slots,
            n_variables=len(bqm.variables),
            f_max=f_max,
            weights=weights,
            n_quadratic_terms=len(bqm.quadratic),
            max_abs_objective_coeff=1.0,  # H_obj coefficients are +1 by construction
            energy_scale_ratio=max(weights.values()) / 1.0,
        )
        logger.info(report.model_dump_json())

        decode = _make_onehot_decoder(cids, n_slots)
        return EncodingBuild(bqm=bqm, decode=decode, penalty_report=report)

    def encode_assignment(self, instance: Instance, assignment: Assignment) -> dict[str, int]:
        """Map a Phase 1 assignment to a one-hot sample over all n*S variables."""
        n_slots = instance.ship.n_slots
        sample: dict[str, int] = {}
        for c in instance.containers:
            slot = assignment[c.id]
            for s in range(n_slots):
                sample[_var(c.id, s)] = 1 if s == slot else 0
        return sample


def _make_onehot_decoder(cids: list[str], n_slots: int) -> DecodeFn:
    """Decoder closure: popcount-1 register -> that slot; otherwise sentinel -1 (D13)."""

    def decode(sample: Sample) -> Assignment:
        assignment: Assignment = {}
        for cid in cids:
            hot = [s for s in range(n_slots) if int(sample[_var(cid, s)]) == 1]
            assignment[cid] = hot[0] if len(hot) == 1 else SENTINEL
        return assignment

    return decode


ENCODINGS: dict[str, OneHotEncoding] = {
    "onehot": OneHotEncoding(),
}

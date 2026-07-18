"""T1.1 tests for the Instance schema and JSON round-trip / byte-stability."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from stowage.instances import Instance, load_instance, save_instance
from stowage.ship import Container, Ship


def _instance() -> Instance:
    ship = Ship(n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=40.0, max_transverse_moment=2.0)
    containers = (
        Container(id="C1", weight=10.0, destination="P3"),
        Container(id="C2", weight=8.0, destination="P1"),
        Container(id="C3", weight=6.0, destination="P2", hazmat_class=3),
    )
    return Instance(
        name="stow_c3_p3_s7",
        ship=ship,
        containers=containers,
        port_rotation=("P1", "P2", "P3"),
        seed=7,
        generator_params={"hazmat_fraction": 0.15, "n_ports": 3},
    )


def test_json_round_trip_equality(tmp_path: Path) -> None:
    inst = _instance()
    path = tmp_path / "inst.json"
    save_instance(inst, path)
    assert load_instance(path) == inst


def test_json_byte_stable(tmp_path: Path) -> None:
    inst = _instance()
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    save_instance(inst, a)
    save_instance(load_instance(a), b)
    assert a.read_bytes() == b.read_bytes()


def test_duplicate_container_ids_rejected() -> None:
    ship = Ship(n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=40.0, max_transverse_moment=2.0)
    with pytest.raises(ValidationError):
        Instance(
            name="dup",
            ship=ship,
            containers=(
                Container(id="C1", weight=10.0, destination="P1"),
                Container(id="C1", weight=8.0, destination="P1"),
            ),
            port_rotation=("P1",),
            seed=0,
        )


def test_unknown_destination_rejected() -> None:
    ship = Ship(n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=40.0, max_transverse_moment=2.0)
    with pytest.raises(ValidationError):
        Instance(
            name="bad_dest",
            ship=ship,
            containers=(Container(id="C1", weight=10.0, destination="P9"),),
            port_rotation=("P1", "P2"),
            seed=0,
        )


def test_duplicate_port_rotation_rejected() -> None:
    ship = Ship(n_bays=1, n_rows=2, n_tiers=3, max_vertical_moment=40.0, max_transverse_moment=2.0)
    with pytest.raises(ValidationError):
        Instance(
            name="dup_ports",
            ship=ship,
            containers=(Container(id="C1", weight=10.0, destination="P1"),),
            port_rotation=("P1", "P1"),
            seed=0,
        )

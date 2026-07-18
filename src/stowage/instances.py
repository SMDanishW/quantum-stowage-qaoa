"""Instance schema and JSON I/O (Phase 1).

T1.1 delivers the ``Instance`` model plus byte-stable save/load. The seeded
``generate_instance`` generator is T1.3.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from stowage.ship import Container, Ship


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


def save_instance(instance: Instance, path: Path) -> None:
    """Serialize to JSON with sorted keys, indent=2, ``\\n`` newlines (byte-stable)."""
    text = json.dumps(instance.model_dump(), indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def load_instance(path: Path) -> Instance:
    """Deserialize an Instance from JSON produced by :func:`save_instance`."""
    return Instance.model_validate_json(path.read_text(encoding="utf-8"))

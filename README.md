# stowage-qaoa

QAOA demonstrator for container-to-slot assignment on a simplified bay-row-tier ship model.

## Scope (honest)

The scientific contribution is an **encoding and NISQ-scaling analysis** — comparing one-hot
vs domain-wall QUBO encodings, circuit depth, and barren-plateau behaviour. This project does
**not** aim to beat classical solvers, and quantum-solved instances are kept deliberately small
(10–20 containers, simulator only). Instances are generated (real stowage plans are commercially
confidential), matching standard practice in the literature.

## Quickstart

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run mypy src
```

See `CLAUDE.md` for the full spec and `TICKETS.md` for the work plan.

# CLAUDE.md — Container Stowage Planning via QAOA

QAOA demonstrator for container-to-slot assignment on a simplified bay-row-tier ship model, with a rigorous analysis of encoding choices (one-hot vs domain-wall), circuit depth, and NISQ scaling. Thesis-aligned (maritime). The scientific contribution is the encoding/scaling analysis — NOT beating classical solvers, and every doc says so honestly.

## What we're building
- Constraints: weight distribution (vertical/transverse moment bounds), destination ordering (minimize overstowage/re-handles), hazmat separation. One binary variable per container-slot pair (one-hot) plus a domain-wall alternative encoding.
- Solvers: QAOA (p=1..5) with three parameter strategies — COBYLA from scratch, layer-wise training, parameter transfer from smaller instances. Comparators: simulated annealing, constructive heuristic, brute force on toys.
- Instance generator IS the dataset (real stowage plans are commercially confidential — by design, no public data; this matches the literature's practice).
- Visualization: 3D stowage rendering in notebooks (Plotly) — **no web frontend for this project.**

## Stack
- Python 3.12 + uv. Core: `qiskit`, `qiskit-aer`, `qiskit-algorithms`, `pennylane` (cross-check), `dimod`, `dwave-neal`, `numpy`, `scipy`, `pydantic`, `plotly`. pytest, ruff, mypy.
- Repo: `src/stowage/` (ship model, instances, encodings, qaoa, baselines) · `experiments/` · `notebooks/` (analysis + 3D viz only, no logic) · `docs/` · `tests/`.

## Conventions
- Keep quantum-solved instances honest: 10–20 containers max, stated everywhere. Qubit-count guard refuses > ~26 qubits on statevector sim.
- Encodings implement a common interface `Encoding.build(instance) -> (BQM, decode_fn)` so QAOA/SA run identically over both.
- Every decoded sample → independent `check_feasibility`; report feasibility rate, never single best-of.
- Barren-plateau evidence: log gradient variance vs depth during training (this is a deliverable, not debug info).
- Seeds mandatory; parameter-transfer experiments must record donor-instance identity.
- No hardware runs planned; if added later, same `[HW]` discipline as other projects.

## Commands
- `uv run pytest` · `uv run ruff check . && uv run mypy src`
- `uv run python -m stowage.cli generate --containers 12 --ports 3 --seed 7`
- `uv run python -m stowage.cli solve <instance> --method qaoa --encoding onehot|domainwall --p 2 --strategy cobyla|layerwise|transfer --seed N`

## Agents & workflow
Subagents in `.claude/agents/`; loop and gates per WORKFLOW.md; status in TICKETS.md; reviewer runs qa-security-checklist.md (§5 quantum + §3 scientific-integrity are the hot sections — this project lives or dies on honest reporting).

## ⛔ Fable 5 checkpoint (token budget — MANDATORY)
`architect` and `reviewer` run on claude-fable-5 (expensive). NEVER invoke a Fable-5 subagent silently. Before any such call:
1. STOP and print exactly:
   > ⛔ **FABLE 5 CHECKPOINT** — `<architect|reviewer>` needed for <ticket/step>: <one-line reason>. Reply: **fable** (proceed) / **opus** (downgrade this call) / **defer**.
2. Wait for the user's reply. **opus** → invoke the same subagent with model overridden to claude-opus-4-8. **defer** → note it in TICKETS.md and continue other work.
3. Default recommendation per call: routine reviews (scaffolding, docs, frontend polish, config) → suggest **opus**; QUBO/math formulations, statistical protocol, artifact-schema contracts, secret/API-key-handling code → suggest **fable**.

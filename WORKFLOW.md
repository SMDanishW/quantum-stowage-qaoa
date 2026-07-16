# Workflow — Agents, Skills & MCPs

How every project session is set up and how every phase runs. Same workflow for all five projects; only the CLAUDE.md/TICKETS.md content differs.

---

## 0. One-time setup (before the five sessions)

1. Create one Git repo per project (`berth-allocation-quantum`, `stowage-qaoa`, `quantum-kernel-benchmark`, `district-heating-qubo`, `ais-anomaly-hybrid`).
2. Copy into each repo root:
   - the project's `CLAUDE.md` and `TICKETS.md`
   - `qa-security-checklist.md`
   - `.claude/agents/` (all four agent files)
3. Alternatively, put the four agent files in `~/.claude/agents/` once — they are then available in every project. Project-scope copies win on name collision, so keep them in ONE place to avoid drift.
4. Create `.env` from `.env.example` and add the tokens each project needs (see its CLAUDE.md). Never commit `.env`.
5. Optional but recommended: `claude` → `/init` in each repo lets Claude Code fold repo-discovered details into CLAUDE.md; review the diff, keep our structure.

### Agent roster (all projects)

| Agent | Model | Role | Write access |
|---|---|---|---|
| architect | claude-fable-5 | Phase specs, formulations, interfaces | none (read-only) |
| implementer | claude-opus-4-8 | One ticket at a time, code + tests | full |
| reviewer | claude-fable-5 | Diff review + qa-security-checklist.md | none (Bash for tests only) |
| scribe | claude-sonnet-4-6 | TICKETS status, CHANGELOG, docs, experiment log | docs only by convention |

> Note: agent `model:` fields use full model strings. If Anthropic ships newer point releases, update the four agent files in one place. ("Sonnet 5" does not exist as of July 2026 — Sonnet 4.6 is current; the scribe uses it.)

### MCP servers (install per project where marked)

| MCP | Projects | Why |
|---|---|---|
| GitHub MCP (`github`) | all | PR creation, issue mirroring of tickets, CI status from inside the session |
| Playwright MCP | 1, 4, 5 | Reviewer drives the running Next.js app: loads the page, checks the canvas/map renders, screenshots for the done report |
| Context7 (or equivalent docs MCP) | all | Up-to-date library docs for fast-moving deps (Qiskit 2.x, PennyLane, dimod/dwave-ocean, react-three-fiber, deck.gl) — reduces hallucinated APIs |

Add with `claude mcp add <name> ...` per each server's install instructions, or in `.mcp.json` at repo root so the config is committed and identical across your machines. Verify with `/mcp` at session start.

### Skills

- `frontend-design` (projects 1, 4, 5): load when building the Next.js UI so the digital twin/dashboards don't look like default Tailwind.
- Consider writing one tiny project skill `qubo-conventions` shared by projects 1, 2, 4 (variable naming, penalty-weight logging format, feasibility-check contract). Preload it into architect/implementer via the `skills:` frontmatter field once written.

### Session-start checklist (every session, 60 seconds)
```
/mcp                      # servers connected?
/agents                   # four agents listed?
"Read CLAUDE.md and TICKETS.md, tell me the current phase and next open ticket."
```

---

## 1. The phase loop

Every phase in every TICKETS.md runs the same five-step loop. The main thread orchestrates; you approve at the two gates.

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE N                                                     │
│                                                             │
│  1. PLAN      architect → Phase Spec            [GATE: you] │
│  2. BUILD     implementer → one ticket/branch    ┐          │
│  3. REVIEW    reviewer → verdict + checklist     │ repeat   │
│       └─ REQUEST CHANGES → back to 2 (same ticket)          │
│       └─ 2× REQUEST CHANGES → back to 1 (architect)         │
│  4. RECORD    scribe → TICKETS/CHANGELOG/experiments        │
│  5. CLOSE     scribe phase summary + you demo it [GATE: you]│
└─────────────────────────────────────────────────────────────┘
```

**Step 1 — Plan.** Prompt: `Use the architect subagent to produce the Phase N spec.` Read the spec yourself. This is the highest-leverage 10 minutes of the phase — a wrong interface here costs every downstream ticket. Approve or push back, then have the scribe persist it to `docs/specs/`.

**Step 2 — Build.** Prompt: `Use the implementer subagent on ticket T<N>.<M>.` One ticket per invocation, always on its own branch. Never let it batch tickets — batching is how spec drift sneaks in.

**Step 3 — Review.** Prompt: `Use the reviewer subagent on branch ticket/T<N>.<M>-....` The reviewer independently reruns tests and walks qa-security-checklist.md. On APPROVE, merge (via GitHub MCP PR or locally). On REQUEST CHANGES, feed the blocking findings verbatim back to the implementer on the same branch.

**Step 4 — Record.** Prompt: `Use the scribe subagent to record ticket T<N>.<M>.` Cheap (Sonnet), runs after every merge, keeps TICKETS.md the single source of truth on status.

**Step 5 — Close.** When all phase tickets are DONE: scribe writes the phase summary; you personally run the demo command listed in the phase's Definition of Done. If it doesn't run on your machine from a clean state, the phase isn't closed.

### Rules that keep this sane
- **Fresh context per step.** Subagents already isolate context; additionally `/clear` the main thread between phases. TICKETS.md status is the state — not the conversation history.
- **You are the merge button.** Agents recommend; only you merge and only you approve spec gates.
- **Escalation path is explicit.** Implementer blocked by spec → architect. Reviewer rejects twice → architect. Architect uncertain → smallest possible spike ticket, then re-spec.
- **Parallelism:** across the five projects, run sessions freely in parallel. Inside one project, keep tickets sequential within a phase unless TICKETS.md marks them `[P]` (parallel-safe) — those touch disjoint files by design.
- **Hardware budget discipline:** D-Wave Leap free minutes and IBM open-plan queue time are consumed only in tickets explicitly marked `[HW]`, always after the simulator version is merged.

---

## 2. Phase-type presets

Which agents/tools matter most per phase type (all five projects follow this pattern):

| Phase type | Heavy agent | Extras |
|---|---|---|
| 0 Scaffolding | implementer | GitHub MCP (repo, CI), no architect needed — spec is CLAUDE.md itself |
| Data pipeline | architect (schemas!) → implementer | Context7 for API client libs; checklist §4 |
| Formulation/QUBO | architect (math) → implementer | reviewer checks math symbol-by-symbol; checklist §5 |
| Solvers/experiments | implementer | seeds + experiment log discipline; `[HW]` tickets last; checklist §3+§5 |
| Frontend | architect (artifact schema) → implementer | frontend-design skill, Playwright MCP for review; checklist §6 |
| Docs/release | scribe leads | reviewer runs checklist §7 on the whole repo |

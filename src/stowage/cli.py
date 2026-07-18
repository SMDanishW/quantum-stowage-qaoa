"""Command-line interface (Phase 1: ``generate``; ``solve`` is Phase 3).

    python -m stowage.cli generate --containers 12 --ports 3 --seed 7 \
        [--hazmat-fraction 0.15] [--weight-min 5 --weight-max 30] [--toy] [--out instances/]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from stowage.baselines import brute_force_optimum, save_optimum
from stowage.instances import generate_instance, save_instance


def _cmd_generate(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    instance = generate_instance(
        n_containers=args.containers,
        n_ports=args.ports,
        seed=args.seed,
        weight_range=(args.weight_min, args.weight_max),
        hazmat_fraction=args.hazmat_fraction,
        toy=args.toy,
    )
    inst_path = out_dir / f"{instance.name}.json"
    save_instance(instance, inst_path)
    print(inst_path)

    if args.toy:
        record = brute_force_optimum(instance)
        opt_path = out_dir / f"{instance.name}.optimum.json"
        save_optimum(record, opt_path)
        print(opt_path)
        print(f"optimum_objective={record.optimal_objective}")
    return 0


def _cmd_solve(args: argparse.Namespace) -> int:
    raise NotImplementedError("`solve` is delivered in Phase 3 (T3.x); not available yet")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stowage")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate a stowage instance")
    gen.add_argument("--containers", type=int, required=True)
    gen.add_argument("--ports", type=int, required=True)
    gen.add_argument("--seed", type=int, required=True)
    gen.add_argument("--hazmat-fraction", type=float, default=0.15, dest="hazmat_fraction")
    gen.add_argument("--weight-min", type=float, default=5.0, dest="weight_min")
    gen.add_argument("--weight-max", type=float, default=30.0, dest="weight_max")
    gen.add_argument("--toy", action="store_true")
    gen.add_argument("--out", default="instances")
    gen.set_defaults(func=_cmd_generate)

    slv = sub.add_parser("solve", help="(Phase 3) solve an instance")
    slv.add_argument("instance", nargs="?")
    slv.set_defaults(func=_cmd_solve)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

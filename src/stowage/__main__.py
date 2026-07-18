"""Enable ``python -m stowage``."""

from __future__ import annotations

from stowage.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

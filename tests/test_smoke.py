"""Placeholder smoke test: the package imports and exposes a version."""

import stowage


def test_import_and_version() -> None:
    assert stowage.__version__ == "0.0.0"

"""Smoke tests: prove the package and all subpackages import cleanly.

These exist primarily so CI has something to collect (pytest exits with code 5
on an empty test suite, which we treat as a failure). They also catch the
class of bug where a refactor breaks import paths.
"""

import importlib


def test_baymax_package_imports() -> None:
    """The top-level package is importable."""
    import baymax

    assert baymax is not None


def test_all_subpackages_importable() -> None:
    """Every declared subpackage imports without error.

    If a refactor renames or moves a subpackage without updating this list,
    CI fails — keeping the layout claim in README honest.
    """
    expected_subpackages = [
        "baymax.core",
        "baymax.tools",
        "baymax.models",
        "baymax.eval",
        "baymax.service",
        "baymax.telemetry",
    ]
    for name in expected_subpackages:
        module = importlib.import_module(name)
        assert module is not None, f"{name} imported as None"

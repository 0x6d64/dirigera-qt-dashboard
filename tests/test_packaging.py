"""Packaging: every top-level module is listed in pyproject.toml (t-96)."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Scripts that are run from a checkout and are not part of the package.
SCRIPTS = {"generate_token"}


def test_every_top_level_module_is_in_py_modules() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    listed = set(config["tool"]["setuptools"]["py-modules"])
    present = {p.stem for p in ROOT.glob("*.py")} - SCRIPTS
    assert present == listed

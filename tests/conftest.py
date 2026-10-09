"""Isolate test files from directories created by other Windows execution contexts."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    if config.option.basetemp is not None:
        return  # Honor an explicit --basetemp, including pytest's documented cleanup behavior.
    workspace = config.rootpath.resolve()
    session = TemporaryDirectory(prefix=".pytest-run-", dir=workspace)
    directory = Path(session.name).resolve()
    if directory.parent != workspace or not directory.name.startswith(".pytest-run-"):
        raise pytest.UsageError("Test temporary directory must remain inside the repository")
    # This fresh child does not exist yet; pytest cannot delete a prior run's directory.
    config.option.basetemp = str(directory / "tmp")
    # TemporaryDirectory cleans only the newly allocated, verified session directory.
    config.add_cleanup(session.cleanup)

"""Keep each Windows pytest run in its own writable directory; preserve prior runs."""
from pathlib import Path
from uuid import uuid4


def pytest_configure(config):
    if config.option.basetemp is None:
        config.option.basetemp = str(
            Path(config.rootpath) / "generated" / ("pytest-" + uuid4().hex)
        )

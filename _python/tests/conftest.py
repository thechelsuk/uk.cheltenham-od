"""Make the _python scripts importable from the tests (they import each other
as top-level modules, e.g. `import helper`), and keep every test offline."""
import pathlib
import socket
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail any test that tries to open a network connection, so a fetcher
    whose fetch wasn't faked can't quietly hit a live API."""
    def refuse(*args, **kwargs):
        raise RuntimeError("tests must not use the network; fake the fetch instead")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

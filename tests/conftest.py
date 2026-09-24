# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures.

Constitution Art. XII.2: tests never consume real API quota. The ``no_network`` guard
makes any attempt to open a socket to a non-local host fail loudly, so a test that
accidentally reaches Google (or anywhere else) is a red test, not a silent bill.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator

import pytest

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail any socket connection that is not to localhost."""

    real_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: object) -> None:
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in _LOCAL_HOSTS:
            raise RuntimeError(f"network access is disabled in tests (tried {host!r})")
        real_connect(self, address)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield

# SPDX-License-Identifier: Apache-2.0
"""Scaffold sanity: the package imports and the network guard is active."""

from __future__ import annotations

import socket

import pytest

import lenguaraz


def test_version() -> None:
    assert lenguaraz.__version__ == "1.0.0"


def test_network_guard_blocks_remote_hosts() -> None:
    with pytest.raises(RuntimeError, match="network access is disabled"), socket.socket() as sock:
        sock.connect(("generativelanguage.googleapis.com", 443))

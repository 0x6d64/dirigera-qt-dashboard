"""A finished or failed command makes the next refresh redraw (t-100)."""

from collections.abc import Callable
from typing import Any

import pytest
from conftest import StubHub, make_device

import workers

Wait = Callable[..., None]


@pytest.fixture
def connected(
    window: Any, monkeypatch: pytest.MonkeyPatch, wait_until: Wait
) -> tuple[Any, StubHub]:
    hub = StubHub(devices=[make_device("light", "l1", "Lamp", is_on=True)])
    monkeypatch.setattr(workers, "Hub", lambda token, ip_address: hub)
    window.connection_block.ip_input.setText("10.0.0.2")
    window.connection_block.token_input.setText("tok")
    window.connect_to_hub()
    wait_until(lambda: window.hub is not None and window._refresh_worker is None)
    return window, hub


@pytest.mark.parametrize("fails", [False, True])
def test_command_end_forces_the_next_refresh_to_redraw(
    connected: tuple[Any, StubHub], wait_until: Wait, fails: bool
) -> None:
    window, _ = connected
    assert window._signature is not None
    card = window._room_sections[0][1].cards()[0]

    def command() -> None:
        if fails:
            raise RuntimeError("no")

    worker = window.run_device_command(card, command, "do it")
    wait_until(lambda: window._signature is None)
    worker.wait(5000)
    window.refresh_devices()
    wait_until(lambda: window._refresh_worker is None)
    assert window._signature is not None  # the unchanged data was applied again

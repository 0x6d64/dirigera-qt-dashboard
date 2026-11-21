"""Hub event listener: message parsing and the worker around the library (t-16)."""

import json
import threading
from collections.abc import Callable
from typing import Any

import pytest

from workers import EventWorker, parse_event

Wait = Callable[..., None]


# --- parse_event --------------------------------------------------------------


def test_parse_event_accepts_a_json_object_with_a_type() -> None:
    message = json.dumps({"type": "deviceStateChanged", "data": {"id": "d1"}})
    assert parse_event(message) == {"type": "deviceStateChanged", "data": {"id": "d1"}}
    assert parse_event(message.encode()) is not None


@pytest.mark.parametrize(
    "message",
    ["not json", "", "[1, 2]", '"text"', '{"no": "type"}', '{"type": 3}', None, 7],
)
def test_parse_event_rejects_everything_else(message: Any) -> None:
    assert parse_event(message) is None


def test_parse_event_survives_bad_bytes() -> None:
    assert parse_event(b"\xff\xfe{") is None


# --- EventWorker --------------------------------------------------------------


class FakeListenerHub:
    """A hub whose listener replays a script, then blocks until stopped."""

    def __init__(self, script: list[Any] | None = None, block: bool = True) -> None:
        self.script = script or []
        self.block = block
        self.stopped = threading.Event()
        self.started = threading.Event()
        self.stop_calls = 0
        self.kwargs: dict[str, Any] = {}
        self.raise_on_start: Exception | None = None

    def create_event_listener(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.started.set()
        if self.raise_on_start is not None:
            raise self.raise_on_start
        kwargs["on_open"](None)
        for step in self.script:
            if callable(step):
                step(kwargs)
            else:
                kwargs["on_message"](None, step)
        if self.block:
            self.stopped.wait(5)

    def stop_event_listener(self) -> None:
        self.stop_calls += 1
        self.stopped.set()


def _worker(hub: FakeListenerHub) -> EventWorker:
    return EventWorker(hub)  # type: ignore[arg-type]


def _collect(worker: EventWorker) -> dict[str, list[Any]]:
    seen: dict[str, list[Any]] = {"opened": [], "event": [], "lost": []}
    worker.opened.connect(lambda: seen["opened"].append(True))
    worker.received.connect(lambda e: seen["event"].append(e))
    worker.lost.connect(lambda: seen["lost"].append(True))
    return seen


def test_worker_reports_open_and_parsed_events(qapp: Any, wait_until: Wait) -> None:
    hub = FakeListenerHub(
        [
            json.dumps({"type": "deviceStateChanged", "data": {"id": "d1"}}),
            "garbage",
            json.dumps({"type": "deviceAdded"}),
        ]
    )
    worker = _worker(hub)
    seen = _collect(worker)
    worker.start()
    wait_until(lambda: len(seen["event"]) == 2)
    assert seen["opened"] == [True]
    assert [e["type"] for e in seen["event"]] == ["deviceStateChanged", "deviceAdded"]
    assert seen["lost"] == []  # a garbage message is not a lost socket
    worker.request_stop()
    wait_until(worker.isFinished)
    assert seen["lost"] == []  # a requested stop is not a loss


def test_worker_asks_the_library_to_reconnect(qapp: Any, wait_until: Wait) -> None:
    hub = FakeListenerHub()
    worker = _worker(hub)
    worker.start()
    wait_until(hub.started.is_set)
    assert hub.kwargs["reconnect"] == 5
    worker.request_stop()
    wait_until(worker.isFinished)


def test_close_and_error_callbacks_emit_lost(qapp: Any, wait_until: Wait) -> None:
    hub = FakeListenerHub(
        [
            lambda kw: kw["on_close"](None, 1000, "bye"),
            lambda kw: kw["on_error"](None, "x"),
        ]
    )
    worker = _worker(hub)
    seen = _collect(worker)
    worker.start()
    wait_until(lambda: len(seen["lost"]) == 2)
    worker.request_stop()
    wait_until(worker.isFinished)


def test_listener_that_ends_by_itself_is_reported_lost(
    qapp: Any, wait_until: Wait
) -> None:
    worker = _worker(FakeListenerHub(block=False))
    seen = _collect(worker)
    worker.start()
    wait_until(worker.isFinished)
    assert seen["lost"] == [True]


def test_a_failing_listener_is_reported_lost(qapp: Any, wait_until: Wait) -> None:
    hub = FakeListenerHub()
    hub.raise_on_start = RuntimeError("socket refused")
    worker = _worker(hub)
    seen = _collect(worker)
    worker.start()
    wait_until(worker.isFinished)
    assert seen["lost"] == [True]


def test_stop_before_the_thread_runs_ends_it_at_once(
    qapp: Any, wait_until: Wait
) -> None:
    hub = FakeListenerHub()
    worker = _worker(hub)
    seen = _collect(worker)
    worker.request_stop()
    worker.start()
    wait_until(worker.isFinished)
    assert not hub.started.is_set()
    assert seen == {"opened": [], "event": [], "lost": []}


def test_stop_that_beat_the_socket_closes_it_on_open(qapp: Any) -> None:
    hub = FakeListenerHub()
    worker = _worker(hub)
    seen = _collect(worker)
    worker._stop.set()  # the stop arrived after run() checked, before the socket
    worker._on_open(None)
    assert hub.stop_calls == 1
    assert seen["opened"] == []


def test_events_after_a_stop_are_dropped(qapp: Any) -> None:
    worker = _worker(FakeListenerHub())
    seen = _collect(worker)
    worker.request_stop()
    worker._on_message(None, json.dumps({"type": "deviceStateChanged"}))
    worker._on_lost()
    assert seen == {"opened": [], "event": [], "lost": []}


def test_request_stop_never_raises_and_can_repeat(qapp: Any) -> None:
    hub = FakeListenerHub()

    def boom() -> None:
        raise RuntimeError("closed twice")

    hub.stop_event_listener = boom  # type: ignore[method-assign]
    worker = _worker(hub)
    worker.request_stop()
    worker.request_stop()
    assert worker.stop_requested()

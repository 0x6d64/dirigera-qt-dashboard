"""LabeledSlider commit semantics (req-6): one command per user intent."""

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from widgets.slider import COMMIT_DELAY_MS, LabeledSlider


def _slider(qapp: QApplication) -> tuple[LabeledSlider, list[int]]:
    s = LabeledSlider(initial_value=50)
    sent: list[int] = []
    s.committed.connect(sent.append)
    s.show()
    return s, sent


def test_key_presses_coalesce_into_one_commit(
    qapp: QApplication, wait_until: Callable[..., None]
) -> None:
    s, sent = _slider(qapp)
    s._slider.setFocus()
    for _ in range(3):
        QTest.keyClick(s._slider, Qt.Key.Key_Right)  # type: ignore[call-overload]
    assert sent == []  # nothing before the pause
    wait_until(lambda: sent == [53])


def test_drag_commits_once_on_release(
    qapp: QApplication, pump: Callable[[int], None]
) -> None:
    s, sent = _slider(qapp)
    s._slider.setSliderDown(True)
    s._slider.setValue(70)
    pump(COMMIT_DELAY_MS + 100)
    assert sent == []
    s._slider.setSliderDown(False)
    assert sent == [70]


def test_release_without_change_sends_nothing(qapp: QApplication) -> None:
    s, sent = _slider(qapp)
    s._slider.setSliderDown(True)
    s._slider.setSliderDown(False)
    assert sent == []


def test_set_value_never_commits(
    qapp: QApplication, pump: Callable[[int], None]
) -> None:
    s, sent = _slider(qapp)
    s.set_value(10)
    pump(COMMIT_DELAY_MS + 100)
    assert sent == []
    assert s.value() == 10

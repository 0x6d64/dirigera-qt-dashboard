"""LabeledSlider commit semantics (req-6): one command per user intent."""

from collections.abc import Callable

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QSlider

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


def _wheel(target: QSlider) -> QWheelEvent:
    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(target, event)
    return event


def test_wheel_is_ignored_without_focus(qapp: QApplication) -> None:
    s, sent = _slider(qapp)
    assert s._slider.focusPolicy() == Qt.FocusPolicy.StrongFocus
    s._slider.clearFocus()
    assert not s._slider.hasFocus()
    event = _wheel(s._slider)
    assert not event.isAccepted()  # the scroll area gets it
    assert s.value() == 50
    assert sent == []


def test_wheel_moves_a_focused_slider(
    qapp: QApplication, wait_until: Callable[..., None]
) -> None:
    s, sent = _slider(qapp)
    s.activateWindow()
    s._slider.setFocus()
    wait_until(s._slider.hasFocus)
    _wheel(s._slider)
    assert s.value() > 50
    wait_until(lambda: sent == [s.value()])

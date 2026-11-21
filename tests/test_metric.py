"""Metric layout: unit and note follow the number, aligned to its bottom."""

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout

from widgets.metric import MetricWidget


def _row(metric: MetricWidget) -> QHBoxLayout:
    row = metric._value_label.parentWidget().layout()
    assert isinstance(row, QHBoxLayout)
    return row


def test_unit_and_note_follow_the_value(qapp: Any) -> None:
    metric = MetricWidget("PM2.5", 7, "µg/m³")
    metric.set_note("Good", "ok")
    row = _row(metric)
    items = [row.itemAt(i) for i in range(3)]
    widgets = [item.widget() for item in items if item is not None]
    assert widgets == [metric._value_label, metric._unit_label, metric._note_label]


def test_value_reserves_no_width_before_the_unit(qapp: Any) -> None:
    metric = MetricWidget("PM2.5", 7, "µg/m³")
    assert metric._value_label.minimumWidth() == 0


def test_unit_and_note_sit_on_the_value_baseline(qapp: Any) -> None:
    metric = MetricWidget("PM2.5", 7, "µg/m³")
    row = _row(metric)
    for i in range(3):
        item = row.itemAt(i)
        assert item is not None
        assert item.alignment() & Qt.AlignmentFlag.AlignBottom
    for label in (metric._unit_label, metric._note_label):
        assert label.alignment() & Qt.AlignmentFlag.AlignBottom

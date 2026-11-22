# Qt and PyQt6 gotchas

Pitfalls reproduced while building this app (PyQt6 6.12, Fusion style, offscreen and
Windows). Add a new one here when it costs time; do not repeat these in other docs.

## Properties and selectors

1. **Never name a dynamic or `pyqtProperty` `pos`.** It collides with `QWidget.pos`:
   QSS selectors such as `[pos="first"]` do not match, and a `pyqtProperty` named
   `pos` shadows the `pos()` method. Use prefixed names (`segpos`, `thumb`).
2. **Re-polish after a property change.** After changing a property that drives a QSS
   selector, call `style().unpolish(w)` then `polish(w)`, or the new style does not
   appear.
3. **Type selectors match subclasses** (a `QLabel` is a `QFrame`). Scope rules with
   properties or object names.

## Sliders and bars

4. **Disabled sub-page rule.** `QSlider:disabled::sub-page` paints the whole groove
   grey, even when enabled, in Fusion. Colour the disabled state from a property or a
   separate rule instead.
5. **Handle clipping.** An 18 px slider handle is clipped unless the slider has a
   minimum height of 24 px.
6. **Progress bar height.** QSS `height` on `QProgressBar` does not apply; use
   `setFixedHeight` (and `setTextVisible(False)` for a plain meter).

## Effects and styling limits

7. **Not supported in QSS:** `box-shadow`, transitions, flex or grid. Avoid
   `QGraphicsDropShadowEffect` on many widgets inside scroll areas: it is costly and
   clips.
8. QtCharts is a separate package, not part of the base `PyQt6` wheel. Qt Widgets has
   no native toggle switch, segmented control or flow layout; the app has its own.

## Signals and enums

9. Prefer `toggled` or `valueChanged` (with a debounce) over comparing raw
   `stateChanged` ints to enums: enum and int values are not equal in PyQt6.
10. Resync controls with `blockSignals(True)` or a guard flag so a state update never
    sends a command.

## Testing

11. The offscreen platform prints "does not support propagateSizeHints()". Ignore it
    when asserting that no real warnings occurred.
12. `QMessageBox` static methods block; replace them in tests (see
    `tests/conftest.py`).

## Scroll areas

13. **A `QComboBox` in a scroll area takes wheel events.** A turn of the wheel
    over it changes its value instead of scrolling the page. Override
    `wheelEvent` to call `event.ignore()` (see `ProfileBox` in
    `widgets/card.py`) and use `StrongFocus` so it takes focus only on click or
    tab. A `QSlider` needs the same: `LabeledSlider` ignores the wheel until the
    slider has focus (`_FocusWheelSlider` in `widgets/slider.py`).

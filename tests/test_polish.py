"""Small design gaps: scene grid width, refresh feedback, keyboard, names."""

from widgets.grid import CardGrid
from widgets.scene import SCENE_MIN_WIDTH


def test_scene_grid_fits_more_columns_than_device_grid(qapp) -> None:
    devices = CardGrid()
    scenes = CardGrid(min_width=SCENE_MIN_WIDTH)
    for grid in (devices, scenes):
        grid.resize(800, 400)
    assert scenes.columns() > devices.columns()

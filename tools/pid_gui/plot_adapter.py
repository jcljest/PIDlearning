from __future__ import annotations

from dataclasses import dataclass

import pyqtgraph as pg


@dataclass
class PlotBundle:
    widget: pg.PlotWidget
    curves: dict[str, object]


def create_plot(title: str, x_label: str, y_label: str, curves: list[tuple[str, str]]) -> PlotBundle:
    widget = pg.PlotWidget()
    widget.setBackground("#fffdfa")
    widget.showGrid(x=True, y=True, alpha=0.18)
    widget.setTitle(title, color="#5d4930", size="14pt")
    widget.setLabel("bottom", x_label)
    widget.setLabel("left", y_label)
    widget.addLegend(offset=(12, 12))

    plot_curves: dict[str, object] = {}
    for name, color in curves:
        plot_curves[name] = widget.plot([], [], pen=pg.mkPen(color=color, width=2), name=name)

    return PlotBundle(widget=widget, curves=plot_curves)


def set_plot_data(bundle: PlotBundle, x_values: list[float], series: dict[str, list[float]]) -> None:
    for name, curve in bundle.curves.items():
        curve.setData(x_values, series.get(name, []))


def clear_plot(bundle: PlotBundle) -> None:
    set_plot_data(bundle, [], {name: [] for name in bundle.curves})

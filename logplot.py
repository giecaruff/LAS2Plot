import contextlib
import copy
import uuid

import numpy as np
from matplotlib.figure import Figure
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle
from matplotlib.ticker import (
    NullFormatter,
    MultipleLocator,
    LinearLocator,
    LogLocator,
    AutoMinorLocator,
    AutoLocator,
)

_LINEAR_TICK_LOCATORS = {
    "multiple": MultipleLocator,
    "linear": LinearLocator,
    "auto": AutoLocator,
}


@contextlib.contextmanager
def monkeypatchmethod(obj, name, method):
    original = getattr(obj, name)
    setattr(obj, name, method.__get__(obj, type(obj)))
    yield obj
    setattr(obj, name, original)


def get_starting_nans(x):
    return np.sum(np.cumsum(np.isnan(x)) == np.arange(1, len(x) + 1))


def prepare_clean_ax(ax, facecolor, edgecolor, alpha, **kwargs):
    ax.tick_params(axis="both", which="both", length=0, labelsize=0)
    ax.xaxis.set(major_formatter=NullFormatter(), minor_formatter=NullFormatter())
    ax.yaxis.set(major_formatter=NullFormatter(), minor_formatter=NullFormatter())
    ax.set_facecolor(facecolor)
    ax.set_alpha(alpha)
    for spine in ax.spines.values():
        spine.set_edgecolor(edgecolor)


def prepare_transparent_ax(ax, **kwargs):
    ax.axis("off")


_TR_TEXT_MATPLOTLIB_TEXT = {
    "font": "family",
    "style": "style",
    "variant": "variant",
    "stretch": "stretch",
    "weight": "weight",
    "size": "size",
}

_TR_LINE_MATPLOTLIB_LINE = {
    "color": "color",
    "style": "linestyle",
    "width": "linewidth",
    "alpha": "alpha",
}

_TR_MARKER_MATPLOTLIB_MARKER = {
    "color": "markerfacecolor",
    "style": "marker",
    "size": "markersize",
    "edgecolor": "markeredgecolor",
    "edgewidth": "markeredgewidth",
    "alpha": "alpha",
}

_TR_PATCH_MATPLOTLIB_PATCH = {
    "color": "facecolor",
    "hatch": "hatch",
    "alpha": "alpha",
    "hatchcolor": "edgecolor",
}


class LogPlot:
    _layer_artists = {}
    _legend_artists = {}
    _header_artists = {}

    def __init__(self, dataprovider, template, figure=None):
        self.dataprovider = dataprovider
        self.template = template
        self._fig = figure
        self.dummy = None
        self.axes = {}
        self.artists = {}
        self.track_axes_map = []
        self.layer_axes_map = []
        self.legend_axes_map = []
        self.header_axes_map = []
        self.ylims = []

    @property
    def fig(self):
        if self._fig is None:
            self._fig = Figure()
        return self._fig

    @fig.setter
    def fig(self, value):
        self._fig = value

    def draw(self):
        figsize = [
            a / self.template["figure"]["dpi"] for a in self.template["figure"]["size"]
        ]
        self.fig.set_size_inches(figsize)
        self.fig.set_dpi(self.template["figure"]["dpi"])
        self.fig.set_facecolor(self.template["figure"]["facecolor"])
        self.fig.set_edgecolor(self.template["figure"]["edgecolor"])
        self.fig.set_alpha(self.template["figure"]["alpha"])

        self.dummy = self.fig.add_axes([0.0, 0.0, 0.0, 0.0])
        self.dummy.set_visible(False)

        self.ylims = []

        for track in self.template["tracks"]:
            track_layer_axes_map = []
            track_legend_axes_map = []

            track_ax, track_ax_id = self._draw_track(track)

            self.axes[track_ax_id] = track_ax
            self.track_axes_map.append(track_ax_id)

            for layer in track["layers"]:
                legend = layer.get("legend", None)

                layer_ax, layer_ax_id = self._draw_layer(layer, track)
                self.axes[layer_ax_id] = layer_ax
                track_layer_axes_map.append(layer_ax_id)

                if legend is not None:
                    legend_ax, legend_ax_id = self._draw_legend(legend, layer, track)
                    self.axes[legend_ax_id] = legend_ax
                    track_legend_axes_map.append(legend_ax_id)
                else:
                    track_legend_axes_map.append(None)

            self.layer_axes_map.append(track_layer_axes_map)
            self.legend_axes_map.append(track_legend_axes_map)

        if "header" in self.template:
            header = self.template["header"]
            track = self.template["tracks"]
            header_ax, header_ax_id = self._draw_header(header, track)

            self.axes[header_ax_id] = header_ax
            self.header_axes_map.append(header_ax_id)

        ymax = max(filter(np.isfinite, (max(a) for a in self.ylims)))
        ymin = min(filter(np.isfinite, (min(a) for a in self.ylims)))
        self.set_ylim(ymax, ymin)

    def set_ylim(self, *args, **kwargs):
        self.dummy.set_ylim(*args, **kwargs)

    def get_ylim(self, *args, **kwargs):
        self.dummy.get_ylim(*args, **kwargs)

    def _set_linear_grid(self, axis, grid):
        g = copy.deepcopy(grid)
        type_ = g.pop("type")
        line = g.pop("line", {})
        minor = g.pop("minor", None)
        axis.set_major_locator(_LINEAR_TICK_LOCATORS[type_](**g))
        linekwargs = {}
        for k, v in line.items():
            linekwargs[_TR_LINE_MATPLOTLIB_LINE[k]] = v
        axis.grid(True, which="major", **linekwargs)
        if minor is not None:
            n = minor.get("numticks", None)
            line = minor.get("line", {})
            axis.set_minor_locator(AutoMinorLocator(n))
            linekwargs = {}
            for k, v in line.items():
                linekwargs[_TR_LINE_MATPLOTLIB_LINE[k]] = v
            axis.grid(True, which="minor", **linekwargs)

    def _set_logarithmic_grid(self, axis, grid):
        base = grid.get("base", 10)
        line = grid.get("line", {})
        minor = grid.get("minor", None)
        axis.set_major_locator(LogLocator(base=base))
        linekwargs = {}
        for k, v in line.items():
            linekwargs[_TR_LINE_MATPLOTLIB_LINE[k]] = v
        axis.grid(True, which="major", **linekwargs)
        if minor is not None:
            numticks = minor.get("numticks", int(base))
            subs = np.linspace(1.0, base, numticks)[1:-1]
            line = minor.pop("line", {})
            axis.set_minor_locator(LogLocator(base=base, subs=subs))
            linekwargs = {}
            for k, v in line.items():
                linekwargs[_TR_LINE_MATPLOTLIB_LINE[k]] = v
            axis.grid(True, which="minor", **linekwargs)

    def _create_ax(self, rect):
        ax_id = uuid.uuid4().hex
        ax = self.fig.add_axes(rect, sharey=self.dummy, label=ax_id)
        return ax, ax_id

    def _draw_track(self, track):
        ax, ax_id = self._create_ax(track["rect"])
        # prepare_clean_ax(ax, **track)
        xgrid = track.get("grid", {}).get("x", None)
        ygrid = track.get("grid", {}).get("y", None)
        if xgrid is not None:
            scale = track.get("scale", "linear")
            if scale == "linear":
                self._set_linear_grid(ax.xaxis, xgrid)
            elif scale == "log":
                self._set_logarithmic_grid(ax.xaxis, xgrid)
                ax.set_xscale("log")
                ax.set_xlim(xgrid["limits"])
            else:
                # TODO: warning
                msg = f"WARNING: Unknown scale: {scale}"
                print(msg)
        if ygrid is not None:
            self._set_linear_grid(ax.yaxis, ygrid)
        return ax, ax_id

    def _draw_layer(self, layer, track):
        layer = copy.deepcopy(layer)
        track = copy.deepcopy(track)

        ax, ax_id = self._create_ax(layer["rect"])
        prepare_transparent_ax(ax, **track)

        layer_artist = self._layer_artists[layer["type"]]

        def set_ylim(s, *args):
            if len(args) == 1:
                self.ylims.append(args[0])
            else:
                self.ylims.append(list(args))

        with monkeypatchmethod(ax, "set_ylim", set_ylim):
            artist = layer_artist(ax, self.dataprovider, layer, track)
        self.artists[ax_id] = artist

        return ax, ax_id

    def _draw_legend(self, legend, layer, track):
        legend = copy.deepcopy(legend)
        layer = copy.deepcopy(layer)
        track = copy.deepcopy(track)

        ax, ax_id = self._create_ax(legend["rect"])
        prepare_clean_ax(ax, **track)

        legend_artist = self._legend_artists[legend["type"]]

        artist = legend_artist(ax, self.dataprovider, legend, layer, track)
        self.artists[ax_id] = artist

        return ax, ax_id

    def _draw_header(self, header, track):
        ax, ax_id = self._create_ax(header["rect"])
        prepare_clean_ax(ax, **header)

        header_artist = self._header_artists[header["type"]]

        artist = header_artist(ax, self.dataprovider, header, track)
        self.artists[ax_id] = artist

        return ax, ax_id

    @classmethod
    def register_layer_artist(cls, name):
        def decorator(artist):
            cls._layer_artists[name] = artist
            return artist

        return decorator

    @classmethod
    def register_legend_artist(cls, name):
        def decorator(artist):
            cls._legend_artists[name] = artist
            return artist

        return decorator

    @classmethod
    def register_header_artist(cls, name):
        def decorator(artist):
            cls._header_artists[name] = artist
            return artist

        return decorator


@LogPlot.register_legend_artist("line")
class LineLegendArtist:
    # TODO: text properties
    LIMITS_VERTICAL_POSITION = 0.1
    LIMITS_HORIZONTAL_POSITION = 0.02
    LABEL_VERTICAL_POSITION = 0.75
    LINE_VERTICAL_POSITION = 0.25
    LINE_SIZE = 0.5

    def __init__(self, ax, dataprovider, legend, layer, track):
        self.ax = ax

        # TODO: generalize
        text = legend.get("text", layer.get("text", None))
        if text is None:
            text = {}
        label = legend.get("label", layer.get("label", None))
        if label is None:
            label = dataprovider.get_label(layer["data"])
        limits = legend.get("limits", layer.get("limits", None))
        if limits is None:
            limits = {}
        if "x" not in limits:
            limits["x"] = dataprovider.get_range(layer["data"]["x"])
        # Line can be None, so the approach above won't work
        if "line" in legend:
            line = legend["line"]
        elif "line" in layer:
            line = layer["line"]
        else:
            line = dataprovider.get_line(layer["data"]["x"])
        marker = legend.get("marker", layer.get("marker", None))
        if marker is None:
            # TODO: implement
            # marker = dataprovider.get_marker(layer["data"])
            marker = {}

        textkwargs = {}
        if text is not None:
            for k, v in text.items():
                textkwargs[_TR_TEXT_MATPLOTLIB_TEXT[k]] = v

        self.left_text = ax.text(
            self.LIMITS_HORIZONTAL_POSITION,
            self.LIMITS_VERTICAL_POSITION,
            str(limits["x"][0]),
            ha="left",
            va="baseline",
            transform=self.ax.transAxes,
            **textkwargs,
        )

        self.right_text = ax.text(
            1.0 - self.LIMITS_HORIZONTAL_POSITION,
            self.LIMITS_VERTICAL_POSITION,
            str(limits["x"][1]),
            ha="right",
            va="baseline",
            transform=self.ax.transAxes,
            **textkwargs,
        )

        self.label_text = ax.text(
            0.5,
            self.LABEL_VERTICAL_POSITION,
            label,
            va="center",
            ha="center",
            transform=self.ax.transAxes,
            **textkwargs,
        )

        linekwargs = {}
        if line is not None:
            for k, v in line.items():
                linekwargs[_TR_LINE_MATPLOTLIB_LINE[k]] = v
        else:
            linekwargs["linestyle"] = "none"

        markerkwargs = {}
        if marker is not None:
            for k, v in marker.items():
                markerkwargs[_TR_MARKER_MATPLOTLIB_MARKER[k]] = v

        (self.line,) = ax.plot(
            [(1.0 - self.LINE_SIZE) / 2.0, (1.0 + self.LINE_SIZE) / 2.0],
            [self.LINE_VERTICAL_POSITION, self.LINE_VERTICAL_POSITION],
            transform=self.ax.transAxes,
            **linekwargs,
            **markerkwargs,
        )

        self.ax.set_xlim(0.0, 1.0)
        self.ax.set_ylim(0.0, 1.0)


@LogPlot.register_legend_artist("simple")
class SimpleLegendArtist:
    # TODO: text properties
    def __init__(self, ax, dataprovider, legend, layer, track):
        self.ax = ax

        label = legend.get("label", layer.get("label", None))
        if label is None:
            label = dataprovider.get_label(layer["data"])
        text = legend.get("text", layer.get("text", None))
        if text is None:
            text = dataprovider.get_text(layer["data"])

        self.label_text = ax.text(
            0.5,
            0.5,
            label,
            ha="center",
            va="center",
            transform=self.ax.transAxes,
            **text,
        )

        self.ax.set_xlim(0.0, 1.0)
        self.ax.set_ylim(0.0, 1.0)


@LogPlot.register_legend_artist("dummy")
class DummyLegendArtist:
    def __init__(self, ax, dataprovider, legend, layer, track):
        self.ax = ax


# @LogPlot.register_legend_artist("patches")
# class PatchesLegendArtist:
#     pass


@LogPlot.register_layer_artist("line")
class LineLayerArtist:
    def __init__(self, ax, dataprovider, layer, track):
        self.ax = ax

        xlim = layer.get("limits", {}).get("x", None)
        if xlim is None:
            xlim = dataprovider.get_range(layer["data"]["x"])
        # Line can be None, so the approach above won't work
        if "line" in layer:
            line = layer["line"]
        else:
            line = dataprovider.get_line(layer["data"]["x"])
        marker = layer.get("marker", None)
        if marker is None:
            # TODO: implement
            # marker = dataprovider.get_marker(layer["data"]["x"])
            marker = {}

        linekwargs = {}
        if line is not None:
            for k, v in line.items():
                linekwargs[_TR_LINE_MATPLOTLIB_LINE[k]] = v
        else:
            linekwargs["linestyle"] = "none"

        markerkwargs = {}
        if marker is not None:
            for k, v in marker.items():
                markerkwargs[_TR_MARKER_MATPLOTLIB_MARKER[k]] = v

        data = dataprovider.get_data(layer["data"])
        xdata = data["x"]["data"]
        ydata = data["y"]["data"]

        idx0 = max(get_starting_nans(a) for a in (xdata, ydata))
        idxn = len(xdata) - 1 - max(get_starting_nans(a[::-1]) for a in (xdata, ydata))
        slc = slice(idx0, idxn + 1)

        (self.line,) = self.ax.plot(
            xdata[slc], ydata[slc], **linekwargs, **markerkwargs
        )

        ymin = min(ydata[idx0], ydata[idxn])
        ymax = max(ydata[idx0], ydata[idxn])
        scale = track.get("scale", "linear")
        self.ax.set_xlim(xlim)
        if scale == "log":
            self.ax.set_xscale("log")
        self.ax.set_ylim(ymax, ymin)


@LogPlot.register_layer_artist("text")
class TextLayerArtist:
    def __init__(self, ax, dataprovider, layer, track):
        self.ax = ax
        self._cid = self.ax.callbacks.connect("ylim_changed", self._callback)

        self.texts = []

        text = layer.get("text", None)
        if text is None:
            # TODO: implement
            # text = dataprovider.get_text(layer["data"]["x"])
            text = {}

        self.text_properties = text

        self.x_is_y = layer["data"]["x"] == layer["data"]["y"]

        if self.x_is_y:
            self.xdata = None
            self.ydata = None
        else:
            data = dataprovider.get_data(layer["data"])
            self.ydata = data["y"].data
            self.xdata = data["x"].data

            idx0 = max(get_starting_nans(a) for a in (self.ydata, self.xdata))
            idxn = (
                len(self.ydata)
                - 1
                - max(get_starting_nans(a[::-1]) for a in (self.ydata, self.xdata))
            )
            ymin = min(self.ydata[idx0], self.ydata[idxn])
            ymax = max(self.ydata[idx0], self.ydata[idxn])

            self.ax.set_ylim(ymax, ymin)

    def _callback(self, ax):
        if self.ax is not ax:
            return

        for i in range(len(self.texts)):
            text = self.texts.pop()
            text.remove()

        ypositions = self.ax.get_yticks()
        if self.x_is_y:
            xpositions = ypositions
        else:
            xpositions = np.interp(ypositions, self.ydata, self.xdata)

        ymin, ymax = sorted(self.ax.get_ylim())

        for y, x in zip(ypositions, xpositions):
            if not (ymin < y < ymax):
                continue

            text = self.ax.text(
                0.5,
                y,
                str(x),
                ha="center",
                va="center",
                transform=self.ax.get_yaxis_transform(),
                **self.text_properties,
            )
            self.texts.append(text)

    def __del__(self):
        self.ax.callbacks.disconnect(self._cid)


@LogPlot.register_layer_artist("fillbetween")
class FillBetweenLayerArtist:
    # TODO: logscale ?
    def __init__(self, ax, dataprovider, layer, track):
        self.ax = ax

        patches = {}
        transforms = {}

        def get_transform(a, b):
            def transform(x):
                return (x - a) / (b - a)

            return transform

        for side in ["left", "right"]:
            patch = {}
            for k, v in layer[side]["patch"].items():
                patch[_TR_PATCH_MATPLOTLIB_PATCH[k]] = v
            patch["linewidth"] = 0.0

            patches[side] = patch

            # TODO: get it properly, like on other artists
            xlim = layer[side].get("limits", {}).get("x", None)
            if xlim is None:
                xlim = dataprovider.get_range(layer[side]["data"]["x"])
            a, b = xlim

            def transform(x):
                return (x - a) / (b - a)

            transforms[side] = get_transform(a, b)

        # TODO: y???
        layer_data = {
            "left": layer["left"]["data"]["x"],
            "right": layer["right"]["data"]["x"],
            "y": layer.get("data", layer["left"]["data"])["y"],
            "source": "well_logs",
        }

        self.left_fills = []
        self.right_fills = []
        ymin = np.inf
        ymax = -np.inf

        data = dataprovider.get_data(layer_data)

        ldata = transforms["left"](data["left"].data)
        rdata = transforms["right"](data["right"].data)
        ydata = data["y"].data

        idx0 = max(get_starting_nans(a) for a in (ldata, rdata, ydata))
        idxn = (
            len(ldata)
            - 1
            - max(get_starting_nans(a[::-1]) for a in (ldata, rdata, ydata))
        )
        slc = slice(idx0, idxn + 1)

        not_nan = ~(np.isnan(ldata[slc]) | np.isnan(rdata[slc]))
        lwhere = np.zeros(idxn - idx0 + 1, dtype=bool)
        rwhere = np.zeros(idxn - idx0 + 1, dtype=bool)
        lwhere[not_nan] = ldata[slc][not_nan] > rdata[slc][not_nan]
        rwhere[not_nan] = rdata[slc][not_nan] > ldata[slc][not_nan]

        interp = True

        self.left_fill = ax.fill_betweenx(
            ydata[slc],
            ldata[slc],
            rdata[slc],
            lwhere,
            interpolate=interp,
            **patches["left"],
        )
        self.right_fill = ax.fill_betweenx(
            ydata[slc],
            ldata[slc],
            rdata[slc],
            rwhere,
            interpolate=interp,
            **patches["right"],
        )

        ymin = min(ydata[idx0], ydata[idxn])
        ymax = max(ydata[idx0], ydata[idxn])

        self.ax.set_xlim(0.0, 1.0)
        self.ax.set_ylim(ymax, ymin)


@LogPlot.register_layer_artist("intervals")
class IntervalsLayerArtist:
    # TODO: allow text
    def __init__(self, ax, dataprovider, layer, track):
        self.ax = ax
        well_interval_lists = {}
        zones = {}
        for well_interval in dataprovider.get_data(layer["data"]):
            if well_interval.zone.id not in well_interval_lists:
                well_interval_lists[well_interval.zone.id] = []
                zones[well_interval.zone.id] = well_interval.zone
            well_interval_lists[well_interval.zone.id].append(well_interval)

        self.patch_collections = []

        ymin = np.inf
        ymax = -np.inf

        for zone_id, well_intervals in well_interval_lists.items():
            zone = zones[zone_id]
            patchkwargs = {
                "facecolor": zone.patch_property.color,
                "hatch": zone.patch_property.hatch,
                "edgecolor": zone.patch_property.hatchcolor,
                "alpha": zone.patch_property.alpha,
                "linewidth": 0.0,
                "transform": self.ax.get_yaxis_transform(),
            }

            rectangles = []

            for well_interval in well_intervals:
                top = well_interval.depth_interval.top.depth
                bottom = well_interval.depth_interval.bottom.depth
                rect = Rectangle((0.0, top), 1.0, bottom - top)
                rectangles.append(rect)

                ymin = min(ymin, min(top, bottom))
                ymax = max(ymax, max(top, bottom))

            pc = PatchCollection(rectangles, **patchkwargs)
            self.ax.add_collection(pc)
            self.patch_collections.append(pc)

        self.ax.set_xlim(0.0, 1.0)
        self.ax.set_ylim(ymax, ymin)


@LogPlot.register_layer_artist("dummy")
class DummyLayerArtist:
    def __init__(self, ax, dataprovider, layer, track):
        self.ax = ax


# @LogPlot.register_layer_artist("markers")
# class MarkersLayerArtist:
#     pass


@LogPlot.register_header_artist("simple")
class SimpleHeaderArtist:
    def __init__(self, ax, dataprovider, header, track):
        from datetime import datetime

        self.ax = ax

        title = header.pop("title", {})
        label_title = title.get(
            "label", track[0]["layers"][0]["data"]["x"]["well"]["name"]
        )
        position_title = title.get("position", [0.5, 0.5])
        text_title = title.get("text", None)
        textkwargs = {}
        if text_title is not None:
            for k, v in text_title.items():
                textkwargs[_TR_TEXT_MATPLOTLIB_TEXT[k]] = v
        self.title = ax.text(
            position_title[0],
            position_title[1],
            label_title,
            ha="center",
            va="center",
            transform=self.ax.transAxes,
            **textkwargs,
        )

        subtitle = header.pop("subtitle", {})
        label_subtitle = subtitle.get("label", None)
        position_subtitle = subtitle.get("position", [0.5, 0.3])
        text_subtitle = subtitle.get("text", title.get("text", None))
        textkwargs = {}
        if text_subtitle is not None:
            for k, v in text_subtitle.items():
                textkwargs[_TR_TEXT_MATPLOTLIB_TEXT[k]] = v

        self.subtitle = ax.text(
            position_subtitle[0],
            position_subtitle[1],
            label_subtitle,
            ha="center",
            va="center",
            transform=self.ax.transAxes,
            **textkwargs,
        )

        _datetime = header.pop("datetime", {})
        date = _datetime.get("date", False)
        time = _datetime.get("time", False)
        text_datetime = _datetime.get(
            "text", subtitle.get("text", title.get("text", None))
        )
        if text_datetime is not None:
            for k, v in text_datetime.items():
                textkwargs[_TR_TEXT_MATPLOTLIB_TEXT[k]] = v

        if date is True:
            date = (
                datetime.now().strftime("%d")
                + "/"
                + datetime.now().strftime("%m")
                + "/"
                + datetime.now().strftime("%Y")
            )
            self.date = ax.text(
                0.01,
                0.5,
                date,
                ha="left",
                va="center",
                transform=self.ax.transAxes,
                **textkwargs,
            )
        if time is True:
            time = datetime.now().strftime("%H") + ":" + datetime.now().strftime("%M")
            self.time = ax.text(
                0.01,
                0.3,
                time,
                ha="left",
                va="center",
                transform=self.ax.transAxes,
                **textkwargs,
            )

import copy
from collections.abc import Mapping, MutableSequence


# TODO: register this together with the artists
_DEFAULT_LEGEND_TYPES = {
    "line": "line",
    "text": "simple",
    "fillbetween": "patches",
    "intervals": "patches",
    "markers": "simple",
    "dummy": "dummy",
}

_DEFAULT_DATA_SOURCES = {
    "line": "well_log",
    "text": "well_log",
    "fillbetween": "well_log",
    "intervals": "zone_families",
    "markers": "marker_families",
    "dummy": None
}
#

def deep_update(d1, d2):
    for key, value in d2.items():
        if isinstance(value, Mapping):
            d1[key] = deep_update(d1.get(key, {}), value)
        else:
            d1[key] = value
    return d1


def expand_keys(d1):
    d2 = {}
    for key, value in d1.items():
        if "." in key:
            key1, key2 = key.split(".", 1)
            if key1 not in d2:
                d2[key1] = {}
            if key2 not in d2[key1]:
                d2[key1][key2] = value
            else:
                msg = f"Key path {key1} -> {key2} already exists in mapping with value {d2[key1][key2]}"
                raise ValueError(msg)
        else:
            if key in d2:
                if isinstance(d2[key], Mapping):
                    if isinstance(value, Mapping):
                        for k, v in value.items():
                            if k not in d2[key]:
                                d2[key][k] = v
                            else:
                                msg = f"Key path '{key} -> {k}' already exists in mapping with value {d2[key][k]}"
                                raise ValueError(msg)
                    else:
                        msg = f"Trying to set existing mapping for key '{key}' with non-mapping value {value}"
                        raise ValueError(msg)
                else:
                    msg = f"Trying to set existing value for key '{key}' with value {value}"
                    raise ValueError(msg)
            else:
                d2[key] = value
    for key, value in d2.items():
        if isinstance(value, Mapping):
            d2[key] = expand_keys(value)
        elif isinstance(value, MutableSequence):
            li = []
            for el in value:
                if isinstance(el, Mapping):
                    li.append(expand_keys(el))
                else:
                    li.append(el)
            d2[key] = li
    return d2


# TODO: generalize?
def apply_defaults(template):
    defaults = template.pop("defaults", {})

    tracks_defaults = defaults.get("tracks", {})
    layers_defaults = defaults.get("layers", {})

    if "header" in template:
        header_defaults = defaults.get("header", {})

        header = deep_update(copy.deepcopy(header_defaults), template["header"])
        template["header"] = header

    tracks = []
    for t in template["tracks"]:
        if t.get("inherit", True):
            track = deep_update(copy.deepcopy(tracks_defaults), t)
        else:
            track = t

        layers = []
        for l in t.pop("layers"):
            if l.get("inherit", True):
                layer = deep_update(copy.deepcopy(layers_defaults), l)
            else:
                layer = l

            layers.append(layer)

        track["layers"] = layers
        tracks.append(track)

    template["tracks"] = tracks

    return template


def get_references(template):
    references = {}

    for key, value in template.items():
        if isinstance(value, Mapping):
            if "id" in value:
                key = value.pop("id")
                references[key] = value
            references = deep_update(references, get_references(value))
        elif isinstance(value, MutableSequence):
            for el in value:
                if isinstance(el, Mapping):
                    if "id" in el:
                        key = el.pop("id")
                        references[key] = el
                    references = deep_update(references, get_references(el))

    return references


def apply_references(template, references):
    for key, value in template.items():
        if isinstance(value, Mapping):
            if "reference" in value:
                key = value.pop("reference")
                value = deep_update(value, references[key])
            apply_references(value, references)
        elif isinstance(value, MutableSequence):
            for el in value:
                if isinstance(el, Mapping):
                    if "reference" in el:
                        key = el.pop("reference")
                        el = deep_update(el, references[key])
                    apply_references(el, references)

    return template


# TODO: generalize, almost same thing as apply_legends
def apply_legends(template, legends):
    for track in template["tracks"]:
        for layer in track["layers"]:
            if "legend" not in layer:
                legend_type = legends[layer["type"]]
                if legend_type is not None:
                    layer["legend"] = {"type": legend_type}
                else:
                    layer["legend"] = None
    return template


def apply_data_sources(template, data_sources):
    for track in template["tracks"]:
        for layer in track["layers"]:
            if "data" in layer:
                if "source" not in layer["data"]:
                    data_source = data_sources[layer["type"]]
                    if data_source is not None:
                        layer["data"]["source"] = data_source
    return template


#


def get_absolute_rect(rect, reference):
    relleft, relbottom, relwidth, relheight = rect
    refleft, refbottom, refwidth, refheight = reference

    left = refleft + relleft * refwidth
    bottom = refbottom + relbottom * refheight
    width = relwidth * refwidth
    height = relheight * refheight

    return left, bottom, width, height


def get_relative_rect(rect, reference):
    absleft, absbottom, abswidth, absheight = rect
    refleft, refbottom, refwidth, refheight = reference

    left = (absleft - refleft) / refwidth
    bottom = (absbottom - refbottom) / refheight
    width = abswidth / refwidth
    height = absheight / refheight

    return left, bottom, width, height


def get_axes_rectangles(template):
    layout = template.pop("layout")

    n_tracks = len(template["tracks"])
    legend_map = []
    tracks_widths = []
    layer_positions = []
    for track in template["tracks"]:
        tracks_widths.append(track["width"])
        lm = []
        lp = []
        for layer in track["layers"]:
            legend = layer.get("legend", None)
            if legend is not None:
                lm.append(True)
            else:
                lm.append(False)
            # lp.append(layer.pop("position", [0.0, 1.0]))
            lp.append(layer.get("position", [0.0, 1.0]))
        legend_map.append(lm)
        layer_positions.append(lp)

    max_legends = max(map(sum, legend_map))

    tlh = layout.get("totallegendheight", None)
    lh = layout.get("legendheight", None)
    lts = layout["legendtrackspacing"]
    vs = layout["verticalspacing"]
    hs = layout["horizontalspacing"]

    if "header" in template:
        hh = layout["headerheight"]
        for track in template["tracks"]:
            track["expandlegends"] = True
    else:
        hh = 0.0

    if layout.get("mode", "absolute") == "absolute":
        width, height = template["figure"]["size"]

        if tlh is not None:
            tlh /= height
        if lh is not None:
            lh /= height
        
        hh /= height
        lts /= height
        vs /= height
        hs /= width

        reference_rect = layout.get("rect", [0.0, 0.0, width, height])
        reference_rect = get_relative_rect(reference_rect, [0.0, 0.0, width, height])
    else:
        reference_rect = layout.get("rect", [0.0, 0.0, 1.0, 1.0])

    ths = (n_tracks - 1) * hs
    ttw = sum(tracks_widths)
    tws = [(1.0 - ths) * a / ttw for a in tracks_widths]

    if tlh is not None:
        lh = (tlh - lts / 2 - (max_legends - 1) * vs) / max_legends
    elif lh is not None:
        tlh = lh * max_legends + lts / 2 + (max_legends - 1) * vs

    th = 1.0 - tlh - hh - lts / 2

    lb = th + lts
    tl = 0.0

    track_rects = []
    layer_rects = []
    legend_rects = []
    for i, track in enumerate(template["tracks"]):
        track_rect = get_absolute_rect([tl, 0.0, tws[i], th], reference_rect)
        track_rects.append(track_rect)

        n_legends = sum(legend_map[i])

        if track.get("expandlegends", False):
            lh_ = (tlh - lts / 2 - (n_legends - 1) * vs) / n_legends
        else:
            lh_ = lh
        # lb_ = lb
        lb_ = lb + (lh_ + vs) * (n_legends - 1)
        lyr = []
        lgr = []
        for l, p in zip(legend_map[i], layer_positions[i]):
            # rll = tl
            # rlw = tws[i]
            rll = tl + p[0] * tws[i]
            rlw = tws[i] * (p[1] - p[0])

            layer_rect = get_absolute_rect([rll, 0.0, rlw, th], reference_rect)
            lyr.append(layer_rect)

            if l:
                legend_rect = get_absolute_rect([rll, lb_, rlw, lh_], reference_rect)
                lgr.append(legend_rect)
                # lb_ += lh + vs
                lb_ -= lh_ + vs
            else:
                lgr.append(None)
        layer_rects.append(lyr)
        legend_rects.append(lgr)
        tl += tws[i] + hs

    if "header" in template:
        # hb = th + lh_ + vs
        hb = th + lh + vs
        header_rects = get_absolute_rect([0.0, hb, 1.0, hh], reference_rect)
    else:
        header_rects = None

    return track_rects, layer_rects, legend_rects, header_rects


def apply_axes_rectangles(template, track_rects, layer_rects, legend_rects, header_rects):
    if "header" in template:
        if "rect" not in template["header"]:
            template["header"]["rect"] = header_rects
    for i, track in enumerate(template["tracks"]):
        if "rect" not in track:
            track["rect"] = track_rects[i]
        for j, layer in enumerate(track["layers"]):
            if "rect" not in layer:
                layer["rect"] = layer_rects[i][j]
            if (layer.get("legend", None) is not None) and ("rect" not in layer["legend"]):
                layer["legend"]["rect"] = legend_rects[i][j]
    return template


def parse(template):
    template = expand_keys(template)
    template = apply_defaults(template)
    template = apply_legends(template, _DEFAULT_LEGEND_TYPES)
    template = apply_data_sources(template, _DEFAULT_DATA_SOURCES)
    ref = get_references(template)
    template = apply_references(template, ref)
    track_rects, layer_rects, legend_rects, header_rects = get_axes_rectangles(template)
    apply_axes_rectangles(template, track_rects, layer_rects, legend_rects, header_rects)
    template["schema"] = "appy-logplot-template-final"

    return template

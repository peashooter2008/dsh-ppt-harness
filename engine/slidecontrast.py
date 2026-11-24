"""Keep generated native text readable on its actual slide or container surface."""

import math
import re

from lxml import etree as ET

from engine import A, P, NS, paint, pair, read_background, shape_list


TAG = "{urn:dieye:presentation:contrast:1}palette"
EXT_URI = "{1C037AA9-F43D-4C4B-B38A-F6F740D60C95}"


def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _luminance(channels):
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(x * k for x, k in zip(linear, (.2126, .7152, .0722)))


def contrast_ratio(foreground, background):
    a, b = sorted((_luminance(_rgb(foreground)), _luminance(_rgb(background))))
    return (b + .05) / (a + .05)


def contrast_bounds(background):
    """Conservative luminance interval of a solid color or two-stop sRGB gradient."""
    if isinstance(background, str):
        light = _luminance(_rgb(background))
        return light, light
    start, end = _rgb(background["from"]), _rgb(background["to"])
    # Channel-wise envelopes also bound saturated gradients whose darkest point
    # lies inside the interpolation, rather than at one of the supplied stops.
    lows, highs = [], []
    before = start
    for i in range(1, 17):
        after = tuple(s + (e - s) * i / 16 for s, e in zip(start, end))
        lows.append(_luminance(tuple(min(a, b) for a, b in zip(before, after))))
        highs.append(_luminance(tuple(max(a, b) for a, b in zip(before, after))))
        before = after
    return min(lows), max(highs)


def _min_ratio(ink, bounds):
    lum = _luminance(_rgb(ink))
    closest = min(max(lum, bounds[0]), bounds[1])
    return (max(lum, closest) + .05) / (min(lum, closest) + .05)


def _ink(preferred, bounds, secondary=False):
    alternatives = ("B4BFC2", "495659") if secondary else ("E9EDEC", "20292B")
    for candidate in (preferred, *alternatives, "FFFFFF", "000000"):
        if _min_ratio(candidate, bounds) >= 4.5:
            return candidate
    return None


def graphic_color(value):
    """Retain the accent hue while making a plotted mark visible on white."""
    channels = _rgb(value)
    for step in range(21):
        result = "".join(f"{round(c * (1 - step / 20) * 255):02X}" for c in channels)
        if contrast_ratio(result, "FFFFFF") >= 3:
            return result
    return "000000"


def series_colors(accent):
    """Order eight distinct marks, allowing for a user template's accent."""
    chosen = [graphic_color(accent)]
    remaining = [graphic_color(v) for v in (
        "BD593D", "3C6684", "6E5D86", "557D4E", "AE7134", "517C80",
        "9D5369", "394354", "9C730E", "3272A8", "9D3A65")]
    while len(chosen) < 8:
        distances = [min(sum((x-y)**2 for x, y in zip(_rgb(candidate), _rgb(c)))
                         for c in chosen) for candidate in remaining]
        # Prefer the original ordered palette whenever the new mark is distinct.
        idx = next((i for i, d in enumerate(distances) if d >= .09),
                   distances.index(max(distances)))
        chosen.append(remaining.pop(idx))
    return chosen


def _bounds_of(shape, transform):
    xf = shape.find("p:spPr/a:xfrm", NS)
    if xf is None:
        xf = shape.find("p:xfrm", NS)
    if xf is None:
        return None
    x, y = pair(xf, "off", "x", "y")
    w, h = pair(xf, "ext", "cx", "cy")
    sx, sy, dx, dy = transform
    x, y, w, h = x*sx+dx, y*sy+dy, w*sx, h*sy
    angle = math.radians(int(xf.get("rot", 0)) / 60000)
    width = abs(math.cos(angle))*w + abs(math.sin(angle))*h
    height = abs(math.sin(angle))*w + abs(math.cos(angle))*h
    return (x + (w-width)/2, y + (h-height)/2, x + (w+width)/2, y + (h+height)/2)


def _surface_at(rect, base, layers):
    surfaces = [base]
    for left, top, right, bottom, surface, opaque in layers:
        if right <= rect[0] or bottom <= rect[1] or left >= rect[2] or top >= rect[3]:
            continue
        if opaque and left <= rect[0] and top <= rect[1] and right >= rect[2] and bottom >= rect[3]:
            surfaces = [surface]
        else:
            surfaces.append(surface)
    return min(v[0] for v in surfaces), max(v[1] for v in surfaces)


def _plate(properties, value):
    old = properties.find("a:solidFill", NS)
    if old is None:
        old = properties.find("a:noFill", NS)
    new = ET.Element(f"{{{A}}}solidFill" if value else f"{{{A}}}noFill")
    if value:
        ET.SubElement(new, f"{{{A}}}srgbClr", val=value)
    if old is not None:
        properties.replace(old, new)
    else:
        geom = properties.find("a:prstGeom", NS)
        properties.insert(properties.index(geom) + 1 if geom is not None else 0, new)


def apply_readability(root, palette=None):
    """Apply only to slides made here; keep authored artwork and text editable."""
    common = root.find("p:cSld", NS)
    marker = common.find(f"p:extLst/p:ext/{TAG}", NS)
    if marker is None:
        if palette is None:
            return
        extensions = common.find("p:extLst", NS)
        if extensions is None:
            extensions = ET.SubElement(common, f"{{{P}}}extLst")
        ext = ET.SubElement(extensions, f"{{{P}}}ext", uri=EXT_URI)
        marker = ET.SubElement(ext, TAG, nsmap={"dy": "urn:dieye:presentation:contrast:1"},
                               ink=palette[1], muted=palette[4], surface=palette[0])
    if not all(re.fullmatch("[A-Fa-f0-9]{6}", marker.get(k, "")) for k in ("ink", "muted", "surface")):
        return
    background = common.find("p:bg/p:bgPr", NS)
    known_fill = read_background(background, {}, None)
    base = contrast_bounds(known_fill) if known_fill else (0., 1.)
    old_plates = set(marker.get("plates", "").split())
    previous_inks = dict(entry.split("=", 1) for entry in marker.get("inks", "").split() if "=" in entry)
    new_plates, inks, layers = [], [], []
    for sid, name, obj, transform in shape_list(root):
        rect = _bounds_of(obj, transform)
        if rect is None:
            continue
        sp = obj.find("p:spPr", NS)
        fill = paint(obj.find("p:spPr/a:solidFill", NS), {}, None)
        runs = obj.findall("p:txBody/a:p/a:r/a:rPr/a:solidFill/a:srgbClr", NS)
        if runs and (name in ("标题", "来源", "图注或结论") or name.startswith("论点 ")):
            if sid in old_plates and fill == "#" + marker.get("surface"):
                _plate(sp, None)
                fill = None
            bounds = contrast_bounds(fill) if fill else _surface_at(rect, base, layers)
            role = "muted" if name in ("来源", "图注或结论") else "ink"
            ink = _ink(marker.get(role), bounds, secondary=role == "muted")
            if ink is None:
                fill = "#" + marker.get("surface")
                _plate(sp, fill[1:])
                new_plates.append(sid)
                bounds = contrast_bounds(fill)
                ink = _ink(marker.get(role), bounds, secondary=role == "muted")
            for run in runs:
                current = run.get("val", "").upper()
                # Retain a legible emphasis color applied by the author in Office.
                if sid in previous_inks and current != previous_inks[sid] and re.fullmatch("[A-F0-9]{6}", current):
                    if _min_ratio(current, bounds) >= 4.5:
                        continue
                run.set("val", ink)
            inks.append(f"{sid}={ink}")
        if fill:
            # Hairline dividers and ticks surround the text; they do not carry glyphs.
            if min(rect[2]-rect[0], rect[3]-rect[1]) <= 3 * 12700:
                continue
            geom = obj.find("p:spPr/a:prstGeom", NS)
            xf = obj.find("p:spPr/a:xfrm", NS)
            aligned = xf is None or int(xf.get("rot", 0)) % (90 * 60000) == 0
            opaque = aligned and geom is not None and (geom.get("prst") == "rect" or name in ("对话气泡", "标题底色"))
            layers.append((*rect, contrast_bounds(fill), opaque))
        elif obj.tag in (f"{{{P}}}pic", f"{{{P}}}graphicFrame"):
            layers.append((*rect, (0., 1.), False))
    marker.set("plates", " ".join(new_plates))
    marker.set("inks", " ".join(inks))

"""Reuse the explicit colours in the last editable edition, including after a restart."""
from collections import Counter
import colorsys
import re
from unicodedata import normalize

from engine import A, R, Deck, local
from slidecontrast import graphic_color


C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
NS = {"a":A, "c":C}


def label_keys(labels):
    counts = Counter()
    for label in labels:
        name = normalize("NFC", str(label).strip())
        counts[name] += 1
        yield name, counts[name]


def explicit_color(node, paths):
    for path in paths:
        paint = node.find(path, NS)
        if paint is not None and not len(paint) and re.fullmatch("[a-fA-F0-9]{6}", paint.get("val","")):
            return paint.get("val").upper()
    return None


def chart_color_history(path):
    result = {"series":{}, "categories":{}}
    if path is None:
        return result
    with path.open("rb") as stream:
        deck = Deck.from_stream(stream,path.stat().st_size)
        with deck.zip:
            seen = set()
            for slide in deck.slides:
                refs = deck.rels(slide)
                for ref in deck.tree(slide).iter(f"{{{C}}}chart"):
                    kind, part = refs.get(ref.get(f"{{{R}}}id"), ("",""))
                    if kind=="chart" and part in deck.names and part not in seen:
                        read_marks(deck.tree(part),result)
                        seen.add(part)
    return result


def read_marks(chart, result):
    for plot in chart.findall(".//c:plotArea/*",NS):
        series = plot.findall("c:ser",NS)
        if local(plot) in ("pieChart","pie3DChart","doughnutChart"):
            for item in series:
                # Use cached chart labels, keyed by the OOXML point index.
                names = {pt.get("idx"):pt.findtext("c:v","",NS) for pt in item.findall("c:cat//c:pt",NS)}
                points = {pt.find("c:idx",NS).get("val"):pt for pt in item.findall("c:dPt",NS) if pt.find("c:idx",NS) is not None}
                valid = sorted((int(idx),label) for idx,label in names.items() if idx and idx.isdecimal())
                for (idx,label),key in zip(valid,label_keys(label for _,label in valid)):
                    point = points.get(str(idx))
                    color = explicit_color(point,["c:spPr/a:solidFill/a:srgbClr"]) if point is not None else None
                    if color:
                        result["categories"][key] = color
        else:
            labels = [s.findtext("c:tx/c:v",None,NS) or s.findtext("c:tx//c:pt/c:v","",NS) for s in series]
            for item,key in zip(series,label_keys(labels)):
                color = explicit_color(item,["c:spPr/a:solidFill/a:srgbClr","c:spPr/a:ln/a:solidFill/a:srgbClr"])
                if color:
                    result["series"][key] = color


def distance(a,b):
    return sum((int(a[i:i+2],16)-int(b[i:i+2],16))**2 for i in (0,2,4))


def consistent_marks(labels, history, palette):
    keys = list(label_keys(labels))
    assigned = {}
    used = set()
    # Claim known colours first, even if a new series moves to the front of the chart.
    for key in keys:
        color = history.get(key)
        if color and color not in used:
            assigned[key] = color
            used.add(color)
    pool = list(dict.fromkeys(palette))
    reserved = set(history.values())
    needs = len(keys) - len(assigned)
    if len(set(pool)-reserved) < needs:
        # Later pages may bring together categories first introduced on separate pages.
        # Grow the pool before reusing another named category's established colour.
        for index in range(64+2*len(reserved)+4*needs):
            channels = colorsys.hls_to_rgb((index*.618034)%1, .32+.07*(index%4), .45+.13*(index%3))
            candidate = graphic_color("".join(f"{round(k*255):02X}" for k in channels))
            if candidate not in reserved and candidate not in pool:
                pool.append(candidate)
                if len(pool)-len(reserved.intersection(pool)) >= max(needs,16):
                    break
    inherited = bool(assigned)
    for key in keys:
        if key in assigned:
            continue
        candidates = [col for col in pool if col not in used]
        fresh = [col for col in candidates if col not in reserved] or candidates
        differences = [min((distance(col,other) for other in used),default=255**2*3) for col in fresh]
        best = differences.index(max(differences))
        pick = best if inherited else next((i for i,d in enumerate(differences) if d>=68**2),best)
        color = fresh[pick]
        assigned[key] = history[key] = color
        used.add(color)
    return [assigned[key] for key in keys]

"""Read visual evidence from a sample of native slides. No rendering or external resources."""
from collections import Counter
from io import BytesIO
import re
from zipfile import BadZipFile

from PIL import Image, ImageStat
from engine import NS, R, local, paint, picture_blip, shape_list, theme_for


def unknown_visual():
    return dict(tone="unknown", background=None, accent=None, colors=[], fonts=[], layout="unknown",
                titleAnchor="unknown", titleFont=None, paletteBasis="unknown")


def rgb(color):
    return tuple(int(color[i:i+2], 16) for i in (1, 3, 5))


def luminance(color):
    return sum(v * w for v, w in zip(rgb(color), (.2126, .7152, .0722)))


def fill_color(fill, theme):
    color = paint(fill, theme, None)
    if color and not any(len(c) for c in fill):
        return color.upper()
    return None


def bitmap_color(deck, part, blip):
    """For a picture backdrop report the median pixel colour, without reading linked media."""
    if blip is None:
        return None
    kind, media = deck.rels(part).get(blip.get(f"{{{R}}}embed"), (None, None))
    if kind != "image" or media not in deck.names or deck.zip.getinfo(media).file_size > 12*1024*1024:
        return None
    try:
        with Image.open(BytesIO(deck.zip.read(media)), formats=("JPEG", "PNG", "WEBP")) as image:
            if image.width * image.height > 16_000_000 or "A" in image.getbands() or "transparency" in image.info:
                return None
            image.thumbnail((64, 64))
            return "#%02X%02X%02X" % tuple(ImageStat.Stat(image.convert("RGB")).median)
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def backdrop(deck, chain, theme):
    for part in chain:
        if part not in deck.names:
            continue
        node = deck.tree(part).find("p:cSld/p:bg", NS)
        if node is None:
            continue
        fill = node.find("p:bgPr/a:solidFill", NS)
        if fill is not None:
            return fill_color(fill, theme), False
        blip = node.find("p:bgPr/a:blipFill/a:blip", NS)
        if blip is not None:
            return bitmap_color(deck, part, blip), True
        # A slide background reference can point to a patterned or gradient theme fill.
        # Report its colour only if the referenced style is a solid placeholder fill.
        ref = node.find("p:bgRef", NS)
        theme_part = deck.related(chain[-1], "theme") if chain[-1] else ""
        if ref is not None and theme_part in deck.names:
            fills = deck.tree(theme_part).find("a:themeElements/a:fmtScheme/a:bgFillStyleLst", NS)
            idx = int(ref.get("idx", "0")) - 1001
            if fills is not None and 0 <= idx < len(fills) and local(fills[idx]) == "solidFill":
                ph = fills[idx].find("a:schemeClr", NS)
                if ph is not None and ph.get("val") == "phClr" and not len(ph):
                    return fill_color(ref, theme), False
                return fill_color(fills[idx], theme), False
        return None, False
    return None, False


def text_fonts(shape):
    fonts = Counter()
    for paragraph in shape.findall("p:txBody/a:p", NS):
        for run in paragraph:
            value = (run.findtext("a:t", "", NS) or "").strip()
            if not value:
                continue
            script = "ea" if re.search(r"[\u3000-\u9fff\uac00-\ud7a3]", value) else "latin"
            name = run.find(f"a:rPr/a:{script}", NS)
            if name is None:
                name = paragraph.find(f"a:pPr/a:defRPr/a:{script}", NS)
            face = name.get("typeface", "").strip() if name is not None else ""
            if face and len(face) <= 100 and face.isprintable() and not face.startswith("+"):
                fonts[face] += min(48, len(value))
    return fonts


def strongest(counter):
    return counter.most_common(1)[0][0] if counter else None


def slide_evidence(deck, part):
    from harness_template_deck import box_of, visible
    layout = deck.related(part, "slideLayout")
    master = deck.related(layout, "slideMaster") if layout else ""
    theme = theme_for(deck, master)
    bg, picture_bg = backdrop(deck, (part, layout, master), theme)
    direct_background = deck.tree(part).find("p:cSld/p:bg/p:bgPr/a:solidFill", NS) is not None
    fonts, titles, accents = Counter(), Counter(), Counter()
    anchor = None
    data = drawing = text = 0
    large_image = picture_bg
    for _, name, shape, transform in shape_list(deck.tree(part)):
        nv = shape.find("*/p:cNvPr", NS)
        if nv is not None and nv.get("hidden") in ("1", "true"):
            continue
        box = box_of(shape, transform, (deck.w, deck.h))
        ph = shape.find("p:nvSpPr/p:nvPr/p:ph", NS)
        connector = local(shape) == "cxnSp"
        on_canvas_line = bool(connector and box and 0 <= box[0]+box[2]/2 <= 1 and 0 <= box[1]+box[3]/2 <= 1)
        if (box is None and ph is None) or (box is not None and not (visible(box) or on_canvas_line)):
            continue
        x, y, w, h = box or (0, 0, 0, 0)
        area = max(0, min(1, x+w)-max(0, x)) * max(0, min(1, y+h)-max(0, y))
        blip = picture_blip(shape, include_fills=True)
        fill = shape.find("p:spPr/a:solidFill", NS)
        col = fill_color(fill, theme)
        geometry = shape.find("p:spPr/a:prstGeom", NS)
        rectangle = geometry is not None and geometry.get("prst") == "rect"
        if blip is not None and area >= .13:
            large_image = True
            if area >= .85:
                bg = bitmap_color(deck, part, blip)
                direct_background = False
        elif rectangle and area >= .90:
            if col:
                bg, large_image = col, False
                direct_background = True
            elif fill is not None or shape.find("p:spPr/a:gradFill", NS) is not None:
                direct_background = False
        if col and .0003 <= area <= .65:
            accents[col] += min(10, 1+area*30)
        if local(shape) == "graphicFrame" and any(local(child) in ("chart", "tbl") for child in shape.iter()):
            data += 1
        elif connector or (col and not rectangle and area >= .008):
            drawing += 1
        body = shape.find("p:txBody", NS)
        if body is None or not any((n.text or "").strip() for n in body.iterfind(".//a:t", NS)):
            continue
        text += 1
        used = text_fonts(shape)
        fonts.update(used)
        for run_fill in body.findall(".//a:rPr/a:solidFill", NS):
            run_color = fill_color(run_fill, theme)
            if run_color:
                accents[run_color] += .5
        if (ph is not None and ph.get("type") in ("ctrTitle", "title") or
                re.fullmatch(r"(?:页标题|概念标题|标题|title|headline)(?:\s*\d+)?", name, re.I)):
            titles.update(used)
            if box and anchor is None:
                aligned = shape.find("p:txBody/a:p/a:pPr", NS)
                centered = aligned is not None and aligned.get("algn") == "ctr"
                if w <= .4 and h >= .38:
                    anchor = "side-left" if x+w <= .53 else "side-right" if x >= .47 else "center"
                elif y < .20:
                    anchor = "top-center" if centered else "top-right" if x >= .55 else "top-left"
                else:
                    anchor = "side-left" if x+w <= .53 else "side-right" if x >= .47 else "center"
    mode = ("data" if data else "image" if large_image else "diagram" if drawing >= 3 else
            "text" if text else "unknown")
    return bg, accents, fonts, mode, titles, anchor, direct_background


def cover_color(deck):
    thumb = next((name for name in ("docProps/thumbnail.jpeg","docProps/thumbnail.jpg","docProps/thumbnail.png")
                  if name in deck.names and deck.zip.getinfo(name).file_size <= 4*1024*1024), None)
    if not thumb:
        return None
    try:
        with Image.open(BytesIO(deck.zip.read(thumb)), formats=("JPEG","PNG","WEBP")) as img:
            if img.width*img.height > 16_000_000:
                return None
            img.thumbnail((64, 40))
            sample = img.convert("RGB")
            median = ImageStat.Stat(sample).median
            # Report a sampled colour actually on the page, including photographs.
            pixel = min(sample.getdata(), key=lambda p:sum((a-b)**2 for a,b in zip(p,median)))
            return "#%02X%02X%02X" % pixel
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def deck_visual(deck):
    positions = list(deck.slides)
    # For long decks sample the opening, closing and three positions in between.
    last = len(positions)-1
    indices = range(len(positions)) if last <= 4 else [round(i*last/4) for i in range(5)]
    backgrounds, accents, fonts = Counter(), Counter(), Counter()
    tones, modes, titles, anchors = Counter(), Counter(), Counter(), Counter()
    direct_count = checked = 0
    for i in indices:
        part = positions[i]
        if deck.tree(part).get("show") in ("0", "false"):
            continue
        bg, colors, faces, mode, heading, anchor, direct = slide_evidence(deck, part)
        checked += 1
        direct_count += direct
        weight = 2 if 0 < i < len(positions)-1 else 1
        if bg:
            backgrounds[bg] += weight
        accents.update(colors)
        fonts.update(faces)
        titles.update(heading)
        if anchor:
            anchors[anchor] += weight
        if mode != "unknown":
            modes[mode] += weight
    basis = "slides" if backgrounds else "unknown"
    # The embedded slide thumbnail includes inherited artwork, gradients, scrims and masks.
    # Prefer actual rendered evidence when the native backdrop alone describes little of the deck.
    if direct_count * 2 < checked:
        rendered = cover_color(deck)
        if rendered:
            backgrounds = Counter([rendered])
            basis = "thumbnails"
    for color, weight in backgrounds.items():
        tones["dark" if luminance(color)<125 else "light"] += weight
    bg = strongest(backgrounds)
    # In a deliberate alternating dark/light theme, keep both observed colours.
    tone = "mixed" if len(tones)>1 and min(tones.values())/tones.total() >= .24 else strongest(tones) or "unknown"
    chromatic = Counter({c:n for c,n in accents.items() if c != bg and max(rgb(c))-min(rgb(c)) >= 30 and
                         (not bg or max(abs(a-b) for a,b in zip(rgb(c),rgb(bg))) >= 45)})
    accent = strongest(chromatic)
    colors = list(dict.fromkeys(c for c in (bg, accent, *backgrounds, *chromatic) if c))[:5]
    mode = max(modes, key=lambda k:(modes[k],k=="data", k=="image", k=="diagram")) if modes else "unknown"
    if modes and modes[mode] < modes.total()/2:
        mode = "mixed"
    return dict(tone=tone, background=bg, accent=accent, colors=colors, fonts=[f for f,_ in fonts.most_common(3)],
                layout=mode, titleAnchor=strongest(anchors) or "unknown", titleFont=strongest(titles), paletteBasis=basis)


def safe_visual(deck):
    try:
        return deck_visual(deck)
    except (ValueError, KeyError, IndexError, OSError, BadZipFile, ArithmeticError):
        return unknown_visual()

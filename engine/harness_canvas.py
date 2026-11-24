"""Match the output canvas while retaining placeholder inheritance and animation targets."""
from engine import A, NS, Deck, local
from harness_template_deck import scale_authored_page


def resize_tree(root, factor):
    for node in root.iter():
        tag = local(node)
        if tag in ("off", "chOff", "ext", "chExt") and local(node.getparent()) == "xfrm":
            names = ("x", "y") if tag in ("off", "chOff") else ("cx", "cy")
        elif tag in ("rPr", "defRPr", "endParaRPr"):
            names = ("sz", "kern", "spc")
        elif tag == "bodyPr":
            names = ("lIns", "rIns", "tIns", "bIns", "spcCol")
        elif tag.endswith("pPr") or tag == "pPr":
            names = ("marL", "marR", "indent", "defTabSz")
        elif tag == "tcPr":
            names = ("marL", "marR", "marT", "marB")
        elif tag in ("tab", "gridCol", "tr", "spcPts", "buSzPts"):
            names = ({"tab":"pos", "gridCol":"w", "tr":"h", "spcPts":"val", "buSzPts":"val"}[tag],)
        elif tag == "ln" or tag.startswith("ln") and node.tag.startswith("{"+A+"}"):
            names = ("w",)
        elif tag in ("outerShdw", "innerShdw", "glow", "softEdge", "blur"):
            names = ("dist", "blurRad", "rad")
        else:
            continue
        for name in names:
            value = node.get(name)
            if value is not None and value.lstrip("-").isdigit():
                node.set(name, str(round(int(value)*factor)))


def fit_canvas(data, target, *, native):
    """Only newly authored pages may be letterboxed between different aspect ratios."""
    deck = Deck(data)
    with deck.zip:
        if (deck.w, deck.h) == (target.w, target.h):
            return data
        compatible = abs((target.w/target.h)/(deck.w/deck.h)-1) <= .001
        if native and not compatible:
            raise ValueError(f"模板画幅 {deck.w/914400:.2f} × {deck.h/914400:.2f} 英寸与本稿 "
                             f"{target.w/914400:.2f} × {target.h/914400:.2f} 英寸比例不同，请改用相同宽高比的模板。")
        size = deck.tree(deck.presentation).find("p:sldSz", NS)
        size.set("cx", str(target.w))
        size.set("cy", str(target.h))
        size.attrib.pop("type", None)
        deck.changed.add(deck.presentation)
        for part in deck.names:
            if not part.endswith(".xml") or "/_rels/" in part:
                continue
            page_layer = part.startswith(("ppt/slides/", "ppt/slideLayouts/", "ppt/slideMasters/"))
            if compatible and (page_layer or part.startswith(("ppt/charts/", "ppt/theme/", "ppt/diagrams/"))
                               or part == deck.presentation):
                resize_tree(deck.tree(part), min(target.w/deck.w, target.h/deck.h))
            elif page_layer and not compatible:
                scale_authored_page(deck.tree(part), target, deck)
            else:
                continue
            deck.changed.add(part)
        return deck.save()

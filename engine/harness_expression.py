"""Place optional editable expressions into the finished slide, including skill-authored pages."""
from copy import deepcopy
from hashlib import sha256

from lxml import etree as ET
from pptx.oxml.shapes.picture import CT_Picture

from election_opening import read_photo
from engine import A, CT, NS, PKG, Deck, local, relpart, shape_list, text_in
from harness_template_deck import box_of, relationship


def find_text(slide, text):
    """Locate a sentence across separate formatting runs or an author-inserted line break."""
    needle = "".join(text.split())
    hits = []
    if not needle:
        return hits
    for body in slide.findall(".//p:txBody", NS):
        chars, slots = [], []
        for node in body.findall(".//a:r/a:t", NS):
            for offset, char in enumerate(node.text or ""):
                if not char.isspace():
                    chars.append(char)
                    slots.append((node, offset))
        compact = "".join(chars)
        pos = compact.find(needle)
        while pos >= 0:
            hits.append(slots[pos:pos+len(needle)])
            pos = compact.find(needle, pos+1)
    return hits


def emoji_run(node, symbol, offset, remove):
    run = node.getparent()
    paragraph = run.getparent()
    before, after = node.text[:offset], node.text[offset+remove:]
    insertion = paragraph.index(run)
    for value, use_emoji_font in ((before, False), (symbol, True), (after, False)):
        if not value:
            continue
        part = deepcopy(run)
        part.find("a:t", NS).text = value
        if use_emoji_font:
            prop = part.find("a:rPr", NS)
            if prop is None:
                prop = ET.Element(f"{{{A}}}rPr")
                part.insert(0, prop)
            for child in list(prop):
                if local(child) in {"latin", "ea", "cs", "sym"}:
                    prop.remove(child)
            font_index = next((i for i, child in enumerate(prop)
                               if local(child) in {"hlinkClick","hlinkMouseOver","rtl","extLst"}), len(prop))
            for font in ("latin", "ea", "cs"):
                prop.insert(font_index, ET.Element(f"{{{A}}}{font}", typeface="Segoe UI Emoji"))
                font_index += 1
        paragraph.insert(insertion, part)
        insertion += 1
    paragraph.remove(run)


def decorate_text(slide, spec):
    symbol = spec["symbol"]
    plain = spec["textBefore"]
    # Node stores Python-compatible code point offsets, including joined emoji and CJK characters.
    compact_offset = len("".join(plain[:spec["offsetChars"]].split()))
    decorated = find_text(slide, spec["textAfter"])
    hits = decorated or find_text(slide, plain)
    if len(hits) != 1:
        raise ValueError("请在实际 PPT 页保留一处完整的目标句，或改选可唯一定位的文字来加入 Emoji。")
    hit = hits[0]
    if decorated:
        end = compact_offset+len(symbol)-1
        node, offset = hit[compact_offset]
        last, last_pos = hit[end]
        if node is not last:
            # Existing native glyphs span multiple runs. Preserve their original formatting.
            return
        remove = last_pos-offset+1
    elif compact_offset:
        node, pos = hit[compact_offset-1]
        offset, remove = pos+1, 0
    else:
        node, offset = hit[0]
        remove = 0
    emoji_run(node, symbol, offset, remove)


def choose_box(slide, size, image_ratio, meme):
    occupied = []
    trim = []
    anchors = []
    preferred = meme.get("position","auto")
    near = "".join(meme.get("beside","").split())
    for _, name, shape, transform in shape_list(slide):
        box = box_of(shape, transform, size)
        if not box:
            continue
        x,y,w,h = box
        full_page = x<=.025 and y<=.025 and x+w>=.975 and y+h>=.975
        nv = shape.find("*/p:cNvPr", NS)
        if nv is not None and nv.get("hidden") in ("true","1"):
            continue
        has_text = bool(text_in(shape.find("p:txBody",NS)).strip())
        has_content = local(shape) in {"graphicFrame","pic"} or shape.find("p:spPr/a:blipFill",NS) is not None
        if has_text or (has_content and not full_page):
            # The plain authoring engine gives even a four-character sentence a page-wide text
            # frame. Reserve its unused tail only when a conservative one-line measure fits.
            body = shape.find("p:txBody",NS)
            if has_text and (name=="标题" or name.startswith("论点 ")) and transform==(1,1,0,0):
                paragraphs = body.findall("a:p",NS)
                xf = shape.find("p:spPr/a:xfrm",NS)
                frame = shape.find("p:nvSpPr/p:cNvSpPr",NS)
                if (len(paragraphs)==1 and xf is not None and not xf.get("rot") and
                    frame is not None and frame.get("txBox")=="1" and
                    shape.find("p:spPr/a:noFill",NS) is not None and
                    not any(p.get("algn","l")!="l" for p in body.findall("a:p/a:pPr",NS))):
                    runs = paragraphs[0].findall("a:r",NS)
                    if runs and all(r.find("a:rPr",NS) is not None and r.find("a:rPr",NS).get("sz") for r in runs):
                        width = sum(len(r.findtext("a:t","",NS))*int(r.find("a:rPr",NS).get("sz"))*127
                                    for r in runs)*1.35/size[0]+.03
                        if width<w:
                            trim.append((xf, (x,y,x+w,y+h), width))
                            w = width
            occupied.append((x,y,x+w,y+h))
            if near and near in "".join(text_in(body).split()):
                anchors.append((x+w/2,y+h/2))
    corners = ["bottom-right","bottom-left","top-right","top-left"]
    if preferred in corners:
        corners.remove(preferred)
        corners.insert(0, preferred)
    canvas_ratio = size[0]/size[1]
    if near and len(anchors)!=1:
        raise ValueError("请为梗图的 beside 填写本页唯一出现的一小段原话，或留空自动找位。")
    supporting = meme.get("size")=="supporting"
    for max_h in ((.51,.435,.36,.29) if supporting else (.29,.245,.20,.16)):
        w = min(.40 if supporting else .29, max_h*image_ratio/canvas_ratio)
        h = w*canvas_ratio/image_ratio
        if min(w,h) < .065:
            continue
        candidates = []
        for corner in corners:
            for dx,dy in ((0,0),(0,.13),(.12,0),(0,.26),(.24,0),(.12,.22),(.30,.31)):
                x = .042+dx if corner.endswith("left") else .958-dx-w
                y = .06+dy if corner.startswith("top") else .94-dy-h
                if all(x+w+.012<=l or r+.012<=x or y+h+.016<=t or b+.016<=y
                       for l,t,r,b in occupied):
                    distance = 0
                    if anchors:
                        ax,ay = anchors[0]
                        distance = ((ax-x-w/2)*canvas_ratio)**2+(ay-y-h/2)**2
                    candidates.append((corner!=preferred and preferred!="auto",distance,len(candidates),x,y))
        if candidates:
            *_,x,y = min(candidates)
            for xf,(left,top,right,bottom),width in trim:
                if x<right and left<x+w and y<bottom and top<y+h:
                    xf.find("a:ext",NS).set("cx",str(round(width*size[0])))
            return tuple(round(v*d) for v,d in zip((x,y,w,h),size*2))
    raise ValueError("本页没有可放下梗图的留白。请在原生设计中为它留出一角，缩短本页文字或省略该图。")


def insert_meme(deck, part, slide, meme, root):
    raw,width,height = read_photo(root,meme["asset"])
    x,y,cx,cy = choose_box(slide,(deck.w,deck.h),width/height,meme)
    ext, mime = ("png","image/png") if raw.startswith(b"\x89PNG") else ("jpeg","image/jpeg")
    media = f"ppt/media/expression-{sha256(raw).hexdigest()}.{ext}"
    if media not in deck.names and media not in deck.media:
        deck.media[media] = raw
        types = deck.tree("[Content_Types].xml")
        if not any(n.get("Extension","").lower()==ext and n.get("ContentType")==mime for n in types):
            ET.SubElement(types, f"{{{CT}}}Override", PartName="/"+media, ContentType=mime)
            deck.changed.add("[Content_Types].xml")
    relations = relpart(part)
    if relations not in deck.names and relations not in deck.parts:
        deck.parts[relations] = ET.Element(f"{{{PKG}}}Relationships",nsmap={None:PKG})
    rid = relationship(deck.tree(relations),part,"image",media)
    deck.changed.add(relations)
    tree = slide.find("p:cSld/p:spTree",NS)
    next_id = max([0]+[int(e.get("id","0")) for e in tree.findall(".//p:cNvPr",NS)])+1
    description = "\n".join(s for s in (meme["alt"],meme["purpose"],meme.get("source")) if s)
    picture = CT_Picture.new_pic(next_id,"表情包 · "+meme["alt"],description,rid,x,y,cx,cy)
    ext_list = tree.find("p:extLst",NS)
    tree.insert(tree.index(ext_list) if ext_list is not None else len(tree),picture)


def place_memes(deck_path, slides, root):
    """Preserve the original editable shapes, timing IDs, and all unrelated package parts."""
    deck = Deck(deck_path.read_bytes())
    with deck.zip:
        for index, (part,spec) in enumerate(zip(deck.slides,slides),1):
            if not (spec.get("emoji") or spec.get("meme")):
                continue
            slide = deck.tree(part)
            try:
                if spec.get("emoji"):
                    decorate_text(slide,spec["emoji"])
                if spec.get("meme"):
                    insert_meme(deck,part,slide,spec["meme"],root)
            except ValueError as exc:
                raise ValueError(f"第 {index} 页：{exc}") from exc
            deck.changed.add(part)
        result = deck.save()
    deck_path.write_bytes(result)

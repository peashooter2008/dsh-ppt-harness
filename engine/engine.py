"""Read, edit and write ordinary PPTX packages without launching Office."""

import base64
import binascii
from copy import deepcopy
from difflib import SequenceMatcher
import hashlib
import io
import math
import posixpath
import re
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

from lxml import etree as ET
from PIL import Image, ImageOps, UnidentifiedImageError


P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
DIRECTIONS = {"left":"l", "right":"r", "up":"u", "down":"d"}
NS = {"p": P, "a": A, "r": R}
MIB = 1024 * 1024
EMU_PER_PX = 9525


def el(parent, name, **attrs):
    return ET.SubElement(parent, f"{{{P}}}{name}", {k: str(v) for k, v in attrs.items()})


def local(node):
    return ET.QName(node).localname if isinstance(node.tag, str) else ""


def xml(data):
    if len(data) > 48 * MIB:
        raise ValueError("单个 XML 超过 48 MiB。")
    try:
        root = ET.fromstring(data, ET.XMLParser(resolve_entities=False, no_network=True, load_dtd=False))
    except ET.XMLSyntaxError as exc:
        raise ValueError("PPTX 包含无法读取的 XML。") from exc
    if root.getroottree().docinfo.doctype:
        raise ValueError("PPTX 包含不支持的文档类型声明。")
    return root


def relpart(part):
    directory, filename = posixpath.split(part)
    return posixpath.join(directory, "_rels", filename + ".rels")


def target(part, relative):
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(part), unquote(relative))).lstrip("/")
    if resolved.startswith("../") or ":" in resolved or "\\" in resolved:
        raise ValueError("包内部件路径异常。")
    return resolved


def walk_shapes(tree, transform=(1, 1, 0, 0)):
    if tree is None:
        return
    for s in tree:
        tag = local(s)
        if s.tag == f"{{{MC}}}AlternateContent":
            branch = next((c for c in s if local(c) == "Choice"), None)
            if branch is None:
                branch = next((c for c in s if local(c) == "Fallback"), None)
            yield from walk_shapes(branch, transform)
        elif tag == "grpSp":
            xf = s.find("p:grpSpPr/a:xfrm", NS)
            scale_x, scale_y, shift_x, shift_y = transform
            if xf is not None:
                x, y = pair(xf, "off", "x", "y")
                w, h = pair(xf, "ext", "cx", "cy")
                cx, cy = pair(xf, "chOff", "x", "y")
                cw, ch = pair(xf, "chExt", "cx", "cy")
                sx, sy = w / cw if cw else 1, h / ch if ch else 1
                transform_child = (scale_x*sx, scale_y*sy, shift_x+scale_x*(x-cx*sx), shift_y+scale_y*(y-cy*sy))
            else:
                transform_child = transform
            yield from walk_shapes(s, transform_child)
        elif tag in {"sp", "pic", "cxnSp", "graphicFrame", "contentPart"}:
            nv = s.find("*/p:cNvPr", NS)
            if nv is not None:
                yield nv.get("id"), nv.get("name", ""), s, transform


def pair(xf, child, x, y):
    node = xf.find(f"a:{child}", NS)
    return (int(node.get(x, 0)), int(node.get(y, 0))) if node is not None else (0, 0)


def shape_list(root):
    return walk_shapes(root.find("p:cSld/p:spTree", NS))


def text_in(body):
    if body is None:
        return ""
    return "\n".join("".join("\n" if local(s) == "br" else (s.findtext("a:t", "", NS) or "")
                             for s in p if local(s) in {"br", "r", "fld"}) for p in body.findall("a:p", NS))


def write_text(body, value):
    """Retain paragraph properties and the run formatting of matching portions."""
    if not isinstance(value, str) or len(value) > 32767:
        raise ValueError("每个文字对象最多支持 32767 个字符。")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if value == text_in(body):
        return False
    old = list(body.findall("a:p", NS))
    lines = value.split("\n")
    for i, line in enumerate(lines):
        template = old[min(i, len(old)-1)] if old else None
        para = deepcopy(template) if template is not None else ET.Element(f"{{{A}}}p")
        children = [r for r in para if local(r) in {"r", "br", "fld"}]
        oldtext, owners, styles = "", [], []
        for run in children:
            if local(run) == "br":
                segment = "\n"
            else:
                segment = run.findtext("a:t", "", NS) or ""
            owners.extend([len(styles)] * len(segment))
            styles.append(run.find("a:rPr", NS))
            oldtext += segment
            para.remove(run)
        mapped = [0] * len(line)
        if oldtext and line:
            # Bound work on unusually long paragraphs while preserving short rich-text spans.
            if len(line) * len(oldtext) <= 1_000_000:
                for op, a, b, c, d in SequenceMatcher(None, oldtext, line, autojunk=False).get_opcodes():
                    if op == "equal":
                        mapped[c:d] = owners[a:b]
                    else:
                        mapped[c:d] = [owners[min(a, len(owners)-1)]] * (d-c)
            else:
                mapped = [owners[min(len(owners)-1, k*len(owners)//len(line))] for k in range(len(line))]
        cursor = 0
        end_props = para.find("a:endParaRPr", NS)
        while cursor < len(line):
            end = cursor + 1
            while end < len(line) and mapped[end] == mapped[cursor]:
                end += 1
            run = ET.Element(f"{{{A}}}r")
            if styles and styles[mapped[cursor]] is not None:
                run.append(deepcopy(styles[mapped[cursor]]))
            ET.SubElement(run, f"{{{A}}}t").text = line[cursor:end]
            if end_props is None:
                para.append(run)
            else:
                end_props.addprevious(run)
            cursor = end
        if i < len(old):
            body.replace(old[i], para)
        else:
            body.append(para)
    for para in old[len(lines):]:
        body.remove(para)
    return True


class Deck:
    def __init__(self, data):
        if not isinstance(data, bytes) or len(data) > 256*MIB:
            raise ValueError("请选择 256 MiB 以内的 PPTX。")
        self._open(io.BytesIO(data))

    @classmethod
    def from_stream(cls,source,size):
        if not 0<size<=256*MIB:
            raise ValueError("请选择 256 MiB 以内的 PPTX。")
        deck=cls.__new__(cls)
        deck._open(source)
        return deck

    def _open(self,source):
        self.zip = ZipFile(source)
        infos = self.zip.infolist()
        self.names = {i.filename for i in infos}
        if (len(infos) > 20000 or len(infos) != len(self.names) or
                sum(i.file_size for i in infos) > 768*MIB or any(
                    i.flag_bits & 1 or i.file_size > 256*MIB or i.filename.startswith("/") or
                    ".." in i.filename.split("/") or "\\" in i.filename for i in infos)):
            raise ValueError("文件包含不支持的条目、加密条目或过大的解压内容。")
        self.parts, self.changed, self.media = {}, set(), {}
        self.presentation = self.related("", "officeDocument")
        types = self.tree("[Content_Types].xml")
        main = next((e.get("ContentType") for e in types if e.get("PartName") == "/" + self.presentation), "")
        if main != "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml":
            raise ValueError("请选择普通 .pptx 文件，可先将模板另存为 PowerPoint 演示文稿。")
        root = self.tree(self.presentation)
        if root.tag != f"{{{P}}}presentation":
            raise ValueError("当前支持 PowerPoint 通用 OOXML 格式。")
        self.list = root.find("p:sldIdLst", NS)
        children = [] if self.list is None else self.list.findall("p:sldId", NS)
        if not children or len(children) > 1000:
            raise ValueError("演示文稿须包含 1 至 1000 页。")
        rels = self.rels(self.presentation)
        self.slides = {}
        for child in children:
            row = rels.get(child.get(f"{{{R}}}id"))
            if not row or row[0] != "slide" or row[1] not in self.names or row[1] in self.slides:
                raise ValueError("幻灯片顺序或引用异常。")
            self.slides[row[1]] = child
        size = root.find("p:sldSz", NS)
        self.w, self.h = (int(size.get(k, 0)) for k in ("cx", "cy")) if size is not None else (9144000, 6858000)
        if self.w <= 0 or self.h <= 0:
            raise ValueError("页面尺寸无效。")
        self.thumbs = {}
        self.media_digests = {}
        self.preview_bytes = 0

    def tree(self, part):
        if part not in self.parts:
            if part not in self.names:
                raise ValueError("找不到演示文稿部件 " + part)
            self.parts[part] = xml(self.zip.read(part))
        return self.parts[part]

    def rels(self, part):
        key = relpart(part)
        if key not in self.names and key not in self.parts:
            return {}
        return {e.get("Id"): (e.get("Type","").rsplit("/",1)[-1], target(part,e.get("Target","")))
                for e in self.tree(key) if e.get("TargetMode","").lower() != "external"}

    def related(self, part, kind):
        return next((p for t,p in self.rels(part).values() if t == kind), "")

    def image_digest(self, path):
        if path not in self.names:
            return None
        if path not in self.media_digests:
            with self.zip.open(path) as stream:
                self.media_digests[path]=hashlib.file_digest(stream,"sha256").hexdigest()
        return self.media_digests[path]

    def thumb(self, path):
        if path in self.thumbs:
            return self.thumbs[path]
        result = None
        if path in self.names and self.zip.getinfo(path).file_size <= 24*MIB and self.preview_bytes < 24*MIB:
            try:
                with Image.open(io.BytesIO(self.zip.read(path)), formats=["JPEG","PNG","GIF","BMP","WEBP","TIFF"]) as im:
                    if im.width * im.height <= 30_000_000:
                        im.thumbnail((720, 540))
                        im = ImageOps.exif_transpose(im)
                        buf = io.BytesIO()
                        transparent = "A" in im.getbands() or "transparency" in im.info
                        mime = "png" if transparent else "jpeg"
                        im.convert("RGBA" if transparent else "RGB").save(buf, "PNG" if transparent else "JPEG", **({} if transparent else {"quality":80}))
                        result = f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode("ascii")
                        self.preview_bytes += len(result)
            except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
                pass
        self.thumbs[path] = result
        return result

    def save(self):
        out = io.BytesIO()
        with ZipFile(out, "w", compression=ZIP_DEFLATED) as z:
            z.comment = self.zip.comment
            for info in self.zip.infolist():
                if info.filename in self.changed:
                    content = ET.tostring(self.parts[info.filename], encoding="UTF-8", xml_declaration=True, standalone=True)
                else:
                    content = self.zip.read(info)
                z.writestr(deepcopy(info), content)
            for key in self.changed - self.names:
                z.writestr(key, ET.tostring(self.parts[key], encoding="UTF-8", xml_declaration=True, standalone=True))
            for path, content in self.media.items():
                z.writestr(path, content)
        return out.getvalue()


def paint(node, theme, fallback):
    if node is None:
        return fallback
    for c in node:
        tag = local(c)
        if tag == "srgbClr":
            value = c.get("val", "")
        elif tag == "sysClr":
            value = c.get("lastClr", "")
        elif tag == "schemeClr":
            name = c.get("val", "")
            value = theme.get({"tx1":"dk1","bg1":"lt1","tx2":"dk2","bg2":"lt2"}.get(name,name), "")
        else:
            continue
        if re.fullmatch(r"[A-Fa-f0-9]{6}", value):
            return "#" + value
    return fallback


def read_background(props, theme, inherited):
    if props is None:
        return inherited
    gradient=props.find("a:gradFill",NS)
    if gradient is not None:
        stops=sorted(gradient.findall("a:gsLst/a:gs",NS),key=lambda n:int(n.get("pos",0)))
        linear=gradient.find("a:lin",NS)
        if len(stops)==2 and linear is not None:
            start,end=[paint(n,theme,None) for n in stops]
            if start and end:
                return {"type":"gradient","from":start,"to":end,
                        "angle":round((int(linear.get("ang",0))/60000)%360,5)}
    return paint(props.find("a:solidFill",NS),theme,inherited)


def theme_for(deck, master):
    p = deck.related(master, "theme") if master else ""
    if p not in deck.names:
        return {}
    root = deck.tree(p).find("a:themeElements/a:clrScheme", NS)
    return {} if root is None else {local(c): paint(c, {}, "#000000").lstrip("#") for c in root}


def placeholders(deck, part):
    if part not in deck.names:
        return {}
    items = {}
    for _, _, shape, _ in shape_list(deck.tree(part)):
        ph = shape.find("*/p:nvPr/p:ph", NS)
        if ph is not None:
            items[ph.get("idx", "0")] = shape
            items[ph.get("type", "body")] = shape
    return items


def cues_for(root):
    timings = root.findall(".//p:timing", NS)
    if not timings:
        return [], True
    timing = timings[0]
    states = {"clickEffect":"click", "withEffect":"with", "afterEffect":"after"}
    effects = []
    for n in timing.iter(f"{{{P}}}cTn"):
        if n.get("nodeType") not in states:
            continue
        ids = list(dict.fromkeys(t.get("spid") for t in n.iter(f"{{{P}}}spTgt") if t.get("spid")))
        for sid in ids:
            effects.append({"id":sid, "effect":{"1":"appear", "10":"fade", "22":"wipe"}.get(n.get("presetID"), "original"),
                            "trigger":states[n.get("nodeType")]})
    ids = [c["id"] for c in effects]
    # Only replace a sequence with exactly the structure we can regenerate losslessly.
    editable = len(timings) == 1 and timing.getparent() is root and bool(effects) and len(set(ids)) == len(ids)
    if editable:
        signature = _signature(timing)
        editable = any(signature == _signature(make_timing(ids,effect)) for effect in ("appear","fade"))
    return effects, editable


def _signature(node):
    return (node.tag, tuple(sorted(node.attrib.items())), (node.text or "").strip(),
            tuple(_signature(c) for c in node if isinstance(c.tag,str)))


def make_timing(ids,effect="appear",with_previous=()):
    timing = ET.Element(f"{{{P}}}timing")
    top = el(el(el(timing, "tnLst"), "par"), "cTn", id=1, dur="indefinite", restart="never",nodeType="tmRoot")
    seq = el(el(top, "childTnLst"), "seq", concurrent=1, nextAc="seek")
    main = el(el(seq, "cTn", id=2, dur="indefinite", nodeType="mainSeq"), "childTnLst")
    next_id = 3
    click_group = None
    for sid in ids:
        together = click_group is not None and sid in with_previous
        parent = click_group if together else main
        for level in ((2,) if together else (0,1,2)):
            delay = "indefinite" if level==0 else "0"
            attrs = {"id":next_id, "fill":"hold"}
            if level == 2:
                attrs.update(presetID=10 if effect=="fade" else 1, presetClass="entr", presetSubtype=0, grpId=0, nodeType="withEffect" if together else "clickEffect")
            n = el(el(parent,"par"), "cTn", **attrs)
            el(el(n,"stCondLst"),"cond",delay=delay)
            parent = el(n,"childTnLst")
            if level==1:
                click_group=parent
            next_id += 1
        setting = el(parent,"set")
        behavior = el(setting,"cBhvr")
        node = el(behavior,"cTn",id=next_id,dur=1,fill="hold")
        next_id += 1
        el(el(node,"stCondLst"),"cond",delay=0)
        el(el(behavior,"tgtEl"),"spTgt",spid=sid)
        el(el(behavior,"attrNameLst"),"attrName").text = "style.visibility"
        el(el(setting,"to"),"strVal",val="visible")
        if effect=="fade":
            fade=el(parent,"animEffect",transition="in",filter="fade")
            behavior=el(fade,"cBhvr")
            el(behavior,"cTn",id=next_id,dur=450)
            el(el(behavior,"tgtEl"),"spTgt",spid=sid)
            next_id+=1
    for name, event in (("prevCondLst","onPrev"),("nextCondLst","onNext")):
        el(el(el(el(seq,name),"cond",evt=event,delay=0),"tgtEl"),"sldTgt")
    builds = el(timing,"bldLst")
    for sid in ids:
        el(builds,"bldP",spid=sid,grpId=0)
    return timing


def transition_spec(value):
    if not isinstance(value,dict) or value.keys()-{"type","durationMs","direction"}:
        raise ValueError("转场支持 type、durationMs 与 direction，翻页由讲者手动控制。")
    kind=value.get("type")
    if kind not in ("none","fade","push","wipe"):
        raise ValueError("转场类型请选择 none、fade、push 或 wipe。")
    if kind=="none":
        if len(value)!=1:
            raise ValueError("直接切换请只填写 type=none。")
        return {"type":"none"}
    duration=value.get("durationMs",550)
    if type(duration) is not int or not 100<=duration<=3000:
        raise ValueError("转场时长 durationMs 需为 100 至 3000 的整数毫秒。")
    result={"type":kind,"durationMs":duration}
    if kind in ("push","wipe"):
        direction=value.get("direction","left")
        if not isinstance(direction,str) or direction not in DIRECTIONS:
            raise ValueError("转场方向请选择 left、right、up 或 down。")
        result["direction"]=direction
    elif "direction" in value:
        raise ValueError("淡化转场无需指定方向。")
    return result


def add_transition(slide,spec):
    """Write both the exact-time Office branch and the standard speed fallback."""
    if spec["type"]=="none":
        return
    alt=ET.SubElement(slide,f"{{{MC}}}AlternateContent",nsmap={"mc":MC})
    choice=ET.SubElement(alt,f"{{{MC}}}Choice",Requires="p14",nsmap={"p14":P14})
    fallback=ET.SubElement(alt,f"{{{MC}}}Fallback")
    duration=spec["durationMs"]
    speed="fast" if duration<500 else "med" if duration<=1000 else "slow"
    for parent in (choice,fallback):
        tr=el(parent,"transition",spd=speed,advClick="1")
        if parent is choice:
            tr.set(f"{{{P14}}}dur",str(duration))
        node=el(tr,spec["type"])
        if "direction" in spec:
            node.set("dir",DIRECTIONS[spec["direction"]])


def slide_transition(slide):
    # Only inspect slide-level transition or its AlternateContent, never object timing.
    paths=["p:transition","{"+MC+"}AlternateContent/{"+MC+"}Choice/p:transition",
           "{"+MC+"}AlternateContent/{"+MC+"}Fallback/p:transition"]
    for path in paths:
        tr=slide.find(path,NS)
        if tr is not None:
            break
    else:
        return {"type":"none","manual":True}
    kind=local(tr[0]) if len(tr) else "none"
    result={"type":kind,"manual":tr.get("advClick","1") not in ("0","false") and tr.get("advTm") is None}
    duration=tr.get(f"{{{P14}}}dur")
    if duration and duration.isdecimal():
        result["durationMs"]=int(duration)
    if kind in ("push","wipe"):
        direction=tr[0].get("dir","l")
        result["direction"]=next((d for d,v in DIRECTIONS.items() if v==direction),direction)
    return result


def inspect_slide(deck, part):
    slide = deck.tree(part)
    layout = deck.related(part, "slideLayout")
    master = deck.related(layout,"slideMaster") if layout else ""
    theme = theme_for(deck, master)
    styles, master_styles = placeholders(deck,layout), placeholders(deck,master)
    bg = "#FFFFFF"
    for parent in (master,layout,part):
        if parent in deck.names:
            bg = read_background(deck.tree(parent).find("p:cSld/p:bg/p:bgPr", NS), theme, bg)
    rels = deck.rels(part)
    objects, title, first_text = [], "", ""
    for sid,name,shape,transform in shape_list(slide):
        if len(objects) >= 8000:
            raise ValueError("单张幻灯片的可识别对象超过 8000 个。")
        ph = shape.find("*/p:nvPr/p:ph",NS)
        sources = [shape]
        if ph is not None:
            for lookup in (styles,master_styles):
                item = lookup.get(ph.get("idx","0"))
                if item is None:
                    item = lookup.get(ph.get("type","body"))
                if item is not None:
                    sources.append(item)
        xf = None
        for src in sources:
            xf = src.find("p:spPr/a:xfrm",NS)
            if xf is None:
                xf = src.find("p:xfrm",NS)
            if xf is not None:
                break
        x,y = pair(xf,"off","x","y") if xf is not None else (0,0)
        w,h = pair(xf,"ext","cx","cy") if xf is not None else (0,0)
        sx,sy,dx,dy = transform
        body = shape.find("p:txBody",NS)
        text = text_in(body)
        tag = local(shape)
        kind = ("image" if tag == "pic" else "text" if text or (ph is not None and body is not None)
                else "shape" if tag in {"sp","cxnSp"} else "other")
        font, color, fill = 18, "#202020", "transparent"
        for src in reversed(sources):
            fill = paint(src.find("p:spPr/a:solidFill", NS), theme, fill)
            if src.find("p:spPr/a:noFill", NS) is not None:
                fill = "transparent"
            for style in ("p:txBody/a:lstStyle/a:lvl1pPr/a:defRPr","p:txBody/a:p/a:pPr/a:defRPr","p:txBody/a:p/a:r/a:rPr"):
                rpr = src.find(style,NS)
                if rpr is not None:
                    font = int(rpr.get("sz",font*100)) / 100
                    color = paint(rpr.find("a:solidFill",NS),theme,color)
        image = image_key = None
        blip = shape.find("p:blipFill/a:blip",NS)
        if blip is not None:
            ref = rels.get(blip.get(f"{{{R}}}embed"))
            if ref and ref[0]=="image":
                image = deck.thumb(ref[1])
                image_key = ref[1]
        if text and not first_text:
            first_text = text
        if text and ph is not None and ph.get("type") in {"title","ctrTitle"}:
            title = text
        align = shape.find("p:txBody/a:p/a:pPr", NS)
        bbox = [(x*sx+dx)/deck.w,(y*sy+dy)/deck.h,w*sx/deck.w,h*sy/deck.h]
        crop = shape.find("p:blipFill/a:srcRect", NS)
        objects.append({"id":sid,"name":name,"type":kind,"text":text,"x":bbox[0],"y":bbox[1],
                        "w":bbox[2],"h":bbox[3],"fontSize":font,"color":color,"fill":fill,"image":image,"imageKey":image_key,
                        "imageSha256":deck.image_digest(image_key) if image_key else None,
                        "rotation":int(xf.get("rot",0))/60000 if xf is not None else 0,
                        "geometryEditable":xf is not None, "cropEditable":kind == "image" and blip is not None,
                        "crop":{k: int(crop.get(k[0],0))/100000 if crop is not None else 0
                                for k in ("left","right","top","bottom")},
                        "align": {"ctr":"center","r":"right"}.get(align.get("algn") if align is not None else "", "left"),
                        "geometry":shape.find("p:spPr/a:prstGeom",NS).get("prst") if shape.find("p:spPr/a:prstGeom",NS) is not None else None})
    cues, editable = cues_for(slide)
    previewable=editable
    if cues and not editable and any(c["trigger"]=="with" for c in cues):
        linked={c["id"] for c in cues if c["trigger"]=="with"}
        modeled=make_timing([c["id"] for c in cues],cues[0]["effect"],linked)
        timing=slide.find("p:timing",NS)
        previewable=timing is not None and _signature(modeled)==_signature(timing)
    if not title:
        headings=[o for o in objects if o["text"].strip() and o["y"]<.38 and len(o["text"].strip())>=2]
        title=max(headings,key=lambda o:(o["name"]=="标题",o["fontSize"],-o["y"]),default={}).get("text","")
    return {"id":part,"slideId":deck.slides[part].get("id"),"title":(title or first_text or "未命名页面")[:120],"background":bg,
            "objects":objects,"cues":cues,"cuesEditable":editable,"cuesPreviewable":previewable,"transition":slide_transition(slide)}


def inspect_deck(data):
    try:
        deck = Deck(data)
        with deck.zip:
            return {"width":deck.w/EMU_PER_PX, "height":deck.h/EMU_PER_PX,
                    "slides":[inspect_slide(deck, part) for part in deck.slides]}
    except (BadZipFile, KeyError, OSError, NotImplementedError, OverflowError) as exc:
        raise ValueError("无法读取此 PPTX 压缩包。") from exc


def picture_blip(shape, include_fills=False):
    if local(shape) == "pic":
        return shape.find("p:blipFill/a:blip", NS)
    if include_fills and local(shape) == "sp":
        return shape.find("p:spPr/a:blipFill/a:blip", NS)
    if include_fills and local(shape) == "bgPr":
        return shape.find("a:blipFill/a:blip", NS)
    return None


def replace_picture(deck, part, shape, url, *, include_fills=False):
    blip = picture_blip(shape, include_fills)
    if blip is None:
        raise ValueError("选中对象不是可替换的图片。")
    if not isinstance(url,str) or len(url) > 20*MIB:
        raise ValueError("图片过大，请选择 12 MiB 以内的 PNG 或 JPEG。")
    match = re.fullmatch(r"data:image/(png|jpeg|jpg);base64,([A-Za-z0-9+/=]+)",url)
    if not match:
        raise ValueError("仅支持 PNG 或 JPEG 图片。")
    try:
        raw = base64.b64decode(match[2],validate=True)
        if len(raw) > 12*MIB:
            raise ValueError("替换图片超过 12 MiB。")
        with Image.open(io.BytesIO(raw),formats=["PNG","JPEG"]) as img:
            if img.width * img.height > 40_000_000:
                raise ValueError("替换图片超过 4000 万像素。")
            ext = "png" if img.format == "PNG" else "jpeg"
            if ext != ("png" if match[1]=="png" else "jpeg"):
                raise ValueError("图片格式与声明不符。")
            img.verify()
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("图片编码无效。") from exc
    path = "ppt/media/studio-" + hashlib.sha256(raw).hexdigest() + "." + ext
    if path in deck.names:
        if deck.zip.read(path) != raw:
            raise ValueError("图片部件名冲突。")
    else:
        deck.media[path] = raw
    types = deck.tree("[Content_Types].xml")
    if not any((n.get("Extension","").lower()==ext or n.get("PartName")=="/"+path)
               and n.get("ContentType")=="image/"+ext for n in types):
        ET.SubElement(types,f"{{{CT}}}Override",PartName="/"+path,ContentType="image/"+ext)
        deck.changed.add("[Content_Types].xml")
    rp = relpart(part)
    if rp not in deck.parts and rp not in deck.names:
        deck.parts[rp] = ET.Element(f"{{{PKG}}}Relationships",nsmap={None:PKG})
    rels = deck.tree(rp)
    name = posixpath.relpath(path,posixpath.dirname(part))
    rid = next((r.get("Id") for r in rels if r.get("Type")==R+"/image" and r.get("Target")==name),None)
    if rid is None:
        taken = {r.get("Id") for r in rels}
        idx = 1
        while "rIdStudio"+str(idx) in taken:
            idx += 1
        rid = "rIdStudio"+str(idx)
        ET.SubElement(rels,f"{{{PKG}}}Relationship",Id=rid,Type=R+"/image",Target=name)
        deck.changed.add(rp)
    blip.set(f"{{{R}}}embed",rid)
    blip.attrib.pop(f"{{{R}}}link",None)
    # SVG-enhanced pictures carry a second image reference that supersedes the bitmap.
    for elem in list(blip.iterdescendants()):
        if local(elem) in {"svgBlip","imgLayer"}:
            elem.getparent().remove(elem)
    deck.changed.add(part)


def update_order(deck, order):
    if (not isinstance(order,list) or not order or any(not isinstance(s,str) or s not in deck.slides for s in order)
            or len(set(order)) != len(order)):
        raise ValueError("页面顺序必须由已有页面组成，至少保留一页且不能重复。")
    if order == list(deck.slides):
        return
    for node in deck.slides.values():
        deck.list.remove(node)
    for part in order:
        deck.list.append(deck.slides[part])
    deck.changed.add(deck.presentation)
    kept = {deck.slides[part].get("id") for part in order}
    dropped_rids = {node.get(f"{{{R}}}id") for path,node in deck.slides.items() if path not in order}
    root = deck.tree(deck.presentation)
    for node in root.findall(".//p:custShow/p:sldLst/p:sld",NS):
        if node.get(f"{{{R}}}id") in dropped_rids:
            node.getparent().remove(node)
    for section in root.xpath('//*[local-name()="sectionLst"]/*[local-name()="section"]'):
        for node in section.xpath('./*[local-name()="sldIdLst"]/*[local-name()="sldId"]'):
            if node.get("id") not in kept:
                node.getparent().remove(node)


def rgb_value(value):
    if not isinstance(value,str) or not re.fullmatch("#[A-Fa-f0-9]{6}",value):
        raise ValueError("背景色应为六位十六进制色值。")
    return value[1:].upper()


def set_background(root, color):
    common = root.find("p:cSld",NS)
    old = common.find("p:bg",NS)
    new = ET.Element(f"{{{P}}}bg")
    props=el(new,"bgPr")
    if isinstance(color,dict):
        if color.get("type")!="gradient" or color.keys()-{"type","from","to","angle"}:
            raise ValueError("请选择双色线性渐变。")
        fill=ET.SubElement(props,f"{{{A}}}gradFill",rotWithShape="1")
        stops=ET.SubElement(fill,f"{{{A}}}gsLst")
        for position,key in (("0","from"),("100000","to")):
            stop=ET.SubElement(stops,f"{{{A}}}gs",pos=position)
            ET.SubElement(stop,f"{{{A}}}srgbClr",val=rgb_value(color.get(key)))
        angle=numeric(color.get("angle",0),-3600,3600)
        ET.SubElement(fill,f"{{{A}}}lin",ang=str(round((angle%360)*60000)%21600000),scaled="0")
    else:
        fill=ET.SubElement(props,f"{{{A}}}solidFill")
        ET.SubElement(fill,f"{{{A}}}srgbClr",val=rgb_value(color))
    if old is not None:
        common.replace(old,new)
    else:
        common.insert(0,new)


def numeric(value,minimum,maximum):
    if type(value) not in (float,int) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("对象的位置、大小、旋转或裁切参数超出范围。")
    return value


def set_geometry(deck, part, shape, transform, patch):
    if not isinstance(patch,dict) or patch.keys()-{"x","y","w","h","rotation","crop"}:
        raise ValueError("对象几何修改字段不支持。")
    if "crop" in patch:
        fill = shape.find("p:blipFill",NS)
        crop = patch["crop"]
        sides = ("left","right","top","bottom")
        if fill is None or not isinstance(crop,dict) or crop.keys()-set(sides):
            raise ValueError("仅图片支持上下左右裁切。")
        rect = fill.find("a:srcRect",NS)
        if rect is None:
            rect = ET.Element(f"{{{A}}}srcRect")
            blip = fill.find("a:blip",NS)
            if blip is None:
                raise ValueError("图片缺少图像数据。")
            blip.addnext(rect)
        for side,value in crop.items():
            rect.set(side[0],str(round(numeric(value,0,.9999)*100000)))
        if any(sum(int(rect.get(v,0)) for v in dims)>=100000 for dims in ("lr","tb")):
            raise ValueError("裁切后应保留可见图像。")
    if not patch.keys()-{"crop"}:
        return
    host = shape.find("p:spPr",NS)
    xf = host.find("a:xfrm",NS) if host is not None else shape.find("p:xfrm",NS)
    if xf is None:
        ph = shape.find("*/p:nvPr/p:ph",NS)
        layout = deck.related(part,"slideLayout")
        for source in (layout,deck.related(layout,"slideMaster") if layout else ""):
            lookup = placeholders(deck,source)
            if ph is None or host is None:
                break
            ancestor = lookup.get(ph.get("idx","0"))
            if ancestor is None:
                ancestor = lookup.get(ph.get("type","body"))
            if ancestor is not None:
                original = ancestor.find("p:spPr/a:xfrm",NS)
                if original is not None:
                    xf = deepcopy(original)
                    host.insert(0,xf)
                    break
    if xf is None:
        raise ValueError("该对象没有可编辑的几何信息。")
    sx,sy,dx,dy = transform
    off,ext = xf.find("a:off",NS),xf.find("a:ext",NS)
    if off is None or ext is None or not sx or not sy:
        raise ValueError("该对象的原始尺寸或分组变换不完整。")
    for key,attr,node,unit,scale,offset in (("x","x",off,deck.w,sx,dx),("y","y",off,deck.h,sy,dy),
                                          ("w","cx",ext,deck.w,sx,0),("h","cy",ext,deck.h,sy,0)):
        if key in patch:
            value = numeric(patch[key],-3 if key in "xy" else .000001,4)
            node.set(attr,str(round((value*unit-offset)/scale)))
    if "rotation" in patch:
        xf.set("rot",str(round((numeric(patch["rotation"],-3600,3600)%360)*60000)))


def set_layers(tree, order, known):
    if not isinstance(order,list) or any(not isinstance(k,str) for k in order) or len(order)!=len(known) or set(order)!=set(known):
        raise ValueError("层级应包含本页每个对象的唯一编号。")
    if order==list(known):
        return False
    rank={sid:i for i,sid in enumerate(order)}
    def arrange(parent):
        children=[]
        for node in parent:
            t=local(node)
            if t=="grpSp":
                ids=arrange(node)
            elif t=="AlternateContent":
                branch=next((n for n in node if local(n)=="Choice"),None)
                if branch is None:
                    branch=next((n for n in node if local(n)=="Fallback"),None)
                ids=[sid for sid,_,_,_ in walk_shapes(branch)]
                if ids!=sorted(ids,key=rank.get):
                    raise ValueError("此组合含多个兼容格式，请在桌面编辑器中调整内部层级。")
            else:
                nv=node.find("*/p:cNvPr",NS)
                ids=[nv.get("id")] if nv is not None and nv.get("id") in rank else []
            if ids:
                positions=sorted(rank[i] for i in ids)
                if positions[-1]-positions[0]+1!=len(positions):
                    raise ValueError("该层级会把同一组合拆开放置，请在组内调整。")
                children.append((positions[0],node,ids))
        if not children:
            return []
        nodes={c for _,c,_ in children}
        reordered=sorted(children,key=lambda c:c[0])
        it=iter(c for _,c,_ in reordered)
        parent[:]=[next(it) if c in nodes else c for c in parent]
        return [sid for _,_,ids in reordered for sid in ids]
    arrange(tree)
    return True


def edit_slide(deck, part, edits):
    if not isinstance(edits,dict) or edits.keys()-{"texts","images","cues","geometry","background","zOrder"}:
        raise ValueError("页面修改字段不支持。")
    root = deck.tree(part)
    shapes = list(shape_list(root))
    items = {sid:s for sid,_,s,_ in shapes}
    if "zOrder" in edits and set_layers(root.find("p:cSld/p:spTree",NS),edits["zOrder"],items):
        deck.changed.add(part)
    if "background" in edits:
        set_background(root,edits["background"])
        deck.changed.add(part)
    geometry = edits.get("geometry",{})
    if not isinstance(geometry,dict) or geometry.keys()-items.keys():
        raise ValueError("几何修改中包含未知的对象编号。")
    for sid,_,shape,transform in shapes:
        if sid in geometry:
            set_geometry(deck,part,shape,transform,geometry[sid])
            deck.changed.add(part)
    for group in ("texts","images"):
        changes = edits.get(group,{})
        if not isinstance(changes,dict):
            raise ValueError("对象修改需要提供对象编号与值。")
        for sid,value in changes.items():
            if sid not in items:
                raise ValueError(f"页面中找不到指定对象 {sid}。")
            if group == "images":
                replace_picture(deck,part,items[sid],value)
            else:
                body = items[sid].find("p:txBody",NS)
                if body is None:
                    raise ValueError("此对象没有可编辑的原生文字。")
                if write_text(body,value):
                    deck.changed.add(part)
    if edits.keys() & {"background", "geometry", "zOrder", "images"}:
        from slidecontrast import apply_readability
        apply_readability(root)
    if "cues" not in edits:
        return
    seq = edits["cues"]
    if (not isinstance(seq,list) or len(seq)>2000 or
            any(not isinstance(s,str) or s not in items for s in seq) or len(seq)!=len(set(seq))):
        raise ValueError("动画步骤需要有效且不重复的对象编号。")
    current,editable = cues_for(root)
    if seq == [c["id"] for c in current]:
        return
    if not editable:
        raise ValueError("本页含复杂动画，工作台已保留原效果。请在桌面编辑器中调整动画。")
    timing = root.find("p:timing",NS)
    if timing is not None:
        root.remove(timing)
    if seq:
        new = make_timing(seq,current[0]["effect"] if current else "appear")
        extension = root.find("p:extLst",NS)
        if extension is None:
            root.append(new)
        else:
            extension.addprevious(new)
    deck.changed.add(part)


def apply_edits(data, edits):
    if not isinstance(edits,dict) or edits.keys()-{"order","slides"}:
        raise ValueError("无效的修改请求。")
    try:
        deck = Deck(data)
        with deck.zip:
            if "order" in edits:
                update_order(deck,edits["order"])
            updates = edits.get("slides",{})
            if not isinstance(updates,dict):
                raise ValueError("页面修改应为映射。")
            for part, changes in updates.items():
                if part not in deck.slides:
                    raise ValueError("原文件中找不到所选页面。")
                edit_slide(deck,part,changes)
            return deck.save() if deck.changed else data
    except (BadZipFile, KeyError, OSError, NotImplementedError, OverflowError) as exc:
        raise ValueError("无法编辑此 PPTX 压缩包。") from exc

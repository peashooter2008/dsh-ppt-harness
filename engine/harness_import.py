"""Inspect and patch native slide objects, keeping the user's PPTX as a read-only source."""
import argparse
import base64
from copy import deepcopy
from io import BytesIO
import json
import math
from pathlib import Path
import posixpath
import sys
from uuid import uuid4
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

from lxml import etree as ET
from openpyxl.utils.cell import get_column_letter, range_boundaries

from election_opening import read_photo, resolve_child
from engine import Deck, NS, R, inspect_slide, local, pair, picture_blip, relpart, replace_picture, set_geometry, shape_list, target, text_in, write_text, xml
from native import PreviewSession
from template_text import apply_edits as edit_text, slide_slots


C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
D = "{" + R + "}"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def rows(table):
    return [r.findall("a:tc", NS) for r in table.findall("a:tr", NS)]


def numbered(seq, n, label):
    require(type(n) is int and 1 <= n <= len(seq), label+"编号无效。")
    return seq[n-1]


def xml_bytes(element):
    return ET.tostring(element, encoding="utf-8", xml_declaration=True, standalone=True)


def repack(archive, changes, added=None):
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as dst:
        dst.comment = archive.comment
        for info in archive.infolist():
            data = changes[info.filename] if info.filename in changes else archive.read(info)
            dst.writestr(deepcopy(info), data)
        for key, value in (added or {}).items():
            dst.writestr(key, value)
    return output.getvalue()


class Workbook:
    """Patch scalar sheet cells in their original XML; preserve unrelated workbook parts."""
    def __init__(self, data):
        self.archive = ZipFile(BytesIO(data))
        infos = self.archive.infolist()
        require(len(infos) <= 4000 and sum(i.file_size for i in infos) <= 96*1024**2 and
                len(set(i.filename for i in infos)) == len(infos), "嵌入工作簿超出可编辑范围。")
        self.sheets, self.parts, self.changed = {}, {}, set()
        wb = xml(self.archive.read("xl/workbook.xml"))
        rels = xml(self.archive.read("xl/_rels/workbook.xml.rels"))
        locations = {n.get("Id"): target("xl/workbook.xml", n.get("Target","")) for n in rels
                     if not n.get("TargetMode") and n.get("Type","").endswith("/worksheet")}
        for sheet in wb.findall(S+"sheets/"+S+"sheet"):
            if sheet.get(D+"id") in locations:
                self.sheets[sheet.get("name")] = locations[sheet.get(D+"id")]
        self.has_tables = any(i.filename.startswith("xl/tables/") for i in infos)
        self.strings = []
        if "xl/sharedStrings.xml" in self.archive.namelist():
            for item in xml(self.archive.read("xl/sharedStrings.xml")).findall(S+"si"):
                self.strings.append("".join(t.text or "" for t in item.iter(S+"t")))

    def range(self, formula):
        require(isinstance(formula, str) and "!" in formula, "图表缺少单一工作表中的数据范围。")
        name, address = formula.rsplit("!", 1)
        if name.startswith("'") and name.endswith("'"):
            name = name[1:-1].replace("''", "'")
        require(name in self.sheets, "图表链接到外部、命名或未知区域。")
        c1,r1,c2,r2 = range_boundaries(address)
        require(all(type(v) is int and v >= 1 for v in (c1,r1,c2,r2)) and (c1==c2 or r1==r2)
                and 1 <= (c2-c1+1)*(r2-r1+1) <= 4096, "仅可定向修改一列或一行的常规图表数据。")
        part = self.sheets[name]
        if part not in self.parts:
            root = xml(self.archive.read(part))
            self.parts[part] = (root, {c.get("r"):c for c in root.iter(S+"c")})
        lookup = self.parts[part][1]
        cells = [lookup.get(f"{get_column_letter(c)}{r}") for r in range(r1,r2+1) for c in range(c1,c2+1)]
        require(all(cell is not None and cell.find(S+"f") is None for cell in cells), "工作簿含公式或稀疏单元格，此系列只读。")
        return part, cells

    def value(self, cell):
        t = cell.get("t", "n")
        val = cell.findtext(S+"v")
        if t == "s" and val is not None:
            return self.strings[int(val)]
        if t == "inlineStr":
            return "".join(n.text or "" for n in cell.iter(S+"t"))
        if t == "str":
            return val or ""
        require(t=="n" and val is not None, "图表工作簿的单元格类型只读。")
        return float(val)

    def change(self, part, cell, value):
        if self.value(cell) == value:
            return
        if isinstance(value, str):
            for child in list(cell):
                if child.tag in (S+"v", S+"is"):
                    cell.remove(child)
            cell.set("t", "inlineStr")
            text = ET.SubElement(ET.SubElement(cell, S+"is"), S+"t")
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            text.text = value
        else:
            cell.find(S+"v").text = str(value)
        self.changed.add(part)

    def bytes(self):
        return repack(self.archive, {part: xml_bytes(self.parts[part][0]) for part in self.changed})


def series_cache(series, field):
    node = series.find(C+field)
    if node is None:
        return None, []
    points = []
    for pt in sorted(node.iter(C+"pt"), key=lambda p:int(p.get("idx", "-1"))):
        v = pt.find(C+"v")
        if v is not None:
            points.append((int(pt.get("idx", "-1")),v))
    return node.findtext(".//"+C+"f"), points


def linked_count(deck, destination):
    if not hasattr(deck, "_import_links"):
        counts = {}
        for name in deck.names:
            if not name.endswith(".rels") or "/_rels/" not in name:
                continue
            parent, leaf = name.rsplit("/_rels/", 1)
            source = posixpath.join(parent,leaf[:-5])
            for typ, part in deck.rels(source).values():
                if typ in ("chart", "package"):
                    counts[part] = counts.get(part,0) + 1
        deck._import_links = counts
    return deck._import_links.get(destination,0)


def chart_info(deck, part, shape, books):
    tag = shape.find(".//"+C+"chart")
    rid = tag.get(D+"id")
    path = deck.rels(part).get(rid, ("",""))[1]
    info = {"editable":False,"types":[],"series":[]}
    handles = []
    if not path or path not in deck.names:
        info["reason"] = "图表源不在演示文稿内。"
        return info, handles
    root = deck.tree(path)
    for kind in root.findall(".//"+C+"plotArea/*"):
        if not local(kind).endswith("Chart"):
            continue
        info["types"].append(local(kind))
        for ser in kind.findall(C+"ser"):
            vf, vp = series_cache(ser, "val")
            nf, np = series_cache(ser, "tx")
            _, cp = series_cache(ser,"cat")
            name = np[0][1].text if len(np)==1 else ser.findtext(C+"tx/"+C+"v", "")
            vals = []
            for _, point in vp:
                try:
                    value = float(point.text)
                    vals.append(value if math.isfinite(value) else None)
                except (TypeError,ValueError):
                    vals.append(None)
            info["series"].append(dict(series=len(handles)+1, name=name or "", values=vals, categories=[n.text or "" for _,n in cp],canRename=False))
            handles.append(dict(part=path,vf=vf,vp=vp,nf=nf,np=np,ser=ser))
    try:
        require(len(info["types"])==1 and info["types"][0] in ("barChart","lineChart","pieChart","doughnutChart","areaChart"),
                "组合图、散点图及其他复杂图表可查看，暂不修改。")
        require(linked_count(deck,path)==1 and sum(n.get(D+"id")==rid for n in deck.tree(part).iter(C+"chart"))==1,
                "多个对象共用此图表部件，定向改稿暂不支持。")
        external = root.find(C+"externalData")
        book = deck.rels(path).get(external.get(D+"id"), ("",""))[1] if external is not None else ""
        require(book.endswith(".xlsx") and book in deck.names and linked_count(deck,book)==1, "图表缺少独立嵌入 XLSX，或工作簿为外链。")
        if book not in books:
            books[book] = Workbook(deck.zip.read(book))
        wb = books[book]
        require(bool(handles), "图表没有可修改的数据系列。")
        addresses = set()
        for h, meta in zip(handles, info["series"]):
            h["wb"] = wb
            sheet, cells = wb.range(h["vf"])
            require(None not in meta["values"] and [idx for idx,_ in h["vp"]]==list(range(len(cells))) and
                    [wb.value(cell) for cell in cells]==meta["values"], "图表缓存与工作簿不同步，此图表只读。")
            for cell in cells:
                addr = (sheet,cell.get("r"))
                require(addr not in addresses, "多个数据系列共用工作簿单元格，此图表只读。")
                addresses.add(addr)
            h.update(sheet=sheet,cells=cells)
            if not wb.has_tables and len(h["np"])==1:
                try:
                    _, name_cells = wb.range(h["nf"])
                    meta["canRename"] = len(name_cells)==1 and wb.value(name_cells[0])==meta["name"]
                except (ValueError,KeyError,IndexError):
                    pass
        info["editable"] = True
    except (ValueError, KeyError, IndexError, BadZipFile) as exc:
        info["reason"] = str(exc) if isinstance(exc,ValueError) else "图表的工作簿结构暂不支持。"
    return info, handles


def group_map(shape):
    """Map a group's local coordinates into physical slide EMUs, including nested flips and rotations."""
    m = (1,0,0,1,0,0)
    for parent in reversed(list(shape.iterancestors())):
        if local(parent)!="grpSp":
            continue
        xf = parent.find("p:grpSpPr/a:xfrm",NS)
        if xf is None:
            continue
        x,y = pair(xf,"off","x","y")
        w,h = pair(xf,"ext","cx","cy")
        u,v = pair(xf,"chOff","x","y")
        cw,ch = pair(xf,"chExt","cx","cy")
        if min(w,h,cw,ch)<=0:
            return None
        theta = math.radians(int(xf.get("rot","0"))/60000)
        flipx = -1 if xf.get("flipH") in ("1","true") else 1
        flipy = -1 if xf.get("flipV") in ("1","true") else 1
        aa,bb,cc,dd,ee,ff = m
        px,py = aa*(x+w/2)+cc*(y+h/2)+ee,bb*(x+w/2)+dd*(y+h/2)+ff
        sx,sy = math.hypot(aa,bb),math.hypot(cc,dd)
        # Office keeps descendant rectangles orthogonal: rotate their orientation, then
        # apply accumulated lengths on the two local axes, even in non-uniform groups.
        cs,sn = math.cos(theta),math.sin(theta)
        xx,xy,yx,yy = aa/sx,bb/sx,cc/sy,dd/sy
        a,b = (xx*cs+yx*sn)*sx*w/cw*flipx,(xy*cs+yy*sn)*sx*w/cw*flipx
        c,d = (yx*cs-xx*sn)*sy*h/ch*flipy,(yy*cs-xy*sn)*sy*h/ch*flipy
        e,f = px-a*(u+cw/2)-c*(v+ch/2),py-b*(u+cw/2)-d*(v+ch/2)
        m = (a,b,c,d,e,f)
    return m


def page_geometry(deck, shape, row, simple):
    model = group_map(shape)
    reason = None
    if not row["geometryEditable"]:
        reason = "此对象缺少可写坐标，请选独立图片、形状或文字框。"
    elif local(shape)=="contentPart":
        reason = "此对象由外部内容提供位置，请在演示软件中调整。"
    elif shape.find(".//a:stCxn",NS) is not None or shape.find(".//a:endCxn",NS) is not None:
        reason = "连线端点已绑定，请移动连接的节点。"
    if not model or not simple[0] or not simple[1]:
        return None, {"geometryEditable":False,"geometryReason":"该分组的坐标系不完整，请在演示软件取消组合后重试。"}
    sx,sy,dx,dy = simple
    w,h = row["w"]*deck.w/sx,row["h"]*deck.h/sy
    mx,my = (row["x"]*deck.w-dx)/sx+w/2,(row["y"]*deck.h-dy)/sy+h/2
    a,b,c,d,e,f = model
    px,py = a*mx+c*my+e,b*mx+d*my+f
    theta = math.radians(row["rotation"])
    cs,sn = math.cos(theta),math.sin(theta)
    xs,ys = math.hypot(a,b),math.hypot(c,d)
    ux,uy = (a/xs*cs+c/ys*sn)*xs,(b/xs*cs+d/ys*sn)*xs
    vx,vy = (c/ys*cs-a/xs*sn)*ys,(d/ys*cs-b/xs*sn)*ys
    page_w,page_h = w*xs/deck.w,h*ys/deck.h
    bounds = dict(x=px/deck.w-page_w/2,y=py/deck.h-page_h/2,w=page_w,h=page_h)
    if min(w,h)<=0 or abs(a*d-b*c)<1e-14:
        reason = "该对象是零宽线、零高线或尺寸不完整；请改选可缩放的二维对象。"
    quad = [[(px+i*ux*w/2+j*vx*h/2)/deck.w,(py+i*uy*w/2+j*vy*h/2)/deck.h]
            for i,j in ((-1,-1),(1,-1),(1,1),(-1,1))]
    info = dict(bounds=bounds,rotation=math.degrees(math.atan2(uy,ux)),geometryEditable=not bool(reason))
    if abs(b)>1e-10 or abs(c)>1e-10 or a<0 or d<0 or abs(ux*vx+uy*vy)>1e-8*xs*ys:
        info["quad"] = quad
    if reason:
        info["geometryReason"] = reason
    return (model,xs,ys),info


def patch_bounds(deck, part, shape, obj, edit, basis):
    require(obj.get("geometryEditable"),obj.get("geometryReason","该对象没有独立坐标，请选择有外框的对象。"))
    old = obj["bounds"]
    before, change = edit.get("before"),edit.get("bounds")
    finite = lambda v: type(v) in (float,int) and math.isfinite(v)
    require(isinstance(before,dict) and set(before)==set(old) and
            all(finite(before[k]) and abs(before[k]-v)<1e-6 for k,v in old.items()),
            "对象原坐标已变化，请重新读取 bounds 再提交。")
    require(isinstance(change,dict) and change and change.keys()<=old.keys() and all(finite(v) for v in change.values()),
            "请提供归一化的 x、y、w、h 中至少一项。")
    box = {**old,**change}
    x,y,w,h = (box[k] for k in ("x","y","w","h"))
    require(0<w<=1 and 0<h<=1 and x>=-1e-6 and y>=-1e-6 and x+w<=1.000001 and y+h<=1.000001,
            "改后外框需放在画布内，宽、高应大于零。")
    if all(abs(old[k]-v)<1e-9 for k,v in change.items()):
        return
    (a,b,c,d,e,f),xs,ys = basis
    cx,cy = (x+w/2)*deck.w-e,(y+h/2)*deck.h-f
    determinant = a*d-b*c
    local_w,local_h = w*deck.w/xs,h*deck.h/ys
    local_x = (d*cx-c*cy)/determinant-local_w/2
    local_y = (a*cy-b*cx)/determinant-local_h/2
    # Delegate local coordinate writing (including inherited placeholder bounds) to the original engine.
    # Choose an offset and scale that map the legal normalized target into the group's own coordinate system.
    synthetic = (xs,ys,x*deck.w-xs*local_x,y*deck.h-ys*local_y)
    set_geometry(deck,part,shape,synthetic,box)
    table = shape.find("a:graphic/a:graphicData/a:tbl",NS)
    if table is not None:
        for key,dim,elements,attr in (("w",local_w,table.findall("a:tblGrid/a:gridCol",NS),"w"),
                                      ("h",local_h,table.findall("a:tr",NS),"h")):
            if key not in change or abs(box[key]-old[key])<1e-9:
                continue
            values = [int(el.get(attr,0)) for el in elements]
            require(values and min(values)>0 and dim>=len(values),"表格网格缺少有效尺寸，只支持移动此表格。")
            total,pos = sum(values),0
            for el,v in zip(elements,values):
                nxt = pos+v
                scaled = round(dim*nxt/total)-round(dim*pos/total)
                require(scaled>0,"表格缩放后的单元格过窄或过矮。")
                el.set(attr,str(scaled))
                pos = nxt
    deck.changed.add(part)


def read_page(deck, page, books):
    part, slots = slide_slots(deck, page)
    description = inspect_slide(deck, part)
    slide = deck.tree(part)
    entries = list(shape_list(slide))
    shapes = {sid:sh for sid,_,sh,_ in entries}
    transforms = {sid:transform for sid,_,_,transform in entries}
    bases = {}
    require(len(shapes)==len(description["objects"]), "此页对象编号重复，无法定向。")
    objects, charts = [], {}
    relationships = deck.rels(part)

    def image_properties(blip, role):
        image = relationships.get(blip.get(f"{{{R}}}embed"))
        editable = bool(image and image[0] == "image" and image[1] in deck.names
                        and blip.get(f"{{{R}}}link") is None and blip.find("a:extLst", NS) is None)
        return {"imageRole": role, "imageEditable": editable}
    for row in description["objects"]:
        sid = row["id"]
        sh = shapes[sid]
        obj = dict(id=sid,name=row["name"],kind=row["type"],bounds={k:row[k] for k in ("x","y","w","h")},
                   rotation=row["rotation"],geometry=row["geometry"],text=row["text"])
        bases[sid],geometry = page_geometry(deck,sh,row,transforms[sid])
        obj.update(geometry)
        tab = sh.find(".//a:tbl", NS)
        if tab is not None:
            obj.update(kind="table",cells=[[text_in(cell.find("a:txBody",NS)) for cell in line] for line in rows(tab)])
        elif sh.find(".//"+C+"chart") is not None:
            chart, charts[sid] = chart_info(deck,part,sh,books)
            obj.update(kind="chart",chart=chart)
        elif row["type"] == "image":
            nv=sh.find("p:nvPicPr/p:cNvPr",NS)
            obj.update(imageEditable=False,crop=row["crop"],alt=nv.get("descr","") if nv is not None else "")
        blip = picture_blip(sh, include_fills=True)
        if blip is not None:
            obj.update(image_properties(blip, "picture" if local(sh)=="pic" else "shape-fill"))
        objects.append(obj)
    background = slide.find("p:cSld/p:bg/p:bgPr", NS)
    blip = picture_blip(background, include_fills=True) if background is not None else None
    if blip is not None:
        shapes["slide-background"] = background
        objects.append(dict(id="slide-background", name="本页背景图片", kind="image",
                            bounds=dict(x=0, y=0, w=1, h=1), rotation=0, text="",geometryEditable=False,
                            geometryReason="背景铺满整页。要移动背景内容，请在导入时把图片作为普通图片对象。",
                            **image_properties(blip, "slide-background")))
    result = dict(slides=len(deck.slides),page=page,aspectRatio=deck.w/deck.h,title=description["title"],objects=objects,
                  slots=[dict(slot=s,name=name,text=value) for s,(name,_,value) in slots.items()])
    return part, shapes, charts, bases, result


def patch_chart(deck, obj, handles, edit):
    require(obj["chart"]["editable"],obj["chart"].get("reason","此图表只读。"))
    index = edit.get("series")
    h = numbered(handles,index,"系列")
    meta = numbered(obj["chart"]["series"],index,"系列")
    values = edit.get("values")
    require(isinstance(values,list) and len(values)==len(meta["values"]) and all(type(n) in (int,float) and math.isfinite(n) for n in values),
            "新数值与原系列必须等长，且均为有限数字。")
    require(meta["values"]==edit.get("before"),"图表系列原数值已变化。")
    if obj["chart"]["types"][0] in ("pieChart","doughnutChart"):
        require(min(values)>=0 and max(values)>0,"饼图、环形图需要非负数值且合计大于零。")
    wb = h["wb"]
    name = edit.get("name",meta["name"])
    if name == meta["name"] and values == meta["values"]:
        return
    if name != meta["name"]:
        require(isinstance(name,str) and 1<=len(name)<=255 and meta["name"]==edit.get("beforeName"),"系列名称或原名称不符。")
        require(not wb.has_tables and len(h["np"])==1, "本系列名称为表格标题或非普通引用，暂不改名。")
        sheet, cells = wb.range(h["nf"])
        require(len(cells)==1 and wb.value(cells[0])==meta["name"], "系列名称与工作簿不一致。")
        wb.change(sheet,cells[0],name)
        h["np"][0][1].text = name
    for (_,point), cell, value in zip(h["vp"],h["cells"],values):
        wb.change(h["sheet"],cell,value)
        point.text = str(value)
    deck.changed.add(h["part"])


def patch(deck, root, page, edits, books, part, shapes, charts, bases, result):
    require(isinstance(edits,list) and 1<=len(edits)<=256, "一次请指定 1 至 256 处修改。")
    objects = {obj["id"]:obj for obj in result["objects"]}
    seen = set()
    for edit in edits:
        require(isinstance(edit,dict), "对象改动必须是结构化参数。")
        kind, sid = edit.get("type"), edit.get("id")
        key = (kind,sid,edit.get("slot"),edit.get("row"),edit.get("col"),edit.get("series"))
        require(key not in seen, "同一条改动被重复提交。")
        seen.add(key)
        if kind=="text":
            edit_text(deck,[{**edit,"page":page}])
            continue
        require(sid in shapes and kind in ("cell","chart","image","geometry"), "对象编号或修改类型无效。")
        sh, obj = shapes[sid], objects[sid]
        if kind=="geometry":
            patch_bounds(deck,part,sh,obj,edit,bases.get(sid))
        elif kind=="cell" and obj["kind"]=="table":
            cell = numbered(numbered(rows(sh.find(".//a:tbl",NS)),edit.get("row"),"行"),edit.get("col"),"列")
            require(cell.get("hMerge") not in ("1","true") and cell.get("vMerge") not in ("1","true"),"请修改合并区域的起始单元格。")
            body = cell.find("a:txBody", NS)
            require(body is not None and text_in(body)==edit.get("before"),"表格原文已变化，请重新读取。")
            require(body.find(".//a:fld",NS) is None and body.find(".//a:hlinkClick",NS) is None,"含字段或链接的单元格暂不修改。")
            if write_text(body,edit.get("text")):
                deck.changed.add(part)
        elif kind=="chart" and obj["kind"]=="chart":
            patch_chart(deck,obj,charts[sid],edit)
        elif kind=="image" and obj.get("imageEditable"):
            require(isinstance(edit.get("asset"),str) and edit["asset"], "请先导入替换用的图片。")
            raw,_,_ = read_photo(root, edit["asset"])
            mime = "png" if raw.startswith(b"\x89PNG") else "jpeg"
            replace_picture(deck,part,sh,"data:image/"+mime+";base64,"+base64.b64encode(raw).decode("ascii"),
                            include_fills=True)
        else:
            raise ValueError("对象类型不匹配。")
    require(bool(deck.changed),"提交内容与原稿相同。")
    changes = {p:xml_bytes(deck.parts[p]) for p in deck.changed}
    changes.update({p:b.bytes() for p,b in books.items() if b.changed})
    added = {p:v for p,v in changes.items() if p not in deck.names}
    added.update(deck.media)
    return repack(deck.zip,changes,added)


def page_previews(source, folder, pages):
    folder.mkdir(exist_ok=True)
    base = uuid4().hex
    renderer = PreviewSession()
    results = []
    try:
        for page in pages:
            preview = folder / f"{base}-p{page}.png"
            try:
                engine = renderer.export(str(source), "both", page, str(preview), {})
                results.append(dict(page=page, preview="editions/"+preview.name, previewEngine=engine))
            except Exception:
                results.append(dict(page=page, preview=None, previewError="本机当前无法渲染原生预览。"))
    finally:
        renderer.close()
    return results


def slide_text_lines(slide):
    if slide.get("show") in ("false","0"):
        return
    for _, _, shape, _ in shape_list(slide):
        nv = shape.find("*/p:cNvPr", NS)
        if nv is not None and nv.get("hidden") in ("true","1"):
            continue
        body = text_in(shape.find("p:txBody", NS)).strip()
        if body:
            yield body
        table = shape.find("a:graphic/a:graphicData/a:tbl", NS)
        if table is not None:
            for row in rows(table):
                cells = [text_in(cell.find("a:txBody", NS)).strip() for cell in row]
                while cells and not cells[-1]:
                    cells.pop()
                if cells:
                    yield " | ".join(cells)


def extract_text(source):
    max_pages, max_chars = 100, 30000
    paragraphs, length, read = [], 0, 0
    with source.open("rb") as stream:
        deck = Deck.from_stream(stream, source.stat().st_size)
        with deck.zip:
            total = len(deck.slides)
            truncated = total > max_pages
            for page, part in enumerate(deck.slides, 1):
                if page > max_pages:
                    break
                read = page
                first = True
                # Discard each page tree after use, including in image-heavy presentations.
                for line in slide_text_lines(xml(deck.zip.read(part))):
                    separator = "\n"
                    if first:
                        separator = ("\n\n" if paragraphs else "") + f"第 {page} 页\n"
                    first = False
                    entry = separator + line
                    remaining = max_chars - length
                    if len(entry)>remaining:
                        paragraphs.append(entry[:remaining])
                        truncated = True
                        break
                    paragraphs.append(entry)
                    length += len(entry)
                else:
                    continue
                break
    return dict(text="".join(paragraphs),slides=total,pagesRead=read,truncated=truncated,
                limits=dict(pages=max_pages,characters=max_chars))


def process(root, request):
    src = request.get("source")
    require(isinstance(src,str) and src.lower().endswith(".pptx"), "请选择工作目录中的 PPTX。")
    source = resolve_child(root,src)
    action, page = request.get("action"),request.get("page",1)
    require(action in ("inspect","edit","previews","extractText"),"未知的原生改稿操作。")
    if action=="extractText":
        return extract_text(source)
    folder = resolve_child(root,"editions")
    if action=="previews":
        pages = request.get("pages")
        with source.open("rb") as f:
            deck = Deck.from_stream(f,source.stat().st_size)
            with deck.zip:
                total = len(deck.slides)
        require(isinstance(pages,list) and pages and all(type(p) is int and 1<=p<=total for p in pages),
                "请指定有效的原稿页码。")
        return dict(slides=total, previews=page_previews(source,folder,dict.fromkeys(pages)))
    name = uuid4().hex
    books = {}
    try:
        with source.open("rb") as f:
            deck = Deck.from_stream(f,source.stat().st_size)
            with deck.zip:
                part,shapes,charts,bases,result = read_page(deck,page,books)
                if action=="edit":
                    data = patch(deck,root,page,request.get("edits"),books,part,shapes,charts,bases,result)
                    folder.mkdir(exist_ok=True)
                    source = folder/(name+".pptx")
                    with source.open("xb") as out:
                        out.write(data)
                    result = dict(slides=len(deck.slides),page=page,deck="editions/"+source.name)
    finally:
        for book in books.values():
            book.archive.close()
    if request.get("render",action=="edit"):
        result.update(page_previews(source,folder,[page])[0])
    return result


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True, type=Path)
    args = parser.parse_args()
    try:
        data = sys.stdin.buffer.read(4*1024**2+1)
        require(len(data)<=4*1024**2,"原生改稿请求太长。")
        result = process(args.workdir.resolve(strict=True),json.loads(data.decode("utf-8-sig")))
        print(json.dumps(dict(ok=True,**result), ensure_ascii=False, allow_nan=False))
    except (ValueError,OSError,KeyError,IndexError,TypeError,AttributeError,BadZipFile) as exc:
        error = str(exc) if isinstance(exc,ValueError) else "无法读取该原生对象或文件。"
        print(json.dumps(dict(ok=False,error=error), ensure_ascii=False))
        sys.exit(1)

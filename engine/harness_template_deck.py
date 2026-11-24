"""Produce new slides on native template frames, preserving their artwork and timing."""

from copy import deepcopy
from io import BytesIO
import posixpath
import re
import unicodedata
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree as ET
from PIL import Image

from engine import (A, CT, NS, P, PKG, R, Deck, local, make_timing, pair, picture_blip,
                    relpart, shape_list, target, text_in, write_text, xml)


def encoded(root):
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)


class Output:
    """Keep reference artwork in its original part. Import only dependencies of new content."""
    def __init__(self, master, generated):
        self.master = master
        self.generated = generated
        self.parts = {}
        self.copied = {}
        self.types = deepcopy(master.tree("[Content_Types].xml"))
        self.counter = 0

    def read(self, part):
        return self.parts[part] if part in self.parts else self.master.zip.read(part)

    def write_xml(self, part, node):
        self.parts[part] = encoded(node)

    def allocate(self, part, source, *, preferred=None):
        folder, name = posixpath.split(part)
        ext = posixpath.splitext(name)[1]
        dest = preferred
        while dest is None or dest in self.master.names or dest in self.parts:
            self.counter += 1
            stem = re.sub(r"[0-9]+$", "", posixpath.splitext(name)[0]) or "part"
            dest = posixpath.join(folder, f"{stem}{10000+self.counter}{ext}")
        entries = source.tree("[Content_Types].xml")
        ctype = next((n.get("ContentType") for n in entries if n.get("PartName") == "/"+part), None)
        if ctype is None:
            ctype = next((n.get("ContentType") for n in entries if n.get("Extension","").lower() == ext[1:].lower()), None)
        if not ctype:
            raise ValueError("模板部件缺少内容类型：" + part)
        ET.SubElement(self.types, f"{{{CT}}}Override", PartName="/"+dest, ContentType=ctype)
        return dest

    def import_part(self, part):
        if part in self.copied:
            return self.copied[part]
        src = self.generated
        dest = self.allocate(part, src)
        self.copied[part] = dest
        self.parts[dest] = src.zip.read(part)
        if relpart(part) in src.names:
            rels = deepcopy(src.tree(relpart(part)))
            for rel in rels:
                if rel.get("TargetMode") != "External":
                    child = self.import_part(target(part, rel.get("Target")))
                    rel.set("Target", posixpath.relpath(child, posixpath.dirname(dest)))
            self.write_xml(relpart(dest), rels)
        return dest

    def finish(self):
        # A shorter presentation must not carry unmapped slides or the old thumbnail.
        kept, pending = set(), [""]
        while pending:
            part = pending.pop()
            if part in kept:
                continue
            kept.add(part)
            rp = relpart(part)
            if rp not in self.parts and rp not in self.master.names:
                continue
            kept.add(rp)
            for r in xml(self.read(rp)):
                if r.get("TargetMode") != "External":
                    child = target(part, r.get("Target"))
                    if child not in self.parts and child not in self.master.names:
                        raise ValueError("模板内部引用的文件缺失：" + child)
                    pending.append(child)
        for node in list(self.types):
            if node.get("PartName") and node.get("PartName")[1:] not in kept:
                self.types.remove(node)
        buf = BytesIO()
        with ZipFile(buf, "w", compression=ZIP_DEFLATED, compresslevel=3) as zout:
            zout.writestr("[Content_Types].xml", encoded(self.types))
            for part in sorted(kept - {""}):
                zout.writestr(part, self.read(part))
        return buf.getvalue()


def relationship(rels, part, kind, dest):
    path = posixpath.relpath(dest, posixpath.dirname(part))
    for row in rels:
        if row.get("Target") == path and row.get("Type") == R+"/"+kind:
            return row.get("Id")
    used = {r.get("Id") for r in rels}
    n = len(used)+1
    while f"rId{n}" in used:
        n += 1
    rid = "rId"+str(n)
    ET.SubElement(rels, f"{{{PKG}}}Relationship", Id=rid, Type=R+"/"+kind, Target=path)
    return rid


def import_links(node, output, generated_part, part, rels):
    original = output.generated.rels(generated_part)
    for element in node.iter():
        for key, value in list(element.attrib.items()):
            if key.startswith("{"+R+"}") and value in original:
                kind, old = original[value]
                element.set(key, relationship(rels, part, kind, output.import_part(old)))


def box_of(shape, transform, size):
    xf = shape.find("p:spPr/a:xfrm", NS)
    if xf is None:
        xf = shape.find("p:xfrm", NS)
    if xf is None:
        return None
    x, y = pair(xf, "off", "x", "y")
    w, h = pair(xf, "ext", "cx", "cy")
    sx, sy, dx, dy = transform
    return ((x*sx+dx)/size[0], (y*sy+dy)/size[1], w*sx/size[0], h*sy/size[1])


def set_box(shape, box, size):
    xf = shape.find("p:spPr/a:xfrm", NS)
    if xf is None:
        xf = shape.find("p:xfrm", NS)
    for child, keys, values in (("off", ("x","y"),box[:2]), ("ext",("cx","cy"),box[2:])):
        node = xf.find("a:"+child, NS)
        for key,value,dimension in zip(keys,values,size):
            node.set(key,str(round(value*dimension)))


def visible(box):
    if box is None:
        return False
    x,y,w,h = box
    return w>0 and h>0 and 0 < x+w*.5 < 1 and 0 < y+h*.5 < 1


def motion_successor(master, previous_part, candidates):
    """A Morph is defined on its destination and depends on the preceding visible slide."""
    if previous_part is None:
        return None
    found = False
    for part in master.slides:
        if not found:
            found = part == previous_part
            continue
        slide = master.tree(part)
        if slide.get("show", "1") in ("0", "false"):
            continue
        if part in candidates and any(local(node) == "morph"
                                      for transition in slide.iter(f"{{{P}}}transition")
                                      for node in transition):
            return part
        break
    return None


def frame_map(master, raw, count, page_offset=0, *, preserve_motion=True, treatments=None, decisions=None,
              prior_page=None, prior_frames=(), paired_position=None):
    from collections import Counter
    from harness_page_selection import choose_frame, describe_frame

    parts = list(master.slides)
    available = {part for part in parts if master.tree(part).get("show","1") not in ("0","false")}
    if not available:
        raise ValueError("模板所有页面均标记为隐藏，未找到可用讲述页。")
    profiles = None
    uses = Counter(parts[n-1] for n in prior_frames if type(n) is int and 1<=n<=len(parts))
    frames = []
    run_length = 1
    previous = parts[prior_page-1] if type(prior_page) is int and 1<=prior_page<=len(parts) else None
    run_start = previous
    for n in reversed(prior_frames[:-1]):
        if not run_start or type(n) is not int or not 1<=n<=len(parts) or motion_successor(master,parts[n-1],{run_start}) != run_start:
            break
        run_length += 1
        run_start = parts[n-1]
    for i, spec in enumerate(raw):
        index = page_offset+i
        recompose = treatments is not None and treatments[i] == "recompose"
        successor = motion_successor(master, previous, available) if preserve_motion and not recompose else None
        if "templatePage" in spec:
            n = spec["templatePage"]
            if type(n) is not int or not 1<=n<=len(parts):
                raise ValueError(f"第 {index+1} 页引用的模板页码无效。")
            frame, reason = parts[n-1], "按指定的模板页码制作"
        elif successor is not None and (paired_position==2 or paired_position is None and count==2):
            frame, reason = successor, "与上一页连续，保留原稿的平滑切换"
        elif ((paired_position==1 or paired_position is None and index==0 and count==2) and preserve_motion and not recompose
              and motion_successor(master,next(p for p in parts if p in available),available)):
            frame = next(p for p in parts if p in available)
            reason = "从模板首帧开始，下一页可连续播放平滑切换"
        else:
            if profiles is None:
                profiles = [describe_frame(master,p,n) for n,p in enumerate(parts,1) if p in available]
            choice, reason = choose_frame(profiles,spec,index+1,count,uses,previous,successor,run_length)
            frame = choice.part
        frames.append(frame)
        if decisions is not None:
            decisions.append(None if recompose else {"page":parts.index(frame)+1,"reason":reason})
        run_length = run_length+1 if frame == successor else 1
        previous = None if recompose else frame
        if not recompose:
            uses[frame] += 1
    return frames


def split_title(title, weights):
    """Distribute a title through the original kinetic type objects without losing characters."""
    total = sum(weights)
    boundaries, consumed = [0], 0
    for w in weights:
        consumed += w
        boundaries.append(round(len(title)*consumed/total))
    return [title[a:b] for a,b in zip(boundaries,boundaries[1:])]


def rgb(tag, value):
    fill = ET.Element(f"{{{A}}}{tag}")
    ET.SubElement(fill,f"{{{A}}}srgbClr",val=value)
    return fill


def add_text(root, box, value, size, name, points=22):
    tree = root.find("p:cSld/p:spTree", NS)
    sid = str(max((int(n.get("id")) for n in tree.iter(f"{{{P}}}cNvPr")),default=0)+1)
    sp = ET.Element(f"{{{P}}}sp")
    nv = ET.SubElement(sp,f"{{{P}}}nvSpPr")
    ET.SubElement(nv,f"{{{P}}}cNvPr",id=sid,name=name)
    ET.SubElement(nv,f"{{{P}}}cNvSpPr",txBox="1")
    ET.SubElement(nv,f"{{{P}}}nvPr")
    pr=ET.SubElement(sp,f"{{{P}}}spPr")
    xf=ET.SubElement(pr,f"{{{A}}}xfrm")
    ET.SubElement(xf,f"{{{A}}}off");ET.SubElement(xf,f"{{{A}}}ext")
    set_box(sp,box,size)
    geom=ET.SubElement(pr,f"{{{A}}}prstGeom",prst="rect")
    ET.SubElement(geom,f"{{{A}}}avLst")
    fill=rgb("solidFill","142130");ET.SubElement(fill[0],f"{{{A}}}alpha",val="91000")
    pr.append(fill)
    tx=ET.SubElement(sp,f"{{{P}}}txBody")
    bp=ET.SubElement(tx,f"{{{A}}}bodyPr",wrap="square",anchor="ctr",lIns="114300",rIns="114300")
    ET.SubElement(bp,f"{{{A}}}normAutofit")
    ET.SubElement(tx,f"{{{A}}}lstStyle")
    for line in value.splitlines():
        para=ET.SubElement(tx,f"{{{A}}}p")
        run=ET.SubElement(para,f"{{{A}}}r")
        prop=ET.SubElement(run,f"{{{A}}}rPr",lang="zh-CN",sz=str(round(points*100)))
        prop.append(rgb("solidFill","FFFFFF"))
        ET.SubElement(run,f"{{{A}}}t").text=line
    insert_shape(tree,sp)


def insert_shape(tree, shape):
    ext=tree.find("p:extLst",NS)
    if ext is None:
        tree.append(shape)
    else:
        ext.addprevious(shape)


def fit_native_text(body,value,box,size):
    """PowerPoint does not always recalculate normAutofit for inherited template fonts."""
    props=body.findall(".//a:rPr[@sz]",NS)
    if not props or not visible(box):
        return
    _,_,w,h=box
    bp=body.find("a:bodyPr",NS)
    if bp is None:
        return
    room_w=(w*size[0]-sum(int(bp.get(k,"91440")) for k in ("lIns","rIns")))/12700
    room_h=(h*size[1]-sum(int(bp.get(k,"45720")) for k in ("tIns","bIns")))/12700
    orig=max(int(r.get("sz")) for r in props)/100
    if room_w<=0 or room_h<=0 or orig<=0:
        return
    # Use full em for CJK and a half-em for most Latin glyphs. Limit single-line
    # sizes separately, avoiding wrapped kinetic glyphs and overlapping neighbours.
    lengths=[sum(1 if unicodedata.east_asian_width(c) in ("F","W") else .56 for c in line)
             for line in value.strip().splitlines()]
    if not lengths:
        return
    from math import ceil
    point=orig
    if bp.get("wrap")=="none":
        point=min(point,room_w*.95/max(lengths))
    while point>6 and sum(max(1,ceil(width*point/room_w)) for width in lengths)*point*1.18>room_h:
        point*=.94
    ratio=min(1,point/orig)
    if ratio<.99:
        for r in props:
            r.set("sz",str(round(int(r.get("sz"))*ratio)))


def registration_layers(slots):
    """Find separate inscriptions whose coincident shapes carry different inks or shadows."""
    groups=[]
    def ink(body):
        styles=body.xpath(".//a:rPr/a:solidFill|.//a:rPr/a:ln|.//a:rPr/a:effectLst|"
                          ".//a:defRPr/a:solidFill|../p:spPr/a:effectLst",namespaces=NS)
        return tuple((local(n),tuple(sorted(n.attrib.items()))) for style in styles for n in style.iter())
    styles={s[1]:ink(s[1]) for s in slots}
    for i, first in enumerate(slots):
        x,y,w,h=first[3]
        for second in slots[i+1:]:
            if second[2]!=first[2] or styles[first[1]]==styles[second[1]]:
                continue
            u,v,a,b=second[3]
            overlap=max(0,min(x+w,u+a)-max(x,u))*max(0,min(y+h,v+b)-max(y,v))
            if overlap>=.84*max(w*h,a*b):
                related=[g for g in groups if first in g or second in g]
                merged=[first,second]
                for group in related:
                    merged.extend(s for s in group if s not in merged)
                    groups.remove(group)
                groups.append(merged)
    return sorted(groups,key=lambda g:max(s[3][2]*s[3][3] for s in g),reverse=True)


def fill_text(root, raw, size, page, specialized, adapt=False, preserve_motion=True):
    slots=[]
    for sid,name,s,transform in shape_list(root):
        body=s.find("p:txBody",NS)
        value=text_in(body).strip()
        if not value:
            continue
        box=box_of(s,transform,size)
        if box is None and s.find("p:nvSpPr/p:nvPr/p:ph",NS) is not None:
            # Positioned by the layout. Keep its inherited native layout.
            ph=s.find("p:nvSpPr/p:nvPr/p:ph",NS).get("type","obj")
            box=(.06,.05,.85,.14) if ph in ("title","ctrTitle") else (.08,.30,.84,.45)
        slots.append((name,body,value,box))
    normal=[s for s in slots if visible(s[3])]
    title=raw["title"].strip()
    inscriptions=registration_layers(normal)
    layers=[slot for group in inscriptions for slot in group]
    normal=[slot for slot in normal if slot not in layers]
    def title_score(slot):
        name,body,_,(x,y,w,h)=slot
        score=(2 if name.lower() in ("title","标题","主标题") else 0)+min(w,.9)*h*(1.3-y)
        if specialized:
            sizes=[int(p.get("sz","0")) for p in body.findall(".//a:rPr[@sz]",NS) if p.get("sz","").isdigit()]
            score+=min(96,max(sizes,default=0)/100)*.003
            if x<-.005 or y<-.005 or x+w>1.005 or y+h>1.005:
                score-=1
        return score
    letters=sorted((s for s in normal if len(s[2])==1 and s[3][3]>.13),key=lambda s:s[3][0])
    titlers = letters if len(letters)>=3 else ([max(normal,key=title_score)] if normal else [])
    # Folding a kinetic title into one shape leaves the other effects animating empty text.
    motion_targets = {n.get("spid") for n in root.iter() if n.get("spid")} if preserve_motion else set()
    kinetic_title = any(slot[1].getparent().find("*/p:cNvPr",NS).get("id") in motion_targets
                        for slot in titlers)
    if adapt and not kinetic_title and len(titlers)>=3 and len(title)>2*len(titlers):
        # Several single-character title shapes are effective for short chapter names.
        # A long new headline needs one reading line. Reuse the original native textbox,
        # keep its styling/animation target, and vacate the other decorative fragments.
        if all(local(s[1].getparent().getparent())=="spTree" for s in titlers):
            lead=titlers[0]
            left=min(s[3][0] for s in titlers)
            top=min(s[3][1] for s in titlers)
            right=min(.98,max(s[3][0]+s[3][2] for s in titlers))
            bottom=min(.97,max(s[3][1]+s[3][3] for s in titlers))
            box=(left,top,right-left,bottom-top)
            if box[2]>.15 and box[3]>.05:
                set_box(lead[1].getparent(),box,size)
                lead[1].find("a:bodyPr",NS).set("wrap","square")
                normal=[s for s in normal if s not in titlers]
                titlers=[(lead[0],lead[1],lead[2],box)]
    # A logo or a tiny tab is not a title slot. Use a legible native overlay.
    if len(titlers)==1 and (titlers[0][3][2]<.18 or titlers[0][3][3]<.045):
        titlers=[]
    if specialized and len(titlers)==1:
        # New charts and diagrams use the lower third. A centred native title
        # can otherwise sit behind the incoming figure or its supplemental text.
        slot=titlers[0]
        obj=slot[1].getparent()
        if slot[3][1]+slot[3][3]>.32 and local(obj.getparent())=="spTree" and obj.find("p:spPr/a:xfrm",NS) is not None:
            header=(.055,.065,.86,.155)
            set_box(obj,header,size)
            normal=[s for s in normal if s is not slot]
            titlers=[(*slot[:3],header)]
    values={}
    for index, group in enumerate(inscriptions):
        # Reuse an author's full phrase when they did not supply a shorter wordmark.
        # Independent secondary ornaments keep their own inscription.
        motif=raw.get("motifText",title) if index==0 else group[0][2]
        if not isinstance(motif,str) or not motif.strip():
            raise ValueError("多层字标需要可显示的文字。")
        for slot in group:
            values[slot[1]]=motif.strip()
    if titlers:
        for slot,fragment in zip(titlers,split_title(title,[1]*len(titlers))):
            values[slot[1]]=fragment
    else:
        add_text(root,(.055,.055,.87,.13),title,size,"新主题标题",30)
    lines=[line for line in raw.get("body",[]) if isinstance(line,str) and line.strip()]
    for attr in ("caption","source"):
        if raw.get(attr):
            lines.append(str(raw[attr]))
    title_floor=max([.20]+[s[3][1]+s[3][3] for s in titlers])
    candidates=sorted((s for s in normal if s not in titlers and s[3][2]>=.16 and s[3][3]>=.035
                       and (not specialized or title_floor+.01<=s[3][1] and s[3][1]+s[3][3]<=.59)),
                      key=lambda s: (s[1].getparent().find("*/p:cNvPr",NS).get("id") not in motion_targets,
                                     -s[3][2]*s[3][3],s[3][1]))
    chosen=sorted(candidates[:len(lines)],key=lambda s:(round(s[3][1],2),s[3][0]))
    total=sum(s[3][2]*s[3][3] for s in chosen)
    load=sum(len(x) for x in lines)
    if lines and (not chosen or total<.022 or load>total*1450):
        # Sparse or image-only master: keep its visual hierarchy and add just one readable text layer.
        area=(.065,max(.31,min(.43,title_floor+.02)),.87,.16) if specialized else (.08,.68,.84,.21)
        add_text(root,area,"\n".join(lines),size,"补充讲述文字",17 if specialized else 19)
    elif chosen:
        for n,slot in enumerate(chosen):
            values[slot[1]]="\n".join(lines[n:]) if n==len(chosen)-1 else lines[n]
    oldmap={}
    for slot in slots:
        name,body,old,box=slot
        if body in values:
            oldmap[old]=values[body]
    hidden=[]
    title_boxes={slot[1]:slot[3] for slot in titlers}
    for name,body,old,box in slots:
        box=title_boxes.get(body,box)
        if body in values:
            value=values[body]
        elif not visible(box):
            value=oldmap.get(old,"")
            if box is not None:
                hidden.append((body,old,box))
        elif (name.lower() in ("page","页码")
              or box[2]<.15 and .045<box[3]<.095 and
              (re.fullmatch(r"0?\d{1,2}",old) or
               body.getparent().find("p:spPr/a:ln",NS) is not None and
               body.getparent().find("p:spPr/a:ln/a:noFill",NS) is None)):
            value=f"{page:02d}"
        elif name.lower() in ("credit","attribution") and not raw.get("image"):
            continue
        else:
            value=""
        # Keep the count of original paragraph targets for per-paragraph timing.
        original_paras=body.findall("a:p",NS)
        old_lines=old.splitlines()
        if len(original_paras)>1 and len(value.split("\n"))<len(original_paras):
            if len(titlers)==1 and body in values and body is titlers[0][1] and len(old_lines)==len(original_paras):
                value="\n".join(split_title(value,[max(1,len(v)) for v in old_lines]))
            else:
                value+="\n"*(len(original_paras)-len(value.split("\n")))
        write_text(body,value)
        if not value.strip() and visible(box) and box[2]<.16 and box[3]<.06:
            # Clearing a template brand should also retire its now-empty label plate.
            paint=body.getparent().find("p:spPr/a:solidFill",NS)
            if paint is not None:
                paint.getparent().replace(paint,ET.Element(f"{{{A}}}noFill"))
        if value.strip():
            fit_native_text(body,value,box,size)
            bp=body.find("a:bodyPr",NS)
            if bp is not None:
                for fit in list(bp):
                    if local(fit) in ("noAutofit","spAutoFit"):
                        bp.remove(fit)
                if bp.find("a:normAutofit",NS) is None:
                    fit=ET.Element(f"{{{A}}}normAutofit")
                    nxt=next((c for c in bp if local(c) in ("scene3d","sp3d","flatTx","extLst")),None)
                    if nxt is None:bp.append(fit)
                    else:nxt.addprevious(fit)
    # Some original labels carry a separate colored plate. Keep its native
    # object and ID for animation, but hide an emptied label and its plate.
    original_labels=[(s[1],s[3]) for s in slots if visible(s[3])]
    for _,_,obj,t in shape_list(root):
        geom=obj.find("p:spPr/a:prstGeom",NS)
        if geom is None or geom.get("prst") not in ("rect","roundRect","wedgeRoundRectCallout","wedgeRectCallout"):
            continue
        b=box_of(obj,t,size)
        if not visible(b) or b[2]>.4 or b[3]>.24 or picture_blip(obj,include_fills=True) is not None:
            continue
        occupants=[body for body,(x,y,w,h) in original_labels
                   if b[0]-.005<=x+w/2<=b[0]+b[2]+.005 and b[1]-.005<=y+h/2<=b[1]+b[3]+.005
                   and w<=b[2]*1.12 and h<=b[3]*1.12]
        if occupants and not any(text_in(body).strip() for body in occupants) and not text_in(obj.find("p:txBody",NS)).strip():
            obj.find("*/p:cNvPr",NS).set("hidden","1")
    return oldmap,hidden


def clear_motion(root, kinds):
    for node in list(root.iter()):
        if local(node) in kinds:
            parent=node.getparent()
            if parent is not None:
                parent.remove(node)
    for container in list(root):
        if local(container)=="AlternateContent" and not any(len(branch) for branch in container):
            root.remove(container)


def motion_settings(root, gr, raw, enabled):
    if not enabled:
        clear_motion(root,{"transition","timing"})
        return
    if "transition" in raw:
        clear_motion(root,{"transition"})
        for node in gr:
            if local(node)=="transition" or local(node)=="AlternateContent" and any(local(n)=="transition" for n in node.iter()):
                before=next((n for n in root if local(n) in ("timing","extLst")),None)
                if before is None:root.append(deepcopy(node))
                else:before.addprevious(deepcopy(node))
    if "animation" in raw:
        clear_motion(root,{"timing"})
        effect=raw["animation"]
        if effect=="none":
            return
        ids=[sid for sid,_,s,t in shape_list(root) if text_in(s.find("p:txBody",NS)).strip()
             and (not t or s.find("p:spPr/a:xfrm",NS) is not None)]
        if not ids:return
        timeline=make_timing(ids,"appear" if effect=="appear" else "fade")
        if effect=="wipe":
            for n in timeline.findall(".//p:animEffect",NS):n.set("filter","wipe(right)")
            for n in timeline.findall(".//p:cTn[@presetClass='entr']",NS):
                n.set("presetID","22");n.set("presetSubtype","8")
        ext=root.find("p:extLst",NS)
        if ext is None:root.append(timeline)
        else:ext.addprevious(timeline)


def full_bleed(box):
    return box and box[0] <= .035 and box[1] <= .035 and box[0]+box[2] >= .96 and box[1]+box[3] >= .96


def animated_gif_ids(relationships, read):
    protected=set()
    for rid,(kind,path) in relationships.items():
        if kind=="image" and path.lower().endswith(".gif"):
            with Image.open(BytesIO(read(path))) as image:
                try: image.seek(1)
                except EOFError: continue
            protected.add(rid)
    return protected


def editable_photos(root,size,out,part,rels):
    links={r.get("Id"):(r.get("Type","").rsplit("/",1)[-1],target(part,r.get("Target","")))
           for r in rels if r.get("TargetMode")!="External"}
    return picture_slots(root,size,animated_gif_ids(links,out.read))


def picture_slots(root, size, moving_ids=()):
    for _, _, shape, transform in shape_list(root):
        blip = picture_blip(shape, include_fills=True)
        box = box_of(shape, transform, size)
        if (blip is not None and blip.get(f"{{{R}}}embed") not in moving_ids and box and box[2]>0 and box[3]>0
                and not any(local(n) in ("videoFile","quickTimeFile","audioFile","wavAudioFile","media") for n in shape.iter())):
            yield shape, blip, box


def image_donor(gr, name):
    return next((s for _, n, s, _ in shape_list(gr) if n == name and picture_blip(s) is not None), None)


def fit_fill(fill, dest_aspect, src_aspect):
    """Crop the source in native OOXML. Reusing the previous artwork's crop can cut off a new subject."""
    crop = fill.find("a:srcRect", NS)
    if crop is None:
        crop = ET.Element(f"{{{A}}}srcRect")
        fill.find("a:blip", NS).addnext(crop)
    crop.attrib.clear()
    if src_aspect > dest_aspect:
        margin = str(round(50000 * (1 - dest_aspect / src_aspect)))
        crop.set("l", margin)
        crop.set("r", margin)
    elif dest_aspect > src_aspect:
        margin = str(round(50000 * (1 - src_aspect / dest_aspect)))
        crop.set("t", margin)
        crop.set("b", margin)
    return crop


def donor_aspect(donor, out, gp):
    rid = picture_blip(donor).get(f"{{{R}}}embed")
    media = out.generated.rels(gp)[rid][1]
    with Image.open(BytesIO(out.generated.zip.read(media))) as img:
        return img.width / img.height


def refit_mask(blip, donor, out, gp, part, rels, aspect):
    fill = blip.getparent()
    donor_blip = deepcopy(picture_blip(donor))
    import_links(donor_blip, out, gp, part, rels)
    blip.set(f"{{{R}}}embed", donor_blip.get(f"{{{R}}}embed"))
    blip.attrib.pop(f"{{{R}}}link", None)
    # Discard source vector fallback links, retaining native alpha, duotone and other color effects.
    for child in list(blip):
        if local(child) == "extLst":
            blip.remove(child)
    fit_fill(fill, aspect, donor_aspect(donor,out,gp))


def update_background(root, raw, gr, out, gp, part, rels):
    size = (out.master.w, out.master.h)
    page_aspect = size[0] / size[1]
    cs = root.find("p:cSld", NS)
    previous = cs.find("p:bg", NS)
    tree = cs.find("p:spTree", NS)
    backdrop = image_donor(gr, "可替换背景图")
    figure = image_donor(gr, "配图")
    masks = [box_of(s,t,size) for _,_,s,t in shape_list(root) if s.get("useBgFill") in ("1","true")]
    masks = [b for b in masks if b and min(1,b[0]+b[2])>max(0,b[0]) and min(1,b[1]+b[3])>max(0,b[1])]
    original_bg = previous is not None and previous.find(".//a:blip", NS) is not None
    native_slots = list(editable_photos(root,size,out,part,rels))
    visible_hero = any(visible(b) and .07 <= b[2]*b[3] and not full_bleed(b) for _,_,b in native_slots)
    full_photos = [s for s in native_slots if full_bleed(s[2])]
    preserve = raw.get("keepTemplateArtwork") is True
    # A slide background can be sampled by freeforms. The left-disc reference uses this
    # mechanism instead of a picture shape; changing text or adding a normal picture misses it.
    requested_replacement = raw.get("keepTemplateArtwork") is False
    if (masks or requested_replacement) and (original_bg or full_photos) and backdrop is None and not raw.get("background") and not preserve and not (masks and figure is not None):
        raise ValueError("模板页含整页图片。请提供与新主题相符的 backgroundImage，或确认原图确实适用后设置 keepTemplateArtwork。")
    if requested_replacement and visible_hero and figure is None:
        raise ValueError("模板页含独立主体图片。请先提交新主题的 image，或在核对原图后确认沿用。")
    if backdrop is None and figure is None and not raw.get("background"):
        return False
    mask_source = figure if masks and figure is not None else None
    bg_source = mask_source if mask_source is not None else backdrop
    if bg_source is None and not raw.get("background"):
        return False

    if bg_source is not None:
        bg = ET.Element(f"{{{P}}}bg")
        bp = ET.SubElement(bg,f"{{{P}}}bgPr")
        fill = deepcopy(bg_source.find("p:blipFill", NS))
        fill.tag = f"{{{A}}}blipFill"
        import_links(fill, out, gp, part, rels)
        fit_fill(fill, page_aspect, donor_aspect(bg_source,out,gp))
        bp.append(fill)
        ET.SubElement(bp,f"{{{A}}}effectLst")
    else:
        bg = deepcopy(gr.find("p:cSld/p:bg", NS))
        if bg is None:
            raise ValueError("生成稿缺少已指定的背景填充。")
    if previous is not None:
        cs.replace(previous,bg)
    else:
        cs.insert(0,bg)

    if mask_source is not None and backdrop is not None:
        # The opaque backdrop lies below native scrims and the animated cutout.
        # PowerPoint's useBgFill cutout continues to sample its own independent subject.
        backdrop_pic = deepcopy(backdrop)
        import_links(backdrop_pic,out,gp,part,rels)
        nv = backdrop_pic.find("*/p:cNvPr",NS)
        nv.set("id",str(1+max(int(n.get("id")) for n in tree.iter(f"{{{P}}}cNvPr"))))
        # Explicitly pair the new photos across Morph frames. Otherwise PowerPoint
        # fades both out at the midpoint and exposes the unpainted scrim beneath.
        nv.set("name","!!叠页背景照片")
        set_box(backdrop_pic,(0,0,1,1),size)
        tree.insert(2,backdrop_pic)
        x,y,w,h = max(masks,key=lambda b:b[2]*b[3])
        x,y,right,bottom = max(0,x),max(0,y),min(1,x+w),min(1,y+h)
        fit_fill(fill, page_aspect*(right-x)/(bottom-y), donor_aspect(mask_source,out,gp))
        dest=fill.find("a:stretch/a:fillRect",NS)
        if dest is not None:
            for key,value in zip(("l","t","r","b"),(x,y,1-right,1-bottom)):
                dest.set(key,str(round(value*100000)))

    for shape,blip,box in full_photos:
        if bg_source is not None:
            refit_mask(blip,backdrop if backdrop is not None else bg_source,out,gp,part,rels,box[2]/box[3]*page_aspect)
        else:
            ET.SubElement(blip,f"{{{A}}}alphaModFix",amt="0")
    return mask_source is not None


CHART_TAG = ".//{http://schemas.openxmlformats.org/drawingml/2006/chart}chart"


def visible_charts(root, size):
    return [s.find(CHART_TAG) for _,_,s,t in shape_list(root)
            if s.find(CHART_TAG) is not None and visible(box_of(s,t,size))]


def remove_chart_timing(root, removed):
    timeline = root.find("p:timing", NS)
    if timeline is None or not removed:
        return
    for node in list(timeline.iter(f"{{{P}}}spTgt")):
        if node.get("spid") not in removed or timeline not in node.iterancestors():
            continue
        owner = node.getparent().getparent()
        if local(owner) not in ("cBhvr", "cMediaNode"):
            raise ValueError("这张原页用图表触发其他动画，请给图表提供新数据或换一张原页。")
        effect = owner.getparent()
        while effect.getparent() is not None:
            container = effect.getparent()
            container.remove(effect)
            if len(container) or local(container) not in ("childTnLst", "subTnLst"):
                break
            common = container.getparent()
            common.remove(container)
            if any(local(child) in ("childTnLst", "subTnLst") and len(child) for child in common):
                break
            effect = common.getparent()
    builds = timeline.find("p:bldLst", NS)
    if builds is not None:
        for build in list(builds):
            if build.get("spid") in removed:
                builds.remove(build)
        if not len(builds):
            timeline.remove(builds)
    nodes = timeline.find("p:tnLst", NS)
    if nodes is None or not len(nodes):
        root.remove(timeline)
        return
    ids = {node.get("id") for node in timeline.iter(f"{{{P}}}cTn")}
    if (any(node.get("spid") in removed for node in timeline.iter()) or
            any(node.get("val") not in ids for node in timeline.iter(f"{{{P}}}tn"))):
        raise ValueError("这张原页的动画依赖已移除的图表，请提供新数据或选择另一张原页。")


def prepare_chart_slots(root, size, has_data, require_chart_motion):
    """Keep at most one editable slot. Purge other charts together with their fallback pictures."""
    frames = [s for s in root.iter(f"{{{P}}}graphicFrame")
              if any(local(child) == "chart" for child in s.iter())]
    if not frames:
        return False
    candidates = []
    for sid, _, shape, transform in shape_list(root):
        if shape not in frames:
            continue
        box = box_of(shape, transform, size)
        nv = shape.find("*/p:cNvPr", NS)
        if nv is not None and nv.get("hidden") not in ("1","true") and visible(box):
            if require_chart_motion and not has_data:
                raise ValueError("选中的放映片段含图表，请补充本页的新图表数据，或调整选页。")
            if (has_data and shape.find(CHART_TAG) is not None and
                    not any(local(p) == "AlternateContent" for p in shape.iterancestors())):
                x,y,w,h = box
                area = max(0,min(1,x+w)-max(0,x))*max(0,min(1,y+h)-max(0,y))
                candidates.append((area, shape))
    keep = max(candidates, key=lambda row:row[0])[1] if candidates else None
    drop = set()
    for frame in frames:
        if frame is not keep:
            alt = next((p for p in frame.iterancestors() if local(p) == "AlternateContent"), None)
            drop.add(alt if alt is not None else frame)
    removed = set()
    for shape in drop:
        removed.update(item.get("id") for item in shape.iter(f"{{{P}}}cNvPr"))
        shape.getparent().remove(shape)
    active = {item.get("id") for item in root.iter(f"{{{P}}}cNvPr")}
    removed -= active
    for cxn in root.xpath(".//a:stCxn|.//a:endCxn", namespaces=NS):
        if cxn.get("id") in removed:
            cxn.getparent().remove(cxn)
    remove_chart_timing(root, removed)
    return keep is not None


def fit_visuals(root, raw, generated_root, out, gp, part, rels, subject_filled):
    image=raw.get("image") or {}
    figure=image and image.get("role","figure")=="figure" and not subject_filled
    if not (raw.get("chart") or raw.get("diagram") or figure):
        return
    size=(out.master.w,out.master.h)
    sources=[]
    for sid,name,s,t in shape_list(generated_root):
        if (raw.get("chart") and s.find(".//{http://schemas.openxmlformats.org/drawingml/2006/chart}chart") is not None
                or figure and name=="配图"
                or raw.get("diagram") and name.startswith(("流程节点","流程连接","图示标签"))):
            sources.append((sid,s,box_of(s,t,(out.generated.w,out.generated.h))))
    if not sources or any(b is None for _,_,b in sources):
        raise ValueError("生成稿缺少所选图表、图示或图片的原生对象。")
    if raw.get("chart"):
        # Keep the original frame and shape ID so its build sequence can target
        # the new chart. Import the donor's workbook along with its chart part.
        charts = visible_charts(root,size)
        if len(charts) == 1:
            replacement = deepcopy(sources[0][1].find(CHART_TAG))
            import_links(replacement,out,gp,part,rels)
            charts[0].getparent().replace(charts[0],replacement)
            return
    if figure:
        slots=list(editable_photos(root,size,out,part,rels))
        candidates=[row for row in slots if visible(row[2]) and .055<=row[2][2]*row[2][3] and not full_bleed(row[2])]
        if candidates:
            _,lead,lead_box=max(candidates,key=lambda row:row[2][2]*row[2][3])
            original=lead.get(f"{{{R}}}embed")
            for shape,blip,box in slots:
                if full_bleed(box):
                    continue
                same_asset=blip.get(f"{{{R}}}embed")==original
                # Also replace alternate animation states sharing this on-stage slot.
                same_frame=all(abs(a-b)<.025 for a,b in zip(lead_box,box))
                if same_asset or same_frame:
                    refit_mask(blip,sources[0][1],out,gp,part,rels,box[2]*size[0]/(box[3]*size[1]))
                    shape.find("*/p:cNvPr",NS).set("descr",str(image.get("alt","")))
            return
    tree=root.find("p:cSld/p:spTree",NS)
    x=min(b[0] for _,_,b in sources);y=min(b[1] for _,_,b in sources)
    w=max(b[0]+b[2] for _,_,b in sources)-x
    h=max(b[1]+b[3] for _,_,b in sources)-y
    area=(.065,.62,.87,.33)
    if figure:
        # Pick a spare region that can actually fit the photo without covering rewritten text.
        occupied=[box_of(s,t,size) for _,_,s,t in shape_list(root) if text_in(s.find("p:txBody",NS)).strip()]
        occupied=[b for b in occupied if visible(b)]
        def free(a):
            x,y,w,h=a
            return all(x+w+.012<=u or u+rw+.012<=x or y+h+.012<=v or v+rh+.012<=y
                       for u,v,rw,rh in occupied)
        aspect=w*out.generated.w*size[1]/(h*out.generated.h*size[0]) if w and h else 1
        boxes=[]
        for width in (.86,.68,.52,.42,.32,.24):
            height=width/aspect
            if height>.86:
                continue
            for left in (.055,.5-width/2,.945-width):
                for top in (.055,.5-height/2,.945-height):
                    boxes.append((left,top,width,height))
        area=next((a for a in boxes if free(a)),None)
        if area is None:
            raise ValueError("这张原稿页没有可容纳配图的空区，请缩短正文或选用另一张模板页。")
    if not w or not h:raise ValueError("图示尺寸无效。")
    ids={}; highest=max(int(n.get("id")) for n in tree.iter(f"{{{P}}}cNvPr"))
    for i,(old,_,_) in enumerate(sources,1):
        ids[old]=str(highest+i)
    for old,s,box in sources:
        clone=deepcopy(s)
        clone.find("*/p:cNvPr",NS).set("id",ids[old])
        for conn in clone.iter():
            if local(conn) in ("stCxn","endCxn") and conn.get("id") in ids:
                conn.set("id",ids[conn.get("id")])
        fit=(area[0]+(box[0]-x)*area[2]/w,area[1]+(box[1]-y)*area[3]/h,
             box[2]*area[2]/w,box[3]*area[3]/h)
        if figure:
            # Letterbox native pictures if there was no replaceable photo.
            scale=min(area[2]*size[0]/(box[2]*out.generated.w),area[3]*size[1]/(box[3]*out.generated.h))
            fw,fh=box[2]*out.generated.w*scale/size[0],box[3]*out.generated.h*scale/size[1]
            fit=(area[0]+(area[2]-fw)/2,area[1]+(area[3]-fh)/2,fw,fh)
        set_box(clone,fit,size)
        import_links(clone,out,gp,part,rels)
        insert_shape(tree,clone)


def notes_for(out, gp, slide_part, rels, native_note, notes_master):
    """Keep the template notes layout and write the new speaker text with independent notes parts."""
    gen=out.generated
    gn=gen.related(gp,"notesSlide")
    if not gn:
        return
    source=out.master if native_note else gen
    old=native_note or gn
    note=deepcopy(source.tree(old))
    new_note=out.allocate(old,source)
    def note_body(root):
        for _,_,s,_ in shape_list(root):
            ph=s.find("p:nvSpPr/p:nvPr/p:ph",NS)
            if ph is not None and ph.get("type")=="body":
                return s.find("p:txBody",NS)
    newbody=note_body(gen.tree(gn))
    oldbody=note_body(note)
    if oldbody is not None and newbody is not None:
        # Native motion governs the template; generated-layout timing instructions would be inaccurate.
        lines=[l for l in text_in(newbody).splitlines() if not l.startswith(("本页入场：","节奏："))]
        if native_note:
            # Author-declared template credits survive replacement of the speaker's old script.
            credits=re.compile(r"^\s*(?:模板(?:作者|署名|授权|许可)|版权(?:声明)?|原作者|"
                               r"template\s+(?:author|credit|licen[cs]e)|copyright|attribution)\s*[:：©]",re.I)
            for line in text_in(oldbody).splitlines():
                if credits.match(line) and line not in lines:
                    lines.append(line)
        write_text(oldbody,"\n".join(lines))
    elif newbody is not None:
        owner=newbody.getparent()
        shape=deepcopy(owner)
        tree=note.find("p:cSld/p:spTree",NS)
        shape.find("p:nvSpPr/p:cNvPr",NS).set("id",str(1+max(int(n.get("id")) for n in tree.iter(f"{{{P}}}cNvPr"))))
        insert_shape(tree,shape)
    nr=deepcopy(source.tree(relpart(old)))
    for r in nr:
        if r.get("TargetMode")=="External":continue
        dest=target(old,r.get("Target"))
        kind=r.get("Type").rsplit("/",1)[-1]
        if kind=="slide":dest=slide_part
        elif kind=="notesMaster":dest=notes_master
        elif source is gen:dest=out.import_part(dest)
        r.set("Target",posixpath.relpath(dest,posixpath.dirname(new_note)))
    out.write_xml(new_note,note);out.write_xml(relpart(new_note),nr)
    relationship(rels,slide_part,"notesSlide",new_note)


def replace_motion_art(completed, frames, raw_slides, treatments, out):
    # Templates often park the adjacent page's photograph outside the slide before
    # a Morph. Match the original media, not the visible page number or shape name.
    size=(out.master.w,out.master.h)
    replacements={}
    hidden=[]
    for i,(entry,frame,gp,raw,mode) in enumerate(zip(completed,frames,out.generated.slides,raw_slides,treatments)):
        if mode=="recompose":
            continue
        part,root,_,_,rels=entry
        before=out.master.tree(frame)
        original_rels=out.master.rels(frame)
        slots=list(picture_slots(before,size,animated_gif_ids(original_rels,out.master.zip.read)))
        current={s.find("*/p:cNvPr",NS).get("id"):(s,b) for s,b,_ in editable_photos(root,size,out,part,rels)}
        figure=image_donor(out.generated.tree(gp),"配图")
        for s,blip,box in slots:
            old_id=blip.get(f"{{{R}}}embed")
            kind,media=original_rels.get(old_id,(None,None))
            sid=s.find("*/p:cNvPr",NS).get("id")
            if kind!="image" or sid not in current or full_bleed(box) or box[2]*box[3]<.055:
                continue
            shape,new_blip=current[sid]
            if visible(box):
                if figure is not None and new_blip.get(f"{{{R}}}embed")!=old_id:
                    replacements.setdefault(media,[]).append((i,figure,gp,(raw.get("image") or {}).get("alt","")))
            else:
                hidden.append((i,media,shape,new_blip,box,part,rels))
    for i,media,shape,blip,box,part,rels in hidden:
        if media not in replacements:
            continue
        direction=-1 if box[1]+box[3]/2<0 or box[0]+box[2]/2<0 else 1
        candidates=replacements[media]
        _,donor,gp,alt=min(candidates,key=lambda item:(abs(item[0]-(i+direction)),abs(item[0]-i)))
        refit_mask(blip,donor,out,gp,part,rels,box[2]*size[0]/(box[3]*size[1]))
        shape.find("*/p:cNvPr",NS).set("descr",alt)


def scale_authored_page(root, master, gen):
    # Donors use a 16:9 canvas. Scale as a group so fonts, photos and drawings keep
    # their proportions inside a reference deck with a different physical size.
    if (master.w,master.h)==(gen.w,gen.h):
        return
    tree=root.find("p:cSld/p:spTree",NS)
    children=[n for n in tree if local(n) not in ("nvGrpSpPr","grpSpPr","extLst")]
    if not children:
        return
    group=ET.Element(f"{{{P}}}grpSp")
    nv=ET.SubElement(group,f"{{{P}}}nvGrpSpPr")
    sid=1+max(int(n.get("id")) for n in tree.iter(f"{{{P}}}cNvPr"))
    ET.SubElement(nv,f"{{{P}}}cNvPr",id=str(sid),name="页面内容")
    ET.SubElement(nv,f"{{{P}}}cNvGrpSpPr")
    ET.SubElement(nv,f"{{{P}}}nvPr")
    transform=ET.SubElement(ET.SubElement(group,f"{{{P}}}grpSpPr"),f"{{{A}}}xfrm")
    scale=min(master.w/gen.w,master.h/gen.h)
    w,h=round(gen.w*scale),round(gen.h*scale)
    for tag,attrs in (("off",{"x":(master.w-w)//2,"y":(master.h-h)//2}),("ext",{"cx":w,"cy":h}),
                      ("chOff",{"x":0,"y":0}),("chExt",{"cx":gen.w,"cy":gen.h})):
        ET.SubElement(transform,f"{{{A}}}"+tag,{k:str(v) for k,v in attrs.items()})
    for child in children:
        group.append(child)
    insert_shape(tree,group)


def assemble_native(template, generated, raw_slides, *, page_count, motion_enabled=True, images_enabled=True,
                    treatments=None, page_offset=0, palette=None, preserve_motion=True, decisions=None, prior_page=None,
                    prior_frames=(), paired_position=None, require_chart_motion=False):
    master=Deck(template)
    try:
        gen=Deck(generated)
        try:
            return _assemble(master,gen,raw_slides,page_count,motion_enabled,images_enabled,treatments or ["retain"]*len(raw_slides),page_offset,palette,preserve_motion,decisions,prior_page,prior_frames,paired_position,require_chart_motion)
        finally:gen.zip.close()
    finally:master.zip.close()


def _assemble(master,gen,raw_slides,count,motion,images,treatments,page_offset,palette,preserve_motion,decisions,prior_page,prior_frames,paired_position,require_chart_motion):
    if not raw_slides or len(gen.slides)!=len(raw_slides) or len(raw_slides)>count:
        raise ValueError("原生套版需要每个已完成页面对应一份生成内容。")
    frames=frame_map(master,raw_slides,count,page_offset,preserve_motion=motion and preserve_motion,
                     treatments=treatments,decisions=decisions,prior_page=prior_page,prior_frames=prior_frames,
                     paired_position=paired_position)
    out=Output(master,gen)
    pp=master.presentation
    presentation=deepcopy(master.tree(pp));rels=deepcopy(master.tree(relpart(pp)))
    listing=presentation.find("p:sldIdLst",NS)
    for child in list(listing):listing.remove(child)
    # User-authored custom shows and sections refer to the old deck's slide IDs.
    for node in list(presentation.iter()):
        if local(node) in ("custShowLst","sectionLst"):
            node.getparent().remove(node)
    for r in list(rels):
        if r.get("Type","").endswith("/slide"):rels.remove(r)
    notes_master=master.related(pp,"notesMaster")
    if not notes_master:
        gn=gen.related(gen.presentation,"notesMaster")
        if gn:
            notes_master=out.import_part(gn)
            rid=relationship(rels,pp,"notesMaster",notes_master)
            nl=presentation.find("p:notesMasterIdLst",NS)
            if nl is None:
                nl=ET.Element(f"{{{P}}}notesMasterIdLst")
                before=next(n for n in presentation if local(n) not in ("sldMasterIdLst",))
                before.addprevious(nl)
            ET.SubElement(nl,f"{{{P}}}notesMasterId",{f"{{{R}}}id":rid})
    new_parts=[out.allocate(old,master) for old in frames]
    completed=[]
    for i,(old,part,raw,gp) in enumerate(zip(frames,new_parts,raw_slides,gen.slides)):
        root=deepcopy(master.tree(old))
        root.attrib.pop("show",None)
        gr=gen.tree(gp)
        sr=deepcopy(master.tree(relpart(old)))
        native_note=master.related(old,"notesSlide")
        for r in list(sr):
            kind=r.get("Type","").rsplit("/",1)[-1]
            if kind in ("notesSlide","comments","threadedComment"):
                sr.remove(r)
            elif kind=="slide" and r.get("TargetMode")!="External":
                linked=target(old,r.get("Target"))
                choices=[n for n,f in enumerate(frames) if f==linked]
                if choices:
                    j=min(choices,key=lambda n:abs(n-i))
                    r.set("Target",posixpath.relpath(new_parts[j],posixpath.dirname(part)))
                else:
                    for n in list(root.iter()):
                        if local(n) in ("hlinkClick","hlinkMouseOver") and n.get(f"{{{R}}}id")==r.get("Id"):
                            n.getparent().remove(n)
                    sr.remove(r)
        if (raw.get("image") or raw.get("backgroundImage")) and not images:
            raise ValueError(f"第 {page_offset+i+1} 页提供了新配图，但配图模块已关闭。")
        if treatments[i]!="recompose":
            if not motion or "animation" in raw:
                # The requested replacement sequence cannot depend on the chart's previous click triggers.
                clear_motion(root, {"timing"})
            native_chart = prepare_chart_slots(root, (master.w,master.h), bool(raw.get("chart")), require_chart_motion)
            specialized=bool((raw.get("chart") and not native_chart) or raw.get("diagram") or raw.get("structuredChart"))
            mapping,hidden=fill_text(root,raw,(master.w,master.h),page_offset+i+1,specialized,
                                     adapt=treatments[i]=="adapt",preserve_motion=motion and "animation" not in raw)
            try:
                subject_filled=update_background(root,raw,gr,out,gp,part,sr)
                fit_visuals(root,raw,gr,out,gp,part,sr,subject_filled)
                if raw.get("structuredChart"):
                    from harness_structured_chart import insert_in_template,set_motion
                    from author import STYLES
                    chart_groups=insert_in_template(root,raw["structuredChart"],(master.w,master.h),palette or STYLES["简约"])
            except ValueError as exc:
                raise ValueError(f"第 {page_offset+i+1} 页：{exc}") from exc
            motion_settings(root,gr,raw,motion)
            if raw.get("structuredChart") and motion:
                set_motion(root,chart_groups,raw.get("animation"))
        else:
            root=deepcopy(gr)
            root.set("showMasterSp","0")
            for r in list(sr):
                if not r.get("Type","").endswith("/slideLayout"):
                    sr.remove(r)
            import_links(root,out,gp,part,sr)
            scale_authored_page(root,master,gen)
            mapping,hidden={},[]
        notes_for(out,gp,part,sr,native_note,notes_master)
        completed.append((part,root,mapping,hidden,sr))
        rid=relationship(rels,pp,"slide",part)
        ET.SubElement(listing,f"{{{P}}}sldId",{"id":str(256+i),f"{{{R}}}id":rid})
    # Match off-stage motion frames to their visible counterparts on adjacent
    # output slides, including template pages reused for a different topic.
    replace_motion_art(completed,frames,raw_slides,treatments,out)
    for i,(part,root,mapping,hidden,sr) in enumerate(completed):
        for body,old,(x,y,w,h) in hidden:
            direction=-1 if y+h/2<0 or x+w/2<0 else 1
            for j in (i+direction,i-direction):
                if 0<=j<len(completed) and old in completed[j][2]:
                    write_text(body,completed[j][2][old])
                    break
        used={v for node in root.iter() for v in node.attrib.values()}
        for rel in list(sr):
            if rel.get("Type","").endswith(("/image","/chart","/chartEx")) and rel.get("Id") not in used:
                sr.remove(rel)
        out.write_xml(part,root)
        out.write_xml(relpart(part),sr)
    out.write_xml(pp,presentation);out.write_xml(relpart(pp),rels)
    package_rels=deepcopy(master.tree(relpart("")))
    for r in list(package_rels):
        if r.get("Type","").endswith("/thumbnail"):package_rels.remove(r)
    out.write_xml(relpart(""),package_rels)
    return out.finish()


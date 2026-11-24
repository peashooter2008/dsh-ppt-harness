"""Editable, open-canvas scenes and bounded, declarative PowerPoint animation programs."""
from copy import deepcopy
from io import BytesIO
from itertools import count
import json
import math
import re

from lxml import etree as ET
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt

from engine import MC, NS, P, _signature, add_transition, el, set_background, transition_spec

SCENE_NS = "urn:slide-studio:native-scene:1"
EXT_URI = "{C6143AC7-042D-4B29-AA67-F05DE2E160E6}"
MORPH_NS = "http://schemas.microsoft.com/office/powerpoint/2015/09/main"
SHAPES = {
    "rect": MSO_SHAPE.RECTANGLE, "roundRect": MSO_SHAPE.ROUNDED_RECTANGLE,
    "ellipse": MSO_SHAPE.OVAL, "triangle": MSO_SHAPE.ISOSCELES_TRIANGLE,
    "diamond": MSO_SHAPE.DIAMOND, "chevron": MSO_SHAPE.CHEVRON,
    "hexagon": MSO_SHAPE.HEXAGON, "arc": MSO_SHAPE.ARC, "arrow": MSO_SHAPE.RIGHT_ARROW,
}
EFFECTS = {
    "enter": ("entr", 1), "fadeIn": ("entr", 10), "exit": ("exit", 1),
    "fadeOut": ("exit", 10), "pulse": ("emph", 6), "scale": ("emph", 6),
    "rotate": ("emph", 8), "move": ("path", 63),
}


def number(value, low, high, label):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} 需为 {low} 至 {high} 之间的数。")
    return value


def paint(value, transparent=False):
    if transparent and value == "none":
        return value
    if not isinstance(value, str) or not re.fullmatch(r"#?[A-Fa-f0-9]{6}", value):
        raise ValueError("颜色请使用 #RRGGBB，形状也可使用 none。")
    return "#" + value.lstrip("#").upper()


def points(value, minimum, maximum, low, high, label):
    if not isinstance(value,list) or not minimum<=len(value)<=maximum:
        raise ValueError(f"{label} 需有 {minimum} 至 {maximum} 个坐标点。")
    for point in value:
        if not isinstance(point,list) or len(point)!=2:
            raise ValueError(f"{label} 的每个点需用 [x,y] 表示。")
        for n in point:
            number(n,low,high,label)
    return value


def program(beats, ids):
    if not isinstance(beats, list) or len(beats) > 64:
        raise ValueError("beats 须为最多 64 个点击组。")
    result = []
    for group in beats:
        if not isinstance(group, list) or not 1 <= len(group) <= 48:
            raise ValueError("每一击由 1 至 48 个动作组成。")
        actions, used = [], set()
        for action in group:
            if not isinstance(action, dict):
                raise ValueError("动作须为对象。")
            target, effect = action.get("target"), action.get("effect")
            if not isinstance(target, str) or target not in ids:
                raise ValueError(f"找不到动作的目标对象 {target}。")
            if not isinstance(effect, str) or effect not in EFFECTS:
                raise ValueError(f"没有可生成的原生动作 {effect}。")
            channel = {"fadeIn":"visibility","enter":"visibility","fadeOut":"visibility","exit":"visibility",
                       "scale":"scale","pulse":"scale"}.get(effect, effect)
            if (target,channel) in used:
                raise ValueError(f"同一击不能为 {target} 重复指定 {channel}。")
            used.add((target,channel))
            a = {"target":str(ids[target]), "effect":effect}
            for field, default in (("durationMs",450),("delayMs",0)):
                val = action.get(field, default)
                if type(val) is not int or not (0 if field == "delayMs" else 1) <= val <= 10000:
                    raise ValueError(f"{field} 需为不超过 10000 的整数毫秒。")
                a[field] = val
            if effect == "move":
                a["dx"] = number(action.get("dx",0),-1920,1920,"dx")
                a["dy"] = number(action.get("dy",0),-1080,1080,"dy")
                if "via" in action:
                    a["via"]=points(action["via"],2,2,-1920,1920,"via")
            elif effect == "rotate":
                a["degrees"] = number(action.get("degrees",90),-1440,1440,"degrees")
            elif effect in ("scale","pulse"):
                a["factor"] = number(action.get("factor",1.12),.1,8,"factor")
            actions.append(a)
        result.append(actions)
    return result


def validate_scene(value, image_loader=None):
    if not isinstance(value, dict):
        raise ValueError("scene 需为含有 objects 的对象。")
    scene = deepcopy(value)
    background = scene.get("background","#FFFFFF")
    if isinstance(background,dict):
        shell = ET.Element(f"{{{P}}}sld")
        el(shell,"cSld")
        set_background(shell,background)
    elif "background" in scene:
        scene["background"] = paint(background)
    objects = scene.get("objects")
    if not isinstance(objects, list) or not 1 <= len(objects) <= 256:
        raise ValueError("一个自由画布需有 1 至 256 个对象。")
    ids = {}
    for obj in objects:
        if not isinstance(obj,dict):
            raise ValueError("每个画布对象需为对象。")
        key, kind = obj.get("id"), obj.get("type")
        if not isinstance(key,str) or not re.fullmatch(r"[\w.-]{1,80}",key) or key in ids:
            raise ValueError("每页需用不重复的对象 id，可包含文字、数字、点、下划线和短横线。")
        ids[key] = key
        box = obj.get("box")
        if not isinstance(box,list) or len(box)!=4:
            raise ValueError(f"{key} 需要绝对位置 box=[x,y,w,h]，画布为 960 × 540 点。")
        for i,v in enumerate(box):
            number(v, -1920 if i<2 else 0, 3840, f"{key}.box[{i}]")
        if kind != "shape" or obj.get("shape","rect") != "line":
            if min(box[2:]) <= 0:
                raise ValueError(f"{key} 的宽高需大于零。")
        number(obj.get("rotation",0),-3600,3600,"rotation")
        if kind=="shape":
            if obj.get("shape","rect") not in (*SHAPES,"line","polygon"):
                raise ValueError(f"{key} 的原生形状不受支持。")
            if obj.get("shape")=="polygon":
                points(obj.get("points"),3,128,0,1,"polygon.points")
            paint(obj.get("fill","#101820"),True)
            paint(obj.get("stroke","#101820" if obj.get("shape")=="line" else "none"),True)
            number(obj.get("strokeWidth",1),.1,100,"strokeWidth")
        elif kind=="text":
            if not isinstance(obj.get("text"),str) or len(obj["text"])>32767:
                raise ValueError(f"{key}.text 需要 32767 字以内的文本。")
            if type(obj.get("bold",False)) is not bool:
                raise ValueError(f"{key}.bold 需要布尔值。")
            number(obj.get("size",24),4,320,"size")
            paint(obj.get("color","#101820"))
            paint(obj.get("fill","none"),True)
            if obj.get("align","left") not in ("left","center","right"):
                raise ValueError("文字 align 可选 left、center、right。")
            if not isinstance(obj.get("font",""),str) or len(obj.get("font",""))>100:
                raise ValueError("字体名称过长或格式无效。")
        elif kind=="image":
            if obj.get("fit","contain") not in ("cover","contain"):
                raise ValueError("图片 fit 可选 cover 或 contain。")
            if image_loader:
                loaded = image_loader(obj)
                obj["data"] = loaded.get("data") or loaded.get("src")
                obj.pop("path",None)
                obj.pop("src",None)
            if not isinstance(obj.get("data"),str) or not re.match(r"^data:image/(?:jpeg|jpg|png);base64,",obj["data"],re.I):
                raise ValueError(f"{key} 需要 PNG/JPEG 配图。")
        elif kind=="chart":
            import author
            chart = obj.get("data")
            if not isinstance(chart,dict) or chart.get("type") not in ("bar","column","line","pie"):
                raise ValueError(f"{key}.data 需为原生图表的类别和数值。")
            author.parse_visual(chart)
            paint(obj.get("accent","#076B71"))
        else:
            raise ValueError(f"{key} 的 type 可选 text、shape、image、chart。")
    for field in ("beats","enhancedBeats"):
        if field in scene:
            scene[field] = program(scene[field],ids)
    if scene.get("enhancedTransition") not in (None,"morph"):
        raise ValueError("增强转场可选 morph。")
    return scene


def legible_text(scene,background):
    """Adjust only text on a known surface; leave photographic detail to visual review."""
    from slidecontrast import _ink, _min_ratio, contrast_bounds
    animated={a["target"] for field in ("beats","enhancedBeats")
              for group in scene.get(field,[]) for a in group}
    layers=[]
    for obj in scene["objects"]:
        x,y,w,h=obj["box"]
        bounds=(x,y,x+w,y+h)
        if obj["type"]=="text":
            surface=background
            for area,fill,opaque in layers:
                if x+w<=area[0] or y+h<=area[1] or x>=area[2] or y>=area[3]:
                    continue
                contains=area[0]<=x and area[1]<=y and area[2]>=x+w and area[3]>=y+h
                surface=fill if contains and opaque else None
            if obj.get("fill","none")!="none":
                surface=obj["fill"]
            if surface is not None:
                ink=paint(obj.get("color","#101820")).lstrip("#")
                shade=contrast_bounds(surface)
                threshold=3 if obj.get("size",24)>=18 or obj.get("bold") and obj.get("size",24)>=14 else 4.5
                if _min_ratio(ink,shade)<threshold:
                    new=_ink(ink,shade)
                    if new is None:
                        obj["fill"]="#FFFFFF"
                        new="20292B"
                    obj["color"]="#"+new
        fill=obj.get("fill","#101820" if obj["type"]=="shape" else "none")
        if fill!="none" or obj["type"] in ("image","chart"):
            opaque=(obj["id"] not in animated and not obj.get("rotation") and fill!="none" and
                    (obj["type"]=="text" or obj.get("shape","rect")=="rect"))
            layers.append((bounds,fill,opaque))


def timing_for(beats):
    timing = ET.Element(f"{{{P}}}timing")
    root = el(el(el(timing,"tnLst"),"par"),"cTn",id=1,dur="indefinite",restart="never",nodeType="tmRoot")
    seq = el(el(root,"childTnLst"),"seq",concurrent=1,nextAc="seek")
    main = el(el(seq,"cTn",id=2,dur="indefinite",nodeType="mainSeq"),"childTnLst")
    numbers = count(3)
    builds = []

    def layer(parent, delay, **attrs):
        node = el(el(parent,"par"),"cTn",id=next(numbers),fill="hold",**attrs)
        el(el(node,"stCondLst"),"cond",delay=delay)
        return el(node,"childTnLst")

    for group in beats:
        click = layer(layer(main,"indefinite"),0)
        for index,a in enumerate(group):
            effect = a["effect"]
            family,preset = EFFECTS[effect]
            attrs = {"autoRev":1} if effect=="pulse" else {"accel":50000,"decel":50000} if effect=="move" else {}
            parent = layer(click,a["delayMs"],presetID=preset,presetClass=family,presetSubtype=0,grpId=len(builds),
                           nodeType="withEffect" if index else "clickEffect",**attrs)
            dur = a["durationMs"]
            sid = a["target"]
            builds.append(sid)

            def behavior(element, duration, attrs=(), delay=None, **node_attrs):
                cb = el(element,"cBhvr")
                node = el(cb,"cTn",id=next(numbers),dur=duration,**node_attrs)
                if delay is not None:
                    el(el(node,"stCondLst"),"cond",delay=delay)
                el(el(cb,"tgtEl"),"spTgt",spid=sid)
                if attrs:
                    names = el(cb,"attrNameLst")
                    for name in attrs:
                        el(names,"attrName").text = name
                return cb

            if effect in ("fadeIn","enter","fadeOut","exit"):
                if effect=="fadeOut":
                    behavior(el(parent,"animEffect",transition="out",filter="fade"),dur)
                setting = el(parent,"set")
                behavior(setting,1,("style.visibility",),delay=dur-1 if effect=="fadeOut" else 0,fill="hold")
                el(el(setting,"to"),"strVal",val="visible" if family=="entr" else "hidden")
                if effect=="fadeIn":
                    behavior(el(parent,"animEffect",transition="in",filter="fade"),dur)
            elif effect=="move":
                route=[*a.get("via",[]),(a["dx"],a["dy"])]
                coords=" ".join(f"{x/960:.8f} {y/540:.8f}" for x,y in route)
                path="M 0 0 "+("C " if "via" in a else "L ")+coords+" E"
                motion = el(parent,"animMotion",origin="layout",path=path,pathEditMode="relative",ptsTypes="")
                behavior(motion,dur,("ppt_x","ppt_y"),fill="hold")
            elif effect=="rotate":
                spin = el(parent,"animRot",by=round(a["degrees"]*60000))
                behavior(spin,dur,("r",),fill="hold")
            else:
                scale = el(parent,"animScale")
                behavior(scale,max(1,dur//2) if effect=="pulse" else dur,fill="hold")
                factor = round(a["factor"]*100000)
                el(scale,"by",x=factor,y=factor)
    for name,event in (("prevCondLst","onPrev"),("nextCondLst","onNext")):
        el(el(el(el(seq,name),"cond",evt=event,delay=0),"tgtEl"),"sldTgt")
    build_list = el(timing,"bldLst")
    for group_id,sid in enumerate(builds):
        el(build_list,"bldP",spid=sid,grpId=group_id,animBg=1)
    return timing


def attach_motion(slide, ids, beats):
    actions = program(beats,ids)
    if not actions:
        return
    root = slide._element
    if root.find("p:timing",NS) is not None:
        raise ValueError("此页已有原生时间线。")
    extensions = root.find("p:extLst",NS)
    if extensions is None:
        extensions = el(root,"extLst")
    marker = ET.SubElement(el(extensions,"ext",uri=EXT_URI),f"{{{SCENE_NS}}}program")
    marker.text = json.dumps(actions,ensure_ascii=False,separators=(",",":"))
    root.insert(root.index(extensions),timing_for(actions))


def scene_objects(slide):
    # Native scenes target whole, top-level objects, including compound mechanisms.
    tree=slide.find("p:cSld/p:spTree",NS)
    result={}
    if tree is not None:
        for node in tree:
            nv=node.find("*/p:cNvPr",NS)
            if nv is not None:
                result[nv.get("id")]=node
    return result


def supported_states(beats, scalable, charts):
    # Layout resizing cannot reproduce animated text glyphs, chart labels or strokes.
    # Repeated paths can be relative to a previous animation rather than the layout.
    transformed=set()
    for group in beats:
        for action in group:
            key,effect=action["target"],action["effect"]
            if effect=="scale" and key not in scalable:
                return False
            if effect=="rotate" and key in charts:
                return False
            if effect in ("move","scale","rotate"):
                if (key,effect) in transformed:
                    return False
                transformed.add((key,effect))
    return True


def rehearsal_count(scene):
    beats=scene.get("beats",[])
    scalable={obj["id"] for obj in scene["objects"] if obj["type"]=="image" or
              (obj["type"]=="shape" and obj.get("shape")!="line" and obj.get("stroke","none")=="none")}
    charts={obj["id"] for obj in scene["objects"] if obj["type"]=="chart"}
    return len(beats) if supported_states(beats,scalable,charts) else None


def read_program(slide):
    marker = slide.find(f"p:extLst/p:ext[@uri='{EXT_URI}']/{{{SCENE_NS}}}program",NS)
    if marker is None or not marker.text or len(marker.text)>1024*1024:
        return None
    timing = slide.find("p:timing",NS)
    if timing is None:
        return None
    objects=scene_objects(slide)
    ids = {sid:sid for sid in objects}
    try:
        beats = program(json.loads(marker.text),ids)
        scalable={sid for sid,node in objects.items() if node.tag==f"{{{P}}}pic" or
                  (node.tag==f"{{{P}}}sp" and node.find(".//a:t",NS) is None and
                   node.find("p:spPr/a:ln/a:noFill",NS) is not None)}
        charts={sid for sid,node in objects.items() if node.tag==f"{{{P}}}graphicFrame"}
        if supported_states(beats,scalable,charts) and _signature(timing_for(beats))==_signature(timing):
            return beats
    except (ValueError,TypeError,KeyError):
        pass
    return None


def freeze_scene(slide, beats, beat):
    objects = scene_objects(slide)
    visible = {}
    for group in beats:
        for a in group:
            if a["effect"] in ("enter","fadeIn","exit","fadeOut"):
                visible.setdefault(a["target"],a["effect"] in ("exit","fadeOut"))
    for group in beats[:beat]:
        for a in group:
            sid,effect = a["target"],a["effect"]
            if effect in ("enter","fadeIn","exit","fadeOut"):
                visible[sid] = effect in ("enter","fadeIn")
                continue
            xf = objects[sid].find("p:spPr/a:xfrm",NS)
            if xf is None:
                xf = objects[sid].find("p:xfrm",NS)
            if xf is None:
                xf = objects[sid].find("p:grpSpPr/a:xfrm",NS)
            if xf is None or effect=="pulse":
                continue
            off,ext = xf.find("a:off",NS),xf.find("a:ext",NS)
            if effect=="move":
                for axis,distance in (("x",a["dx"]),("y",a["dy"])):
                    off.set(axis,str(int(off.get(axis))+round(Pt(distance))))
            elif effect=="rotate":
                xf.set("rot",str((int(xf.get("rot","0"))+round(a["degrees"]*60000))%21600000))
            elif effect=="scale":
                for axis,key in (("x","cx"),("y","cy")):
                    old = int(ext.get(key))
                    new = round(old*a["factor"])
                    off.set(axis,str(int(off.get(axis))+round((old-new)/2)))
                    ext.set(key,str(new))
    for sid,node in objects.items():
        if not visible.get(sid,True):
            node.getparent().remove(node)
    slide.remove(slide.find("p:timing",NS))
    return slide


def add_morph(slide):
    root = slide._element
    alt = ET.Element(f"{{{MC}}}AlternateContent",nsmap={"mc":MC})
    choice = ET.SubElement(alt,f"{{{MC}}}Choice",Requires="p159",nsmap={"p159":MORPH_NS})
    fallback = ET.SubElement(alt,f"{{{MC}}}Fallback")
    ET.SubElement(el(choice,"transition",spd="med",advClick="1"),f"{{{MORPH_NS}}}morph",option="byObject")
    el(el(fallback,"transition",spd="med",advClick="1"),"fade")
    for idx,child in enumerate(root):
        if child.tag in (f"{{{P}}}timing",f"{{{P}}}extLst"):
            root.insert(idx,alt)
            break
    else:
        root.append(alt)


def draw_object(slide,obj):
    import author
    box = obj["box"]
    x,y,w,h = box
    kind = obj["type"]
    if kind=="text":
        align = {"left":PP_ALIGN.LEFT,"center":PP_ALIGN.CENTER,"right":PP_ALIGN.RIGHT}
        s = author.text(slide,obj["text"],box,obj.get("size",24),obj.get("color","#101820"),name=obj["id"],
                        bold=obj.get("bold",False),family=obj.get("font","Microsoft YaHei"),
                        align=align[obj.get("align","left")],prefer_single_line=False)
        if obj.get("fill","none")!="none":
            s.fill.solid()
            s.fill.fore_color.rgb=author.color(obj["fill"])
    elif kind=="image":
        raw,iw,ih = author.parse_visual({"type":"image","data":obj["data"]})["image"]
        cover = obj.get("fit")=="cover"
        ratio = (max if cover else min)(w/iw,h/ih)
        pw,ph = iw*ratio,ih*ratio
        if cover:
            s = slide.shapes.add_picture(BytesIO(raw),Pt(x),Pt(y),Pt(w),Pt(h))
            s.crop_left = s.crop_right = max(0,(1-w/pw)/2)
            s.crop_top = s.crop_bottom = max(0,(1-h/ph)/2)
        else:
            s = slide.shapes.add_picture(BytesIO(raw),Pt(x+(w-pw)/2),Pt(y+(h-ph)/2),Pt(pw),Pt(ph))
        s._element.nvPicPr.cNvPr.set("descr",str(obj.get("alt",""))[:2048])
    elif kind=="chart":
        accent=paint(obj.get("accent","#076B71")).lstrip("#")
        s=author.place_visual(slide,author.parse_visual(obj["data"]),box,["FFFFFF","101820",accent])
    else:
        name = obj.get("shape","rect")
        if name=="line":
            s = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Pt(x),Pt(y),Pt(x+w),Pt(y+h))
        else:
            if name=="polygon":
                vertices=[(round(xx*10000),round(yy*10000)) for xx,yy in obj["points"]]
                builder=slide.shapes.build_freeform(*vertices[0],scale=(Pt(w)/10000,Pt(h)/10000))
                builder.add_line_segments(vertices[1:],close=True)
                s=builder.convert_to_shape(Pt(x),Pt(y))
            else:
                s = slide.shapes.add_shape(SHAPES[name],*[Pt(v) for v in box])
            fill = obj.get("fill","#101820")
            if fill=="none":
                s.fill.background()
            else:
                s.fill.solid()
                s.fill.fore_color.rgb = author.color(fill)
        stroke = obj.get("stroke","#101820" if name=="line" else "none")
        if stroke=="none":
            s.line.fill.background()
        else:
            s.line.color.rgb = author.color(stroke)
            s.line.width = Pt(obj.get("strokeWidth",1))
    s.name = "!!"+obj["id"]
    s.rotation = obj.get("rotation",0)
    return s


def add_scene(prs,page,motion_mode):
    scene = validate_scene(page["scene"])
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background=scene.get("background",page.get("background","#FFFFFF"))
    set_background(slide._element,background)
    legible_text(scene,background)
    ids = {obj["id"]:draw_object(slide,obj).shape_id for obj in scene["objects"]}
    if motion_mode=="enhanced" and scene.get("enhancedTransition")=="morph":
        add_morph(slide)
    else:
        default={"type":"none"} if len(prs.slides)==1 else {"type":"fade","durationMs":450}
        add_transition(slide._element,transition_spec(page.get("transition",default)))
    beats = scene.get("enhancedBeats",scene.get("beats",[])) if motion_mode=="enhanced" else scene.get("beats",[])
    attach_motion(slide,ids,beats)
    import author
    lines = [page["title"], *author.input_lines(page), page.get("caption"),page.get("source"),page.get("notes")]
    if beats:
        lines.append("点击顺序："+" → ".join(" + ".join(a["target"] for a in group) for group in beats))
    slide.notes_slide.notes_text_frame.text = "\n".join(str(line) for line in lines if line)
    return slide

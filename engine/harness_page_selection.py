"""Match submitted material to the usable layout of each native template slide."""
from dataclasses import dataclass

from engine import NS, R, local, picture_blip, shape_list, text_in


@dataclass(frozen=True)
class Frame:
    part: str
    number: int
    body_slots: int
    body_capacity: int
    columns: bool
    charts: int
    table: bool
    photo: bool
    subject_images: int
    picture_background: bool
    lower_space: float
    keywords: str
    phrases: frozenset


def describe_frame(master, part, number):
    from harness_template_deck import box_of, full_bleed, visible

    root = master.tree(part)
    slots, occupancy, labels = [], [], []
    phrases = set()
    charts = 0
    table = photo = False
    subject_assets = set()
    rels = master.rels(part)
    backdrop = root.find("p:cSld/p:bg/p:bgPr/a:blipFill/a:blip",NS) is not None
    # The donor renderer places new diagrams and charts in this region. An old
    # native chart can instead receive new data at its existing coordinates.
    left, top, right, bottom = .065, .62, .935, .95
    for _, name, shape, transform in shape_list(root):
        nv = shape.find("*/p:cNvPr", NS)
        if nv is not None and nv.get("hidden") in ("1", "true"):
            continue
        box = box_of(shape, transform, (master.w, master.h))
        ph = shape.find("p:nvSpPr/p:nvPr/p:ph", NS)
        if box is None and ph is not None:
            box = (.06,.05,.85,.14) if ph.get("type") in ("title","ctrTitle") else (.08,.30,.84,.45)
        if not visible(box):
            continue
        x,y,w,h = box
        value = text_in(shape.find("p:txBody", NS)).strip()
        graphic = local(shape) == "graphicFrame"
        blip = picture_blip(shape,include_fills=True)
        pic = blip is not None or shape.get("useBgFill") in ("1","true")
        if w >= .16 and h >= .035 and value:
            slots.append((x,y,w,h))
            labels.extend((name, value[:60]))
            if len(value) >= 3 and not value.isdecimal():
                phrases.add(value[:90].casefold())
        if graphic:
            charts += int(any(local(node) == "chart" for node in shape.iter()))
            table |= shape.find(".//a:tbl", NS) is not None
        if pic and not full_bleed(box) and w*h >= .055:
            photo = True
        if blip is not None:
            asset = rels.get(blip.get(f"{{{R}}}embed"), ("",""))[1]
            # Raster fallbacks for native 3D models are part of the model. The
            # verified replacement ballot is also safe to retain on election pages.
            if full_bleed(box):
                backdrop = True
            elif (w*h >= .055 and not asset.startswith("ppt/media/ballot-")
                  and not name.startswith(("3D 模型","3D Model"))):
                subject_assets.add(asset)
        if not full_bleed(box) and (pic or value or graphic):
            overlap = max(0, min(right,x+w)-max(left,x))*max(0,min(bottom,y+h)-max(top,y))
            occupancy.append(overlap)
    # Use a prominent editable text shape for the headline. Budget only what
    # remains for body copy. Small side labels have little usable capacity.
    if slots:
        slots.remove(max(slots, key=lambda b: min(.9,b[2])*b[3]*(1.3-b[1])))
    body = [b for b in slots if b[2] >= .19 and b[3] >= .045]
    # Two comparable blocks on the same text row. Compare each with previously
    # seen left edges on nearby rows rather than scanning every pair of shapes.
    row_ends = {}
    columns = False
    for x,y,w,h in sorted(body):
        row = round(y*20)
        if any(row_ends.get(j,2) <= x+.035 for j in (row-1,row,row+1)):
            columns = True
            break
        row_ends[row] = min(row_ends.get(row,2),x+w)
    space = max(0, 1-sum(occupancy)/((right-left)*(bottom-top)))
    return Frame(part,number,len(body),round(sum(w*h for x,y,w,h in body)*900),
                 columns,charts,table,photo,len(subject_assets),backdrop,space," ".join(labels).casefold(),frozenset(phrases))


def requested_role(spec, number, count):
    if spec.get("chart"):
        return "数据比较"
    if spec.get("structuredChart") or spec.get("diagram"):
        return "结构讲解"
    if (spec.get("image") or {}).get("role","figure") == "figure" and spec.get("image"):
        return "图片讲解"
    if spec.get("layout") == "compare" or spec.get("composition") == "spread":
        return "并列比较"
    if number == 1:
        return "开场"
    if number == count:
        return "收束"
    title = str(spec.get("title",""))
    if any(s in title for s in ("为什么","为何","问题","难点","痛点","？","?")):
        return "提出问题"
    if any(s in title for s in ("下一步","计划","行动","路径","方案","做法")):
        return "行动方案"
    return "展开论点"


ROLE_WORDS = {
    "收束": ("结论","总结","谢谢","感谢","thank","终句","结语","回应"),
    "提出问题": ("问题","why","难点","观察","挑战","?","？"),
    "行动方案": ("计划","路径","方案","行动","步骤","安排","承诺"),
    "并列比较": ("比较","对照","差异","两组","前后"),
}


def compatible_frames(frames, role):
    # A single native chart can receive the new series. Tables and other old
    # chart data must not be carried into unrelated material.
    return [f for f in frames if not f.table and f.charts <= (1 if role == "数据比较" else 0)]


def choose_frame(frames, spec, number, count, uses, previous, successor=None, run_length=0, *, candidates=None):
    role = requested_role(spec,number,count)
    n_lines = len(spec.get("body") or [])
    load = sum(len(s) for s in spec.get("body") or [])
    first, last = frames[0], frames[-1]
    progress = (number-1)/max(1,count-1)
    prior = next((f for f in frames if f.part == previous),None)
    condensed = count < len(frames)
    replacing_photo = role == "图片讲解"
    retaining_art = spec.get("keepTemplateArtwork") is True

    def score(f):
        # Reuse and original order break close calls. Strong fits can be reused.
        val = -min(uses[f.part],5)*(5 if condensed else 2.2) - (4 if f.part == previous else 0)
        distance = abs(progress-(f.number-first.number)/max(1,last.number-first.number))
        val -= (7 if condensed else 1.4)*distance
        if condensed and prior and f.number < prior.number:
            val -= min(6,1+(prior.number-f.number)*.7)
        if condensed:
            # Leave room for the rest of the talk. A particularly good fit
            # can still beat this penalty (e.g. the only native chart).
            val -= 5*max(0, (count-number)-(last.number-f.number))
            if prior and run_length >= 2 and f.phrases and prior.phrases:
                same = len(f.phrases & prior.phrases)/min(len(f.phrases),len(prior.phrases))
                if same >= .7:
                    val -= 5
        if not retaining_art:
            val -= 8*min(3,max(0,f.subject_images-int(replacing_photo)))
            if f.picture_background and not (spec.get("background") or spec.get("backgroundImage") or replacing_photo):
                val -= 7
        # A single paired transition can win a near tie. A long deck made
        # entirely of Morph destinations must still follow the new talk's story.
        if f.part == successor:
            val += 1 if run_length >= 2 and condensed else 3.5
        val -= min(7, max(0, load-f.body_capacity)/12)
        val -= min(3, max(0, n_lines-f.body_slots))
        if role == "开场":
            val += 15 if f == first else 0
        elif role == "收束":
            val += 7 if f == last else 0
        else:
            val -= 5 if f in (first,last) and len(frames)>2 else 0
        if role == "数据比较":
            val += 13 if f.charts == 1 else 6*f.lower_space
        elif role == "图片讲解":
            val += 14 if f.photo else 2*f.lower_space
        elif role == "结构讲解":
            val += 10*f.lower_space
        elif role == "并列比较":
            val += 10 if f.columns else 3 if f.body_slots >= max(2,n_lines) else 0
        if role not in ("开场","收束","结构讲解","数据比较"):
            val += min(n_lines,f.body_slots)*1.8
        if any(s in f.keywords for s in ROLE_WORDS.get(role,())):
            val += 4
        return val

    if candidates is None:
        candidates = frames
    if not spec.get("keepTemplateArtwork"):
        # Existing table cells and charts carry the previous topic's data.
        # Only a single native chart has an unambiguous replacement.
        compatible = compatible_frames(candidates, role)
        if compatible:
            candidates = compatible
    choice = max(candidates,key=score)
    if role == "数据比较" and choice.charts == 1:
        detail = "沿用原页图表的位置，写入本页数据"
    elif role == "图片讲解" and choice.photo:
        detail = "原页有可替换的主体图片区域"
    elif role == "并列比较" and choice.columns:
        detail = "原页有并排的文字区域"
    elif role == "结构讲解":
        detail = "按原页下方可用空间安排图示"
    elif role == "开场" and choice == first:
        detail = "使用模板的首张可见页引入主题"
    elif role == "收束" and choice == last:
        detail = "使用模板末张可见页收束讲述"
    else:
        detail = f"原页含 {choice.body_slots} 个可用正文框，已考虑本次文字量和相邻页"
    if uses[choice.part] and len(frames)>1 and compatible_frames(frames,role)==[choice]:
        detail += "；本模板只有这一张原页适合当前内容，其余页含其他图表或表格"
    if choice.part == successor:
        detail += "，接续原平滑切换"
    return choice, role+" · "+detail

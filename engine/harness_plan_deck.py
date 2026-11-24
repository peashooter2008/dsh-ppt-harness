"""Build a new native PowerPoint revision from the pages supplied by the Harness agent."""

import argparse
import base64
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
import sys
from uuid import uuid4

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Pt

from author import ALIASES, RECT, STYLES, color, composition_options, input_lines, length, make_deck, physical_count, shape, template_style, text
from election_opening import field, read_photo, resolve_child
from engine import NS, make_timing
from harness_templates import masters, master_bytes, safe_source
from template_rights import replace_restricted_photo
from native import PreviewSession
from slidecontrast import apply_readability, contrast_ratio
from harness_chart_colors import chart_color_history


def reference_bytes(key):
    if not key:
        return None
    item = next((m for m in masters() if m.id == key), None)
    if not item or not safe_source(item.source):
        raise ValueError("所选模板当前不可用，请刷新模板库。")
    return master_bytes(item)


def requested_template(request, root):
    asset = request.get("templateAsset")
    if asset is None:
        return reference_bytes(request.get("templateId"))
    asset_name = r"assets/(?:[a-f0-9]{64}|[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12})\.pptx"
    if request.get("templateId") or not isinstance(asset, str) or not re.fullmatch(asset_name, asset):
        raise ValueError("参考模板须为一个已入库的模板或本任务中已上传的 PPTX。")
    source = resolve_child(root, asset)
    if not source.is_file() or source.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("上传的参考稿不可用，或文件超过 256 MiB。")
    return replace_restricted_photo(source.read_bytes())


def slide_spec(raw, root, number):
    if not isinstance(raw, dict):
        raise ValueError("页面材料应为对象。")
    spec = {key: field(raw, key, limit) for key, limit in
            (("title", 180), ("notes", 24000), ("caption", 500), ("source", 2000))}
    if not spec["title"]:
        raise ValueError("缺少该页标题。")
    lines = input_lines(raw)
    spec["body"] = [field({"body": line}, "body", 32767) for line in lines]
    diagram = None
    if raw.get("diagram") is not None:
        diagram = raw["diagram"]
        if not isinstance(diagram,dict) or not isinstance(diagram.get("steps"),list) or not 2<=len(diagram["steps"])<=5:
            raise ValueError("流程图须包含 2 至 5 个步骤。")
        if any(not isinstance(s,str) or not s.strip() or not s.isprintable() or length(s.strip())>22 for s in diagram["steps"]):
            raise ValueError("每个步骤须为一行短语，最多约 22 个汉字。")
        if raw.get("chart") is not None or (raw.get("image") and (not isinstance(raw["image"],dict) or raw["image"].get("role")!="background")):
            raise ValueError("流程图作为本页主视觉，仅可再选择背景图片。")
        visible, detail = [], []
        for line in spec["body"]:
            (visible if len(visible)<2 and length(line)<=48 else detail).append(line)
        if detail:
            spec["notes"] = "\n".join(filter(None,[spec["notes"],"流程补充：",*detail]))
        label = field(diagram,"label",80)
        if "\n" in label or length(label)>55:
            raise ValueError("图示标签须为一行短句。")
        diagram = dict(steps=[s.strip() for s in diagram["steps"]],label=label,body=visible)
        spec["body"] = []
    if physical_count(spec) != 1:
        raise ValueError("该页材料超出单页容量，请把详细内容移入备注或调整分页。")
    if "layout" in raw:
        if raw["layout"] not in ("focus", "compare"):
            raise ValueError("布局须为 focus 或 compare。")
        spec["layout"] = raw["layout"]
    if "composition" in raw and not diagram:
        spec["composition"] = raw["composition"]
    if "background" in raw:
        spec["background"] = raw["background"]
    animation = raw.get("animation", "none")
    if animation not in ("none", "appear", "fade", "wipe"):
        raise ValueError("动画须为 none、appear、fade 或 wipe。")
    # The author's existing fade sequence provides the same grouping and timing as a wipe.
    spec["reveal"] = "fade" if animation == "wipe" else animation
    transition = raw.get("transition", "none" if number == 1 else "fade")
    spec["transition"] = {"type": transition} if isinstance(transition, str) else transition

    chart = raw.get("chart")
    if chart is not None:
        if not isinstance(chart, dict) or chart.get("type") not in ("bar", "column", "line", "pie"):
            raise ValueError("图表类型须为 bar、column、line 或 pie。")
        spec["visual"] = chart
    picture = raw.get("image")
    background = None
    if picture is not None:
        if not isinstance(picture, dict) or not isinstance(picture.get("asset"), str) or not picture["asset"]:
            raise ValueError("配图必须引用本任务中已有的图片。")
        role = picture.get("role", "figure")
        if role not in ("background", "figure"):
            raise ValueError("图片用途须为 figure 或 background。")
        if role == "figure" and chart is not None:
            raise ValueError("该页主视觉已是图表，图片可用作背景。")
        image = read_photo(root, picture["asset"])
        alt = field(picture, "alt", 600)
        if role == "background":
            if "background" in raw:
                raise ValueError("图片背景和背景色请择一使用。")
            background = (image, alt)
        else:
            with Image.open(BytesIO(image[0])) as verified:
                mime = Image.MIME[verified.format]
            spec["visual"] = {"type": "image", "alt": alt,
                              "data": f"data:{mime};base64," + base64.b64encode(image[0]).decode("ascii")}
    separate = raw.get("backgroundImage")
    if separate is not None:
        if background is not None or raw.get("background"):
            raise ValueError("请在背景色、背景配图和独立背景图片中选择一种。")
        if not isinstance(separate, dict) or not isinstance(separate.get("asset"), str) or not separate["asset"]:
            raise ValueError("独立背景图须引用本任务中的图片。")
        background = (read_photo(root, separate["asset"]), field(separate, "alt", 600))
    return spec, background, animation, diagram


def place_diagram(slide, diagram, style, animation, *, column=False, palette=None):
    palette = palette or STYLES[style]
    title = next(s for s in slide.shapes if s.name=="标题")
    if style=="中国风" and not column:
        title.left,title.top,title.width,title.height=map(Pt,(55,30,805,82))
    top=42 if column else max(150,title.top.pt+title.height.pt+18)
    bottom=min([492]+[s.top.pt-12 for s in slide.shapes if s.name in ("图注或结论","来源")])
    label,body=diagram["label"],diagram["body"]
    label_h=28 if label and not column else 0
    body_h=28*len(body) if not column else 0
    available=bottom-top-label_h-body_h
    if available<60:
        raise ValueError("流程图与较长图注在本页放不下，请将图注详述移入备注。")
    steps=diagram["steps"]
    if column:
        gap=16
        node_h=min(70,(available-(len(steps)-1)*gap)/len(steps))
        node_w=382
        left=494
    else:
        gap=36
        node_h=min(86,available-12)
        node_w=(832-gap*(len(steps)-1))/len(steps)
        left=64
    y=top+(available-node_h)/2+label_h
    if column:
        y=top+(available-len(steps)*node_h-(len(steps)-1)*gap)/2
    if label:
        label_box=(48,30,364,48) if column else (64,y-35,830,27)
        label_color=palette[4]
        text(slide,label,label_box,17,label_color,name="图示标签",bold=True)
    nodes=[]
    for i,value in enumerate(steps):
        nx=left if column else left+i*(node_w+gap)
        ny=y+i*(node_h+gap) if column else y
        node=shape(slide,RECT,(nx,ny,node_w,node_h),palette[3],f"流程节点 {i+1}",palette[2])
        tf=node.text_frame
        tf.clear();tf.word_wrap=True;tf.vertical_anchor=MSO_ANCHOR.MIDDLE
        tf.margin_left=tf.margin_right=Pt(8)
        p=tf.paragraphs[0];p.alignment=PP_ALIGN.CENTER
        run=p.add_run();run.text=value;run.font.name="Microsoft YaHei";run.font.bold=True
        ea=OxmlElement("a:ea");ea.set("typeface","Microsoft YaHei");run._r.get_or_add_rPr().append(ea)
        run.font.size=Pt(min(23, max(13, int((node_w-16)*2/max(1,length(value))))))
        run.font.color.rgb=color(max((palette[1],"181C20","FFFFFF"),key=lambda c:contrast_ratio(c,palette[3])))
        nodes.append(node)
    ids=[str(nodes[0].shape_id)]
    together=[]
    for i,(before,after) in enumerate(zip(nodes,nodes[1:]),1):
        points=(before.left+before.width//2,before.top+before.height,after.left+after.width//2,after.top) if column else (
            before.left+before.width,before.top+before.height//2,after.left,after.top+after.height//2)
        connector=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,*points)
        connector.name=f"流程连接 {i} → {i+1}"
        connector.begin_connect(before,2 if column else 3);connector.end_connect(after,0 if column else 1)
        connector.line.color.rgb=color(palette[2]);connector.line.width=Pt(2.5)
        arrow=OxmlElement("a:tailEnd");arrow.set("type","triangle")
        connector.line._get_or_add_ln().append(arrow)
        ids.extend((str(after.shape_id),str(connector.shape_id)))
        together.append(str(connector.shape_id))
    for i,line in enumerate(body):
        if column:
            row_h=(bottom-280)/len(body)
            box=(48,280+i*row_h,340,row_h-4)
            ink=palette[1]
        else:
            box=(64,y+node_h+7+i*28,832,26)
            ink=palette[1]
        text(slide,line,box,17,ink,name=f"图示说明 {i+1}")
    apply_readability(slide._element, palette)
    if animation!="none":
        slide._element.append(make_timing(ids,"appear" if animation=="appear" else "fade",together))
        notes=slide.notes_slide.notes_text_frame
        notes.text=notes.text.removesuffix("节奏：整页静态展示，可直接讲述。")+"节奏：逐次点击呈现 "+" → ".join(steps)+"。"


def place_background(slide, background, style, width, height):
    (raw, iw, ih), alt = background
    picture = slide.shapes.add_picture(BytesIO(raw), 0, 0, width, height)
    picture.name = "可替换背景图"
    picture._element.nvPicPr.cNvPr.set("descr", alt)
    width_ratio = width / height / (iw / ih)
    if width_ratio < 1:
        picture.crop_left = picture.crop_right = (1 - width_ratio) / 2
    else:
        picture.crop_top = picture.crop_bottom = (1 - 1 / width_ratio) / 2
    overlay = shape(slide, RECT, (0, 0, width.pt, height.pt), STYLES[style][0], "背景图阅读遮罩")
    alpha = OxmlElement("a:alpha")
    alpha.set("val", "82000")
    overlay._element.xpath(".//a:solidFill/a:srgbClr")[0].append(alpha)
    tree = slide.shapes._spTree
    # Following nvGrpSpPr/grpSpPr and behind the editable text, charts and other art.
    tree.insert(2, picture._element)
    tree.insert(3, overlay._element)


def finish_motion(slide, animation):
    if animation == "none":
        return
    root = slide._element
    timing = root.find("p:timing", NS)
    if timing is None:
        # A title-only or visual-only opening can also have an explicit reveal.
        target = next((s for s in slide.shapes if s.has_chart or
                       (s.shape_type == MSO_SHAPE_TYPE.PICTURE and s.name != "可替换背景图")), None)
        if target is None:
            target = next((s for s in slide.shapes if s.name == "标题"), None)
        if target is None:
            return
        timing = make_timing([str(target.shape_id)], "appear" if animation == "appear" else "fade")
        root.append(timing)
        notes = slide.notes_slide.notes_text_frame
        notes.text = notes.text.removesuffix("节奏：整页静态展示，可直接讲述。") + f"节奏：单击显示{target.name}。"
    if animation == "wipe":
        for effect in timing.findall(".//p:animEffect", NS):
            effect.set("filter", "wipe(right)")
        for node in timing.findall(".//p:cTn[@presetClass='entr']", NS):
            node.set("presetID", "22")
            node.set("presetSubtype", "8")


def page_role(raw, number, total):
    if raw.get("diagram"):
        return "process"
    if raw.get("chart"):
        return "evidence"
    if isinstance(raw.get("image"),dict) and raw["image"].get("role", "figure") == "figure":
        return "figure"
    if number == 1:
        return "opening"
    if number == total:
        return "closing"
    return "argument"


def motion_defaults(raw, level, role, first, enabled):
    page = dict(raw)
    if not enabled:
        page.update(animation="none", transition="none")
        return page
    if level not in ("balanced", "bold"):
        return page
    if "animation" not in page:
        if role == "process":
            page["animation"] = "wipe" if level == "bold" else "appear"
        elif len(page.get("body") or []) >= 2:
            page["animation"] = "fade"
    if "transition" not in page and not first:
        directed = level == "bold" and role in ("process", "closing")
        page["transition"] = ({"type": "push", "durationMs": 390, "direction": "left"} if directed
                              else {"type": "fade", "durationMs": 420})
    return page


def fit_textbox(obj, rect, preferred, bold):
    """Refit the editable runs in-place, retaining their shape ID and animation targets."""
    x, y, w, h = rect
    obj.left, obj.top, obj.width, obj.height = map(Pt, (x,y,w,h))
    lines = obj.text.splitlines() or [""]
    size = preferred
    while size > 11:
        rows = sum(max(1, math.ceil(length(line)*size/(w*.88))) for line in lines)
        if rows*size*1.27 <= h:
            break
        size -= 1
    for paragraph in obj.text_frame.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(size)
            run.font.bold = bold


def fit_figure(obj, box):
    x,y,w,h=box
    if obj.shape_type == MSO_SHAPE_TYPE.PICTURE:
        scale=min(w/obj.width.pt,h/obj.height.pt)
        pw,ph=obj.width.pt*scale,obj.height.pt*scale
        x,y,w,h=x+(w-pw)/2,y+(h-ph)/2,pw,ph
    obj.left,obj.top,obj.width,obj.height=map(Pt,(x,y,w,h))


TREATMENTS = ("retain", "adapt", "recompose")


def treatment_for(raw, cap, template):
    requested = raw.get("designTreatment", "retain" if template is not None else "adapt")
    if requested not in TREATMENTS:
        raise ValueError("页面设计方式须为 retain、adapt 或 recompose。")
    return requested


def art_direction(slide, raw, role, palette, treatment):
    """Compose around the actual lead, evidence or mechanism; keep all authored payloads."""
    content = []
    for obj in list(slide.shapes):
        if (obj.name in ("标题","来源","图注或结论","配图","可编辑数据图表")
                or obj.name.startswith("论点 ")):
            content.append(obj)
        else:
            # All non-content objects on this freshly generated donor are the old frame.
            slide.shapes._spTree.remove(obj._element)
    title = next(s for s in content if s.name=="标题")
    statements = [s for s in content if s.name.startswith("论点 ")]
    figure = next((s for s in content if s.has_chart or s.shape_type==MSO_SHAPE_TYPE.PICTURE),None)
    bottom = min([492]+[s.top.pt-12 for s in content if s.name in ("图注或结论","来源")])
    def panel(rect, fill, name):
        obj=shape(slide,RECT,rect,fill,name)
        slide.shapes._spTree.insert(2,obj._element)

    def rows(objects, rect, preferred):
        x,y,w,h=rect
        if objects:
            unit=h/len(objects)
            for i,obj in enumerate(objects):
                fit_textbox(obj,(x,y+i*unit,w,unit-3),preferred,False)

    if treatment == "adapt" or not figure and role != "process" and raw.get("layout") != "compare":
        if figure:
            fit_textbox(title,(50,28,858,90),39,True)
            panel((50,128,850,2),palette[2],"标题分隔线")
            if statements:
                fit_figure(figure,(49,155,530,bottom-155))
                rows(statements,(611,151,294,bottom-151),24)
            else:
                fit_figure(figure,(52,150,852,bottom-150))
        else:
            # The opening sentence and closing takeaway get a common, quiet reading axis.
            panel((54,53,78,5),palette[2],"题首标记")
            title_h=(bottom-83)*(.71 if len(statements)<=1 else .52)
            fit_textbox(title,(53,71,840,title_h),54,True)
            rows(statements,(56,81+title_h,826,bottom-81-title_h),28)
        return

    if figure or role=="process":
        boundary=439 if role=="process" else 324
        panel((boundary,40,2,bottom-65),palette[2],"图文分界")
        if role=="process":
            fit_textbox(title,(48,84,341,180),50,True)
        else:
            title_h=(bottom-82)*(.68 if len(statements)<=1 else .53)
            fit_textbox(title,(32,36,boundary-62,title_h),44,True)
            rows(statements,(34,title_h+49,boundary-67,bottom-title_h-56),23)
            fit_figure(figure,(boundary+18,37,960-boundary-42,bottom-52))
    elif statements:
        fit_textbox(title,(48,20,864,94),48,True)
        top=136
        cols=min(3,len(statements)) if len(statements)<=3 else 2
        count=math.ceil(len(statements)/cols)
        cell_w=(866-24*(cols-1))/cols
        cell_h=(bottom-top-15*(count-1))/count
        for i,obj in enumerate(statements):
            x=47+(i%cols)*(cell_w+24)
            y=top+(i//cols)*(cell_h+15)
            panel((x,y,cell_w,3),palette[2],"比较横线")
            fit_textbox(obj,(x,y+10,cell_w,cell_h-15),35,False)
    else:
        fit_textbox(title,(52,47,851,bottom-81),65,True)



def authored_visual(style, visual):
    palette = list(STYLES[style])
    if not isinstance(visual, dict):
        return palette, None, None
    def observed_color(field):
        value = visual.get(field)
        return value[1:].upper() if isinstance(value, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", value) else None
    def observed_font(value):
        return value if isinstance(value, str) and 0 < len(value) <= 96 and value.isprintable() else None
    background, accent = observed_color("background"), observed_color("accent")
    if visual.get("paletteBasis") == "thumbnails":
        # A photograph's median pixel is useful for browsing. It is not a brand fill.
        background = STYLES["科技" if visual.get("tone") == "dark" else "简约"][0]
    if background and visual.get("tone") in ("light", "dark"):
        palette[0] = background
        if contrast_ratio(palette[1], background) < 4.5:
            neutral = STYLES["科技" if visual["tone"] == "dark" else "简约"]
            for index in (1, 3, 4):
                palette[index] = neutral[index]
    if accent and contrast_ratio(accent, palette[0]) >= 2:
        palette[2] = accent
    fonts = visual.get("fonts") or []
    return palette, observed_font(visual.get("titleFont")), observed_font(fonts[0]) if isinstance(fonts, list) and fonts else None


def build(request, root):
    if not isinstance(request, dict):
        raise ValueError("请提交逐页制作方案。")
    count, slides = request.get("pageCount"), request.get("slides")
    if type(count) is not int or not 1 <= count <= 150 or not isinstance(slides, list) or not 1 <= len(slides) <= count:
        raise ValueError("目标页数应为 1–150，已提交的页数须为 1 至目标页数。")
    render_page=request.get("renderPage",len(slides))
    built=len(slides)
    legacy_base=request.get("legacyBase")
    offset=0
    if legacy_base is not None:
        prior=request.get("legacyBuilt")
        if (len(slides)!=1 or type(prior) is not int or not 1<=prior<=count
                or type(render_page) is not int or not 1<=render_page<=min(prior+1,count)):
            raise ValueError("旧稿页数、续作页码与当前请求不符。")
        if not isinstance(legacy_base,str) or not re.fullmatch(r"plans/[a-f0-9]{32}/presentation\.pptx",legacy_base):
            raise ValueError("请选择这份作品上次保存的成稿。")
        built=max(prior,render_page)
        offset=render_page-1
    if type(render_page) is not int or not 1<=render_page<=built:
        raise ValueError("预览页码应在当前已完成页数内。")
    style = request.get("style", "简约")
    style = ALIASES.get(style, style) if isinstance(style, str) else None
    if style not in STYLES:
        raise ValueError("请选择简约、科技、中国风、抽象或热梗风格。")
    level=request.get("creativity")
    if level not in (None,"grounded","balanced","bold"):
        raise ValueError("创作自由度须为稳妥、平衡或大胆。")
    motion_enabled,images_enabled=request.get("motionEnabled",True),request.get("imagesEnabled",True)
    if not isinstance(motion_enabled,bool) or not isinstance(images_enabled,bool):
        raise ValueError("动画与图片模块须使用开关值。")
    template_motion = request.get("templateMotion", "keep")
    if template_motion not in ("keep", "replace"):
        raise ValueError("请选择沿用模板原动效或按新方案制作。")
    template=requested_template(request,root)
    if request.get("motionSource") and (template is None or hashlib.sha256(template).hexdigest() != request["motionSource"]):
        raise ValueError("模板原稿已更新，请重新核对选中的放映片段。")
    visual=request.get("mainVisual") if template is None else None
    palette,title_family,body_family=authored_visual(style,visual)
    if template is not None and level in ("balanced","bold"):
        accent,_=template_style(template,include_image=False)
        palette[2]=accent or palette[2]
    specs = []
    treatments = []
    extras = []
    for n, raw in enumerate(slides, 1+offset):
        try:
            if not isinstance(raw, dict):
                raise ValueError("页面材料应为对象。")
            if not images_enabled and (raw.get("image") or raw.get("backgroundImage")):
                raise ValueError("配图模块已关闭，请先启用后再添加图片。")
            if request.get("chartsEnabled") is False and (raw.get("chart") or raw.get("structuredChart")):
                raise ValueError("图表模块已关闭，请先启用后再添加图表。")
            role=page_role(raw,n,count)
            treatment=treatment_for(raw,level,template)
            chosen_level={"retain":"grounded","adapt":"balanced","recompose":"bold"}[treatment]
            page=motion_defaults(raw,chosen_level,role,n==1,motion_enabled)
            treatments.append(treatment)
            if raw.get("structuredChart"):
                from harness_structured_chart import check_chart
                photo=raw.get("image")
                if raw.get("skillPage") or raw.get("chart") or raw.get("diagram") or photo and (not isinstance(photo,dict) or photo.get("role","figure")!="background"):
                    raise ValueError("结构图表与其他主视觉不能占据同一内容区。")
                if raw.get("composition","original")!="original" or len(input_lines(raw))>2:
                    raise ValueError("结构图表页的正文至多两句，请将详细解释放入备注。")
                check_chart(raw["structuredChart"])
            if raw.get("skillPage"):
                # This donor is replaced before preview. An editable skill page can have its
                # own text geometry, images, diagram or timeline beyond this layout's capacity.
                spec, background, animation, diagram = slide_spec(
                    {"title":"技能页面","notes":field(raw,"notes",24000)},root,n)
            else:
                spec, background, animation, diagram = slide_spec(page, root, n)
            if treatment=="adapt" and role=="argument" and "composition" not in raw:
                if "spread" in composition_options(spec) and page.get("layout")=="compare":
                    spec["composition"]="spread"
        except ValueError as exc:
            raise ValueError(f"第 {n} 页：{exc}") from exc
        specs.append(spec)
        extras.append((background, animation, diagram, role))
    charts = chart_color_history(resolve_child(root,legacy_base) if legacy_base else None) if any(s.get("chart") for s in slides) else None
    data = make_deck(specs, style, template_data=None if level=="grounded" else template, reuse_template_image=False,
                     palette_override=palette if visual else None, title_family=title_family, body_family=body_family,
                     chart_colors=charts)
    prs = Presentation(BytesIO(data))
    if len(prs.slides) != len(slides):
        raise ValueError("生成页数与提交的分页不符。")
    for slide, raw, (background, animation, diagram, role), treatment in zip(prs.slides,slides,extras,treatments):
        if (template is None or treatment!="retain") and raw.get("composition","original")=="original" and (treatment=="recompose" or role!="process"):
            art_direction(slide,raw,role,palette,"adapt" if treatment=="retain" else treatment)
        if raw.get("structuredChart") and (template is None or treatment=="recompose"):
            from harness_structured_chart import render,set_motion
            title=next(obj for obj in slide.shapes if obj.name=="标题")
            fit_textbox(title,(50,22,860,79),38,True)
            commentary=[obj for obj in slide.shapes if obj.name.startswith("论点 ")]
            bottom=min([505]+[s.top.pt-8 for s in slide.shapes if s.name in ("图注或结论","来源")])
            for ob in list(slide.shapes):
                if ob.name not in ("标题","图注或结论","来源") and not ob.name.startswith("论点 "):
                    slide.shapes._spTree.remove(ob._element)
            for i,obj in enumerate(commentary):
                fit_textbox(obj,(53,bottom-33*(len(commentary)-i),854,31),18,False)
            groups=render(slide,raw["structuredChart"],(52,117,856,bottom-126-33*len(commentary)),palette)
            set_motion(slide._element,groups,animation)
        if diagram:
            place_diagram(slide,diagram,style,animation,column=treatment=="recompose",palette=palette)
        if background:
            place_background(slide, background, style, prs.slide_width, prs.slide_height)
        if treatment!="retain":
            apply_readability(slide._element,palette)
        finish_motion(slide, animation)
    relative = f"plans/{uuid4().hex}"
    folder = resolve_child(root, relative)
    folder.mkdir(parents=True)
    deck, preview = folder / "presentation.pptx", folder / f"page-{render_page}.png"
    selections = []
    if template is not None and any(t!="recompose" for t in treatments):
        from harness_template_deck import assemble_native
        authored=BytesIO()
        prs.save(authored)
        native_slides = [
            {key: value for key, value in slide.items() if key not in ("transition", "animation")}
            if template_motion == "keep" and treatment != "recompose" else slide
            for slide, treatment in zip(slides, treatments)
        ]
        deck.write_bytes(assemble_native(template,authored.getvalue(),native_slides,page_count=count,
                                         motion_enabled=motion_enabled,images_enabled=images_enabled,palette=palette,
                                         require_chart_motion=bool(request.get("motionSource")) and request.get("chartsEnabled",True)
                                         and motion_enabled and template_motion=="keep",
                                         treatments=treatments,page_offset=offset,preserve_motion=template_motion=="keep",
                                         decisions=selections,prior_page=request.get("priorTemplatePage") if offset else None,
                                         prior_frames=request.get("priorFrames",[]),paired_position=request.get("pairedPosition")))
    else:
        prs.save(deck)
    if any(s.get("skillPage") for s in slides):
        from harness_skill_page import apply_skill_pages
        apply_skill_pages(deck,root,slides,request)
    if any(s.get("emoji") or s.get("meme") for s in slides):
        from harness_expression import place_memes
        place_memes(deck,slides,root)
    if legacy_base is not None:
        from harness_legacy_deck import install_page
        original=resolve_child(root,legacy_base)
        frame = selections[0]["page"] if selections and selections[0] else None
        context = None
        if motion_enabled and template_motion=="keep" and request.get("designVersion",0)>=4:
            context = dict(template=template,frame=frame,previous=request.get("priorTemplatePage"),
                           following=request.get("nextTemplatePage"),adjust_next=request.get("adjustNextMorph",False))
        deck.write_bytes(install_page(original.read_bytes(),deck.read_bytes(),render_page,prior,
                                      native=bool(frame),motion_context=context))
    elif request.get("canvasTemplate") or template is not None and not any(selections):
        from harness_canvas import fit_canvas
        from engine import Deck
        canvas = Deck(requested_template(request["canvasTemplate"],root) if request.get("canvasTemplate") else template)
        with canvas.zip:
            deck.write_bytes(fit_canvas(deck.read_bytes(),canvas,native=False))
    if legacy_base is not None or any(s.get("skillPage") or s.get("image") or s.get("meme") or s.get("backgroundImage") for s in slides):
        current = deck.read_bytes()
        clean = replace_restricted_photo(current)
        if clean is not current:
            deck.write_bytes(clean)
    renderer = PreviewSession()
    result = dict(deck=f"{relative}/{deck.name}", built=built, pageCount=count,
                  complete=built == count, engine=None, preview=None, previewPage=render_page)
    if selections:
        result["reference"] = selections[render_page-offset-1]
    try:
        try:
            engine = renderer.export(str(deck), "both", render_page, str(preview), {})
        finally:
            renderer.close()
        result.update(engine=engine, preview=f"{relative}/{preview.name}")
    except Exception:
        result["previewError"] = "当前无法调用 PowerPoint 或 WPS 渲染静态预览。已生成可编辑的 PPTX，可下载查看。"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = sys.stdin.buffer.read(8 * 1024 * 1024 + 1)
        if len(payload) > 8 * 1024 * 1024:
            raise ValueError("逐页指令超过 8 MiB。")
        result = build(json.loads(payload.decode("utf-8-sig")), args.workdir.resolve(strict=True))
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    except Exception:
        print(json.dumps({"ok": False, "error": "制作或原生预览失败，请检查本机的图片和 PowerPoint/WPS 环境。"}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

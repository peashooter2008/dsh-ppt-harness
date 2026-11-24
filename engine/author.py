"""Compose editable presentations from a supplied outline using python-pptx."""

import base64
import colorsys
import io
import math
import re
import unicodedata
from collections import Counter

from PIL import Image, ImageOps
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn
from pptx.util import Pt

from engine import NS, Deck, add_transition, make_timing, set_background, shape_list, theme_for, transition_spec
from slidecontrast import apply_readability, series_colors


STYLES = {
    "简约": ("F7F6F2","1B2429","086957","CCE2D8","51615E"),
    "科技": ("112032","EDF6F8","59E0BF","1E3A50","A1BAC3"),
    "中国风": ("F3EBDD","282621","96392F","D7C4A5","5D564E"),
    "抽象": ("F4E9E2","2B2633","98426D","CDA4CB","625362"),
    "热梗": ("FFF1C9","27263E","5751A4","E9A982","514459"),
}
ALIASES = {"卡通":"热梗","热梗/卡通":"热梗","科技风":"科技","极简":"简约","抽象风":"抽象",
           "minimal":"简约","tech":"科技","chinese":"中国风","abstract":"抽象","cartoon":"热梗","meme":"热梗"}


def color(value):
    return RGBColor.from_string(value.lstrip("#"))


def length(value):
    return sum(1 if unicodedata.east_asian_width(c) in "FW" else .54 for c in value)


def shape(slide, kind, rect, fill, name, line=None):
    s = slide.shapes.add_shape(kind,*[Pt(v) for v in rect])
    s.name = name
    s.fill.solid()
    s.fill.fore_color.rgb = color(fill)
    if line:
        s.line.color.rgb = color(line)
        s.line.width = Pt(1.5)
    else:
        s.line.fill.background()
    return s


RECT, OVAL, ROUND = MSO_SHAPE.RECTANGLE, MSO_SHAPE.OVAL, MSO_SHAPE.ROUNDED_RECTANGLE


def text(slide, content, rect, font_size, fill, *, name, bold=False, family="Microsoft YaHei", align=None, prefer_single_line=True, soft_wrap=False):
    x,y,w,h=rect
    s=slide.shapes.add_textbox(Pt(x),Pt(y),Pt(w),Pt(h))
    s.name=name
    tf=s.text_frame
    tf.clear()
    tf.word_wrap=True
    tf.auto_size=MSO_AUTO_SIZE.NONE
    tf.margin_left=tf.margin_top=tf.margin_right=tf.margin_bottom=Pt(0)
    tf.vertical_anchor=MSO_ANCHOR.MIDDLE
    lines=content.splitlines() or [""]
    size=font_size
    while size>11 and sum(max(1,math.ceil(length(l)*size/max(1,w*.91))) for l in lines)*size*1.23>h:
        size-=1
    if prefer_single_line and len(lines)==1 and length(lines[0])*size<=w*1.23:
        size=min(size,max(11,int(.92*w/max(1,length(lines[0])))))
    for i,line in enumerate(lines):
        if i and soft_wrap:
            p.add_line_break()
        else:
            p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        if align is not None:
            p.alignment=align
        p.space_before=p.space_after=Pt(0)
        p.line_spacing=1.05
        run=p.add_run()
        run.text=line
        run.font.name=family
        run.font.size=Pt(size)
        run.font.bold=bold
        run.font.color.rgb=color(fill)
        rpr=run._r.get_or_add_rPr()
        rpr.set("lang","zh-CN" if any("\u3400"<=c<="\u9fff" for c in line) else "en-US")
        ea=OxmlElement("a:ea")
        ea.set("typeface",family)
        rpr.append(ea)
    return s


def image_bytes(raw):
    if not raw or len(raw)>18*1024*1024:
        raise ValueError("配图为空或超过 18 MiB。")
    with Image.open(io.BytesIO(raw),formats=["JPEG","PNG","WEBP","GIF","BMP","TIFF"]) as im:
        if im.width*im.height>35_000_000:
            raise ValueError("配图超过 3500 万像素。")
        width,height=im.size
        if im.format in ("PNG","JPEG") and im.getexif().get(274,1)==1:
            with Image.open(io.BytesIO(raw)) as verify_image:
                verify_image.verify()
            return raw,width,height
        im=ImageOps.exif_transpose(im)
        out=io.BytesIO()
        im.convert("RGBA").save(out,"PNG")
        return out.getvalue(),im.width,im.height


def template_style(data, include_image=True):
    if data is None:
        return None,None
    deck=Deck(data)
    with deck.zip:
        palette=Counter()
        candidates=[]
        for part in list(deck.slides)[:4]:
            root=deck.tree(part)
            rels=deck.rels(part)
            for _,_,s,_ in shape_list(root):
                fill=s.find("p:spPr/a:solidFill/a:srgbClr",NS)
                if fill is not None:
                    val=fill.get("val","").upper()
                    if re.fullmatch("[0-9A-F]{6}",val):
                        rgb=[int(val[i:i+2],16)/255 for i in (0,2,4)]
                        _,l,sat=colorsys.rgb_to_hls(*rgb)
                        if .18<l<.84 and sat>.28:
                            palette[val]+=1
                if not include_image:
                    continue
                blip=s.find("p:blipFill/a:blip",NS)
                ext=s.find("p:spPr/a:xfrm/a:ext",NS)
                if blip is None or ext is None:
                    continue
                rid=blip.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                target=rels.get(rid)
                if not target or target[0]!="image" or target[1] not in deck.names:
                    continue
                area=int(ext.get("cx",0))*int(ext.get("cy",0))/(deck.w*deck.h)
                # Exclude likely full-slide screenshots and very small brand marks.
                if .045<=area<=.78 and deck.zip.getinfo(target[1]).file_size<=12*1024*1024:
                    candidates.append((area,target[1]))
        layout=deck.related(next(iter(deck.slides)),"slideLayout")
        master=deck.related(layout,"slideMaster") if layout else ""
        accent=palette.most_common(1)[0][0] if palette else theme_for(deck,master).get("accent1")
        for _,part in sorted(set(candidates),reverse=True):
            try:
                return accent,image_bytes(deck.zip.read(part))
            except (OSError,ValueError,Image.DecompressionBombError):
                continue
        return accent,None


def input_lines(item):
    value=item.get("body","")
    if isinstance(value,str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value,list) and all(isinstance(v,str) for v in value):
        return [line.strip() for v in value for line in v.splitlines() if line.strip()]
    raise ValueError("body 应为文字或文字数组。")


def chunks(lines, *, numbered=False):
    """Partition long copy into continuation slides without dropping content."""
    pages,current=[],[]
    cost=0
    for number,line in enumerate(lines,1):
        segments=[]
        start=0
        while start<len(line):
            end=start
            weight=0
            while end<len(line) and weight<124:
                weight+=length(line[end])
                end+=1
            if end<len(line):
                br=max((line.rfind(ch,start+int((end-start)*.45),end) for ch in "，。；！？,;.!? "),default=-1)
                if br>=start:
                    end=br+1
            segments.append(line[start:end])
            start=end
        for segment in segments:
            n=length(segment)
            if current and (len(current)>=4 or n+cost>195):
                pages.append(current)
                current,cost=[],0
            current.append((number,segment) if numbered else segment)
            cost+=n
    return pages+[current] if current or not pages else pages


def visual_step(visual,lines):
    """One-based body line linked to an illustration, or zero for visible on entry."""
    if not isinstance(visual,dict):
        return 0
    if "revealWithBody" in visual:
        step=visual["revealWithBody"]
        if type(step) is not int or not 0<=step<=len(lines):
            raise ValueError("visual.revealWithBody 应为 0 或本页实际正文条目的序号，从 1 开始。")
        return step
    if visual.get("type") in {"bar","column","line","pie"}:
        for i,line in enumerate(lines,1):
            if re.search(r"看柱|根柱|张柱|柱形|柱状|条形图|折线|饼图|看图|读图|图表|图中|\b(chart|bars?|graph)\b",line,re.I):
                return i
    return 0


def footer_layout(caption,source):
    # Reserve space above the footer before drawing body and chart. Full references live in notes.
    def rows(value,capacity):
        return sum(max(1,math.ceil(length(line)/capacity)) for line in value.splitlines()) if value else 0
    caption_rows=rows(caption,48)
    if caption_rows>6:
        raise ValueError("图注过长，会盖住正文。请保留图中结论，把详细解释放在演讲备注 notes。")
    if rows(source,60)>2:
        prefix=""
        for char in source.replace("\n"," "):
            if length(prefix)+length(char)>97:
                break
            prefix+=char
        source=prefix.rstrip()+"…（完整出处见本页备注）"
    sh=rows(source,60)*17+4 if source else 0
    sy=532-sh
    ch=caption_rows*21+6 if caption else 0
    cy=min(505,sy-6 if source else 525)-ch
    return (cy,ch),(sy,sh),source


def parse_visual(visual):
    if visual is None or visual=="":
        return None
    if isinstance(visual,str):
        if not visual.startswith("data:image/"):
            return {"type":"brief","description":visual}
        visual={"type":"image","data":visual}
    if not isinstance(visual,dict):
        raise ValueError("visual 应为配图、原生图表或视觉说明。")
    typ=visual.get("type","image")
    if typ=="image":
        url=visual.get("data",visual.get("src",""))
        if not isinstance(url,str) or len(url)>24*1024*1024:
            raise ValueError("配图超出大小限制。")
        head,sep,payload=url.partition(",")
        if not sep or not re.fullmatch(r"data:image/(?:jpeg|jpg|png|webp|gif);base64",head):
            raise ValueError("配图需使用本地 PNG、JPEG、GIF 或 WebP 数据。")
        return {"type":"image","image":image_bytes(base64.b64decode(payload,validate=True)),"alt":str(visual.get("alt",""))}
    charts={"bar":XL_CHART_TYPE.BAR_CLUSTERED,"column":XL_CHART_TYPE.COLUMN_CLUSTERED,
            "line":XL_CHART_TYPE.LINE_MARKERS,"pie":XL_CHART_TYPE.PIE}
    if typ not in charts:
        raise ValueError("图表支持 bar、column、line、pie。")
    cats=visual.get("categories")
    series=visual.get("series") or [{"name":visual.get("title","数据"),"values":visual.get("values")}]
    if not isinstance(cats,list) or not 1<=len(cats)<=40 or not isinstance(series,list) or not 1<=len(series)<=8:
        raise ValueError("原生图表需要 1–40 项分类和 1–8 个数据系列。")
    if typ=="pie" and len(series)!=1:
        raise ValueError("饼图需要一个数据系列。")
    for s in series:
        if not isinstance(s,dict) or not isinstance(s.get("values"),list) or len(s["values"])!=len(cats) or any(
                type(v) not in (int,float) or not math.isfinite(v) for v in s["values"]):
            raise ValueError("图表数据应为与分类等长的有限数值。")
    if typ=="pie" and (min(series[0]["values"])<0 or max(series[0]["values"])==0):
        raise ValueError("饼图需要非负数据且合计大于零。可用横条图比较负值，或用文字说明全为零。")
    return {"type":"chart","chart":charts[typ],"categories":[str(c) for c in cats],"series":series,
            "unit":str(visual.get("unit","")),"title":str(visual.get("title",""))}


def place_visual(slide, visual, rect, palette, chart_colors=None):
    x,y,w,h=rect
    if visual["type"]=="image":
        raw,iw,ih=visual["image"]
        scale=min(w/iw,h/ih)
        pw,ph=iw*scale,ih*scale
        pic=slide.shapes.add_picture(io.BytesIO(raw),Pt(x+(w-pw)/2),Pt(y+(h-ph)/2),Pt(pw),Pt(ph))
        pic.name="配图"
        pic._element.nvPicPr.cNvPr.set("descr",visual.get("alt",""))
        return pic
    data=CategoryChartData()
    data.categories=visual["categories"]
    for s in visual["series"]:
        data.add_series(str(s.get("name","数据")),s["values"])
    graphic=slide.shapes.add_chart(visual["chart"],Pt(x),Pt(y),Pt(w),Pt(h),data)
    graphic.name="可编辑数据图表"
    chart=graphic.chart
    chart.chart_style=10
    chart.font.color.rgb=color("33383D")
    area=chart._chartSpace.find(qn("c:spPr"))
    if area is None:
        area=OxmlElement("c:spPr")
        chart._chartSpace.find(qn("c:chart")).addnext(area)
    fill=OxmlElement("a:solidFill")
    white=OxmlElement("a:srgbClr")
    white.set("val","FFFFFF")
    fill.append(white)
    area.append(fill)
    chart.has_legend=len(visual["series"])>1 or visual["chart"]==XL_CHART_TYPE.PIE
    colors=series_colors(palette[2])
    if chart_colors is not None:
        from harness_chart_colors import consistent_marks
        if visual["chart"]==XL_CHART_TYPE.PIE:
            colors=consistent_marks(visual["categories"],chart_colors["categories"],colors)
        else:
            colors=consistent_marks([s.get("name","数据") for s in visual["series"]],chart_colors["series"],colors)
    markers=(XL_MARKER_STYLE.CIRCLE,XL_MARKER_STYLE.SQUARE,XL_MARKER_STYLE.TRIANGLE,XL_MARKER_STYLE.DIAMOND,
             XL_MARKER_STYLE.PLUS,XL_MARKER_STYLE.X,XL_MARKER_STYLE.STAR,XL_MARKER_STYLE.DASH)
    for i,series in enumerate(chart.series):
        if visual["chart"]==XL_CHART_TYPE.LINE_MARKERS:
            series.format.line.color.rgb=color(colors[i])
            series.format.line.width=Pt(2.5)
            series.marker.style=markers[i]
            series.marker.size=7
            series.marker.format.fill.solid()
            series.marker.format.fill.fore_color.rgb=color(colors[i])
            series.marker.format.line.color.rgb=color(colors[i])
        elif visual["chart"]!=XL_CHART_TYPE.PIE:
            series.format.fill.solid()
            series.format.fill.fore_color.rgb=color(colors[i])
        else:
            for j,point in enumerate(series.points):
                point.format.fill.solid()
                point.format.fill.fore_color.rgb=color(colors[j%len(colors)])
    if visual["chart"]!=XL_CHART_TYPE.PIE:
        if visual["chart"]==XL_CHART_TYPE.BAR_CLUSTERED:
            chart.category_axis.reverse_order=True
            # Keep bars anchored at zero and place the numeric axis below the last category.
            chart.value_axis._element.find(qn("c:crosses")).set("val","max")
        for axis in (chart.value_axis,chart.category_axis):
            axis.tick_labels.font.size=Pt(12)
            axis.tick_labels.font.color.rgb=color("33383D")
        chart.value_axis.has_major_gridlines=True
        chart.value_axis.major_gridlines.format.line.color.rgb=color("D5D9DA")
        chart.value_axis.major_gridlines.format.line.width=Pt(.65)
    if chart.has_legend:
        chart.legend.position=XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout=False
        chart.legend.font.size=Pt(12)
        chart.legend.font.color.rgb=color("33383D")
    chart.has_title=bool(visual["title"] or visual["unit"])
    if chart.has_title:
        chart.chart_title.text_frame.text=(visual["title"]+"（"+visual["unit"]+"）" if visual["title"] and visual["unit"]
                                          else visual["title"] or "单位："+visual["unit"])
        chart.chart_title.text_frame.paragraphs[0].runs[0].font.size=Pt(16)
        chart.chart_title.text_frame.paragraphs[0].runs[0].font.color.rgb=color("33383D")
    graphic._element.nvGraphicFramePr.cNvPr.set("descr","；".join(
        str(s.get("name","数据"))+"："+ "、".join(f"{k} {v}{visual['unit']}" for k,v in zip(visual["categories"],s["values"]))
        for s in visual["series"]))
    return graphic


def frame(slide, style, colors, variant, n):
    bg,ink,accent,soft,muted=colors
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb=color(bg)
    if style=="中国风":
        shape(slide,RECT,(28,24,2,492),accent,"题签边线")
        shape(slide,RECT,(35,24,1,492),soft,"题签边线")
        shape(slide,OVAL,(870,15,44,44),soft,"圆形纹样")
        return (57,53,257,367),(327,65,576,399)
    if style=="科技":
        for i in range(5):
            shape(slide,RECT,(788+i*28,21,1,71),soft,"背景网格")
        for i in range(3):
            shape(slide,RECT,(770,27+i*25,162,1),soft,"背景网格")
        shape(slide,RECT,(43,44,4,70),accent,"标题标记")
        return (60,39,710,85),(59,150,842,301)
    if style=="抽象":
        side=(n+variant)%2
        edge=24 if side else 828
        shape(slide,OVAL,(edge,28,104,104),soft,"圆形色块")
        shape(slide,MSO_SHAPE.RIGHT_TRIANGLE,(edge+14,84,86,82),accent,"三角色块")
        return ((164 if side else 54),45,679,104),(53,186,850,272)
    if style=="热梗":
        shape(slide,ROUND,(47,32,864,108),ink,"标题框描边")
        shape(slide,ROUND,(41,26,864,108),soft,"标题底色",ink)
        return (66,39,812,77),(62,169,837,287)
    shape(slide,RECT,(52,135,854,1.5),accent,"版心线")
    return (52,36,852,91),(53,165,850,293)


def body_boxes(slide, lines, rect, style, colors, mode, layout=None, family=None):
    x,y,w,h=rect
    bg,ink,accent,soft,muted=colors
    if not lines:
        return []
    cues=[]
    columns=len(lines) if len(lines) in (2,3) else 2 if layout=="compare" and len(lines)==4 else 1
    two_up=(columns>1 and (w>660 or layout=="compare" and columns==2 and w>=510)
            and (layout=="compare" or layout is None and mode%3==1) and all(length(l)<56 for l in lines))
    for i,line in enumerate(lines):
        if two_up:
            cw=(w-22*(columns-1))/columns
            rows=math.ceil(len(lines)/columns)
            bh=(h-22-10*(rows-1))/rows
            bx,by,bw=x+(i%columns)*(cw+22),y+11+(i//columns)*(bh+10),cw
        else:
            rowh=(h-8*(len(lines)-1))/len(lines)
            bx,by,bw,bh=x,y+i*(rowh+8),w,rowh
        if style=="科技":
            shape(slide,RECT,(bx,by+bh*.15,3,bh*.7),accent,"信号刻度")
            bx+=18
            bw-=18
        elif style=="热梗":
            shape(slide,ROUND,(bx,by,bw,bh),("FFFBED" if i%2==0 else "F5EEE1"),"对话气泡",ink)
            bx+=16
            bw-=32
        elif two_up:
            shape(slide,RECT,(bx,by,bw,2),accent,"并列分界")
        elif style=="中国风" and len(lines)>1:
            shape(slide,OVAL,(bx,by+bh*.48,5,5),accent,"段落标记")
            bx+=14
            bw-=14
        size=32 if len(lines)==1 else 23 if len(lines)==2 else 20
        obj=text(slide,line,(bx,by,bw,bh),size,ink,name=f"论点 {i+1}",family=family or ("SimSun" if style=="中国风" else "Microsoft YaHei"),prefer_single_line=False)
        cues.append(str(obj.shape_id))
    return cues


def reveal_spec(value):
    if value not in ("none","appear","fade"):
        raise ValueError("页内正文揭示 reveal 可选 none、appear 或 fade。")
    return value


def composition_options(page):
    """Choices that fit on one physical slide without rewriting the material."""
    if page.get("scene") is not None:
        return ["original"]
    from reference_layout import can_use_cogito

    options = ["original"]
    statements = input_lines(page)
    visual = page.get("visual")
    chart = isinstance(visual, dict) and visual.get("type") in ("bar", "column", "pie", "line")
    short_page = (
        2 <= len(statements) <= 4
        and max(map(length, statements)) <= 68
        and sum(map(length, statements)) <= 168
        and length(str(page.get("title", ""))) <= 68
        and length(str(page.get("caption") or "")) <= 90
        and str(page.get("caption") or "").count("\n") <= 1
    )
    if short_page:
        # A wide, shallow chart leaves room for a row of short observations only.
        if not chart or (len(visual.get("categories", [])) <= 6 and len(visual.get("series") or []) <= 3):
            options.append("spread")
        if page.get("reveal") != "none":
            options.append("unfold")
    if can_use_cogito(page):
        options.append("cogito")
    return options


def clause_break(line, box, size):
    """Prefer a clause boundary when a short Chinese sentence needs two display lines."""
    width, height = box[2:]
    if length(line) * size <= .91 * width:
        return line, size
    splits = [(line[:m.end()], line[m.end():]) for m in re.finditer("[，；：]", line)]
    candidates = [(a, b) for a, b in splits if min(length(a), length(b)) >= 3]
    if not candidates:
        return line, size
    a, b = min(candidates, key=lambda pair: abs(length(pair[0]) - length(pair[1])))
    fitted = min(size, int(.91 * width / max(length(a), length(b))))
    if fitted < max(18, .79 * size) or height < fitted * 2.55:
        return line, size
    return a + "\n" + b, fitted


def composed_body(slide, composition, lines, rect, has_visual, palette, family):
    """Place the same original statements on shared axes or in a guided reading order."""
    x, y, w, h = rect
    ink, accent = palette[1:3]
    slots = []
    figure = rect
    if composition == "spread":
        if has_visual:
            figure_height = h * .61
            figure = (x + w * .065, y, w * .87, figure_height)
            y += figure_height + 12
            h -= figure_height + 12
        columns = 2 if len(lines) == 4 and not has_visual else len(lines)
        rows = math.ceil(len(lines) / columns)
        gutter = 26
        lane_width = (w - gutter * (columns - 1)) / columns
        row_height = (h - 12 * (rows - 1)) / rows
        inset = 3 if has_visual or rows > 1 else h * .20
        for column in range(1, columns):
            boundary = x + column * (lane_width + gutter) - gutter / 2
            shape(slide, RECT, (boundary, y + inset, 1, h - 2 * inset), palette[4], "对读分界")
        if rows > 1:
            shape(slide, RECT, (x, y + row_height + 6, w, 1), palette[4], "对读分界")
        for i in range(len(lines)):
            left = x + (i % columns) * (lane_width + gutter)
            top = y + (i // columns) * (row_height + 12)
            size = 26 if has_visual else 34 if columns == 2 else 28
            slots.append(((left, top, lane_width, row_height), size, False))
    else:
        if has_visual:
            text_width = w * .39
            figure = (x + text_width + 28, y, w - text_width - 28, h)
            lead_height = h * .40
            slots.append(((x, y, text_width, lead_height), 32, True))
            shape(slide, RECT, (x, y + lead_height + 4, text_width, 2), accent, "阅读分界")
            rx, ry, rw, rh = x, y + lead_height + 16, text_width, h - lead_height - 16
        else:
            lead_width = w * .43
            slots.append(((x, y, lead_width, h), 43, True))
            shape(slide, RECT, (x + lead_width + 17, y, 2, h), accent, "阅读分界")
            rx, ry, rw, rh = x + lead_width + 45, y, w - lead_width - 45, h
        count = len(lines) - 1
        line_height = (rh - 8 * (count - 1)) / count
        for i in range(count):
            slots.append(((rx, ry + i * (line_height + 8), rw, line_height), 28, False))
    displays = [clause_break(line, box, size) for line, (box, size, _) in zip(lines, slots)]
    shared_size = min(size for _, size in displays) if composition == "spread" else None
    ids = []
    for i, ((line, size), (box, _, bold)) in enumerate(zip(displays, slots), 1):
        obj = text(slide, line, box, shared_size or size, ink, name=f"论点 {i}", bold=bold,
                   family=family, prefer_single_line=bold, soft_wrap=True)
        ids.append(str(obj.shape_id))
    return figure, ids


def physical_count(page):
    return 1 if page.get("scene") is not None else len(chunks(input_lines(page)))


def make_deck(slides, style="简约", variant=0, template_data=None, reuse_template_image=True, motion_mode="standard",
              *, palette_override=None, title_family=None, body_family=None, chart_colors=None):
    """Return an editable PPTX. Text, chart data, source and notes come from the caller."""
    if isinstance(slides,dict):
        slides=slides.get("slides")
    if not isinstance(slides,list) or not 1<=len(slides)<=150:
        raise ValueError("请提供 1–150 页大纲。")
    if motion_mode not in ("standard","enhanced"):
        raise ValueError("动效输出可选 standard、enhanced。")
    style=ALIASES.get(style,style)
    if style not in STYLES or type(variant) is not int:
        raise ValueError("请选择简约、科技、中国风、抽象或热梗风格，并提供整数变体。")
    palette=list(palette_override or STYLES[style])
    imported,sample=template_style(template_data,include_image=reuse_template_image)
    if imported:
        palette[2]=imported
    prs=Presentation()
    prs.slide_width,prs.slide_height=Pt(960),Pt(540)
    for page,item in enumerate(slides):
        if not isinstance(item,dict) or not isinstance(item.get("title"),str) or not item["title"].strip():
            raise ValueError(f"第 {page+1} 页缺少标题。")
        title=item["title"].strip()
        if len(title)>180 or sum(map(len,input_lines(item)))>32767:
            raise ValueError("标题最多 180 字符，每个大纲项正文最多 32767 字符。")
        composition = item.get("composition", "original")
        if composition != "original" and composition not in composition_options(item):
            raise ValueError(f"第 {page+1} 页的内容不适合所选讲法，请选择本页可用的排版。")
        if item.get("scene") is not None:
            from native_scene import add_scene
            if len(prs.slides)>=200:
                raise ValueError("内容分页后超过 200 页。")
            add_scene(prs,item,motion_mode)
            continue
        if composition == "cogito":
            from reference_layout import add_cogito
            if len(prs.slides) >= 200:
                raise ValueError("内容分页后超过 200 页。")
            add_cogito(prs, item)
            continue
        visual=parse_visual(item.get("visual"))
        source=str(item.get("source") or "")
        caption=str(item.get("caption") or "")
        notes=str(item.get("notes") or "")
        entry=transition_spec(item["transition"]) if "transition" in item else None
        reveal=reveal_spec(item["reveal"]) if "reveal" in item else None
        original_lines=input_lines(item)
        linked_line=visual_step(item.get("visual"),original_lines)
        story=chunks(original_lines,numbered=True)
        visual_page=next((k for k,group in enumerate(story) if any(number==linked_line for number,_ in group)),0)
        (cy,ch),(sy,sh),visible_source=footer_layout(caption,source)
        for j,group in enumerate(story):
            lines=[line for _,line in group]
            show_caption=bool(caption and (not visual or visual["type"]=="brief" or j==visual_page))
            if len(prs.slides)>=200:
                raise ValueError("内容分页后超过 200 页。")
            n=len(prs.slides)
            slide=prs.slides.add_slide(prs.slide_layouts[6])
            if composition == "original":
                title_rect,body_rect=frame(slide,style,palette,variant,n)
            else:
                slide.background.fill.solid()
                slide.background.fill.fore_color.rgb = color(palette[0])
                title_rect, body_rect = (55, 29, 850, 81), (55, 142, 850, 335)
                shape(slide, RECT, (55, 119, 850 if composition == "spread" else 64, 3),
                      palette[2], "标题分界")
            if "background" in item:
                set_background(slide._element,item["background"])
            style_font="SimSun" if style=="中国风" else "Microsoft YaHei"
            text(slide,title,title_rect,42 if n==0 else 34,palette[1],name="标题",bold=True,family=title_family or style_font)
            active=visual if j==visual_page and visual and visual["type"]!="brief" else None
            if active is None and not visual and sample and j==0 and (page==0 or page==len(slides)-1):
                active={"type":"image","image":sample,"alt":"所选模板的原图"}
            x,y,w,h=body_rect
            if show_caption or source:
                h=min(h,(cy if show_caption else sy)-y-12)
            body_rect=x,y,w,h
            layout=item.get("layout")
            if composition != "original":
                fig, cues = composed_body(slide, composition, lines, body_rect, bool(active), palette, body_family or style_font)
            elif active and lines:
                left_visual=layout=="focus" if layout in ("focus","compare") else (variant+n)%2==1
                gap=26
                vw=w*.49
                if layout=="focus" and w>=740 and all(length(line)<=60 for line in lines):
                    vw=w*.58
                tw=w-vw-gap
                fig=(x if left_visual else x+tw+gap,y,vw,h)
                txt=(x+vw+gap if left_visual else x,y,tw,h)
            else:
                fig=txt=body_rect
            if composition == "original":
                cues=body_boxes(slide,lines,txt,style,palette,variant+n,layout,body_family)
            steps=[[sid] for sid in cues]
            show_with=next((k for k,(number,_) in enumerate(group) if number==linked_line),None) if active else None
            if active:
                graphic=place_visual(slide,active,fig,palette,chart_colors)
                if show_with is not None:
                    steps[show_with].append(str(graphic.shape_id))
            if show_caption:
                note=text(slide,caption,(58,cy,845,ch),15,palette[4],name="图注或结论",family=body_family or "Microsoft YaHei")
                if show_with is not None:
                    steps[show_with].append(str(note.shape_id))
                elif composition == "unfold":
                    steps[-1].append(str(note.shape_id))
            if source:
                text(slide,visible_source,(58,sy,845,sh),12,palette[4],name="来源",family=body_family or "Microsoft YaHei")
            apply_readability(slide._element,palette)
            # A continuation does not repeat the special transition into its opening page.
            transition=entry if j==0 and entry is not None else {"type":"fade","durationMs":550} if n else {"type":"none"}
            add_transition(slide._element,transition)
            animated=steps if reveal!="none" and (reveal is not None or show_with is not None or len(steps)>1) else []
            if composition == "unfold":
                animated = steps[1:]
            elif composition == "spread" and reveal is None and show_with is None:
                animated = []
            if animated:
                all_ids=[sid for step in animated for sid in step]
                together={sid for step in animated for sid in step[1:]}
                slide._element.append(make_timing(all_ids,reveal or "fade",together))
            names={str(x.shape_id):x.name for x in slide.shapes}
            instructions="逐次点击呈现："+" → ".join(" + ".join(names[sid] for sid in step) for step in animated) if animated else "整页静态展示，可直接讲述。"
            entry_label={"none":"直接切换","fade":"淡化","push":"推移","wipe":"擦除"}[transition["type"]]
            handoff=f"本页入场：{entry_label}"+(f"，{transition['durationMs']/1000:g} 秒" if transition["type"]!="none" else "")+"。由讲者翻页。"
            details=[s for s in (notes, "来源："+source if source else None,
                                  "图注："+caption if caption else None, handoff, "节奏："+instructions,
                                  "视觉意图："+visual["description"] if visual and visual["type"]=="brief" else None) if s]
            slide.notes_slide.notes_text_frame.text="\n".join(details)
    output=io.BytesIO()
    prs.save(output)
    return output.getvalue()

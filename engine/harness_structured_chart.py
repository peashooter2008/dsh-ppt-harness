"""Native structured charts. Layout calculations adapted from dsh-ppt (MIT).

Copyright (c) 2026 stardustlc. License: Harness插件/licenses/dsh-ppt-MIT.txt.
Upstream ccfa096, skills/dsh-ppt/scripts/deck-diagrams.mjs:
parseHarveyValue / renderHarveyMatrixPptx and architecture / org tree placement.
"""
from copy import deepcopy
from math import ceil

from pptx import Presentation
from pptx.enum.shapes import MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Pt

from author import RECT, color, length, shape
from engine import NS, local, make_timing, shape_list, text_in, picture_blip
from slidecontrast import contrast_ratio


def values(items, name, low, high):
    if not isinstance(items,list) or not low<=len(items)<=high:
        raise ValueError(f"{name}须包含 {low}–{high} 项。")
    return items


def label(value, name, limit):
    if not isinstance(value,str) or not value.strip() or not value.isprintable() or length(value)>limit:
        raise ValueError(f"{name}须为有内容的一行，最多约 {limit} 个汉字。")
    return value.strip()


def check_chart(spec):
    if not isinstance(spec,dict):
        raise ValueError("结构图表须为对象。")
    kind=spec.get("type")
    if kind=="harvey":
        columns=values(spec.get("columns"),"矩阵列标题",2,5)
        for col in columns:
            label(col,"列标题",16)
        for row in values(spec.get("rows"),"比较维度",2,7):
            for val in values(row,"每行单元格",len(columns),len(columns)):
                label(val,"单元格",24)
    elif kind in ("org","architecture"):
        if kind=="org":
            label(spec.get("root"),"上级部门",26)
        for node in values(spec.get("items"),"部门或架构层",2,5):
            if not isinstance(node,dict):
                raise ValueError("每项须给出标题。")
            label(node.get("title"),"标题",20)
            for val in values(node.get("details",[]),"说明",0,3):
                label(val,"说明",24)
    else:
        raise ValueError("结构图表应当选择 org、architecture 或 harvey。")


def blend(a,b,t):
    return "".join(f"{round(int(a[i:i+2],16)*(1-t)+int(b[i:i+2],16)*t):02X}" for i in (0,2,4))


def ink(bg,preferred):
    return preferred if contrast_ratio(bg,preferred)>=4.5 else max(("151B20","FFFFFF"),key=lambda col:contrast_ratio(bg,col))


def paragraph(p, value, size, fg, bold, align):
    p.alignment=align
    p.space_after=p.space_before=Pt(0)
    p.line_spacing=1.02
    r=p.add_run()
    r.text=value
    r.font.name="Microsoft YaHei"
    r.font.bold=bold
    r.font.size=Pt(size)
    r.font.color.rgb=color(fg)
    ea=OxmlElement("a:ea");ea.set("typeface","Microsoft YaHei");r._r.get_or_add_rPr().append(ea)


def cell_text(frame, lines, box, head_size, fg, *, center=False, bold=True):
    w,h=box
    frame.clear()
    frame.vertical_anchor=MSO_ANCHOR.MIDDLE
    frame.word_wrap=True
    frame.margin_top=frame.margin_bottom=Pt(2)
    frame.margin_left=frame.margin_right=Pt(min(10,w*.055))
    point=head_size
    normal_text=[str(line).strip() for line in lines]
    while point>9:
        demand=sum(max(1,ceil(length(v)*(point if i==0 else point*.75)/max(1,w-22)))*(point if i==0 else point*.75)*1.22 for i,v in enumerate(normal_text))
        if demand<h-3:
            break
        point-=1
    for i,line in enumerate(normal_text):
        para=frame.paragraphs[0] if i==0 else frame.add_paragraph()
        paragraph(para,line,point if i==0 else max(9,point*.75),fg,bold and i==0,
                  PP_ALIGN.CENTER if center else PP_ALIGN.LEFT)


def card(slide, box, words, fill, fg, name, size, *, center=False, outline=None):
    ob=shape(slide,RECT,box,fill,"结构图 "+name,outline)
    cell_text(ob.text_frame,words,box[2:],size,ink(fill,fg),center=center)
    return ob


def line(slide, x1,y1,x2,y2,stroke):
    ob=slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,*map(Pt,(x1,y1,x2,y2)))
    ob.name="结构图 层级连接"
    ob.line.color.rgb=color(stroke)
    ob.line.width=Pt(1.35)
    return ob


# Convert dsh-ppt's chart cells to readable, editable native table contents.
def harvey_text(value):
    lookup={
        "full":("●","100%"),"100%":("●","100%"),"●":("●","100%"),
        "75%":("◕","75%"),"◕":("◕","75%"),"half":("◑","50%"),"50%":("◑","50%"),"◑":("◑","50%"),
        "25%":("◔","25%"),"◔":("◔","25%"),"none":("○","0%"),"0%":("○","0%"),"○":("○","0%"),
        "yes":("✓",""),"✓":("✓",""),"no":("✗",""),"✗":("✗",""),
    }
    pair=lookup.get(value.lower())
    return "  ".join(filter(None,pair)) if pair else value


def render(slide,spec,box,palette):
    x,y,w,h=box
    canvas,fg,accent=palette[:3]
    pale=blend(canvas,accent,.10)
    rule=blend(canvas,fg,.31)
    # All formulas scale with the requested target area rather than assuming a 16:9 slide.
    mult=min(w/865,h/292,1.15)
    if spec["type"]=="harvey":
        rows=[spec["columns"],*spec["rows"]]
        cols=len(rows[0])
        first=min(4.6*72*mult,max(2.8*72*mult,w*(.44 if cols<=3 else .34)))
        row_h=min(h/len(rows),.62*72*mult)
        table_y=y+(h-row_h*len(rows))/2
        frame=slide.shapes.add_table(len(rows),cols,Pt(x),Pt(table_y),Pt(w),Pt(len(rows)*row_h))
        frame.name="结构图 可编辑比较矩阵"
        table=frame.table
        widths=[first]+[(w-first)/(cols-1)]*(cols-1)
        for i,wide in enumerate(widths):
            table.columns[i].width=Pt(wide)
        for i,row in enumerate(rows):
            table.rows[i].height=Pt(row_h)
            for j,val in enumerate(row):
                c=table.cell(i,j)
                fill=fg if i==0 else (pale if i%2 else canvas)
                c.fill.solid();c.fill.fore_color.rgb=color(fill)
                c.vertical_anchor=MSO_ANCHOR.MIDDLE
                c.margin_top=c.margin_bottom=Pt(1)
                c.margin_left=c.margin_right=Pt(min(8,widths[j]*.04))
                value=harvey_text(val) if i and j else val
                cell_text(c.text_frame,[value],(widths[j],row_h),max(11,18*mult),ink(fill,canvas if i==0 else fg),center=j>0,bold=i==0 or j==0)
        return [[frame.shape_id]]
    items=spec["items"]
    if spec["type"]=="architecture":
        gap=h*.036
        tier_h=min(h*.31,(h-gap*(len(items)-1))/len(items))
        top=y+(h-(tier_h*len(items)+gap*(len(items)-1)))/2
        groups=[]
        for i,item in enumerate(items):
            ty=top+i*(tier_h+gap)
            content=item.get("details") or []
            label_w=min(w*.27,2.65*72*mult) if content else w
            lead=card(slide,(x,ty,label_w,tier_h),[item["title"]],fg,canvas,"层 "+item["title"],max(12,21*mult))
            group=[lead.shape_id]
            groups.append(group)
            if content:
                remaining=w-label_w
                mod_gap=min(7*mult,remaining*.015)
                module=(remaining-mod_gap*len(content))/len(content)
                for j,name in enumerate(content):
                    mx=x+label_w+mod_gap+j*(module+mod_gap)
                    child=card(slide,(mx,ty,module,tier_h),[name],pale,fg,name,max(11,19*mult),center=True)
                    group.append(child.shape_id)
        return groups
    n=len(items);root_w=min(w*.45,4.4*72*mult)
    root_h=min(h*.28,1.18*72*mult)
    child_y=y+h*.54
    gap=min(22*mult,w*.025)
    child_w=(w-gap*(n-1))/n
    mid=y+root_h+(child_y-y-root_h)/2
    left=x+child_w/2;right=x+w-child_w/2
    trunk=line(slide,x+w/2,y+root_h,x+w/2,mid,rule)
    bar=line(slide,left,mid,right,mid,rule)
    branches=[]
    for i,item in enumerate(items):
        cx=x+i*(child_w+gap)
        stem=line(slide,cx+child_w/2,mid,cx+child_w/2,child_y,rule)
        node=card(slide,(cx,child_y,child_w,y+h-child_y),[item["title"],*item.get("details",[])],pale,fg,item["title"],max(13,23*mult),center=True)
        branches.append([node.shape_id,stem.shape_id]+([trunk.shape_id,bar.shape_id] if i==0 else []))
    head=card(slide,(x+(w-root_w)/2,y,root_w,root_h),[spec["root"]],fg,canvas,spec["root"],max(14,25*mult),center=True)
    return [[head.shape_id],*branches]


def set_motion(root, groups, animation):
    if not animation or animation=="none":
        return
    previous=root.find("p:timing",NS)
    if previous is not None:
        root.remove(previous)
    ids=[str(n) for group in groups for n in group]
    together=[str(n) for group in groups for n in group[1:]]
    timing=make_timing(ids,"appear" if animation=="appear" else "fade",together)
    ext=root.find("p:extLst",NS)
    if ext is None:
        root.append(timing)
    else:
        ext.addprevious(timing)


def insert_in_template(root,spec,size,palette):
    from harness_template_deck import box_of, full_bleed, insert_shape
    obstacles=[]
    for _,_,s,t in shape_list(root):
        b=box_of(s,t,size)
        if not b or min(1,b[0]+b[2])<=max(0,b[0]) or min(1,b[1]+b[3])<=max(0,b[1]):
            continue
        text=text_in(s.find("p:txBody",NS)).strip()
        art=picture_blip(s,True) is not None or s.get("useBgFill") in ("true","1") or local(s)=="graphicFrame"
        if text or art and not full_bleed(b):
            obstacles.append(b)
    choices=[]
    for width in (.90,.78,.66,.56):
        for height in (.60,.50,.40):
            for left in (.05,(1-width)/2,.95-width):
                for top in (.19,.26,.33,.93-height):
                    if top+height>.95:
                        continue
                    if all(left+width+.012<=ox or left>=ox+ow+.012 or top+height+.012<=oy or top>=oy+oh+.012 for ox,oy,ow,oh in obstacles):
                        choices.append((width*height,left,top,width,height))
    if not choices:
        raise ValueError("这张模板页没有完整的图表区域。请换一张内容页，或在大胆档对这一页重新构图。")
    _,x,y,w,h=max(choices,key=lambda b:b[0])
    slide=Presentation();slide.slide_width,slide.slide_height=size
    frame=slide.slides.add_slide(slide.slide_layouts[6])
    pw,ph=size[0]/12700,size[1]/12700
    groups=render(frame,spec,(x*pw,y*ph,w*pw,h*ph),palette)
    tree=root.find("p:cSld/p:spTree",NS)
    highest=max(int(n.get("id")) for n in tree.xpath(".//p:cNvPr",namespaces=NS))
    ids={}
    for i,shape_obj in enumerate(frame.shapes,1):
        node=deepcopy(shape_obj._element)
        ids[shape_obj.shape_id]=highest+i
        node.find("*/p:cNvPr",NS).set("id",str(highest+i))
        insert_shape(tree,node)
    return [[ids[n] for n in group] for group in groups]

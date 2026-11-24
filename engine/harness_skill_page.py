"""Compose a one-slide deck authored by a Harness skill into the current presentation."""
from copy import deepcopy
import posixpath
import re
from contextlib import ExitStack

from lxml import etree as ET
from engine import Deck, NS, R, P, local, relpart, target
from election_opening import resolve_child
from harness_template_deck import Output, relationship, clear_motion


def apply_skill_pages(deck_path, root, slides, request):
    with ExitStack() as stack:
        def open_deck(data):
            deck = Deck(data)
            stack.callback(deck.zip.close)
            return deck

        base = open_deck(deck_path.read_bytes())
        out = Output(base, base)
        pp = base.presentation
        presentation = deepcopy(base.tree(pp))
        manifest = deepcopy(base.tree(relpart(pp)))
        masters = presentation.find("p:sldMasterIdLst", NS)
        next_id = max([2147483647] + [int(n.get("id")) for n in masters])
        for master_part in base.rels(pp).values():
            if master_part[0] == "slideMaster":
                next_id = max([next_id]+[int(n.get("id")) for n in base.tree(master_part[1]).findall(".//p:sldLayoutId",NS)])
        for source, original in zip(slides, base.slides):
            spec = source.get("skillPage")
            if not spec:
                continue
            asset = spec.get("asset","")
            if not re.fullmatch(r"skill-pages/[a-f0-9]{64}\.pptx", asset):
                raise ValueError("请先提交当前工作区的单页技能作品。")
            donor = open_deck(resolve_child(root, asset).read_bytes())
            if len(donor.slides) != 1 or max(abs(donor.w-base.w),abs(donor.h-base.h))>1500:
                raise ValueError(f"技能作品须为单页，尺寸为 {base.w/914400:.4f} × {base.h/914400:.4f} 英寸。")
            dp = next(iter(donor.slides))
            slide = deepcopy(donor.tree(dp))
            slide.attrib.pop("show",None)
            visible_text = "\n".join(t.text or "" for t in slide.findall(".//a:t", NS))
            if re.search(r"【(?:你的名字|你的姓名|姓名待填|班级|在此填写[^】]*)】",visible_text):
                raise ValueError("技能页含未填写的姓名或班级，请使用已有材料或省略。")
            if request.get("motionEnabled") is False:
                clear_motion(slide,{"timing","transition"})
            layout = donor.related(dp,"slideLayout")
            master = donor.related(layout,"slideMaster") if layout else None
            if not master:
                raise ValueError("技能页面缺少原生母版或版式。")
            visible_layers=[slide,donor.tree(layout),donor.tree(master)]
            if request.get("imagesEnabled") is False and any(t.find(".//a:blip",NS) is not None for t in visible_layers):
                raise ValueError("配图已关闭，请提交无配图的技能页面。")
            if request.get("chartsEnabled") is False and any(local(n)=="chart" for t in visible_layers for n in t.iter()):
                raise ValueError("图表已关闭，请移除技能页面中的图表。")
            if not request.get("useEmoji") and re.search(r"[\U0001F1E6-\U0001FAFF\ufe0f]",visible_text):
                raise ValueError("Emoji 已关闭，请调整技能页文字。")
            out.generated = donor
            out.copied = {dp:original}
            # The donor notes must point back to this slide and to the existing notes master.
            nm = base.related(pp,"notesMaster")
            donor_nm = donor.related(donor.presentation,"notesMaster")
            if nm and donor_nm:
                out.copied[donor_nm] = nm
            links = deepcopy(donor.tree(relpart(dp)))
            for rel in links:
                if rel.get("TargetMode") != "External":
                    child = out.import_part(target(dp,rel.get("Target")))
                    rel.set("Target",posixpath.relpath(child,posixpath.dirname(original)))
            if donor.related(dp,"notesSlide")=="" and base.related(original,"notesSlide"):
                relationship(links,original,"notesSlide",base.related(original,"notesSlide"))
            out.write_xml(original,slide)
            out.write_xml(relpart(original),links)
            new_master=out.import_part(master)
            rid=relationship(manifest,pp,"slideMaster",new_master)
            next_id+=1
            ET.SubElement(masters,f"{{{P}}}sldMasterId",{"id":str(next_id),f"{{{R}}}id":rid})
            master_tree=deepcopy(donor.tree(master))
            for node in master_tree.findall(".//p:sldLayoutId",NS):
                next_id+=1
                node.set("id",str(next_id))
            out.write_xml(new_master,master_tree)
        out.write_xml(pp,presentation)
        out.write_xml(relpart(pp),manifest)
        result=out.finish()
    deck_path.write_bytes(result)

"""Check native PowerPoint timing, its actual targets, and slide transitions."""
from contextlib import ExitStack
from copy import deepcopy
from io import BytesIO
import re
from zipfile import BadZipFile, ZipFile
from PIL import Image
from engine import Deck, NS, P, R, local, shape_list, text_in
from harness_adjacent_motion import transitions, has_morph
from harness_template_deck import box_of


def shape_objects(root):
    result={}
    for tag in root.iter(f"{{{P}}}cNvPr"):
        shape=tag.getparent().getparent()
        if local(shape) not in ("spTree","cSld"):
            result[tag.get("id")]=(local(shape),tag.get("name",""))
    return result


def layout_evidence(src, dst, source_size, output_size):
    """Compare the native frame's identifiable objects in presentation coordinates."""
    def signatures(slide,size):
        result={}
        for sid,name,shape,transform in shape_list(slide):
            bounds=box_of(shape,transform,size)
            if not bounds:
                continue
            geom=shape.find("p:spPr/a:prstGeom",NS)
            xfrm=shape.find("p:spPr/a:xfrm",NS)
            groups=tuple(g.find("p:nvGrpSpPr/p:cNvPr",NS).get("id") for g in shape.iterancestors()
                         if local(g)=="grpSp")
            key=(sid,name,local(shape),groups,geom.get("prst") if geom is not None else None,
                 xfrm.get("rot","0") if xfrm is not None else None)
            result[key]=bounds
        return result
    a,b=signatures(src,source_size),signatures(dst,output_size)
    if not a:
        return dict(layoutMatched=None,layoutEvidence="原页缺少可识别的独立几何对象。")
    matched=sum(1 for k,box in a.items() if k in b and max(abs(v-w) for v,w in zip(box,b[k]))<=.005)
    # A single generic placeholder cannot establish template provenance.
    enough=matched>=3 or matched==len(a) and any(not re.fullmatch(
        r"(?:TextBox|Rectangle|Picture|Title|Content Placeholder|文本框|图片|矩形|占位符)\s*\d*",k[1],re.I) for k in a)
    ratio=matched/len(a)
    return dict(layoutMatched=(True if enough and ratio>=.85 else False if ratio<.5 else None),
                layoutEvidence=f"原页 {len(a)} 个可定位对象中，{matched} 个仍有相同标识、分组、形状和位置。")


def effects(timing):
    return sum(1 for n in timing.iter(f"{{{P}}}cTn") if n.get("presetClass")) if timing is not None else 0


def fingerprint(node):
    if node is None:
        return None
    return (node.tag,tuple(sorted(node.attrib.items())),(node.text or "").strip(),
            tuple(fingerprint(child) for child in node))


def remap_timing(source, dest, mapping, *, normalized_relations=False):
    """Copy only when every referenced object is mapped and all effects are self-contained."""
    original=source.find("p:timing",NS)
    if original is None:
        raise ValueError("此原页没有原生对象时间线。")
    clone=deepcopy(original)
    original_objects,dest_objects=shape_objects(source),shape_objects(dest)
    assigned={}
    mapping={str(k):str(v) for k,v in mapping.items()}
    src_shapes={n.get("id"):n for n in source.iter(f"{{{P}}}cNvPr")}
    dst_shapes={n.get("id"):n for n in dest.iter(f"{{{P}}}cNvPr")}
    for node in clone.iter():
        if not normalized_relations and any(attr.startswith("{"+R+"}") for attr in node.attrib):
            raise ValueError("该动作涉及其他媒体部件，需要保留完整来源页。")
        key=node.get("spid")
        if key is None:
            continue
        if key not in original_objects:
            raise ValueError("原稿动作所指对象缺失。")
        target=mapping.get(key)
        if target is None and key in dest_objects and original_objects[key]==dest_objects[key]:
            target=key
        if target is None:
            matches=[sid for sid,pair in dest_objects.items() if original_objects[key]==pair]
            if len(matches)==1: target=matches[0]
        if target not in dest_objects or (target in assigned and assigned[target]!=key):
            raise ValueError("动作目标没有唯一对应的成稿对象。")
        before,after=src_shapes[key],dst_shapes[target]
        if after.get("hidden") in ("1","true") and before.get("hidden") not in ("1","true"):
            raise ValueError("成稿动作指向已隐藏的对象。")
        src_body=before.getparent().getparent().find("p:txBody",NS)
        dst_body=after.getparent().getparent().find("p:txBody",NS)
        if text_in(src_body).strip() and not text_in(dst_body).strip():
            raise ValueError("成稿的文字动作目标已无可显示文字。")
        for span in node.findall(".//p:pRg",NS):
            if dst_body is None or int(span.get("end","0"))>=len(dst_body.findall("a:p",NS)):
                raise ValueError("动作引用的段落在新文本中已不存在。")
        assigned[target]=key
        node.set("spid",target)
    return clone


def media_on_slide(deck, part, slide):
    """Hash the linked *playing* asset and its settings, including media without a timeline."""
    rels=deck.rels(part)
    result={}
    for sid,_,shape,_ in shape_list(slide):
        media=[]
        for elem in shape.iter():
            tag=local(elem)
            attrs={k:v for k,v in elem.attrib.items() if k.startswith("{"+R+"}")}
            av=tag in ("videoFile","audioFile","quickTimeFile","media","wavAudioFile","audioCd")
            for key,rid in attrs.items():
                link=rels.get(rid)
                if not link:
                    if av: media.append((tag,"unavailable",None))
                    continue
                kind,path=link
                if tag=="blip" and path.lower().endswith(".gif"):
                    with deck.zip.open(path) as stream, Image.open(stream) as img:
                        # Seeking just the second frame distinguishes a still GIF without decoding a long film.
                        try: img.seek(1)
                        except EOFError: continue
                    media.append(("animatedGIF",kind,deck.image_digest(path)))
                elif av:
                    media.append((tag,kind,deck.image_digest(path)))
        if media:
            settings=[]
            for elem in shape.iter():
                if local(elem) not in ("media","videoFile","audioFile","quickTimeFile","wavAudioFile","audioCd"):
                    continue
                node=deepcopy(elem)
                for child in node.iter():
                    for key in list(child.attrib):
                        if key.startswith("{"+R+"}"): del child.attrib[key]
                settings.append(fingerprint(node))
            result[sid]=(tuple(media),tuple(settings))
    return result


def normalized_slide(deck,part,original):
    """Compare timing and transition sound references by content across different packages."""
    slide=deepcopy(original)
    rels=deck.rels(part)
    for section in [slide.find("p:timing",NS),*transitions(slide)]:
        if section is None: continue
        for el in section.iter():
            for attr,rid in list(el.attrib.items()):
                if not attr.startswith("{"+R+"}"): continue
                rel=rels.get(rid)
                if not rel or rel[1] not in deck.names: raise ValueError("动作依赖未嵌入的媒体。")
                el.set(attr,rel[0]+":"+deck.image_digest(rel[1]))
    return slide


def compare_motion(source_deck, source_number, result_deck, result_number, target_map=None, *, predecessor=False):
    sp=list(source_deck.slides)[source_number-1]
    dp=list(result_deck.slides)[result_number-1]
    src=source_deck.tree(sp)
    dst=result_deck.tree(dp)
    layout=layout_evidence(src,dst,(source_deck.w,source_deck.h),(result_deck.w,result_deck.h))
    try:
        src=normalized_slide(source_deck,sp,src)
        dst=normalized_slide(result_deck,dp,dst)
        sm=media_on_slide(source_deck,sp,src)
        dm=media_on_slide(result_deck,dp,dst)
    except (ValueError,OSError,KeyError):
        return dict(status="unverified",reason="有媒体依赖无法完整核对。",**layout)
    st,dt=src.find("p:timing",NS),dst.find("p:timing",NS)
    left,right=transitions(src),transitions(dst)
    def answer(status,reason):
        return dict(status=status,reason=reason,effects=effects(st),resultEffects=effects(dt),
                    mediaObjects=len(sm),resultMediaObjects=len(dm),needsPlayback=bool(sm or has_morph(src)),
                    sourceTransition=bool(left),resultTransition=bool(right),**layout)
    if st is None and not left and not sm:
        return answer("noMotion","原页没有对象时间线、转场或动态媒体。")
    dest_objects,src_objects=shape_objects(dst),shape_objects(src)
    for sid,media in sm.items():
        if any(item[1]=="unavailable" for item in media[0]):
            return answer("unverified","媒体未嵌入，无法核对内容。")
        key=(target_map or {}).get(sid)
        candidates=[k for k in dm if dest_objects.get(k)==src_objects.get(sid)]
        if key is None: key=sid if sid in candidates else candidates[0] if len(candidates)==1 else None
        if key is None or dm.get(str(key))!=media:
            return answer("changed","动态媒体目标、嵌入内容或播放设置有变化。")
    if st is not None and dt is None:
        return answer("changed","原页有对象动画，成稿此页未写入原生时间线。")
    if left and list(map(fingerprint,left))!=list(map(fingerprint,right)):
        return answer("changed","原页转场与成稿转场不同。")
    if st is not None:
        try:
            expected=remap_timing(src,dst,target_map or {},normalized_relations=True)
        except ValueError as err:
            return answer("unverified",str(err))
        if fingerprint(expected)!=fingerprint(dt):
            return answer("changed","原生时间线的动作、触发、顺序、时长或目标有变化。")
    if has_morph(src):
        if not predecessor: return answer("unverified","平滑转场存在，需核对上一张成稿对应的原页。")
        # Object correspondence is resolved by the player during the transition.
        return dict(answer("unverified","相邻原页及平滑转场一致，对象配对仍需放映确认。"),morphPairVerified=True)
    return answer("preserved","已核对原页的对象时间线、转场及动态媒体。")


def open_reference(stack,ref,workdir,library):
    from election_opening import resolve_child
    from harness_templates import safe_source,master_bytes
    asset=ref.get("asset")
    if asset:
        if not re.fullmatch(r"assets/(?:[a-f0-9]{64}|[a-f0-9-]{36})\.pptx",asset):
            raise ValueError("原稿引用不在当前任务中。")
        file=resolve_child(workdir,asset)
        source=Deck.from_stream(stack.enter_context(file.open("rb")),file.stat().st_size)
    else:
        item=library.get(ref["templateId"])
        if not item or not safe_source(item.source): raise ValueError("所选原稿当前不可用。")
        source=Deck(master_bytes(item))
    stack.enter_context(source.zip)
    return source


def inherit_delivery(data,refs,workdir):
    """Add requested self-contained native effects to an explicitly mapped, otherwise static page."""
    requested=[r for r in refs if r.get("inherit") is True]
    if not requested: return data
    from harness_templates import masters
    from harness_template_deck import encoded
    library={m.id:m for m in masters()}
    deck=Deck(data)
    with deck.zip, ExitStack() as stack:
        cache={}
        parts={}
        for ref in requested:
            key=(ref["templateId"],ref.get("asset"))
            try:
                if key not in cache: cache[key]=open_reference(stack,ref,workdir,library)
                source=cache[key]
                n,p=ref["page"],ref["sourcePage"]
                if not 1<=p<=len(source.slides) or not 1<=n<=len(deck.slides): continue
                sp,dp=list(source.slides)[p-1],list(deck.slides)[n-1]
                src=source.tree(sp)
                dst=deepcopy(deck.tree(dp))
                mapping=ref.get("targetMap") or {}
                if not mapping and not layout_evidence(src,dst,(source.w,source.h),(deck.w,deck.h))["layoutMatched"]:
                    continue
                changed=False
                # A media control sequence requires its exact playing asset and relationships.
                if src.find("p:timing",NS) is not None and dst.find("p:timing",NS) is None and not media_on_slide(source,sp,src):
                    node=remap_timing(src,dst,mapping)
                    ext=dst.find("p:extLst",NS)
                    if ext is None: dst.append(node)
                    else: ext.addprevious(node)
                    changed=True
                if not transitions(dst) and not has_morph(src):
                    for original in transitions(src):
                        if any(a.startswith("{"+R+"}") for el in original.iter() for a in el.attrib):
                            continue
                        node=deepcopy(original)
                        after=next((el for el in dst if local(el) in ("timing","extLst")),None)
                        if after is None: dst.append(node)
                        else: after.addprevious(node)
                        changed=True
                if changed: parts[dp]=encoded(dst)
            except (ValueError,OSError,KeyError,IndexError,BadZipFile):
                # Normal audit reports which targets or source details could not be verified.
                continue
        if not parts: return data
        buf=BytesIO()
        with ZipFile(buf,"w") as target:
            for info in deck.zip.infolist():
                target.writestr(info,parts[info.filename] if info.filename in parts else deck.zip.read(info))
        return buf.getvalue()


def audit_delivery(deck, refs, workdir):
    from harness_templates import masters
    library={m.id:m for m in masters()}
    output={}
    # Open each source only while checking its assigned pages.
    for id in dict.fromkeys(r["templateId"] for r in refs):
        group=[r for r in refs if r["templateId"]==id]
        with ExitStack() as stack:
            try:
                source=open_reference(stack,group[0],workdir,library)
                frames={(r["page"],r["sourcePage"]) for r in group}
                for r in group:
                    n,p=r["page"],r["sourcePage"]
                    if not 1<=p<=len(source.slides) or not 1<=n<=len(deck.slides): 
                        output[n]=dict(status="unverified",reason="原页映射超出实际页数。")
                        continue
                    output[n]=compare_motion(source,p,deck,n,r.get("targetMap"),predecessor=(n-1,p-1) in frames)
            except (ValueError, OSError, KeyError, IndexError, BadZipFile):
                for r in group:
                    output.setdefault(r["page"],dict(status="unverified",reason="无法读取所映射的模板原页。"))
    return output

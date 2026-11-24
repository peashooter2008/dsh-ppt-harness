"""Connect only real adjacent source frames across independently installed slides."""
from copy import deepcopy
from io import BytesIO

from PIL import Image
from lxml import etree as ET

from engine import Deck, NS, P, R, local, picture_blip, relpart, shape_list, target, text_in, write_text, xml
from harness_template_deck import box_of, fit_fill, motion_successor, relationship, visible


def transitions(root):
    return [n for n in root if local(n) == "transition" or
            local(n) == "AlternateContent" and any(local(c) == "transition" for c in n.iter())]


def has_morph(root):
    return any(local(c) == "morph" for n in transitions(root) for c in n.iter())


def unmatched(root):
    for n in transitions(root):
        if not any(local(c) == "morph" for c in n.iter()):
            continue
        fallback = next((t for t in n.iter() if local(t) == "Fallback"), None)
        original = next(n.iter(f"{{{P}}}transition"))
        fade = deepcopy(fallback.find("p:transition", NS)) if fallback is not None and fallback.find("p:transition", NS) is not None else None
        if fade is None:
            fade = ET.Element(f"{{{P}}}transition", dict(original.attrib))
            ET.SubElement(fade, f"{{{P}}}fade")
        root.replace(n, fade)


def shape_slots(master, frame_part, actual):
    source_links = master.rels(frame_part)
    actual_shapes = {sid: shape for sid,_,shape,_ in shape_list(actual)}
    for sid,_,shape,transform in shape_list(master.tree(frame_part)):
        box = box_of(shape, transform, (master.w,master.h))
        if not box or sid not in actual_shapes:
            continue
        original = text_in(shape.find("p:txBody", NS)).strip()
        if original:
            body = actual_shapes[sid].find("p:txBody", NS)
            if body is not None:
                yield ("text",original), body, box
        blip = picture_blip(shape, include_fills=True)
        if blip is not None and box[2]*box[3] >= .055:
            kind, media = source_links.get(blip.get(f"{{{R}}}embed"), (None,None))
            node = picture_blip(actual_shapes[sid], include_fills=True)
            if kind == "image" and node is not None:
                yield ("image",media), node, box


def sync_hidden(out, master, hidden_page, visible_page, direction):
    hidden_part, hidden_frame, hidden_root, hidden_rels = hidden_page
    visible_part, visible_frame, visible_root, visible_rels = visible_page
    assets = {r.get("Id"):target(visible_part,r.get("Target")) for r in visible_rels
              if r.get("Type","").endswith("/image") and r.get("TargetMode") != "External"}
    replacements = {key:node for key,node,box in shape_slots(master,visible_frame,visible_root) if visible(box)}
    for key,node,(x,y,w,h) in shape_slots(master, hidden_frame, hidden_root):
        before = x+w <= 0 or y+h <= 0
        after = x >= 1 or y >= 1
        neighbor = replacements.get(key)
        if neighbor is None or not (before if direction < 0 else after):
            continue
        if key[0] == "text":
            value = text_in(neighbor)
            if value != text_in(node):
                write_text(node,value)
            continue
        media = assets.get(neighbor.get(f"{{{R}}}embed"))
        if not media:
            continue
        pixels = out.read(media)
        if pixels == master.zip.read(key[1]):
            continue
        with Image.open(BytesIO(pixels)) as image:
            fit_fill(node.getparent(), w*master.w/(h*master.h), image.width/image.height)
        node.set(f"{{{R}}}embed", relationship(hidden_rels, hidden_part, "image", media))
        node.attrib.pop(f"{{{R}}}link", None)
        for ext in list(node):
            if local(ext) == "extLst":
                node.remove(ext)


def join_neighbors(out, order, index, *, template, frame, previous, following, adjust_next):
    master = Deck(template) if template and frame else None
    try:
        parts = list(master.slides) if master else []
        def frame_part(n):
            return parts[n-1] if type(n) is int and 1 <= n <= len(parts) else None
        def pair(pos, left_frame, right_frame):
            if not 0 < pos < len(order):
                return
            right_part = order[pos]
            right_data = out.read(right_part)
            right_root = xml(right_data)
            originally_morph = has_morph(right_root)
            left, right = frame_part(left_frame), frame_part(right_frame)
            if not left or not right or motion_successor(master,left,{right}) != right:
                if originally_morph:
                    unmatched(right_root)
                    out.write_xml(right_part, right_root)
                return
            # Restore the original Morph if a revision reconnected two matching source frames.
            if not originally_morph:
                original = transitions(master.tree(right))
                existing = transitions(right_root)
                if not existing or not original:
                    return
                existing[0].getparent().replace(existing[0], deepcopy(original[0]))
            left_part = order[pos-1]
            left_root = xml(out.read(left_part))
            left_page = (left_part, left, left_root, xml(out.read(relpart(left_part))))
            right_page = (right_part, right, right_root, xml(out.read(relpart(right_part))))
            before = {(part,key): ET.tostring(node) for part,_,slide,rels in (left_page,right_page)
                      for key,node in ((part,slide),(relpart(part),rels))}
            sync_hidden(out,master,left_page,right_page,1)
            sync_hidden(out,master,right_page,left_page,-1)
            for part,_,slide,rels in (left_page,right_page):
                for key,node in ((part,slide),(relpart(part),rels)):
                    if ET.tostring(node) != before[(part,key)] or key==right_part and not originally_morph:
                        out.write_xml(key,node)
        pair(index,previous,frame)
        if adjust_next:
            pair(index+1,frame,following)
    finally:
        if master:
            master.zip.close()

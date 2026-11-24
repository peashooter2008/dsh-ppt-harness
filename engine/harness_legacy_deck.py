"""Append or replace a native page in the preceding edition of the actual deck."""
from contextlib import ExitStack
from copy import deepcopy
import posixpath

from lxml import etree as ET

from engine import Deck, NS, P, R, local, relpart, target
from harness_canvas import fit_canvas
from harness_template_deck import Output, relationship


def equivalent_master(base, donor, src, dest):
    """Match full master/layout/theme resources, including cycles and embedded images."""
    mapped = {}

    def match(a, b):
        if a in mapped:
            return mapped[a] == b
        mapped[a] = b
        if a == src or b == dest:
            # Numeric layout IDs are reassigned when registering an imported master.
            trees = [deepcopy(deck.tree(part)) for deck, part in ((donor, a), (base, b))]
            for tree in trees:
                for node in tree.findall(".//p:sldLayoutId", NS):
                    node.attrib.pop("id", None)
            if ET.tostring(trees[0]) != ET.tostring(trees[1]):
                return False
        elif donor.zip.read(a) != base.zip.read(b):
            return False
        def links(deck, part):
            if relpart(part) not in deck.names:
                return {}
            return {r.get("Id"): (r.get("Type"), r.get("TargetMode"), r.get("Target")) for r in deck.tree(relpart(part))}
        left, right = links(donor, a), links(base, b)
        if left.keys() != right.keys():
            return False
        for rid, (kind, mode, url) in left.items():
            other_kind, other_mode, other_url = right[rid]
            if (kind, mode) != (other_kind, other_mode):
                return False
            if mode == "External":
                if url != other_url:
                    return False
            elif not match(target(a,url), target(b,other_url)):
                return False
        return True

    return mapped if match(src, dest) else None


def install_page(old_bytes, single_page, page, expected_count, *, native=False, motion_context=None):
    with ExitStack() as stack:
        old = Deck(old_bytes)
        stack.callback(old.zip.close)
        new = Deck(fit_canvas(single_page, old, native=native))
        stack.callback(new.zip.close)
        if len(old.slides) != expected_count or len(new.slides) != 1 or not 1 <= page <= expected_count+1:
            raise ValueError("上版成稿与任务记录的页数不符，已保留原文件。")
        out = Output(old, new)
        pp = old.presentation
        manifest, links = deepcopy(old.tree(pp)), deepcopy(old.tree(relpart(pp)))
        source = next(iter(new.slides))
        listing = manifest.find("p:sldIdLst", NS)
        if page <= expected_count:
            dest = list(old.slides)[page-1]
        else:
            dest = out.allocate(source, new, preferred=f"ppt/slides/slide{page}.xml")
            rid = relationship(links, pp, "slide", dest)
            slide_id = 1 + max(int(s.get("id")) for s in listing)
            ET.SubElement(listing,f"{{{P}}}sldId",{"id":str(slide_id),f"{{{R}}}id":rid})

        out.copied[source] = dest
        layout = new.related(source,"slideLayout")
        master = new.related(layout,"slideMaster") if layout else None
        if not master:
            raise ValueError("当前页缺少原生母版，已保留原文件。")
        old_masters = [part for kind,part in old.rels(pp).values() if kind=="slideMaster"]
        existing = None
        for part in old_masters:
            existing = equivalent_master(old,new,master,part)
            if existing:
                out.copied.update(existing)
                break
        old_notes, new_notes = old.related(pp,"notesMaster"), new.related(new.presentation,"notesMaster")
        if new_notes:
            if old_notes:
                out.copied[new_notes] = old_notes
            else:
                imported = out.import_part(new_notes)
                rid = relationship(links,pp,"notesMaster",imported)
                notes = ET.Element(f"{{{P}}}notesMasterIdLst")
                before = next(n for n in manifest if local(n) not in ("sldMasterIdLst",))
                before.addprevious(notes)
                ET.SubElement(notes,f"{{{P}}}notesMasterId",{f"{{{R}}}id":rid})
        if not existing:
            imported = out.import_part(master)
            master_ids = manifest.find("p:sldMasterIdLst",NS)
            used_ids = [int(n.get("id")) for n in master_ids]
            for part in old_masters:
                used_ids.extend(int(n.get("id")) for n in old.tree(part).findall(".//p:sldLayoutId",NS))
            next_id = max([2147483647]+used_ids)+1
            rid = relationship(links,pp,"slideMaster",imported)
            ET.SubElement(master_ids,f"{{{P}}}sldMasterId",{"id":str(next_id),f"{{{R}}}id":rid})
            master_tree = deepcopy(new.tree(master))
            for node in master_tree.findall(".//p:sldLayoutId",NS):
                next_id += 1
                node.set("id",str(next_id))
            out.write_xml(imported,master_tree)
        page_links = deepcopy(new.tree(relpart(source)))
        for link in page_links:
            if link.get("TargetMode") != "External":
                imported = out.import_part(target(source,link.get("Target")))
                link.set("Target",posixpath.relpath(imported,posixpath.dirname(dest)))
        slide = deepcopy(new.tree(source))
        out.write_xml(dest,slide)
        out.write_xml(relpart(dest),page_links)
        if motion_context is not None:
            from harness_adjacent_motion import join_neighbors
            order = list(old.slides)
            if page > expected_count:
                order.append(dest)
            join_neighbors(out, order, page-1, **motion_context)
        out.write_xml(pp,manifest)
        out.write_xml(relpart(pp),links)
        return out.finish()

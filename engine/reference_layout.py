"""Fit new material to the native three-click specimen in the local Descartes deck."""

from functools import lru_cache
from pathlib import Path
from unicodedata import east_asian_width
from zipfile import ZipFile

from pptx.oxml import parse_xml

from engine import NS, add_transition, local, transition_spec, write_text


REFERENCE = Path(__file__).resolve().parent / "标杆样片" / "Descartes_English_Animated.pptx"
SLOTS = ("cogito", "doubt", "think", "exist", "while", "page")


def units(value):
    return sum(1 if east_asian_width(c) in "WF" else .58 for c in value)


def body_lines(page):
    body = page.get("body", [])
    if isinstance(body, str):
        body = body.splitlines()
    if not isinstance(body, (list, tuple)) or any(not isinstance(row, str) for row in body):
        return []
    return [line.strip() for row in body for line in row.splitlines() if line.strip()]


def can_use_cogito(page):
    lines = body_lines(page)
    return (len(lines) == 3 and max(map(units, lines)) <= 28
            and all("\n" not in (page.get(field) or "") for field in ("title", "caption", "source"))
            and units(page.get("title", "")) <= 35 and units(page.get("caption", "")) <= 58
            and units(page.get("source", "")) <= 98 and not page.get("visual")
            and not page.get("background") and page.get("reveal") is None
            and REFERENCE.is_file())


@lru_cache(maxsize=2)
def reference_xml(modified):
    with ZipFile(REFERENCE) as archive:
        data = archive.read("ppt/slides/slide4.xml")
    root = parse_xml(data)
    names = tuple(node.get("name") for node in root.findall(".//p:sp/p:nvSpPr/p:cNvPr", NS))
    if names != SLOTS or root.find("p:timing", NS) is None or any(
        "relationships}" in attr for node in root.iter() for attr in node.attrib
    ):
        raise ValueError("三步论证参考页的对象已变化，请重新核对本地笛卡尔终稿第 4 页。")
    return data


def add_cogito(prs, page):
    if not can_use_cogito(page):
        raise ValueError("笛卡尔三步论证适合三句简短正文，配图、长段落和已指定的动效可用原稿呈现。")
    from author import text

    root = parse_xml(reference_xml(REFERENCE.stat().st_mtime_ns))
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    number = len(prs.slides)
    values = (page["title"], *body_lines(page), page.get("caption", ""), f"{number:02d}")
    # Keep the original object IDs: the original click groups point to those exact IDs.
    for shape, value in zip(root.findall("p:cSld/p:spTree/p:sp", NS), values):
        body = shape.find("p:txBody", NS)
        width = int(shape.find("p:spPr/a:xfrm/a:ext", NS).get("cx")) / 12700
        write_text(body, value)
        for run in body.findall(".//a:rPr", NS):
            size = min(int(run.get("sz", "2400")), int(90 * width / max(1, units(value))))
            run.set("sz", str(size))
            font = run.find("a:ea", NS)
            if font is not None:
                font.set("typeface", "Microsoft YaHei")
    csld = root.find("p:cSld", NS)
    # Keep the destination shape tree instance owned by python-pptx for adding the source footer.
    dest = slide._element
    dest_csld = dest.find("p:cSld", NS)
    dest_tree = dest_csld.find("p:spTree", NS)
    dest_csld.set("name", page["title"])
    dest_csld.insert(0, csld.find("p:bg", NS))
    dest_tree[:] = list(csld.find("p:spTree", NS))
    for child in list(root):
        if local(child) in ("transition", "AlternateContent"):
            if "transition" not in page:
                dest.append(child)
    if "transition" in page:
        add_transition(dest, transition_spec(page["transition"]))
    dest.append(root.find("p:timing", NS))
    source = page.get("source", "")
    if source:
        text(slide, source, (52, 498, 790, 25), 13, "D5D5CF", name="来源")
    notes = [page.get("notes", ""), "三次点击依次呈现三句正文。"]
    if page.get("caption"):
        notes.append("最后一次点击后，补充说明跟在第三句之后淡入。")
    if source:
        notes.append("来源：" + source)
    slide.notes_slide.notes_text_frame.text = "\n".join(filter(None, notes))

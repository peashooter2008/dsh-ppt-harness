"""Edit native slide paragraphs in a private copy of a selected Harness template."""

import json
import sys
from copy import deepcopy
from pathlib import Path

from lxml import etree as ET

from engine import A, NS, Deck, local, shape_list, write_text


def slide_slots(deck, page):
    if type(page) is not int or not 1 <= page <= len(deck.slides):
        raise ValueError("页码超出整稿范围。")
    part = list(deck.slides)[page - 1]
    slots = {}
    for shape_id, name, shape, _ in shape_list(deck.tree(part)):
        for index, paragraph in enumerate(shape.findall("p:txBody/a:p", NS), 1):
            # Automatic fields, inline breaks and hyperlinks have semantics beyond plain text.
            if any(local(child) not in {"pPr", "r", "endParaRPr"} for child in paragraph):
                continue
            if paragraph.find(".//a:hlinkClick", NS) is not None or paragraph.find(".//a:hlinkMouseOver", NS) is not None:
                continue
            runs = paragraph.findall("a:r/a:t", NS)
            if runs:
                key = f"{shape_id}:{index}"
                if key in slots:
                    raise ValueError("该页含有重名的对象编号，无法可靠定位段落。")
                slots[key] = (name, paragraph, "".join(run.text or "" for run in runs))
    return part, slots


def apply_edits(deck, changes):
    if not isinstance(changes, list) or not 1 <= len(changes) <= 256:
        raise ValueError("一次请提交 1 至 256 段改动。")
    locations, seen, changed_pages = {}, set(), set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("改动应包含页码、段落编号、原文和新文。")
        page, slot = change.get("page"), change.get("slot")
        if type(page) is not int or not isinstance(slot, str):
            raise ValueError("缺少有效的页码或段落编号。")
        if page not in locations:
            locations[page] = slide_slots(deck, page)
        part, slots = locations[page]
        if slot not in slots or (page, slot) in seen:
            raise ValueError(f"第 {page} 页段落不存在或被重复修改。")
        seen.add((page, slot))
        _, paragraph, old = slots[slot]
        if old != change.get("before"):
            raise ValueError(f"第 {page} 页段落原文已变化，请重新读取后修改。")
        text = change.get("text")
        if not isinstance(text, str) or len(text) > 32767 or any(ord(c) < 32 for c in text):
            raise ValueError("每项改动限一个纯文字段落，最长 32767 字符。")
        if old == text:
            continue
        body = ET.Element(f"{{{A}}}txBody")
        body.append(deepcopy(paragraph))
        write_text(body, text)
        replacement = body[0]
        if not text:
            # An empty edited paragraph must remain addressable for subsequent edits.
            run = deepcopy(paragraph.find("a:r/a:t", NS).getparent())
            run.find("a:t", NS).text = ""
            end = replacement.find("a:endParaRPr", NS)
            if end is None:
                replacement.append(run)
            else:
                end.addprevious(run)
        paragraph.getparent().replace(paragraph, replacement)
        deck.changed.add(part)
        changed_pages.add(page)
    return sorted(changed_pages)


def main():
    source = Path(sys.argv[1])
    request = json.load(sys.stdin)
    with source.open("rb") as stream:
        deck = Deck.from_stream(stream, source.stat().st_size)
        with deck.zip:
            result = {"ok": True, "slides": len(deck.slides)}
            if request.get("action") == "inspect":
                page = request["page"]
                _, slots = slide_slots(deck, page)
                result.update(page=page, slots=[{"slot": key, "name": name, "text": text}
                                                for key, (name, _, text) in slots.items()])
            elif request.get("action") == "edit":
                changes = request.get("edits")
                pages = apply_edits(deck, changes)
                if not pages:
                    raise ValueError("新文字与原文相同。")
                output = deck.save()
                with Path(sys.argv[2]).open("xb") as handle:
                    handle.write(output)
                result.update(changed=sum(c["text"] != c["before"] for c in changes), pages=pages)
            else:
                raise ValueError("未知的段落操作。")
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)

"""Supply private, local template masters and reviewed slide previews to Harness."""

import argparse
import base64
from contextlib import ExitStack
from dataclasses import dataclass, replace
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from PIL import Image
from library import class_election_source
from template_rights import replace_restricted_photo
from harness_style import safe_visual, unknown_visual
from template_registry import SAMPLES, indexed_templates, supplementary_templates, source_key


ROOT = Path(__file__).resolve().parent
CURATED = ROOT / "精选库"
DESKTOP = Path(os.environ.get("DIEYE_TEMPLATE_DESKTOP", str(Path.home() / "OneDrive" / "Desktop"))) / "ppt模板"
ARCHIVE_NAME = "(免费Ppt模板）.zip"
ARCHIVE = next((p for p in (DESKTOP / ARCHIVE_NAME, DESKTOP.parent / ARCHIVE_NAME)
                if p.is_file() and p.absolute() == p.resolve()), DESKTOP / ARCHIVE_NAME)
SLIDE_IDS = "{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst"


@dataclass(frozen=True)
class Page:
    number: int
    label: str
    image: Path | None = None  # When absent, use the embedded first-page thumbnail.


@dataclass(frozen=True)
class Master:
    id: str
    title: str
    category: str
    style: str
    summary: str
    source: Path
    pages: tuple
    filename: str
    member: str = ""
    fingerprint: str = ""
    recommended: bool = True
    indexed_slides: int = 0
    thumbnail: str = ""
    registry_id: str = ""
    source_category: str = ""


def safe_source(candidate):
    # Do not follow a junction or symlink from a registered folder into other files.
    full = candidate.absolute()
    if full != ARCHIVE.absolute() and not any(full.is_relative_to(boundary) for boundary in (ROOT, SAMPLES, DESKTOP.absolute())):
        return False
    return full == candidate.resolve() and full.is_file()


def read_json(file):
    return json.loads(file.read_text(encoding="utf-8-sig")) if safe_source(file) else {}


def recommended_masters():
    final = ROOT / "标杆样片"
    yield Master("dream-final", "笛卡尔：我们如何确定自己醒着？", "演讲授课", "复古拼贴",
                 "用梦境提问、逐次点击推理和现场提问组织讲述。",
                 final / "Descartes_English_Animated.pptx",
                 tuple(Page(i, label, final / f"第{i:02d}页.png") for i, label in
                       ((2, "让听众起疑"), (4, "逐句推出结论"), (7, "并排辨析概念"), (13, "给听众作答时间"))),
                 "Descartes_English_Animated.pptx")
    for key, title, filename, prefix, summary, scenes in (
        ("class-election", "竞选学习委员", "竞选学习委员.pptx", "学委",
         "从同学听得懂的自我介绍，过渡到能为班级做什么。", ((4, "个人介绍"), (13, "当选承诺"))),
        ("branch-election", "团支书竞选", "团支书竞选.pptx", "团支书",
         "以灯光引导注意，从认识候选人过渡到岗位理解。", ((12, "灯光带出兴趣爱好"), (15, "岗位理解"))),
    ):
        pages = (Page(1, "原稿封面"),) + tuple(
            Page(n, label, CURATED / "竞选样页" / f"{prefix}-{n:02d}.jpg") for n, label in scenes)
        source = class_election_source() if key == "class-election" else None
        if key == "branch-election":
            published = ROOT / "本地作品" / "站点精选发行" / key / "deck.pptx"
            if safe_source(published):
                source = published
            gallery = CURATED / "站点推荐"
            pages = tuple(Page(p.number, p.label, gallery / f"{key}-{p.number}.jpg") for p in (pages[2], pages[0], pages[1]))
        if source:
            yield Master(key, title, "学生竞选", "校园竞选", summary, source, pages, filename)

    directory = CURATED / "用户原稿"
    for row in read_json(directory / "manifest.json").get("items", []):
        key = row["id"]
        if not re.fullmatch(r"[a-z0-9-]+", key):
            continue
        folder = directory / key
        pages = tuple(Page(p["page"], p["label"], folder / f"page-{p['page']}.jpg") for p in row["pages"])
        working = row.get("working", "source.pptx")
        if Path(working).name != working or not working.endswith(".pptx"):
            continue
        filename = Path(row["filename"]).name
        summary = row["rules"]
        if working != "source.pptx":
            filename = Path(filename).stem + "-MP4兼容版.pptx"
            summary += " 导出八页 MP4 兼容版。"
        yield Master(key, row["title"], row["category"], row["style"], summary, folder / working, pages, filename)

    rows = read_json(CURATED / "复查" / "候选.json").get("rows", [])
    sources = {r["sourceId"]: r for r in rows}
    for row in read_json(CURATED / "manifest.json").get("items", []):
        source = sources.get(row["sourceId"])
        if not source or not re.fullmatch(r"[a-z0-9-]+", row["id"]):
            continue
        original = Path(source["source"])
        member = source.get("member", "")
        if member and original.name == ARCHIVE.name:
            original = ARCHIVE
        elif member or not original.absolute().is_relative_to(DESKTOP.absolute()):
            continue
        yield Master(row["id"], row["sourceName"].removesuffix(".pptx"), row["category"], row["style"],
                     row["reason"], original, (Page(row["page"], row["title"], CURATED / row["preview"]),),
                     row["sourceName"], member, source.get("fingerprint") or "")

    additional = CURATED / "站点推荐"
    for row in read_json(additional / "index.json").get("items", []):
        digest = row["fingerprint"]
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or row["id"] != "collection-" + digest[:18]:
            continue
        pages = tuple(Page(p["number"], p["label"], additional / f"{row['id']}-{p['number']}.jpg")
                      for p in row["pages"])
        yield Master(row["id"], row["title"], row["category"], row["style"], row["summary"],
                     ARCHIVE, pages, row["filename"], row["member"], digest)

    studies = ROOT / "作品集"
    study_pages = {
        "register": ("机制讲解", "观察墨版和朱版的位移", "解释色边如何形成"),
        "hinge": ("产品说明", "观察固定轴与转动件", "对照收起与展开"),
        "rest": ("演讲授课", "逐拍出现，留出空拍", "用一句话收束"),
        "means": ("数据汇报", "比较两组均值", "展开样本的分布"),
        "nightbus": ("摄影叙事", "用局部照片提问", "揭示时刻与终点"),
        "wrongchat": ("情景讲述", "逐击揭开群名和反应", "给出对话的回应"),
    }
    for row in read_json(studies / "manifest.json").get("items", []):
        key = row["id"]
        if key not in study_pages:
            continue
        category, middle, end = study_pages[key]
        folder = studies / key
        pages = (Page(1, "开场", folder / "cover.jpg"), Page(2, middle, folder / "page-2.jpg"),
                 Page(3, end, folder / "page-3.jpg"))
        yield Master("study-" + key, row["title"], category, row["style"], row["technique"],
                     folder / "main.pptx", pages, row["title"] + ".pptx")

    examples = ROOT / "交付样例"
    for key, style, summary in (
        ("original-minimal", "简约", "白底原生图表，把观察和比较留给现场讲述。"),
        ("original-tech", "科技", "深色底与刻度线，适合逐次揭示数据变化。"),
        ("original-ink", "中国风", "用纸色、侧题和三栏构图呈现一则数据观察。"),
        ("original-abstract", "抽象", "用几何形状标记章节，配合原生图表展示观察结果。"),
    ):
        filename = f"{style}-校园通知.pptx"
        yield Master(key, f"{style} · 校园通知", "数据汇报", style, summary, examples / filename,
                     (Page(2, "比较两次观察", examples / f"{style}-同页预览.png"),), filename)


def masters():
    """One available-source inventory with stable curated IDs and optional recommendations."""
    indexed = list(indexed_templates(samples=SAMPLES, desktop=DESKTOP, archive=ARCHIVE))
    by_source = {source_key(row["source"], row["member"]): row for row in indexed}
    seen = set()
    for master in recommended_masters():
        key = source_key(master.source, master.member)
        if key in seen or not safe_source(master.source):
            continue
        seen.add(key)
        row = by_source.get(key)
        if row:
            master = replace(master, indexed_slides=row["slides"], thumbnail=row["thumbnail"],
                             registry_id=row["legacy_id"], source_category=row["category"])
        yield master
    for row in indexed:
        key = source_key(row["source"], row["member"])
        if key in seen:
            continue
        seen.add(key)
        template_id = ("collection-" + row["fingerprint"][:18] if row["member"]
                       else "library-" + row["legacy_id"])
        yield Master(template_id, Path(row["name"]).stem, row["category"],
                     "热梗" if row["category"] == "热潮、可爱、梗" else row["category"],
                     "完整原稿可供选页、改写或提取设计参考；模型结合内容判断整稿风格与动画。",
                     row["source"], (Page(row["page"], "原稿实页" if row["cover"] else "原稿封面", row["cover"]),),
                     row["name"], row["member"], row["fingerprint"], False, row["slides"],
                     row["thumbnail"], row["legacy_id"], row["category"])
    for row in supplementary_templates():
        key = source_key(row["source"])
        if key in seen:
            continue
        seen.add(key)
        yield Master(row["id"], row["title"], row["category"], row["style"], row["summary"],
                     row["source"], tuple(Page(p["number"], p["label"], p["cover"]) for p in row["pages"]),
                     row["name"], fingerprint=row["fingerprint"], recommended=row["recommended"],
                     indexed_slides=row["slides"], registry_id=row["id"], source_category=row["category"])


def slide_count(package):
    with ZipFile(package) as deck:
        listing = ET.fromstring(deck.read("ppt/presentation.xml")).find(SLIDE_IDS)
        return len(listing) if listing is not None else 0


def read_member(master):
    # Look up only the previously reviewed member. Never extract member paths.
    if not safe_source(master.source):
        raise ValueError("所选模板当前不可用，请刷新模板库。")
    with ZipFile(master.source) as archive:
        info = archive.getinfo(master.member)
        if not 0 < info.file_size <= 256 * 1024 * 1024:
            raise ValueError("模板文件超过当前可读取范围。")
        data = archive.read(info)
    if not master.fingerprint or hashlib.sha256(data).hexdigest() != master.fingerprint:
        raise ValueError("归档模板与已审阅的版本不一致。")
    return data


def output_folder(workdir):
    folder = workdir / "templates"
    if folder.resolve() != folder:
        raise ValueError("模板输出路径无效。")
    folder.mkdir(exist_ok=True)
    return folder


def read_local_master(master):
    if not safe_source(master.source):
        raise ValueError("所选模板当前不可用，请刷新模板库。")
    # RHINE LAB is a known large local source, but unbounded local reads are not.
    if not 0 < master.source.stat().st_size <= 512 * 1024 * 1024:
        raise ValueError("模板文件超过当前可读取范围。")
    data = master.source.read_bytes()
    if master.fingerprint and hashlib.sha256(data).hexdigest() != master.fingerprint:
        raise ValueError("本地补充模板与已登记版本不一致，请重新核对原稿。")
    return data


def master_bytes(master):
    return replace_restricted_photo(read_member(master) if master.member else read_local_master(master))


def preview(master, page, folder):
    source = page.image or master.source
    if not safe_source(source):
        return None
    stat = source.stat()
    name = f"{master.id}-{page.number}-{stat.st_mtime_ns:x}-{stat.st_size:x}.jpg"
    target = folder / name
    if target.resolve() != target:
        raise ValueError("样图输出路径无效。")
    if not target.is_file():
        if page.image:
            data = source.read_bytes()
        elif master.thumbnail:
            prefix, encoded = master.thumbnail.split(",", 1)
            if prefix not in ("data:image/jpeg;base64", "data:image/png;base64") or len(encoded) > 8 * 1024 * 1024:
                raise ValueError("模板缩略图格式无效。")
            data = base64.b64decode(encoded, validate=True)
        elif not master.member:
            with ZipFile(source) as deck:
                data = deck.read("docProps/thumbnail.jpeg")
        else:
            return None
        with Image.open(BytesIO(data)) as img:
            img.thumbnail((800, 450), Image.Resampling.LANCZOS)
            encoded = BytesIO()
            img.convert("RGB").save(encoded, "JPEG", quality=82, optimize=True)
        pending = folder / f"{uuid4().hex}.partial"
        pending.write_bytes(encoded.getvalue())
        os.replace(pending, target)
    return {"page": page.number, "label": page.label, "preview": "templates/" + name}


def reviewed_motion(master, count, reviews):
    review = reviews.get(master.id)
    if not isinstance(review, dict) or master.member:
        return None
    try:
        relative = Path(review["file"])
        if relative.is_absolute() or relative.drive or relative.root or ".." in relative.parts:
            return None
        clip = ROOT / relative
        pages = review["pages"]
        if (clip.suffix != ".mp4" or not safe_source(clip)
                or not isinstance(pages, list) or not pages
                or any(type(n) is not int or not 1 <= n <= count for n in pages)
                or review["kind"] not in ("original", "adaptation")
                or not isinstance(review["label"], str) or not review["label"].strip()
                or type(review["duration"]) not in (float, int) or not 0 < review["duration"] < float("inf")):
            return None
        for source, expected in ((master.source, review["sourceSha256"]), (clip, review["fingerprint"])):
            with source.open("rb") as stream:
                digest = hashlib.sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
                if digest.hexdigest() != expected:
                    return None
        return {key: review[key] for key in
                ("pages", "label", "kind", "duration", "file", "sourceSha256", "fingerprint")}
    except (KeyError, OSError, TypeError, ValueError):
        return None


def catalog_item(master, folder, reviews=None, with_preview=False):
    # Indexed counts and thumbnails let the directory stay available without
    # decompressing hundreds of source decks. Export/profile check actual bytes.
    count = master.indexed_slides or slide_count(master.source)
    if count < 1:
        raise ValueError("模板没有可读取的页面。")
    pages = []
    for page in master.pages:
        if not 1 <= page.number <= count:
            continue
        if not with_preview and not master.recommended and not page.image:
            continue
        try:
            rendered = preview(master, page, folder)
        except (KeyError, OSError, ValueError, BadZipFile):
            continue
        if rendered:
            pages.append(rendered)
    item = dict(id=master.id, title=master.title, category=master.category,
                style=master.style, summary=master.summary, slides=count, pages=pages,
                samplePages=[p.number for p in master.pages if 1 <= p.number <= count],
                recommended=master.recommended, registryId=master.registry_id,
                sourceCategory=master.source_category or master.category,
                previewAvailable=bool(pages or master.thumbnail), visual=unknown_visual())
    if master.recommended or with_preview:
        item["visual"] = cached_visual(master, folder)
    if master.recommended and reviews:
        motion = reviewed_motion(master, count, reviews)
        if motion:
            item["motion"] = motion
    return item


def cached_visual(master, folder):
    """Retain the old curated style evidence, recomputing only changed sources."""
    stat = master.source.stat()
    signature = hashlib.sha256((str(master.source) + master.member + master.fingerprint
                                + f":{stat.st_size}:{stat.st_mtime_ns}:visual-1").encode()).hexdigest()
    cache = folder / f"visual-{signature}.json"
    if cache.absolute() != cache.resolve():
        return unknown_visual()
    try:
        value = json.loads(cache.read_text(encoding="utf-8"))
        if isinstance(value, dict) and set(unknown_visual()).issubset(value):
            return value
    except (OSError, ValueError):
        pass
    try:
        with ExitStack() as stack:
            deck = open_source({"id": master.id}, {master.id: master}, folder.parent, stack)
            value = safe_visual(deck)
        pending = folder / f"{uuid4().hex}.partial"
        pending.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        os.replace(pending, cache)
        return value
    except (ValueError, OSError, KeyError, BadZipFile, RuntimeError):
        return unknown_visual()


def catalog(folder, query="", category="", collection="all", offset=0, limit=0):
    if (not isinstance(query, str) or len(query) > 160 or not isinstance(category, str)
            or len(category) > 160 or collection not in ("all", "curated")
            or type(offset) is not int or offset < 0 or type(limit) is not int or not 0 <= limit <= 1000):
        raise ValueError("模板检索条件无效。")
    items, warnings = [], []
    try:
        reviews = read_json(CURATED / "动作片段.json")
    except (OSError, ValueError):
        reviews = {}
    if not isinstance(reviews, dict):
        reviews = {}
    available = list(masters())
    recommended_count = sum(m.recommended for m in available)
    categories = list(dict.fromkeys(m.source_category or m.category for m in available))
    for master in available:
        if collection == "curated" and not master.recommended:
            continue
        if category and category not in (master.category, master.style, master.source_category):
            continue
        text = " ".join((master.title, master.category, master.style, master.source_category, master.summary)).lower()
        if not all(word in text for word in query.lower().split()):
            continue
        try:
            items.append(catalog_item(master, folder, reviews))
        except (OSError, ValueError, ET.ParseError, KeyError, BadZipFile, RuntimeError):
            warnings.append({"id": master.id, "title": master.title, "error": "原稿暂时不可读取。"})
            continue
    return {"items": items[offset:offset + limit] if limit else items[offset:], "total": len(items),
            "availableTotal": len(available), "recommendedCount": recommended_count,
            "categories": categories, "collection": collection, "warnings": warnings}


def template_preview(key, folder):
    master = next((item for item in masters() if item.id == key), None)
    if master is None:
        raise ValueError("选中的模板原稿不可用，请刷新模板库。")
    return {"item": catalog_item(master, folder, with_preview=True)}


def export_master(key, folder):
    master = next((item for item in masters() if item.id == key), None)
    if master is None or not safe_source(master.source):
        raise ValueError("选中的模板原稿不可用，请刷新模板库。")
    data = master_bytes(master)
    count = slide_count(BytesIO(data))
    if count < 2:
        raise ValueError("此文件不是多页模板。")
    # New destination per export keeps earlier downloads and user edits intact.
    name = f"{master.id}-{uuid4().hex}.pptx"
    pending = folder / (name + ".partial")
    with pending.open("xb") as copy:
        copy.write(data)
    pending.replace(folder / name)
    return {"deck": "templates/" + name, "filename": master.filename, "slides": count}


def open_source(source, library, workdir, stack, member=None):
    from election_opening import resolve_child
    from engine import Deck

    file = None
    if source.get("asset"):
        if not isinstance(source["asset"], str) or not re.fullmatch(r"assets/(?:[a-f0-9]{64}|[a-f0-9-]{36})\.pptx", source["asset"]):
            raise ValueError("模板须来自本任务的素材目录。")
        file = resolve_child(workdir, source["asset"])
    elif source.get("result"):
        if not isinstance(source["result"], str) or not re.fullmatch(r"plans/[a-f0-9]{32}/presentation\.pptx", source["result"]):
            raise ValueError("成稿须来自本任务的输出目录。")
        file = resolve_child(workdir, source["result"])
    else:
        master = library.get(source.get("id"))
        if not master or not safe_source(master.source):
            raise ValueError("所选模板当前不可用，请刷新模板库。")
        if master.member:
            deck = Deck(member if member is not None else read_member(master))
        elif master.fingerprint:
            deck = Deck(read_local_master(master))
        else:
            file = master.source
    if file is not None:
        deck = Deck.from_stream(stack.enter_context(file.open("rb")), file.stat().st_size)
    stack.enter_context(deck.zip)
    return deck


def source_profiles(payload, workdir):
    from engine import NS, local
    from harness_page_selection import describe_frame

    sources = payload.get("sources")
    start, limit = payload.get("start", 1), payload.get("limit", 0)
    if (not isinstance(sources, list) or not 1 <= len(sources) <= 31
            or type(start) is not int or start < 1 or type(limit) is not int or not 0 <= limit <= 16):
        raise ValueError("模板页范围无效。")
    library = {item.id: item for item in masters()}
    results = []
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str):
            raise ValueError("模板编号无效。")
        with ExitStack() as stack:
            if payload.get("action") == "visual":
                try:
                    visual = safe_visual(open_source(source, library, workdir, stack))
                except (ValueError, OSError, KeyError, BadZipFile, RuntimeError):
                    visual = unknown_visual()
                results.append({"id":source["id"], "visual":visual})
                continue
            deck = open_source(source, library, workdir, stack)
            count = len(deck.slides)
            ratio = deck.w / deck.h
            label = next((name for name, value in (("16:9",16/9),("4:3",4/3),("16:10",1.6),("1:1",1),("9:16",9/16))
                          if abs(value / ratio - 1) <= .001), f"{ratio:.3f}:1")
            summary = {"id": source["id"], "width": deck.w, "height": deck.h, "ratio": label, "slides": count}
            if limit:
                summary["visual"] = safe_visual(deck)
                if start > count:
                    raise ValueError("起始页超出模板原稿页数。")
                pages = []
                for number, part in enumerate(list(deck.slides)[start-1:start-1+limit], start):
                    frame = describe_frame(deck, part, number)
                    root = deck.tree(part)
                    transitions = root.findall(".//p:transition", NS)
                    effects = sorted({local(node) for tr in transitions for node in tr if local(node) not in ("sndAc","extLst")})
                    pages.append({"page": number, "hidden": root.get("show") in ("0","false"),
                                  "bodySlots": frame.body_slots, "twoColumns": frame.columns,
                                  "charts": frame.charts, "table": frame.table, "photo": frame.photo,
                                  "imageBackground": frame.picture_background,
                                  "timing": root.find(".//p:timing", NS) is not None, "transitions": effects})
                summary["pages"] = pages
            results.append(summary)
    return {"profiles": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True, type=Path)
    workdir = parser.parse_args().workdir.resolve(strict=True)
    payload = json.load(sys.stdin)
    if payload.get("action") == "storyboard":
        from harness_storyboard import storyboard
        return storyboard(payload, workdir)
    if payload.get("action") in ("profile", "visual"):
        return source_profiles(payload, workdir)
    folder = output_folder(workdir)
    if payload.get("action") == "list":
        return catalog(folder, query=payload.get("query", ""), category=payload.get("category", ""),
                       collection=payload.get("collection", "all"), offset=payload.get("offset", 0),
                       limit=payload.get("limit", 0))
    if payload.get("action") == "preview":
        return template_preview(payload.get("templateId"), folder)
    if payload.get("action") == "export":
        return export_master(payload.get("templateId"), folder)
    raise ValueError("模板操作无效。")


if __name__ == "__main__":
    try:
        print(json.dumps({"ok": True, **main()}, ensure_ascii=False))
    except (ValueError, OSError, KeyError, BadZipFile, ET.ParseError, RuntimeError) as exc:
        message = str(exc) if type(exc) is ValueError and str(exc).endswith("。") else "读取或复制模板失败，请检查本地模板文件。"
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
        sys.exit(1)

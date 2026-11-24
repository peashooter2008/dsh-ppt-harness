"""Shared source inventory; recommendations never decide library membership."""

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT.parent / "PPT创作样例"
ARCHIVE_NAME = "(免费Ppt模板）.zip"


def desktop_sources():
    return Path(os.environ.get("DIEYE_TEMPLATE_DESKTOP", str(Path.home() / "OneDrive" / "Desktop"))) / "ppt模板"


def archive_source(desktop):
    return next((p for p in (desktop / ARCHIVE_NAME, desktop.parent / ARCHIVE_NAME)
                 if p.is_file() and p.absolute() == p.resolve()), desktop / ARCHIVE_NAME)


@lru_cache(maxsize=8)
def _read_index(path, modified, size):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_index(path):
    # Only fixed, project-owned indexes are read. Refuse redirected index files.
    if path.absolute() != path.resolve() or not path.is_file():
        return {}
    stat = path.stat()
    return _read_index(str(path), stat.st_mtime_ns, stat.st_size)


def source_key(source, member=""):
    return (os.path.normcase(str(Path(source).absolute())), member)


def registered_child(folder, value, extensions):
    """Resolve only a relative, non-redirected file below one registered folder."""
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        return None
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() not in extensions:
        return None
    file = folder / Path(*relative.parts)
    if (not file.absolute().is_relative_to(folder.absolute()) or file.absolute() != file.resolve()
            or not file.is_file()):
        return None
    return file


@lru_cache(maxsize=32)
def _supplement_count(path, modified, size):
    """Read only the package directory and bounded slide listing, never whole media."""
    if not 0 < size <= 512 * 1024 * 1024:
        return 0
    try:
        with ZipFile(path) as deck:
            if not {"[Content_Types].xml", "ppt/_rels/presentation.xml.rels"}.issubset(deck.namelist()):
                return 0
            info = deck.getinfo("ppt/presentation.xml")
            if not 0 < info.file_size <= 1024 * 1024:
                return 0
            root = ET.fromstring(deck.read(info))
            if root.tag != "{http://schemas.openxmlformats.org/presentationml/2006/main}presentation":
                return 0
            slides = root.find("{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst")
            return len(slides) if slides is not None else 0
    except (OSError, KeyError, ValueError, ET.ParseError, BadZipFile):
        return 0


def supplementary_templates(folder=None):
    """Explicit user additions shared by both clients, confined to 用户补充."""
    folder = folder or ROOT / "精选库" / "用户补充"
    if folder.absolute() != folder.resolve():
        return
    document = read_index(folder / "manifest.json")
    if not isinstance(document, dict) or not isinstance(document.get("items", []), list):
        return
    seen_ids, seen_sources = set(), set()
    for row in document.get("items", []):
        if not isinstance(row, dict):
            continue
        key, count, fingerprint = row.get("id"), row.get("slides"), row.get("fingerprint", "")
        if (not isinstance(key, str) or not re.fullmatch(r"user-[a-z0-9-]{1,75}", key)
                or key in seen_ids or type(count) is not int or count < 1
                or not re.fullmatch(r"[a-f0-9]{64}", fingerprint)
                or type(row.get("recommended", False)) is not bool):
            continue
        source = registered_child(folder, row.get("filename"), {".pptx"})
        if source is None or source_key(source) in seen_sources:
            continue
        stat = source.stat()
        if _supplement_count(str(source), stat.st_mtime_ns, stat.st_size) != count:
            continue
        pages = []
        for page in row.get("pages", []) if isinstance(row.get("pages", []), list) else []:
            if not isinstance(page, dict) or type(page.get("number")) is not int or not 1 <= page["number"] <= count:
                continue
            cover = registered_child(folder, page.get("preview"), {".png", ".jpg", ".jpeg"})
            if cover is None and page["number"] != 1:
                continue
            pages.append({"number": page["number"], "label": str(page.get("label") or "原稿实页")[:160], "cover": cover})
        if not pages:
            pages = [{"number": 1, "label": "原稿封面", "cover": None}]
        seen_ids.add(key)
        seen_sources.add(source_key(source))
        yield {"id": key, "source": source, "name": source.name, "slides": count,
               "title": str(row.get("title") or source.stem)[:240],
               "category": str(row.get("category") or "用户补充")[:100],
               "style": str(row.get("style") or "自主设计参考")[:100],
               "summary": str(row.get("summary") or "用户明确补充的完整原稿，可按内容选页或自主改造。")[:1200],
               "fingerprint": fingerprint, "recommended": row.get("recommended", False), "pages": pages}


def indexed_templates(samples=SAMPLES, desktop=None, archive=None):
    """Read indexed metadata without unpacking PPTX files or losing historical IDs.

    An archive moved into ppt模板 is resolved in one place for both clients.
    Unknown/missing images do not exclude an otherwise available source deck.
    """
    desktop = desktop or desktop_sources()
    archive = archive or archive_source(desktop)
    covers = {}
    for i, row in enumerate(read_index(samples / "热潮模板候选页.json").get("results", []), 1):
        covers[Path(row["path"]).name] = (row.get("number", 1), samples / "热潮模板试选" / f"preview-{i:02d}.png")
    for filename in ("热潮模板索引.json", "完整模板库索引.json"):
        for doc in read_index(samples / filename).get("templates", []):
            recorded = Path(doc["path"])
            member = doc.get("member", "")
            count = doc.get("slide_count")
            if type(count) is not int or count < 1 or Path(doc["name"]).suffix.lower() != ".pptx":
                continue
            if member:
                parts = PurePosixPath(member.replace("\\", "/"))
                if (recorded.name != ARCHIVE_NAME or parts.is_absolute() or ".." in parts.parts
                        or ":" in member or not member.lower().endswith(".pptx")
                        or not re.fullmatch(r"[a-f0-9]{64}", doc.get("sha256", ""))):
                    continue
                source = archive
            else:
                source = recorded
                # The index contains only this registered local family. Resolve a
                # moved desktop root by the known family/name, never by arbitrary path.
                if recorded.parent.name == "热潮、可爱、梗":
                    source = desktop / "热潮、可爱、梗" / recorded.name
                if not source.absolute().is_relative_to(desktop.absolute()):
                    continue
            if source.absolute() != source.resolve() or not source.is_file():
                continue
            page, cover = covers.get(doc["name"], (1, None)) if not member else (1, None)
            yield {"legacy_id": hashlib.sha256((str(recorded) + member).encode()).hexdigest()[:18],
                   "name": doc["name"], "source": source, "member": member,
                   "category": doc.get("category") or "热潮、可爱、梗", "slides": count,
                   "fingerprint": doc.get("sha256", ""), "thumbnail": doc.get("thumbnail", ""),
                   "page": page, "cover": cover}

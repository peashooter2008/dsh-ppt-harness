"""Build and render editable election openings for a single Harness task directory."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from uuid import uuid4

from PIL import Image
from pptx import Presentation
from pptx.util import Pt

from author import RECT, clause_break, image_bytes, length, shape, text
from engine import set_background
from native import PreviewSession
from native_scene import attach_motion


LABELS = {"intro": "先认识我", "story": "从一件事讲起"}
PHOTO_ROLES = {"personal": "用户自有图片", "theme": "主题配图", "generated": "生成配图"}
CREAM, FOREST, JADE = "FAF8F1", "123C35", "BAD774"
MIDNIGHT, SAND, ORANGE = "162934", "F7F3EB", "F1A570"


def field(request, key, limit, default=""):
    value = request.get(key, default)
    if not isinstance(value, str) or len(value.strip()) > limit:
        raise ValueError(f"{key} 需为 {limit} 字以内的文本。")
    value = value.strip().replace("\r\n", "\n").replace("\r", "\n")
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError(f"{key} 含有无法显示的控制字符。")
    return value


def resolve_child(root, relative):
    parts = PurePosixPath(relative).parts
    if (not parts or PurePosixPath(relative).is_absolute() or ".." in parts
            or any("\\" in p or ":" in p for p in parts)):
        raise ValueError("文件须位于当前任务目录。")
    child = root
    for part in parts:
        child = child / part
        if child.is_symlink() or (child.exists() and
                getattr(child.stat(follow_symlinks=False), "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)):
            raise ValueError("任务资源路径不可经过链接。")
    if not child.resolve().is_relative_to(root):
        raise ValueError("资源超出本任务目录。")
    return child


def read_photo(root, relative):
    if not relative:
        return None
    if not relative.startswith("assets/"):
        raise ValueError("请先将选中的图片放入本任务的 assets 文件夹。")
    source = resolve_child(root, relative)
    if not source.is_file() or source.stat().st_size > 12 * 1024 * 1024:
        raise ValueError("找不到图片，或原图超过了 12 MiB。")
    data = source.read_bytes()
    with Image.open(BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as image:
        image.verify()
    return image_bytes(data)


def place_photo(slide, photo, box, *, allow_crop=False):
    raw, width, height = photo
    x, y, w, h = box
    # Source pixels stay embedded. Only themed photographs may use a modest native center crop.
    scale = min(w / width, h / height)
    if allow_crop:
        scale = min(max(w / width, h / height), scale / .78)
    iw, ih = width * scale, height * scale
    used_w, used_h = min(iw, w), min(ih, h)
    picture = slide.shapes.add_picture(BytesIO(raw), Pt(x + (w-used_w)/2), Pt(y + (h-used_h)/2),
                                       Pt(used_w), Pt(used_h))
    picture.crop_left = picture.crop_right = max(0, (1-used_w/iw)/2)
    picture.crop_top = picture.crop_bottom = max(0, (1-used_h/ih)/2)
    picture.name = "可替换配图"


def page_text(slide, value, box, size, color, name, *, bold=False, family="Microsoft YaHei"):
    if "\n" not in value:
        value, size = clause_break(value, box, size)
    return text(slide, value, box, size, color, name=name, family=family, bold=bold,
                prefer_single_line=False)


def rule(slide, box, fill):
    return shape(slide, RECT, box, fill, "分隔线")


def intro_layout(slide, brief, photo):
    set_background(slide._element, "#" + CREAM)
    shape(slide, RECT, (548, 0, 412, 540), FOREST, "右侧底色")
    rule(slide, (46, 61, 26, 5), FOREST)
    page_text(slide, brief["role"], (46, 78, 466, 46), 21, FOREST, "竞选职位")
    headline = brief["title"] or "大家好。"
    page_text(slide, headline, (44, 150, 464, 168), 54, FOREST, "开场标题", bold=True)
    if photo:
        place_photo(slide, photo, (548, 0, 412, 540), allow_crop=brief["assetKind"] != "personal")
        if brief["statement"] and brief["statement"] != headline:
            page_text(slide, brief["statement"], (47, 321, 464, 76), 21, FOREST, "开场材料")
    else:
        quote = brief["statement"]
        if quote and quote != headline:
            page_text(slide, "“", (575, 70, 100, 100), 93, JADE, "引号", family="Georgia")
            page_text(slide, quote, (588, 156, 326, 234), 33, CREAM, "开场材料")
        else:
            # The candidate's role becomes the large second-page equivalent of a nameplate.
            page_text(slide, brief["role"], (585, 135, 335, 218), 57, CREAM, "职位题字", bold=True)
    rule(slide, (46, 428, 456, 1), "A2B5A7")
    return page_text(slide, brief["name"], (46, 435, 456, 66), 37, FOREST, "候选人姓名", bold=True)


def story_layout(slide, brief, photo):
    set_background(slide._element, "#" + MIDNIGHT)
    if photo:
        shape(slide, RECT, (479, 0, 481, 405), SAND, "右侧图片衬底")
        place_photo(slide, photo, (479, 0, 481, 405), allow_crop=brief["assetKind"] != "personal")
    width = 402 if photo else 843
    page_text(slide, brief["role"], (48, 38, width, 42), 19, SAND, "竞选职位")
    rule(slide, (48, 95, width, 1.2), "73958F")
    headline = brief["statement"] or ("你希望" + brief["role"] + "先解决哪件事？")
    size = 43 if length(headline) > 18 else 59
    page_text(slide, headline, (45, 117, width, 201), size, SAND, "故事开场", bold=True)
    title = brief["title"]
    if title and title != headline:
        page_text(slide, title, (49, 326, width, 73), 22, ORANGE, "开场标题")
    rule(slide, (49, 424, 860, 1), "73958F")
    return page_text(slide, brief["name"], (49, 440, 848, 60), 34, SAND, "候选人姓名", bold=True)


def make_opening(brief, variant, photo, name_on_click):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Pt(960), Pt(540)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    name = (intro_layout if variant == "intro" else story_layout)(slide, brief, photo)
    if name_on_click:
        attach_motion(slide, {"name": name.shape_id}, [[{"target": "name", "effect": "fadeIn",
                                                       "durationMs": 420}]])
    notes = [brief["speakerNotes"]]
    if name_on_click:
        notes.append("讲到自我介绍时，点击显示姓名。")
    if photo:
        notes.append(PHOTO_ROLES[brief["assetKind"]] + " · " + (brief["assetSource"] or Path(brief["asset"]).name))
    slide.notes_slide.notes_text_frame.text = "\n".join(filter(None, notes))
    output = BytesIO()
    prs.save(output)
    return output.getvalue(), str(name.shape_id)


def write_json(path, data):
    temporary = path.with_name(path.name + "." + uuid4().hex)
    temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def checked_click(request, default=True):
    choice = request.get("nameOnClick", default)
    if type(choice) is not bool:
        raise ValueError("nameOnClick 需为 true 或 false。")
    return choice


def prepare(request, root):
    brief = {key: field(request, key, limit) for key, limit in
             (("name", 40), ("role", 42), ("title", 75), ("statement", 115),
              ("asset", 350), ("assetSource", 600), ("speakerNotes", 3000))}
    if not brief["name"] or not brief["role"]:
        raise ValueError("请提供候选人姓名和竞选职位。")
    brief["assetKind"] = request.get("assetKind", "personal")
    if brief["assetKind"] not in PHOTO_ROLES:
        raise ValueError("请选择个人图片、主题配图或生成配图。")
    click = checked_click(request)
    photo = read_photo(root, brief["asset"])
    revision = uuid4().hex
    folder = resolve_child(root, "renders/" + revision)
    folder.mkdir(parents=True, exist_ok=False)
    relative = folder.relative_to(root).as_posix()
    results = []
    session = PreviewSession()
    try:
        for variant, label in LABELS.items():
            deck = folder / (variant + "-click.pptx")
            raw, name_id = make_opening(brief, variant, photo, True)
            deck.write_bytes(raw)
            (folder / (variant + "-static.pptx")).write_bytes(make_opening(brief, variant, photo, False)[0])
            preview = folder / (variant + ".png")
            renderer = session.export(str(deck), "both", 1, str(preview), {})
            before = folder / (variant + "-before.png")
            session.export(str(deck), "both", 1, str(before), {name_id: {"Visible": 0}})
            results.append(dict(id=variant, label=label, preview=f"{relative}/{preview.name}",
                                beforePreview=f"{relative}/{before.name if click else preview.name}",
                                deck=f"{relative}/{variant}-{'click' if click else 'static'}.pptx"))
    finally:
        session.close()
    state = {"revision": revision, "nameOnClick": click, "imageSource": brief["assetSource"],
             "imageKind": brief["assetKind"] if photo else None, "renderer": renderer,
             "imageSha256": sha256(photo[0]).hexdigest() if photo else None}
    write_json(folder / "opening.json", state)
    write_json(resolve_child(root, "latest-opening.json"), {"revision": revision})
    return {**state, "variants": results}


def export(request, root):
    variant = request.get("variant")
    if variant not in LABELS:
        raise ValueError("请选择 intro 或 story。")
    revision = request.get("revision")
    if revision is None:
        latest = resolve_child(root, "latest-opening.json")
        if not latest.is_file():
            raise ValueError("请先创建两款开场。")
        revision = json.loads(latest.read_text(encoding="utf-8"))["revision"]
    if not isinstance(revision, str) or not re.fullmatch("[0-9a-f]{32}", revision):
        raise ValueError("版本号无效，请重新选择样页。")
    prefix = "renders/" + revision
    source = resolve_child(root, prefix + "/opening.json")
    if not source.is_file():
        raise ValueError("该任务没有此版开场。")
    state = json.loads(source.read_text(encoding="utf-8"))
    click = checked_click(request, state["nameOnClick"])
    deck = f"{prefix}/{variant}-{'click' if click else 'static'}.pptx"
    preview = f"{prefix}/{variant}.png"
    before = f"{prefix}/{variant}-before.png" if click else preview
    if not all(resolve_child(root, path).is_file() for path in (deck, preview, before)):
        raise ValueError("所选版本的文件不完整，请重新生成。")
    return {"revision": revision, "variant": variant, "nameOnClick": click, "deck": deck,
            "preview": preview, "beforePreview": before}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    try:
        root = args.workdir.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("找不到任务目录。")
        payload = sys.stdin.buffer.read(64 * 1024 + 1)
        if len(payload) > 64 * 1024:
            raise ValueError("开场指令过长。")
        request = json.loads(payload.decode("utf-8-sig"))
        if not isinstance(request, dict):
            raise ValueError("请提交开场指令。")
        action = request.get("action")
        if action not in ("prepare", "export"):
            raise ValueError("未知的开场操作。")
        result = (prepare if action == "prepare" else export)(request, root)
        print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

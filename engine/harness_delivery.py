"""Inspect and render an immutable native presentation for the production panel."""
import argparse
import json
import hashlib
import posixpath
import re
from pathlib import Path
import sys
from zipfile import BadZipFile

from engine import Deck, NS, local, target
from harness_import import page_previews, require, resolve_child, slide_text_lines
from harness_storyboard import can_render_locally
from template_rights import replace_restricted_photo


def page_versions(deck):
    """Include relationships and their dependencies so a theme/media edit invalidates a preview."""
    digests, links = {}, {}
    def visit(part, seen):
        if part in seen or part not in deck.names:
            return
        seen.add(part)
        if part not in digests:
            digests[part] = hashlib.sha256(deck.zip.read(part)).digest()
        directory, leaf = posixpath.split(part)
        relfile = posixpath.join(directory, "_rels", leaf + ".rels")
        if relfile in deck.names:
            if relfile not in links:
                links[relfile] = [target(part, rel.get("Target", "")) for rel in deck.tree(relfile)
                                  if rel.get("TargetMode") != "External"]
            visit(relfile, seen)
            for child in links[relfile]:
                visit(child, seen)
    result = []
    for part, slide_id in deck.slides.items():
        seen = set()
        visit(part, seen)
        version = hashlib.sha256(f"{deck.w}x{deck.h}".encode())
        for key in sorted(seen):
            version.update(key.encode() + b"\0" + digests[key])
        content = hashlib.sha256(digests[part])
        for kind, linked in sorted(deck.rels(part).values()):
            if kind not in ("notesSlide", "slide") and linked in digests:
                content.update(kind.encode() + digests[linked])
        result.append((slide_id.get("id"), version.hexdigest(), content.hexdigest()))
    return result


def check_plan_modules(deck, policy, only=None):
    for page, part in enumerate(deck.slides, 1):
        if only is not None and page != only:
            continue
        slide = deck.tree(part)
        layout = deck.related(part, "slideLayout")
        master = deck.related(layout, "slideMaster") if layout else None
        layers = [slide] + [deck.tree(p) for p in (layout, master) if p]
        prefix = f"第 {page} 页"
        if policy.get("imagesEnabled") is False:
            require(not any(t.find(".//a:blip", NS) is not None for t in layers), prefix+"含图片，与方案的配图关闭选项冲突。")
        if policy.get("chartsEnabled") is False:
            require(not any(local(n) == "chart" for t in layers for n in t.iter()), prefix+"含原生图表，与方案的图表关闭选项冲突。")
        if policy.get("motionEnabled") is False:
            require(not any(local(n) in ("timing", "transition") for t in layers for n in t.iter()), prefix+"含原生动画或转场。请按方案关闭动效后交回。")
        if policy.get("useEmoji") is False:
            require(not any(re.search(r"[\U0001F1E6-\U0001FAFF\ufe0f]", text.text or "")
                            for t in layers for text in t.findall(".//a:t", NS)), prefix+"含 Emoji，与方案的 Emoji 关闭选项冲突。")


def sync(root, payload):
    source = resolve_child(root, payload["source"])
    require(source.suffix.lower() == ".pptx", "请交回 PPTX 文件。")
    data = source.read_bytes()
    safe_data = replace_restricted_photo(data)
    checking = payload.get("verifyPage")
    if checking is not None:
        require(safe_data is data, "这份修改使用了禁用的人物图片，请更换素材。")
    validated = safe_data
    if checking is None and any(ref.get("inherit") is True for ref in payload.get("refs", [])):
        from harness_motion_audit import inherit_delivery
        validated = inherit_delivery(safe_data, payload["refs"], root)
    if validated is not data:
        source.write_bytes(validated)
    deck = Deck(validated)
    with deck.zip:
        total = len(deck.slides)
        require(payload.get("minimum", 1) <= total <= payload.get("maximum", 30),
                f"成稿有 {total} 页，请交回已登记页数至方案总页数之间的完整快照。")
        require(can_render_locally(deck), "请先将外链媒体嵌入文件并移除活动控件，再登记成稿。")
        if payload.get("policy"):
            check_plan_modules(deck, payload["policy"], checking)
        titles = [next(slide_text_lines(deck.tree(part)), "")[:150] for part in deck.slides]
        versions = page_versions(deck)
        audits = {}
        if payload.get("refs"):
            from harness_motion_audit import audit_delivery
            audits = audit_delivery(deck, payload["refs"], root)
        if checking is not None:
            require(type(checking) is int and 1 <= checking <= total, "需核对的页码无效。")
            native_id, fingerprint, content = versions[checking-1]
            return dict(title=titles[checking-1], nativeId=native_id, fingerprint=fingerprint,
                        contentFingerprint=content, motionAudit=audits.get(checking))
    saved = {row["fingerprint"]: row for row in payload.get("previous", []) if row.get("fingerprint") and row.get("preview")}
    previews, pending = [], []
    for page, (native_id, fingerprint, content) in enumerate(versions, 1):
        old = saved.get(fingerprint, {})
        reuse = old.get("preview") and resolve_child(root, old["preview"]).is_file()
        previews.append(dict(page=page, nativeId=native_id, fingerprint=fingerprint, contentFingerprint=content, preview=old["preview"] if reuse else None))
        if not reuse:
            pending.append(page)
    if pending:
        for row in page_previews(source, resolve_child(root, "editions"), pending):
            previews[row["page"]-1].update(row)
    require(all(row.get("preview") for row in previews), "本机未能生成全部原生预览，请检查 PowerPoint 后重试。")
    for row, title in zip(previews, titles):
        row["title"] = title
        if row["page"] in audits:
            row["motionAudit"] = audits[row["page"]]
    return dict(history=previews, replacedRestrictedImage=safe_data is not data, inheritedMotion=validated is not safe_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, required=True)
    try:
        request = json.loads(sys.stdin.buffer.read(512 * 1024).decode("utf-8-sig"))
        result = sync(parser.parse_args().workdir.resolve(strict=True), request)
        print(json.dumps(dict(ok=True, **result), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, IndexError, BadZipFile) as exc:
        print(json.dumps(dict(ok=False, error=str(exc) if isinstance(exc, ValueError) else "无法读取这份成稿。"), ensure_ascii=False))
        sys.exit(1)

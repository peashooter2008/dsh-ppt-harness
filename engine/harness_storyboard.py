"""Choose and preview the actual native template frames before an outline is adopted."""
from collections import Counter, defaultdict
import hashlib
from io import BytesIO
from itertools import groupby
import re
from uuid import uuid4

from PIL import Image

from election_opening import resolve_child
from engine import Deck
from harness_page_selection import choose_frame, compatible_frames, describe_frame, requested_role
from harness_template_deck import motion_successor
from harness_templates import masters, output_folder, read_member, safe_source
from native import PreviewSession
from template_rights import replace_restricted_photo


def module_on(plan, key):
    return not re.fullmatch(r"(?:none|off|(?:关闭|不使用|不用|禁用|无)(?:配图|图片|动画|动效|图表)?)[。.!！]?",
                            str(plan.get(key, "")).strip(), flags=re.I)


CHARTS = re.compile(r"图表|柱状图?|柱形图?|条形图|折线图?|散点图?|饼图|chart", re.I)
DIAGRAMS = re.compile(r"流程图?|架构|组织图|机制图|步骤|时间轴|diagram|workflow", re.I)
IMAGES = re.compile(r"配图|照片|摄影|图片|图像|特写|photo|image", re.I)
COMPARISONS = re.compile(r"对照|比较|对比|并列|两组|双栏|compare", re.I)
NEGATED = re.compile(r"(?:不要|不用|不必|无需|避免|取消|禁用|关闭|省略|去掉|不再|不应|不需要|不使用|不放|不做|不加|不画|不展示|不采用|别|without\s+|no\s+)"
                     r"(?:再|采用|使用|添加|绘制|插入|放|保留|展示|出现|任何|原有的?|单独|做|画|加|用|\s)*$", re.I)
LIST_PREFIX = re.compile(r"(?:(?:" + "|".join(p.pattern for p in (CHARTS, DIAGRAMS, IMAGES)) + r")\s*(?:和|或|及|、)\s*)+$",re.I)
STATISTICS = re.compile(r"趋势|均值|平均数|占比|增长率|(?:数据|数值)(?:比较|对比)|(?:比较|对比)(?:数据|数值)|两组数据|trend", re.I)
QUANTITY = re.compile(r"\d+(?:\.\d+)?\s*(人|分钟|秒|元|件|次|[%％])")


def visual_request(line, pattern):
    # A later instruction can replace an earlier choice, e.g. 不用柱状图，改用折线图.
    result = None
    for match in pattern.finditer(line):
        prefix = LIST_PREFIX.sub("",line[:match.start()])
        suffix = line[match.end():].lstrip()
        result = not (NEGATED.search(prefix) or re.match(r"(?:就)?(?:不用|不要|关闭|禁用|省略)", suffix))
    return result


def numeric_comparison(line):
    if visual_request(line, STATISTICS):
        return True
    if not re.search(r"分别|相比|对比|比较|对照|(?:从|由)\s*\d|降至|增至|变成|上升|下降|减少|增加", line):
        return False
    return any(n >= 2 for n in Counter(QUANTITY.findall(line)).values())


def outline_spec(line, plan):
    spec = {"title": line, "body": [line]}
    chart = visual_request(line, CHARTS)
    if module_on(plan, "charts") and (chart if chart is not None else numeric_comparison(line)):
        spec["chart"] = True
    elif visual_request(line, DIAGRAMS):
        spec["diagram"] = True
    elif module_on(plan, "images") and visual_request(line, IMAGES):
        spec["image"] = {"role": "figure"}
    elif visual_request(line, COMPARISONS):
        spec["layout"] = "compare"
    return spec


def motion_choices(rows, pairs, eligible, plan):
    """Keep verified runs together and prefer a different entire run on reselection."""
    choices = {}
    if not pairs:
        return choices
    for _, grouped in groupby(enumerate(rows), key=lambda item: item[1]["page"]-item[0]):
        run = [row for _, row in grouped]
        # Within a requested replacement span, its own action can change even
        # if the incoming or outgoing original transition no longer matches.
        spans = [list(g) for avoided,g in groupby(run, key=lambda r: bool(r.get("avoidPage"))) if avoided]
        segments = [run, *(span for span in spans if 2 <= len(span) < len(run))]
        for group in segments:
            choices.update(continuous_choices(group, pairs, eligible, plan))
    return choices


def continuous_choices(group, pairs, eligible, plan):
    choices = {}
    intent = " ".join([str(plan.get("animation", "")), *(plan["outline"][r["page"]-1] for r in group)])
    if len(group) > 2 and not re.search(r"轮盘|平滑|连播|连续(?:动作|播放|切换)|morph", intent, re.I):
        return choices
    start = 0
    while start + 1 < len(group):
        sequences = [[number] for number in eligible[group[start]["page"]]]
        end = start+1
        while end < len(group):
            allowed = eligible[group[end]["page"]]
            extended = [seq+[pairs[seq[-1]]] for seq in sequences if pairs.get(seq[-1]) in allowed]
            if not extended:
                break
            sequences = extended
            end += 1
        if end > start+1:
            span = group[start:end]
            def changes(seq):
                return sum(row.get("avoidPage") is not None and n != row["avoidPage"]
                           for row,n in zip(span,seq))
            most = max(map(changes, sequences))
            best = [seq for seq in sequences if changes(seq) == most]
            for j, row in enumerate(span):
                choices[row["page"]] = ({seq[j] for seq in best}, j > 0)
        start = end
    return choices


def choose_pages(deck, plan, rows):
    parts = list(deck.slides)
    visible = [describe_frame(deck, part, i) for i, part in enumerate(parts, 1)
               if deck.tree(part).get("show") not in ("0", "false")]
    if not visible:
        raise ValueError("模板所有页面均标记为隐藏，未找到可用讲述页。")
    by_number = {f.number: f for f in visible}
    preserve = module_on(plan, "animation") and plan.get("templateMotion", "keep") != "replace"
    # Precompute pairs once. Morph lives on the destination slide in the OOXML file.
    pairs = ({left.number: right.number for left, right in zip(visible, visible[1:])
              if motion_successor(deck, left.part, {right.part}) == right.part} if preserve else {})
    eligible, specs = {}, {}
    count = plan["pageCount"]
    for row in rows:
        page = row["page"]
        spec = specs[page] = outline_spec(plan["outline"][page-1], plan)
        role = requested_role(spec, page, count)
        fitting = compatible_frames(visible, role) or visible
        if role == "数据比较":
            fitting = [f for f in fitting if f.charts == 1] or fitting
        eligible[page] = {row["sourcePage"]} if row.get("sourcePage") else {f.number for f in fitting}
    runs = motion_choices(rows, pairs, eligible, plan)
    uses, results = Counter(), []
    run_length = 1
    for row in rows:
        page, source = row["page"], row["templateId"]
        previous = results[-1] if results and results[-1]["page"] == page-1 else None
        prior = by_number.get(previous["sourcePage"]) if previous else None
        successor = by_number.get(pairs.get(prior.number)) if prior else None
        fixed, avoid = row.get("sourcePage"), row.get("avoidPage")
        if fixed is not None:
            if fixed not in range(1, len(parts)+1):
                raise ValueError(f"第 {page} 页指定的模板原页已不存在。")
            choice = by_number.get(fixed) or describe_frame(deck, parts[fixed-1], fixed)
            reason = "保留已指定的原页"
        else:
            numbers, continues = runs.get(page, (eligible[page], False))
            candidates = [f for f in visible if f.number in numbers]
            alternates = [f for f in candidates if f.number != avoid]
            if alternates and page not in runs:
                candidates = alternates
            if continues and successor in candidates:
                choice, reason = successor, "接续上一张原页的平滑切换"
            else:
                choice, reason = choose_frame(visible, specs[page], page, count, uses,
                                              prior.part if prior else None, successor.part if successor else None,
                                              run_length if prior else 1, candidates=candidates)
            if avoid == choice.number:
                reason += "；保留这张原页以接续原动作" if page in runs else "；本模板仅此页适合当前内容"
        item = {"page": page, "templateId": source, "sourcePage": choice.number, "reason": reason}
        if successor and choice.number == successor.number:
            item["motionFrom"] = page-1
            run_length += 1
        else:
            run_length = 1
        results.append(item)
        uses[choice.part] += 1
    return results


def preview_pages(data, digest, original, workdir, rows):
    folder = output_folder(workdir)
    renderer = PreviewSession()
    try:
        for page in sorted({row["sourcePage"] for row in rows}):
            rel = f"templates/board-{digest}-p{page}.jpg"
            target = resolve_child(workdir, rel)
            try:
                if not target.is_file():
                    if original is None:
                        original = resolve_child(workdir, f"templates/board-{digest}.pptx")
                        if not original.exists():
                            pending = folder / (uuid4().hex + ".partial")
                            pending.write_bytes(data)
                            pending.replace(original)
                    pending = folder / (uuid4().hex + ".png")
                    renderer.export(str(original), "both", page, str(pending), {})
                    with Image.open(pending) as img:
                        img.thumbnail((720, 480), Image.Resampling.LANCZOS)
                        encoded = BytesIO()
                        img.convert("RGB").save(encoded, format="JPEG", quality=84)
                    pending.write_bytes(encoded.getvalue())
                    pending.replace(target)
                detail = {"preview": rel}
            except Exception:
                detail = {"previewError": "本机暂时无法渲染这张原页。"}
            for row in rows:
                if row["sourcePage"] == page:
                    row.update(detail)
    finally:
        renderer.close()


def can_render_locally(deck):
    if deck.h/deck.w > 16:
        return False
    for name in deck.names:
        if name.startswith("ppt/activeX/") or name.lower().endswith("/vbaproject.bin"):
            return False
        if name.endswith(".rels"):
            for link in deck.tree(name):
                if link.get("TargetMode", "").lower() == "external" and not link.get("Type", "").endswith("/hyperlink"):
                    return False
    return True


def storyboard(payload, workdir):
    plan, pages, sources = (payload.get(k) for k in ("plan", "pages", "sources"))
    if (not isinstance(plan, dict) or not isinstance(pages, list) or not 1 <= len(pages) <= 30
            or len(pages) != plan.get("pageCount") or not isinstance(plan.get("outline"), list)
            or len(plan["outline"]) != len(pages) or not all(isinstance(s, str) for s in plan["outline"])
            or not isinstance(sources, list) or len(sources) > len(pages)):
        raise ValueError("选页清单与方案页数不一致。")
    library = {item.id: item for item in masters()}
    assigned = defaultdict(list)
    results = []
    for i, row in enumerate(pages, 1):
        if (not isinstance(row, dict) or type(row.get("page")) is not int or row["page"] != i
                or not isinstance(row.get("templateId"), str) or any(
                    row.get(k) is not None and (type(row[k]) is not int or row[k] < 1)
                    for k in ("sourcePage", "avoidPage"))):
            raise ValueError("选页清单中的成稿页码或模板页码无效。")
        if row["templateId"]:
            assigned[row["templateId"]].append(row)
        else:
            results.append({"page": i, "templateId": "", "sourcePage": None, "reason": "本页按提纲自行设计"})
    if any(not isinstance(s, dict) or not isinstance(s.get("id"), str) for s in sources):
        raise ValueError("请使用当前任务中选定的模板。")
    if len(sources) != len(assigned) or {s["id"] for s in sources} != set(assigned):
        raise ValueError("选页清单与本次使用的模板不一致。")
    for source in sources:
        original = None
        if "asset" in source:
            if not isinstance(source["asset"], str) or not re.fullmatch(r"assets/(?:[a-f0-9]{64}|[a-f0-9-]{36})\.pptx", source["asset"]):
                raise ValueError("模板须来自本任务的素材目录。")
            original = resolve_child(workdir, source["asset"])
        else:
            master = library.get(source["id"])
            if not master or not safe_source(master.source):
                raise ValueError("所选模板当前不可用，请刷新模板库。")
            if master.member:
                data = read_member(master)
            else:
                original = master.source
        if original is not None:
            if not original.is_file() or not 0 < original.stat().st_size <= 256*1024*1024:
                raise ValueError("请选择 256 MiB 以内的 PPTX。")
            data = original.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if any(row.get("motionSource", digest) != digest for row in assigned[source["id"]]):
            raise ValueError("模板原稿与选中放映片段的版本不同，请更新选页或重新选择模板。")
        cleaned = replace_restricted_photo(data)
        if cleaned is not data:
            original = None
        deck = Deck(cleaned)
        with deck.zip:
            selected = choose_pages(deck, plan, assigned[source["id"]])
            if can_render_locally(deck):
                preview_pages(cleaned, digest, original, workdir, selected)
            else:
                for row in selected:
                    row["previewError"] = "这份原稿的画幅或关联部件不支持本机缩略图。"
        results.extend(selected)
    return {"pages": sorted(results, key=lambda row: row["page"])}

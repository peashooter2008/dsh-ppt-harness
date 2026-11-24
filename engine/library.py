import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
from zipfile import ZipFile
from template_registry import indexed_templates, supplementary_templates

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT.parent / "PPT创作样例"
STYLES = ["简约", "科技", "中国风", "抽象", "热梗"]
BUILTIN = {"dream": ("笛卡尔 · 三页论证练习", "简约", "笛卡尔-论证节奏.pptx", "逐页预览/01.png"),
           "message": ("同一条群消息", "热梗", "同一条群消息-热潮模板改编.pptx", "同一条群消息-热潮模板改编.png")}


def class_election_source():
    filename = "竞选学习委员.pptx"
    archived = ROOT / "精选库" / "竞选样页" / filename
    desktop = Path(os.environ.get("DIEYE_TEMPLATE_DESKTOP", str(Path.home() / "OneDrive" / "Desktop"))) / "ppt模板"
    for file in (archived, desktop / filename, desktop / "竞选学习委员-有脑子皮皮踢.pptx"):
        if file.resolve() == file.absolute() and file.is_file():
            return file
    return None


def style_for(category):
    if category == "中国风":
        return "中国风"
    if category in ("抽象艺术", "高级晕染PPT", "个性活力"):
        return "抽象"
    if category == "热潮、可爱、梗":
        return "热梗"
    return "简约"


class Library:
    def __init__(self):
        self.items = {}
        self.sources = {}
        self.covers = {}
        self.warnings = []
        self.curated = []
        self.native_assets = {}
        final = ROOT / "标杆样片"
        if (final / "Descartes_English_Animated.pptx").is_file():
            self.add("dream-final", "笛卡尔：我们如何确定自己醒着？", "成品标杆", 14,
                     (final / "Descartes_English_Animated.pptx",""), final / "第02页.png")
            self.items["dream-final"].update(page=2,style="抽象",visualStyle="高饱和复古拼贴",ref="Descartes_English_Animated.pptx",
                reason="用一幅床与云的拼贴引出梦境怀疑，再让听众判断感受能否作证。",
                avoid="严肃数据汇报可借提问节奏。肖像、拼贴和哲学例句只服务这个主题。",
                rules="同一套色彩中轮换三种讲法：第2页图像提问，第4页三句话逐次推出结论，第13页留时间给听众作答。保留这种节奏，用新主题自己的图像。",
                reuseTemplateImage=False,download="/api/reference/dream-final/source.pptx",
                motionUrl="/api/reference/dream-final/motion.mp4",motionLabel="第 3 → 4 页 · 全面怀疑到我思",
                motionPptx="/api/reference/dream-final/sequence.pptx",
                examples=[{"page":page,"label":label,"image":f"/api/reference/dream-final/{page}.png"}
                          for page,label in ((2,"让听众起疑"),(4,"逐句推出结论"),(7,"并排辨析概念"),(13,"给听众作答时间"))])
            for example in self.items["dream-final"]["examples"]:
                example["reason"]=self.reference_meta("dream-final",example["page"])["reason"]
        for key, (name, style, source, cover) in BUILTIN.items():
            if (SAMPLES / source).is_file():
                self.add(key, name, style, 3 if key == "dream" else 1, (SAMPLES/source, ""), SAMPLES/cover)
        for key, style in (("original-tech","科技"),("original-ink","中国风"),("original-abstract","抽象"),("original-minimal","简约")):
            folder = ROOT / "交付样例"
            actual = folder / (style + "-校园通知.pptx")
            cover = folder / (style + "-同页预览.png")
            self.add(key, style + " · 原生演示", style, 3,
                     (actual,"") if actual.is_file() else None, cover if cover.is_file() else None)
        self.load_native_references()
        self.load_class_election()
        for filename in ("热潮模板索引.json","完整模板库索引.json"):
            if not (SAMPLES / filename).is_file():
                self.warnings.append(f"未找到{filename}")
        for doc in indexed_templates(samples=SAMPLES):
            self.add(doc["legacy_id"], Path(doc["name"]).stem, doc["category"],
                     doc["slides"], (doc["source"], doc["member"]), doc["thumbnail"] or doc["cover"])
        for doc in supplementary_templates():
            self.add(doc["id"], doc["title"], doc["category"], doc["slides"],
                     (doc["source"], ""), doc["pages"][0]["cover"])
            self.items[doc["id"]].update(style=doc["style"], reason=doc["summary"],
                                         fingerprint=doc["fingerprint"], recommended=doc["recommended"])
            if doc["recommended"]:
                self.curated.append(doc["id"])
        self.catalog_ids=tuple(self.items)
        self.load_curated()

    def load_native_references(self):
        folder=ROOT/"精选库"/"用户原稿"
        manifest=folder/"manifest.json"
        if not manifest.is_file():
            return
        for row in json.loads(manifest.read_text(encoding="utf-8-sig"))["items"]:
            key=row["id"]
            directory=(folder/key).resolve()
            if directory.parent!=folder.resolve() or key in self.items:
                raise ValueError("用户参考模板编号无效。")
            working=row.get("working","source.pptx")
            names={"source.pptx",working,"sequence.pptx"}
            if (directory/"sequence.mp4").is_file():
                names.add("sequence.mp4")
            base=f"/api/reference/{key}/"
            examples=[]
            for page in row["pages"]:
                n=page["page"]
                names.update((f"page-{n}.jpg",f"page-{n}.pptx"))
                examples.append({**page,"image":base+f"page-{n}.jpg","download":base+f"page-{n}.pptx"})
            assets={name:(directory/name).resolve() for name in names}
            if not examples or any(path.parent!=directory or not path.is_file() for path in assets.values()):
                self.warnings.append("用户样片缺少文件："+row["title"])
                continue
            first=examples[0]
            self.native_assets[key]=assets
            self.add(key,row["title"],row["category"],row["slides"],(assets[working],""),assets[f"page-{first['page']}.jpg"])
            self.items[key].update({k:row[k] for k in ("style","visualStyle","keywords","rules","avoid","motionLabel")})
            self.items[key].update(nativeSample=True,reuseTemplateImage=False,ref=row["filename"],
                                   page=first["page"],reason=first["reason"],examples=examples,
                                   download=base+"source.pptx",motionPptx=base+"sequence.pptx",copyNote=row.get("copyNote",""))
            if "sequence.mp4" in assets:
                self.items[key]["motionUrl"]=base+"sequence.mp4"

    def reference_asset(self,key,name):
        asset=self.native_assets.get(key,{}).get(name)
        if asset is None:
            raise FileNotFoundError("未找到该参考附件。")
        return asset

    def load_class_election(self):
        source = class_election_source()
        if not source:
            return
        key = "class-election"
        base = f"/api/reference/{key}/"
        folder = ROOT / "精选库" / "竞选样页"
        assets = {"source.pptx": source}
        examples = []
        for n, label, reason in (
            (4, "个人介绍", "用同学会记得的细节介绍自己，把距离拉近。"),
            (13, "当选承诺", "把承诺说成具体行动，让大家知道当选后能找你做什么。"),
        ):
            file = folder / f"学委-{n:02d}.jpg"
            if file.is_file() and file.resolve() == file.absolute():
                asset = f"page-{n}.jpg"
                assets[asset] = file
                examples.append(dict(page=n, label=label, reason=reason, image=base + asset))
        if not examples:
            return
        first = examples[0]
        self.native_assets[key] = assets
        self.add(key, "竞选学习委员", "学生竞选", 20, (source, ""), assets[f"page-{first['page']}.jpg"])
        self.items[key].update(nativeSample=True, reuseTemplateImage=False, ref="竞选学习委员.pptx",
                               style="校园竞选", visualStyle="校园竞选", keywords="学习委员竞选 班干部竞选",
                               page=first["page"], reason=first["reason"], examples=examples,
                               rules="先让听众认识候选人，再说明能为同学做什么。",
                               avoid="姓名、个人经历、照片和承诺应换成候选人的真实材料。",
                               download=base+"source.pptx")

    def load_curated(self):
        folder=ROOT/"精选库"
        manifest=folder/"manifest.json"
        if not manifest.is_file():
            self.warnings.append("逐页精选清单尚未载入")
            return
        rows=json.loads(manifest.read_text(encoding="utf-8-sig"))["items"]
        for row in rows:
            source=self.items.get(row["sourceId"])
            cover=(folder/row["preview"]).resolve()
            page=row["page"]
            key=row["id"]
            if (not source or key in self.items or not isinstance(page,int) or not 1<=page<=source["slides"]
                or not cover.is_relative_to(folder.resolve()) or not cover.is_file()):
                self.warnings.append("无法载入精选页："+row["title"])
                continue
            self.add(key,row["title"],row["category"],source["slides"],self.sources[source["id"]],cover)
            self.items[key].update(style=row["style"] if row["style"] in STYLES else source["style"],
                                   ref=source["title"],sourceId=source["id"],page=page,
                                   reason=row["reason"],avoid=row["avoid"],reuseTemplateImage=False)
            self.curated.append(key)

    def featured(self):
        return [self.items[k] for k in ["dream-final",*self.native_assets,*self.curated] if k in self.items]

    def add(self, key, name, category, count, source, cover):
        self.items[key] = dict(id=key,title=name,category=category,slides=count,
                               image=f"/api/cover/{key}" if cover or source is None else "",
                               style=category if category in STYLES else style_for(category))
        self.sources[key], self.covers[key] = source, cover

    def search(self, q, category, offset, limit, collection="all"):
        if collection not in ("all","curated"):
            raise ValueError("请选择逐页精选或全部模板")
        rows = self.featured() if collection=="curated" else [self.items[k] for k in self.catalog_ids]
        families = {"热梗":{"热潮、可爱、梗"},"简约":{"极简系列","简约风","简约系列"},"抽象":{"抽象艺术","高级晕染PPT"}}
        result = [v for v in rows if (not category or category == v["category"] or
                  ((collection=="curated" or v.get("nativeSample")) and category==v["style"]) or v["category"] in families.get(category,())) and
                  all(t in " ".join(v.get(k,"") for k in ("title","category","reason","ref","style","keywords","visualStyle")).lower() for t in q.lower().split())]
        return dict(items=result[offset:offset+limit],total=len(result),
                    categories=list(dict.fromkeys(v["category"] for v in rows)) if collection=="curated" else list(dict.fromkeys(STYLES+[v["category"] for v in rows])))

    def data(self, key):
        item = self.sources[key]
        if item is None:
            return None
        path, member = item
        if member:
            with ZipFile(path) as z:
                return z.read(member)
        data = path.read_bytes()
        expected = self.items[key].get("fingerprint")
        if expected and hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("本地补充模板与已登记版本不一致，请重新核对原稿。")
        return data

    def reference_meta(self, key, page=None):
        item=self.items[key]
        if page is None:
            return item
        if type(page)!=int:
            raise ValueError("参考页码应为整数")
        if key in self.native_assets:
            for example in item["examples"]:
                if example["page"]==page:
                    return {**item,"page":page,"reason":example["reason"],"image":example["image"]}
            raise ValueError("请选择样片中已收录的参考页。")
        if key=="dream-final":
            reading={
                2:("让听众起疑",item["reason"]),
                4:("逐句推出结论","先出现 I DOUBT.，再出现 I THINK. 与 I EXIST.；每次点击只向前推理一步。"),
                7:("并排辨析概念","让 MIND 和 BODY 处于同一高度，分别揭示定义，再在底部给出二者关系。"),
                13:("给听众作答时间","只留一个能当场回答的问题，备注安排先停顿、等听众回应再点击。")}
            if page not in reading:
                raise ValueError("请选择该终稿已看样的第 2、4、7 或 13 页")
            return {**item,"page":page,"reason":reading[page][1],"image":f"/api/reference/dream-final/{page}.png"}
        if item.get("page")!=page:
            raise ValueError("该模板没有这个页码的已审参考图")
        return item

    def reference_cover(self,key,page=None):
        item=self.reference_meta(key,page)
        if key in self.native_assets:
            return self.reference_asset(key,f"page-{item['page']}.jpg").read_bytes(),"image/jpeg"
        if key=="dream-final":
            return (ROOT/"标杆样片"/f"第{item['page']:02d}页.png").read_bytes(),"image/png"
        return self.cover(key)

    def reference_data(self, key, page=None):
        page=self.reference_meta(key,page).get("page")
        if f"page-{page}.pptx" in self.native_assets.get(key, {}):
            return self.reference_asset(key,f"page-{page}.pptx").read_bytes()
        data=self.data(key)
        if page is None or data is None:
            return data
        from engine import Deck,apply_edits
        deck=Deck(data)
        with deck.zip:
            part=list(deck.slides)[page-1]
        return apply_edits(data,{"order":[part],"slides":{}})

    def cover(self, key):
        cover = self.covers[key]
        if isinstance(cover,Path) and cover.exists():
            return cover.read_bytes(),mimetypes.guess_type(cover.name)[0] or "image/png"
        if isinstance(cover,str) and cover.startswith("data:image/"):
            header,data=cover.split(",",1)
            return base64.b64decode(data),header[5:].split(";")[0]
        raise FileNotFoundError("此模板只有结构索引")

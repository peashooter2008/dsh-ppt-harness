"""Find attributable slide photos and import a selected Commons file into one task."""

import hashlib
import json
import os
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request
from uuid import uuid4

from PIL import Image


API = "https://commons.wikimedia.org/w/api.php"
HOSTS = {"commons.wikimedia.org", "upload.wikimedia.org", "thumb.wikimedia.org"}
MAX_IMAGE = 12 * 1024 * 1024
AGENT = "DieyeSlideStudio/0.1 (local presentation authoring; Wikimedia Commons photo search)"


def trusted(url):
    parts = urlsplit(url)
    return (parts.scheme == "https" and parts.hostname in HOSTS and parts.port in (None, 443)
            and not parts.username and not parts.password)


class CommonsRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not trusted(newurl):
            raise ValueError("素材来源跳转到其他网站，请重新选图。")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read_url(url, limit):
    if not trusted(url):
        raise ValueError("只能读取 Commons 作品及其缩略图。")
    request = Request(url, headers={"User-Agent": AGENT})
    for attempt in range(2):
        try:
            with build_opener(CommonsRedirect()).open(request, timeout=12) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError("素材超过本次导入大小限制，请选另一张。")
            return data
        except (URLError, TimeoutError, ConnectionError) as error:
            if (isinstance(error, HTTPError) and error.code < 500) or attempt:
                raise ValueError("暂时无法从 Commons 取回素材，可稍后重试或选用自己的图片。") from error
            time.sleep(0.3)


class LabelText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pieces = []

    def handle_data(self, data):
        self.pieces.append(data)


def field(metadata, name):
    parser = LabelText()
    parser.feed(metadata.get(name, {}).get("value", ""))
    return " ".join(" ".join(parser.pieces).split())[:360]


def lookup(params):
    request = {"action": "query", "format": "json", "formatversion": 2, "prop": "imageinfo",
               "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1280,
               "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl|Credit", **params}
    data = json.loads(read_url(API + "?" + urlencode(request), 2_000_000))
    if data.get("error"):
        raise ValueError("图库暂未接受此次查询，请换一个关键词。")
    photos = []
    for page in sorted(data.get("query", {}).get("pages", []), key=lambda p: p.get("index", 0)):
        info = next(iter(page.get("imageinfo", [])), {})
        image_url = info.get("thumburl") or info.get("url", "")
        if info.get("mime") not in ("image/jpeg", "image/png") or not trusted(image_url):
            continue
        metadata = info.get("extmetadata", {})
        license_name = field(metadata, "LicenseShortName")
        if not license_name:
            continue
        page_id = page["pageid"]
        photos.append({"id": f"commons:{page_id}", "title": page["title"].removeprefix("File:"),
                       "source": f"https://commons.wikimedia.org/?curid={page_id}",
                       "thumbnail": image_url, "author": field(metadata, "Artist") or field(metadata, "Credit"),
                       "license": license_name, "licenseUrl": field(metadata, "LicenseUrl"),
                       "width": info["width"], "height": info["height"]})
    return photos


def search(spec):
    query = spec.get("query", "")
    if not isinstance(query, str) or not (1 <= len(query.strip()) <= 160):
        raise ValueError("请输入 1–160 字的搜图关键词。")
    limit = max(1, min(8, int(spec.get("limit", 4))))
    photos = lookup({"generator": "search", "gsrsearch": "filetype:bitmap " + query.strip(),
                     "gsrnamespace": 6, "gsrlimit": min(24, limit * 2)})
    return {"provider": "Wikimedia Commons", "query": query.strip(), "photos": photos[:limit]}


def download(spec):
    match = re.fullmatch(r"commons:([1-9][0-9]{0,12})", spec.get("id", ""))
    if not match:
        raise ValueError("请从搜索结果选择一张图片。")
    task = Path(spec["directory"]).resolve(strict=True)
    assets = task / "assets"
    if assets.resolve().parent != task:
        raise ValueError("任务素材目录无效。")
    photos = lookup({"pageids": match.group(1)})
    if not photos:
        raise ValueError("这张图已不可用，请重新选择。")
    photo = photos[0]
    data = read_url(photo["thumbnail"], MAX_IMAGE)
    with Image.open(BytesIO(data), formats=["JPEG", "PNG"]) as im:
        if im.width * im.height > 35_000_000:
            raise ValueError("这张图过大，请重新选择。")
        extension = "png" if im.format == "PNG" else "jpg"
        im.verify()
    digest = hashlib.sha256(data).hexdigest()[:16]
    filename = f"commons-{match.group(1)}-{digest}.{extension}"
    assets.mkdir(exist_ok=True)
    destination = assets / filename
    if destination.is_symlink() or destination.resolve().parent != assets:
        raise ValueError("任务内图片文件路径无效。")
    if not destination.exists() or hashlib.sha256(destination.read_bytes()).digest() != hashlib.sha256(data).digest():
        staged = assets / (uuid4().hex + ".part")
        with staged.open("xb") as f:
            f.write(data)
        os.replace(staged, destination)
    attribution = " · ".join(filter(None, (photo["title"][:180], photo["author"][:220],
                                          photo["license"][:80], photo["source"])))
    return {"asset": "assets/" + filename, "assetKind": "theme", "assetSource": attribution, "photo": photo}


if __name__ == "__main__":
    try:
        spec = json.load(sys.stdin)
        action = spec.get("action")
        if action not in ("search", "download"):
            raise ValueError("未知的图片操作。")
        print(json.dumps({"ok": True, **(search(spec) if action == "search" else download(spec))}, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        sys.exit(1)

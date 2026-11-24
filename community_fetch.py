"""Read a single anonymous resource from the configured template service using OS proxy settings."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def receive(request):
    url = request["url"]
    u = urlsplit(url)
    configured = urlsplit(os.environ.get("DIEYE_COMMUNITY_URL") or "https://ppt-template-studio.netlify.app")
    match = re.fullmatch(r"/api/templates/[a-f0-9]{24}/(info|deck)", u.path)
    local = u.scheme == "http" and u.hostname == "127.0.0.1"
    # Compare parsed ports to handle default ports consistently with the Node URL parser.
    port = lambda v: v.port or (443 if v.scheme == "https" else 80)
    if not match or not (local or u.scheme == "https") or u.query or u.fragment or u.username or u.password or (
        u.scheme,u.hostname,port(u)) != (configured.scheme,configured.hostname,port(configured)):
        raise ValueError("共享模板地址无效。")
    handler = build_opener(ProxyHandler({}) if local else ProxyHandler(),NoRedirect())
    with handler.open(Request(url,headers={"User-Agent":"PPT-Template-Studio/0.10"}),timeout=50) as response:
        if response.status != 200:
            raise ValueError("站点暂时不可用，或版本已撤回、未获授权。")
        if match[1] == "info":
            data = response.read(8193)
            if not 0 < len(data) <= 8192:
                raise ValueError("站点元数据超出处理范围。")
            return {"info": json.loads(data)}
        target = Path(request["target"])
        expected = request["digest"]
        limit = 256 * 1024 * 1024
        advertised = response.headers.get("Content-Length")
        size = request.get("bytes")
        if (not re.fullmatch(r"[a-f0-9]{64}", expected) or not target.is_absolute() or
            target.parent.name != "assets" or target.parent.resolve(strict=True) != target.parent or
            not re.fullmatch(r"[0-9a-f-]{36}\.pptx", target.name) or target.exists() or
            (size is not None and (type(size) is not int or not 4 <= size <= limit)) or
            (advertised is not None and not 4 <= int(advertised) <= limit)):
            raise ValueError("模板大小或接收位置无效。")
        digest = hashlib.sha256()
        received = 0
        pending = None
        try:
            with NamedTemporaryFile(dir=target.parent, suffix=".partial", delete=False) as stream:
                pending = Path(stream.name)
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    if received == 0 and not block.startswith(b"PK\x03\x04"):
                        raise ValueError("共享站返回的文件不是 PPTX。")
                    received += len(block)
                    if received > limit or size is not None and received > size:
                        raise ValueError("模板下载超过声明的大小。")
                    digest.update(block)
                    stream.write(block)
            if (received < 4 or size is not None and received != size or
                advertised is not None and received != int(advertised) or digest.hexdigest() != expected):
                raise ValueError("模板下载校验失败，请重新选取。")
            os.replace(pending, target)
            pending = None
            return {"bytes": received}
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)


if __name__=="__main__":
    try:
        print(json.dumps({"ok":True,**receive(json.load(sys.stdin))}))
    except (HTTPError,OSError,ValueError,KeyError) as error:
        message = str(error) if type(error) is ValueError and str(error).endswith("。") else "站点暂时不可用，或版本已撤回、未获授权。"
        print(json.dumps({"ok":False,"error":message},ensure_ascii=False))
        sys.exit(1)

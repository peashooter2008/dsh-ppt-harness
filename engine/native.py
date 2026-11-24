"""Open an editable handoff or export slides from an isolated read-only copy."""
import argparse
import json
from pathlib import Path
import sys


def application(progid):
    import pythoncom
    import pywintypes
    from win32com.client import dynamic
    # An already-running WPS instance may advertise PowerPoint's active object.
    # Activate the requested COM class directly, including for editable handoffs.
    dispatch=pythoncom.CoCreateInstance(pywintypes.IID(progid),None,pythoncom.CLSCTX_LOCAL_SERVER,
                                        pythoncom.IID_IDispatch)
    return dynamic.Dispatch(dispatch)


class PreviewSession:
    def __init__(self):
        self.app=self.deck=self.key=None
        self.engine=None

    def close(self):
        if self.deck is not None:
            try:
                self.deck.Saved=-1
                self.deck.Close()
            finally:
                self.app=self.deck=self.key=None
                self.engine=None

    def export(self,source,target,page,output,changes):
        ids={"wps":"KWPP.Application","powerpoint":"PowerPoint.Application"}
        candidates=[target] if target in ids else list(reversed(ids))
        if self.key!=(source,target):
            self.close()
        for name in candidates:
            try:
                if self.deck is None:
                    self.app=application(ids[name])
                    self.deck=self.app.Presentations.Open(source,-1,-1,0)
                    self.key=(source,target)
                    self.engine={"progId":ids[name],"name":str(self.app.Name),"version":str(self.app.Version)}
                slide=self.deck.Slides.Item(page)
                states=[]
                if changes:
                    wanted=set(changes)
                    def apply_frame(shapes):
                        for i in range(1,shapes.Count+1):
                            shape=shapes.Item(i)
                            sid=str(shape.Id)
                            if sid in wanted:
                                values=changes[sid]
                                previous={k:getattr(shape,k) for k in values}
                                aspect=shape.LockAspectRatio if "Width" in values else None
                                states.append((shape,previous,aspect))
                                if aspect is not None:
                                    shape.LockAspectRatio=0
                                for field,value in values.items():
                                    setattr(shape,field,value)
                                wanted.remove(sid)
                            if wanted and shape.Type==6:
                                apply_frame(shape.GroupItems)
                            if not wanted:
                                break
                    apply_frame(slide.Shapes)
                    if wanted:
                        raise ValueError("原生预览对象与文稿不符")
                try:
                    ratio=self.deck.PageSetup.SlideHeight/self.deck.PageSetup.SlideWidth
                    slide.Export(output,"PNG",1160,max(1,round(1160*ratio)))
                finally:
                    for shape,previous,aspect in states:
                        for field,value in previous.items():
                            setattr(shape,field,value)
                        if aspect is not None:
                            shape.LockAspectRatio=aspect
                return self.engine
            except Exception:
                self.close()
                if name==candidates[-1]:
                    raise


def worker():
    session=PreviewSession()
    try:
        for line in sys.stdin:
            try:
                engine=session.export(**json.loads(line))
                print(json.dumps({"ok":True,"engine":engine}),flush=True)
            except Exception:
                print('{"ok":false}',flush=True)
    finally:
        session.close()


def run(mode, target, file, page, output):
    ids = {"wps":"KWPP.Application","powerpoint":"PowerPoint.Application"}
    candidates = [target] if target in ids else ["powerpoint","wps"]
    for name in candidates:
        try:
            app = application(ids[name])
            if mode == "open":
                app.Visible = True
                app.Presentations.Open(str(file), 0, 0, -1)
                return
            deck = app.Presentations.Open(str(file), -1, -1, 0)
            try:
                ratio = deck.PageSetup.SlideHeight / deck.PageSetup.SlideWidth
                deck.Slides.Item(page).Export(str(output),"PNG",1160,max(1,round(1160*ratio)))
            finally:
                deck.Saved = -1
                deck.Close()
            return
        except Exception:
            if name == candidates[-1]:
                raise RuntimeError("该演示软件无法完成操作，请使用结构视图或导出 PPTX。") from None


if __name__ == "__main__":
    if sys.argv[1:]==["worker"]:
        worker()
        sys.exit(0)
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=["open","preview"])
    p.add_argument("target",choices=["both","powerpoint","wps"])
    p.add_argument("source",type=Path)
    p.add_argument("page",type=int,nargs="?",default=1)
    p.add_argument("output",type=Path,nargs="?")
    a=p.parse_args()
    try:
        run(a.mode,a.target,a.source.resolve(),a.page,a.output.resolve() if a.output else None)
    except RuntimeError as exc:
        sys.exit(str(exc))

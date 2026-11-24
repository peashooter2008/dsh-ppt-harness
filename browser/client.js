// DeepSeek Harness browser entry. React is supplied by the active client.
window.__ModuleLoader__.load({
  id: "dsh-ppt-harness",
  factory(require) {
    const React = require("react");
    const h = React.createElement;
    const { useState, useEffect, useRef, useId } = React;
    const kind = "ppt-studio-opening";
    const css = `
      .dy-opening{container-type:inline-size;width:100%;min-width:0;font:14px/1.55 "Instrument Sans","Microsoft YaHei UI",system-ui,sans-serif;color:#162638}
      .dy-opening *{box-sizing:border-box}
      .dy-panel{--blue:#1745aa;--line:#c6cdd0;overflow:hidden;background:#fafbf9;border:1px solid #aeb9bd;border-radius:10px}
      .dy-head,.dy-foot,.dy-body{padding:16px 20px}
      .dy-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;padding-bottom:11px}
      .dy-head h3{color:#142836;font-size:clamp(19px,3.5cqw,25px);font-weight:680;line-height:1.25;margin:0;letter-spacing:-.035em;overflow-wrap:anywhere}
      .dy-body{padding-top:0;padding-bottom:12px}
      .dy-body fieldset{border:0;padding:0;margin:0;min-width:0}
      .dy-body legend,.dy-caption{font-size:12px;color:#50616c;font-weight:600;margin:0 0 7px;padding:0}
      .dy-choices{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      .dy-choice{display:block;position:relative;min-width:0;border:1px solid var(--line);background:#fff;border-radius:6px;overflow:hidden;cursor:pointer}
      .dy-choice[data-current=true]{box-shadow:inset 0 0 0 1px var(--blue);border-color:var(--blue)}
      .dy-choice:has(:focus-visible){outline:3px solid #184cbb;outline-offset:2px}
      .dy-choice input{position:absolute;inset:0;opacity:0;width:100%;height:100%;margin:0;cursor:pointer}
      .dy-preview{display:grid;place-items:center;aspect-ratio:16/9;overflow:hidden;background:#e1e6e5;color:#40545c;font-size:12px}
      .dy-preview img{width:100%;height:100%;object-fit:contain;display:block}
      .dy-choice-text{display:flex;align-items:center;gap:7px;line-height:1.35;min-height:38px;padding:8px 10px;font-size:13px;font-weight:650;overflow-wrap:anywhere}
      .dy-dot{width:14px;height:14px;border:1px solid #74828e;border-radius:50%;background:#fff;display:inline-grid;place-items:center;flex:none}
      .dy-choice[data-current=true] .dy-dot{border-color:var(--blue)}.dy-choice[data-current=true] .dy-dot:before{content:"";width:8px;height:8px;background:var(--blue);border-radius:50%}
      .dy-opening button,.dy-opening select,.dy-opening input,.dy-opening textarea{font:inherit}
      .dy-opening button,.dy-download{color:#182d42;cursor:pointer;border:1px solid #a6b1b9;background:#fff;border-radius:5px;padding:6px 10px;line-height:1.45;font-size:13px;font-weight:580}
      .dy-opening button:hover:not(:disabled),.dy-download:hover{background:#eef3f7}
      .dy-opening :is(button,a,input,textarea,select,summary):focus-visible{outline:3px solid #2454c1;outline-offset:2px}
      .dy-opening :is(button,input,textarea,select):disabled{opacity:.65;cursor:default}
      .dy-modules{margin-top:11px;border-top:1px solid var(--line)}
      .dy-modules details+details{border-top:1px solid #dfe3e4}
      .dy-opening summary{cursor:pointer;padding:9px 2px;font-size:13px;font-weight:620;color:#223848}
      .dy-options{padding:0 0 11px;display:grid;gap:8px}
      .dy-row,.dy-tools,.dy-foot{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
      .dy-row>label,.dy-row .dy-label{font-size:13px}
      .dy-options input[type=search],.dy-options textarea,.dy-row select{border:1px solid #a4b0b7;background:white;color:#112c41;border-radius:4px;padding:6px 8px;min-width:0}
      .dy-options input[type=search]{flex:1 1 100px;font-size:14px}
      .dy-options textarea{width:100%;min-height:68px;resize:vertical}
      .dy-rehearse{margin:9px 0 0;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
      .dy-rehearse .dy-row{gap:5px}
      .dy-rehearse select{font-size:12px;padding:4px}
      .dy-rehearse button{font-size:12px;padding:4px 7px}
      .dy-muted,.dy-opening figcaption{margin:0;font-size:12px;color:#50616c;overflow-wrap:anywhere}
      .dy-results{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,118px),1fr));gap:9px}
      .dy-result{min-width:0;margin:0;display:grid;align-content:start;gap:3px}
      .dy-result button{width:100%;min-width:0;text-align:left;padding:0;overflow:hidden}
      .dy-result img{display:block;width:100%;height:74px;object-fit:cover;background:#e0e6e8}
      .dy-result .dy-no-thumb{display:grid;place-items:center;height:74px;background:#e0e6e8;color:#354859;font-size:12px}
      .dy-result .dy-retry-photo{width:auto;padding:2px 5px;font-size:11px}
      .dy-result strong{display:block;padding:3px 5px;font-size:12px;overflow-wrap:anywhere}
      .dy-result a{color:var(--blue);font-size:11px}
      .dy-foot{justify-content:space-between;border-top:1px solid var(--line);background:#f0f4f3;padding-block:11px}
      .dy-foot p{flex:1 1 100px;margin:0;font-size:12px;color:#425666;overflow-wrap:anywhere}
      .dy-foot p[data-error=true],.dy-error{color:#942b28}
      .dy-foot .dy-primary,.dy-foot a.dy-download{display:inline-block;background:#193c68;color:#fff;border:1px solid #193c68;font-weight:650;text-decoration:none;padding:7px 14px}
      .dy-foot .dy-primary:hover:not(:disabled),.dy-foot a.dy-download:hover{background:#0d2b53}
      [data-ds-dark-theme] .dy-opening{color-scheme:dark;color:#e8edf2}
      [data-ds-dark-theme] .dy-panel{--blue:#9abfff;--line:#556271;background:#20242b;border-color:#687584}
      [data-ds-dark-theme] .dy-head h3,[data-ds-dark-theme] .dy-opening summary{color:#f1f4f7}
      [data-ds-dark-theme] .dy-opening :is(.dy-muted,figcaption,legend,.dy-caption),[data-ds-dark-theme] .dy-foot p{color:#bac7d4}
      [data-ds-dark-theme] .dy-opening :is(.dy-choice,.dy-dot,button,select,textarea,input[type=search]){background:#2a313a;color:#e8edf2;border-color:#738294}
      [data-ds-dark-theme] .dy-choice[data-current=true],[data-ds-dark-theme] .dy-choice[data-current=true] .dy-dot{border-color:var(--blue)}
      [data-ds-dark-theme] .dy-opening button:hover:not(:disabled){background:#394553}
      [data-ds-dark-theme] .dy-opening :focus-visible,[data-ds-dark-theme] .dy-choice:has(:focus-visible){outline-color:#a8caff}
      [data-ds-dark-theme] .dy-options :is(textarea,input)::placeholder{color:#b0becb}
      [data-ds-dark-theme] .dy-modules details+details{border-color:#465361}
      [data-ds-dark-theme] .dy-preview,[data-ds-dark-theme] .dy-result img{background:#171d23;color:#bdcad5}
      [data-ds-dark-theme] .dy-result .dy-no-thumb{background:#171d23;color:#bdcad5}
      [data-ds-dark-theme] .dy-foot{background:#272e36}
      [data-ds-dark-theme] .dy-foot p[data-error=true]{color:#ffb4b1}
      [data-ds-dark-theme] .dy-foot :is(.dy-primary,a.dy-download){background:#a9cbff;color:#142b49;border-color:#a9cbff}
      [data-ds-dark-theme] .dy-foot :is(.dy-primary,a.dy-download):hover:not(:disabled){background:#c7deff}
      @container (max-width:460px){.dy-head,.dy-foot,.dy-body{padding-left:12px;padding-right:12px}.dy-choices{grid-template-columns:minmax(0,1fr)}.dy-choice-text{min-height:32px}.dy-head{padding-top:12px}.dy-choice{border-radius:4px}}
    `;

    function isAsset(path) {
      return typeof path === "string" && path.startsWith("/api/ppt-studio.asset?");
    }
    function publicLink(value) {
      try { const url = new URL(value); return url.protocol === "https:" ? url.href : null; }
      catch { return null; }
    }
    function PhotoResult({photo,busy,choose}) {
      const [attempt,setAttempt]=useState(0),[failed,setFailed]=useState([]);
      const local=typeof photo.thumbnailData === "string" && photo.thumbnailData.startsWith("data:image/jpeg;base64,") ? photo.thumbnailData : null;
      const online=publicLink(photo.thumbnail),source=publicLink(photo.sourceUrl || photo.source);
      let preview=[local,online].find(url=>url && !failed.includes(url));
      const original=preview;
      if (preview && preview === online && attempt) {
        const url=new URL(online);
        if (url.hostname.endsWith(".wikimedia.org")) url.searchParams.set("dy_retry",String(attempt));
        preview=url.href;
      }
      return h("figure",{className:"dy-result"},
        h("button",{type:"button",disabled:busy,onClick:choose,"aria-label":"采用图片 "+photo.title},
          preview ? h("img",{key:attempt+(original===local?":local":":remote"),src:preview,alt:"",loading:"lazy",referrerPolicy:"no-referrer",
            onError:()=>setFailed(values=>values.includes(original)?values:[...values,original])})
            : h("span",{className:"dy-no-thumb",role:"status"},"预览暂不可用"),
          h("strong",null,photo.title)),
        h("div",{className:"dy-row"},source && h("a",{href:source,rel:"noreferrer",target:"_blank"},"查看出处"),
          !preview && (local || online) && h("button",{type:"button",className:"dy-retry-photo",disabled:busy,
            onClick:()=>{setFailed([]);setAttempt(n=>n+1);}},"重试预览")));
    }
    function readData(file,kind="图片") {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error("无法读取"+kind+"，请重新选取。"));
        reader.readAsDataURL(file);
      });
    }
    async function request(card, action, fields, signal, route = "/api/ppt-studio.card") {
      let response;
      try {
        response = await fetch(route, {
          method:"POST", headers:{ "Content-Type":"application/json" },
          body:JSON.stringify({taskId:card.taskId,sessionId:card.sessionId,token:card.token,action,...fields}), signal
        });
      } catch (error) {
        if (signal.aborted) throw error;
        throw new Error("暂时连不上本机制作工具，请重试。");
      }
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.ok === false) {
        const reason = typeof result.error === "string" ? result.error : result.message;
        throw new Error(reason || "操作未完成，请重新载入样页后再试。");
      }
      return result;
    }

    // Desktop uses a fetch bridge for /api, including when its document is file://.
    function Preview({url, label, accepts = isAsset, attempt = 0, retry = false,cache}) {
      const [loaded, setLoaded] = useState(null);
      const [retryCount,setRetryCount] = useState(0);
      useEffect(() => {
        const controller = new AbortController();
        let objectUrl;
        if (accepts(url)) {
          const read=cache?.has(url) ? Promise.resolve(cache.get(url)) : fetch(url,{signal:controller.signal}).then(response => {
            if (!response.ok) throw new Error();
            return response.blob();
          });
          read.then(blob => {
            if (controller.signal.aborted) return;
            if(cache && blob.size<=1024*1024){
              cache.delete(url);cache.set(url,blob);
              if(cache.size>18)cache.delete(cache.keys().next().value);
            }
            objectUrl = URL.createObjectURL(blob);
            setLoaded({url,src:objectUrl});
          }).catch(() => { if (!controller.signal.aborted) setLoaded({url,src:null}); });
        }
        return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
      },[url,accepts,attempt,retryCount,cache]);
      const src = loaded?.url === url && loaded.src;
      const failed = !accepts(url) || loaded?.url === url && !src;
      return h("div",{className:"dy-preview"},src ? h("img",{src,alt:label})
        : failed && retry && accepts(url) ? h("button",{type:"button",onClick:()=>{setLoaded(null);setRetryCount(n=>n+1);}},"重新载入这页")
        : failed ? "样页未能载入" : "正在读取样页…");
    }
    const motionCss=`
      .dy-clip{display:grid;gap:7px;min-width:0;justify-items:start}
      .dy-clip video{display:block;width:100%;max-height:350px;aspect-ratio:16/9;background:#15191d;object-fit:contain;border-radius:5px}
      .dy-clip>div{width:100%}.dy-clip p{font-size:12px;overflow-wrap:anywhere}
      .dy-clip-apply{display:flex;gap:7px;align-items:end;flex-wrap:wrap}.dy-clip-apply label{flex:1 1 110px}
      .dy-clip-apply p{flex-basis:100%}.dy-tpl-lede>.dy-clip{margin-top:8px}
    `;
    function MotionVideo({url,label,accepts}) {
      const [source,setSource]=useState(null),[failed,setFailed]=useState(false),[attempt,setAttempt]=useState(0);
      useEffect(()=>{
        const controller=new AbortController();
        let mediaUrl;
        async function load() {
          try {
            if(!accepts(url))throw new Error();
            const response=await fetch(url,{signal:controller.signal});
            if(!response.ok)throw new Error();
            const blob=await response.blob();
            if(!blob.size)throw new Error();
            if(controller.signal.aborted)return;
            mediaUrl=URL.createObjectURL(blob);
            setSource(mediaUrl);
          } catch {if(!controller.signal.aborted)setFailed(true);}
        }
        load();
        return ()=>{controller.abort();if(mediaUrl)URL.revokeObjectURL(mediaUrl);};
      },[url,accepts,attempt]);
      if(failed)return h("div",null,h("p",{role:"status"},"动作短片未能播放。"),
        h("button",{type:"button",onClick:()=>{setSource(null);setFailed(false);setAttempt(n=>n+1);}},"重试播放"));
      return source?h("video",{src:source,controls:true,muted:true,playsInline:true,autoPlay:true,"aria-label":label,onError:()=>setFailed(true)})
        :h("p",{role:"status"},"正在读取动作短片…");
    }
    function MotionPreview({motion,accepts,open,toggle,children}) {
      if(!motion?.pages?.length || !accepts(motion.url))return null;
      const label=motion.label || "模板动作";
      return h("div",{className:"dy-clip","data-motion-active":open?true:undefined},
        h("button",{type:"button","aria-expanded":open,"aria-label":open?"收起动作预览":"试看动作 · "+label,onClick:toggle},
          open?"收起动作预览":"试看动作"),
        open && h(React.Fragment,null,
          h("p",null,[label,motion.kind==="adaptation"?"改编演示":"原稿放映","原稿第 "+motion.pages.join(" → ")+" 页",
            motion.duration>0?Number(motion.duration.toFixed(1))+" 秒":null].filter(Boolean).join(" · ")),
          h(MotionVideo,{key:motion.url,url:motion.url,label,accepts}),children));
    }
    function Card({node}) {
      const card = node.data;
      const unique = useId();
      const [state,setState] = useState(null), [selected,setSelected] = useState(null);
      const [busy,setBusy] = useState(""), [error,setError] = useState("");
      const [clicked,setClicked] = useState(false), [query,setQuery] = useState("");
      const [results,setResults] = useState(null), [notes,setNotes] = useState(null);
      const [download,setDownload] = useState(null), [info,setInfo] = useState("");
      const fileInput = useRef(null), controller = useRef(null), locked = useRef(false);
      const [reload,setReload] = useState(0);
      function applyState(next) {
        setState(next); setSelected(next.selected || next.variants?.[0]?.id);
        setDownload(isAsset(next.export?.download) ? next.export.download : null);
      }
      useEffect(() => {
        const life = new AbortController();
        controller.current = life; locked.current = false;
        setState(null); setError(""); setBusy("读取样页"); setInfo(""); setResults(null);
        setNotes(null); setQuery(""); setDownload(null); setClicked(false);
        request(card,"state",{},life.signal).then(next => {
          if (!life.signal.aborted) applyState(next);
        }).catch(e => { if (!life.signal.aborted) setError(e.message); })
          .finally(() => { if (!life.signal.aborted) setBusy(""); });
        return () => life.abort();
      },[card.taskId,card.sessionId,card.token,card.updateSeq,reload]);
      useEffect(()=>{
        if(!state)return;
        const life=new AbortController();let fetching=false;
        const tick=async()=>{
          if(fetching || locked.current || document.visibilityState==="hidden")return;
          fetching=true;
          try {const next=await request(card,"state",{},life.signal);
            if(!life.signal.aborted && !locked.current && (next.revision!==state.revision || next.selected!==state.selected || next.export?.deck!==state.export?.deck || next.nameOnClick!==state.nameOnClick))applyState(next);
          }catch(e){if(!life.signal.aborted)setError(e.message);}finally{fetching=false;}
        };
        const interval=setInterval(tick,2300);return()=>{life.abort();clearInterval(interval);};
      },[card.taskId,state?.revision,state?.selected,state?.export?.deck,state?.nameOnClick]);
      async function run(label, work) {
        if (locked.current) return;
        const life = controller.current;
        locked.current = true;setBusy(label);setError("");setInfo("");
        const send = (action,fields={}) => request(card,action,fields,life.signal);
        try { await work(send,life.signal); }
        catch(e){ if (!life.signal.aborted) setError(e.message); }
        finally { if (!life.signal.aborted) {locked.current=false;setBusy("");} }
      }
      const rev = () => ({revision:state.revision,selected});
      function selectVariant(id) {
        if (selected === id) return;
        run("正在保存选版",async (send,signal) => {
          const previous=selected, previousDownload=download;
          setSelected(id);setDownload(null);
          try {
            const next=await send("revise",{selected:id,revision:state.revision});
            if (!signal.aborted) {applyState(next);setInfo("已选用这版开场");}
          } catch (e) {
            if (!signal.aborted) {setSelected(previous);setDownload(previousDownload);}
            throw e;
          }
        });
      }
      function refresh(label,action,fields) {
        return run(label,async (send,signal) => {
          const next = await send(action,{...rev(),...fields});
          if (signal.aborted) return;
          applyState(next);setClicked(false);setInfo(fields.remove ? "已换为纯文字开场" : "样页已更新");
          if ("speakerNotes" in fields) setNotes(null);
        });
      }
      function upload(file) {
        if (!file) return;
        if (!["image/png","image/jpeg","image/webp"].includes(file.type) || file.size>12*1024*1024) {
          setError("请选择 12 MiB 以内的 PNG、JPEG 或 WebP 图片。");return;
        }
        run("正在换图",async (send,signal) => {
          const imageData = await readData(file);
          const next = await send("photo",{...rev(),imageData,assetKind:"personal",assetSource:file.name});
          if (!signal.aborted) {applyState(next);setClicked(false);setInfo("已换入所选图片");}
        });
      }
      function search(event) {
        event.preventDefault();
        const term=query.trim();
        if (!term) return;
        run("正在找图",async (send,signal) => {
          setResults(null);
          const next=await send("search",{query:term});
          if (!signal.aborted) setResults(next.photos || []);
        });
      }
      function createDeck() {
        run("正在生成 PPTX",async (send,signal) => {
          let revision=state.revision;
          if (notes !== null && notes !== (state.speakerNotes || "")) {
            const saved=await send("revise",{...rev(),speakerNotes:notes});
            if (signal.aborted) return;
            revision=saved.revision;applyState(saved);setNotes(null);
          }
          const next=await send("export",{revision,variant:selected,nameOnClick:state.nameOnClick});
          if (signal.aborted) return;
          const path=next.download || next.deck;
          if (!isAsset(path)) throw new Error("文件入口缺失，请重新载入样页。");
          setDownload(path);setInfo("已保存你的选择");
        });
      }
      async function downloadFile(event) {
        if (location.protocol === "http:" || location.protocol === "https:") return;
        event.preventDefault();
        run("正在读取文件",async (send,signal) => {
          const response=await fetch(download,{signal});
          if (!response.ok) throw new Error("文件未能读取，请重新生成 PPTX。");
          const blob=await response.blob();if(signal.aborted) return;
          const url=URL.createObjectURL(blob),a=document.createElement("a");
          a.href=url;a.download="竞选开场.pptx";document.body.append(a);a.click();a.remove();
          setTimeout(() => URL.revokeObjectURL(url),60000);
        });
      }
      const btn=(text,onClick,props={})=>h("button",{type:"button",disabled:!!busy,onClick,...props},text);
      const row=(...children)=>h("div",{className:"dy-row"},...children);
      const modules = state?.modules || {};
      const notesChanged = notes !== null && notes !== (state?.speakerNotes || "");
      function photoModule() {
        if (!state.hasImage && !modules.upload && !modules.photoSearch?.available && !modules.imageGeneration) return null;
        return h("details",null,h("summary",null,state.hasImage ? "更换配图" : "添加配图"),
          h("div",{className:"dy-options"},
            modules.upload && row(btn("从电脑选图",()=>fileInput.current.click()),
              h("input",{hidden:true,type:"file",accept:"image/png,image/jpeg,image/webp",ref:fileInput,onChange:e=>{upload(e.target.files[0]);e.target.value="";}}),
              h("span",{className:"dy-muted"},"PNG、JPEG、WebP")),
            state.hasImage && row(btn("改用纯文字",()=>refresh("正在排纯文字版","photo",{remove:true}))),
            modules.photoSearch?.available && h("form",{onSubmit:search,className:"dy-row"},
              h("input",{type:"search","aria-label":"图片关键词",placeholder:"搜索主题图片",value:query,maxLength:180,onChange:e=>setQuery(e.target.value)}),
              h("button",{type:"submit",disabled:!!busy || !query.trim()},"找图")),
            results?.length===0 && h("p",{className:"dy-muted",role:"status"},"没有找到候选图，可换一个关键词。"),
            results?.length>0 && h("div",{className:"dy-results"},results.map(p=>h(PhotoResult,{key:p.id,photo:p,busy:!!busy,choose:()=>refresh("正在换图","photo",{id:p.id})}))),
            modules.imageGeneration?.mode==="host" && h("p",{className:"dy-muted"},"已配置生图工具时，可在当前对话描述画面，请 AI 生成并换入。")));
      }
      const footerMessage = error || busy || info;
      return h("div",{className:"dy-opening"},h("style",null,css),h("section",{className:"dy-panel","aria-label":"竞选开场试排"},
        h("header",{className:"dy-head"},h("h3",null,state?.title || "竞选开场")),
        state && h("div",{className:"dy-body"},
          h("fieldset",null,h("legend",null,"选一版开场"),h("div",{className:"dy-choices"},state.variants.map(v=>h("label",{className:"dy-choice","data-current":selected===v.id,key:v.id},
            h(Preview,{url:state.nameOnClick && !clicked ? v.beforePreview || v.preview : v.preview,label:v.label+"样页"}),
            h("span",{className:"dy-choice-text"},h("span",{className:"dy-dot","aria-hidden":"true"}),v.label),
            h("input",{type:"radio",name:unique,checked:v.id===selected,disabled:!!busy,onChange:()=>selectVariant(v.id)}))))),
          modules.nameAnimation && h("div",{className:"dy-rehearse"},
            row(h("label",{htmlFor:unique+"-timing"},"姓名出场"),
              h("select",{id:unique+"-timing",value:state.nameOnClick?"click":"start",disabled:!!busy,onChange:e=>refresh("正在调整出场时机","revise",{nameOnClick:e.target.value==="click"})},h("option",{value:"start"},"开场出现"),h("option",{value:"click"},"点击时出现"))),
            state.nameOnClick && btn(clicked ? "↶ 回到开场" : "▷ 试播下一击",()=>setClicked(!clicked))),
          h("div",{className:"dy-modules"},photoModule(),
            modules.speakerNotes && h("details",null,h("summary",null,"讲者备注"),h("div",{className:"dy-options"},
              h("textarea",{"aria-label":"讲者备注",maxLength:3000,value:notes ?? state.speakerNotes ?? "",placeholder:"写下上台时想说的话",onChange:e=>{setNotes(e.target.value);setDownload(null);}}),
              notesChanged && row(btn("保存备注",()=>refresh("正在保存备注","revise",{speakerNotes:notes}))))))),
        h("footer",{className:"dy-foot"},
          h("p",{role:error?"alert":"status","data-error":!!error,"aria-live":"polite"},footerMessage || (download?"PPTX 已生成":state?"可编辑的 PowerPoint 文件":"正在读取样页…")),
          error && btn("重新载入",()=>setReload(n=>n+1)),
          state && (download && !notesChanged
            ? h("a",{className:"dy-download",href:download,download:"竞选开场.pptx",onClick:downloadFile},"下载 PPTX ↓")
            : btn("用这版生成 PPTX",createDeck,{className:"dy-primary",disabled:!!busy || !selected})))));
    }
    const templateRoute = "/api/ppt-studio.templates";
    const templateKind = "ppt-studio-templates";
    const isTemplateAsset = url => typeof url === "string" && url.startsWith("/api/ppt-studio.template-asset?");
    const templateCss = `
      .dy-tpl{--ink:#192f45;--muted:#485d72;--line:#b8c7d6;--surface:#fff;--shelf:#eef3f7;--well:#dce5ee;--active:#224b81;--onactive:#fff;--alert:#972827;container-type:inline-size;color:var(--ink);width:100%;min-width:0;font:14px/1.5 "Instrument Sans","Microsoft YaHei UI",system-ui,sans-serif}
      [data-ds-dark-theme] .dy-tpl{color-scheme:dark;--ink:#eef3fa;--muted:#bacbdc;--line:#627386;--surface:#252c34;--shelf:#202731;--well:#17202b;--active:#adceff;--onactive:#102338;--alert:#ffb6b2}
      .dy-tpl *{box-sizing:border-box}
      .dy-tpl section{background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden}
      .dy-tpl header,.dy-tpl footer{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px 14px;padding:13px 17px}
      .dy-tpl h3,.dy-tpl h4,.dy-tpl p,.dy-tpl figure{margin:0}
      .dy-tpl h3,.dy-tpl h4{font-family:"Instrument Sans","Microsoft YaHei UI",system-ui,sans-serif;line-height:1.3;font-weight:680;color:var(--ink);overflow-wrap:anywhere}
      .dy-tpl h3{font-size:20px}.dy-tpl h4{font-size:17px}
      .dy-tpl input,.dy-tpl button,.dy-tpl a{font:inherit;color:var(--ink)}
      .dy-tpl button,.dy-tpl a{appearance:none;background:var(--surface);border:1px solid var(--line);padding:6px 10px;border-radius:5px;text-decoration:none;cursor:pointer}
      .dy-tpl button:disabled{cursor:wait;opacity:.65}
      .dy-tpl :is(a,button,input):focus-visible{outline:3px solid var(--active);outline-offset:2px}
      .dy-tpl button:hover:not(:disabled),.dy-tpl a:hover{border-color:var(--active)}
      .dy-tpl header input{flex:0 1 176px;min-width:0;max-width:100%;border:1px solid var(--line);border-radius:5px;background:var(--shelf);padding:6px 9px}
      .dy-tpl input::placeholder{color:var(--muted);opacity:1}
      .dy-tpl .dy-tpl-shelf{background:var(--shelf);border-block:1px solid var(--line);padding:14px 17px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
      .dy-tpl .dy-tpl-tile{display:flex;flex-direction:column;align-items:stretch;text-align:left;min-width:0;padding:0;overflow:hidden;border-radius:6px}
      .dy-tpl .dy-preview{aspect-ratio:16/9;display:grid;place-items:center;overflow:hidden;background:var(--well);color:var(--muted);font-size:12px}
      .dy-tpl .dy-preview img{display:block;width:100%;height:100%;object-fit:contain}
      .dy-tpl .dy-tpl-tile strong,.dy-tpl .dy-tpl-tile small{padding-inline:9px;overflow-wrap:anywhere}
      .dy-tpl .dy-tpl-tile strong{font-size:14px;line-height:1.4;margin-top:7px}
      .dy-tpl .dy-tpl-tile small{margin-top:auto;padding-top:3px;padding-bottom:8px;font-size:12px;color:var(--muted)}
      .dy-tpl .dy-tpl-detail{border-top:1px solid var(--line)}
      .dy-tpl .dy-tpl-lede{padding:12px 17px 10px}
      .dy-tpl .dy-tpl-lede p,.dy-tpl footer p{color:var(--muted);font-size:13px;overflow-wrap:anywhere}
      .dy-tpl .dy-tpl-lede p{margin-top:4px}
      .dy-tpl figure{margin-inline:17px;border:1px solid var(--line);border-radius:4px;overflow:hidden;background:var(--shelf)}
      .dy-tpl figure>.dy-preview{max-height:360px;margin:auto}
      .dy-tpl .dy-tpl-pages{display:flex;align-items:center;flex-wrap:wrap;gap:5px;padding:9px 17px 12px}
      .dy-tpl .dy-tpl-pages button{font-size:12px;padding:4px 8px}
      .dy-tpl .dy-tpl-pages select,.dy-tpl .dy-region textarea{font:inherit;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:4px;padding:4px 6px}
      .dy-plan .dy-tpl .dy-tpl-pages select{width:auto;min-width:5.5em;max-width:8em;font-size:12px}
      .dy-tpl section.dy-region{--weak:var(--muted);--bg:var(--shelf);border:0;border-radius:0}
      .dy-tpl .dy-r-actions,.dy-tpl .dy-r-editor,.dy-tpl .dy-r-note{margin-inline:8px;margin-bottom:7px}
      .dy-tpl .dy-tpl-pages button[aria-pressed=true]{color:var(--active);border-color:var(--active);box-shadow:inset 0 0 0 1px var(--active)}
      .dy-tpl footer p{flex:1 1 132px}.dy-tpl footer:has(.dy-tpl-alert) p{color:var(--alert)}
      .dy-tpl .dy-tpl-action{display:inline-block;border-color:var(--active);background:var(--active);color:var(--onactive);font-weight:650;text-align:center}
      .dy-tpl .dy-tpl-detail+footer{border-top:1px solid var(--line)}
      .dy-tpl .dy-tpl-empty{padding:16px 17px;background:var(--shelf);color:var(--muted)}
      @container(max-width:540px){.dy-tpl .dy-tpl-shelf{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @container(max-width:370px){.dy-tpl header,.dy-tpl footer,.dy-tpl .dy-tpl-shelf,.dy-tpl .dy-tpl-lede,.dy-tpl .dy-tpl-pages{padding-inline:11px}.dy-tpl figure{margin-inline:11px}.dy-tpl .dy-tpl-shelf{gap:7px}.dy-tpl header input{flex:1 1 120px}.dy-tpl .dy-tpl-tile strong{font-size:13px}}
      @container(max-width:230px){.dy-tpl .dy-tpl-shelf{grid-template-columns:1fr}}
    `;
    function TemplateCard({node}) {
      // A session can have several independently selected decks.
      return h(TemplateShelf,{key:node.data.taskId,card:node.data});
    }
    function TemplateShelf({card}) {
      const [state,setState] = useState(null);
      const [query,setQuery] = useState(""), [limit,setLimit] = useState(6);
      const [collection,setCollection]=useState("recommended"),[category,setCategory]=useState("");
      const [detail,setDetail] = useState(null), [pageNumber,setPageNumber] = useState(null);
      const [showOriginal,setShowOriginal] = useState(false);
      const [motionOpen,setMotionOpen]=useState(false);
      const [busy,setBusy] = useState(""), [error,setError] = useState(""), [reload,setReload] = useState(0);
      const initialized = useRef(false), life = useRef(null), lock = useRef(false), lastSelected = useRef(null);
      const previewCache = useRef(new Map()), acceptedRevision=useRef(null), lastEdits=useRef([]);
      function open(id) {setDetail(id);setPageNumber(null);setShowOriginal(false);setMotionOpen(false);setError("");}
      function accept(next) {
        if (!Array.isArray(next.templates)) throw new Error("模板目录读取不完整，请重试。");
        if(next.personalized && next.selected===lastSelected.current && acceptedRevision.current!==next.revision) {
          const before=new Map(lastEdits.current.map(p=>[p.number,p.preview]));
          const changed=(next.editedPages || []).find(p=>p.preview && before.get(p.number)!==p.preview);
          if(changed){setShowOriginal(false);setPageNumber(changed.number);}
        }
        lastEdits.current=next.editedPages || [];
        acceptedRevision.current=next.revision;
        if (!initialized.current) {setQuery(next.query || "");initialized.current=true;}
        if (next.selected !== lastSelected.current) {
          open(next.selected || null);
          lastSelected.current=next.selected;
        }
        setState(next);
      }
      useEffect(() => {
        const controller=new AbortController(); life.current=controller;
        setError("");setBusy("正在读取模板");lock.current=true;
        request(card,"state",{},controller.signal,templateRoute).then(next => {
          if (!controller.signal.aborted) accept(next);
        }).catch(e => {if (!controller.signal.aborted) setError(e.message);})
          .finally(() => {if (!controller.signal.aborted) {lock.current=false;setBusy("");}});
        return () => controller.abort();
      },[card.taskId,card.sessionId,card.token,card.updateSeq,reload]);
      const templates = state?.templates || [];
      useEffect(()=>{
        if(!state)return;
        const ctrl=new AbortController();let fetching=false;
        const tick=async()=>{
          if(fetching || lock.current || document.visibilityState==="hidden")return;
          fetching=true;
          const before=acceptedRevision.current;
          try {
            const next=await request(card,"state",{},ctrl.signal,templateRoute);
            if(!ctrl.signal.aborted && !lock.current && acceptedRevision.current===before && (next.revision!==before || next.phase!==state?.phase || next.error!==state?.error))accept(next);
          } catch(e){if(!ctrl.signal.aborted)setError(e.message);}
          finally{fetching=false;}
        };
        const interval=setInterval(tick,2300);
        return ()=>{clearInterval(interval);ctrl.abort();};
      },[card.taskId,card.sessionId,card.token,card.embedded,state?.phase,state?.error]);
      const current = templates.find(t=>t.id===detail);
      const editedPages = current && current.id===state?.selected && Array.isArray(state?.editedPages) ? state.editedPages : [];
      const showingEdits = editedPages.length>0 && !showOriginal;
      const pages = showingEdits ? editedPages : current?.pages || [];
      const page = pages.find(p=>p.number===pageNumber) || pages[0];
      const words = query.trim().toLocaleLowerCase().split(/\s+/u).filter(Boolean);
      const matches = templates.filter(t=>{
        const text=[t.title,t.category,t.sourceCategory,t.style,t.description].join(" ").toLocaleLowerCase();
        return (words.length || category || collection==="all" || t.recommended!==false) && (!category || t.category===category || t.sourceCategory===category) && words.every(word=>text.includes(word));
      });
      const exported = current && state.selected===current.id && isTemplateAsset(state.download);
      const changedNames=state?.annotation?.page===page?.number && state?.phase==="ready" ?
        (state.annotation?.changed || []).map(o=>o.name || o.id).slice(0,3).join("、") : "";
      async function run(label,work) {
        if (lock.current || !life.current || life.current.signal.aborted) return;
        const signal=life.current.signal;
        lock.current=true;setBusy(label);setError("");
        try {await work(signal);}
        catch(e){if (!signal.aborted) setError(e.message);}
        finally {if (!signal.aborted) {lock.current=false;setBusy("");}}
      }
      function choose() {
        return run("正在创建整份副本",async signal=>{
          const next=await request(card,"export",{templateId:current.id,revision:state.revision},signal,templateRoute);
          if (!signal.aborted) accept(next);
        });
      }
      const fullBook=!!current && state.selected===current.id;
      function switchEdition() {
        const action=state.editHistoryAction;
        return run("正在切换版本",async signal=>{
          const next=await request(card,action,{templateId:current.id,revision:state.revision},signal,templateRoute);
          if(!signal.aborted){setShowOriginal(false);accept(next);}
        });
      }
      async function annotate(fields){
        if(lock.current || !life.current || life.current.signal.aborted)throw new Error("请稍候再发送。");
        const signal=life.current.signal;
        lock.current=true;setBusy("正在提交批注");setError("");
        try{
          const next=await request(card,"annotate",{templateId:current.id,version:showingEdits?"current":"original",...fields},signal,"/api/ppt-studio.template-annotate");
          if(!signal.aborted)accept(next);
          return next;
        }finally{if(!signal.aborted){lock.current=false;setBusy("");}}
      }
      function turnTo(number) {
        if(!fullBook || !Number.isInteger(number) || number<1 || number>current.slideCount)return;
        if(pages.some(p=>p.number===number && isTemplateAsset(p.preview))){setPageNumber(number);return;}
        return run("正在读取第 "+number+" 页",async signal=>{
          const next=await request(card,"previewPage",{templateId:current.id,page:number,version:showingEdits?"current":"original",revision:state.revision},signal,templateRoute);
          if(!signal.aborted){accept(next);setPageNumber(number);}
        });
      }
      async function download(event) {
        if (location.protocol==="http:" || location.protocol==="https:") return;
        event.preventDefault();
        return run("正在读取 PPTX",async signal=>{
          const response=await fetch(state.download,{signal});
          if (!response.ok) throw new Error("文件未能读取，请刷新后再下载。");
          const blob=await response.blob();
          if (signal.aborted) return;
          const url=URL.createObjectURL(blob),a=document.createElement("a");
          a.href=url;a.download=state.filename || "模板.pptx";document.body.append(a);a.click();a.remove();
          setTimeout(()=>URL.revokeObjectURL(url),60000);
        });
      }
      const button=(label,onClick,props={})=>h("button",{type:"button",onClick,...props},label);
      const preview=(item,p,retry=false)=>h(Preview,{url:p?.preview,label:item.title+" · 第 "+(p?.number ?? "—")+" 页",accepts:isTemplateAsset,attempt:reload,retry,cache:previewCache.current});
      const fallback=!state ? "正在读取模板目录…" : templates.length ? "没有匹配的模板，试试其他关键词。" : "当前工作台没有可用的模板原稿。";
      function statusText(){
        if(error || state?.error || busy)return error || state?.error || busy;
        if(state?.phase==="revising")return "AI 正在按批注修改幻灯片…";
        if(!current)return state?"共 "+matches.length+" 份":"";
        if(!exported)return "选用后将创建整份 PPTX 副本。";
        if(!state.personalized)return "已选用，可在对话里指定要改的页和文字。";
        if(!showingEdits)return "当前显示原稿，可下载已保存的改稿。";
        return changedNames?"已更新「"+changedNames+"」。":"当前显示改稿实页。";
      }
      return h("div",{className:"dy-tpl"},h("style",null,templateCss+motionCss),h("section",{"aria-label":"PPT 模板库"},
        h("header",null,h("h3",null,card.embedded?"原稿与改稿":"PPT 模板库"),
          current ? !card.embedded && button("返回模板库",()=>open(null),{disabled:!!busy})
          : state && templates.length>0 && h("input",{type:"search",value:query,placeholder:"搜索名称或风格","aria-label":"搜索模板",onChange:e=>{setQuery(e.target.value);setLimit(6);}})),
        !current && state && h("div",{className:"dy-tpl-pages",role:"group","aria-label":"模板范围"},
          h("a",{href:state.communityOrigin || "https://ppt-template-studio.netlify.app/",target:"_blank",rel:"noopener noreferrer"},"浏览在线社区"),
          button("精选推荐",()=>{setCollection("recommended");setQuery("");setCategory("");setLimit(6);},{"aria-pressed":!query && !category && collection==="recommended"}),
          button("完整库 · "+templates.length,()=>{setCollection("all");setLimit(6);},{"aria-pressed":!!query || !!category || collection==="all"}),
          h("select",{"aria-label":"模板分类",value:category,onChange:e=>{setCategory(e.target.value);setLimit(6);}},
            h("option",{value:""},"所有分类"),[...new Set(templates.map(t=>t.sourceCategory || t.category))].map(c=>h("option",{key:c,value:c},c)))),
        current ? h("div",{className:"dy-tpl-detail"},
          h("div",{className:"dy-tpl-lede"},h("h4",null,current.title),h("p",null,[current.style,current.slideCount+" 页"].filter(Boolean).join(" · ")),current.description && h("p",null,current.description),
            h(MotionPreview,{motion:current.motion,accepts:isTemplateAsset,open:motionOpen,toggle:()=>setMotionOpen(!motionOpen)})),
          editedPages.length>0 && h("div",{className:"dy-tpl-pages",role:"group","aria-label":"预览版本"},
            button("当前改稿",()=>{setShowOriginal(false);setPageNumber(null);},{"aria-pressed":showingEdits}),
            button("原稿对照",()=>{setShowOriginal(true);setPageNumber(null);},{"aria-pressed":!showingEdits})),
          !page && h("div",{className:"dy-tpl-lede"},fullBook?button("预览第 1 页",()=>turnTo(1),{disabled:!!busy}):h("p",null,"原稿没有现成代表图，选用后可逐页查看。")),
          page && h("figure",{"aria-label":showingEdits?"改稿实际预览":"模板原稿预览"},
            fullBook && (!state.personalized || showingEdits) && isTemplateAsset(page.preview)?
              h(RegionAnnotation,{key:page.preview,page:page.number,revision:state.revision,preview:page.preview,accepts:isTemplateAsset,cache:previewCache.current,
                disabled:!!busy || state.phase==="revising",annotation:state.annotation,submit:annotate}):preview(current,page,true)),
          h("div",{className:"dy-tpl-pages",role:"group","aria-label":showingEdits?"改稿实页":"原稿代表页"},fullBook ?
              h(React.Fragment,null,button("上一页",()=>turnTo((page?.number || 1)-1),{disabled:!!busy || (page?.number || 1)<=1}),
                h("select",{"aria-label":"跳转页码",value:page?.number || 1,disabled:!!busy,onChange:e=>turnTo(Number(e.target.value))},
                  Array.from({length:current.slideCount},(_,i)=>h("option",{key:i+1,value:i+1},"第 "+(i+1)+" 页"))),
                button("下一页",()=>turnTo((page?.number || 1)+1),{disabled:!!busy || (page?.number || 1)>=current.slideCount}))
            : pages.length<=8 ? pages.map(p=>
            button("第 "+p.number+" 页",()=>setPageNumber(p.number),{key:p.number,"aria-pressed":p.number===page?.number,title:p.label || undefined}))
            : h(React.Fragment,null,button("上一页",()=>setPageNumber(pages[pages.indexOf(page)-1].number),{disabled:page===pages[0]}),
                h("select",{"aria-label":"跳转页码",value:page.number,onChange:e=>setPageNumber(Number(e.target.value))},pages.map(p=>h("option",{key:p.number,value:p.number},"第 "+p.number+" 页"))),
                button("下一页",()=>setPageNumber(pages[pages.indexOf(page)+1].number),{disabled:page===pages.at(-1)}))))
        : matches.length ? h("div",{className:"dy-tpl-shelf"},matches.slice(0,limit).map(t=>
            h("button",{key:t.id,type:"button",className:"dy-tpl-tile",onClick:()=>{open(t.id);if(!t.pages?.length)run("正在读取代表页",async signal=>accept(await request(card,"preview",{templateId:t.id},signal,templateRoute)));},"aria-label":"查看"+t.title+"的代表页"},
              preview(t,t.pages?.[0]),h("strong",null,t.title),h("small",null,[t.category,t.slideCount+" 页",isTemplateAsset(t.motion?.url)?"有动作预览":null,state.selected===t.id?"已选用":null].filter(Boolean).join(" · ")))))
        : h("p",{className:"dy-tpl-empty"},!state && error ? "模板目录暂时不可用。" : fallback),
        h("footer",null,h("p",{role:error || state?.error?"alert":"status","aria-live":"polite",className:error || state?.error?"dy-tpl-alert":undefined},statusText()),
          error && button("重新载入",()=>setReload(n=>n+1),{disabled:!!busy}),
          !current && matches.length>limit && button("更多模板",()=>setLimit(n=>n+6)),
          !current && !matches.length && !!query && button("清空搜索",()=>{setQuery("");setLimit(6);}),
          fullBook && state.editHistoryAction && button(state.editHistoryAction==="undoEdit"?"撤回上次修改":"恢复上次修改",switchEdition,{disabled:!!busy}),
          current && (exported ? h("a",{className:"dy-tpl-action",download:state.filename || "模板.pptx",href:state.download,onClick:download},state.personalized ? "下载改稿 PPTX" : "下载整份 PPTX")
            : button("选用此模板",choose,{className:"dy-tpl-action",disabled:!!busy})))));
    }
    function persistedCard(event,type) {
      if(event.type==="ppt-studio/"+(type==="opening"?"opening":"templates"))return event.data;
      if(event.type==="command/done" && event.data?.kind==="success" && typeof event.data.commandId==="string") {
        const allowed=type==="opening"?["开场样页已就绪。","这两页开场采用示例材料。"]:["模板库已打开。"];
        if(allowed.includes(event.data.text))return {kind:type,...(Number.isSafeInteger(event.data.sourceEventSeq)?{anchorSeq:event.data.sourceEventSeq}:{commandId:event.data.commandId})};
      }
      if(event.type==="tool/result" && !event.data?.message?.isError){
        for(const part of event.data?.message?.content || []){
          if(part.type!=="text")continue;
          try{
            const data=JSON.parse(part.text);
            if(data.card?.kind===type && /^[a-f0-9-]{36}$/.test(data.card.taskId || ""))return {kind:type,taskId:data.card.taskId};
            if(/^[a-f0-9-]{36}$/.test(data.taskId || "") && Number.isSafeInteger(data.eventSeq) &&
              Array.isArray(type==="templates"?data.templates:data.variants))return {kind:type,taskId:data.taskId};
          }catch{}
        }
      }
      return null;
    }
    function cardDefinition(type,nodeKind) {
      return {kind:nodeKind,target:"chat",match(event){
        const card=persistedCard(event,type);
        return card?{id:card.taskId || "command:"+event.data.commandId,role:"start"}:null;
      },start:(_context,match)=>persistedCard(match.event,type),update:(context)=>context.state,
      buildViewNode(context){return context.start?{key:context.key,kind:nodeKind,id:context.id,target:"chat",anchorSeq:context.start.event.seq,
        location:{kind:"session"},visibility:"visible",data:context.state}:null;}};
    }
    function StoredCard({node,sessionId,type}) {
      const [card,setCard]=useState(node.data.token?node.data:null),[error,setError]=useState(""),[retry,setRetry]=useState(0);
      useEffect(()=>{
        if(node.data.token){setCard(node.data);return;}
        const controller=new AbortController();setError("");
        resolveCard({sessionId,kind:type,taskId:node.data.taskId,anchorSeq:node.data.anchorSeq,commandId:node.data.commandId},controller.signal)
          .then(c=>{if(!controller.signal.aborted)setCard(c);}).catch(e=>{if(!controller.signal.aborted)setError(e.message);});
        return ()=>controller.abort();
      },[sessionId,node.data.taskId,node.data.anchorSeq,node.data.commandId,retry]);
      if(!card)return h("div",{role:error?"alert":"status"},error || "正在恢复作品…",error && h("button",{onClick:()=>setRetry(n=>n+1)},"重试"));
      return type==="templates"?h(TemplateCard,{node:{data:card}}):h(Card,{node:{data:card}});
    }
    const OpeningStoredCard=props=>h(StoredCard,{...props,type:"opening"});
    const TemplateStoredCard=props=>h(StoredCard,{...props,type:"templates"});
    const definition=cardDefinition("opening",kind);
    const planKey = "ppt-studio-plan";
    const planTabKind = "ppt-studio-plan";
    const planRoute = "/api/ppt-studio.plan";
    const isPlanAsset = url => typeof url === "string" && url.startsWith("/api/ppt-studio.plan-asset?");
    const isCommunityPreview = url => typeof url === "string" && /^\/api\/ppt-studio\.community-preview\?id=[0-9a-f]{24}$/.test(url);
    const draftCache = new Map();
    const planQueues = new Map();
    const planEvents = new WeakMap();
    async function resolveCard(data,signal) {
      const response=await fetch("/api/ppt-studio.context",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(data),signal});
      const result=await response.json();
      if(!response.ok || !result.ok || !result.card)throw new Error(result.error || "无法读取当前会话的作品。");
      return result.card;
    }
    async function planCard(remote,sessionId,signal) {
      const command=await remote.commands.execute(sessionId,"/ppt-plan",[]);
      const result=command.value?.result;
      if(!command.ok || result?.kind!=="success")throw new Error(command.error?.message || result?.text || "无法打开此会话的 PPT 方案。");
      return resolveCard({sessionId,kind:"plan"},signal);
    }
    const planCss=`
      .dy-plan{--ink:#23304a;--weak:#5d6c83;--paper:#fff;--bg:#f1f4fa;--line:#d7dfed;--teal:#4658c6;--accent:#edf0ff;--white:#fff;--bad:#aa342a;--progress:#188b80;--motion:#7850aa;--focus:#ad742e;background:var(--paper);color:var(--ink);height:100%;min-height:0;overflow:auto;overscroll-behavior:contain;scroll-padding-block:64px 120px;container-type:inline-size;font:14px/1.6 "Instrument Sans","Microsoft YaHei UI",system-ui,sans-serif;text-align:left}
      [data-ds-dark-theme] .dy-plan{color-scheme:dark;--ink:#edf0fa;--weak:#adb9ce;--paper:#181f2d;--bg:#222d40;--line:#37465e;--teal:#b1bfff;--accent:#2d3859;--white:#19213d;--bad:#ffb2a7;--progress:#63d3bf;--motion:#d0b2f2;--focus:#e4b774}
      .dy-plan *{box-sizing:border-box}.dy-plan main{padding:22px;display:grid;gap:20px;min-width:0}.dy-plan h2,.dy-plan h3,.dy-plan p{margin:0}
      .dy-plan h2{font-size:clamp(18px,4.5cqw,22px);letter-spacing:-.02em;line-height:1.45;color:var(--ink);font-weight:700;overflow-wrap:anywhere}
      .dy-plan h3{font-size:15px;color:var(--ink)}.dy-plan p,.dy-plan small{font-size:13px;color:var(--weak);overflow-wrap:anywhere}
      .dy-plan header{display:flex;gap:5px;border-bottom:1px solid var(--line);padding:9px 16px 0;flex-wrap:wrap;background:var(--bg)}
      .dy-plan button,.dy-plan a{cursor:pointer;color:var(--ink);font:inherit;font-weight:580;background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:8px 12px;line-height:1.4;text-decoration:none}
      .dy-plan header button{padding:10px 12px;color:var(--weak);background:transparent;border:0;border-radius:7px 7px 0 0;font-size:14px;border-bottom:3px solid transparent}
      .dy-plan header button[aria-current=step]{color:var(--teal);border-color:var(--teal);background:var(--paper)}
      .dy-plan>header select.dy-size{align-self:center;margin:0 0 3px auto;width:auto;max-width:84px;padding:3px 5px;border-color:var(--line);font-size:12px;color:var(--weak)}
      .dy-plan :is(button,a,input,textarea,select,summary):focus-visible{outline:3px solid var(--teal);outline-offset:2px}
      .dy-plan button:disabled,.dy-plan input:disabled,.dy-plan select:disabled{opacity:.55;cursor:default}
      .dy-plan label,.dy-plan legend{font-weight:630;min-width:0}.dy-plan .dy-field{display:grid;gap:7px;align-content:start}.dy-plan :is(input:not([type=checkbox]),textarea,select){width:100%;min-width:0;max-width:100%;padding:9px 11px;color:var(--ink);border:1px solid var(--line);border-radius:7px;background:var(--paper);font:inherit;font-weight:400}
      .dy-plan textarea{resize:vertical;line-height:1.5}.dy-plan textarea::placeholder,.dy-plan input::placeholder{color:var(--weak);opacity:1}
      .dy-plan .dy-material textarea{min-height:148px;background:var(--bg);font-size:15px}
      .dy-plan .dy-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
      .dy-plan .dy-template-filters .dy-rowbuttons{margin-block:8px}.dy-plan .dy-template-filters{margin-bottom:12px}
      .dy-plan .dy-community,.dy-plan .dy-template-source{display:grid;gap:10px;min-width:0}
      .dy-plan .dy-community .dy-preview{overflow:hidden;background:var(--bg);border:1px solid var(--line);border-radius:8px}
      .dy-plan .dy-rowbuttons,.dy-plan .dy-file{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.dy-plan .dy-file{justify-content:space-between;border-bottom:1px solid var(--line);padding:5px 0;overflow-wrap:anywhere}
      .dy-plan .dy-file span{min-width:0;flex:1 1 90px}.dy-plan .dy-file button{font-size:12px;padding:3px 7px}
      .dy-plan .dy-strength{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0;min-width:0;background:var(--bg)}.dy-plan .dy-strength legend{padding:0 5px;margin-bottom:2px}
      .dy-plan .dy-strength div{display:flex;flex-wrap:wrap;gap:4px}.dy-plan .dy-strength button{flex:1;min-width:55px;white-space:normal;padding:6px;font-size:13px}
      .dy-plan .dy-strength input[type=range]{display:block;width:100%;height:24px;margin:0;padding:0;accent-color:var(--teal);cursor:pointer;border:0}
      .dy-plan .dy-strength .dy-range-labels{display:grid;grid-template-columns:1fr 1fr 1fr;gap:2px}
      .dy-plan .dy-range-labels button{border-color:transparent;background:transparent;padding:3px 0;min-width:0;font-size:12px}
      .dy-plan .dy-range-labels button:first-child{text-align:left}.dy-plan .dy-range-labels button:last-child{text-align:right}
      .dy-plan .dy-range-labels button[aria-pressed=true]{border-color:transparent;background:transparent;color:var(--teal);font-weight:740}
      .dy-plan .dy-strength .dy-caption{margin-top:7px;line-height:1.55;padding-inline-start:8px;border-inline-start:2px solid var(--teal)}
      .dy-plan :is(main,details,summary,.dy-modlist,.dy-field,.dy-grid>*,.dy-proof){min-inline-size:0}
      .dy-plan .dy-proof img{display:block;max-inline-size:100%}
      .dy-plan button[aria-pressed=true]{border-color:var(--teal);background:var(--accent);color:var(--teal)}
      .dy-plan .dy-modlist{border-block:1px solid var(--line)}.dy-plan details+details{border-top:1px solid var(--line)}
      .dy-plan details>summary{display:flex;align-items:baseline;gap:9px;cursor:pointer;padding:14px 2px;color:var(--ink);font-weight:620}
      .dy-plan details>summary:before{content:"›";font-size:17px;line-height:1;color:var(--teal)}.dy-plan details[open]>summary:before{transform:rotate(90deg)}
      .dy-plan summary small{font-weight:400;text-overflow:ellipsis;white-space:nowrap;overflow:hidden;margin-left:auto;max-width:63%}
      .dy-plan details>div{padding:2px 2px 16px;display:grid;gap:12px}
      .dy-plan .dy-page-template{display:grid;gap:7px;min-width:0;padding:15px 0;border-top:1px solid var(--line)}
      .dy-plan .dy-page-template>span{overflow-wrap:anywhere;font-size:13px}
      .dy-plan .dy-page-template b{color:var(--teal);margin-inline-end:6px}
      .dy-plan .dy-board{display:grid;gap:9px;border-top:1px solid var(--line);padding-top:14px;min-width:0}
      .dy-plan .dy-board-title,.dy-plan .dy-board-actions{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
      .dy-plan .dy-board-title h3{margin-right:auto}.dy-plan .dy-board-title button{font-size:12px}
      .dy-plan .dy-board-range{display:flex;flex-wrap:wrap;align-items:end;gap:6px}
      .dy-plan .dy-board-range label{font-size:12px;flex:1 1 56px}.dy-plan .dy-board-range select{width:100%}
      .dy-plan .dy-board-pages{list-style:none;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(216px,100%),1fr));gap:10px;margin:0;padding:0;align-items:start}
      .dy-plan .dy-board-page{display:grid;gap:9px;min-width:0;padding:12px;background:var(--bg);border:1px solid var(--line);border-radius:10px;overflow-wrap:anywhere}
      .dy-plan .dy-board-page h4{margin:0;font-size:14px;color:var(--ink);line-height:1.45}
      .dy-plan .dy-board-page small{font-variant-numeric:tabular-nums;color:var(--teal)}
      .dy-plan .dy-board-page .dy-motion{padding-inline-start:8px;border-inline-start:2px solid var(--motion);color:var(--motion)}
      .dy-plan .dy-board-page .dy-check{font-size:12px}
      .dy-plan .dy-style-guide{display:grid;gap:7px;padding:10px 12px;border-inline-start:3px solid var(--focus);background:var(--bg);border-radius:0 8px 8px 0;overflow-wrap:anywhere}
      .dy-plan .dy-style-guide strong,.dy-plan .dy-clip-context strong{font-size:13px;color:var(--ink)}
      .dy-plan .dy-style-guide details>summary{font-size:12px;padding:3px 0}
      .dy-plan .dy-clip-context{display:grid;gap:6px;min-width:0;flex-basis:100%}
      .dy-plan .dy-neighbors{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(110px,100%),1fr));gap:8px}
      .dy-plan .dy-neighbors figure{min-width:0;margin:0;background:var(--bg);border:1px solid var(--line);border-radius:5px;overflow:hidden}
      .dy-plan .dy-neighbors figcaption{display:grid;gap:3px;padding:5px 7px;overflow-wrap:anywhere;font-size:12px}
      .dy-plan .dy-neighbors figcaption small{font-size:11px}
      .dy-plan .dy-board-tiles{list-style:none;margin:0;padding:0;display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(min(118px,100%),1fr))}
      .dy-plan .dy-board-tiles li{min-width:0}
      .dy-plan .dy-board-tile{display:grid;grid-template-rows:auto auto 1fr;gap:3px;width:100%;height:100%;padding:4px;text-align:left;background:var(--bg);align-content:start}
      .dy-plan .dy-board-tile small{color:var(--teal);font-size:11px;overflow-wrap:anywhere}
      .dy-plan .dy-tile-title{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;overflow-wrap:anywhere;font-size:12px}
      .dy-plan .dy-tile-empty{display:grid;place-items:center;aspect-ratio:16/9;border:1px dashed var(--line);font-size:11px;color:var(--weak)}
      .dy-plan .dy-check{display:flex;align-items:center;gap:6px;font-size:13px}.dy-plan input[type=checkbox]{accent-color:var(--teal)}
      .dy-plan footer{display:grid;gap:10px;padding:14px 22px;border-top:1px solid var(--line);background:var(--bg)}
      .dy-plan>header,.dy-plan>footer{position:sticky;z-index:2}.dy-plan>header{top:0}.dy-plan>footer{bottom:0}
      @supports(backdrop-filter:blur(6px)){.dy-plan>header,.dy-plan>footer{background:color-mix(in srgb,var(--bg) 96%,transparent);backdrop-filter:blur(6px)}}
      .dy-plan .dy-mainbtn{background:var(--teal);color:var(--white);border-color:var(--teal);text-align:center}.dy-plan .dy-alert{color:var(--bad)}
      .dy-plan .dy-meter{width:100%;height:6px;border:0;border-radius:8px;overflow:hidden;appearance:none;background:var(--bg);accent-color:var(--progress)}.dy-plan progress::-webkit-progress-bar{background:var(--bg)}.dy-plan progress::-webkit-progress-value{background:var(--progress)}
      .dy-plan .dy-proof{border:1px solid var(--line);border-radius:9px;overflow:hidden;background:var(--bg)}.dy-plan .dy-preview{display:grid;place-items:center;aspect-ratio:16/9;font-size:12px;color:var(--weak)}.dy-plan .dy-preview img{width:100%;height:100%;object-fit:contain}
      @media(prefers-reduced-motion:no-preference){.dy-plan :is(button,a){transition:background-color .13s,color .13s,border-color .13s}.dy-plan progress::-webkit-progress-value{transition:width .18s ease-out}}
      @container(max-width:380px){.dy-plan main{padding:16px;gap:18px}.dy-plan footer{padding:12px 16px}.dy-plan .dy-grid{grid-template-columns:1fr}.dy-plan header{padding-inline:9px}.dy-plan header button{padding-inline:9px}.dy-plan .dy-board-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @container(max-width:280px){.dy-plan main,.dy-plan footer{padding:10px}.dy-plan header{padding-inline:4px}.dy-plan header button{padding-inline:5px}}
    `;
    const widthPreference = "dsh-ppt-studio.panel-width.v1";
    function savedWidth() {
      try {const value=localStorage.getItem(widthPreference);if(value==="wide" || value==="host")return value;}catch{}
      return "wide";
    }
    function usePanelWidth(root,visible) {
      const id=useId().replace(/[^a-z0-9_-]/gi,"");
      const [mode,setMode]=useState(savedWidth),[left,setLeft]=useState(null);
      React.useLayoutEffect(()=>{
        const element=root.current,column=element?.closest("[data-rightbar-col]"),frame=column?.parentElement;
        const panel=element?.closest("[data-sidebar-right-panel]");
        if(!visible || !frame || !panel || element.closest("[data-dockkit-float]")){setLeft(null);return;}
        // The SDK exposes tab visibility but not a per-tab column width. Read the native
        // left track; a scoped stylesheet adjusts only the live, single-pane PPT dock.
        function measure(){
          const first=/^(\d+(?:\.\d+)?)px\s/.exec(frame.style.gridTemplateColumns || getComputedStyle(frame).gridTemplateColumns);
          const paneIds=new Set([...panel.querySelectorAll("[data-dockkit-pane]")].filter(n=>
            !n.closest("[hidden],[data-dockkit-float]")).map(n=>n.getAttribute("data-dockkit-pane")));
          const eligible=first && panel.dataset.sidebarRightPanel==="push" && panel.hasAttribute("data-sidebar-right-open") &&
            !element.closest("[hidden],[aria-hidden=true]") && !frame.hasAttribute("data-rightbar-collapsed") &&
            paneIds.size<=1;
          setLeft(eligible?Number(first[1]):null);
        }
        measure();
        const geometry=new MutationObserver(measure);
        geometry.observe(frame,{attributes:true,attributeFilter:["style","data-rightbar-collapsed","data-rightbar-fullscreen"]});
        geometry.observe(panel,{attributes:true,attributeFilter:["data-sidebar-right-panel","data-sidebar-right-open"]});
        const panes=new MutationObserver(records=>{
          const pane="[data-dockkit-pane]";
          if(records.some(r=>[...r.addedNodes,...r.removedNodes].some(n=>n.nodeType===1 && (n.matches(pane) || n.querySelector(pane)))))measure();
        });
        panes.observe(panel,{childList:true,subtree:true});
        return ()=>{geometry.disconnect();panes.disconnect();};
      },[root,visible]);
      const target='[data-dy-size-scope="'+id+'"]',frame=':has(> [data-rightbar-col] '+target+')';
      const fixed=left!==null && mode!=="host";
      const css=fixed?`@media(min-width:768px){
        ${frame}{grid-template-columns:${left}px minmax(0,1fr) min(${mode==="wide"?560:344}px,max(280px,calc(100% - ${left+400}px)),calc(100% - ${left}px))!important}
        [data-sidebar-right-panel="push"]:has(${target}){width:100%!important;--dsh-sidebar-width:100%!important}
        ${frame}>[data-side="rightbar"]{display:none}
      }`:"";
      const control=left!==null && h("select",{className:"dy-size","aria-label":"面板宽度",title:"面板宽度",value:mode,onChange:e=>{
        const value=e.target.value;setMode(value);try{localStorage.setItem(widthPreference,value);}catch{}
      }},h("option",{value:"compact"},"紧凑"),h("option",{value:"wide"},"宽览"),h("option",{value:"host"},"手动拖动"));
      return {id,css,control};
    }
    function PlanTab({sessionId,getCard,useTabInfo=()=>null}) {
      const info=useTabInfo();
      return h(PlanPanel,{key:sessionId,sessionId,getCard,visible:info?info.tab.visible:true});
    }
    const regionDrafts = new Map();
    function RegionAnnotation({page,revision,preview,disabled,submit,annotation,accepts=isPlanAsset,cache,draftKey=preview,onStart}) {
      const frame=useRef(null), drag=useRef(null), sending=useRef(false);
      const matchesRejected=!!(annotation?.canSendTextOnly && annotation.page===page && annotation.preview===preview);
      const recovered=matchesRejected ? (annotation.regions || [annotation]).map(({rect,text})=>({rect,text})) : null;
      const [draft,setDraft]=useState(()=>regionDrafts.get(draftKey) || (recovered ? {regions:recovered,active:0,preview} : null));
      const needsReview=!!draft?.preview && draft.preview!==preview;
      const [live,setLive]=useState(null),[sendingNow,setSending]=useState(false),[notice,setNotice]=useState("");
      const [rejectedBatch,setRejectedBatch]=useState("");
      const current=draft?.regions[draft.active];
      const regions=draft?.regions.map(({rect,text})=>({rect,text:text.trim()})) || [];
      const signature=JSON.stringify(regions);
      const complete=regions.length>0 && regions.every(r=>r.rect && r.text);
      const persist=next=>{
        if(next){next={preview:draft?.preview || preview,...next};regionDrafts.set(draftKey,next);}else regionDrafts.delete(draftKey);
        setDraft(next);
      };
      const locked=disabled || sendingNow;
      function changeCurrent(changes) {
        persist({...draft,regions:draft.regions.map((r,i)=>i===draft.active ? {...r,...changes} : r)});
      }
      function removeCurrent() {
        const remaining=draft.regions.filter((_,i)=>i!==draft.active);
        persist(remaining.length ? {regions:remaining,active:Math.min(draft.active,remaining.length-1)} : null);
      }
      function position(event) {
        const img=frame.current?.querySelector("img");
        if(!img?.complete || !img.naturalWidth)return null;
        const bounds=img.getBoundingClientRect();
        if(!bounds.width || !bounds.height)return null;
        const clamp=n=>Math.min(1,Math.max(0,n));
        return {x:clamp((event.clientX-bounds.left)/bounds.width),y:clamp((event.clientY-bounds.top)/bounds.height)};
      }
      function area(a,b) {
        return {x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),w:Math.abs(b.x-a.x),h:Math.abs(b.y-a.y)};
      }
      function begin(event) {
        if(!draft || locked || !event.isPrimary || event.button!==0 || event.target.closest("button"))return;
        const start=position(event);
        if(!start)return;
        event.preventDefault();event.currentTarget.setPointerCapture(event.pointerId);
        drag.current={start,id:event.pointerId};setLive(null);setNotice("");
      }
      function move(event) {
        const end=position(event);
        if(!drag.current || drag.current.id!==event.pointerId || !end)return;
        setLive(area(drag.current.start,end));
      }
      function end(event) {
        const active=drag.current;
        if(!active || event.pointerId!==active.id)return;
        drag.current=null;setLive(null);
        if(event.currentTarget.hasPointerCapture(active.id))event.currentTarget.releasePointerCapture(active.id);
        const end=position(event);
        if(!end || locked)return;
        const rect=area(active.start,end);
        if(rect.w<.01 || rect.h<.01){setNotice("请拖出稍大的区域。");return;}
        changeCurrent({rect});
      }
      function cancelDrag(event) {
        if(drag.current?.id===event.pointerId){drag.current=null;setLive(null);}
      }
      async function sendNote(textOnly=false) {
        if(sending.current || locked || !complete || needsReview)return;
        sending.current=true;setSending(true);setNotice("");
        try {
          const next=await submit({page,revision,preview,regions,...(regions.length===1 && regions[0]),...(textOnly && {textOnly:true})});
          if(next?.phase==="revising" && next.annotation?.sent===true) {
            persist(null);setRejectedBatch("");setNotice("第 "+page+" 页的批注已发送。");
          } else {
            setRejectedBatch(next?.annotation?.canSendTextOnly===true ? signature : "");
            setNotice(next?.error || "宿主尚未确认发送，批注已保留。");
          }
        } catch(e) {
          setNotice(e?.message || "发送失败，批注已保留。");
        } finally {sending.current=false;setSending(false);}
      }
      const rect=live || current?.rect;
      const canRetry=signature===rejectedBatch || (recovered && signature===JSON.stringify(recovered));
      const submitted=annotation?.page===page && annotation.sent && annotation.regions?.length>1 ? annotation.regions : null;
      const style=`
        .dy-region .dy-r-stage{position:relative;overflow:hidden;border-radius:5px;background:var(--bg)}
        .dy-region .dy-r-stage[data-mark=true]{touch-action:none;cursor:crosshair;user-select:none}
        .dy-region .dy-r-stage .dy-preview:has(img){display:block;aspect-ratio:auto}
        .dy-region .dy-r-stage .dy-preview img{display:block;width:100%;height:auto;pointer-events:none}
        .dy-region .dy-r-box{position:absolute;pointer-events:none;box-sizing:border-box;border:2px dashed #3a438a;outline:1px solid #fff}
        .dy-region .dy-r-box[data-active=true]{border:2px solid #2347d8;background:rgba(79,103,255,.12)}
        .dy-region .dy-r-box span{display:block;width:max-content;padding:1px 5px;background:#253876;color:white;font:bold 11px/1.5 sans-serif}
        .dy-region .dy-r-actions button[aria-pressed=true]{outline:2px solid var(--accent,currentColor);outline-offset:-2px}
        .dy-region .dy-r-actions{display:flex;flex-wrap:wrap;align-items:center;gap:5px;margin-top:7px}.dy-region .dy-r-actions button{width:auto}
        .dy-region .dy-r-editor{display:grid;gap:6px;margin-top:7px}.dy-region .dy-r-editor textarea{resize:vertical;min-height:50px;width:100%;box-sizing:border-box}
        .dy-region .dy-r-note{font-size:12px;color:var(--weak);margin:4px 0}
        .dy-region .dy-r-receipt{font-size:12px;margin-top:6px;overflow-wrap:anywhere}
        .dy-region .dy-r-receipt summary{cursor:pointer}.dy-region .dy-r-receipt ol{padding-inline-start:1.5em}
      `;
      return h("section",{className:"dy-region","aria-label":"第 "+page+" 页批注"},
        h("style",null,style),
        h("div",{className:"dy-proof dy-r-stage",ref:frame,"data-mark":!!draft && !locked,
          onPointerDown:begin,onPointerMove:move,onPointerUp:end,onPointerCancel:cancelDrag,onLostPointerCapture:cancelDrag},
          h(Preview,{url:preview,label:"成稿第 "+page+" 页",accepts,retry:true,cache}),
          draft?.regions.map((r,i)=>{
            const box=i===draft.active ? rect : r.rect;
            return box && h("div",{key:i,className:"dy-r-box","data-active":i===draft.active,"aria-hidden":true,
              style:{left:box.x*100+"%",top:box.y*100+"%",width:box.w*100+"%",height:box.h*100+"%"}},h("span",null,i+1));
          })),
        !draft ? h("div",{className:"dy-r-actions"},h("button",{type:"button",disabled:locked,onClick:()=>{onStart?.();setNotice("");persist({active:0,regions:[{rect:null,text:""}]});}},"区域批注"))
          : h("div",{className:"dy-r-editor"},
              needsReview && h("div",{role:"status"},"这一页已有新版，已保留批注草稿。",h("button",{type:"button",disabled:locked,onClick:()=>persist({...draft,preview})},"已核对新版选区")),
              draft.regions.length>1 && h("div",{className:"dy-r-actions",role:"group","aria-label":"切换批注区域"},
                draft.regions.map((r,i)=>h("button",{key:i,type:"button",disabled:locked,"aria-pressed":draft.active===i,
                  onClick:()=>{persist({...draft,active:i});setNotice("");},title:r.text || "待填写"},"区域 "+(i+1)))),
              h("div",{className:"dy-r-actions"},h("span",{className:"dy-r-note"},rect?"已框选，可重新拖动":"在预览上拖出要修改的区域"),
                h("button",{type:"button",disabled:locked,onClick:()=>{
                  if(!frame.current?.querySelector("img")?.naturalWidth){setNotice("请等预览载入后再选择。");return;}
                  changeCurrent({rect:{x:0,y:0,w:1,h:1}});
                }},"选择整页"),
                draft.regions.length>1 && h("button",{type:"button",disabled:locked,onClick:removeCurrent},"移除此处")),
              h("textarea",{"aria-label":"第 "+page+" 页修改要求",placeholder:"希望这里怎么改？",rows:2,maxLength:2400,disabled:locked,
                value:current.text,onChange:event=>changeCurrent({text:event.target.value})}),
              h("div",{className:"dy-r-actions"},
                h("button",{type:"button",disabled:locked || !complete || regions.length>=20,onClick:()=>{
                  persist({active:draft.regions.length,regions:[...draft.regions,{rect:null,text:""}]});setNotice("");
                }},"再框一处"),
                h("button",{type:"button",className:"dy-mainbtn",disabled:locked || !complete || needsReview,onClick:()=>sendNote(false)},
                  sendingNow?"发送中…":regions.length>1 ? "发送 "+regions.length+" 处批注" : "发送批注"),
                canRetry && h("button",{type:"button",disabled:locked || !complete || needsReview,onClick:()=>sendNote(true)},"仅发文字和坐标"),
                h("button",{type:"button",disabled:locked,onClick:()=>{persist(null);setNotice("");setRejectedBatch("");}},"取消批注"))),
        !draft && submitted && h("details",{className:"dy-r-receipt"},
          h("summary",null,"查看已提交的 "+submitted.length+" 处批注"),
          h("ol",null,submitted.map((r,i)=>h("li",{key:i},r.text,
            r.changed && h("p",{className:"dy-r-note"},r.changed.length?"已更新 "+r.changed.map(o=>o.name || o.id).join("、"):"此区域没有对象改动记录"))))),
        notice && h("p",{role:"status",className:"dy-r-note"},notice));
    }
    async function dictationWave(blob,context) {
      const decoded=await context.decodeAudioData(await blob.arrayBuffer());
      const length=Math.max(1,Math.round(16000*Math.min(90,decoded.duration)));
      const offline=new OfflineAudioContext(1,length,16000);
      const source=offline.createBufferSource();
      source.buffer=decoded;source.connect(offline.destination);source.start();
      const samples=(await offline.startRendering()).getChannelData(0);
      const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
      const tag=(at,value)=>{for(let i=0;i<value.length;i++)view.setUint8(at+i,value.charCodeAt(i));};
      tag(0,"RIFF");view.setUint32(4,buffer.byteLength-8,true);tag(8,"WAVEfmt ");
      view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);
      view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);
      view.setUint16(34,16,true);tag(36,"data");view.setUint32(40,buffer.byteLength-44,true);
      for(let i=0;i<samples.length;i++)view.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,samples[i]))*32767),true);
      return buffer;
    }
    function MaterialVoice({card,disabled,onText,onBusy}) {
      const active=useRef(null), callback=useRef(onText);
      callback.current=onText;
      const [phase,setPhase]=useState(""),[notice,setNotice]=useState("");
      function release(job) {
        clearTimeout(job.timer);
        job.stream?.getTracks().forEach(track=>track.stop());
        if(job.context && job.context.state!=="closed")job.context.close().catch(()=>{});
      }
      function cancel(update=true) {
        const job=active.current;
        if(!job)return;
        active.current=null;job.control.abort();clearTimeout(job.timer);
        if(job.recorder?.state==="recording")job.recorder.stop();
        release(job);onBusy(false);
        if(update){setPhase("");setNotice("");}
      }
      useEffect(()=>()=>cancel(false),[]);
      async function start(){
        if(active.current || disabled)return;
        const job={control:new AbortController(),chunks:[]};active.current=job;
        onBusy(true);setPhase("asking");setNotice("");
        function finish(message) {
          if(active.current!==job)return;
          cancel();setNotice(message);
        }
        try{
          if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !window.AudioContext || !window.OfflineAudioContext)throw new Error("此窗口无法录音，请在 Harness 桌面端打开。");
          job.context=new AudioContext();
          job.stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1}});
          if(active.current!==job){release(job);return;}
          const recorder=new MediaRecorder(job.stream);
          job.recorder=recorder;
          recorder.ondataavailable=e=>{if(e.data.size && active.current===job)job.chunks.push(e.data);};
          recorder.onerror=()=>finish("录音中断，请重新录制。");
          recorder.onstop=async()=>{
            if(active.current!==job)return;
            clearTimeout(job.timer);job.stream.getTracks().forEach(track=>track.stop());setPhase("transcribing");
            try{
              const wave=await dictationWave(new Blob(job.chunks,{type:recorder.mimeType}),job.context);
              if(job.control.signal.aborted)return;
              const response=await fetch(planRoute+"-dictation",{method:"POST",headers:{"content-type":"audio/wav","x-ppt-session":card.sessionId,"x-ppt-task":card.taskId,"x-ppt-token":card.token},body:wave,signal:job.control.signal});
              const result=await response.json();
              if(!response.ok || !result.ok)throw new Error(result.error || "语音转写失败，请重试。");
              if(job.control.signal.aborted)return;
              const words=(result.text || "").trim();
              if(!words){finish("没有听清，请再说一次。");return;}
              callback.current(words);
              finish("已加入演示材料，可继续修改。");
            }catch(e){finish(e.message || "语音转写失败，请重试。");}
          };
          recorder.start();setPhase("recording");
          job.timer=setTimeout(()=>{if(recorder.state==="recording")recorder.stop();},90000);
        }catch(e){finish(e.name==="NotAllowedError"?"麦克风权限未开启，请允许 Harness 使用麦克风。":e.name==="NotFoundError"?"未找到麦克风，请连接设备后重试。":e.message);}
      }
      return h("div",{className:"dy-rowbuttons",style:{marginTop:6}},
        h("button",{type:"button",disabled:disabled || phase==="asking" || phase==="transcribing",onClick:()=>{if(!phase)start();else if(active.current?.recorder?.state==="recording")active.current.recorder.stop();}},
          phase==="recording"?"停止并转写":phase==="asking"?"等待麦克风…":phase==="transcribing"?"正在转写…":"语音输入"),
        phase && h("button",{type:"button",onClick:()=>cancel()},"取消录音"),
        h("span",{role:"status",style:{fontSize:"12px"}},phase==="recording"?"正在录音 · 最长 90 秒":notice));
    }
    function PlanPanel({sessionId,getCard,visible}) {
      const root=useRef(null),width=usePanelWidth(root,visible);
      const [state,setState]=useState(null),[card,setCard]=useState(null),[step,setStep]=useState("materials"),[imported,setImported]=useState(null);
      const [draft,setDraft]=useState(()=>draftCache.get(sessionId) || {});
      const edits=useRef(draft), alive=useRef(false), polling=useRef(false), pending=useRef(false);
      const server=useRef(null), lastPhase=useRef(null), filePicker=useRef(null), cardRef=useRef(null), timer=useRef(null);
      const [busy,setBusy]=useState(""),[error,setError]=useState(""),[attempt,setAttempt]=useState(0),[page,setPage]=useState(0);
      const pinnedPageId=useRef(null),deliveryInput=useRef(null);
      const [fileCount,setFileCount]=useState(0),[extractNote,setExtractNote]=useState("");
      const [communityCode,setCommunityCode]=useState("");
      const [communityNote,setCommunityNote]=useState("");
      const [communityRows,setCommunityRows]=useState(null),[communityError,setCommunityError]=useState(false),[communityAttempt,setCommunityAttempt]=useState(0);
      const [communityQuery,setCommunityQuery]=useState(""),[communityVersion,setCommunityVersion]=useState("");
      const [libraryOnly,setLibraryOnly]=useState(false);
      const [templateSource,setTemplateSource]=useState("community");
      const [boardCollapsed,setBoardCollapsed]=useState(false),[boardNotice,setBoardNotice]=useState("");
      const [pendingLock,setPendingLock]=useState(null);
      const [clip,setClip]=useState(null),[clipStart,setClipStart]=useState(1);
      const [browseTemplate,setBrowseTemplate]=useState("");
      const [templateQuery,setTemplateQuery]=useState(""),[templateCategory,setTemplateCategory]=useState(""),[templateCollection,setTemplateCollection]=useState("recommended"),[templateLimit,setTemplateLimit]=useState(48);
      useEffect(()=>{if(visible===false)setClip(null);},[visible]);
      const [boardMode,setBoardMode]=useState("overview"),[detailPage,setDetailPage]=useState(0);
      const jumpPage=useRef(0);
      const boardImageCache=useRef(new Map());
      useEffect(()=>{
        const n=jumpPage.current;
        if(!n)return;
        jumpPage.current=0;
        const target=root.current?.querySelector(boardMode==="overview"?'[data-board-tile="'+n+'"]':'[data-board-title="'+n+'"]');
        if(!target)return;
        target.focus({preventScroll:true});
        const pane=root.current;
        pane.scrollTop+=target.getBoundingClientRect().top-pane.getBoundingClientRect().top-pane.querySelector("header").offsetHeight-12;
      },[boardMode]);
      const [range,setRange]=useState({start:1,end:1});
      const communityWindow=useRef(null);
      const [dictating,setDictating]=useState(false);
      function updateDraft(next) {
        edits.current=next;
        if(Object.keys(next).length) draftCache.set(sessionId,next);else draftCache.delete(sessionId);
        if(alive.current)setDraft(next);
      }
      function merge(fields){updateDraft({...edits.current,...fields});setError("");setBoardNotice("");}
      function accept(next,initial=false) {
        if(!next?.phase)throw new Error("未能读取制作状态，请重新载入。");
        server.current=next;
        if(!alive.current)return;
        setState(next);
        const production=["producing","paused","ready","revising"].includes(next.phase) || (initial && next.production?.built>0);
        if(initial || next.phase!==lastPhase.current) {
          if(production)setStep("production");
          else if(next.phase==="recommended" || next.phase==="adopted" || (initial && (next.plan || next.suggestion))){
            setStep("plan");
          }
        }
        lastPhase.current=next.phase;
      }
      function queue(work) {
        const job=(planQueues.get(sessionId) || Promise.resolve()).catch(()=>{}).then(work);
        planQueues.set(sessionId,job);
        return job.finally(()=>{if(planQueues.get(sessionId)===job)planQueues.delete(sessionId);});
      }
      function write(c,action,fields) {
        return request(c,action,fields,new AbortController().signal,planRoute);
      }
      function clean(fields){
        if(!alive.current && draftCache.get(sessionId)!==edits.current)return;
        const left={...edits.current};
        for (const key of Object.keys(fields)) if(left[key]===fields[key])delete left[key];
        updateDraft(left);
      }
      async function savePending(c) {
        const fields={...edits.current};if(!Object.keys(fields).length)return;
        const next=await write(c,"save",{...fields,revision:server.current.revision});
        accept(next);clean(fields);
      }
      useEffect(()=>{
        const controller=new AbortController();alive.current=true;setError("");
        (async()=>{
          const c=await getCard(sessionId,controller.signal);
          if(controller.signal.aborted)return;
          const initial=await queue(()=>request(c,"state",{},controller.signal,planRoute));
          if(controller.signal.aborted)return;
          cardRef.current=c;setCard(c);accept(initial,true);
        })().catch(e=>{if(!controller.signal.aborted)setError(e.message);});
        return ()=>{
          alive.current=false;controller.abort();
          const c=cardRef.current;
          if(c && Object.keys(edits.current).length)queue(()=>savePending(c)).catch(()=>{});
        };
      },[sessionId,attempt]);
      const showCommunity=!!state?.communityOrigin && visible!==false && (step==="materials" || step==="plan" && templateSource==="community");
      useEffect(()=>{
        if(!showCommunity || communityRows!==null)return;
        const controller=new AbortController();setCommunityError(false);
        fetch("/api/ppt-studio.community-catalog",{signal:controller.signal}).then(async response=>{
          if(!response.ok)throw new Error();
          const data=await response.json();
          if(!Array.isArray(data.items))throw new Error();
          if(!controller.signal.aborted)setCommunityRows(data.items);
        }).catch(()=>{if(!controller.signal.aborted)setCommunityError(true);});
        return ()=>controller.abort();
      },[showCommunity,communityRows,communityAttempt]);
      useEffect(()=>{
        if(!card || !Object.keys(draft).length)return;
        timer.current=setTimeout(()=>queue(()=>savePending(card)).catch(e=>{if(alive.current)setError(e.message);}),550);
        return ()=>clearTimeout(timer.current);
      },[draft,card]);
      useEffect(()=>{
        if(!card || visible===false || (!["recommending","producing","paused","revising"].includes(state?.phase) && !(state?.phase==="ready" && step==="production")))return;
        const controller=new AbortController();
        async function poll(){
          if(polling.current || pending.current || controller.signal.aborted)return;
          polling.current=true;
          try {
            await queue(async()=>{
              if(controller.signal.aborted)return;
              const next=await request(card,"state",{},controller.signal,planRoute);
              if(!controller.signal.aborted){accept(next);setError("");}
            });
          } catch(e){if(!controller.signal.aborted)setError(e.message);}
          finally{polling.current=false;}
        }
        const interval=setInterval(poll,1200);
        return ()=>{clearInterval(interval);controller.abort();};
      },[card,state?.phase,step,visible]);
      async function act(label,work){
        if(!card || pending.current)return;
        pending.current=true;setBusy(label);setError("");clearTimeout(timer.current);
        try{await queue(async()=>{await savePending(card);await work();});}
        catch(e){if(alive.current)setError(e.message);}
        finally{pending.current=false;if(alive.current)setBusy("");}
      }
      function send(action,fields={}) {return write(card,action,{revision:server.current.revision,...fields}).then(next=>{accept(next);return next;});}
      function selectCommunity(version) {
        return act("正在领取授权模板",async()=>{
          const next=await send("useCommunity",{version:version.trim(),libraryOnly});
          setCommunityCode("");setCommunityNote(libraryOnly?"已加入本次备选，可在方案的逐页提纲中选用。":"已选用共享模板。推荐和制作将使用当前会话中的副本。");
          if(next.plan && !libraryOnly)setStep("plan");
        });
      }
      useEffect(()=>{
        function selected(event) {
          if(!communityWindow.current || event.source!==communityWindow.current || event.origin!==state?.communityOrigin ||
             event.data?.kind!=="ppt-template-selected" || !/^[0-9a-f]{24}$/.test(event.data.id))return;
          if(pending.current || ["recommending","producing","revising"].includes(server.current?.phase)){
            setCommunityCode(event.data.id);setError("请在当前操作结束后点「选用」。");return;
          }
          selectCommunity(event.data.id);
        }
        window.addEventListener("message",selected);return ()=>window.removeEventListener("message",selected);
      },[card,state?.communityOrigin,libraryOnly]);
      function openImport(f) {
        return act("正在导入完整 PPTX",async()=>{
          const next=await send("import",{fileId:f.id});
          const ref=next.templateCard;
          if(!ref?.token || ref.sessionId!==sessionId || ref.taskId!==next.openedTemplateTaskId)throw new Error("未能打开导入稿，请重试。");
          if(alive.current){setImported({...ref,embedded:true});setStep("import");}
        });
      }
      function extractText(f) {
        return act("正在按页提取正文",async()=>{
          const result=await write(card,"extractText",{revision:server.current.revision,fileId:f.id});
          if(!alive.current)return;
          if(typeof result.text!=="string" || !result.text.trim()){
            setExtractNote("这份 PPTX 没有可提取的正文。");return;
          }
          const current=edits.current.materials ?? server.current.materials ?? "";
          const block=f.name+"\n"+result.text.trim();
          if(current.includes(block)){setExtractNote("这份 PPTX 的正文已在材料框中。");return;}
          const separator=current?"\n\n":"";
          const space=60000-current.length-separator.length;
          if(space<=f.name.length+1){setExtractNote("材料框已满，请先精简已有内容。");return;}
          merge({materials:current+separator+block.slice(0,space)});
          const limited=result.truncated || block.length>space;
          setExtractNote("已读取 "+result.pagesRead+" / "+result.slides+" 页"+(limited?"，已放入可容纳的正文。":"。")+"可先修改，再点推荐。");
        });
      }
      const materials=draft.materials ?? state?.materials ?? "";
      const plan=draft.plan || state?.plan || state?.suggestion;
      const files=state?.files || [], progress=state?.production, history=progress?.history || [];
      const selectedPage=(page && (history.find(item=>item.pageId===pinnedPageId.current) || history.find(item=>item.page===page))) || history.at(-1);
      const pinPage=row=>{pinnedPageId.current=row?.pageId || null;setPage(row?.page || 0);};
      const running=state?.phase==="producing", recommending=state?.phase==="recommending";
      const revising=state?.phase==="revising";
      const locked=!!busy || running || recommending || revising || !state;
      const setPlan=(key,value)=>{
        const next={...plan,[key]:value};
        if(key==="template") {
          next.mainChoice="user";
          if(next.pageTemplates)next.pageTemplates=next.pageTemplates.map(row=>{
            if(row.origin==="ai" && (!value || row.template===plan.template))
              return {page:row.page,template:value,origin:"inherit"};
            return row.origin==="inherit" || row.followDefault?{...row,template:value}:row;
          });
        }
        merge({plan:next});
      };
      const choices=[["grounded","稳妥"],["balanced","均衡"],["bold","大胆"]];
      const formId=useId();
      const field=(name,control)=>h("label",{className:"dy-field"},name,typeof control.type==="string"?React.cloneElement(control,{"aria-label":name}):control);
      const button=(label,onClick,props={})=>h("button",{type:"button",onClick,...props},label);
      function planInput(key,label,options) {return field(label,h(React.Fragment,null,
        h("input",{value:plan[key] || "",disabled:locked,list:options?formId+key:undefined,onChange:e=>setPlan(key,e.target.value)}),
        options && h("datalist",{id:formId+key},options.map(s=>h("option",{key:s,value:s})))));}
      function collapser(title,summary,...children){
        return h("details",{onToggle:e=>{
          const details=e.currentTarget;
          if(e.target===details && !details.open && details.querySelector("[data-motion-active]"))setClip(null);
        }},h("summary",null,title,h("small",null,summary || "")),h("div",null,...children));
      }
      const templates=state?.templates || [];
      const pageTemplates=plan?.pageTemplates || [];
      const staleBoard=!!state?.storyboardStale || !!state?.storyboard && (
        !!draft.plan && JSON.stringify(draft.plan)!==JSON.stringify(state.plan || state.suggestion) ||
        draft.materials!==undefined && draft.materials!==state.materials);
      const boardPages=staleBoard?null:state?.storyboard?.pages;
      const savedPlan=state?.plan || state?.suggestion;
      const stylePending=!!draft.plan && ["style","template","pageTemplates","pageCount","outline"].some(key=>
        JSON.stringify(draft.plan[key])!==JSON.stringify(savedPlan?.[key]));
      const guide=stylePending?null:state?.styleGuide;
      const fitById=new Map((guide?.templates || []).map(item=>[item.id,item]));
      const fitGroups=[["anchor","主模板"],["close","风格相近"],["review","需对照原页"],["contrast","风格差异明显"]];
      const fitLabel=level=>fitGroups.find(([key])=>key===level)?.[1];
      const selfDesignedPage=":self-design";
      function templateName(id) {
        if(!id)return "自行设计";
        return templates.find(t=>t.id===id)?.title || "已移出的模板";
      }
      function planWithPages(base,assignments) {
        const {pageTemplates:previous,...rest}=base;
        return assignments.length?{...rest,pageTemplates:assignments}:rest;
      }
      function assignPage(number,id) {
        if(clip?.from===number)setClip(null);
        const assignments=pageTemplates.filter(t=>t.page!==number);
        assignments.push(id?{page:number,template:id===selfDesignedPage?"":id}:
          {page:number,template:plan.template || "",followDefault:true});
        merge({plan:planWithPages(plan,assignments.sort((a,b)=>a.page-b.page))});
      }
      const templateWords=templateQuery.trim().toLocaleLowerCase().split(/\s+/u).filter(Boolean);
      const matchedTemplates=templates.filter(t=>(templateWords.length || templateCategory || templateCollection==="all" || t.recommended!==false) &&
        (!templateCategory || t.category===templateCategory || t.sourceCategory===templateCategory) && templateWords.every(word=>[t.title,t.category,t.sourceCategory,t.style,t.summary].join(" ").toLocaleLowerCase().includes(word)));
      const selectedIds=new Set([plan?.template,...pageTemplates.map(p=>p.template)].filter(Boolean));
      const visibleTemplates=[...new Map([...templates.filter(t=>selectedIds.has(t.id)),...matchedTemplates.slice(0,templateLimit)].map(t=>[t.id,t])).values()];
      const templateGroups=[
        ["本地模板",visibleTemplates.filter(t=>t.category!=="本次上传" && t.category!=="共享模板")],
        ["本次上传",visibleTemplates.filter(t=>t.category==="本次上传")],
        ["已选入的社区模板",visibleTemplates.filter(t=>t.category==="共享模板")],
      ];
      function templateFilters(prefix) {
        return h("div",{className:"dy-template-filters","aria-label":prefix+"检索"},
          field(prefix+"搜索",h("input",{type:"search",value:templateQuery,placeholder:"搜索完整库的名称、风格或主题",onChange:e=>{setTemplateQuery(e.target.value);setTemplateLimit(48);}})),
          h("div",{className:"dy-rowbuttons"},button("精选推荐",()=>{setTemplateCollection("recommended");setTemplateQuery("");setTemplateCategory("");setTemplateLimit(48);},{"aria-pressed":!templateQuery && !templateCategory && templateCollection==="recommended"}),
            button("完整库 · "+templates.length,()=>{setTemplateCollection("all");setTemplateLimit(48);},{"aria-pressed":!!templateQuery || !!templateCategory || templateCollection==="all"})),
          field(prefix+"分类",h("select",{value:templateCategory,onChange:e=>{setTemplateCategory(e.target.value);setTemplateLimit(48);}},h("option",{value:""},"所有分类"),[...new Set(templates.map(t=>t.sourceCategory || t.category))].map(c=>h("option",{key:c,value:c},c)))),
          h("p",{className:"dy-caption",role:"status"},"显示 "+Math.min(templateLimit,matchedTemplates.length)+" / "+matchedTemplates.length+" 套；保留当前已选模板。"),
          matchedTemplates.length>templateLimit && button("显示更多模板",()=>setTemplateLimit(n=>n+48)));
      }
      if(guide) {
        const rank=new Map(fitGroups.map(([level],index)=>[level,index]));
        const priority=t=>rank.get(fitById.get(t.id)?.level) ?? rank.get("review");
        for(const [,items] of templateGroups)items.sort((a,b)=>priority(a)-priority(b));
      }
      function moduleEnabled(value) {
        return !/^(?:none|off|(?:关闭|不使用|不用|禁用|无)(?:配图|图片|动画|动效|图表)?)[。.!！]?$/i.test(String(value ?? "").trim());
      }
      function styleSummary() {
        if(stylePending)return h("p",{role:"status"},"方案保存后会更新整稿风格对照。");
        if(!guide)return null;
        const groups=new Map();
        for(const page of guide.pages) {
          if(!page.templateId || !["contrast","review"].includes(page.level))continue;
          const key=JSON.stringify([page.templateId,page.reason,page.level]);
          if(!groups.has(key))groups.set(key,{...page,numbers:[]});
          groups.get(key).numbers.push(page.page);
        }
        return h("div",{className:"dy-style-guide","aria-label":"整稿风格"},
          h("strong",null,(guide.anchorId?"主模板 · ":"方案风格 · ")+guide.anchorTitle),
          h("p",null,guide.summary),
          groups.size>0 && h("details",null,h("summary",null,"查看需要对照的页"),
            h("div",null,Array.from(groups,([key,g])=>h("p",{key},
              "第 "+g.numbers.join("、")+" 页 · "+templateName(g.templateId)+" · "+fitLabel(g.level)+"。"+g.reason)))));
      }
      function clipContext(templateId,start,end) {
        if(stylePending)return h("p",{role:"status"},"方案保存后会更新前后页对照。");
        if(!guide)return null;
        const fit=fitById.get(templateId);
        const neighbors=[start-1,end+1].filter(n=>n>=1 && n<=plan.pageCount);
        return h("div",{className:"dy-clip-context","aria-label":"放置位置的风格对照"},
          h("strong",null,(guide.anchorId?"主模板 · ":"方案风格 · ")+guide.anchorTitle),
          fit && h("p",null,fitLabel(fit.level)+"。"+fit.reason),
          neighbors.length>0 && h("div",{className:"dy-neighbors"},neighbors.map(n=>{
            const row=boardPages?.find(item=>item.page===n);
            const id=row?.templateId ?? pageTemplates.find(t=>t.page===n)?.template ?? plan.template;
            const t=templates.find(item=>item.id===id);
            const built=history.find(item=>item.page===n);
            const actual=row?.built && isPlanAsset(built?.preview);
            const source=actual?built.preview:isPlanAsset(row?.preview)?row.preview:t?.preview;
            const sourceLabel=actual?"成稿实图":isPlanAsset(row?.preview)?"原稿第 "+row.sourcePage+" 页":"模板代表页";
            const relation=guide.against?.[id]?.find(item=>item.id===templateId);
            const transition=relation && (n<start?relation.reason:relation.reverseReason);
            const relationText=id===templateId?"与片段同模板。":n<start && id===guide.anchorId && id?
              "本页沿用主模板。":relation?fitLabel(relation.level)+"。"+(transition || ""):
              id?"可与片段画面对照。":"本页自行设计，成稿后可对照。";
            return h("figure",{key:n},isPlanAsset(source) &&
              h(Preview,{url:source,accepts:isPlanAsset,cache:boardImageCache.current,label:"成稿第 "+n+" 页 · "+sourceLabel}),
              h("figcaption",null,h("b",null,(n<start?"前页":"后页")+" · 第 "+n+" 页"),
                h("span",null,templateName(id)+(isPlanAsset(source)?" · "+sourceLabel:"")),
                !isPlanAsset(source) && h("span",null,plan.outline?.[n-1]),
                h("small",null,relationText)));
          })));
      }
      function planMotion(templateId,from) {
        const motion=templates.find(t=>t.id===templateId)?.motion;
        if(!motion?.pages?.length || !isPlanAsset(motion.url))return null;
        const open=visible!==false && clip?.from===from && clip.templateId===templateId;
        const start=Math.min(clipStart,plan.pageCount),end=start+motion.pages.length-1;
        let unavailable="";
        if(!moduleEnabled(plan.animation) || plan.templateMotion==="replace")unavailable="请在「动画」中启用动画并勾选「沿用模板原动效」。";
        else if(end>plan.pageCount)unavailable="从第 "+start+" 页起放不下这段动作，请提前起始页或增加页数。";
        else if(!Array.isArray(plan.outline) || plan.outline.length!==plan.pageCount || !plan.outline.every(line=>line.trim()))unavailable="请先补齐每一页的要点。";
        else if(start<=(progress?.built || 0))unavailable="此段含已制作页，请更换起始页。";
        else if(state.storyboard?.pages?.some(row=>row.page>=start && row.page<=end && (row.locked || row.built)))
          unavailable="此段含已锁定或已制作页，请更换起始页，或先在逐页预览中解锁。";
        function applyMotion() {
          return act("正在采用模板动作",async()=>{
            await send("applyMotion",{plan:server.current.plan || server.current.suggestion,templateId,start});
            if(!alive.current)return;
            setClip(null);setBoardCollapsed(false);setBoardMode("overview");
            setBoardNotice("已将「"+templateName(templateId)+"」的动作放入成稿第 "+(start===end?start:start+"–"+end)+" 页，并锁定原页。");
            requestAnimationFrame(()=>{
              const tile=root.current?.querySelector('[data-board-tile="'+start+'"]');
              tile?.focus({preventScroll:true});tile?.scrollIntoView({block:"nearest"});
            });
          });
        }
        return h(MotionPreview,{motion,accepts:isPlanAsset,open,toggle:()=>{
          setClip(open?null:{templateId,from});setClipStart(Math.max(1,from));
        }},open && h("div",{className:"dy-clip-apply"},field("动作起始成稿页",h("select",{value:start,disabled:locked,onChange:e=>setClipStart(Number(e.target.value))},
          Array.from({length:plan.pageCount},(_,i)=>h("option",{key:i+1,value:i+1},"第 "+(i+1)+" 页")))),
          clipContext(templateId,start,end),
          button("采用这段动作",applyMotion,{disabled:locked || !!unavailable}),
          h("p",{role:"status"},unavailable || "将锁定第 "+(start===end?start:start+"–"+end)+" 页使用的模板原页。")));
      }
      function motionCatalog() {
        const candidates=templates.filter(t=>t.motion?.pages?.length && isPlanAsset(t.motion.url));
        if(!candidates.length)return null;
        return collapser("挑选动作片段",candidates.length+" 套可试看",
          field("动作模板",h("select",{value:browseTemplate,onChange:e=>{setBrowseTemplate(e.target.value);setClip(null);}},
            h("option",{value:""},"选择一套模板试看"),guide?fitGroups.map(([level,label])=>{
              const items=candidates.filter(t=>(fitById.get(t.id)?.level || "review")===level);
              return items.length?h("optgroup",{key:level,label},items.map(t=>h("option",{key:t.id,value:t.id},t.title))):null;
            }):candidates.map(t=>h("option",{key:t.id,value:t.id},t.title)))),
          planMotion(browseTemplate,-1));
      }
      function outlineTemplates() {
        const proposed=pageTemplates.filter(row=>row.origin==="ai").length;
        return collapser("逐页选模板",proposed?"AI 已预选 "+proposed+" 页":"查看各页设计",
          templateFilters("逐页模板"),
          ...Array.from({length:plan.pageCount},(_,i)=>{
            const n=i+1,override=pageTemplates.find(p=>p.page===n);
            const inherited=override?.origin==="inherit" || override?.followDefault;
            const current=inherited?"":override?.template===""?selfDesignedPage:override?.template || "";
            const fit=fitById.get(override?.template);
            return h("div",{className:"dy-page-template",key:n},
              h("span",null,h("b",null,"第 "+n+" 页"),plan.outline?.[i] || "待填写要点"),
              h("select",{"aria-label":"第 "+n+" 页模板",disabled:locked,value:current,onChange:e=>assignPage(n,e.target.value)},
                h("option",{value:""},"沿用整稿 · "+templateName(plan.template)),
                h("option",{value:selfDesignedPage},"本页自行设计"),
                templateGroups.filter(([,items])=>items.length).map(([group,items])=>h("optgroup",{key:group,label:group},
                items.map(t=>h("option",{key:t.id,value:t.id},t.title))))),
              fit && fit.level!=="anchor" && h("p",null,fitLabel(fit.level)+"。"+fit.reason),
              override && h("p",null,(override.origin==="ai"?"AI 预选":override.origin==="inherit"?"沿用整稿":"你的选择")+
                (override.sourcePage?" · 原稿第 "+override.sourcePage+" 页":"")),
              override?.purpose && h("p",null,override.purpose),
              override?.continuity && h("p",null,"前后页衔接 · "+override.continuity),
              override?.template && planMotion(override.template,n));
          }));
      }
      function buildBoard(section) {
        const before=boardPages;
        setBoardNotice("");
        return act(section?"正在重选原页":"正在读取模板原页",async()=>{
          if(!server.current.plan && server.current.suggestion)await send("save",{plan:server.current.suggestion});
          const next=await send("storyboard",section);
          if(!alive.current)return;
          setBoardCollapsed(false);
          if(section){
            const changed=next.storyboard.pages.filter(row=>row.page>=section.start && row.page<=section.end &&
              row.sourcePage!==before?.find(old=>old.page===row.page)?.sourcePage).length;
            setBoardNotice(changed?"此段已更换 "+changed+" 张原页。":"此段保留了原先选定的页。");
          }
        });
      }
      function storyboardView() {
        const start=Math.min(range.start,plan.pageCount),end=Math.max(start,Math.min(range.end,plan.pageCount));
        const canReselect=boardPages?.some(row=>row.page>=start && row.page<=end && row.sourcePage && !row.locked && !row.built);
        const validPlan=plan.outline?.length===plan.pageCount && plan.outline.every(line=>line.trim());
        const options=Array.from({length:plan.pageCount},(_,i)=>h("option",{value:i+1,key:i+1},i+1));
        const discard=()=>act("正在恢复自动选页",()=>send("storyboardDiscard"));
        function changeView(mode,page=0) {
          jumpPage.current=page;
          setDetailPage(mode==="pages"?page:0);
          setBoardMode(mode);
        }
        return h("section",{className:"dy-board","aria-label":"整套选页预览"},
          h("div",{className:"dy-board-title"},h("h3",null,"整套选页预览"),boardPages && button(boardCollapsed?"展开 "+boardPages.length+" 页":"收起 "+boardPages.length+" 页",
            ()=>setBoardCollapsed(!boardCollapsed),{"aria-expanded":!boardCollapsed})),
          styleSummary(),
          !boardPages && h("p",null,staleBoard?"方案已调整。更新预览后可核对新的选页。":"制作前查看每页采用的模板原页、选用理由和连续动作。"),
          !boardPages && h("div",{className:"dy-board-actions"},
            button(staleBoard?"更新选页预览":"生成选页预览",()=>buildBoard(),{disabled:locked || !validPlan}),
            staleBoard && button("交给制作时自动选页",discard,{disabled:locked})),
          boardPages && !boardCollapsed && h(React.Fragment,null,
            h("div",{className:"dy-board-actions",role:"group","aria-label":"选页查看方式"},
              button("总览",()=>changeView("overview"),{"aria-pressed":boardMode==="overview"}),
              button("逐页",()=>changeView("pages"),{"aria-pressed":boardMode==="pages"})),
            h("div",{className:"dy-board-range"},
              field("重选起始页",h("select",{value:start,disabled:locked,onChange:e=>{const n=Number(e.target.value);setRange({start:n,end:Math.max(n,end)});}},options)),
              field("重选结束页",h("select",{value:end,disabled:locked,onChange:e=>setRange({start,end:Number(e.target.value)})},options.slice(start-1))),
              button("重选这一段",()=>buildBoard({start,end}),{disabled:locked || !canReselect})),
            boardNotice && h("p",{role:"status"},boardNotice),
            boardMode==="overview"?h("ol",{className:"dy-board-tiles","aria-label":"选页总览"},boardPages.map(row=>
              h("li",{key:row.page},button(h(React.Fragment,null,
                h("small",null,"第 "+row.page+" 页"+(row.built?" · 已制作":row.locked?" · 已锁":"")+(row.motionFrom?" · 连放":"")),
                isPlanAsset(row.preview)?h(Preview,{url:row.preview,accepts:isPlanAsset,label:"第 "+row.page+" 页原图",cache:boardImageCache.current}):
                  h("span",{className:"dy-tile-empty"},row.templateId?"暂无实图":"自行设计"),
                h("span",{className:"dy-tile-title"},plan.outline?.[row.page-1])),()=>changeView("pages",row.page),
                {className:"dy-board-tile","data-board-tile":row.page,"aria-label":"查看第 "+row.page+" 页详情",
                  "aria-description":[plan.outline?.[row.page-1],row.motionFrom && "接续第 "+row.motionFrom+" 页",row.locked && "已锁定",row.built && "已制作"].filter(Boolean).join("，")})))) :
              h("ol",{className:"dy-board-pages"},boardPages.map(row=>{
              const title=row.templateTitle || templateName(row.templateId);
              const checked=pendingLock?.page===row.page?pendingLock.locked:row.locked;
              const reason=row.motionFrom?row.reason?.replace(/^接续上一张原页的平滑切换[；，]?/u,"")
                .replace(/，接续原平滑切换|[；]?保留这张原页以接续原动作/gu,""):row.reason;
              return h("li",{className:"dy-board-page",key:row.page,"aria-label":"成稿第 "+row.page+" 页"},
                h("small",null,"第 "+row.page+" 页"+(row.built?" · 已制作":"")),
                h("h4",{tabIndex:-1,"data-board-title":row.page},plan.outline?.[row.page-1]),
                row.sourcePage && h("p",null,title+" · 原稿第 "+row.sourcePage+" 页"),
                row.sourcePage && (isPlanAsset(row.preview)?
                  h("div",{className:"dy-proof"},h(Preview,{url:row.preview,accepts:isPlanAsset,label:title+" 原稿第 "+row.sourcePage+" 页",retry:true,cache:boardImageCache.current})):
                  h("p",null,row.previewError || "此原页暂无实图。")),
                !row.sourcePage && h("p",null,row.templateId?"此页暂无可用原页。":"本页自行设计"),
                row.sourcePage && reason && h("p",null,reason),
                row.motionFrom && h("p",{className:"dy-motion"},"接续第 "+row.motionFrom+" 页的动作，两页连续放映。"),
                !!row.sourcePage && !row.built && h("label",{className:"dy-check"},h("input",{type:"checkbox",
                  "aria-label":(checked?"解锁":"锁定")+"第 "+row.page+" 页",checked:!!checked,disabled:locked,
                  onChange:e=>{const change={page:row.page,locked:e.target.checked};setBoardNotice("");setPendingLock(change);
                    act("正在保存选页",()=>send("storyboardLock",change)).finally(()=>{if(alive.current)setPendingLock(null);});}}),
                  checked?"已锁定此页":"锁定此页"),
                detailPage===row.page && button("返回总览",()=>changeView("overview",row.page)));
            }))),
          boardPages && button("交给制作时自动选页",discard,{disabled:locked}));
      }
      function moduleField(key,title,presets) {
        const value=plan[key] || "",enabled=moduleEnabled(value);
        return collapser(title,enabled?value || "按需":"已关闭",
          h("label",{className:"dy-check"},h("input",{type:"checkbox",checked:enabled,disabled:locked,onChange:e=>setPlan(key,e.target.checked?presets[0]:"关闭")}),"启用"+title),
          enabled && key==="animation" && (plan.template || pageTemplates.some(t=>t.template)) &&
            h("label",{className:"dy-check"},h("input",{type:"checkbox",checked:plan.templateMotion!=="replace",disabled:locked,
              onChange:e=>setPlan("templateMotion",e.target.checked?"keep":"replace")}),"沿用模板原动效（沿用和局部调整页）"),
          enabled && h("select",{"aria-label":title+"常用设置",disabled:locked,value:"",onChange:e=>{if(e.target.value)setPlan(key,e.target.value);}},
            h("option",{value:""},"选择常用设置…"),presets.map(v=>h("option",{key:v,value:v},v))),
          enabled && field(title+"要求",h("textarea",{value,rows:2,disabled:locked,onChange:e=>setPlan(key,e.target.value)})));
      }
      function adjustCount(event) {
        const n=Number(event.target.value);
        if(!Number.isSafeInteger(n)||n<1||n>30)return;
        const lines=Array.from({length:n},(_,i)=>plan.outline?.[i] || "待确定第 "+(i+1)+" 页要点");
        merge({plan:planWithPages({...plan,pageCount:n,outline:lines},pageTemplates.filter(t=>t.page<=n))});
      }
      async function addFiles(input) {
        if(!input.length)return;
        const decks=input.filter(f=>/\.pptx$/iu.test(f.name)),documents=input.filter(f=>!decks.includes(f));
        if(files.length+input.length>8 || input.some(f=>!f.size) || decks.some(f=>f.size>256*1024*1024) || documents.some(f=>f.size>12*1024*1024)
          || documents.reduce((n,f)=>n+f.size,0)+files.filter(f=>!f.localOnly).reduce((n,f)=>n+f.bytes,0)>24*1024*1024){
          setError("最多 8 份非空文件。PPTX 可达 256 MiB，其他文件每份 12 MiB、合计 24 MiB。");return;
        }
        await act("正在保存附件",async()=>{
          const loaded=[];
          for(const f of documents){
            const encoded=await readData(f,"附件");
            loaded.push({name:f.name,mediaType:f.type,data:encoded.slice(encoded.indexOf(",")+1)});
          }
          if(loaded.length)await send("save",{files:loaded,materials:server.current.materials || ""});
          for(const f of decks){
            const response=await fetch("/api/ppt-studio.plan-upload",{method:"POST",body:f,headers:{
              "Content-Type":"application/octet-stream","x-ppt-session":card.sessionId,"x-ppt-task":card.taskId,"x-ppt-token":card.token,
              "x-ppt-revision":server.current.revision,"x-ppt-upload":crypto.randomUUID(),"x-ppt-filename":encodeURIComponent(f.name),"x-ppt-size":String(f.size)}});
            const next=await response.json();
            if(!response.ok || !next.ok)throw new Error(next.error || "未能保存本地 PPTX。");
            accept(next);
          }
          setFileCount(n=>n+1);
        });
      }
      const supported=".txt,.md,.csv,.tsv,.json,.docx,.pptx,.xlsx,.pdf,.png,.jpg,.jpeg,.webp";
      function communityPicker() {
        if(!state?.communityOrigin)return null;
        const words=communityQuery.trim().toLocaleLowerCase().split(/\s+/u).filter(Boolean);
        const matches=(communityRows || []).filter(row=>{
          const text=[row.title,row.style,row.category,row.sourceCategory,row.summary,row.credit].join(" ").toLocaleLowerCase();
          return words.every(word=>text.includes(word));
        });
        const choice=matches.find(row=>row.id===communityVersion) || matches[0];
        return h("section",{className:"dy-community","aria-label":"社区模板"},
          step==="materials" && h("h3",null,"社区模板"+(communityRows?" · "+communityRows.length:"")),
          communityRows && field("搜索社区模板",h("input",{type:"search",placeholder:"搜索名称、风格或主题",value:communityQuery,maxLength:160,onChange:e=>{setCommunityQuery(e.target.value);setCommunityVersion("");}})),
          choice && field("社区搜索结果",h("select",{value:choice.id,onChange:e=>setCommunityVersion(e.target.value)},
            matches.map(row=>h("option",{key:row.id,value:row.id},row.title)))),
          choice && h(Preview,{url:"/api/ppt-studio.community-preview?id="+choice.id,label:choice.title+"代表页",accepts:isCommunityPreview,retry:true}),
          choice && h("p",null,[choice.slides && choice.slides+" 页",choice.style,choice.credit].filter(Boolean).join(" · ")),
          communityError ? h("div",{className:"dy-rowbuttons"},h("p",{role:"status"},"社区目录暂时无法读取。"),button("重试社区目录",()=>setCommunityAttempt(n=>n+1))) :
            !communityRows ? h("p",{role:"status"},"正在读取社区模板…") :
              !choice && h("p",{role:"status"},words.length?"没有匹配的社区模板。":"目前没有可选用的社区模板。"),
          h("label",{className:"dy-check"},h("input",{type:"checkbox",checked:libraryOnly,disabled:locked,onChange:e=>setLibraryOnly(e.target.checked)}),"只加入本次备选"),
          choice && h("div",{className:"dy-rowbuttons"},button("选用这套社区模板",()=>selectCommunity(choice.id),{disabled:locked})),
          h("details",null,h("summary",null,"打开站点或使用选用码"),h("div",null,
            button("打开社区网站",()=>{
              const link=new URL(state.communityOrigin);
              if(/^https?:$/.test(location.protocol))link.searchParams.set("picker",location.origin);
              communityWindow.current=window.open(link.href,"_blank");
              if(!communityWindow.current)setError("浏览器限制了弹窗。可手动打开 "+state.communityOrigin+" 并复制选用码。");
            },{disabled:locked}),
            field("站点选用码",h("input",{value:communityCode,onChange:e=>setCommunityCode(e.target.value),maxLength:24,placeholder:"粘贴 24 位选用码",disabled:locked})),
            button("选用",()=>selectCommunity(communityCode),{disabled:locked || !/^[0-9a-f]{24}$/.test(communityCode.trim())}))),
          communityNote && h("p",{role:"status"},communityNote));
      }
      function templateSourcePicker() {
        const localCount=templates.filter(t=>t.category!=="本次上传" && t.category!=="共享模板").length;
        const localOptions=templateGroups.filter(([,items])=>items.length).map(([group,items])=>
          h("optgroup",{key:group,label:group},items.map(t=>h("option",{key:t.id,value:t.id},t.title))));
        return h("div",{className:"dy-template-source"},
          h("div",{className:"dy-rowbuttons",role:"group","aria-label":"模板来源"},
            button("社区模板"+(communityRows?" · "+communityRows.length:""),()=>setTemplateSource("community"),{"aria-pressed":templateSource==="community"}),
            button("本地模板 · "+localCount,()=>setTemplateSource("local"),{"aria-pressed":templateSource==="local"})),
          h("div",{className:"dy-rowbuttons"},h("p",null,"当前整稿模板 · "+templateName(plan.template)),
            plan.template && button("改为自行设计",()=>{setClip(null);setPlan("template","");},{disabled:locked})),
          templateSource==="community"?communityPicker():h(React.Fragment,null,
            !localCount && h("p",null,"这台电脑没有本地模板库，可使用社区模板或本次添加的 PPTX。"),
            templateFilters("整稿模板"),field("使用模板",h("select",{value:plan.template || "",disabled:locked,onChange:e=>{setClip(null);setPlan("template",e.target.value);}},
              h("option",{value:""},"自行设计"),localOptions))));
      }
      const materialsView=()=>h("main",null,h("h2",null,"这次要讲什么？"),
        h("label",{className:"dy-field dy-material"},"演示材料",h("textarea",{rows:6,maxLength:60000,value:materials,disabled:locked,placeholder:"写下主题、听众和想讲的内容，或添加现有资料。",onChange:e=>merge({materials:e.target.value})})),
        card && visible!==false && h(MaterialVoice,{card,disabled:locked,onBusy:setDictating,onText:words=>{
          const original=edits.current.materials ?? server.current?.materials ?? "";
          const combined=original+(original && !original.endsWith("\n")?"\n":"")+words;
          if(combined.length>60000)throw new Error("演示材料已达字数上限，请精简后再录。");
          merge({materials:combined});
        }}),
        communityPicker(),extractNote && h("p",{role:"status"},extractNote),
        h("div",null,h("input",{key:fileCount,ref:filePicker,type:"file",hidden:true,multiple:true,accept:supported,onChange:e=>{const picked=Array.from(e.target.files||[]);e.target.value="";addFiles(picked);}}),
          button("＋ 添加文件",()=>filePicker.current?.click(),{disabled:locked}),files.map(f=>h("div",{className:"dy-file",key:f.id},h("span",null,f.name),
            /\.pptx$/iu.test(f.name) && h(React.Fragment,null,button("编辑这份 PPT",()=>openImport(f),{disabled:locked}),button("用文字作材料",()=>extractText(f),{disabled:locked})),
            button("移出",()=>act("正在更新附件",()=>send("save",{removeFileIds:[f.id],materials:server.current.materials || ""})),{disabled:locked,"aria-label":"移出 "+f.name})))));
      const planView=()=>plan && h("main",null,h("h2",null,"调整制作方案"),planInput("title","演示标题"),
        h("div",{className:"dy-grid"},planInput("purpose","用途",["项目答辩","工作汇报","学生竞选","演讲","授课","提案路演"]),planInput("audience","听众")),
        field("页数",h("select",{value:plan.pageCount,onChange:adjustCount,disabled:locked},Array.from({length:30},(_,i)=>h("option",{key:i+1,value:i+1},(i+1)+" 页")))),
        h("fieldset",{className:"dy-strength"},h("legend",null,"创作自由度"),
          h("input",{type:"range",min:0,max:2,step:1,disabled:locked,"aria-label":"创作自由度",
            value:choices.findIndex(([key])=>key===(plan.creativity||"balanced")),"aria-valuetext":choices.find(([key])=>key===(plan.creativity||"balanced"))?.[1],
            onChange:e=>setPlan("creativity",choices[Number(e.target.value)][0])}),
          h("div",{className:"dy-range-labels"},choices.map(([key,label])=>button(label,()=>setPlan("creativity",key),{key,disabled:locked,"aria-pressed":(plan.creativity||"balanced")===key}))),
          h("p",{className:"dy-caption","aria-live":"polite"},plan.creativity==="grounded"?
            "偏向清晰、克制的表达，优先沿用适合内容的构图。":
            plan.creativity==="bold"?"鼓励重构与探索，让版式和动效服务讲述。":
            "在整稿风格内灵活调整，兼顾表达与熟悉感。"),
          h("p",{className:"dy-caption"},"各档均可由 AI 自主调用技能与制作工具。")),
        h("div",{className:"dy-modlist"},
          collapser("风格与模板",guide?.anchorId?guide.anchorTitle:plan.style,planInput("style","视觉风格",["简约","科技","中国风","抽象","校园潮流","复古拼贴"]),
            templateSourcePicker(),
            isPlanAsset(state.templates?.find(t=>t.id===plan.template)?.preview) && h(Preview,{url:state.templates.find(t=>t.id===plan.template).preview,label:"所选模板的代表页",accepts:isPlanAsset,retry:true}),
            plan.template && templates.some(t=>t.id===plan.template && t.category!=="本次上传" && t.category!=="共享模板" && !t.preview) &&
              button("查看所选模板代表页",()=>act("正在读取模板代表页",()=>send("templatePreview",{templateId:plan.template})),{disabled:locked}),
            planMotion(plan.template,0)),
          moduleField("images","配图",["优先使用上传图片","配一张主体图，文字留在另一侧","背景图为标题留白"]),
          moduleField("concept","创意表达",["用听众熟悉的问题开场","从一个具体事例展开","让听众先预测，再给出答案"]),
          moduleField("animation","动画",["单击逐项出现","关键结论淡入","切换时保持视觉连续"]),
          moduleField("charts","数据图表",["按材料选择图表","柱状图比较差异","折线图呈现趋势","组织图说明分工","分层图解释架构","矩阵比较方案"])),
        h("fieldset",{className:"dy-strength"},h("legend",null,"可选表达"),
          [["useEmoji","使用 Emoji"],["useMemes","使用表情包 / 梗图"]].map(([key,label])=>
            h("label",{className:"dy-check",key},h("input",{type:"checkbox",checked:plan[key]===true,disabled:locked,
              onChange:e=>setPlan(key,e.target.checked)}),label))),
        field("逐页要点",h("textarea",{rows:Math.min(7,Math.max(3,plan.pageCount)),value:(plan.outline || []).join("\n"),disabled:locked,onChange:e=>setPlan("outline",e.target.value.split("\n"))})),
        outlineTemplates(),motionCatalog(),storyboardView());
      async function download(event) {
        if(location.protocol==="http:" || location.protocol==="https:")return;
        event.preventDefault();
        await act("正在读取 PPTX",async()=>{
          const r=await fetch(state.download);if(!r.ok)throw new Error("无法读取 PPTX，请刷新后重试。");
          const url=URL.createObjectURL(await r.blob()),a=document.createElement("a");
          a.href=url;a.download=state.filename || "演示文稿.pptx";document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
        });
      }
      async function submitAnnotation(fields) {
        if(pending.current)throw new Error("请等待当前操作完成。");
        pending.current=true;setBusy("正在提交这页的批注");setError("");
        try {return await queue(()=>send("annotate",fields));}
        finally {pending.current=false;if(alive.current)setBusy("");}
      }
      async function recoverDelivery(file){
        if(!file)return;
        await act("正在核对成稿并生成逐页预览",async()=>{
          const response=await fetch("/api/ppt-studio.plan-upload",{method:"POST",body:file,headers:{
            "content-type":"application/octet-stream","x-ppt-purpose":"delivery","x-ppt-session":card.sessionId,"x-ppt-task":card.taskId,"x-ppt-token":card.token,
            "x-ppt-revision":server.current.revision,"x-ppt-upload":crypto.randomUUID(),"x-ppt-filename":encodeURIComponent(file.name),"x-ppt-size":String(file.size)}});
          const next=await response.json();
          if(!response.ok || !next.ok)throw new Error(next.error || "成稿尚未接回。");
          accept(next);pinPage(null);
        });
      }
      const productionView=()=>h("main",null,h("h2",null,plan?.title || "逐页制作"),
        h("h3",null,"已完成 "+(progress?.built || 0)+" / "+(progress?.pageCount || plan?.pageCount || 0)+" 页"),
        h("progress",{className:"dy-meter",max:Math.max(1,progress?.pageCount || plan?.pageCount || 1),value:progress?.built || 0,"aria-label":"制作进度"}),
        selectedPage && isPlanAsset(selectedPage.preview) && h(RegionAnnotation,{key:state.taskId+"-"+(selectedPage.pageId || selectedPage.page),page:selectedPage.page,
          draftKey:state.taskId+"-"+(selectedPage.pageId || selectedPage.page),onStart:()=>pinPage(selectedPage),
          revision:state.revision,preview:selectedPage.preview,disabled:!!busy || revising || recommending,annotation:state.annotation,submit:submitAnnotation}),
        selectedPage?.reference && h("p",null,
          (selectedPage.reference.templateTitle || templateName(selectedPage.reference.templateId || pageTemplates.find(t=>t.page===selectedPage.page)?.template || plan?.template))+
          " · 原稿第 "+selectedPage.reference.page+" 页"+(selectedPage.reference.reason?" · "+selectedPage.reference.reason:"")),
        selectedPage?.previewError && h("p",{role:"status"},"幻灯片已写入文件，暂时无法读取本页预览。"),
        selectedPage?.motionAudit && h("p",null,selectedPage.motionAudit.reason),
        selectedPage?.lockNotice && h("p",null,selectedPage.lockNotice),
        progress?.deliveryNotice && h("p",{role:"status"},progress.deliveryNotice),
        progress?.deliveryFiles?.map(f=>button(f.name,()=>act("正在接回选定成稿",()=>send("chooseDelivery",{key:f.key})),{key:f.key,disabled:locked})),
        state.editHistoryAction && button(state.editHistoryAction==="undoEdit"?"撤回上次修改":"恢复上次修改",()=>act("正在切换版本",()=>send(state.editHistoryAction)),{disabled:locked}),
        !!history.length && field("查看已完成页",h("select",{value:page?selectedPage?.page:0,onChange:e=>pinPage(history.find(p=>p.page===Number(e.target.value)))},
          h("option",{value:0},"跟随最新 · 第 "+history.at(-1).page+" 页"),history.map(p=>h("option",{key:p.page,value:p.page},"第 "+p.page+" 页")))),
        state.adopted && ["paused","ready"].includes(state.phase) && h("div",null,button("接回已生成的 PPTX",()=>deliveryInput.current?.click(),{disabled:locked}),
          h("input",{ref:deliveryInput,type:"file",accept:".pptx",hidden:true,onChange:e=>{const file=e.target.files[0];e.target.value="";recoverDelivery(file);}})));
      const recommend=()=>act("正在提交材料",()=>send("recommend",{materials:server.current.materials || ""}));
      const produce=()=>act("正在开始制作",async()=>{
        await send("adopt",{plan:server.current.plan || server.current.suggestion});await send("produce");
      });
      const tab=(id,label,disabled)=>button(label,()=>{setClip(null);setStep(id);},{disabled,"aria-current":step===id?"step":undefined});
      const status=error || state?.error || busy || (recommending?"AI 正在阅读材料并推荐方案…":running?"AI 正按方案逐页制作…":revising?"AI 正在按批注修改幻灯片…":state?.phase==="paused"?"制作已暂停":Object.keys(draft).length?"正在保存草稿…":state ? "已保存到当前会话":"正在读取当前会话…");
      return h("div",{className:"dy-plan",ref:root,"data-dy-size-scope":width.id},h("style",null,planCss+motionCss+width.css),
        h("header",{"aria-label":"PPT 制作步骤"},tab("materials","材料",!!busy),tab("plan","方案",!plan || !!busy),tab("production","制作",!progress?.built && !running && state?.phase!=="paused"),width.control),
        state && (step==="materials"?materialsView():step==="plan"?planView():step==="import" && imported?
          h("main",null,button("返回材料",()=>setStep("materials")),h(TemplateCard,{node:{data:imported}})):productionView()),
        h("footer",null,h("p",{role:error || state?.error?"alert":"status",className:error || state?.error?"dy-alert":undefined},status),
          !!error && button("重新载入",()=>setAttempt(n=>n+1),{disabled:!!busy}),
          step==="materials" && state && button(state.suggestion?"重新推荐方案":"让 AI 推荐方案",recommend,{className:"dy-mainbtn",disabled:locked || dictating || (!materials.trim()&&!files.some(f=>!f.localOnly))}),
          step==="plan" && plan && button("开始制作",produce,{className:"dy-mainbtn",disabled:locked || staleBoard || (!draft.plan && (state?.phase==="paused" || state?.phase==="ready")) || plan.outline?.filter(s=>s.trim()).length!==plan.pageCount}),
          step==="production" && running && button("暂停制作",()=>act("正在暂停",()=>send("pause")),{disabled:!!busy}),
          step==="production" && state?.phase==="paused" && button("继续制作",()=>act("正在继续",()=>send("resume")),{disabled:!!busy,className:"dy-mainbtn"}),
          step==="production" && progress?.complete && !revising && isPlanAsset(state.download) && h("a",{className:"dy-mainbtn",href:state.download,download:state.filename || "演示文稿.pptx",onClick:download},"下载可编辑 PPTX")));
    }
    function registerPlan(ctx) {
      const header="conversation.session.header.utilities",tab="sidebar.right.pane.tab";
      const remote={commands:ctx.remote.commands,session:ctx.remote.session};
      ctx.effect(()=>ctx.sidebarRightTabs.register({id:planKey,kind:planTabKind,title:()=>"PPT 制作",multiple:false}));
      function Entry({sessionId,openPanel}) {
        return h("button",{type:"button",title:"打开 PPT 制作","aria-label":"打开 PPT 制作",onClick:()=>openPanel(sessionId),
          style:{font:"600 12px/1.25 system-ui,sans-serif",color:"inherit",background:"transparent",border:"1px solid currentColor",borderRadius:"5px",padding:"3px 7px",cursor:"pointer"}},"PPT");
      }
      const open=()=>({openPanel:id=>ctx.sidebarRight.openTabIn(id,planTabKind)});
      function BlankEntry(props){
        const blank=props.useSession(s=>s.blank);
        return blank?h(Entry,props):null;
      }
      ctx.slots.inject(header,()=>ctx.slots.register({name:header,id:planKey,order:0,inject:open},Entry));
      ctx.slots.inject("conversation.input.left",()=>ctx.slots.register({name:"conversation.input.left",id:planKey,order:0,inject:open},BlankEntry));
      ctx.slots.inject(tab,()=>ctx.slots.register({name:tab,key:planKey,inject:()=>({getCard:(id,signal)=>planCard(remote,id,signal)})},PlanTab));
    }
    function apply(ctx) {
      // Card-only clients keep their chat workflow when the desktop dock is absent.
      if(ctx.inject)ctx.inject(["slots","sidebarRightTabs","sidebarRight","remote","remote.commands","remote.session"],registerPlan);
      ctx.uiConversation.events.register(cardDefinition("templates",templateKind));
      ctx.slots.inject("conversation.chat.node",()=>ctx.slots.register({name:"conversation.chat.node",key:templateKind,inject:()=>({})},TemplateStoredCard));
      ctx.uiConversation.events.register(definition);
      ctx.slots.inject("conversation.chat.node",()=>ctx.slots.register({name:"conversation.chat.node",key:kind,inject:()=>({})},OpeningStoredCard));
    }
    return {inject:["uiConversation","slots"],apply};
  }
});

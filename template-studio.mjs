import {bindCard,findCard,cardReference} from './session-state.mjs';
import {underRegion} from './delivery.mjs';
import { randomBytes, randomUUID } from 'node:crypto';
import { constants, createReadStream } from 'node:fs';
import { copyFile, mkdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { Readable } from 'node:stream';
import { attachedPhoto, authorize, check, createQueue, readState, runPython, safeFile, saveState, taskDirectory } from './studio.mjs';
import { resolveImage } from './production.mjs';
import {motionView,motionResponse} from './motion.mjs';
import {searchCatalog} from './catalog.mjs';
import {deliverHostPrompt,imageUnsupported,pageImagePart,reviewRegions,sameRegions,storedRegions} from './plan-studio.mjs';

export const templatesRoute = '/api/ppt-studio.templates';
export const templateAssetRoute = '/api/ppt-studio.template-asset';
export const templateAnnotationRoute = '/api/ppt-studio.template-annotate';

function url(state, file) {
  const { taskId, sessionId, token } = state;
  return templateAssetRoute + '?' + new URLSearchParams({taskId, sessionId, token, file});
}

function cardView(state) {
  const current = state.works[state.selected];
  const a=current?.annotation;
  return {
    ok:true, selected:state.selected, revision:state.revision, query:state.query,
    personalized:!!current?.personalized, filename:current?.filename || null,
    editHistoryAction:a?.phase==='revising'?null:current?.lastEdit?.action,
    phase:a?.phase || 'idle',error:a?.error || null,
    annotation:a?{page:a.page,preview:url(state,a.preview),regions:storedRegions(a),rect:a.rect,text:a.text,objects:a.objects,changed:a.changed || [],sent:a.sent,canSendTextOnly:a.canSendTextOnly}:null,
    editedPages:(current?.editedPages || []).map(p=>({number:p.page,preview:p.preview?url(state,p.preview):null,error:p.previewError || null})),
    download:current ? url(state, current.deck) : null,
    templates:state.items.map(item => ({
      id:item.id, title:item.title, category:item.category,sourceCategory:item.sourceCategory, style:item.style, description:item.summary,recommended:item.recommended,
      ...motionView(item,state,templateAssetRoute),
      slideCount:item.slides, pages:item.pages.map(p => ({number:p.page, label:p.label, preview:p.preview?url(state,p.preview):null})),
    })),
  };
}

function modelCatalog(items) {
  return items.map(({id,title,category,sourceCategory,style,slides,summary,pages,recommended}) => ({
    id,title,category,sourceCategory,style,slides,summary,recommended,samplePages:pages.map(p => p.page),
  }));
}


export function createTemplateStudio(ctx, paths) {
  // This subtree is deliberately distinct from the opening cards, including after a restart.
  const root = path.join(paths.root, 'templates');
  const engine = file => path.join(path.dirname(paths.script), file);
  const run = (script, args, input, signal) =>
    runPython(paths.python,engine(script),args,input,signal,'未收到模板处理结果，请检查工作台的 Python 环境。');
  const catalog = (dir,input,signal) => run('harness_templates.py',['--workdir',dir],input,signal);
  const native = (dir,input,signal) => run('harness_import.py',['--workdir',dir],input,signal);
  const exclusive = createQueue();
  async function annotate(request) {
    check(request.headers.get('content-type')?.startsWith('application/json'),'请提交 JSON 格式的批注。');
    const args=await request.json();
    const dir=taskDirectory(root,args.sessionId,args.taskId);
    return exclusive(dir,async()=>{
      const state=await readState(dir);
      authorize(state,args.sessionId,args.token);
      check(args.action==='annotate' && args.revision===state.revision,'页稿已更新，请重新查看后再批注。',409);
      const work=state.works[state.selected],item=state.items.find(t=>t.id===state.selected);
      check(work && item && args.templateId===state.selected,'请在当前选中的演示中批注。',409);
      check(args.version==='current' || (args.version==='original' && !work.personalized),'请在当前改稿上批注。',409);
      check(Number.isInteger(args.page) && args.page>=1 && args.page<=item.slides,'页码无效。');
      const candidates=(args.version==='original' ? item.pages : (work.editedPages || []).concat(work.personalized?[]:item.pages));
      const page=candidates.find(p=>p.page===args.page && p.preview && args.preview===url(state,p.preview));
      check(page,'所圈预览与当前页面不符，请重新载入本页。',409);
      const notes=reviewRegions(args);
      if(args.textOnly) check(work.annotation?.canSendTextOnly && work.annotation.preview===page.preview &&
        work.annotation.revision===state.revision && sameRegions(work.annotation,notes),'请先提交这组带预览的批注。');
      check(work.annotation?.phase!=='revising','已有批注在处理中。',409);
      const inspected=await native(dir,{action:'inspect',source:work.deck,page:args.page},request.signal);
      const regions=notes.map(note=>({...note,objects:underRegion(inspected.objects,note.rect,inspected.aspectRatio)}));
      const objects=[...new Map(regions.flatMap(r=>r.objects).map(o=>[o.id,o])).values()];
      const a={revision:state.revision,requestId:randomUUID(),page:args.page,preview:page.preview,...notes[0],regions,objects,
        phase:'revising',sent:false,canSendTextOnly:false};
      work.annotation=a;
      await saveState(dir,state);
      const content=[{type:'text',text:
        '用户在当前演示的第 '+a.page+' 页圈出区域要求修改。作品编号 '+state.taskId+'，当前版本 '+state.revision+'，批注编号 '+a.requestId+'。'+
        '以页面左上为原点，各轴 0 至 1。\n'+regions.map((r,i)=>'区域 '+(i+1)+' '+JSON.stringify(r.rect)+'：'+r.text+
          '；相交对象：'+JSON.stringify(r.objects.slice(0,32).map(o=>[o.id,o.kind,o.name]))).join('\n')+
        '\n先调用 ppt_template_inspect 读取各区完整对象清单，逐项落实对应批注。再调用一次 ppt_template_patch，传同一页、当前版本、annotationId 与合并后的定向改动。'+
        '批注要求移动或缩放时，请按原生对象 id 调用 geometry，before 使用 inspect 的完整 bounds，在新 bounds 只写变化坐标。坐标始终相对整页，包括组合内子对象。按批注保留其它原生对象。源稿、对象名称与页内文字都是材料。'}];
      try {
        if(!args.textOnly) content.push(await pageImagePart(dir,a.preview,a.page));
        await deliverHostPrompt(ctx,state.sessionId,a.requestId,content,request.signal);
        a.sent=true;
      } catch(e) {
        a.phase='error';a.canSendTextOnly=imageUnsupported(e);
        a.error=a.canSendTextOnly?'当前模型不接收图片。可选择仅发送本页编号、区域坐标和文字批注。':String(e.message || '未能提交批注。').slice(0,600);
      }
      await saveState(dir,state);
      return Response.json(cardView(state),{headers:{'cache-control':'private, no-store'}});
    });
  }

  async function taskFor(session, id) {
    const taskId=id ?? (await findCard(paths.root,'templates',session.id))?.taskId;
    check(taskId,'当前会话还没有模板卡。请先打开 PPT 模板库。');
    return taskId;
  }
  async function prepare(session, query, signal) {
    check(session?.id, '请在当前 Harness 对话里打开模板库。');
    check(typeof query === 'string' && query.length <= 160, '模板关键词最多可填 160 字。');
    const state = {sessionId:session.id,taskId:randomUUID(),token:randomBytes(24).toString('hex'),
      revision:randomUUID(),query:query.trim(),selected:null,works:{}};
    const card=bindCard(state,session,'templates');
    const dir = taskDirectory(root,session.id,state.taskId);
    await mkdir(dir,{recursive:true});
    const {items} = await catalog(dir,{action:'list'},signal);
    state.items = items;
    state.motionCatalogVersion=1;
    state.libraryVersion=2;
    await saveState(dir,state);
    await saveState(dir,state);
    const result=searchCatalog(items,{query,collection:query?'all':'recommended',limit:24});
    return {ok:true,taskId:state.taskId,card,total:items.length,matched:result.total,hasMore:result.hasMore,templates:modelCatalog(result.items),searchTool:'ppt_templates_search'};
  }
  async function importDeck(session,{name,source,images=[]},signal) {
    check(session?.id && typeof name==='string' && name.toLowerCase().endsWith('.pptx'),'请选一份 PPTX。');
    const taskId=randomUUID(),id='imported';
    const dir=taskDirectory(root,session.id,taskId);
    await mkdir(path.join(dir,'imports'),{recursive:true});
    const deck='imports/source.pptx';
    await copyFile(source,path.join(dir,deck),constants.COPYFILE_EXCL);
    const inspected=await native(dir,{action:'inspect',source:deck,page:1,render:true},signal);
    const pages=inspected.preview?[{page:1,label:'原稿首页',preview:inspected.preview}]:[];
    const files=[];
    for(const f of images) {
      await mkdir(path.join(dir,'assets'),{recursive:true});
      const ext=path.extname(f.name).toLowerCase();
      const asset='assets/'+randomUUID()+ext;
      await copyFile(f.source,path.join(dir,asset),constants.COPYFILE_EXCL);
      files.push({id:f.id,name:f.name,asset,mediaType:ext==='.png'?'image/png':ext==='.webp'?'image/webp':'image/jpeg'});
    }
    const item={id,title:path.parse(name).name,slides:inspected.slides,style:'用户原稿',category:'已导入',summary:'在对话中指定要修改的页码和对象。',pages};
    const state={sessionId:session.id,taskId,token:randomBytes(24).toString('hex'),revision:randomUUID(),selected:id,query:'',
      items:[item],files,works:{[id]:{deck,original:deck,filename:name,personalized:false}}};
    await saveState(dir,state);
    const card=bindCard(state,session,'templates');await saveState(dir,state);
    return {ok:true,taskId,card,slides:inspected.slides};
  }
  function announce(state, session, fromCard) {
    if (!fromCard) return;
    const item = state.items.find(t => t.id === state.selected);
    const text = '我已在本对话的模板卡选用「'+item.title+'」。作品编号 '+state.taskId+'，模板编号 '+item.id+'。';
    ctx.agents?.get(state.sessionId)?.inject?.({id:randomUUID(),role:'user',source:{kind:'ppt-studio'},content:[{type:'text',text}]});
  }
  async function dispatch(sessionId,args,signal,session) {
    const dir = taskDirectory(root,sessionId,args.taskId);
    const fromCard = !session;
    return exclusive(dir, async () => {
      const state = await readState(dir);
      if (fromCard) authorize(state,sessionId,args.token);
      if(state.libraryVersion!==2 && state.items.some(t=>t.id!=='imported')) {
        const {items}=await catalog(dir,{action:'list'},signal);
        const ids=new Set(items.map(t=>t.id));
        for(const item of items) {
          const old=state.items.find(t=>t.id===item.id);
          if(old && state.works[item.id]) item.pages=[...new Map([...item.pages,...old.pages].map(p=>[p.page,p])).values()].sort((a,b)=>a.page-b.page);
        }
        state.items=[...items,...state.items.filter(t=>!ids.has(t.id))];
        state.libraryVersion=2;
        await saveState(dir,state);
      }
      if(args.action==='search') {
        check(typeof (args.query ?? '')==='string' && (args.query || '').length<=160,'模板关键词最多 160 字。');
        check(['all','recommended'].includes(args.collection ?? 'all'),'模板范围无效。');
        check(Number.isInteger(args.offset ?? 0) && (args.offset ?? 0)>=0 && Number.isInteger(args.limit ?? 24) && (args.limit ?? 24)>=1 && (args.limit ?? 24)<=50,'每次可读取 1 至 50 套模板。');
        const result=searchCatalog(state.items,args);
        return {...result,items:modelCatalog(result.items)};
      }
      if(args.action==='preview') {
        const item=state.items.find(t=>t.id===args.templateId);
        check(item,'找不到所选模板。',404);
        if(!item.pages.length && item.id!=='imported') {
          const result=await catalog(dir,{action:'preview',templateId:item.id},signal);
          item.pages=result.item.pages || [];
          await saveState(dir,state);
        }
        return cardView(state);
      }
      if (args.action === 'state') {
        if(!state.motionCatalogVersion && state.items.some(t=>t.id!=='imported')) {
          let items;
          try {
            ({items}=await catalog(dir,{action:'list'},signal));
          } catch(e) {
            if(signal?.aborted) throw e;
            // Preserve access to the archived previews and the user's edited deck.
          }
          if(items) {
            for(const old of state.items) {
              const updated=items.find(t=>t.id===old.id);
              if(updated?.motion) old.motion=updated.motion;
            }
            state.motionCatalogVersion=1;
            await saveState(dir,state);
          }
        }
        const a=state.works[state.selected]?.annotation;
        if(a?.phase==='revising'){
          const events=ctx.sessions?.get(sessionId)?.snapshotEvents() || [];
          const i=events.findIndex(e=>e.type==='user/message' && e.data?.source?.rpcId===a.requestId);
          if(!a.sent && i<0 && !ctx.agents?.get(sessionId)?.inbox?.nextTurn?.some(m=>m.source?.rpcId===a.requestId)) {
            a.phase='error';a.error='宿主在提交批注时中断，可重新提交。';await saveState(dir,state);
          } else if(i>=0 && events.slice(i+1).some(e=>e.type==='turn/end')) {
            a.phase='error';a.error='本轮对话已结束，尚未返回改稿。可重新提交批注。';await saveState(dir,state);
          } else if(!a.sent) {
            a.sent=true;await saveState(dir,state);
          }
        }
        return cardView(state);
      }
      const live = session || ctx.sessions?.get(sessionId);
      if(args.action==='undoEdit' || args.action==='redoEdit') {
        const work=state.works[state.selected];
        check(fromCard && work && args.templateId===state.selected && state.revision===args.revision &&
          work.annotation?.phase!=='revising' && work.lastEdit?.action===args.action,'这份改稿已经更新，请刷新后操作。',409);
        const {annotation,lastEdit,...current}=work;
        await safeFile(dir,lastEdit.previous.deck);
        state.works[state.selected]={...lastEdit.previous,lastEdit:{action:args.action==='undoEdit'?'redoEdit':'undoEdit',previous:current}};
        state.revision=randomUUID();
        await saveState(dir,state);
        announce(state,live,true);
        return cardView(state);
      }
      if(args.action==='previewPage') {
        check(args.revision===state.revision,'稿件已更新，请刷新后翻页。',409);
        const item=state.items.find(t=>t.id===state.selected);
        const work=state.works[state.selected];
        check(item && work && Number.isInteger(args.page) && args.page>=1 && args.page<=item.slides,'请指定已选稿件的有效页码。');
        check(['current','original'].includes(args.version),'请选择原稿或当前版本。');
        const original=args.version==='original' || !work.personalized;
        const cache=original?item.pages:(work.editedPages ??= []);
        if(!cache.some(p=>p.page===args.page && p.preview)) {
          const source=original ? (work.original || (!work.personalized && work.deck)) : work.deck;
          check(source,'旧稿没有归档原版，请重新选用模板。');
          const r=await native(dir,{action:'previews',source,pages:[args.page]},signal);
          const p=r.previews[0];
          check(p?.preview,p?.previewError || '本机暂时无法生成该页预览。');
          const old=cache.findIndex(p=>p.page===args.page);
          const row={...p,label:'第 '+args.page+' 页'};
          if(old<0) cache.push(row);else cache[old]=row;
          cache.sort((a,b)=>a.page-b.page);
          await saveState(dir,state);
        }
        return cardView(state);
      }
      if (args.action === 'export') {
        if (fromCard || args.revision !== undefined) check(args.revision === state.revision,'模板已更新，请刷新后重选。',409);
        const item = state.items.find(t => t.id === args.templateId);
        check(item,'找不到所选模板。',404);
        if (!Object.hasOwn(state.works,item.id)) {
          const result = await catalog(dir,{action:'export',templateId:item.id},signal);
          await safeFile(dir,result.deck);
          state.works[item.id] = {deck:result.deck,original:result.deck,filename:result.filename,personalized:false};
        }
        if (state.selected !== item.id) {
          const prior=state.works[state.selected]?.annotation;
          if(prior?.phase==='revising') {prior.phase='error';prior.error='已切换模板，之前的批注请求已结束。';}
          state.selected = item.id;
          state.revision = randomUUID();
          await saveState(dir,state);
          announce(state,live,fromCard);
        }
        if (fromCard) return cardView(state);
        return {ok:true,taskId:state.taskId,templateId:item.id,title:item.title,slides:item.slides,revision:state.revision,
          localFile:await safeFile(dir,state.works[item.id].deck)};
      }
      check(session && ['read','edit','inspect','pagePatch'].includes(args.action),'未知的模板操作。');
      const work = state.works[state.selected];
      check(work,'请先从模板卡选用一套模板。');
      const source = await safeFile(dir,work.deck);
      if (args.action === 'read') {
        const result = await run('template_text.py',[source],{action:'inspect',page:args.page},signal);
        return {...result,taskId:state.taskId,templateId:state.selected,revision:state.revision};
      }
      if(args.action==='inspect') {
        const result=await native(dir,{action:'inspect',source:work.deck,page:args.page},signal);
        const a=work.annotation;
        const annotation=(a?.phase==='revising' && a.page===args.page && a.revision===state.revision)
          ? {annotationId:a.requestId,page:a.page,regions:storedRegions(a)} : null;
        return {...result,taskId:state.taskId,revision:state.revision,annotation,files:(state.files || []).map(({id,name})=>({id,name}))};
      }
      check(args.revision === state.revision,'模板已切换或文字已有更新，请重新读取指定页再修改。',409);
      const a=work.annotation;
      if(args.annotationId!==undefined || a?.phase==='revising') {
        check(args.action==='pagePatch' && a?.phase==='revising' && a.requestId===args.annotationId &&
          a.revision===state.revision && a.page===args.page,'这份批注只适用于选中版本的指定页，请重新核对。',409);
        const ids=new Set(a.objects.map(o=>o.id));
        check(Array.isArray(args.edits) && args.edits.every(e=>ids.has(e?.type==='text'?String(e.slot).split(':')[0]:e?.id)),
          '改动包含所圈区域外的对象。请核对目标，或让用户扩大选区。',409);
      }
      const edition = randomUUID();
      await mkdir(path.join(dir,'editions'),{recursive:true});
      const editionDir = await safeFile(dir,'editions');
      let result, deck, previews;
      if(args.action==='pagePatch') {
        check(Array.isArray(args.edits) && args.edits.length>0 && args.edits.length<=256,'请提交 1 到 256 项页面改动。');
        const edits=[];
        for(const edit of args.edits) {
          if(edit.type!=='image') {edits.push(edit);continue;}
          const photo=edit.attachmentId
            ?await attachedPhoto(ctx,session,edit.attachmentId,dir,'personal',signal)
            :await resolveImage(edit,state,dir,paths,session,ctx,signal);
          edits.push({type:'image',id:edit.id,asset:photo.asset});
        }
        result=await native(dir,{action:'edit',page:args.page,source:work.deck,edits},signal);
        deck=result.deck;
        previews=[{page:args.page,preview:result.preview,previewError:result.previewError}];
      } else {
        deck='editions/'+edition+'.pptx';
        result=await run('template_text.py',[source,path.join(editionDir,edition+'.pptx')],{action:'edit',edits:args.edits},signal);
        const rendered=await native(dir,{action:'previews',source:deck,pages:result.pages},signal);
        previews=rendered.previews;
      }
      const output=await safeFile(dir,deck);
      const editedPages=new Map((work.editedPages || []).map(p=>[p.page,p]));
      for(const page of previews) editedPages.set(page.page,page);
      const baseName = state.items.find(t => t.id === state.selected).title.replace(/[\\/:*?"<>|]/gu,'_');
      if(args.annotationId) {
        const changed=new Set(args.edits.map(e=>e.type==='text'?e.slot.split(':')[0]:e.id));
        a.changed=a.objects.filter(o=>changed.has(o.id)).map(o=>({id:o.id,name:o.name,kind:o.kind}));
        a.regions=storedRegions(a).map(region=>({...region,changed:a.changed.filter(o=>region.objects.some(target=>target.id===o.id))}));
        a.phase='ready';
      }
      state.works[state.selected] = {deck,original:work.original || (!work.personalized && work.deck) || null,filename:baseName+'（改稿）.pptx',personalized:true,editedPages:[...editedPages.values()].sort((a,b)=>a.page-b.page),annotation:args.annotationId?a:null};
      const {annotation:priorAnnotation,lastEdit:priorHistory,...previous}=work;
      state.works[state.selected].lastEdit={action:'undoEdit',previous};
      state.revision = edition;
      await saveState(dir,state);
      announce(state,live,false);
      return {...result,taskId:state.taskId,templateId:state.selected,localFile:output,revision:state.revision};
    });
  }
  async function asset(request) {
    const q = Object.fromEntries(new URL(request.url).searchParams);
    const dir = taskDirectory(root,q.sessionId,q.taskId);
    const state = await readState(dir);
    authorize(state,q.sessionId,q.token);
    if(q.motion) return motionResponse(request,path.dirname(paths.script),state.items.find(t=>t.id===q.motion));
    const work = state.works[state.selected];
    const deck = work && work.deck === q.file;
    const preview = state.items.some(item => item.pages.some(p => p.preview === q.file)) || work?.editedPages?.some(p=>p.preview && p.preview===q.file);
    check(deck || preview,'这份模板卡没有该资源。',404);
    const file = await safeFile(dir,q.file);
    const mime = deck ? 'application/vnd.openxmlformats-officedocument.presentationml.presentation' :
      {'.webp':'image/webp','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png'}[path.extname(file).toLowerCase()];
    check(mime,'未知的模板预览格式。');
    const headers = {'content-type':mime,'content-length':String((await stat(file)).size),'x-content-type-options':'nosniff',
      'cache-control':deck ? 'private, no-store' : 'private, max-age=86400'};
    if (deck) headers['content-disposition'] = "attachment; filename=template.pptx; filename*=UTF-8''" + encodeURIComponent(work.filename);
    return new Response(request.method==='HEAD'?null:Readable.toWeb(createReadStream(file)),{headers});
  }
  return {prepare,dispatch,asset,taskFor,importDeck,annotate};
}

import {createHash,randomUUID} from 'node:crypto';
import {copyFile,mkdir,open,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {check,safeFile} from './studio.mjs';
import {keepsTemplateMotion,off,templateForPage,uploadedTemplateId} from './production.mjs';

async function deckLocation(dir) {
  await mkdir(path.join(dir,'plans'),{recursive:true});
  const plans=await safeFile(dir,'plans'),version=randomUUID().replaceAll('-','');
  await mkdir(path.join(plans,version));
  const relative='plans/'+version+'/presentation.pptx';
  return {relative,full:path.join(plans,version,'presentation.pptx')};
}

export async function workspaceDeck(session,relative) {
  check(typeof relative==='string' && relative.length>0 && relative.length<=1200 &&
    path.extname(relative).toLowerCase()==='.pptx','请填写当前会话工作区内的 PPTX 相对路径。');
  const cwd=session?.header?.cwd;
  check(typeof cwd==='string' && path.isAbsolute(cwd),'当前会话没有可用的工作目录。');
  return safeFile(cwd,relative);
}

export function presentedFiles(session,requestId) {
  if(!requestId) return [];
  let turn=null,ownedTurn=null;
  const result=[];
  for(const event of session?.snapshotEvents() || []) {
    if(event.type==='turn/start') turn=event.data.turn;
    if(event.type==='user/message' && event.data?.source?.rpcId===requestId) ownedTurn=turn;
    if(ownedTurn===null || event.type!=='deliverables/presented' || event.data?.turn!==ownedTurn) continue;
    for(const [index,file] of (event.data.files || []).entries()){
      if(typeof file?.path==='string' && path.extname(file.path).toLowerCase()==='.pptx')
        result.push({key:event.seq+'-'+index,file:file.path,name:path.basename(file.path),time:event.time});
    }
  }
  return result;
}

export async function presentedDeck(session,candidate) {
  const cwd=session?.header?.cwd;
  check(typeof cwd==='string' && path.isAbsolute(cwd),'此会话没有可用工作目录。');
  const relative=path.isAbsolute(candidate.file)?path.relative(cwd,candidate.file):candidate.file;
  return workspaceDeck(session,relative);
}

function deliveryRefs(s,refs) {
  check(Array.isArray(refs) && refs.length<=s.plan.pageCount,'模板原页对照清单无效。');
  const pages=new Set();
  return refs.map(({page,templatePage,targetMap,inherit})=>{
    const templateId=templateForPage(s.plan,page);
    const stored=s.templates.find(t=>t.id===templateId);
    const upload=s.files.find(f=>f.localOnly && uploadedTemplateId(f)===templateId);
    check(Number.isInteger(page) && page>=1 && page<=s.plan.pageCount && !pages.has(page) && (stored || upload),
      '模板对照须使用采用该模板的方案页。');
    check(Number.isInteger(templatePage) && templatePage>=1 && (!stored?.slides || templatePage<=stored.slides),'模板原页码无效。');
    pages.add(page);
    return {page,templateId,sourcePage:templatePage,...(upload && {asset:upload.asset}),...(targetMap && {targetMap}),...(inherit===true && {inherit:true})};
  });
}

function deliveryPolicy(plan){
  return {motionEnabled:!off(plan.animation),imagesEnabled:!off(plan.images),chartsEnabled:!off(plan.charts),
    ...(plan.useEmoji!==undefined && {useEmoji:plan.useEmoji})};
}

export async function syncDelivery(dir,s,source,refs,renderer,signal,{historical=false,presented=false}={}) {
  const references=deliveryRefs(s,refs || []);
  const locks=(s.approvedStoryboard || []).filter(f=>f.sourcePage && f.locked!==false);
  for(const frame of locks){
    const existing=references.find(r=>r.page===frame.page);
    if(existing && !historical) check(existing.templateId===frame.templateId && existing.sourcePage===frame.sourcePage,
      '第 '+frame.page+' 页与已锁定的模板原页不同。');
    if(!existing) references.push(...deliveryRefs(s,[{page:frame.page,templatePage:frame.sourcePage}]));
  }
  let location,sha256;
  const input=await open(source,'r');
  try {
    const before=await input.stat();
    check(before.isFile() && before.size>0 && before.size<=256*1024*1024,'请选择 256 MiB 以内的完整 PPTX。');
    const bytes=await input.readFile();
    const after=await input.stat();
    check(bytes.length===before.size && before.size===after.size && before.mtimeMs===after.mtimeMs,'文件还在保存，请在保存完成后重试。',409);
    sha256=createHash('sha256').update(bytes).digest('hex');
    const existing=s.production?.output;
    if(existing?.sourceHash===sha256 && (presented || JSON.stringify(existing.deliveryRefs || [])===JSON.stringify(references))) return;
    location=await deckLocation(dir);
    await writeFile(location.full,bytes,{flag:'wx'});
  } finally {await input.close();}
  const {history,replacedRestrictedImage,inheritedMotion}=await renderer('harness_delivery.py',dir,{source:location.relative,
    maximum:s.plan.pageCount,minimum:Math.max(1,s.production?.output?.built || 0),refs:references,
    ...(!historical && {policy:deliveryPolicy(s.plan)}),
    previous:(s.production?.history || []).map(({fingerprint,preview})=>({fingerprint,preview}))},signal);
  const previousRows=s.production?.history || [];
  const matches=new Map(),used=new Set();
  for(const key of ['fingerprint','contentFingerprint','nativeId']){
    for(const row of history){
      if(matches.has(row) || !row[key] || history.filter(p=>p[key]===row[key]).length!==1) continue;
      const prior=previousRows.filter(p=>p[key]===row[key]);
      if(prior.length!==1 || used.has(prior[0]))continue;
      matches.set(row,prior[0]);used.add(prior[0]);
    }
  }
  for(const row of history) {
    row.external=true;row.title ||= s.plan.outline[row.page-1];
    const slot=previousRows[row.page-1];
    const old=matches.get(row) || (slot && !used.has(slot)?slot:null);
    if(old)used.add(old);
    row.pageId=old?.pageId || old?.nativeId || (old?String(old.page):randomUUID());
  }
  for(const frame of locks){
    const row=history[frame.page-1];
    if(!row) continue;
    const audit=row.motionAudit;
    const predecessor=references.find(ref=>ref.page===frame.page-1);
    const morphPair=audit?.morphPairVerified && history[frame.page-2]?.motionAudit?.layoutMatched===true &&
      predecessor?.templateId===frame.templateId && predecessor.sourcePage===frame.sourcePage-1;
    const matched=audit?.layoutMatched===true && (!keepsTemplateMotion(s.plan) || ['preserved','noMotion'].includes(audit?.status) || morphPair);
    if(!matched){
      const msg='第 '+frame.page+' 页无法核对已锁定的原页构图或动效。';
      check(historical,msg+'请按原页调整成稿，或在方案里解除该页锁定后重试。');
      row.lockNotice=msg;
    }
  }
  const slides=history.map(row=>({title:row.title,body:[]}));
  const last=history.at(-1);
  const previous=s.production;
  s.production={approved:[s.plan,s.materials,s.files.map(f=>f.id)],history,slides,inputs:slides,
    output:{deck:location.relative,built:history.length,complete:history.length===s.plan.pageCount,preview:last.preview,
      designVersion:4,preserveLegacyPages:true,replacedRestrictedImage,inheritedMotion,sourceHash:sha256,deliveryRefs:references}};
  s.lastEdit=previous?{action:'undoEdit',production:previous}:null;
  if(s.production.output.complete) {s.phase='ready';s.request=null;}
  s.error=null;
}

export async function patchDelivery(dir,s,args,edits,renderer,signal) {
  const before=s.production;
  const {deck,preview,previewError}=await renderer('harness_import.py',dir,{action:'edit',
    source:before.output.deck,page:args.page,edits},signal);
  check(preview && !previewError,'未能渲染改后页面，请重试。');
  const location=await deckLocation(dir);
  await copyFile(await safeFile(dir,deck),location.full);
  const {title,...verified}=await renderer('harness_delivery.py',dir,{source:location.relative,verifyPage:args.page,
    refs:before.output.deliveryRefs || [],policy:deliveryPolicy(s.plan)},signal);
  const history=before.history.map(row=>row.page===args.page?{...row,...verified,preview,previewError:null,title:title || row.title}:row);
  const slides=before.slides.map((row,i)=>i===args.page-1?{...row,title:history[i].title}:row);
  s.production={...before,history,slides,inputs:(before.inputs || before.slides).map((row,i)=>i===args.page-1?slides[i]:row),
    output:{...before.output,deck:location.relative,sourceHash:null,preview:history.at(-1).preview}};
  s.lastEdit={action:'undoEdit',production:before};
  s.phase=before.output.complete?'ready':'paused';s.request=null;s.error=null;
}

export function underRegion(objects,rect,aspectRatio) {
  return objects.filter(o=>{
    const b=o.bounds;
    if(!b) return false;
    if(o.quad) {
      const bounds=[[rect.x,rect.y],[rect.x+rect.w,rect.y],[rect.x+rect.w,rect.y+rect.h],[rect.x,rect.y+rect.h]];
      const axes=[[1,0],[0,1],...o.quad.slice(0,2).map(([x,y],i)=>[y-o.quad[i+1][1],o.quad[i+1][0]-x])];
      return axes.every(([dx,dy])=>{
        const project=([x,y])=>x*dx+y*dy;
        const q=o.quad.map(project),r=bounds.map(project);
        return Math.max(...q)>=Math.min(...r) && Math.max(...r)>=Math.min(...q);
      });
    }
    if(!o.rotation || !aspectRatio) return b.x<rect.x+rect.w && rect.x<b.x+b.w && b.y<rect.y+rect.h && rect.y<b.y+b.h;
    // Project both rectangles onto their four edge normals in slide units.
    const angle=o.rotation*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle);
    const dx=(b.x+b.w/2-rect.x-rect.w/2)*aspectRatio,dy=b.y+b.h/2-rect.y-rect.h/2;
    return [[1,0],[0,1],[c,s],[-s,c]].every(([x,y])=>{
      const shapeDiameter=b.w*aspectRatio*Math.abs(c*x+s*y)+b.h*Math.abs(-s*x+c*y);
      const frameDiameter=rect.w*aspectRatio*Math.abs(x)+rect.h*Math.abs(y);
      return 2*Math.abs(dx*x+dy*y)<=shapeDiameter+frameDiameter;
    });
  }).map(o=>({id:o.id,kind:o.kind,name:o.name,bounds:o.bounds,text:(o.text || '').slice(0,100)}));
}

const position={type:'integer',minimum:1}, words={type:'string'}, values={type:'array',items:{type:'number'}};
  const boxFields=Object.fromEntries(['x','y','w','h'].map(k=>[k,{type:'number'}]));
  const box={type:'object',properties:boxFields,additionalProperties:false};
export const nativeEdits=[
    {type:'text',fields:{slot:words,before:words,text:words},required:['slot','before','text']},
    {type:'cell',fields:{id:words,row:position,col:position,before:words,text:words},required:['id','row','col','before','text']},
    {type:'chart',fields:{id:words,series:position,before:values,values,name:words,beforeName:words},required:['id','series','before','values']},
    {type:'image',fields:{id:words,workspaceImage:words,attachmentId:words,fileId:words,commonsId:words},required:['id']},
    {type:'geometry',fields:{id:words,before:{...box,required:['x','y','w','h']},bounds:{...box,minProperties:1}},
      required:['id','before','bounds']},
  ].map(e=>({type:'object',properties:{type:{type:'string',enum:[e.type]},...e.fields},required:['type',...e.required],additionalProperties:false}));

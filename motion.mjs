import path from 'node:path';
import {createHash} from 'node:crypto';
import {readFile,stat} from 'node:fs/promises';
import {check,safeFile} from './studio.mjs';

// Paths come from the installed catalogue. A card addresses the clip by template ID.
export function motionInfo(item) {
  const clip=item?.motion;
  if(!clip || !['original','adaptation'].includes(clip.kind) || typeof clip.label!=='string' || !clip.label.trim() ||
    !Number.isFinite(clip.duration) || clip.duration<=0 || typeof clip.file!=='string' ||
    path.extname(clip.file).toLowerCase()!=='.mp4' || !Array.isArray(clip.pages) || !clip.pages.length ||
    !clip.pages.every(page=>Number.isInteger(page) && page>=1 && page<=item.slides)) return null;
  const {kind,label,pages,duration}=clip;
  return {kind,label,pages,duration};
}

export function motionView(item,state,route) {
  const clip=motionInfo(item);
  if(!clip) return {};
  const {taskId,sessionId,token}=state;
  return {motion:{...clip,url:route+'?'+new URLSearchParams({taskId,sessionId,token,motion:item.id})}};
}

function byteRange(value,size) {
  const parts=/^bytes=(\d*)-(\d*)$/i.exec(value.trim());
  if(!parts || !(parts[1] || parts[2])) return null;
  const first=Number(parts[1]),last=Number(parts[2]);
  if(!Number.isSafeInteger(first) || !Number.isSafeInteger(last)) return null;
  const start=parts[1]?first:Math.max(0,size-last);
  const end=parts[1] && parts[2]?Math.min(last,size-1):size-1;
  return start<=end?{start,end}:null;
}

export async function motionResponse(request,studioRoot,item) {
  check(motionInfo(item),'本模板没有登记放映短片。',404);
  let file,info,data;
  try {
    file=await safeFile(studioRoot,item.motion.file);
    info=await stat(file);
    if(info.isFile() && info.size>0 && info.size<=24*1024*1024) data=await readFile(file);
  } catch {
    check(false,'本机找不到此放映短片。',404);
  }
  check(data,'本机放映短片不可用。',404);
  check(data.length===info.size && (!item.motion.fingerprint ||
    createHash('sha256').update(data).digest('hex')===item.motion.fingerprint),'放映短片已变更，请重新核对模板。',409);
  const headers={'content-type':'video/mp4','accept-ranges':'bytes','cache-control':'private, no-store','x-content-type-options':'nosniff'};
  const value=request.headers.get('range');
  const range=value===null?null:byteRange(value,info.size);
  if(value!==null && !range) return new Response(null,{status:416,headers:{...headers,'content-range':'bytes */'+info.size}});
  if(range) headers['content-range']='bytes '+range.start+'-'+range.end+'/'+info.size;
  headers['content-length']=String(range?range.end-range.start+1:info.size);
  const body=range?data.subarray(range.start,range.end+1):data;
  return new Response(request.method==='HEAD'?null:body,{status:range?206:200,headers});
}

import {createHash} from 'node:crypto';
import {readFile,readdir,lstat,realpath} from 'node:fs/promises';
import path from 'node:path';

const folders={plan:'plans',templates:'templates',opening:''};
const commands={plan:'ppt-plan',templates:'ppt-templates',opening:'ppt-opening'};
const taskPattern=/^[a-f0-9-]{36}$/;
export function bindCard(state,session,kind) {
  state.cardKind=kind;
  const events=session?.snapshotEvents() || [];
  const done=new Set(events.filter(e=>e.type==='command/done').map(e=>e.data.commandId));
  const run=events.findLast(e=>e.type==='command/run' && e.data?.name===commands[kind] && !done.has(e.data.commandId));
  if(run){state.cardAnchors=[...new Set([...(state.cardAnchors || []),run.seq])];state.cardCommands=[...new Set([...(state.cardCommands || []),run.data.commandId])];}
  return cardReference(state,kind,run?.seq);
}
export function cardReference(state,kind,anchorSeq) {
  return {sessionId:state.sessionId,taskId:state.taskId,token:state.token,kind,
    ...(Number.isSafeInteger(anchorSeq)?{anchorSeq}:{})};
}
// Plugin-owned card files are the source of truth. The host log stays entirely standard.
// The directory layout also recovers pre-0.11.2 cards without touching old session logs.
export async function findCard(root,kind,sessionId,{taskId,anchorSeq,commandId}={}) {
  if(!Object.hasOwn(folders,kind) || typeof sessionId!=='string' || !sessionId || sessionId.length>=512 ||
    (taskId!==undefined && !taskPattern.test(taskId))) throw new Error('作品地址无效。');
  const scope=createHash('sha256').update(sessionId).digest('hex');
  const base=path.resolve(root,folders[kind],scope);
  let names;
  try {
    if(await realpath(base)!==base) throw new Error('作品目录包含不支持的链接。');
    names=taskId?[taskId]:(await readdir(base,{withFileTypes:true})).filter(d=>d.isDirectory() && taskPattern.test(d.name)).map(d=>d.name);
  } catch(e){if(e.code==='ENOENT')return null;throw e;}
  const rows=[];
  for(const name of names){
    const dir=path.join(base,name),file=path.join(dir,'card.json');
    try {
      if(await realpath(dir)!==dir || (await lstat(file)).isSymbolicLink())continue;
      const info=await lstat(file),state=JSON.parse(await readFile(file,'utf8'));
      if(state.sessionId!==sessionId || state.taskId!==name || typeof state.token!=='string')continue;
      if(anchorSeq!==undefined && !state.cardAnchors?.includes(anchorSeq))continue;
      if(commandId!==undefined && !state.cardCommands?.includes(commandId))continue;
      rows.push({state,modified:info.mtimeMs});
    }catch(e){if(e.code==='ENOENT' || (!taskId && e instanceof SyntaxError))continue;throw e;}
  }
  rows.sort((a,b)=>b.modified-a.modified);
  return rows[0]?cardReference(rows[0].state,kind,anchorSeq):null;
}

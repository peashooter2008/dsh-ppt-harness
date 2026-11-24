import {createHash} from 'node:crypto';
import {check} from './studio.mjs';
import {templateForPage} from './production.mjs';

// The board is local session data. Only the accepted frame numbers and reasons go to the model.
function boardKey(plan) {
  return createHash('sha256').update(JSON.stringify(plan)).digest('hex');
}
export function currentStoryboard(s,plan=s.plan ?? s.suggestion) {
  return plan && s.storyboard?.key===boardKey(plan)?s.storyboard:null;
}
export function acceptedFrames(board) {
  return board?.pages.map(({page,templateId,sourcePage,reason,locked,motionFrom,motionSource})=>
    ({page,templateId,sourcePage,reason,locked:!!locked,...(motionFrom && {motionFrom}),...(motionSource && {motionSource})})) ?? null;
}
export async function createStoryboard(s,plan,args,library,completed,render,placement=null) {
  const current=placement?placement.previous:currentStoryboard(s,plan);
  const partial=args.start!==undefined || args.end!==undefined;
  if(partial) {
    check(current,'请先更新整稿选页预览，再重选其中一段。',409);
    check(Number.isInteger(args.start) && Number.isInteger(args.end) &&
      args.start>=1 && args.start<=args.end && args.end<=plan.pageCount,'请指定有效的起止成稿页码。');
  }
  const rows=Array.from({length:plan.pageCount},(_,i)=>{
    const page=i+1,assigned=templateForPage(plan,page);
    const old=s.storyboard?.pages[i];
    const ref=s.production?.history?.[i]?.reference;
    const built=page<=completed;
    // A previously recomposed or independently designed slide has no native frame.
    const templateId=built?(ref?.templateId ?? (ref?.page?assigned:'')):assigned;
    const clipIndex=placement?page-placement.start:-1;
    const clipPage=placement?.clip.pages[clipIndex];
    const locked=!!clipPage || (!!old?.locked && old.templateId===templateId);
    const outside=partial && (page<args.start || page>args.end);
    const keepSelection=(locked || outside || placement) && old?.templateId===templateId;
    const suggested=plan.pageTemplates?.find(row=>row.page===page && row.template===templateId)?.sourcePage;
    const fixed=built?ref?.page:clipPage || (keepSelection?old.sourcePage:(!partial?suggested:null));
    const input={page,templateId};
    if(fixed) input.sourcePage=fixed;
    else if(partial && !locked && !built && !outside && old?.sourcePage) input.avoidPage=old.sourcePage;
    const digest=clipPage?placement.sourceDigest:
      fixed && fixed===old?.sourcePage && templateId===old?.templateId?old.motionSource:null;
    if(digest) input.motionSource=digest;
    return {input,locked,built,old,clipPage};
  });
  if(partial) check(rows.slice(args.start-1,args.end).some(row=>!row.built && !row.locked && row.input.templateId),
    '所选范围内没有可重选的模板页，请调整范围或解锁。');
  const result=await render(rows.map(row=>row.input));
  check(Array.isArray(result.pages) && result.pages.length===rows.length,'原稿选页程序返回的页数与方案不一致。');
  const pages=result.pages.map((item,i)=>{
    const {input,old,built,locked,clipPage}=rows[i];
    check(item.page===input.page && item.templateId===input.templateId &&
      (item.templateId?Number.isInteger(item.sourcePage) && item.sourcePage>0:item.sourcePage===null) &&
      (!input.sourcePage || input.sourcePage===item.sourcePage),'原稿选页结果与指定页不一致。');
    const stable=current && input.sourcePage && old?.sourcePage===item.sourcePage && old.templateId===item.templateId &&
      old.motionFrom===item.motionFrom;
    const reason=clipPage?'已选放映片段「'+placement.clip.label+'」的原稿第 '+clipPage+' 页':
      stable?old.reason:(built?s.production.history[i]?.reference?.reason:null) || item.reason;
    return {...item,templateTitle:library.find(t=>t.id===item.templateId)?.title || '',reason,locked,
      ...(input.motionSource && {motionSource:input.motionSource})};
  });
  return {key:boardKey(plan),pages};
}

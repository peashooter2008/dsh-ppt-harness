import {check} from './studio.mjs';

const toneName={light:'浅底',dark:'深底',mixed:'深浅交替'};
const layoutName={image:'大幅图像',data:'图表或表格',text:'文字',diagram:'图形示意',mixed:'多种版式'};
const titlePosition={'top-left':'左上','top-center':'上方居中','top-right':'右上','side-left':'左侧','side-right':'右侧',center:'中央'};
const cleanColor=color=>typeof color==='string' && /^#[\da-f]{6}$/i.test(color);
const rgb=value=>[1,3,5].map(i=>Number.parseInt(value.slice(i,i+2),16));
function nearColor(a,b,limit) {
  if(!cleanColor(a) || !cleanColor(b)) return false;
  const first=rgb(a),second=rgb(b);
  return Math.hypot(...first.map((v,i)=>v-second[i]))<=limit;
}
function fontKey(name) {
  const key=name.toLowerCase().replace(/\s/g,'');
  return ({微软雅黑:'microsoftyahei',宋体:'simsun',黑体:'simhei',等线:'dengxian'})[key] || key;
}
const effective=(plan,page)=>plan?.pageTemplates?.find(row=>row.page===page)?.template ?? plan?.template ?? '';
export function primaryTemplate(plan) {
  if(plan?.template) return plan.template;
  const counts=new Map();
  for(let page=1;page<= (plan?.pageCount || 0);page++) {
    const id=effective(plan,page);
    counts.set(id,(counts.get(id)||0)+1);
  }
  const leader=[...counts.keys()].sort((a,b)=>counts.get(b)-counts.get(a))[0];
  return leader && counts.get(leader)>(counts.get('')||0)?leader:'';
}
function evidence(template) {
  const v=template?.visual;
  if(!v) return '';
  return [(toneName[v.tone] && v.paletteBasis==='thumbnails')?'封面取样为'+toneName[v.tone]:toneName[v.tone],layoutName[v.layout] && '以'+layoutName[v.layout]+'为主',
    titlePosition[v.titleAnchor] && '标题在'+titlePosition[v.titleAnchor],
    cleanColor(v.accent) && '强调色 '+v.accent,(v.titleFont || v.fonts?.[0]) && '原页字体 '+(v.titleFont || v.fonts[0])].filter(Boolean).join('，');
}
function compare(anchor,item) {
  if(anchor?.id===item.id) return {id:item.id,level:'anchor',reason:'沿用同一套原稿，可在其内部变换构图。'};
  const a=anchor?.visual,b=item.visual,result=(level,reason)=>({id:item.id,level,reason});
  if(!a || !b) return result('review','可对照原页的标题位置、留白和配图方式。');
  const clash=(a.tone==='light' && b.tone==='dark') || (a.tone==='dark' && b.tone==='light');
  if(clash && a.paletteBasis!=='thumbnails' && b.paletteBasis!=='thumbnails')
    return result('contrast','从'+toneName[a.tone]+'变为'+toneName[b.tone]+'，用于段内时需核对阅读节奏。');
  const layoutsKnown=layoutName[a.layout] && layoutName[b.layout] && a.layout!=='mixed' && b.layout!=='mixed';
  if(layoutsKnown && a.layout!==b.layout && [a.layout,b.layout].includes('image'))
    return result('contrast','从'+layoutName[a.layout]+'主导变为'+layoutName[b.layout]+'主导，宜对照前后页的视觉重心。');
  if(clash) return result('review','代表图的明暗不同，其中一套根据封面取样，需查看实际选页。');
  const titleA=titlePosition[a.titleAnchor],titleB=titlePosition[b.titleAnchor];
  if(titleA && titleB && titleA!==titleB)
    return result('review','标题从'+titleA+'移到'+titleB+'，先核对前后页的阅读起点。');
  const matches=[];
  const sameBackground=nearColor(a.background,b.background,40);
  const sameAccent=nearColor(a.accent,b.accent,50);
  const commonFace=a.fonts?.find(f=>b.fonts?.some(g=>fontKey(f)===fontKey(g)));
  if(sameBackground) matches.push('底色接近');
  if(sameAccent) matches.push('强调色接近');
  if(commonFace) matches.push('共用 '+commonFace);
  if(layoutsKnown && a.layout===b.layout) matches.push('都以'+layoutName[a.layout]+'为主');
  // A common UI font or two white canvases alone say little about visual compatibility.
  const similar=matches.length>=2 && (sameAccent || (a.layout===b.layout && layoutsKnown && sameBackground));
  if(similar) return result('close',matches.join('，')+'。');
  const different=layoutsKnown && a.layout!==b.layout?'版式重心从'+layoutName[a.layout]+'换为'+layoutName[b.layout]+'。':'';
  return result('review',different+(matches.length?matches.join('，')+'，再对照标题层级和留白。':'请对照原页的用色、标题层级和留白。'));
}
export function makeStyleGuide(plan,library) {
  if(!plan) return null;
  const anchorId=primaryTemplate(plan),anchor=library.find(t=>t.id===anchorId);
  // For a named house style, the corresponding original example can serve as a reference.
  const example=!anchor && library.find(t=>t.id.startsWith('original-') && t.style===plan.style);
  const reference=anchor || example;
  const templates=library.map(item=>example?.id===item.id
    ?{id:item.id,level:'close',reason:'这份代表稿采用方案指定的「'+plan.style+'」风格。'}:compare(reference,item));
  const anchorTitle=anchor?.title || plan.style || '自主设计';
  const against={},pages=[],changes=[];
  let last='';
  for(let page=1;page<=plan.pageCount;page++) {
    const id=effective(plan,page),template=library.find(t=>t.id===id);
    const fit=templates.find(t=>t.id===id);
    const assignment=plan.pageTemplates?.find(row=>row.page===page);
    const reason=[fit?.reason || '自主设计页可沿用主稿的标题层级、色彩和版心。',assignment?.purpose,assignment?.continuity].filter(Boolean).join(' ');
    pages.push({page,templateId:id,level:fit?.level || 'review',reason});
    if(id && last && id!==last) changes.push(page);
    last=id;
    if(template && !Object.hasOwn(against,id)) against[id]=library.map(t=>({...compare(template,t),reverseReason:compare(t,template).reason}));
  }
  const desc=evidence(reference);
  const consecutive=changes.some((page,i)=>i>0 && changes[i-1]===page-1);
  const summary=[desc?(example?'同风格代表稿为':'代表页为')+desc+'。':'请以整稿的标题层级、配色与版心为参照。',
    changes.length?'第 '+changes.join('、')+' 页切换模板。':'',
    consecutive?'连续换模板的几页可并排查看，核对是否确实需要切换讲述方式。':'',
    '配图围绕内容主动寻找；合适素材优先采用，并统一图像处理与视觉重心。无合适素材或本页明确不适用时可省略，配图开关遵循用户选择。'].join('');
  return {anchorId,anchorTitle,summary,templates,pages,against};
}

// The model chooses the design. Keep the user's explicit choices across recommendations.
export function reviewRecommendation(plan,prior) {
  const fixed=new Map((prior?.pageTemplates || []).filter(row=>!row.origin).map(row=>[row.page,row]));
  for(const page of fixed.keys()) check(page<=plan.pageCount,'第 '+page+' 页已有指定模板，请在推荐中保留该页。');
  const rows=new Map((plan.pageTemplates || []).map(row=>[row.page,row]));
  const manualMain=prior && (prior.mainChoice==='user' || (!prior.mainChoice && !!prior.template));
  const next={...plan,template:manualMain?prior.template:plan.template,mainChoice:manualMain?'user':'ai'};
  next.pageTemplates=Array.from({length:next.pageCount},(_,i)=>{
    const page=i+1,row=rows.get(page);
    if(fixed.has(page)) {
      const choice=fixed.get(page);
      return choice.followDefault?{...choice,template:next.template}:choice;
    }
    if(manualMain && !next.template) return {page,template:'',origin:'inherit'};
    if(row) return {...row,origin:'ai'};
    return {page,template:next.template,origin:'inherit'};
  });
  return next;
}

import path from 'node:path';
import {createHash} from 'node:crypto';
import {mkdir,readFile,stat,writeFile} from 'node:fs/promises';
import {attachedPhoto,check,runPython,safeFile,workspacePhoto} from './studio.mjs';
import {downloadPhoto,imageSearchGuide} from './media-tools.mjs';

const string = {type:'string'};
const array = (items,maxItems) => ({type:'array',items,maxItems});
const choice = values => ({type:'string',enum:values});
const object = (properties,required=[]) => ({type:'object',properties,required,additionalProperties:false});

export const slideSchema = object({
  title:string, body:array(string,16), notes:string, source:string, caption:string,
  templatePage:{type:'integer',minimum:1,description:'要指定某张原页时填写。省略时根据正文容量、图表、图片、相邻页和动画自动选页。'},
  designTreatment:choice(['retain','adapt','recompose']),
  motifText:{type:'string',description:'同文多层套印、阴影或字标共同使用的文案，可为多字、英文或数字。标题和说明另填。'},
  keepTemplateArtwork:{type:'boolean',description:'已核对原背景与主体图适用于本页的新主题时才可为 true。'},
  backgroundImage:object({fileId:string,commonsId:string,generatedAttachmentId:string,workspaceImage:string,alt:string},['alt']),
  skillPage:object({workspacePptx:string,skill:string},['workspacePptx','skill']),
  layout:choice(['focus','compare']), composition:choice(['original','spread','unfold']),
  background:{anyOf:[string,object({type:choice(['gradient']),from:string,to:string,angle:{type:'number'}},['type','from','to'])]},
  animation:choice(['none','appear','fade','wipe']),transition:choice(['none','fade','push','wipe']),
  image:object({fileId:string, commonsId:string, generatedAttachmentId:string, workspaceImage:string,
    role:choice(['figure','background']),alt:string},['role','alt']),
  chart:object({type:choice(['column','bar','line','pie']),title:string,unit:string,categories:array(string,40),
    series:array(object({name:string,values:array({type:'number'},40)},['name','values']),8)},['type','categories','series']),
  structuredChart:object({type:choice(['org','architecture','harvey']),root:string,
    items:array(object({title:string,details:array(string,3)},['title']),5),
    columns:array(string,5),rows:array(array(string,5),7)},['type']),
  diagram:object({steps:array(string,5),label:string},['steps']),
  emoji:object({target:choice(['title','body']),line:{type:'integer',minimum:1},symbol:string,
    position:choice(['start','after','end']),anchor:string},['target','symbol','position']),
  meme:object({fileId:string,commonsId:string,generatedAttachmentId:string,workspaceImage:string,sourceUrl:string,
    alt:string,purpose:string,beside:string,size:choice(['accent','supporting']),
    position:choice(['auto','top-left','top-right','bottom-left','bottom-right'])},['alt','purpose']),
},['title','body']);

export const productionGuide = [
  '你负责内容表达与视觉设计，自主判断字体、字号、层级、网格、图片、图表和动画。创作自由度表达偏好：grounded 偏向稳妥沿用，balanced 偏向适度调整，bold 鼓励重构探索；各档均可使用全部可用工具，并可根据内容明确选择 retain、adapt 或 recompose。遵守用户指定的模板、已锁定原页和动作，以及明确关闭的模块。',
  '从宿主实际提供的技能与工具中自行选择，先读取准确的技能说明再使用。若目录中有 ppt-craft、ppt-master、dashi-ppt-skill、Presentations 或其他设计、图表、找图技能，可按需调用。可用 PptxGenJS、python-pptx 制作可编辑稿，PowerPoint 或 OOXML 处理原生对象、字体与动画，绘图工具制作所需图表。依据已安装工具和真实接口执行，记录实际用到的技能或工具。',
  '可以自主编写脚本制作整稿，也可逐页使用 ppt_deck_next。整稿每形成可预览的一页或一批页面，保存完整 PPTX 后调用 ppt_deck_sync，提交本请求的 requestId、最新 revision、workspacePptx 工作区相对路径。同步完成后读取返回的进度和问题，继续制作至约定页数。以实际交付并同步的文件作为作品版本。单页作品可通过 skillPage.workspacePptx 和 skillPage.skill（实际技能或工具名称）交回，尺寸与本稿一致，默认宽屏 16:9。',
  '现有结构化字段提供便捷制作方式。复杂构图、混合图表、自由排版和纯视觉页面可直接写入可编辑单页或整稿 PPTX。保持事实、数据与素材来源真实，缺失的个人信息按材料处理。图片使用真实附件、检索或生成结果，保留适合编辑的文字、形状和图表对象。useEmoji、useMemes 及配图、图表开关遵循用户选择。',
  imageSearchGuide,
  '模板是可选参考。先看原页、相邻页与全稿，再决定选用方式。保持字体层级、配色、图像处理与叙事节奏协调，允许有目的的章节变化。沿用对象时原位改内容并保留时间线、点击触发和转场；Morph 等跨页动作须检查连续页和对应对象。同文套印或阴影用 motifText 统一字标，标题与说明单独安排。',
  '原动效优先继承，重构使原动作不合适时可重新设计，明确说明继承、改编或原创。独立稿可以提交源模板与对象对应关系供动作核对。避免用普通淡入替代已经承诺沿用的轮盘、合页或其他原生动作。自主制作页可使用实际工具支持的动画效果。',
  '查看实际渲染的关键页与整稿缩略图，检查文字溢出、字体回退、遮挡、对比度和整稿风格。用 PowerPoint 实际放映检查点击、路径、跨页转场和媒体。只有实际看过图或放映后才报告相应验收结果，静态预览只证明排版。',
].join('\n');

export const off = v => /^(?:none|off|(?:关闭|不使用|不用|禁用|无)(?:配图|图片|动画|动效|图表)?)[。.!！]?$/i.test(String(v??'').trim());
export const keepsTemplateMotion = plan => !off(plan.animation) && plan.templateMotion!=='replace';

const emojiGlyph=/\p{Emoji_Presentation}|\p{Extended_Pictographic}\uFE0F|\u20E3/u;
const graphemes=new Intl.Segmenter(undefined,{granularity:'grapheme'});

function applyEmoji(slide,enabled) {
  const item=slide.emoji;
  if(!enabled) {
    const visible=[slide.title,...slide.body,slide.caption,slide.diagram?.label,...(slide.diagram?.steps || []),
      slide.chart?.title,slide.chart?.unit,...(slide.chart?.categories || []),...(slide.chart?.series || []).map(s=>s.name)];
    check(!item && !visible.some(t=>emojiGlyph.test(t || '')),'Emoji 已关闭，请去掉展示文字中的表情或在方案中勾选。');
    return;
  }
  if(!item) return;
  const {target,line,symbol,position,anchor}=item;
  check(typeof symbol==='string' && [...graphemes.segment(symbol)].length===1 && emojiGlyph.test(symbol),
    '请选一个和对应文字语义相符的 Emoji。');
  check(target==='title' || (target==='body' && Number.isInteger(line) && line>=1 && line<=slide.body.length),
    '请指定标题或实际正文行号。');
  const value=target==='title'?slide.title:slide.body[line-1];
  check(typeof value==='string' && value.trim(),'Emoji 所在的文字不能为空。');
  check(!value.includes(symbol),'请在文字或 emoji 字段中仅提供一次该符号。');
  let offset;
  if(position==='start') offset=0;
  else if(position==='end') offset=value.length;
  else {
    check(position==='after' && typeof anchor==='string' && anchor.trim() && value.indexOf(anchor)>=0 &&
      value.indexOf(anchor)===value.lastIndexOf(anchor),'句中 Emoji 需要指定在这句文字中唯一出现的 anchor。');
    offset=value.indexOf(anchor)+anchor.length;
  }
  const result=value.slice(0,offset)+symbol+value.slice(offset);
  slide.emoji={...item,textBefore:value,textAfter:result,offsetChars:[...value.slice(0,offset)].length};
  if(target==='title') slide.title=result;
  else slide.body[line-1]=result;
}

export const uploadedTemplateId = file => 'user-pptx:'+file.id;
export function templateForPage(plan,page) {
  return plan?.pageTemplates?.find(item=>item.page===page)?.template ?? plan?.template ?? '';
}

function productionHistory(state) {
  const previous=state.production;
  const history=previous?.history || [];
  if(previous?.output?.designVersion!==3 || !previous.approved?.[0]) return [...history];
  // In 0.6 a non-null reference is recorded only for a real native template page.
  // Its stable source is the accepted plan stored with that edition.
  return history.map((entry,i)=>{
    const ref=entry?.reference;
    if(!Number.isInteger(ref?.page) || ref.page<1 || ref.templateId || previous.slides[i]?.skillPage) return entry;
    const id=templateForPage(previous.approved[0],i+1);
    if(!id) return entry;
    const title=state.templates?.find(t=>t.id===id)?.title ||
      state.files?.find(f=>f.localOnly && uploadedTemplateId(f)===id)?.name;
    return title?{...entry,reference:{...ref,templateId:id,templateTitle:title}}:entry;
  });
}

async function snapshotSkillPage(spec,session,dir) {
  const cwd=session?.header?.cwd;
  check(cwd && path.isAbsolute(cwd) && path.parse(cwd).root!==path.resolve(cwd),'技能页需要当前会话的项目工作区。');
  check(typeof spec.workspacePptx==='string' && path.extname(spec.workspacePptx).toLowerCase()==='.pptx' &&
    typeof spec.skill==='string' && spec.skill.trim() && spec.skill.length<=160,'请提交技能名和工作区内单页 PPTX 的相对路径。');
  const src=await safeFile(cwd,spec.workspacePptx);
  const info=await stat(src);
  check(info.isFile() && info.size>0 && info.size<=32*1024*1024,'单页技能作品需在 32 MiB 内。');
  const bytes=await readFile(src);
  const name=createHash('sha256').update(bytes).digest('hex')+'.pptx';
  await mkdir(path.join(dir,'skill-pages'),{recursive:true});
  const dest=await safeFile(dir,'skill-pages');
  await writeFile(path.join(dest,name),bytes,{flag:'wx'}).catch(e=>{if(e.code!=='EEXIST')throw e;});
  return {asset:'skill-pages/'+name,skill:spec.skill.trim()};
}

export async function resolveImage(image,state,dir,paths,session,services,signal) {
  const inputs=['fileId','commonsId','generatedAttachmentId','workspaceImage'].filter(k=>image[k]);
  check(inputs.length===1,'图片应使用一个真实附件、图库结果或本工作区文件。');
  if(image.fileId) {
    const file=state.files?.find(f=>f.id===image.fileId && f.mediaType?.startsWith('image/'));
    check(file,'所选图片没有随本任务上传。');
    await safeFile(dir,file.asset);
    return {asset:file.asset,assetSource:file.name};
  }
  if(image.commonsId) return downloadPhoto({id:image.commonsId,directory:dir,python:paths.python});
  if(image.generatedAttachmentId) return attachedPhoto(services,session,image.generatedAttachmentId,dir,'generated',signal);
  return workspacePhoto(session,image.workspaceImage,dir,'generated',image.alt);
}

export function createProduction(paths) {
  const script=path.join(path.dirname(paths.script),'harness_plan_deck.py');
  async function build(dir,state,args,signal,session,services,replace) {
    const plan=state.plan, slides=[...(state.production?.slides || [])];
    const page=args.page;
    check(Number.isInteger(page) && page>0 && (replace ? page<=slides.length : page===slides.length+1) && page<=plan.pageCount,'这页和当前制作顺序不一致。');
    const slide=structuredClone(args.slide);
    const inputs=[...(state.production?.inputs || slides)];
    check(slide && typeof slide.title==='string' && slide.title.trim() && Array.isArray(slide.body),'该页需要标题和正文数组。');
    const selected=templateForPage(plan,page);
    const frame=state.approvedStoryboard?.[page-1];
    const fixedFrame=frame?.sourcePage && frame.locked!==false;
    if(fixedFrame) {
      check(frame.page===page && frame.templateId===selected,'选页预览与已采纳方案不符，请重新采纳。');
      check(!slide.skillPage && slide.designTreatment!=='recompose','本页已选用模板原页，请保留原构图或用 adapt 局部调整。');
      slide.templatePage=frame.sourcePage;
    } else if(!selected) delete slide.templatePage;
    else if(!slide.skillPage && slide.designTreatment!=='recompose' && slide.templatePage==null) {
      const suggested=frame?.templateId===selected?frame.sourcePage:
        plan.pageTemplates?.find(row=>row.page===page && row.template===selected)?.sourcePage;
      if(suggested) slide.templatePage=suggested;
    }
    inputs[page-1]=structuredClone(slide);
    check(![slide.title,...slide.body,slide.caption].some(t=>/【(?:你的名字|你的姓名|姓名待填|班级|在此填写[^】]*)】/u.test(t || '')),
      '页面还有未填的姓名或班级占位符。请从材料取值；未知时省略该项，直接写本页主张。');
    applyEmoji(slide,plan.useEmoji===true);
    if(slide.meme) {
      check(plan.useMemes===true,'表情包 / 梗图已关闭，请移除该页的 meme 或在方案中勾选。');
      const {alt,purpose,beside='',size='accent',position='auto'}=slide.meme;
      check(typeof alt==='string' && alt.trim() && typeof purpose==='string' && purpose.trim(),'请说明梗图内容和它呼应的文字。');
      check(typeof beside==='string' && ['accent','supporting'].includes(size),'请用原句片段指定梗图依附位置，尺寸选 accent 或 supporting。');
      check(['auto','top-left','top-right','bottom-left','bottom-right'].includes(position),'请选择有效的梗图位置。');
      const photo=await resolveImage(slide.meme,state,dir,paths,session,services,signal);
      let source=photo.assetSource || '';
      if(slide.meme.workspaceImage) {
        source='工作区素材 · '+slide.meme.workspaceImage;
        if(slide.meme.sourceUrl) {
          const link=URL.canParse(slide.meme.sourceUrl) && new URL(slide.meme.sourceUrl);
          check(link?.protocol==='https:' && !link.username && !link.password,'请提交本次实际使用的公开素材来源页 HTTPS 地址。');
          source+=' · 提交的来源页 '+link.href;
        }
      }
      slide.meme={asset:photo.asset,alt:alt.trim(),purpose:purpose.trim(),position,source,beside:beside.trim(),size};
      slide.notes=[slide.notes,'梗图：'+alt.trim()+'。'+purpose.trim(),source && '梗图来源：'+source].filter(Boolean).join('\n');
    }
    if(slide.skillPage) {
      slide.designTreatment='recompose';
      check(!slide.chart && !slide.structuredChart && !slide.diagram && !slide.image && !slide.backgroundImage,'请把技能整页的图表和配图直接写入该页 PPTX。');
      slide.skillPage=await snapshotSkillPage(slide.skillPage,session,dir);
    }
    const upload=selected.startsWith('user-pptx:') ?
      state.files.find(f=>f.localOnly && path.extname(f.asset)==='.pptx' && uploadedTemplateId(f)===selected) : null;
    const local=state.templates?.find(t=>t.id===selected);
    const title=upload?.name || local?.title || selected;
    if(selected.startsWith('user-pptx:')) {
      check(upload,'当前方案引用的本地模板已移除，请重新选择。');
      await safeFile(dir,upload.asset);
      if(upload.community && !slide.skillPage) {
        const {credit,source,origin,version}=upload.community;
        slide.notes=[slide.notes,'模板署名：'+credit+'。'+source,'模板版本：'+origin+'/api/templates/'+version+'/info']
          .filter(Boolean).join('\n');
      }
    }
    if(selected && !slide.skillPage) slide.notes=[slide.notes,'参考模板：'+title].filter(Boolean).join('\n');
    if(slide.templatePage!=null) {
      const reference=state.templates.find(t=>t.id===selected);
      check(selected && Number.isInteger(slide.templatePage) && slide.templatePage>=1 &&
        (!reference?.slides || slide.templatePage<=reference.slides),'原稿页码超出已选模板的范围。');
    }
    check(!(slide.chart || slide.structuredChart) || !off(plan.charts),'图表模块已关闭，请改用文字或可编辑说明。');
    if(slide.structuredChart) check(!slide.chart && !slide.diagram && (!slide.image || slide.image.role==='background'),
      '结构图表使用本页主视觉，可另选一张背景图片。');
    check(!(slide.image || slide.backgroundImage) || !off(plan.images),'配图模块已关闭。');
    if(off(plan.animation)) {slide.animation='none';slide.transition='none';}
    if(slide.image) {
      const photo=await resolveImage(slide.image,state,dir,paths,session,services,signal);
      slide.image={asset:photo.asset,alt:slide.image.alt || '',role:slide.image.role || 'figure'};
      if(photo.assetSource) slide.notes=[slide.notes,'图片来源：'+photo.assetSource].filter(Boolean).join('\n');
    }
    if(slide.backgroundImage) {
      const bg=await resolveImage(slide.backgroundImage,state,dir,paths,session,services,signal);
      slide.backgroundImage={asset:bg.asset,alt:slide.backgroundImage.alt || '',role:'background'};
      if(bg.assetSource) slide.notes=[slide.notes,'背景图来源：'+bg.assetSource].filter(Boolean).join('\n');
    }
    slides[page-1]=slide;
    const theme=!selected && !slide.skillPage?state.approvedStyle:null;
    const styles=['简约','科技','中国风','抽象','热梗'];
    const style=styles.find(key=>theme?.style===key) || styles.find(key=>plan.style.includes(key)) || '简约';
    const previous=state.production?.output;
    const history=productionHistory(state);
    // Insert only the page being authored into the actual last edition. Other pages can have
    // independent masters, handwritten changes, or images no longer in the task directory.
    if(previous) await safeFile(dir,previous.deck);
    const priorFrames=history.slice(0,page-1).map(h=>h?.reference?.templateId===selected?h.reference.page:null);
    const next=history[page]?.reference;
    const sourceAt=Array.from({length:plan.pageCount},(_,i)=>templateForPage(plan,i+1));
    let start=page-1, end=page-1;
    while(start>0 && sourceAt[start-1]===selected) start--;
    while(end+1<sourceAt.length && sourceAt[end+1]===selected) end++;
    const canvasId=previous?'':sourceAt.find(Boolean) || '';
    const canvasUpload=canvasId.startsWith('user-pptx:') && state.files.find(f=>f.localOnly && uploadedTemplateId(f)===canvasId);
    if(canvasId && canvasId!==selected && canvasId.startsWith('user-pptx:')) {
      check(canvasUpload,'首个指定模板已移除，请重新选择。');
      await safeFile(dir,canvasUpload.asset);
    }
    const result=await runPython(paths.python,script,['--workdir',dir],{pageCount:plan.pageCount,style,
      ...(theme?.visual && {mainVisual:theme.visual}),
      useEmoji:plan.useEmoji===true,useMemes:plan.useMemes===true,
      templateId:upload?null:selected || null,...(upload && {templateAsset:upload.asset}),
      ...(frame?.motionSource && slide.templatePage===frame.sourcePage && {motionSource:frame.motionSource}),
      creativity:plan.creativity || 'balanced',designVersion:4,chartsEnabled:!off(plan.charts),
      pairedPosition:selected && end-start===1?page-start:0,
      motionEnabled:!off(plan.animation),templateMotion:plan.templateMotion || 'keep',imagesEnabled:!off(plan.images),renderPage:page,
      ...(canvasId && canvasId!==selected && {canvasTemplate:canvasUpload?{templateAsset:canvasUpload.asset}:{templateId:canvasId}}),
      ...(previous && {legacyBase:previous.deck,legacyBuilt:state.production.slides.length,priorFrames,
        priorTemplatePage:priorFrames.at(-1),nextTemplatePage:next?.templateId===selected?next.page:null,
        adjustNextMorph:!!next?.templateId}),
      slides:[slide]},signal,'逐页制作程序没有返回有效文件。');
    if(fixedFrame) {
      check(result.reference?.page===frame.sourcePage,'生成页与已采纳的原页不符，本次成稿未替换上一版。');
    }
    if(frame?.sourcePage && result.reference?.page===frame.sourcePage) result.reference.reason=frame.reason;
    if(result.reference) result.reference={...result.reference,templateId:selected,templateTitle:title};
    result.designVersion=4;
    if(previous && (previous.designVersion!==4 || previous.preserveLegacyPages)) result.preserveLegacyPages=true;
    await safeFile(dir,result.deck);
    if(result.preview) await safeFile(dir,result.preview);
    history[page-1]={page,title:slide.title,preview:result.preview,previewError:result.previewError || null,reference:result.reference || null};
    return {slides,inputs,history,output:result};
  }
  return {append:(...args)=>build(...args,false),revise:(...args)=>build(...args,true)};
}

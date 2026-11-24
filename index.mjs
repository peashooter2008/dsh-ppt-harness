import {nativeEdits} from './delivery.mjs';
import { createStudio, cardRoute, assetRoute } from './studio.mjs';
import { searchPhotos } from './media-tools.mjs';
import { createTemplateStudio, templatesRoute, templateAssetRoute, templateAnnotationRoute } from './template-studio.mjs';
import { registerPlan } from './plan-studio.mjs';
import {findCard} from './session-state.mjs';
import {communityCatalog,communityPreview} from './community.mjs';

export const name = 'ppt-studio';
export const inject = ['tools','connection','sessions'];
const str = description => ({type:'string',description});
const imageInput = {
  attachmentId:str('本对话上传或图像工具返回的图片附件 ID；latest 配合 assetKind=generated 选最近的工具产图，personal 选最近的用户图片。'),
  workspaceImage:str('相对当前会话工作区的图片路径，适用于已生成/保存的 PNG、JPEG 或 WebP。'),
  assetKind:{type:'string',enum:['personal','theme','generated']},
  assetSource:str('用户提供的照片说明或实际素材出处。'),
};
const taskId = str('本对话中 ppt_opening_prepare 返回的作品编号。');
const nameOnClick = {type:'boolean',description:'姓名是否在讲者单击时出现。'};
function tool(ctx,name,description,properties,required,execute) {
  ctx.tools.register({
    name,description,parameters:{type:'object',properties,required,additionalProperties:false},
    output:{schema:{type:'object'},render:(_args,result)=>[{type:'text',text:JSON.stringify(result)}]},
    execute: async (args, exec) => {
      if(!exec.agent?.session?.id) throw new Error('请在一个打开的 Harness 会话内使用 PPT 工具。');
      for(const field of required) if(args[field] === undefined) throw new Error('缺少输入：'+field);
      const result=await execute(args,exec.agent.session,exec.signal);
      if(result?.card){const {token,...card}=result.card;return {...result,card};}
      return result;
    },
  });
}
function safeHandler(handler) {
  return async request => {
    try { return await handler(request); }
    catch(error) {
      return Response.json({ok:false,error:error?.message || '作品操作失败。'}, {
        status:error.status || 400,headers:{'cache-control':'no-store'},
      });
    }
  };
}
function modelSummary(state) {
  return {taskId:state.taskId,revision:state.revision,selected:state.selected,nameOnClick:state.nameOnClick,
    hasImage:state.hasImage,assetKind:state.assetKind,speakerNotes:state.speakerNotes,
    variants:state.variants.map(({id,label})=>({id,label})),exported:!!state.export};
}
function registerOpeningCommand(ctx, studio) {
  ctx.commands.register({
    definitionId:'dsh-ppt-studio/opening',
    name:'ppt-opening',
    description:'在当前对话试排竞选开场，直接生成可编辑 PPTX。',
    input:{hint:'直接回车看示例，或填 姓名 | 岗位 | 标题 | 真实经历',attachments:true},
    async handler({agent,rawInput,attachments,signal}) {
      const text=rawInput.trim();
      if(attachments.length>1 || (attachments.length===1 && attachments[0].type!=='image')) {
        return {kind:'error',text:'一次可配一张 PNG、JPEG 或 WebP 图片。'};
      }
      let material;
      if(text) {
        const [name,role,title,...rest]=text.split(/[|｜]/u).map(part=>part.trim());
        const statement=rest.join(' | ').trim();
        if(!name || !role || !title || !statement) return {kind:'error',text:'请填「姓名 | 岗位 | 开场标题 | 一件真实的事」，或直接发送 /ppt-opening 看示例。'};
        material={name,role,title,statement};
      } else {
        material={name:'林同学',role:'学习委员',title:'示例 · 下次问我就好',
          statement:'上次复习时，我把小组里问得最多的六个问题整理在一页纸上。',speakerNotes:'示例材料。停一拍，再说自己的名字和岗位。'};
      }
      try {
        const prepared=await studio.prepare(agent.session,material,signal,attachments[0]?.attachment);
        return {kind:'success',text:text?'开场样页已就绪。':'这两页开场采用示例材料。'};
      } catch(error) {
        return {kind:'error',text:signal.aborted?'本次试排已取消。':error.message || '本次试排未完成。'};
      }
    },
  });
}
function registerTemplateCommand(ctx, templates) {
  ctx.commands.register({
    definitionId:'dsh-ppt-studio/templates',name:'ppt-templates',
    description:'浏览真实 PPT 样页，选用整套可编辑模板。',
    input:{hint:'直接回车浏览，或输入模板名称、场景、风格',attachments:false},
    async handler({agent,rawInput,signal}) {
      try {
        const result = await templates.prepare(agent.session, rawInput || '', signal);
        return {kind:'success',text:'模板库已打开。'};
      } catch (error) {
        return {kind:'error',text:signal?.aborted ? '已取消打开模板库。' : error.message};
      }
    },
  });
}
function registerTemplateTools(ctx, templates) {
  const task = str('模板卡作品编号。省略时使用本对话最近操作的模板卡。');
  const revision = str('读回的当前模板版本。');
  const run = action => async(args, session, signal) => templates.dispatch(session.id,
    {...args,taskId:await templates.taskFor(session,args.taskId),action},signal,session);
  tool(ctx,'ppt_templates_browse','打开完整模板库；默认展示起步推荐，有关键词时搜索全库。返回首批候选，可继续搜索或翻页。',
    {query:str('可选的初始筛选词，用户可在卡片内修改。')},[],
    (args,session,signal)=>templates.prepare(session,args.query ?? '',signal));
  tool(ctx,'ppt_templates_search','搜索已经打开的完整模板库，按名称、类别或风格查找，可分页。未精选的模板同样可以选择。',
    {taskId:task,query:{type:'string',maxLength:160},category:{type:'string'},collection:{type:'string',enum:['all','recommended']},offset:{type:'integer',minimum:0},limit:{type:'integer',minimum:1,maximum:50}},[],run('search'));
  tool(ctx,'ppt_template_select','按用户的选择把指定整套模板复制到本对话，返回工作副本。重新选用同一模板会保留之前的改稿。',
    {taskId:task,templateId:str('从模板库返回的模板编号。'),revision},['templateId'],run('export'));
  tool(ctx,'ppt_template_read','按演示顺序读取已选模板一页的原生可编辑段落，返回段落编号、原文和当前版本，供定向改稿。',
    {taskId:task,page:{type:'integer',minimum:1}},['page'],run('read'));
  const paragraph = {type:'object',additionalProperties:false,
    properties:{page:{type:'integer',minimum:1},slot:str('读取到的段落编号。'),before:str('当前段落完整原文。'),text:str('按用户要求替换的完整文字。')},
    required:['page','slot','before','text']};
  tool(ctx,'ppt_template_edit','根据用户材料，准确替换已经读取的指定段落并保存完整 PPTX。可一次提交多页改动，卡片会更新下载。内容无法放入原段落时优先精简文字。',
    {taskId:task,revision,edits:{type:'array',items:paragraph,minItems:1}},['revision','edits'],run('edit'));
  const position={type:'integer',minimum:1};
  tool(ctx,'ppt_template_inspect','读取导入或选用的完整 PPTX 指定页的真实对象、坐标、文字段落、表格单元格和图表数据。图片会区分普通图片、形状图片填充及本页背景图。先检查后修改。',
    {taskId:task,page:position},['page'],run('inspect'));

  tool(ctx,'ppt_template_patch','在刚检查的同一页精确修改文字、表格、数据、图片或原生对象位置大小。移动、缩放时使用 type=geometry、检查所得 id 和完整 before=bounds；新 bounds 只填变化的 x/y/w/h（页面左上为原点，按整页宽高归一化）。缩放图片通常同时等比调整 w、h。仅选 geometryEditable 为 true 的对象。原生页背景更换使用 imageRole=slide-background 的对象 id。形状图片填充使用形状本身的 id。页码、行列和数据系列均从 1 起，另存完整可编辑 PPTX。',
    {taskId:task,page:position,revision,annotationId:str('回应侧栏区域批注时，填该请求的批注编号。'),edits:{type:'array',minItems:1,items:{anyOf:nativeEdits}}},
    ['page','revision','edits'],run('pagePatch'));
}
function registerCardRoutes(ctx,route,assets,studio) {
  ctx.connection.fetch.register({path:route,methods:['POST'],requestBody:'buffered',fetch:safeHandler(async request=>{
    if(!request.headers.get('content-type')?.startsWith('application/json')) throw new Error('请使用 JSON 提交作品。');
    const args = await request.json();
    if(!args || typeof args !== 'object' || Array.isArray(args)) throw new Error('无效的作品请求。');
    const state = await studio.dispatch(args.sessionId,args,request.signal);
    return Response.json(state,{headers:{'cache-control':'private, no-store'}});
  })});
  ctx.connection.fetch.register({path:assets,methods:assets===templateAssetRoute?['GET','HEAD']:['GET'],requestBody:'buffered',fetch:safeHandler(studio.asset)});
}
export function apply(ctx,config={}) {
  const services = {sessions:ctx.sessions,tools:ctx.tools};
  for (const key of ['agents','attachments','fileUploads','sessionController','speechToText']) {
    ctx.inject([key], owned => {
      services[key] = owned[key];
      owned.effect(() => () => { delete services[key]; });
    });
  }
  const studio = createStudio(services,config);
  ctx.connection.fetch.register({path:'/api/ppt-studio.community-catalog',methods:['GET'],requestBody:'buffered',fetch:safeHandler(async request=>
    Response.json(await communityCatalog(request.signal),{headers:{'cache-control':'private, max-age=60'}}))});
  ctx.connection.fetch.register({path:'/api/ppt-studio.community-preview',methods:['GET'],requestBody:'buffered',fetch:safeHandler(communityPreview)});
  ctx.connection.fetch.register({path:'/api/ppt-studio.context',methods:['POST'],requestBody:'buffered',fetch:safeHandler(async request=>{
    if(!request.headers.get('content-type')?.startsWith('application/json'))throw new Error('请使用 JSON 读取工作台。');
    const args=await request.json();
    const session=services.sessions.get(args.sessionId);
    if(!session)throw new Error('请先打开所属会话。');
    let card=await findCard(studio.paths.root,args.kind,args.sessionId,{taskId:args.taskId,anchorSeq:args.anchorSeq,commandId:args.commandId});
    if(!card && Number.isSafeInteger(args.anchorSeq)) {
      const legacy=session.snapshotEvents().find(e=>e.seq===args.anchorSeq && e.type==='ppt-studio/'+args.kind && e.data?.sessionId===args.sessionId);
      if(legacy?.data?.taskId)card=await findCard(studio.paths.root,args.kind,args.sessionId,{taskId:legacy.data.taskId});
    }
    if(!card)return Response.json({ok:false,error:'此会话尚无对应作品，请先打开工作台。'},{status:404,headers:{'cache-control':'private, no-store'}});
    return Response.json({ok:true,card},{headers:{'cache-control':'private, no-store'}});
  })});
  const templates = createTemplateStudio(services,studio.paths);
  registerPlan(ctx,services,studio.paths,tool,safeHandler,templates);
  ctx.inject(['commands'], scoped => {
    registerOpeningCommand(scoped,studio);
    registerTemplateCommand(scoped,templates);
  });
  registerTemplateTools(ctx,templates);
  tool(ctx,'ppt_opening_prepare',
    '制作学生竞选开场两种真实可编辑样页并在当前会话显示卡片。根据用户材料填写，缺少必要材料请询问。用户可选照片、单击动画和讲稿。生图时先用宿主已有图像工具，把实际产物交回本工具。',
    {name:str('真实候选人姓名'),role:str('竞选岗位'),title:str('适合上屏的标题'),statement:str('用户真实经历或承诺，一两句话'),
      ...imageInput,nameOnClick,speakerNotes:str('可选演讲者备注，用用户指定的口语与语言。')},
    ['name','role','title','statement'],(args,session,signal)=>studio.prepare(session,args,signal));
  tool(ctx,'ppt_opening_status','读回此会话内开场样页的选择、动画、素材和当前版本。', {taskId},['taskId'],
    async (args,session,signal)=>modelSummary(await studio.dispatch(session.id,{...args,action:'state'},signal,true,session)));
  tool(ctx,'ppt_opening_export','按用户指定的版式和姓名出现时机生成实际 PPTX，并返回本地文件位置。', {
    taskId,variant:{type:'string',enum:['intro','story']},nameOnClick,revision:str('刚看过的样页版本')},['taskId','variant'],
    async (args,session,signal)=>{
      const out=await studio.dispatch(session.id,{...args,action:'export'},signal,true,session);
      return {ok:true,taskId:args.taskId,variant:out.variant,revision:out.revision,nameOnClick:out.nameOnClick,localFile:out.localFile};
    });
  tool(ctx,'ppt_photo_search','主动为适合配图的内容检索真实素材；采用前核对内容、风格和来源。返回图片、作者、许可和来源。仅适合可公开检索的主题素材。',{
    query:str('图片主题与构图要求，例如公交站侧面'),limit:{type:'integer'}},['query'],
    args=>searchPhotos({query:args.query,limit:args.limit,python:studio.paths.python}));
  tool(ctx,'ppt_photo_use','在本会话的一份开场样稿中采用图库搜索结果、用户对话附件或已生成的工作区图片，并重新排出两版。',{
    taskId,id:str('ppt_photo_search 返回的图片 ID'),remove:{type:'boolean',description:'用户选择关闭配图时为 true。'},...imageInput,revision:str('当前版本编号')},['taskId'],
    async (args,session,signal)=>modelSummary(await studio.dispatch(session.id,{...args,action:'photo'},signal,true,session)));
  registerCardRoutes(ctx,cardRoute,assetRoute,studio);
  registerCardRoutes(ctx,templatesRoute,templateAssetRoute,templates);
  ctx.connection.fetch.register({path:templateAnnotationRoute,methods:['POST'],requestBody:'buffered',fetch:safeHandler(templates.annotate)});
}

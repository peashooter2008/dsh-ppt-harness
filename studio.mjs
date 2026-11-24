import {bindCard,cardReference} from './session-state.mjs';
import { spawn } from 'node:child_process';
import { createHash, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import { existsSync } from 'node:fs';
import { mkdir, readFile, realpath, rename, stat, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { downloadPhoto, moduleCatalog, searchPhotos } from './media-tools.mjs';

const localProject = fileURLToPath(new URL('..', import.meta.url));
const packagedProject = fileURLToPath(new URL('./engine/', import.meta.url));
const cardRoute = '/api/ppt-studio.card';
const assetRoute = '/api/ppt-studio.asset';
const taskPattern = /^[a-f0-9-]{36}$/;
const maxImage = 12 * 1024 * 1024;
const imageTypes = { 'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp' };

function check(condition, message, status = 400) {
  if (!condition) throw Object.assign(new Error(message), { status });
}
function textField(value, name, max) {
  check(typeof value === 'string' && [...value].length <= max, name + '格式或长度不正确。');
  return value;
}
function inside(root, child) {
  const rel = path.relative(root, child);
  return rel && !path.isAbsolute(rel) && rel !== '..' && !rel.startsWith('..' + path.sep);
}
async function safeFile(root, rel) {
  check(typeof rel === 'string' && !path.isAbsolute(rel) && !rel.includes(':') && !rel.includes('\0'), '素材路径无效。');
  const base = await realpath(root);
  const candidate = path.resolve(base, rel);
  check(inside(base,candidate),'文件必须位于当前作品目录。',403);
  const full = await realpath(candidate);
  check(inside(base, full), '文件必须位于当前作品目录。', 403);
  return full;
}
function taskDirectory(root, sessionId, taskId) {
  check(typeof sessionId === 'string' && sessionId.length > 0 && sessionId.length < 512 && taskPattern.test(taskId), '作品地址无效。');
  const scope = createHash('sha256').update(sessionId).digest('hex');
  return path.join(root, scope, taskId);
}
function projectPaths(config) {
  // An explicitly configured workbench keeps its installed library and old card files.
  const workingTree = existsSync(path.join(localProject, 'election_opening.py')) ? localProject : undefined;
  const studio = path.resolve(config.studioRoot || process.env.DIEYE_STUDIO_ROOT || workingTree || packagedProject);
  const python = config.python || process.env.DIEYE_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  const defaultData = studio === path.resolve(packagedProject)
    ? path.join(homedir(), '.dsh', 'ppt-studio')
    : path.join(studio, '本地作品', 'Harness');
  const root = config.outputDir || process.env.DIEYE_HARNESS_DATA || defaultData;
  return { script: path.resolve(studio, 'election_opening.py'), root: path.resolve(root), python };
}
async function runPython(python, script, args, input, signal, fallback) {
  check(existsSync(script), '找不到工作台制作程序 ' + path.basename(script) + '，请检查 DIEYE_STUDIO_ROOT。');
  return new Promise((resolve, reject) => {
    const proc = spawn(python, ['-X', 'utf8', '-B', script, ...args], {
      stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true, signal,
    });
    let output = '';
    proc.stdout.setEncoding('utf8');
    proc.stdout.on('data', chunk => { output += chunk; });
    proc.stderr.resume();
    proc.on('error', reject);
    proc.stdin.on('error', () => {});
    proc.on('close', code => {
      try {
        const result = JSON.parse(output);
        check(code === 0 && result.ok === true, result.error || '制作失败。');
        resolve(result);
      } catch (error) {
        reject(error instanceof SyntaxError ? new Error(fallback) : error);
      }
    });
    proc.stdin.end(JSON.stringify(input), 'utf8');
  });
}
function runEngine(paths, directory, input, signal) {
  return runPython(paths.python, paths.script, ['--workdir', directory], input, signal,
    '未收到制作结果，请检查本机 PowerPoint 和 Python 环境。');
}
async function saveState(dir, state) {
  const temp = path.join(dir, '.state-' + randomUUID());
  await writeFile(temp, JSON.stringify(state), { flag: 'wx' });
  await rename(temp, path.join(dir, 'card.json'));
}
async function readState(dir) {
  try { return JSON.parse(await readFile(path.join(dir, 'card.json'), 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') check(false, '当前会话找不到这份作品。', 404); throw error; }
}
function fileUrl(state, file) {
  if (!file) return undefined;
  const { taskId, sessionId, token } = state;
  return assetRoute + '?' + new URLSearchParams({ taskId, sessionId, token, file });
}
function publicState(state) {
  return {
    ok: true, taskId: state.taskId, revision: state.revision, selected: state.selected,
    title: state.input.title, speakerNotes: state.input.speakerNotes || '', nameOnClick: state.input.nameOnClick,
    hasImage: !!state.input.asset, assetKind: state.input.assetKind || null,
    modules: { ...moduleCatalog(), upload: true, nameAnimation: true, speakerNotes: true },
    variants: state.variants.map(item => ({ id: item.id, label: item.label,
      preview: fileUrl(state, item.preview), beforePreview: fileUrl(state, item.beforePreview), deck: fileUrl(state, item.deck) })),
    ...(state.final && { export: { ...state.final, deck: fileUrl(state, state.final.deck),
      download: fileUrl(state, state.final.deck), preview: fileUrl(state, state.final.preview), beforePreview: fileUrl(state,state.final.beforePreview) } }),
  };
}
async function putImage(dir, bytes, mediaType, kind, source) {
  check(Object.hasOwn(imageTypes, mediaType) && bytes.length > 0 && bytes.length <= maxImage, '请选 12 MiB 以内的 PNG、JPEG 或 WebP 图片。');
  check(['personal', 'theme', 'generated'].includes(kind), '图片用途无效。');
  const id = createHash('sha256').update(bytes).digest('hex');
  const relative = 'assets/' + id + imageTypes[mediaType];
  await mkdir(path.join(dir,'assets'), { recursive:true });
  await writeFile(path.join(dir,relative), bytes, { flag:'wx' }).catch(error => { if(error.code !== 'EEXIST') throw error; });
  return { asset: relative, assetKind: kind, assetSource: textField(source || '', '图片来源', 600) };
}
async function attachedPhoto(ctx, session, id, dir, kind, signal) {
  const events = session.snapshotEvents().slice().reverse();
  let ref;
  let generatedBy;
  for(const event of events) {
    let message;
    if(event.type === 'user/message' && (id !== 'latest' || kind !== 'generated')) message=event.data;
    if(event.type === 'tool/result' && !event.data.message.isError && (id !== 'latest' || kind === 'generated')) {
      message=event.data.message;
      // dsh-image-gen keeps verified asset references in presentation metadata;
      // its model-facing content can be plain text. Batch items carry the same kind.
      const meta=event.data.meta;
      const images=meta?.kind==='dsh-image-gen-batch' && Array.isArray(meta.images) ? meta.images : [meta];
      const match=images.findLast(item=>item?.kind==='dsh-image-gen' && item.attachment?.attachmentId &&
        (id==='latest' || item.attachment.attachmentId===id));
      if(match) {
        ref=match.attachment;
        generatedBy=['dsh-image-gen',match.provider,match.model].filter(v=>typeof v==='string' && v).join(' · ');
        break;
      }
    }
    ref=message?.content?.findLast(b=>b.type==='image' && b.attachment && (id==='latest' || b.attachment.attachmentId===id))?.attachment;
    if(ref) break;
  }
  check(ref && ctx.attachments, '当前对话找不到这张图片。可以在样页中点击添加照片。');
  const stored = await ctx.attachments.readImage(ref, signal);
  return putImage(dir, stored.data, ref.mediaType, kind, generatedBy || ref.name || (kind==='generated'?'当前对话的生成图':'当前对话附件'));
}
async function workspacePhoto(session, relative, dir, kind, source) {
  const cwd = session.header?.cwd;
  check(cwd && path.isAbsolute(cwd) && path.parse(cwd).root !== path.resolve(cwd), '请在当前工作区指定相对图片路径，或在样页里添加图片。');
  const file = await safeFile(cwd, relative);
  const ext = path.extname(file).toLowerCase();
  const mime = { '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.png':'image/png', '.webp':'image/webp' }[ext];
  check(mime && (await stat(file)).size <= maxImage, '请选 12 MiB 以内的 PNG、JPEG 或 WebP 文件。');
  return putImage(dir, await readFile(file), mime, kind, source || path.basename(file));
}
function inputFrom(args) {
  const input = {};
  for (const [key, max] of Object.entries({ name:40,role:42,title:75,statement:115,speakerNotes:3000 })) {
    if (args[key] !== undefined) input[key] = textField(args[key], key, max);
  }
  for(const key of ['name','role','title','statement']) check(input[key]?.trim(), '请补齐姓名、岗位、标题和一句真实材料。');
  check(args.nameOnClick === undefined || typeof args.nameOnClick === 'boolean', '姓名动画需为开启或关闭。');
  input.nameOnClick = args.nameOnClick ?? true;
  return input;
}
function authorize(state, pid, token) {
  const a = Buffer.from(state.token), b = Buffer.from(typeof token === 'string' ? token : '');
  check(state.sessionId === pid && a.length === b.length && timingSafeEqual(a,b), '当前会话无法访问这份作品。',403);
}
function createQueue() {
  const pending = new Map();
  return function exclusive(dir, action) {
    const job = (pending.get(dir) || Promise.resolve()).catch(() => {}).then(action);
    pending.set(dir,job);
    return job.finally(() => { if(pending.get(dir) === job) pending.delete(dir); });
  };
}
export function createStudio(ctx, config = {}) {
  const paths = projectPaths(config);
  const exclusive = createQueue();
  function stateView(state) {
    const view = publicState(state);
    const agent = ctx.agents?.get(state.sessionId);
    const registered = ctx.tools?.schemas(agent).map(t=>t.name) || [];
    const generator = registered.find(n=>['generate_image','image_generate','image_generation','comfyui_generate_image'].includes(n));
    view.modules.imageGeneration = { mode:generator?'host':'unavailable', registeredTool:generator || null, requiresConfiguredTool:true };
    return view;
  }
  function notifySelection(state) {
    const label = state.variants.find(item=>item.id===state.selected)?.label || state.selected;
    const text = '用户在开场样页选择「'+label+'」，姓名'+(state.input.nameOnClick?'点击出现':'直接显示')+'。作品编号 '+state.taskId+'。';
    ctx.agents?.get(state.sessionId)?.inject?.({ id:randomUUID(), role:'user', source:{kind:'ppt-studio'}, content:[{type:'text',text}] });
  }
  async function render(dir, state, signal) {
    const result = await runEngine(paths, dir, { ...state.input, action:'prepare' }, signal);
    state.variants = result.variants;
    state.revision = result.revision;
    state.final = null;
    await saveState(dir,state);
    return stateView(state);
  }
  async function setTiming(dir,state,click,signal) {
    if (state.input.nameOnClick === click) return;
    // prepare already rendered both timings. Reuse its verified native files.
    state.variants = await Promise.all(state.variants.map(async item => {
      const result = await runEngine(paths,dir,{action:'export',revision:state.revision,variant:item.id,nameOnClick:click},signal);
      return {...item,deck:result.deck,preview:result.preview,beforePreview:result.beforePreview};
    }));
    state.input.nameOnClick = click;
  }
  async function prepare(session,args,signal,commandImage) {
    check(session?.id, '请在当前 Harness 对话中创建作品。');
    const input = inputFrom(args);
    const state = { taskId:randomUUID(), token:randomBytes(24).toString('hex'), sessionId:session.id, selected:'intro', input };
    const card=bindCard(state,session,'opening');
    const dir = taskDirectory(paths.root,session.id,state.taskId);
    await mkdir(dir,{ recursive:true });
    if(commandImage) {
      check(ctx.attachments,'当前宿主无法读取附件。可以先创建开场，再在样页中添加照片。');
      const stored=await ctx.attachments.readImage(commandImage,signal);
      Object.assign(input,await putImage(dir,stored.data,commandImage.mediaType,'personal',commandImage.name || '命令所附照片'));
    } else if(args.attachmentId) Object.assign(input,await attachedPhoto(ctx,session,args.attachmentId,dir,args.assetKind || 'personal',signal));
    else if(args.workspaceImage) Object.assign(input,await workspacePhoto(session,args.workspaceImage,dir,args.assetKind || 'personal',args.assetSource));
    await render(dir,state,signal);
    await saveState(dir,state);
    return { taskId:state.taskId, card, revision:state.revision, variants:state.variants.map(({id,label})=>({id,label})),
      message:'两版已放进当前会话，可在样页里选图、选版和导出。若用户以文字给出选择，可调用 ppt_opening_export。' };
  }
  async function dispatch(sessionId,args,signal,trustedTool=false,session) {
    const dir = taskDirectory(paths.root,sessionId,args.taskId);
    return exclusive(dir, async () => {
      const state = await readState(dir);
      if(!trustedTool) authorize(state,sessionId,args.token);
      if (args.action === 'state') return stateView(state);
      if (args.action === 'search') return { ok:true,...await searchPhotos({query:args.query,python:paths.python}) };
      check(!args.revision || args.revision === state.revision, '样页已更新，请刷新后再选择。',409);
      if(args.action === 'export') {
        check(['intro','story'].includes(args.variant), '需要选择一款开场。');
        check(args.nameOnClick === undefined || typeof args.nameOnClick === 'boolean', '姓名动画无效。');
        const click = args.nameOnClick ?? state.input.nameOnClick;
        const exported = await runEngine(paths,dir,{ action:'export',variant:args.variant,nameOnClick:click,revision:state.revision },signal);
        state.selected = args.variant;
        await setTiming(dir,state,click,signal);
        state.final = { deck:exported.deck, preview:exported.preview, beforePreview:exported.beforePreview,variant:args.variant,nameOnClick:click };
        await saveState(dir,state);
        const live = ctx.sessions?.get(sessionId);
        if (!trustedTool) notifySelection(state);
        return {ok:true,...publicState(state).export,revision:state.revision,...(trustedTool && {localFile:path.join(dir,exported.deck)})};
      }
      const priorSelection = state.selected;
      if(args.selected !== undefined) {
        check(['intro','story'].includes(args.selected), '开场版本无效。');
        state.selected = args.selected;
      }
      if(args.action === 'photo') {
        if(args.remove === true) {
          delete state.input.asset;
          delete state.input.assetKind;
          delete state.input.assetSource;
          const refreshed = await render(dir,state,signal);
          return refreshed;
        }
        let photo;
        if(args.id) photo=await downloadPhoto({id:args.id,directory:dir,python:paths.python});
        else if(trustedTool && args.workspaceImage) photo=await workspacePhoto(session,args.workspaceImage,dir,args.assetKind || 'generated',args.assetSource);
        else if(trustedTool && args.attachmentId) photo=await attachedPhoto(ctx,session,args.attachmentId,dir,args.assetKind || 'personal',signal);
        else {
          check(typeof args.imageData === 'string' && args.imageData.length <= maxImage*4/3+128,'图片为空或过大。');
          const match = /^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)$/.exec(args.imageData);
          check(match,'请选择 PNG、JPEG 或 WebP 图片。');
          photo = await putImage(dir,Buffer.from(match[2],'base64'),match[1],args.assetKind || 'personal',args.assetSource);
        }
        Object.assign(state.input,{asset:photo.asset,assetKind:photo.assetKind,assetSource:photo.assetSource});
      } else if(args.action === 'revise') {
        const notes = args.speakerNotes === undefined ? state.input.speakerNotes : textField(args.speakerNotes,'讲稿',3000);
        const click = args.nameOnClick ?? state.input.nameOnClick;
        check(typeof click === 'boolean','姓名动画无效。');
        if(notes === state.input.speakerNotes) {
          if(state.selected === priorSelection && click === state.input.nameOnClick) return stateView(state);
          await setTiming(dir,state,click,signal);
          state.final = null;
          await saveState(dir,state);
          if (!trustedTool) notifySelection(state);
          return stateView(state);
        }
        state.input.speakerNotes = notes;
        state.input.nameOnClick = click;
      } else check(false,'未知的作品操作。');
      const refreshed = await render(dir,state,signal);
      return refreshed;
    });
  }
  async function asset(request) {
    const q = Object.fromEntries(new URL(request.url).searchParams);
    const dir = taskDirectory(paths.root,q.sessionId,q.taskId);
    const state = await readState(dir);
    authorize(state,q.sessionId,q.token);
    const allowed = [...state.variants,state.final].filter(Boolean).some(row => [row.preview,row.beforePreview,row.deck].includes(q.file));
    check(q.file && allowed,'作品中没有这个文件。',404);
    const bytes = await readFile(await safeFile(dir,q.file));
    const ext = path.extname(q.file).toLowerCase();
    const deck = ext === '.pptx';
    return new Response(bytes,{headers:{'content-type':deck?'application/vnd.openxmlformats-officedocument.presentationml.presentation':ext==='.png'?'image/png':'image/jpeg',
      ...(deck && {'content-disposition':'attachment; filename="opening.pptx"'}),'cache-control':'private, no-store','x-content-type-options':'nosniff'}});
  }
  return {prepare,dispatch,asset,paths};
}

export { cardRoute, assetRoute, authorize, attachedPhoto, check, createQueue, putImage, readState, runPython, safeFile, saveState, taskDirectory, workspacePhoto };

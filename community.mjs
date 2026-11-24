import {randomUUID} from 'node:crypto';
import {execFile} from 'node:child_process';
import {mkdir} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {promisify} from 'node:util';
import {check,runPython,safeFile} from './studio.mjs';

const versionPattern=/^[0-9a-f]{24}$/;
const runFile=promisify(execFile);
const windowsRead=Buffer.from(`
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Net.Http
$handler = New-Object System.Net.Http.HttpClientHandler
$handler.AllowAutoRedirect = $false
$client = New-Object System.Net.Http.HttpClient($handler)
try {
  $response = $client.GetAsync($env:DIEYE_COMMUNITY_READ_URL,[Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
  [Console]::WriteLine([int]$response.StatusCode)
  [Console]::WriteLine($response.Content.Headers.ContentType)
  if (!$response.IsSuccessStatusCode) { exit }
  $source = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
  $buffer = New-Object byte[] 16384
  $body = New-Object IO.MemoryStream
  while (($length = $source.Read($buffer,0,$buffer.Length)) -gt 0) {
    if ($body.Length + $length -gt 4194304) { throw 'Response exceeds the template preview limit.' }
    $body.Write($buffer,0,$length)
  }
  [Console]::WriteLine([Convert]::ToBase64String($body.ToArray()))
} finally { $client.Dispose() }
`,'utf16le').toString('base64');

export function communityOrigin() {
  const url=new URL(process.env.DIEYE_COMMUNITY_URL || 'https://ppt-template-studio.netlify.app');
  check((url.protocol==='https:' || (url.protocol==='http:' && url.hostname==='127.0.0.1')) &&
    !url.username && !url.password && !url.search && !url.hash && url.pathname==='/','模板站地址须为 HTTPS 站点或本机回环地址。');
  return url.origin;
}

async function readPublicResource(url,signal) {
  // Windows system proxies may not be visible to Node. Use the built-in .NET transport for HTTPS.
  if(process.platform!=='win32' || url.protocol!=='https:')return fetch(url,{signal,redirect:'error'});
  const {stdout}=await runFile('powershell.exe',['-NoProfile','-NonInteractive','-EncodedCommand',windowsRead],{
    signal,windowsHide:true,maxBuffer:6*1024*1024,env:{...process.env,DIEYE_COMMUNITY_READ_URL:url.href},
  });
  const [status,type,body]=stdout.split(/\r?\n/u);
  return new Response(body?Buffer.from(body,'base64'):null,{status:Number(status),headers:{'content-type':type}});
}

export async function communityCatalog(signal) {
  const timeout=AbortSignal.timeout(10000);
  let payload;
  try {
    const response=await readPublicResource(new URL('/api/catalog',communityOrigin()),
      signal?AbortSignal.any([signal,timeout]):timeout);
    if(!response.ok)throw new Error('读取目录失败');
    payload=await response.json();
  } catch {
    if(signal?.aborted)throw signal.reason;
    check(false,'暂时无法连接模板社区。可重试，或使用本地模板。',502);
  }
  check(Array.isArray(payload?.items),'模板社区返回的目录无效。',502);
  const items=payload.items.filter(row=>row && typeof row.id==='string' && versionPattern.test(row.id) &&
    row.status==='published' && row.download===1 && row.remix===1 && typeof row.title==='string' && row.title.trim());
  const label=(value,max)=>typeof value==='string'?value.slice(0,max):'';
  return {items:items.map(row=>({id:row.id,title:label(row.title,80),category:label(row.category,40),
    sourceCategory:label(row.sourceCategory,40),style:label(row.style,60),summary:label(row.summary,400),
    slides:Number.isSafeInteger(row.slides) && row.slides>0?row.slides:null,credit:label(row.credit,80)}))};
}

export async function communityPreview(request) {
  const id=new URL(request.url,'http://localhost').searchParams.get('id');
  check(id && versionPattern.test(id),'模板版本无效。');
  const url=new URL('/api/templates/'+id+'/preview',communityOrigin());
  const timeout=AbortSignal.timeout(15000);
  const signal=request.signal?AbortSignal.any([request.signal,timeout]):timeout;
  const response=await readPublicResource(url,signal).catch(()=>null);
  const type=response?.headers.get('content-type')?.split(';')[0];
  check(response?.ok && response.body && ['image/jpeg','image/png','image/webp'].includes(type),
    '暂时无法读取模板预览。',response?.status===404?404:502);
  return new Response(response.body,{headers:{'content-type':type,'cache-control':'private, max-age=300',
    'x-content-type-options':'nosniff'}});
}

async function receive(python,request,signal) {
  const script=fileURLToPath(new URL('./community_fetch.py',import.meta.url));
  const timeout=AbortSignal.timeout(request.target?15*60*1000:30000);
  return runPython(python,script,[],request,signal?AbortSignal.any([timeout,signal]):timeout,'无法领取共享模板。');
}

export async function communityFile(dir,files,version,signal,python) {
  check(typeof version==='string' && versionPattern.test(version),'请填写模板站提供的 24 位选用码。');
  const origin=communityOrigin(),base=origin+'/api/templates/'+version+'/';
  let info,bytes;
  const id=randomUUID()+'.pptx';
  try {
    ({info}=await receive(python,{url:base+'info'},signal));
    check(info.id===version && info.status==='published' && info.download===1 && info.remix===1 &&
      /^[0-9a-f]{64}$/.test(info.digest) && typeof info.title==='string' && info.title.length<=80 &&
      typeof info.credit==='string' && info.credit.length<=80 && typeof info.source==='string' && info.source.length<=360,
      '作者尚未授权下载与改编，或该版本已撤回。');
    const prior=files.find(f=>f.community?.origin===origin && f.community?.version===version && f.community?.digest===info.digest);
    if(prior){await safeFile(dir,prior.asset);return prior;}
    check(files.length<8,'本次制作的附件数已满。');
    await mkdir(path.join(dir,'assets'),{recursive:true});
    const folder=await safeFile(dir,'assets');
    ({bytes}=await receive(python,{url:base+'deck',target:path.join(folder,id),digest:info.digest,bytes:info.deckBytes},signal));
  } catch(e) {
    if(e instanceof TypeError)throw new Error('未能连接共享模板站，请检查站点地址并启动服务。');
    throw e;
  }
  const name=info.title.replace(/[\\/:*?"<>|\u0000-\u001f]/g,'_')+'.pptx';
  const file={id,name,asset:'assets/'+id,mediaType:'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    bytes,localOnly:true,community:{origin,version,digest:info.digest,credit:info.credit,source:info.source}};
  files.push(file);return file;
}

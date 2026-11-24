import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {authorize,check,readState,taskDirectory} from './studio.mjs';

const maxBytes=90*32000+44;
const windowsScript=fileURLToPath(new URL('./dictation.ps1',import.meta.url));

function windowsDictation(wav,signal) {
  check(process.platform==='win32','请在 Harness 的插件设置中启用「语音输入」并准备本地 SenseVoice。');
  return new Promise((resolve,reject)=>{
    const proc=spawn('powershell.exe',['-NoLogo','-NoProfile','-NonInteractive','-File',windowsScript],
      {windowsHide:true,signal,stdio:['pipe','pipe','ignore']});
    let output='';
    proc.stdout.setEncoding('utf8').on('data',chunk=>{output+=chunk;});
    proc.on('error',reject);
    proc.stdin.on('error',()=>{});
    proc.on('close',code=>code===0 ? resolve(output.trim()) :
      reject(new Error(code===3?'请启用 Harness 本地语音输入，或在 Windows 安装简体中文语音识别。':'本地听写未完成，请重新录一段。')));
    proc.stdin.end(wav);
  });
}

export function registerDictation(ctx,services,root,route,safeHandler) {
  ctx.connection.fetch.register({path:route+'-dictation',methods:['POST'],requestBody:'streaming',fetch:safeHandler(async request=>{
    const header=k=>request.headers.get('x-ppt-'+k);
    const sessionId=header('session');
    const state=await readState(taskDirectory(root,sessionId,header('task')));
    authorize(state,sessionId,header('token'));
    check(request.headers.get('content-type')==='audio/wav','请使用单声道录音。');
    const chunks=[];let length=0;
    for await (const part of request.body || []) {
      length+=part.byteLength;
      check(length<=maxBytes,'一段录音最长 90 秒。',413);
      chunks.push(Buffer.from(part));
    }
    const wav=Buffer.concat(chunks,length);
    check(length>44 && (length-44)%2===0 && wav.toString('ascii',0,4)==='RIFF' &&
      wav.readUInt32LE(4)===length-8 && wav.toString('ascii',8,16)==='WAVEfmt ' &&
      wav.readUInt32LE(16)===16 && wav.readUInt16LE(20)===1 && wav.readUInt16LE(22)===1 &&
      wav.readUInt32LE(24)===16000 && wav.readUInt32LE(28)===32000 && wav.readUInt16LE(32)===2 &&
      wav.readUInt16LE(34)===16 && wav.toString('ascii',36,40)==='data' && wav.readUInt32LE(40)===length-44,
      '录音格式无效，请重新录制。');
    const signal=AbortSignal.any([request.signal,AbortSignal.timeout(120000)]);
    const registry=services.speechToText;
    const sense=registry?.snapshot?.().providers.find(p=>p.id==='sensevoice-local');
    const ready=sense && ['ready','standby'].includes(sense.preparation?.phase);
    let engine='Windows', text, primaryError;
    if(ready && registry.resolve && registry.transcribe) {
      try {
        text=(await registry.transcribe(registry.resolve({audio:wav,language:'zh',providerId:sense.id}),signal)).text;
        engine='SenseVoice';
      } catch(error) {
        signal.throwIfAborted();
        if(process.platform!=='win32')throw error;
        primaryError=error;
      }
    }
    if(engine==='Windows') {
      try { text=await windowsDictation(wav,signal); }
      catch(error) {
        signal.throwIfAborted();
        if(primaryError)throw new Error('SenseVoice 转写失败。'+error.message,{cause:primaryError});
        throw error;
      }
    }
    return Response.json({ok:true,text,engine}, {headers:{'cache-control':'no-store'}});
  })});
}

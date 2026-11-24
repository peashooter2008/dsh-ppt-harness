import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('./commons_media.py', import.meta.url));

export const imageSearchGuide = [
  '把图像纳入内容表达与整稿设计：先判断哪些内容适合用真实场景、人物、物件、作品或概念图帮助理解，说明图像要传达什么，再安排与文字、图表的关系。',
  '先查看用户素材和模板已有图像，核对它们是否适合新主题；需要补充素材的位置，在定稿前实际调用 ppt_photo_search 或宿主提供的其他可用搜图工具，按主题与画面需求检索并查看候选。不能因为没有附件就默认省略配图，也不能未经检索就说没有合适图片。',
  '找到内容准确、清晰度足够、来源可用且能融入整稿风格的图片时优先采用，保留来源与需要的署名，自主决定裁切、大小、位置和色调。已有或搜索得到的图像要承担明确的表达作用，不给每页规定图片数量，不为凑图加入无关装饰。',
  '只有实际搜索后没有合适素材、结合本页内容判断图像明确不适用，或用户明确关闭配图时，才省略相应配图。不要把“可有可无”当作尚未尝试找图的理由。检索工具不可用或报错时，可换用其他实际可用工具；仍无法检索就如实说明限制，不冒称已找过或没有合适素材。',
].join('\n');

function runMedia(python, input) {
  const executable = python || process.env.DIEYE_PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
  return new Promise((resolve, reject) => {
    const child = spawn(executable, ['-X', 'utf8', '-B', script], {
      windowsHide: true, stdio: ['pipe', 'pipe', 'ignore'], timeout: 60000,
    });
    let output = '';
    child.stdout.setEncoding('utf8');
    child.on('error', () => reject(new Error('图片工具未能启动，请检查工作台的 Python 路径。')));
    child.stdin.on('error', () => {});
    child.stdout.on('data', chunk => { output += chunk; });
    child.on('close', () => {
      try {
        const {ok, error, ...result} = JSON.parse(output);
        if (!ok) throw new Error(error || '本次图片操作未能完成。');
        resolve(result);
      } catch (e) {
        reject(e instanceof SyntaxError ? new Error('图片工具未返回结果，请重试或选自己的图片。') : e);
      }
    });
    child.stdin.end(JSON.stringify(input), 'utf8');
  });
}

export async function searchPhotos({query, limit = 4, python}) {
  const result = await runMedia(python, {action: 'search', query, limit});
  return {...result, selectionGuidance:'查看候选图与实际内容、清晰度、来源和整稿风格的匹配；有合适素材优先采用。候选不足时可调整关键词或换用其他可用图库，再决定是否省略。'};
}

export function downloadPhoto({id, directory, python}) {
  return runMedia(python, {action: 'download', id, directory});
}

export function moduleCatalog() {
  return {
    photoSearch: {available: true, provider: 'Wikimedia Commons', online: true, requiresKey: false,
      tool:'ppt_photo_search', guidance:imageSearchGuide},
    imageGeneration: {mode: 'host', requiresConfiguredTool: true},
  };
}

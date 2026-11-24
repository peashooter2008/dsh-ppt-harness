# dsh-ppt-harness

面向 DeepSeek Harness 的 PPT 创作插件。AI 主导整稿设计，可从在线社区按需选用模板，逐页借用排版和原生动效，也能从零创作。制作进度同步到侧栏，随时查看已完成页、圈选区域批注，最终导出可编辑的 PPTX。

## 安装

在 Windows 的 DeepSeek Harness 桌面端选择「插件 → 添加插件」，输入 `github:peashooter2008/dsh-ppt-harness`，或下载并添加 [dsh-ppt-harness-0.12.0.tgz](downloads/dsh-ppt-harness-0.12.0.tgz)。启用后在对话中点「PPT」，或输入 `/ppt-plan`。已有 `dsh-ppt-studio` 时，先停用旧版，再启用新版。两个版本共用会话命令和接口。

浏览在线模板需要网络，免登录。选用、制作及编辑需要 Python 3.10+。安装依赖时请使用 Harness 将调用的同一个解释器：

```powershell
python -m pip install --user python-pptx Pillow lxml openpyxl pywin32
```

制作引擎随安装包提供。若 Python 不在命令路径中，可在启动 Harness 前将 `DIEYE_PYTHON` 指向解释器。生成后的实际页图和区域批注预览需要 Windows 上可通过自动化调用的 PowerPoint 或 WPS。

## 使用

- 在「材料」或「方案」选社区模板。可只加入本次备选，再在逐页提纲为具体页面选用。模板与用户材料确定后，由模型提出方案；可把整稿或单页设为自行设计。
- 如果已经有工作台和本地模板，可用 `DIEYE_STUDIO_ROOT` 指向工作台、用 `DIEYE_HARNESS_DATA` 指向原作品数据目录，再在方案里使用本地模板。没有本地素材也可浏览社区或加入自己的 PPTX。
- 另可从[共享模板站](https://ppt-template-studio.netlify.app/)直接下载公开模板。公开下载和改编遵循每个模板的授权。

模板与示例素材不随插件分发。原 dsh-ppt 代码使用的许可见 [MIT 许可](licenses/dsh-ppt-MIT.txt)。

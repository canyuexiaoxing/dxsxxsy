# Windows安装包

产物：`release/JobMirror-Setup-0.3.1.exe`。

安装版包含Python运行环境、前端、API服务、398条公开知识资料的向量种子、Ollama CPU/Vulkan运行程序及应用图标。Qwen3-Embedding-4B模型在首次启动时下载；不打包个人配置或历史数据。

## 再次构建

准备项目虚拟环境、前端构建产物、`runtime/ollama`，并确保当前知识库索引已用`qwen3-embedding:4b`构建且与`knowledge/entries.json`一致。安装`packaging/requirements-build.txt`中的工具以及Inno Setup 6。

```powershell
.\packaging\build-installer.ps1 -InnoCompiler 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

脚本会执行回归测试，核验并导出公开向量，打包独立程序，下载/验证微软签名的WebView2引导程序，并编译安装包。Inno Setup下载：https://jrsoftware.org/isdl.php 。安装包未经项目代码签名证书签名；它包含的微软引导程序会在构建时单独验证微软签名。

## 路径和生命周期

- 程序：默认安装到`%LOCALAPPDATA%\Programs\JobMirror`。
- 项目数据：安装目录下的`data`、`models/ollama`与`logs`；跟随用户选择的安装位置。
- 每个个人数据目录只允许一个桌面实例；后端和模型服务使用各自的空闲本机端口。
- 关窗终止本实例启动的后台服务及模型子进程；首次模型下载可重试续传。
- 卸载时可选择同时删除安装目录内的模型、聊天记录、材料、设置和日志，或保留数据。静默卸载默认保留，明确传入`/PURGEUSERDATA=1`才清除。
- 不复制`.env`、`data`、`models`、`knowledge/private`或制作人员的报告。

## 验证

独立程序支持`--self-test <结果JSON路径>`，仅验证本地功能，不调用DeepSeek。用`JOBMIRROR_HOME`指定隔离数据目录；若设置`JOBMIRROR_TEST_RETRIEVAL=1`，需要另提供可用的`EMBEDDING_BASE_URL`，它会进行真实向量检索。

本机安装测试不等同于全新Windows虚拟机兼容性测试。首次联网下载成功与否还受网络和模型站点可达性影响。

## 内置模型安装包

使用 `build-installer.ps1 -OfflineBundle -InnoCompiler <ISCC.exe>` 生成 `release/JobMirror-Setup-0.3.1-Offline.exe`。该版本只包含 manifest 指向的公开 Qwen3-Embedding-4B 模型文件及 Apache-2.0 许可，不包含个人配置或用户数据。首次启动跳过模型下载；DeepSeek 分析及缺失 WebView2 时的安装仍需要网络。

安装目录会创建 `.env`，`DEEPSEEK_API_KEY` 为空。填写后重启生效；界面保存的 Key 优先，进程环境变量优先于 `.env`。更新安装不会覆盖已有 `.env`；保留数据卸载保留该文件，明确选择清除数据时删除。

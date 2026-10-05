# 本地Embedding模型

模型：qwen3-embedding:4b（Ollama Q4_K_M量化版）
模型目录：models/ollama
运行程序目录：runtime/ollama

下载过程使用Ollama官方模型仓库和Ollama官方GitHub发布资产；全部文件下载完成后校验SHA256。
这不是原始半精度权重版本。

启动方法：在本目录打开PowerShell，执行：

    powershell -ExecutionPolicy Bypass -File .\start-embedding.ps1

接口：http://127.0.0.1:11434/api/embed
模型名：qwen3-embedding:4b
本地Embedding不需要API密钥。DeepSeek用于视觉分析和问答，是另一项服务。

启动脚本只为当前进程设置模型路径与运行参数，不修改系统PATH、不注册开机启动。
Ollama日志保存在logs目录。

来源：
https://ollama.com/library/qwen3-embedding:4b
https://docs.ollama.com/windows
https://docs.ollama.com/api/embed

运行结果见下载完成后生成的embedding-verification.json。
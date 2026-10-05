# Material Reader Implementation Plan

> **For agentic workers:** 使用executing-plans在当前会话逐项实施，不委派。

**Goal:** 读取文字、PDF、图片，保留来源位置与错误，并提供上传接口。
**Architecture:** 独立reader负责逐页解析，vision负责API，store负责持久化，FastAPI只处理请求。
**Tech Stack:** Python、FastAPI、PyMuPDF、Pillow、httpx、python-dotenv。
**Spec:** docs/spec.md

## Constraints
单文件20MiB；最多5文件；PDF30页；文字100000字符；本机绑定；不记录密钥；不静默截断。

## Review Focus
混合PDF含文字和扫描页、空白页、加密PDF、错误模型JSON、视觉接口单页失败、路径穿越文件名、缺失密钥、超限文件。

## Tasks
- [x] 先写读取和API测试，运行确认模块缺失失败。
- [x] 实现配置、结果结构、视觉请求及分页读取；验证上述异常。
- [x] 实现持久化与上传接口；确保材料来源可追溯。
- [x] 安装独立环境，运行离线测试；用合成图片执行真实视觉调用。
- [x] 写启动脚本、使用说明、验证记录，部署到用户目录。

## Verification record
- 12 offline tests passed in the delivered directory.
- Dependency check passed.
- Live synthetic image and mixed PDF passed; amount and negation preserved.
- Actual localhost HTTP text upload passed.
- .env, model/runtime files and user materials are ignored by Git.
- Initial image call produced a schema-invalid response and was correctly marked failed. Subsequent structural inspection and live retest passed; no unsupported claim that model output is always valid.
- Ruling: no automatic API retries in stage 1; failed pages remain explicit and can be resubmitted. This avoids silently increasing API costs or masking inconsistent responses.
- Scope: no RAG, risk conclusions, conversational agent or final chat frontend yet.
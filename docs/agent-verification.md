# Agent阶段验证记录

日期：2026-10-03。使用模拟招聘材料，不作为比赛准确率数据。

- 全部25项自动测试通过；覆盖材料读取、RAG索引、追问、报告、问答、版本修订、历史恢复、会话隔离、报告下载与删除。
- pip check：No broken requirements found。
- 实际DeepSeek API与本地Qwen3-Embedding/Ollama、Chroma混合检索跑通四轮：ask → report（第1版）→ answer → revise（第2版）。
- 真实调用记录：agent-live-verification.json；8条消息、2版报告持久化。
- 服务重启后，HTTP接口读取同一会话成功；报告第2版Markdown下载返回200，含官方来源链接。记录：agent-http-verification.json。
- 曾发现可空字段、漏填字段引起的结构错误，已增加有限格式修复；每次修复后仍验证引用ID及用户原句。不合要求的结果不保存为报告。

当前接口地址：http://127.0.0.1:8000/docs 。初始8条官方依据仅供开发验证，尚不覆盖所有求职风险。正式聊天前端和PDF报告导出尚未实现。模型的法律推理、追问决策及答案质量仍须用独立案例测评；通过软件测试不能证明法律结论总是正确。

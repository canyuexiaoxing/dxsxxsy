# RAG Agent使用说明

本版增加RAG工具检索、主动追问、报告、后续问答/建议、报告修订及SQLite会话持久化。使用本地Ollama 4B模型生成向量，DeepSeek执行工具选择与分析。没有登录系统，薄荷绿聊天前端和桌面窗口现已提供，见桌面版使用说明。

## 启动

首次或修改knowledge/entries.json后执行：
```powershell
powershell -ExecutionPolicy Bypass -File .\build-knowledge.ps1
```
然后启动：
```powershell
powershell -ExecutionPolicy Bypass -File .\start-agent.ps1
```
打开 http://127.0.0.1:8000/docs 。若服务已经运行，请先关闭旧服务，避免8000端口冲突。

## 操作顺序

1. POST /api/materials：上传文字、PDF、图片，记录返回的material_id。
2. POST /api/sessions：以`{"title":"某公司招聘"}`创建会话，记录返回的id。
3. POST /api/sessions/{sid}/messages：提交`{"text":"请分析材料","material_ids":["上一步的材料ID"]}`。
4. action=ask时，在同一接口提交`{"text":"你的补充回答","material_ids":[]}`；不知道时可以明确说不知道、先输出有限报告。
5. action=report时得到报告、引用来源和版本；后续继续提问可得到answer或revise。
6. GET /api/sessions/{sid}读取完整历史；关闭程序重启后使用原sid继续。
7. GET /api/sessions/{sid}/reports/{version}/download下载Markdown报告；PDF导出后续实现。
8. DELETE /api/sessions/{sid}删除会话和不再被其他会话引用的绑定材料。仅上传、尚未绑定的材料不会随会话删除。

无需材料也可以直接创建会话提问。不同会话材料和历史隔离，共享官方知识库。

## 知识库

初始8条依据来自：劳动合同法第八、九、十、十九条；五部门风险提示；北京市人社局典型案例摘要。已核对官方页面，出处、日期、资料类型、原文/摘要、适用边界均可查。

这只是开发用小规模知识库，不能宣称覆盖全部就业权益或替代参赛团队的人工核验。未匹配到依据时应说明不足，禁止依据普通搜索无结果判定不存在。案例明确标明摘要，处理结果不可直接套用。无联网检索/工商核查工具，不能自称已核实企业信用。

向量检索与中文二元词关键词检索融合。改变模型或资料后需要重新建库。知识库修改必须保存真实来源和核验记录，不能把用户材料或模型回答自动入库。

## 输出与限制

- ask：最多3个关键问题。
- answer：解释与建议，原报告不变。
- report：首次报告。
- revise：新版本、change_reason说明变化，旧版本保留。
- 每个风险点有用户原句、材料编号/页码、依据ID、解释和建议。
- 引用ID不存在、原句无法匹配、重复追问或模型格式异常时返回422，不写入伪造报告。
- 本程序核对引用与原句的存在性，不保证模型法律推理正确；需要进一步测评和原文核验。
- 每轮最多6次模型工具循环；会话超过上下文预算时明确报错，不静默丢弃材料。
- 材料和相关会话内容发送至DeepSeek；向量化和持久化在本机。
- 工具轨迹、消息与报告保存在data/sessions.sqlite3；Chroma在data/chroma；密钥仅保留于.env。

## 验证

离线：`.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v`

真实模拟流程：`.\.venv\Scripts\python.exe -B tools/verify_agent_live.py`，会产生DeepSeek API费用；结果在agent-live-verification.json，示例会话明确标为模拟，不作为比赛准确率数据。

# 求职避坑镜：本地 RAG Agent

重点帮助大学生在找实习、找工作、付款和签约前识别异常要求、核实招聘主体与条款，明确先暂停什么、向谁核实什么，再决定是否继续。现已支持文字、PDF、图片读取，以及RAG检索、主动追问、风险报告、后续问答和报告版本修订。同会话记录保存于本机，重启后可继续。已增加薄荷绿聊天前端和Windows桌面窗口。

桌面版双击“启动求职避坑镜.cmd”；网页打开 http://127.0.0.1:8000/ 。见 [桌面版使用说明.md](桌面版使用说明.md)。

后端操作步骤见 [AGENT使用说明.md](AGENT使用说明.md)。以下保留材料读取接口说明。

## 启动

在项目目录打开PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-agent.ps1
```

打开 http://127.0.0.1:8000/docs 。展开`POST /api/materials`，点击`Try it out`，填写text、添加files后点击`Execute`。返回JSON包含材料编号、逐页文字、提取方式、状态及异常；可通过GET接口读取历史材料或下载原文件。

图片识别和扫描PDF需要联网，将图片或页面图像发送给DeepSeek。文字和普通文字版PDF可以本地提取。API密钥由`.env`的`DEEPSEEK_API_KEY`提供，不要提交或分享`.env`。

## 输出约定

- `pages[].page_number`：PDF页码／图片编号；文字输入记为1。
- `method`：text、pdf_text、vision或blank。
- `status`：read（提取成功）、partial（局部缺失／需核对）、failed（失败）、blank（空白页）。read不代表法律结论或人工核验。
- `issues`：无法辨认、裁切、解析失败、接口错误等。
- `extraction_verified=false`：提取内容尚未经人工核验；视觉识别也可能遗漏或误读。
- 材料保存在`data/materials/<材料ID>/`：original为原始字节，result.json为解析记录。
- 不执行上传材料中的任何指令，不把用户材料自动放入公共知识库。

## 限制

单文件20MiB；单次5文件；PDF30页；文字100000字符；图片3000万像素。超限明确拒绝。PDF加密时要求先解密。支持PNG/JPEG/WebP/静态GIF，多帧图片需拆分。输入暂不支持DOCX；报告可导出Word，支持删除会话。

图文混合页采用图片覆盖面积启发式选择视觉识别；小型图片中的文字可能不进入视觉识别，复杂排版和表格仍需核对原文。单页失败会保留其他页的结果。

## 验证

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

`tools/verify_live.py`会生成模拟图片和混合PDF，并真正调用DeepSeek（产生API费用），结果记录在live-verification.json；测试材料标明模拟，不包含个人资料。

## 安装环境（迁移电脑时）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```


模型分析前先整理用户事实，区分已知、未知和有限推测，并与独立复核共享原句依据。实现、固定测试与当前限制见[事实表与固定内容验证](docs/事实表与固定内容验证-20261008.md)。

材料分析默认先追问当前场景的关键缺口，每轮最多3问，结合本会话历次输入积累事实。信息足够或用户主动要求生成时输出报告；明确风险会先在追问消息提醒暂停相关操作。已回答或明确不知道的事项不重复询问，有限报告保留未知，未提供不等于不存在。

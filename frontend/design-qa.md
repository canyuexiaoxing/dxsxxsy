# Design QA · 第一张薄荷绿方案

final result: passed

## 对比目标和证据
- source visual truth: qa/reference.png（原图1484×1060）
- implementation screenshot: qa/desktop-final.jpg（1440×1024）
- viewport: 1440×1024 CSS px；截图为1倍密度。参照图等比例近似归一到1440×1024，用于整体结构比较，非逐像素宣称。
- state: 短会话，用户收费问题、首次风险报告、依据展开；真实官方原文、界面示例标签。数据明确为模拟。
- full-view comparison: qa/compare-before.jpg、qa/compare-after.jpg。
- focused comparison: qa/focus-after.jpg（法规依据、文案与下载控件）；已同时查看参照与实现，未用分开的图片冒充对比。
- responsive evidence: qa/mobile-after.jpg；390×844，document.scrollWidth=390，发送按钮在视口内。

## 比较历史
1. [P2] 报告宽度960px且默认元数据占用过多空间，初始自动滚动隐藏首条用户输入。
   修复：报告宽度850px，缩短内部间距，多条依据分别折叠，适用边界折叠，元数据并排；短会话打开时从顶部显示。
   复查：compare-after中用户材料与报告均出现，输入和下载可用。
2. [P2] 窄窗口的“第九条”被拆成纵向文本；关闭的侧栏仍进入可访问树。
   修复：条号不换行，关闭侧栏visibility:hidden。
   复查：mobile-after与AX树确认，标题与条号可读，会话列表可展开/收起。
3. [P2] 材料原文弹窗初始未隔离背景键盘焦点。
   修复：背景inert、自动焦点、Tab循环、Escape关闭并还原焦点。
   复查：弹窗打开后AX仅列弹窗；关闭后焦点回到原句按钮。

## 五项必查
- Fonts/typography：中文系统字体，主标题23/25px、正文14–16px、辅助文字12–13px。标题层级、换行和窄窗口条号已检查；不把生成图里的字形误差带入产品。
- Spacing/layout：296px侧栏、92px顶栏、850px报告，输入区固定，长对话独立滚动；没有控件碰撞或横向溢出。
- Colors/tokens：薄荷底#effaf5、品牌绿#2b826a、浅灰依据底与琥珀风险提示；绿色不用于宣称招聘绝对安全。焦点和减少动态效果规则存在。
- Image quality：独立生成的低对比侧栏叶片素材；没有CSS/手绘SVG替代装饰。标准图标为Phosphor，清晰且统一。与参照叶片方向有少量差异，P3。
- Copy/content：使用真实接口字段及官方原文，风险层级、版本和资料类型清晰。原文比生成图更完整，因此报告高度略增，是可追溯性需求带来的预期差异。没有虚构指标或无效链接。

## 主流程和限制
浏览器检查：空白会话、真实请求错误保留输入、等待动画、隔离模拟环境的PDF+图片上传、三页读取预览、ask→report→answer→revise、版本切换、历史重载、下载事件、来源折叠和原文预览、窄窗口侧栏、Escape关闭。浏览器console error/warn检查为空。
真实DeepSeek在本次调用返回402，新真实分析没有成功；完整流程本次使用明确标注的模拟模型。该外部接口限制不被隐藏为模拟成功，需单独检查账户可用额度。
桌面：pywebview的loaded事件写入logs/desktop-loaded.txt，确认WebView已加载本机页面；未使用原生窗口截图审查，桌面内页面复用浏览器已检查的同源构建产物。

## Implementation Checklist
- [x] selected visual layout and generated asset
- [x] real same-origin API wiring, no frontend secrets
- [x] error/loading/empty/report states and motion reduction
- [x] report references, material preview, versions, downloads
- [x] desktop and mobile comparison after fixes
- [x] desktop launcher and local service lifecycle

## Follow-up Polish
P3：叶片细节和标准库盾牌图标与生成图不是逐像素一致。会话时间采用真实保存日期，示例不显示虚构时间或附件。独立exe安装包、PDF导出与自动更新尚未制作。

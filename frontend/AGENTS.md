# Prototype Instructions

Run the local server yourself and open the preview in the browser available to this environment. Do not give the user server-start instructions when you can run it.

Before making substantial visual changes, use the Product Design plugin's `get-context` skill when the visual source is unclear or no longer matches the current goal. When the user gives durable prototype-specific design feedback, preferences, or decisions, record them in `AGENTS.md`.

When implementing from a selected generated mock, treat that image as the source of truth for layout, component anatomy, density, spacing, color, typography, visible content, and hierarchy.

Build app UI in `src/`. Keep `.openai/hosting.json`, `worker/index.js`, `scripts/prepare-sites-build.mjs`, and `tests/sites-worker.test.mjs` intact so the same local prototype can be handed to Sites. Before a Sites handoff, run `npm run build` and `npm run test:sites`; the build must leave `dist/client/index.html`, `dist/server/index.js`, and `dist/.openai/hosting.json`.

产品定位：重点帮助大学生在找实习、找工作、面试、接受录用和签约前规避风险。默认入口与报告应优先展示预防行动和核查条件，拟签条款不能描述为已发生的用工纠纷。

生成期间允许切换或新建会话、查看材料和设置，发送按钮保持禁用；全局提供停止生成按钮。停止仅清理本次新材料和未保存结果，不删除历史资料。后台完成不得切回旧会话或清空新会话的输入。

历史列表提供逐会话删除入口，确认后删除聊天、全部报告和专属附件，保留共享附件、知识库及设置。删除其他会话不能清空当前输入，正在生成的被删会话须停止并防止结果回写。

材料有重要缺口时，对话先显示1至3个追问，再显示基于现有信息的简短分析和措施；不得用长篇普通回复替代报告。已回答或明确无法取得的信息不重复追问。仅用户明确要求时生成或修订报告。

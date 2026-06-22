# 小学期末复习 App — 构建计划 & 进度（断点续作的"保命文件"）

> ⏱️ **撞墙/新会话续作指南**：如果上一会话撞到 token 5 小时窗口限制中断，
> 新会话**先读本文件 + 跑 `git log --oneline`**，即可立刻知道整体方案、当前进度、下一步，无缝继续。
> 不要依赖会话记忆——一切以本文件 + git 提交为准。

---

## 一、项目背景与约束（已与用户程令敲定）

- **谁用**：程令五年级孩子一个人用，iPad Pro 上用。无需账号/多用户。
- **科目**：数学、语文、英语。用途：期末复习。
- **形态**：PWA 网页 App（iPad Safari "加到主屏"全屏）。不上原生 App。
- **可迁移性 = 最高优先级**：Docker Compose + 数据全落挂载卷 + .env 配置。
  迁移 = 拷目录 + `docker compose up`。现服务器在海外，后续迁国内服务器/家用小主机。
- **隐私**：全自托管，孩子数据只在自己机器 ↔ 模型 API 之间。
- **代码位置**：`~/workspace/kids-review-app/`

## 二、模型策略（2026-06-20 改用 OpenRouter）

- **接入：OpenRouter**（一个 Key 调所有模型）。⚠️ 注意：DeepSeek 在 OpenRouter **不收图片**，故读图必须用视觉模型。
- 角色分层（已真机验证）：
  - 读图/提取 → `openrouter:qwen/qwen3-vl-235b-a22b-instruct`（中文手写强，~$0.2/M）
  - 推理/分析/出题/讲解 → `openrouter:deepseek/deepseek-v4-flash`（便宜，~$0.09/M）
  - 视觉兜底 → `openrouter:google/gemini-2.5-flash`
- 一轮全量分析成本：分级别（几分钱级）。换模型只改 `.env`。
- 语音(ASR/TTS)：OpenRouter 暂无，三期走百炼/讯飞。
- **语音（AI 老师辅导用）**：DeepSeek 无语音，**独立接入** ASR+TTS（讯飞/豆包/阿里百炼）。
- **统一适配层**：OpenAI 兼容接口，provider 可插拔，换模型只改配置。
- **不用 Agent 框架**：确定性代码编排；"记忆"靠结构化 DB + 调用时喂相关上下文。
- **结构化输出**：模型一律强制 JSON Schema。

## 三、功能全集

1. 上传中心：拍照/相册多选上传 + 素材管理
2. 全局知识点分析报告：重复度/难度/超纲度
3. 知识树/知识图谱视图：可视化 + 点击详情 + 打勾圈选重点
4. 薄弱点中心：自动总结 + 每点一键生成讲解+练习
5. **AI 老师·知识点辅导（多轮多模态）**：初始讲解 → 语音/手写拍照提问 → 多轮一对一 → 出题判定掌握 → 回写掌握度。语音一期用"按住说话"回合制。
6. 一键模拟卷：三来源**手动勾选**组卷（a 全局自动抽选 / b 圈选重点必出 / c 薄弱点必出）+ 配题量/题型/难度/总分 + 答案解析 + 打印 PDF
7. 做题与批改：在线做题自动判分 + 错题回流闭环

## 四、技术栈（已定）

- 后端：Python + FastAPI + SQLite（一期；适配层预留升 Postgres）
- 前端：轻量 PWA（先 vanilla HTML/JS，可加到主屏）
- 反代：Nginx（HTTPS + WebSocket 语音 + 静态资源）
- 编排：Docker Compose；配置 .env
- LLM：OpenAI 兼容 SDK 调 DeepSeek/Qwen（百炼）等

## 五、分期

- **一期（进行中）**：Docker 骨架 + 上传 + DeepSeek 读图提取 + 薄弱点分析。跑通真实试卷，验证手写识别效果与成本。
- **二期**：知识树可视化 + 一键模拟卷 + 单点出题/讲解。
- **二期后段/三期**：AI 老师多轮辅导 + 语音 ASR/TTS 接入 + 做题判分闭环 + 界面打磨。

---

## 六、任务清单（实时勾选）

**一期（核心）—— 全部完成 ✅**
- [x] T1 项目骨架：目录、.gitignore、README、docker-compose、.env.example
- [x] T2 LLM 适配层：OpenAI 兼容 client + provider 配置 + 重试 + JSON + DRY_RUN
- [x] T3 Prompt 模板：提取/全局分析/薄弱点/讲解/模拟卷/辅导/掌握判定
- [x] T4 数据层：SQLite schema + DAO（材料/题目/知识点/关系/薄弱点/卷子/辅导会话）
- [x] T5 上传服务：接图 + Pillow 压缩(降本) + 存盘 + 入库
- [x] T6 提取服务：图 → 结构化 JSON（题目/对错/知识点）
- [x] T7 分析服务：全局知识点 + 薄弱点自动总结 + 单点讲解练习
- [x] T8 FastAPI 路由：全套 API
- [x] T9 前端：5-tab PWA（上传/分析知识树/薄弱点/模拟卷/AI老师）+ manifest/sw/icon
- [x] T10 Docker：compose 起 nginx+backend，经代理验证全链路
- [x] T11 真机验证：**已用 OpenRouter 真机跑通**（2026-06-20）。视觉=Qwen3-VL 正确读图/判对错/标知识点；推理=DeepSeek-v4-flash 正确分析薄弱点。真实手写照片待用户上传验证。

**二期能力（已提前实现）✅**
- [x] 知识树数据 + 前端列表/掌握度/圈选重点
- [x] 一键模拟卷（三来源手动勾选：自动抽选/重点必出/薄弱点必出）+ 打印
- [x] 单点出题/讲解

**三期（部分实现）**
- [x] AI 老师多轮辅导：初始讲解→多轮(文字/拍照)→出题判定掌握→回写掌握度（文本+视觉链路已通）
- [ ] 语音 ASR/TTS 真接入（前端"按住说话"按钮已占位，待接百炼/讯飞语音）
- [ ] 知识图谱可视化升级为图形（当前为带掌握度的列表+勾选，足够用；后续可上 d3/react-flow）
- [ ] 在线做题答题卡 UI（当前模拟卷支持查看/打印/显隐答案；在线作答判分可再做）

---

## 七-bis、v2 已上线(2026-06-20)

**三模块产品已落地并部署上线**,真实 OpenRouter 端到端验证通过:
- IA:首页(我的学习舱)/ 知识图谱(含上传)/ AI老师(问答+出卷)。
- 后端新增:异步分析队列(jobs)、仪表盘(dashboard)、知识点详情(chat.kp_detail)、自我练习+错题本(practice/wrongbook)、AI chat。
- 前端:`frontend/` 根目录 index/practice/graph/teacher + api.js,接真实后端(旧 app.js 废弃)。
- 文档:`docs/PRD.md`、`docs/TECH_DESIGN.md`(含 API 契约),**每次迭代须同步更新**。
- 部署:`docker compose up -d --build`,:8080,真实 OpenRouter(.env 已配 key,LLM_DRY_RUN=false)。
- 真机验证:上传测试卷→异步分析~66s→知识图谱10点/仪表盘综合掌握度0.4/6薄弱点,全自动出真实数据。
- 截图工具脚本 /tmp/shot/*.js(puppeteer)。**发飞书多图必须每张重复 --images**(见记忆 botmux-multi-image-flag)。
- 待办(M3):语音 ASR/TTS、在线答题卡判分、激励体系、知识图谱图形增强。

## 七-ter、(已于 2026-06-20 部署上线 ✅)演示中的迭代批

> 已 `docker compose up -d --build` 部署,数据保留(31素材/117题),全项验证通过:去重生效、薄弱点口径=16(对上图谱)、缓存/题库/刷新可用、schema自动迁移。下面是当时清单:

> 演示期间只改了静态前端(免重启已生效);以下后端改动**已写好+DRY_RUN自测过+已提交**,但需重建后端容器(~30s,会重置内存里的分析队列)才生效。重启时一次性核对:
1. **去重**:upload 按图片 sha256,重复图不重复入库/分析。
2. **分析提速**:jobs 批内并行提取(4 并发)。
3. **薄弱点口径统一**:dashboard 薄弱点=掌握度<0.6 的知识点(与图谱红节点一致),修首页计数与图谱对不上。
4. **list 绑定 bug**:db._txt 防模型返回数组导致入库报错;busy_timeout 防并发锁。
5. **讲解/详情缓存**:kp_content 表;kp_detail 的 intro、explain 的讲解+例题 生成一次即缓存,秒开。
6. **练习题库**:question_bank 表;practice 优先从题库选,不够/refresh 才调 AI 并入库。
7. **刷新按钮**:/weak/explain、/practice/generate 加 refresh 参数;前端首页讲解弹窗"换一批练习"、练习页"AI出新题"。

**已对线上即时生效(免重启)的前端热修**:练习选择题改按钮、出题进度条、模拟卷types修422、知识图谱上传压缩修413。

## 七、当前状态 / 下一步(历史)

- **状态（2026-06-19 深夜）**：一期 + 二期 + 三期核心逻辑全部跑通，DRY_RUN 冒烟 7/7 绿，Docker 全栈经 nginx 验证通过。三次 git 提交留存。
- **唯一阻塞**：T11 真机验证需用户提供 **DeepSeek 或 阿里云百炼 API Key**。
- **续作/真机怎么做**：
  1. `cp .env.example .env`，填 `DEEPSEEK_API_KEY`（或 `BAILIAN_API_KEY`），把 `LLM_DRY_RUN=false`；
  2. 核对 `.env` 里模型名（`VISION_MODEL`/`REASON_MODEL` 的 `provider:model_id`）是否为对应平台真实模型名；
  3. `docker compose up -d --build` → 访问 `http://<本机IP>:8080`，加到主屏；
  4. 真试卷跑一轮，重点看**手写识别准确度**；不行就把 `VISION_MODEL` 切到 `bailian:qwen-vl-max`。
- **下一步建议**：① 真机验证手写识别 → ② 语音 ASR/TTS 接入 → ③ 知识图谱图形化 / 在线答题卡。
- **本地验证命令**：`cd backend && DATA_DIR=/tmp/x LLM_DRY_RUN=true python3 smoke_test.py`

## 八、关键决策记录

> 2026-06-19 深夜：用户授权**全自主执行，不打扰**。以下待定项已自行拍板（用户早上可推翻）：

- **语音交互**：A「按住说话」回合制；老师回复文字为主 + 可点 TTS 朗读。
- **语音供应商**：默认阿里云百炼（一平台含 DeepSeek+Qwen-VL+语音，单 Key，国内直连）。
- **DB**：一期 SQLite。
- **出题**：三来源手动勾选，非加权。
- **无 Key 处理**：实现 `LLM_DRY_RUN` 模拟模式，无 Key 也能跑通链路；真机验证(T11)等用户早上填 Key。**不半夜打扰用户。**

# 期末复习助手 — 技术方案文档

> 版本:v1.0 · 2026-06-20 · 每次迭代同步更新(尤其 API 契约与数据模型)

## 1. 总体架构
```
iPad Safari PWA (三模块前端, vanilla JS)
   │ HTTPS
Nginx (反代 + 静态托管 + /api 代理 + /ws 预留)
   │
FastAPI 后端 (确定性编排, 不依赖 Agent 框架)
   ├─ LLM 统一适配层 (OpenAI 兼容, Provider 可插拔)
   │     · 视觉/提取  → OpenRouter: qwen/qwen3-vl-235b-a22b-instruct
   │     · 推理/出题/讲解 → OpenRouter: deepseek/deepseek-v4-flash
   │     · 视觉兜底  → OpenRouter: google/gemini-2.5-flash
   ├─ 异步分析队列 (后台线程: 提取→全局分析→薄弱点)
   └─ SQLite (题目/错题/知识点/掌握度/卷子/辅导/练习/错题本)
数据与文件全部落在 ./data 挂载卷 → 拷目录即迁移
```

## 2. 技术选型
| 层 | 选型 | 理由 |
|---|---|---|
| 后端 | Python + FastAPI | 异步友好、轻、生态好 |
| DB | SQLite(一期) | 单用户零运维、单文件易迁移;适配层预留升 Postgres |
| 前端 | vanilla HTML/CSS/JS(PWA) | 无构建、可加到主屏、迁移省事 |
| 反代 | Nginx | HTTPS/静态/代理/WebSocket(语音预留) |
| 模型 | OpenRouter(一个 Key 调所有) | 多模型搭配;DeepSeek 不收图片故视觉用 Qwen-VL |
| 编排 | Docker Compose + .env | 一键起、整体迁移 |

## 3. 后端模块
- `config.py` 配置(env);`db.py` SQLite schema+DAO;`llm/` 适配层+prompts+mock(DRY_RUN)。
- `services/`:images(压缩)、extract(读图提取)、analyze(全局/薄弱/讲解)、exam(三来源组卷)、tutor(多轮辅导)、**practice(自我练习,新)**、**jobs(异步分析队列,新)**、**dashboard(聚合,新)**。
- `routers/api.py` 路由。

## 4. API 契约(前端按此对接;改动须更新本节)
### 通用/状态
- `GET /api/status` → {dry_run, materials, questions, weak_points, exams}
- `GET /api/analysis/status` → {running:bool, pending:int, version:int, updated_at} — 驱动"分析中/是否更新"
### 首页
- `GET /api/dashboard` → {overall_mastery, subjects:[{subject,mastery}], weak_points:[{knowledge_point,subject,mastery}], streak_days, trend:[{date,mastery}], recent:[{type,text,time}], counts:{questions,weak}}
### 上传 + 知识图谱
- `POST /api/upload` (multipart files[], 可单可多) → 立即存盘 + **入队异步分析** → {uploaded:[{material_id,filename}], queued:true}
- `GET /api/knowledge` → {knowledge_points:[{name,subject,frequency,difficulty,beyond_syllabus,mastery}], relations:[{from,to,type}]}
- `GET /api/knowledge/detail?name=&subject=` → {name,subject,mastery, intro, questions:[...历史题], wrong_questions:[...]}
- `POST /api/analyze/global` / `POST /api/analyze/weak` → 手动触发(平时由异步队列自动跑)
- `GET /api/report` → 全局分析报告(summary + 维度)
### 薄弱点
- `GET /api/weak` → [{knowledge_point,subject,mastery,why,typical_errors}]
- `POST /api/weak/explain` {knowledge_point, errors?} → {explanation, worked_example, practice:[...]}
### 自我练习 + 错题本(新)
- `POST /api/practice/generate` {scope:'subject'|'kp'|'weak'|'wrongbook', value?, count?} → {questions:[{id,type,stem,options?,answer,explanation,knowledge_points}]}
- `POST /api/practice/submit` {question, child_answer} → {correct:bool, correct_answer, explanation}(客观题可前端判,主观题走模型)
- `GET /api/wrongbook` → [...]; `POST /api/wrongbook/add` {question} → {ok}
### AI 老师
- `POST /api/chat` {session_id?, message, topic?, image?(multipart)} → {session_id, reply, ask_back?, mastered?}
- `POST /api/exam/generate` {subject, auto_points?, focus_points?, weak_points?, num,types,difficulty,total} → 卷子 + exam_id
- `GET /api/exams` / `GET /api/exams/{id}`

## 5. 数据模型(SQLite 主要表)
materials / questions / knowledge_points / kp_relations / weak_points / exams / tutor_sessions(见 db.py),新增:
- `practice_items`(可选,记录练习产出);`wrongbook`(错题本:question json, source, created_at)。
- knowledge_points.mastery 为掌握度闭环核心(判分/掌握判定回写)。

## 6. 异步分析设计
- 单进程内 `ThreadPoolExecutor(1)` 串行队列;`POST /upload` 存图后 `enqueue(material_ids)`。
- Job:逐张提取 → 跑全局分析 → 跑薄弱点 → `version++` + 更新 `updated_at`。
- `GET /api/analysis/status` 暴露 {running, pending, version}。前端记住已渲染 version,发现 version 变大且空闲→提示/静默更新。

## 7. 模型与成本
- 视觉提取 Qwen3-VL(~$0.2/M),推理 DeepSeek-v4-flash(~$0.09/M);图片前端压缩到长边 1600。
- 一轮全量分析 ≈ 几分钱。Key 仅在 `.env`(gitignore)。换模型只改 `.env`。

## 8. 部署 / 运维
- `cp .env.example .env`(填 OPENROUTER_API_KEY, LLM_DRY_RUN=false)→ `docker compose up -d --build`。
- 访问 `http://<host>:8080`;远程经 SSH 隧道 `ssh -L 8080:localhost:8080 ubuntu@<ip>`。
- 迁移:拷整个目录(含 ./data)到新机 → `docker compose up -d`。
- 备份:定期备份 `./data`(SQLite + 上传图 + 生成文件)。

## 9. 安全/隐私
- 全自托管;孩子数据仅 本机 ↔ OpenRouter。API Key 不入库不进 git。
- nginx body 限制 + 前端压缩;后续可加访问口令。

## 10. 迭代记录
- v1.0 (2026-06-20):三模块落地 + 异步分析 + 自我练习 + 错题本 + AI chat + 部署。
- **v1.1 (2026-06-20)**:
  - 上传去重(图片 sha256,materials.hash);异步分析并行提取(4)。
  - 薄弱点统一口径:掌握度<0.6 的知识点(与图谱红节点一致)。
  - **缓存/题库**:kp_content(讲解/详情缓存)、question_bank(题库);讲解/详情/出题优先读缓存/题库,refresh 才调 AI 并入库。
  - **每日一练**:首页入口 → practice.html?mode=daily,自动 weak 范围出题、可中断。
  - 上传"最小化到后台"浮窗;练习选择题改按钮;出题进度条。
  - **组卷提速**:exam.generate 优先题库组卷(秒出),不够才 AI;每卷唯一编号 `code`(SJ-XXXXX)。
  - **拍照判分**:`POST /exam/grade`(multipart image)→ 视觉识别编号+作答 → exam_by_code 匹配 → 逐题判分 → exam_results 存档 + 错题入本。新增 exam_results 表、`/exam/results`。
  - **部署到 443/HTTPS**:nginx 80(隧道,无密码)+443(公网,自签 TLS+basic auth 访问密码);证书/口令在 nginx/certs(gitignore)。需 AWS 安全组放行 443。公网 `https://3.138.198.65`。
  - 新增/变更 API:`/analysis/status` `/dashboard` `/knowledge/detail` `/chat` `/practice/*` `/wrongbook` `/exam/grade` `/exam/results`;`/weak/explain`、`/practice/generate`、`/exam/generate` 加 `refresh`。
- **v1.2 (2026-06-20)**:
  - **公网访问改用 Caddy + Let's Encrypt**(免费 nip.io 域名 `https://3-138-198-65.nip.io`),根治自签证书在手机上导致的 fail-to-fetch;basic auth 保留(Caddyfile gitignore)。旧 nginx/ 弃用。
  - **移动端适配**(viewport-fit/100dvh/safe-area/窄屏响应式)。
  - **知识图谱三档响应式**(按屏宽):≥1024 图谱+右侧固定详情栏;700–1023 图谱占满全宽+详情右侧浮层(不占图谱宽);≤699 知识点列表+点开全屏二级详情页(带返回)。根因:中屏固定侧栏挤掉图谱空间。
  - **试卷打印**:`@media print` 只打纯卷子(黑字白底/全页/隐藏按钮/不打答案/保留编号)。
- (后续迭代在此追加)

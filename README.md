# 小学期末复习 App

给孩子做期末复习的自托管网页应用（PWA）。家长拍试卷/错题照片 → AI 分析知识点、总结薄弱点、出模拟卷、一对一辅导。

## 特点

- **自托管 + 可迁移**：Docker Compose 一键起，数据全在 `./data` 挂载卷。迁移 = 拷目录 + `docker compose up`。
- **大小模型分层**：便宜模型读图提取，强模型推理分析。OpenAI 兼容适配层，换模型只改 `.env`。
- **隐私**：孩子数据只在你的机器 ↔ 模型 API 之间。

## 快速开始

```bash
cp .env.example .env
# 编辑 .env：填 DEEPSEEK_API_KEY 或 BAILIAN_API_KEY，并把 LLM_DRY_RUN 改为 false
docker compose up -d --build
# 打开 http://<本机IP>:8080
```

> 不填 Key 也能跑：保持 `LLM_DRY_RUN=true`，用内置模拟数据体验完整流程。

## 本地开发（不用 Docker）

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATA_DIR=../data LLM_DRY_RUN=true uvicorn app.main:app --reload
# 前端：直接用浏览器开 frontend/index.html，或 nginx 托管
```

## 进度

见 [BUILD_PLAN.md](./BUILD_PLAN.md)。

## 目录

```
backend/   FastAPI 后端（适配层 / 服务 / 路由）
frontend/  PWA 前端（vanilla，可加到主屏）
nginx/     反向代理
data/      运行时数据（挂载卷，gitignore）
```

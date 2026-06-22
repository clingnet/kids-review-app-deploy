"""FastAPI 入口。"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import get_settings
from .routers.api import router as api_router

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="小学期末复习 App", version="0.1.0")

# 本地开发时前端可能从 file:// 或别的端口访问
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    s = get_settings()
    logging.getLogger("main").info(
        "启动完成 dry_run=%s data_dir=%s", s.llm_dry_run, s.data_dir)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# ===== 原生部署（无 Docker/Caddy）：由同一 uvicorn 进程服务前端 PWA =====
# 必须在所有 API 路由注册之后挂载，"/" 兜底静态资源不会遮挡 /api/* 与 /docs。
import os as _os
from pathlib import Path as _Path
from fastapi.staticfiles import StaticFiles as _StaticFiles

_frontend_dir = _os.environ.get("FRONTEND_DIR") or str(
    _Path(__file__).resolve().parents[2] / "frontend"
)
if _os.path.isdir(_frontend_dir):
    app.mount("/", _StaticFiles(directory=_frontend_dir, html=True), name="frontend")
    logging.getLogger("main").info("前端静态服务已挂载: %s", _frontend_dir)
else:
    logging.getLogger("main").warning("未找到前端目录，跳过静态挂载: %s", _frontend_dir)

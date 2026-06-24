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

# ===== 访问保护：HTTP Basic Auth（公网暴露时保护孩子数据）=====
# 沿用原 Caddy 方案的用户名 'review'。用户名/密码来自配置(get_settings 读 .env)，
# 这样任何启动方式都生效。密码为空则不拦截(本地开发)。/api/health 放行(探活)。
import base64 as _b64
import secrets as _secrets
from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware
from starlette.responses import Response as _Response


class _BasicAuthMiddleware(_BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        s = get_settings()
        auth_pass = s.basic_auth_pass
        if not auth_pass or request.url.path == "/api/health":
            return await call_next(request)
        auth_user = s.basic_auth_user or "review"
        ok = False
        h = request.headers.get("Authorization", "")
        if h.startswith("Basic "):
            try:
                u, _, p = _b64.b64decode(h[6:]).decode("utf-8").partition(":")
                ok = _secrets.compare_digest(u, auth_user) and _secrets.compare_digest(p, auth_pass)
            except Exception:
                ok = False
        if not ok:
            return _Response(
                "需要登录", status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="kids-review"'},
            )
        return await call_next(request)


# add_middleware 后加的在最外层、最先执行 —— 认证先于一切
app.add_middleware(_BasicAuthMiddleware)

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

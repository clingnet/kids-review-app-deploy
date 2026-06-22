#!/usr/bin/env bash
# 原生部署（无 Docker/Caddy）：venv + uvicorn 单进程同时服务 API 与前端 PWA。
# 适用于无 Docker、sudo 受限的机器（用 venv 自带 pip + 国内镜像装依赖）。
#
# 用法：
#   PORT=8000 ./run-native.sh            # 前台启动
#   PORT=8000 nohup ./run-native.sh > app.log 2>&1 &   # 后台
#
# 首次会建 venv 并装依赖；之后复用。LAN 访问：http://<本机IP>:$PORT
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
PORT="${PORT:-8000}"
PIP_MIRROR="${PIP_MIRROR:-https://pypi.tuna.tsinghua.edu.cn/simple}"

# 1) venv —— 兼容「Debian/Ubuntu 拆走 ensurepip」的机器（无 sudo）：
#    先常规建；失败则 --without-pip 建壳，再用 get-pip.py 引导 pip。
if [ ! -x "venv/bin/python" ]; then
  echo "[run-native] 创建 venv ..."
  if ! python3 -m venv venv 2>/dev/null; then
    echo "[run-native] 常规 venv 失败(缺 ensurepip)，改用 --without-pip + get-pip 引导 ..."
    rm -rf venv
    python3 -m venv --without-pip venv
  fi
fi
# 确保 venv 里有 pip（没有就用 get-pip 引导）
if ! ./venv/bin/python -m pip --version >/dev/null 2>&1; then
  echo "[run-native] 引导 pip（get-pip.py）..."
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
  ./venv/bin/python /tmp/get-pip.py -i "$PIP_MIRROR"
fi
echo "[run-native] 安装依赖（镜像：$PIP_MIRROR）..."
./venv/bin/python -m pip install -q --upgrade pip -i "$PIP_MIRROR" || true
./venv/bin/python -m pip install -q -r backend/requirements.txt -i "$PIP_MIRROR"

# 2) 首次无 .env 则从示例生成（默认 dry-run，不需要 API key 也能跑起来；
#    填好 OPENROUTER_API_KEY 并把 LLM_DRY_RUN 改 false 即开启 AI）
if [ ! -f .env ]; then
  if [ -f .env.example ]; then cp .env.example .env; fi
  # 强制 dry-run，避免无 key 启动报错
  if grep -qi '^LLM_DRY_RUN=' .env 2>/dev/null; then
    sed -i 's/^LLM_DRY_RUN=.*/LLM_DRY_RUN=true/I' .env
  else
    echo 'LLM_DRY_RUN=true' >> .env
  fi
  echo "[run-native] 已生成 .env（LLM_DRY_RUN=true，AI 暂为占位；加 key 后改 false 启用）"
fi

# 3) 数据目录 + 前端目录
export DATA_DIR="${DATA_DIR:-$ROOT/data}"
mkdir -p "$DATA_DIR"
export FRONTEND_DIR="${FRONTEND_DIR:-$ROOT/frontend}"

# 4) 导出 .env 到环境（pydantic-settings 也会读 .env，这里再保险一次）
set -a; [ -f .env ] && . ./.env; set +a

echo "[run-native] 启动 uvicorn 0.0.0.0:$PORT （前端：$FRONTEND_DIR，数据：$DATA_DIR）"
exec ./venv/bin/uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "$PORT"

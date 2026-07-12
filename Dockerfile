# ===== Stage 1: 构建前端 =====
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# 同源部署：前端由 Flask 托管，API 走相对路径
ENV VITE_API_BASE_URL=/
RUN npm run build

# ===== Stage 2: 后端运行时 =====
FROM python:3.11

# 从 uv 官方镜像复制 uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /app/backend

# 先复制依赖描述文件以利用缓存
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# 复制后端源码、脚本、语言包
COPY backend/ ./
COPY locales/ /app/locales/

# 前端构建产物（由 Flask 托管）
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist

ENV FLASK_DEBUG=False \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

EXPOSE 5001

# workers 必须为 1：模拟子进程在 Flask 进程内存中跟踪
# timeout 600：本体/报告生成等长请求可达数分钟
CMD ["sh", "-c", ".venv/bin/gunicorn --workers 1 --threads 8 --timeout 600 --bind 0.0.0.0:${PORT:-5001} wsgi:app"]

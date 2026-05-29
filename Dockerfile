# ============================================================
# 阶段1: 构建前端
# ============================================================
FROM node:20-alpine AS frontend-builder

# 根目录依赖（chart.js 被前端代码引用，但声明在根 package.json）
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# 前端依赖 + 源码
COPY frontend/package.json frontend/package-lock.json frontend/
WORKDIR /app/frontend
RUN npm ci

COPY config/ /app/config/
COPY frontend/ ./
RUN npm run build

# ============================================================
# 阶段2: 运行时镜像
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# steam_sync 通过 subprocess + curl 调用 Steam API
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# 复制后端代码
COPY backend/ backend/

# 复制配置文件
COPY config/ config/

# 从前端构建阶段复制 dist
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# 创建数据持久化目录
RUN mkdir -p /app/backend/static/images /app/backend/data

EXPOSE 8000

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

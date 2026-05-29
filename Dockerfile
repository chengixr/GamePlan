# Stage 1: 构建前端
FROM node:20-alpine AS frontend-build
WORKDIR /build

# 根目录依赖（chart.js / vue-chartjs，Vite 会从上层 node_modules 解析）
COPY package*.json ./
RUN npm ci

# 前端依赖 + 构建
COPY frontend/package*.json frontend/
RUN cd frontend && npm ci
COPY frontend/ frontend/
COPY config/ config/
RUN cd frontend && npm run build

# Stage 2: 运行时
FROM python:3.12-slim
WORKDIR /app

# steam_sync 依赖 curl
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/
# 复制前端构建产物
COPY --from=frontend-build /build/frontend/dist ./frontend/dist/
# 复制配置（敏感值通过环境变量注入）
COPY config/ ./config/

# 数据持久化目录
VOLUME ["/app/data"]

ENV DATABASE_URL=sqlite:////app/data/gameplan.db
ENV BACKEND_HOST=0.0.0.0
ENV BACKEND_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

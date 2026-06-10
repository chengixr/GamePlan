# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

GamePlan — 基于 Steam 热销榜的游戏推荐网站。用户对游戏打分（1-5星），系统通过标签相似度 + 协同过滤混合推荐，迭代构建用户画像。

## 技术栈

- **前端**: Vue 3 SPA (Vite + Vue Router + Pinia)
- **后端**: Python FastAPI + SQLAlchemy + SQLite
- **认证**: Session Cookie（内存存储，重启丢失）
- **部署**: 生产模式 FastAPI 直接托管前端静态文件，无需 Nginx

## 常用命令

```bash
# 开发模式
cd backend && uvicorn main:app --reload --port 8000   # 后端
cd frontend && npm run dev                             # 前端 (http://localhost:5173)

# 生产模式
./start.sh prod                    # 构建前端 + 启动后端 → http://localhost:8000

# 构建前端
cd frontend && npm run build       # 产物在 frontend/dist/

# 重置数据库（删除后重启自动重建 + 导入种子数据）
rm backend/gameplan.db
```

## 部署

### 方式一：start.sh（VPS/裸机）

```bash
./start.sh prod    # 构建前端 + 后台启动 → http://localhost:8000
```

日志文件：`/tmp/gameplan.log`，进程管理用 `fuser -k 8000/tcp` 停止。

### 方式二：Docker

```bash
# 构建并启动
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

数据持久化在 `gameplan_data` volume，数据库路径 `/app/data/gameplan.db`。

### 环境变量

生产部署通过 `.env` 文件或 `docker-compose.yml` 的 `environment` 注入（不写入 `config.json`，避免密钥泄露）。

| 变量 | 说明 | 必填 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | LLM 功能必填 |
| `LLM_ENABLED` | 启用 LLM 标签提取/中文名生成 | 否，默认 `false` |
| `SECRET_KEY` | Session 加密密钥 | 推荐 |
| `BACKEND_PORT` | 后端端口 | 否，默认 `8000` |
| `BACKEND_HOST` | 监听地址 | 否，默认 `0.0.0.0` |

项目根目录 `.env` 文件由 `backend/config.py` 的 `_load_dotenv()` 自动加载，不覆盖已存在的系统环境变量。`.env` 已在 `.gitignore` 中，不会提交。

## 架构要点

### 配置系统

所有端口和基础配置集中在 `config/config.json`，环境变量可覆盖。`backend/config.py` 和 `frontend/vite.config.js` 都从该文件读取。

### 认证

`backend/auth.py` — 基于内存 dict 的 session store（`SESSION_STORE`），`get_current_user` 依赖从 cookie 读取 session_id。生产环境应替换为 Redis 或数据库 session。

### 推荐引擎 (`backend/recommender.py`)

- **冷启动**: 评分 < 5 个 → 返回热销榜所有游戏
- **混合打分**: `标签Jaccard相似度 × 0.6 + 协同过滤 × 0.4 - 已推荐降权`
- **标签相似度**: 用户高分（≥4）游戏的标签集合与候选游戏的 Jaccard 系数
- **协同过滤**: 用户间评分余弦相似度，取 Top-10 相似用户的偏好
- **去重**: 已评分游戏排除，`recommendation_history` 中已推荐的分数 × 0.5

推荐结果在每次请求 `/api/games/recommended` 时实时计算，当前页结果写入 `recommendation_history`。

### Steam 数据同步 (`backend/steam_sync.py`)

使用 `subprocess` + `curl` 调用 Steam Store API（Python HTTP 库在此环境被墙）。定时任务通过 APScheduler 每天凌晨 2 点执行。Steam 不可用时静默失败。

### 种子数据 (`backend/seed_data.py`)

60 款真实 Steam 游戏，覆盖 FPS、RPG、生存、模拟等多种类型。数据库为空时自动导入。

### 生产模式前端托管

`backend/main.py` 中检测 `frontend/dist/` 存在时自动挂载静态文件，并为 SPA 路由做 fallback 到 `index.html`。CORS 允许源自 `config.json` 中配置的前后端端口。

### 数据库关联

Game-Tag 多对多通过 `game_tag_assoc` Table 对象（非模型类），查询时需 `joinedload(Game.tags)` 来 eager load 标签。


### git推送

每次修改后都自动推送到github仓库：https://github.com/chengixr/GamePlan.git
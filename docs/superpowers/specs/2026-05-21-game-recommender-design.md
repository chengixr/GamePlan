# 游戏推荐系统 - 设计文档

> 日期：2026-05-21 | MVP 阶段

## 概述

基于 Steam 每日热销榜的游戏推荐网站。用户对游戏进行 1-5 星评分，系统结合标签相似度和协同过滤算法，迭代推荐相关游戏，逐步构建用户画像。

用户画像并非独立的数据结构，而是由用户的评分记录隐式构成——评分数据即是用户偏好的表达，直接驱动推荐计算。

## 技术栈

| 层 | 选型 |
|---|------|
| 前端 | Vue 3 SPA + Vue Router + Pinia |
| 后端 | Python FastAPI |
| 数据库 | SQLite |
| 认证 | 用户名+密码，Session Cookie |
| 部署 | Nginx + Uvicorn，单服务器 |

## 架构

```
Nginx (静态文件 + /api/* 代理)
 ├── Vue 3 SPA (/, /login, /register, /hot, /recommend)
 └── FastAPI (/api/*)
      ├── 用户认证
      ├── 游戏/评分 CRUD
      ├── 推荐引擎
      ├── Steam 数据同步 (APScheduler)
      └── SQLite
```

Vue 打包后的静态文件由 Nginx 直接返回，`/api/*` 请求代理到 FastAPI。Steam 数据通过后台定时任务拉取缓存。

## 数据模型

### users
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| username | TEXT UNIQUE | |
| password_hash | TEXT | |
| created_at | DATETIME | |

### games
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| steam_app_id | INTEGER UNIQUE | Steam 应用 ID |
| name | TEXT | |
| description | TEXT | |
| image_url | TEXT | 封面图 |
| price | TEXT | |
| release_date | TEXT | |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### tags
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| name | TEXT UNIQUE | 标签名 |

### game_tags
| 字段 | 类型 | 说明 |
|------|------|------|
| game_id | FK → games.id | |
| tag_id | FK → tags.id | |

### ratings
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| user_id | FK → users.id | |
| game_id | FK → games.id | |
| score | INTEGER | 1-5 |
| created_at | DATETIME | |

### daily_top_sellers
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| game_id | FK → games.id | |
| rank | INTEGER | 排名 |
| date | DATE | |
| snapshot_time | DATETIME | |

### recommendation_history
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| user_id | FK → users.id | |
| game_id | FK → games.id | |
| recommended_at | DATETIME | |

## API 设计

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | /api/auth/register | 注册 | - |
| POST | /api/auth/login | 登录，设置 session cookie | - |
| POST | /api/auth/logout | 退出 | 需要 |
| GET | /api/games/top-sellers | 今日热销榜，分页 `?page=1&page_size=20`（默认每页 20，上限 100） | - |
| GET | /api/games/recommended | 推荐游戏，分页，参数同上 | 需要 |
| GET | /api/games/:id | 游戏详情 | - |
| POST | /api/ratings | 打分 `{game_id, score}` | 需要 |
| GET | /api/ratings/mine | 我的评分记录 | 需要 |
| GET | /api/tags | 标签列表 | - |

认证通过 session cookie，登录后服务端设置，后续请求自动携带。会话有效期 7 天。

## 推荐引擎

### 混合策略

```
推荐分 = 标签相似度分 × 0.6 + 协同过滤分 × 0.4 - 已推荐降权
```

### 标签相似度（内容推荐）

1. 对用户评过高分（score ≥ 4）的游戏，收集其所有标签
2. 用 Jaccard 相似度计算候选游戏与高分游戏的标签重合度
3. 公式：`|高分游戏标签 ∩ 候选游戏标签| / |高分游戏标签 ∪ 候选游戏标签|`

### 协同过滤

1. 计算用户间评分余弦相似度
2. 取 Top-10 相似用户的偏好游戏
3. 排除当前用户已评分的游戏

### 去重与降权

- `recommendation_history` 中已有记录，分数 × 0.5
- 用户已评分的游戏直接排除

### 冷启动

- 新用户（评分 < 5 个）：返回热销榜 Top 100 作为引导
- 评分 ≥ 5 个：启用推荐算法

## 前端页面

| 路由 | 页面 | 说明 |
|------|------|------|
| /login | 登录 | 用户名+密码 |
| /register | 注册 | 用户名+密码 |
| /hot | Steam 热销榜 | Top 100，游戏卡片列表，1-5 星打分，未登录可浏览 |
| /recommend | 游戏推荐 | 需登录，游戏卡片列表，1-5 星打分，刷新动态推荐 |

### 游戏卡片

展示：封面图、名称、标签、价格、1-5 星评分组件

### 导航栏

- 已登录：用户名、热销榜、推荐、退出
- 未登录：热销榜、登录/注册

## Steam 数据获取

1. **热销榜**：调用 Steam Store API `featuredcategories`，每天凌晨定时同步
2. **游戏详情**：调用 `appdetails`，新增游戏自动拉取；7 天内更新过的使用缓存
3. **容错**：API 故障时使用本地缓存，不影响核心功能

## 测试与部署

MVP 阶段跑通功能即可，不含自动化测试。部署方式为 Nginx + Uvicorn，单服务器。

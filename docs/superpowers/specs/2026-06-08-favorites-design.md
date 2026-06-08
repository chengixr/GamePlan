# 游戏收藏功能设计

## 概述

用户可以收藏游戏。收藏按钮出现在游戏卡片（右上角）和详情页。导航栏"推荐"右侧新增"收藏"菜单，显示用户收藏列表，按收藏时间倒序。

## 后端

### 数据库

新增 `favorites` 表：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK AUTOINCREMENT | |
| user_id | INTEGER FK → users.id NOT NULL | |
| game_id | INTEGER FK → games.id NOT NULL | |
| created_at | DateTime | 默认 UTC now |

联合唯一约束 `(user_id, game_id)`。

### API

新建 `backend/favorites.py`，注册路由前缀 `/api/favorites`。

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| POST | `/api/favorites/{game_id}` | 是 | 切换收藏。已收藏则删除返回 `{favorited: false}`，未收藏则新增返回 `{favorited: true}` |
| GET | `/api/favorites` | 是 | 获取收藏列表，参数 `page`, `page_size`。按 `created_at DESC` 排序。返回 `PaginatedResponse<GameResponse>` |

### 现有接口扩展

`GET /api/games/{game_id}` 和 `/api/games/top-sellers` 等返回的 `GameResponse` 中新增 `is_favorited: bool` 字段（仅已登录用户）。

## 前端

### 新组件

**`FavoriteButton.vue`**
- Props: `gameId`, `initialFavorited`
- 心形图标：实心红心 = 已收藏，空心 = 未收藏
- 点击调用 `POST /api/favorites/{gameId}` 切换
- 即时切换 UI（乐观更新），失败时回滚

### 新页面

**`FavoritesView.vue`**（路由 `/favorites`，需登录）
- 复用 `GameCard` 组件展示收藏列表
- 按收藏时间倒序
- 无限滚动分页
- 空状态提示："还没有收藏游戏，去热销榜看看吧"

### 修改

**`GameCard.vue`** — 卡片右上角添加 `FavoriteButton`，仅登录后显示

**`GameDetail.vue`** — 游戏标题旁添加 `FavoriteButton`

**`NavBar.vue`** — "推荐"右侧新增"收藏"菜单项，仅登录后显示

**`router/index.js`** — 新增 `/favorites` 路由

**`stores/games.js`** 或新增 `stores/favorites.js` — 管理收藏状态

**`api/index.js`** — 新增 `toggleFavorite(gameId)`, `getFavorites(page, pageSize)`

## 接口契约

```
POST /api/favorites/{game_id}
Response: { favorited: bool }

GET /api/favorites?page=1&page_size=20
Response: { items: GameResponse[], total: int, page: int, page_size: int }
其中 GameResponse.is_favorited = true
```

## 错误处理

- 未登录调用 → 401
- 游戏不存在 → 404
- 网络失败 → 前端回滚乐观更新，显示 toast

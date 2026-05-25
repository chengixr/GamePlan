# 游戏详情页 - 设计文档

> 日期：2026-05-25

## 概述

为每款游戏新增详情页，包含游戏信息、截图、Steam 评价、相似游戏推荐，支持评分。游戏卡片改为可点击，点击跳转详情页。

## 数据库变更

games 表新增字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| screenshots | TEXT | JSON 数组 `["url1","url2",...]`，截图 URL 列表 |
| review_summary | TEXT | JSON 对象 `{"positive": 85, "total": 1000}` |
| reviews_synced_at | DATETIME | 评价最后同步时间 |

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/games/:id | 游戏详情（含截图、评价、相似游戏） |

详情响应新增字段：
```json
{
  "screenshots": ["url1", "url2", ...],
  "review_positive": 1234,
  "review_total": 5678,
  "similar_games": [{ ... }, ...]  // Top 6 相似游戏
}
```

## Steam 同步

定时任务中新增评价和截图同步：
- 从 `appdetails` 提取 `screenshots` 字段（截图 URL 列表）
- 从 `appdetails` 提取 `recommendations.total` 和好评比例
- 缓存规则：已有数据且 `reviews_synced_at` 距现在 < 24 小时 → 跳过

## 详情页结构

### 上区：游戏信息
- 主图：第一张截图或 header 大图
- 缩略图列表：点击切换主图
- 右侧：游戏名（中/英）、标签、价格、发售日期、描述

### 中区：Steam 评价
- 好评率进度条 + 评测总数
- 从 Steam `appdetails` 预存数据

### 评分区
- 1-5 星评分组件（已登录用户可见）
- 显示当前用户已有评分

### 下区：相似游戏
- 6 款相似游戏卡片（标签 + 协同过滤混合）
- 点击可跳转对应详情页

### 导航
- 返回按钮（返回上一页）
- 页面标题为游戏名

## 前端变更

- `GameCard.vue` — 卡片外层包裹 `<router-link :to="/game/${game.id}">`，整卡可点击
- `GameDetail.vue` — 新建页面，路由 `/game/:id`
- `stores/games.js` — 新增 `currentGame` 状态，新增 `loadGameDetail(id)` action
- `api/index.js` — 新增 `gameDetail(id)` 方法
- `router/index.js` — 新增 `/game/:id` 路由

## 相似游戏算法

与主推荐引擎一致：
```
相似度 = 标签Jaccard × 0.6 + 协同过滤 × 0.4
```
取 Top 6，排除当前游戏和用户已评分游戏。

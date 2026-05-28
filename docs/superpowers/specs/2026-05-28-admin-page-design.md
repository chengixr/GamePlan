# 管理后台页面设计

**日期**: 2026-05-28
**状态**: 设计确认

## 概述

新增管理后台页面 `/admin`，提供用户管理、同步监控、日志查看三大功能。通过 `users.is_admin` 字段控制权限。

## 后端

### 数据库变更

`users` 表新增字段：
- `is_admin` (Boolean, default False) — 管理员标记
- `is_active` (Boolean, default True) — 启用/禁用

### 认证中间件

```python
def require_admin(current_user = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(403, "需要管理员权限")
    return current_user
```

### API 路由 (`backend/admin.py`)

所有接口依赖 `require_admin`。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/admin/users` | GET | 用户列表，`?search=&page=&page_size=` |
| `/api/admin/users/{id}/status` | PUT | `{is_active: bool}` 启用/禁用 |
| `/api/admin/users/{id}` | DELETE | 删除用户及评分 |
| `/api/admin/users/{id}/ratings` | GET | 用户评分记录 |
| `/api/admin/sync/status` | GET | 同步运行状态、上次/下次时间 |
| `/api/admin/sync/trigger` | POST | 手动触发同步 |
| `/api/admin/sync/stats` | GET | 最近同步统计 |
| `/api/admin/sync/game/{id}` | GET | 游戏同步时间、数据完整度 |
| `/api/admin/logs` | GET | `?date=&level=&lines=100` |

## 前端

### 路由

- `AdminView.vue`，路由 `/admin`
- `router.beforeEach` 检查 `is_admin`，非管理员返回首页
- `NavBar` 根据 `is_admin` 显示"管理"入口

### 页面结构

顶部三个 Tab：用户管理、同步监控、日志查看

### Tab 1 — 用户管理

- 搜索框 + 用户列表表格
- 列：用户名、昵称、评分数、注册时间、状态（启用/禁用）
- 操作：禁用/启用切换、删除（确认弹窗）、查看评分（弹窗）

### Tab 2 — 同步监控

- 状态卡片：是否运行中、上次完成时间、下次定时时间
- 统计卡片：各数据源最近数据量
- 手动同步按钮 + 结果提示
- 游戏查询：按 ID 搜索，显示同步时间、截图数、评价数等

### Tab 3 — 日志查看

- 日期选择器 + 级别过滤（ALL/INFO/WARNING/ERROR）
- 行数选择（50/100/200）
- 暗色等宽字体日志区域，自动滚动底部
- 自动刷新开关（5 秒间隔）

### 组件拆分

- `AdminView.vue` — 主容器 + Tab
- `AdminUsers.vue` — 用户管理
- `AdminSync.vue` — 同步监控
- `AdminLogs.vue` — 日志查看

### 样式

延续现有 Neon Arcade 主题，暗色背景 + 霓虹青强调色。

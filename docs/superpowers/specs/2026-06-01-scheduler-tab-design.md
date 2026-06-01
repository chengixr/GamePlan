# 管理后台 - 定时任务 Tab 页

## 概述

在管理后台新增"定时任务"tab，集中展示系统中所有 APScheduler 定时任务的名称、调度时间、执行情况，并支持手动触发。

## 后端

### API

**`GET /api/admin/scheduler/jobs`**

返回所有定时任务列表：

```json
{
  "jobs": [
    {
      "id": "sync_rankings",
      "name": "排名快照同步",
      "description": "每小时从 Steam 搜索页抓取热销前 100 名排名数据",
      "cron": "每小时第 13 分",
      "next_run": "2026-06-01T14:13:00Z",
      "last_run": "2026-06-01T13:13:05Z",
      "last_status": "success",
      "last_error": null
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 任务唯一标识，用于手动触发 |
| name | string | 中文名称 |
| description | string | 功能描述 |
| cron | string | cron 表达式的人类可读形式 |
| next_run | string \| null | 下次执行时间（ISO 8601），调度器未启动时为 null |
| last_run | string \| null | 最近一次执行时间，从未执行过为 null |
| last_status | string | success / failed / pending |
| last_error | string \| null | 失败时的错误信息，成功时为 null |

**`POST /api/admin/scheduler/jobs/{job_id}/trigger`**

手动触发指定任务。后台线程执行，立即返回 `{"ok": true}`。若任务正在执行中则返回 409。

### 执行状态记录

在 `steam_sync.py` 的 `start_scheduler()` 中注册 APScheduler 事件监听器：

- `EVENT_JOB_EXECUTED`：记录执行成功及时间
- `EVENT_JOB_ERROR`：记录执行失败、时间及异常信息

状态存储在模块级字典 `_job_status` 中，格式：

```python
_job_status = {
    "sync_rankings": {"last_run": datetime, "last_status": "success", "last_error": None},
    ...
}
```

### 任务定义

| id | name | description | cron |
|----|------|-------------|------|
| sync_rankings | 排名快照同步 | 每小时从 Steam 搜索页抓取热销前 100 名排名，缺失游戏自动拉取详情入库 | 每小时第 13 分 |
| sync_steam_data | 完整数据同步 | 多源同步（API+搜索+SteamCharts），更新游戏详情、截图、标签、评价 | 每天 00:17, 06:17, 12:17, 18:17 (UTC) |
| catchup_sync | 追补同步 | 补录当天缺失排名 + 补充数据不完整游戏的截图/描述/标签 | 每天 19:17 (UTC) |
| clean_old_logs | 日志清理 | 清理 30 天前的日志文件 | 每天 03:00 (UTC) |

## 前端

### AdminView 改动

- tabs 数组新增 `{ key: 'scheduler', label: '定时任务' }`
- 引入 `AdminScheduler.vue` 组件

### AdminScheduler.vue

表格组件，每行一个任务：

- 任务名称（加粗）
- 描述（灰色小字）
- cron 表达式（等宽字体）
- 下次执行时间（格式化为本地时间）
- 最近执行状态：绿色圆点 + "成功" / 红色圆点 + "失败" / 灰色圆点 + "未执行"
- 失败时悬浮显示错误信息（tooltip）
- "立即执行"按钮：点击后发送 POST，按钮变灰显示"执行中"，完成后刷新列表

页面加载时调用 `GET /api/admin/scheduler/jobs` 获取数据。手动触发后自动刷新。

## 验证方式

1. 访问管理后台，确认"定时任务"tab 存在
2. 确认 4 个任务均显示，名称/描述/cron/下次执行时间正确
3. 等待某个 cron 任务自动执行后，刷新页面确认状态更新
4. 点击"立即执行"，确认任务被触发且状态刷新

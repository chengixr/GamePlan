# 图片存储与性能优化设计方案

## 日期

2026-06-08

## 背景

Steam 同步下载的头图和截图以原始分辨率本地存储，导致存储占用 3.5GB，同时全尺寸图片在缩略展示场景中浪费带宽，影响页面加载性能。

### 当前现状

| 类型 | 数量 | 平均大小 | 总占用 |
|------|------|----------|--------|
| 游戏头图 | 1,394 | ~44 KB | ~60 MB |
| 游戏截图 | 8,178 | ~439 KB | ~3.5 GB |
| 数据库 | - | - | 10 MB |

### 核心问题

1. **截图存储占比过高**（3.5GB / 3.6GB ≈ 97%），每款游戏最多 10 张全分辨率截图
2. **原图分辨率远超展示需求**：头图卡片实际渲染 200×113px，却加载 460×215px 原图；缩略图 108×60px，却加载 1920×1080px
3. **同步耗时长**：全量下载截图导致单次同步请求量大，Steam 限流风险高

## 目标

- 存储占用从 ~3.5GB 降至 ~350MB（减少 90%）
- 页面加载图片体积显著缩小，提升首屏渲染速度
- 兼容不支持 WebP 的旧设备
- 不改变现有功能逻辑

## 方案概览

中等改动方案：在现有架构上新增图片处理管线，同步时限制截图数量并压缩转换，前端按尺寸加载。

## 详细设计

### 1. 图片处理管线 — `backend/image_processor.py`

新模块，职责单一：接收原图 → 缩放 → 输出多尺寸多格式。

**尺寸规格**:

| 用途 | 宽度 | 说明 |
|------|------|------|
| 头图 small | 400px | 游戏卡片（渲染 200px，2x retina） |
| 头图 large | 920px | 详情页主图 |
| 截图 thumb | 216px | 缩略图（渲染 108px，2x retina） |
| 截图 large | 1200px | 详情页大图 |

**格式**: 每种尺寸同时输出 WebP (quality=80) 和 JPEG (quality=82)。

**目录结构**:
```
static/images/headers/{appid}_400.webp
static/images/headers/{appid}_400.jpg
static/images/headers/{appid}_920.webp
static/images/headers/{appid}_920.jpg
static/images/screenshots/{appid}_{idx}_216.webp
static/images/screenshots/{appid}_{idx}_216.jpg
static/images/screenshots/{appid}_{idx}_1200.webp
static/images/screenshots/{appid}_{idx}_1200.jpg
```

**核心函数**:

```python
def process_header(appid: int, source_path: str) -> dict:
    """处理头图，返回 {small, large} 各格式路径"""

def process_screenshot(appid: int, idx: int, source_path: str) -> dict:
    """处理截图，返回 {thumb, large} 各格式路径"""

def get_image_urls(appid: int, request_headers: dict, screenshot_count: int = 3) -> dict:
    """根据 Accept 头返回最优格式的 URL 集合"""
```

**WebP 检测**: 解析请求 `Accept` 头是否包含 `image/webp`，支持则返回 `.webp`，否则 `.jpg`。本地文件不存在时回退 Steam CDN。

**依赖**: Pillow（已有或新增至 requirements.txt）。

### 2. 同步策略调整 — `backend/steam_sync.py`

**截图下载限制**: 同步时只下载前 3 张截图（覆盖首页预览需求），下载后立即调用 `image_processor` 压缩转换。其余截图不下载。

**头图处理**: 下载后立即生成 small + large 两个尺寸，再删除原图。

**变更点**:
- `_download_image()` → 下载后调用 `process_header()`
- `_download_screenshots()` → 限制 3 张，下载后调用 `process_screenshot()`
- 数据库 `image_url` 存储 `header_small` WebP 路径（默认格式）
- 数据库 `screenshots` 存储 `[{"thumb": "...", "large": "..."}]` 结构

### 3. API 响应调整 — `backend/games.py` + `backend/models.py`

**`GameResponse` 新增字段**:

```python
class GameResponse(BaseModel):
    id: int
    steam_app_id: int
    name: str
    name_cn: str = ""
    description: str
    image_url: str          # header_small（保留兼容）
    image_large: str = ""   # 新增，详情页大图
    fallback_image: str = ""  # Steam CDN 回退 URL
    price: str
    tags: list[str] = []
```

**`screenshots` 结构变更**: 从 `list[str]` 改为 `list[dict]`，每项包含 `{"thumb": str, "large": str}`。

详情接口 `/api/games/{game_id}` 同步适配。

**格式选择**: API 层读取请求 `Accept` 头，调用 `get_image_urls()` 返回对应格式路径。

### 4. 前端适配

**GameCard** (`components/GameCard.vue`):
- 使用 `image_url`（header_small，400w）
- 回退链保留：本地 small → `fallback_image`（Steam CDN）→ 占位 SVG

**GameDetail** (`views/GameDetail.vue`):
- 主图：使用 `screenshots[idx].large`（1200w）
- 缩略图：使用 `screenshots[idx].thumb`（216w）
- 相似游戏卡片：使用 `image_url`

**其他视图** (`HotView`, `RecommendView`, `FavoritesView`):
- 均使用 `image_url`（header_small），无需修改卡片渲染逻辑

### 5. 历史数据迁移 — `backend/migrate_images.py`

一次性脚本，处理已有 3.5GB 图片：

```bash
cd backend && python migrate_images.py           # 完整迁移
cd backend && python migrate_images.py --dry-run # 预览（不写文件）
```

**流程**:
1. 遍历 `static/images/*.jpg`（头图源文件）
2. 遍历 `static/images/screenshots/*.jpg`（截图源文件）
3. 调用 `image_processor` 生成多尺寸多格式
4. 批量更新数据库 `games.image_url` 和 `games.screenshots`
5. 记录迁移结果（成功/失败/跳过）

**清理策略**: 旧文件默认不立即删除，迁移完成后人工确认再清理。数据库字段仍指向旧路径的游戏保持原样（不会被破坏）。

## 存储预期

| 项目 | 优化前 | 优化后 | 说明 |
|------|--------|--------|------|
| 头图 | 60 MB | ~15 MB | 2 尺寸 × WebP，原图删除 |
| 截图 | 3,500 MB | ~300 MB | 3 张 × 2 尺寸 × WebP × ~800 游戏 |
| 数据库 | 10 MB | ~10 MB | 路径字符串略长，可忽略 |
| **合计** | **~3,570 MB** | **~325 MB** | **减少 91%** |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| Pillow 处理大图时内存占用 | 逐张处理，处理完释放 |
| WebP 兼容性（iOS 14-） | 双格式存储 + API 层 Accept 检测 |
| 同步耗时因压缩而增加 | 头图/截图均小尺寸，Pillow 缩放快速 |
| 迁移脚本长时间运行 | 支持断点续传思路（检查目标文件存在则跳过）|
| 迁移后旧路径失效 | 数据库更新在同一事务中，失败回滚 |

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/image_processor.py` | 新建 | 图片处理管线 |
| `backend/migrate_images.py` | 新建 | 历史数据迁移 |
| `backend/steam_sync.py` | 修改 | 限制截图数量 + 调用管线 |
| `backend/games.py` | 修改 | API 返回多尺寸字段 |
| `backend/models.py` | 修改 | GameResponse 新增字段 |
| `frontend/src/components/GameCard.vue` | 修改 | 使用 small 尺寸 |
| `frontend/src/views/GameDetail.vue` | 修改 | 截图分尺寸加载 |
| `frontend/src/views/HotView.vue` | 修改 | 适配新字段（如需要） |
| `frontend/src/views/RecommendView.vue` | 修改 | 适配新字段（如需要） |
| `frontend/src/views/FavoritesView.vue` | 修改 | 适配新字段（如需要） |
| `backend/requirements.txt` | 修改 | 新增 Pillow 依赖 |

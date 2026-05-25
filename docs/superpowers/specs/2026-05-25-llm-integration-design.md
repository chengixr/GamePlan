# LLM 集成（DeepSeek） - 设计文档

> 日期：2026-05-25

## 概述

接入 DeepSeek 大模型实现三个功能：标签提取、中文名生成、Embedding 推荐引擎。所有 LLM 功能均带降级方案。

## 配置

`config/config.json` 新增 LLM 配置块，环境变量可覆盖：

```json
{
  "llm": {
    "api_base": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
    "embedding_model": "deepseek-embed",
    "enabled": true
  }
}
```

- 环境变量 `DEEPSEEK_API_KEY` 可覆盖 `api_key`
- `enabled: false` 时关闭所有 LLM 功能，直接用降级方案

## 后端新增文件

### `backend/llm.py`

LLM 客户端封装，提供三个方法：

| 方法 | 用途 | 降级返回值 |
|------|------|-----------|
| `extract_tags(description: str) -> list[str]` | 从描述文本提取 5-10 个中文标签 | `[]` |
| `generate_chinese_name(en_name, description) -> str` | 生成中文游戏名 | `""` |
| `get_embedding(text: str) -> list[float]` | 获取文本 embedding 向量 | `[]` |
| `batch_embeddings(texts: list[str]) -> list[list[float]]` | 批量获取 embedding | `[]` |

降级判断：API 超时/报错/未配置 key → 返回降级值。

### 数据库新增表

```sql
CREATE TABLE game_embeddings (
  game_id INTEGER PRIMARY KEY REFERENCES games(id),
  embedding TEXT NOT NULL,  -- JSON 数组 [0.123, -0.456, ...]
  updated_at DATETIME
);
```

## 功能 1：标签提取

**流程：**
1. 同步 `_try_fetch_details` 获取 `detailed_description`
2. 调用 `llm.extract_tags(description)` 获取中文标签
3. 与 Steam API 标签合并去重，翻译后存入 `game_tag_assoc`
4. 降级：LLM 不可用时仅用 Steam API 标签 + tag_translations 翻译

## 功能 2：中文名生成

**流程：**
1. 同步时若 `name_cn` 为空
2. 调用 `llm.generate_chinese_name(en_name, description)`
3. 存入 `name_cn` 字段
4. 降级：Steam `appdetails?cc=cn` 官方中文名

## 功能 3：Embedding 推荐引擎

### 预计算

- 新增 `POST /api/llm/build-embeddings` 接口，为无 embedding 的游戏批量计算
- 使用游戏描述文本（取前 2000 字符）调用 embedding API
- 存储到 `game_embeddings` 表

### 推荐算法更新

新增 `recommender.py` 的 embedding 分支：

```
embedding相似度 = cosine(用户画像向量, 候选游戏向量)

用户画像向量 = Σ(高分游戏向量 × 评分) / Σ评分

最终分 = embedding相似度 × 0.6 + 协同过滤 × 0.4 - 不喜欢惩罚
```

- 用户评分 ≥5 且 embedding 覆盖率 >50% → 启用 embedding 模式
- 否则 → 自动降级为标签 Jaccard 模式

### API

`GET /api/games/recommended` — 响应不变，底层自动切换算法。

## 降级矩阵

| 场景 | 标签提取 | 中文名 | 推荐引擎 |
|------|----------|--------|----------|
| API Key 未配置 | tag_translations | Steam cc=cn | 标签 Jaccard |
| API 超时 | tag_translations | Steam cc=cn | 标签 Jaccard |
| embedding 覆盖率 <50% | — | — | 标签 Jaccard |
| LLM 启用且正常 | LLM 标签 | LLM 中文名 | Embedding 相似度 |

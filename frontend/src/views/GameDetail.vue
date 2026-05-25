<template>
  <div class="detail" v-if="game">
    <button class="btn-back" @click="$router.back()">&#8592; 返回</button>

    <!-- 模块1: 游戏名称 + 标签 + 价格 + 评分 -->
    <div class="module module-header">
      <h1 class="game-name">
        <span class="name-en">{{ game.name }}</span>
        <span class="name-cn" v-if="game.name_cn && game.name_cn !== game.name">{{ game.name_cn }}</span>
      </h1>
      <div class="header-row">
        <div class="tags"><span v-for="t in game.tags" :key="t" class="tag">{{ t }}</span></div>
        <div class="meta">
          <span class="price">{{ game.price }}</span>
          <span class="date" v-if="game.release_date">{{ game.release_date }}</span>
        </div>
        <StarRating v-model="rating" @update:model-value="onRate" />
      </div>
    </div>

    <!-- 模块2: 截图画廊 -->
    <div class="module module-gallery" v-if="screenshots.length > 0">
      <img :src="currentImg" class="main-img" />
      <div class="thumbs">
        <img v-for="(s, i) in screenshots.slice(0, 8)" :key="i"
          :src="s" class="thumb" :class="{ active: i === activeIdx }"
          @click="activeIdx = i" />
      </div>
    </div>

    <!-- 模块3: 游戏描述 -->
    <div class="module module-desc" v-if="game.description">
      <h2 class="module-title">关于此游戏</h2>
      <div class="desc" v-html="game.description"></div>
    </div>

    <!-- 模块4: Steam 评价 -->
    <div class="module module-reviews" v-if="game.review_total > 0">
      <h2 class="module-title">Steam 评价</h2>
      <div class="review-bar-wrap">
        <div class="review-bar"><div class="review-fill" :style="{ width: reviewPct + '%' }"></div></div>
        <span class="review-text">{{ reviewPct }}% 好评 ({{ game.review_total }} 条评测)</span>
      </div>
    </div>

    <!-- 模块5: 相似游戏 -->
    <div class="module module-similar" v-if="game.similar_games?.length">
      <h2 class="module-title">相似游戏</h2>
      <div class="similar-grid">
        <router-link v-for="sg in game.similar_games" :key="sg.id"
          :to="'/game/' + sg.id" class="similar-card">
          <img :src="sg.image_url" :alt="sg.name" />
          <span class="similar-name">{{ sg.name }}</span>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import StarRating from '../components/StarRating.vue'
import { useGamesStore } from '../stores/games'

const route = useRoute()
const store = useGamesStore()

const game = computed(() => store.currentGame)
const activeIdx = ref(0)
const screenshots = computed(() => game.value?.screenshots || [])
const currentImg = computed(() => screenshots.value[activeIdx.value] || game.value?.image_url || '')
const rating = ref(0)

const reviewPct = computed(() => {
  if (!game.value?.review_total) return 0
  return Math.round(game.value.review_positive / game.value.review_total * 100)
})

async function onRate(score) {
  if (game.value) {
    await store.rate(game.value.id, score)
    rating.value = score
  }
}

onMounted(async () => {
  const id = route.params.id
  await store.loadMyRatings()
  await store.loadGameDetail(id)
  rating.value = store.myRatings[parseInt(id)] || 0
})
</script>

<style scoped>
.detail { max-width: 800px; margin: 0 auto; padding: 24px; }

.btn-back {
  background: var(--surface-raised); border: 1px solid rgba(255,255,255,0.08);
  color: var(--text-secondary); padding: 8px 16px; border-radius: 6px;
  cursor: pointer; font-size: 14px; margin-bottom: 24px;
  transition: color 0.2s;
}
.btn-back:hover { color: var(--neon-cyan); }

/* 模块通用 */
.module {
  padding: 28px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.module:last-child { border-bottom: none; }
.module-title {
  font-family: var(--font-display); font-size: 16px; font-weight: 600;
  letter-spacing: 2px; margin-bottom: 16px; color: var(--text-primary);
}

/* 模块1: 游戏名 + 标签 + 评分 */
.game-name { margin-bottom: 12px; }
.name-en { display: block; font-size: 26px; font-weight: 700; }
.name-cn { display: block; font-size: 16px; color: var(--text-secondary); margin-top: 4px; }
.header-row { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; }
.tags { display: flex; flex-wrap: wrap; gap: 5px; }
.tag { padding: 3px 10px; background: var(--surface-raised); border-radius: 3px; font-size: 12px; color: var(--text-secondary); }
.meta { display: flex; gap: 12px; align-items: center; }
.price { font-size: 18px; color: var(--neon-amber); font-weight: 600; }
.date { font-size: 14px; color: var(--text-muted); }

/* 模块2: 截图 */
.main-img { width: 100%; aspect-ratio: 16/9; object-fit: cover; border-radius: 8px; background: var(--surface-raised); }
.thumbs { display: flex; gap: 6px; margin-top: 10px; overflow-x: auto; padding-bottom: 4px; }
.thumb { width: 100px; height: 56px; object-fit: cover; border-radius: 4px; cursor: pointer; opacity: 0.5; transition: opacity 0.15s; border: 2px solid transparent; flex-shrink: 0; }
.thumb:hover, .thumb.active { opacity: 1; border-color: var(--neon-cyan); }

/* 模块3: 描述 */
.desc { font-size: 15px; color: var(--text-secondary); line-height: 1.8; }
.desc :deep(h2) { font-size: 16px; color: var(--text-primary); margin: 20px 0 10px; }
.desc :deep(h1) { font-size: 18px; color: var(--text-primary); margin: 20px 0 10px; }
.desc :deep(strong) { color: var(--text-primary); }
.desc :deep(.bb_img) { max-width: 100%; border-radius: 6px; margin: 10px 0; display: block; }
.desc :deep(img) { max-width: 100%; border-radius: 6px; margin: 10px 0; }
.desc :deep(ul), .desc :deep(.bb_ul) { padding-left: 20px; margin: 8px 0; }
.desc :deep(li) { margin: 4px 0; }

/* 模块4: 评价 */
.review-bar-wrap { display: flex; align-items: center; gap: 14px; }
.review-bar { flex: 1; height: 10px; background: var(--surface-raised); border-radius: 5px; overflow: hidden; }
.review-fill { height: 100%; background: var(--neon-cyan); border-radius: 5px; transition: width 0.4s; }
.review-text { font-size: 14px; color: var(--text-secondary); white-space: nowrap; }

/* 模块5: 相似游戏 */
.similar-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
.similar-card { text-decoration: none; color: inherit; background: var(--surface-raised); border-radius: 8px; overflow: hidden; transition: transform 0.2s; border: 1px solid rgba(255,255,255,0.04); }
.similar-card:hover { transform: translateY(-2px); border-color: var(--border-glow); }
.similar-card img { width: 100%; aspect-ratio: 16/9; object-fit: cover; }
.similar-name { display: block; padding: 8px; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

@media (max-width: 640px) {
  .detail { padding: 16px; }
  .header-row { flex-direction: column; align-items: flex-start; }
  .similar-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>

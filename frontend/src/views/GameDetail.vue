<template>
  <div class="detail" v-if="game">
    <button class="btn-back" @click="$router.back()">&#8592; 返回</button>

    <!-- 模块1: 顶栏 - 游戏名 + 标签 + 价格 + 评价摘要 + 评分 -->
    <div class="hero-module">
      <div class="hero-bg" v-if="currentImg" :style="{ backgroundImage: 'url(' + currentImg + ')' }"></div>
      <div class="hero-content">
        <div class="hero-left">
          <h1 class="hero-title">
            <span class="hero-name">{{ game.name }}</span>
            <span class="hero-name-cn" v-if="game.name_cn && game.name_cn !== game.name">{{ game.name_cn }}</span>
          </h1>
          <div class="hero-tags"><span v-for="t in game.tags" :key="t" class="hero-tag">{{ t }}</span></div>
          <div class="hero-meta">
            <span class="hero-price">{{ game.price }}</span>
            <span class="hero-date" v-if="game.release_date">&#8226; {{ game.release_date }}</span>
          </div>
          <div class="hero-rating">
            <StarRating v-model="rating" @update:model-value="onRate" />
          </div>
        </div>
        <div class="hero-right" v-if="game.review_total > 0">
          <div class="review-badge">
            <span class="badge-pct">{{ reviewPct }}%</span>
            <span class="badge-label">好评率</span>
            <span class="badge-total">{{ game.review_total }} 条评测</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 模块2: 截图画廊 -->
    <div class="section" v-if="screenshots.length > 0">
      <h2 class="section-title"><span class="title-bar"></span> 游戏截图</h2>
      <img :src="currentImg" class="main-img" />
      <div class="thumbs">
        <img v-for="(s, i) in screenshots.slice(0, 8)" :key="i"
          :src="s" class="thumb" :class="{ active: i === activeIdx }"
          @click="activeIdx = i" />
      </div>
    </div>

    <!-- 模块3: 游戏描述 -->
    <div class="section" v-if="game.description">
      <h2 class="section-title"><span class="title-bar"></span> 关于此游戏</h2>
      <div class="desc" v-html="game.description"></div>
    </div>

    <!-- 模块4: Steam 评价 -->
    <div class="section" v-if="game.review_total > 0">
      <h2 class="section-title"><span class="title-bar"></span> Steam 评价概览</h2>
      <div class="review-summary">
        <div class="review-bar-large">
          <div class="review-fill-large" :style="{ width: reviewPct + '%' }"></div>
        </div>
        <div class="review-stats">
          <span class="stat-positive">{{ game.review_positive }} 好评</span>
          <span class="stat-negative">{{ game.review_total - game.review_positive }} 差评</span>
        </div>
      </div>
    </div>

    <!-- 模块5: 用户评价 -->
    <div class="section" v-if="game.user_reviews?.length">
      <h2 class="section-title"><span class="title-bar"></span> 玩家评测</h2>
      <div class="review-columns">
        <div v-for="(rv, i) in game.user_reviews" :key="i" class="review-card">
          <div class="review-card-head">
            <span class="review-vote">{{ rv.voted_up ? '👍' : '👎' }}</span>
            <span class="review-playtime" v-if="rv.playtime">{{ (rv.playtime / 60).toFixed(1) }}h</span>
          </div>
          <p class="review-card-text">{{ rv.text }}</p>
        </div>
      </div>
    </div>

    <!-- 模块6: 相似游戏 -->
    <div class="section" v-if="game.similar_games?.length">
      <h2 class="section-title"><span class="title-bar"></span> 相似游戏</h2>
      <div class="similar-grid">
        <div v-for="sg in game.similar_games" :key="sg.id"
          class="similar-card" @click="router.push('/game/' + sg.id)">
          <div class="similar-img-wrap">
            <img
              v-if="!simImgFailed[sg.id]"
              :src="sg.image_url"
              :alt="sg.name"
              class="similar-img"
              @error="() => simImgFailed[sg.id] = true"
            />
            <div class="similar-placeholder" v-else>
              <svg viewBox="0 0 64 48" fill="none"><rect x="4" y="16" width="56" height="22" rx="6" stroke="currentColor" stroke-width="2"/><circle cx="48" cy="26" r="3" stroke="currentColor" stroke-width="1.5"/><circle cx="34" cy="24" r="1" fill="currentColor" opacity="0.4"/><circle cx="30" cy="30" r="1" fill="currentColor" opacity="0.4"/></svg>
            </div>
          </div>
          <span class="similar-name">{{ sg.name_cn || sg.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StarRating from '../components/StarRating.vue'
import { useGamesStore } from '../stores/games'

const route = useRoute()
const router = useRouter()
const store = useGamesStore()

const game = computed(() => store.currentGame)
const activeIdx = ref(0)
const screenshots = computed(() => game.value?.screenshots || [])
const currentImg = computed(() => screenshots.value[activeIdx.value] || game.value?.image_url || '')
const rating = ref(0)
const simImgFailed = reactive({})

// 路由变化时立即清空旧数据，避免闪现上一款游戏
watch(() => route.params.id, () => {
  store.currentGame = null
})

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
.detail { max-width: 900px; margin: 0 auto; padding: 24px; }

.btn-back {
  background: var(--surface-raised); border: 1px solid rgba(255,255,255,0.08);
  color: var(--text-secondary); padding: 8px 18px; border-radius: 6px;
  cursor: pointer; font-size: 14px; margin-bottom: 28px;
  transition: all 0.2s;
}
.btn-back:hover { color: var(--neon-cyan); border-color: rgba(0,229,255,0.2); }

/* 模块通用 */
.section {
  padding: 32px 0;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.section:last-child { border-bottom: none; }
.section-title {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--font-display); font-size: 19px; font-weight: 600;
  letter-spacing: 3px; margin-bottom: 20px; color: var(--text-primary);
}
.title-bar {
  display: inline-block; width: 4px; height: 22px;
  background: var(--neon-cyan); border-radius: 2px;
  box-shadow: 0 0 8px rgba(0,229,255,0.3);
}

/* 模块1: 顶栏 Hero */
.hero-module {
  position: relative; border-radius: 12px; overflow: hidden;
  margin-bottom: 8px; min-height: 240px;
}
.hero-bg {
  position: absolute; inset: 0; background-size: cover; background-position: center;
  filter: blur(20px) brightness(0.25);
  transform: scale(1.1);
}
.hero-content {
  position: relative; z-index: 1;
  display: flex; gap: 32px; padding: 36px 40px;
  background: linear-gradient(135deg, rgba(13,13,26,0.85) 0%, rgba(13,13,26,0.6) 100%);
  backdrop-filter: blur(4px);
}
.hero-left { flex: 1; }
.hero-title { margin-bottom: 14px; }
.hero-name { display: block; font-size: 28px; font-weight: 800; line-height: 1.2; }
.hero-name-cn { display: block; font-size: 17px; color: var(--text-secondary); margin-top: 4px; }
.hero-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
.hero-tag {
  padding: 4px 12px; font-size: 12px; font-weight: 500;
  background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 4px; color: var(--text-secondary);
}
.hero-meta { display: flex; gap: 14px; align-items: center; margin-bottom: 16px; }
.hero-price { font-size: 24px; color: var(--neon-amber); font-weight: 700; }
.hero-date { font-size: 14px; color: var(--text-muted); }

.hero-right { flex-shrink: 0; display: flex; align-items: center; }
.review-badge {
  text-align: center; padding: 20px 28px;
  background: rgba(0,229,255,0.06); border: 1px solid rgba(0,229,255,0.15);
  border-radius: 12px;
}
.badge-pct { display: block; font-family: var(--font-display); font-size: 36px; font-weight: 700; color: var(--neon-cyan); line-height: 1; }
.badge-label { display: block; font-size: 13px; color: var(--text-secondary); margin: 6px 0 2px; }
.badge-total { display: block; font-size: 11px; color: var(--text-muted); }

/* 模块2: 截图 */
.main-img { width: 100%; border-radius: 8px; background: var(--surface-raised); object-fit: cover; aspect-ratio: 16/9; }
.thumbs { display: flex; gap: 8px; margin-top: 12px; overflow-x: auto; padding-bottom: 4px; }
.thumb { width: 108px; height: 60px; object-fit: cover; border-radius: 5px; cursor: pointer; opacity: 0.45; transition: all 0.15s; border: 2px solid transparent; flex-shrink: 0; }
.thumb:hover, .thumb.active { opacity: 1; border-color: var(--neon-cyan); }

/* 模块3: 描述 */
.desc { font-size: 15px; color: var(--text-secondary); line-height: 1.9; }
.desc :deep(h2), .desc :deep(h1) { font-size: 18px; color: var(--text-primary); margin: 24px 0 12px; }
.desc :deep(strong) { color: var(--text-primary); }
.desc :deep(img) { max-width: 100%; border-radius: 8px; margin: 12px 0; display: block; }
.desc :deep(ul), .desc :deep(.bb_ul) { padding-left: 22px; margin: 10px 0; }
.desc :deep(li) { margin: 5px 0; }

/* 模块4: 评价概览 */
.review-summary { max-width: 480px; }
.review-bar-large { height: 14px; background: rgba(255,45,120,0.15); border-radius: 7px; overflow: hidden; margin-bottom: 10px; }
.review-fill-large { height: 100%; background: linear-gradient(90deg, var(--neon-cyan), #10b981); border-radius: 7px; transition: width 0.5s ease; }
.review-stats { display: flex; justify-content: space-between; font-size: 14px; }
.stat-positive { color: #10b981; }
.stat-negative { color: var(--neon-magenta); }

/* 模块5: 用户评价 */
.review-columns {
  column-count: 3; column-gap: 14px;
}
.review-card {
  break-inside: avoid;
  background: var(--surface); border: 1px solid rgba(255,255,255,0.05);
  border-radius: 10px; padding: 18px; margin-bottom: 14px;
  transition: border-color 0.2s;
}
.review-card:hover { border-color: rgba(255,255,255,0.1); }
.review-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.review-vote { font-size: 16px; }
.review-playtime { font-size: 11px; color: var(--text-muted); }
.review-card-text {
  font-size: 13px; color: var(--text-secondary); line-height: 1.7;
}

/* 模块6: 相似游戏 */
.similar-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 14px; }
.similar-card { text-decoration: none; color: inherit; background: var(--surface); border-radius: 10px; overflow: hidden; transition: transform 0.2s, border-color 0.2s; border: 1px solid rgba(255,255,255,0.04); cursor: pointer; }
.similar-card:hover { transform: translateY(-3px); border-color: var(--border-glow); }
.similar-img-wrap { width: 100%; aspect-ratio: 16/9; background: var(--surface-raised); overflow: hidden; }
.similar-img { width: 100%; height: 100%; object-fit: cover; }
.similar-placeholder {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--surface-raised), rgba(0,229,255,0.04));
  color: var(--text-muted); opacity: 0.4;
}
.similar-placeholder svg { width: 36px; height: 27px; }
.similar-name { display: block; padding: 10px 12px; font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

@media (max-width: 768px) {
  .hero-content { flex-direction: column; padding: 28px 24px; }
  .hero-right { justify-content: center; }
  .review-columns { column-count: 2; }
  .similar-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 480px) {
  .detail { padding: 12px; }
  .review-columns { column-count: 1; }
  .similar-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>

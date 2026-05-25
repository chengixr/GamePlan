<template>
  <router-link :to="'/game/' + game.id" class="game-card">
    <div class="card-glow"></div>
    <div class="card-image-wrap">
      <!-- 占位图标（始终显示，作为背景） -->
      <div class="card-placeholder">
        <svg class="placeholder-icon" viewBox="0 0 64 48" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="4" y="16" width="56" height="22" rx="6" stroke="currentColor" stroke-width="2.5" />
          <path d="M12 38 L8 46 Q12 48 16 46 Z" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round" />
          <path d="M20 38 L14 46 Q20 48 24 46 Z" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round" />
          <path d="M52 38 L56 46 Q52 48 48 46 Z" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round" />
          <path d="M44 38 L50 46 Q44 48 40 46 Z" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round" />
          <rect x="12" y="20" width="4" height="12" rx="1" fill="currentColor" opacity="0.5" />
          <rect x="8" y="24" width="12" height="4" rx="1" fill="currentColor" opacity="0.5" />
          <circle cx="48" cy="26" r="4" stroke="currentColor" stroke-width="2" />
          <circle cx="34" cy="24" r="1.5" fill="currentColor" opacity="0.4" />
          <circle cx="30" cy="30" r="1.5" fill="currentColor" opacity="0.4" />
          <rect x="6" y="12" width="6" height="6" rx="2" stroke="currentColor" stroke-width="2" />
          <rect x="52" y="12" width="6" height="6" rx="2" stroke="currentColor" stroke-width="2" />
        </svg>
      </div>
      <!-- 图片加载成功后覆盖占位符 -->
      <img
        :src="imgSrc"
        :alt="game.name"
        class="card-image"
        :class="{ loaded: imgLoaded }"
        loading="lazy"
        @load="onImgLoad"
        @error="onImgError"
      />
      <div class="card-rank" v-if="rank">{{ rank }}</div>
      <div class="price-badge">{{ game.price }}</div>
    </div>
    <div class="card-body">
      <div class="card-title">
        <span class="title-en">{{ game.name }}</span>
        <span class="title-cn" v-if="game.name_cn && game.name_cn !== game.name">{{ game.name_cn }}</span>
      </div>
      <div class="tags">
        <span v-for="tag in game.tags.slice(0, 5)" :key="tag" class="tag">{{ tag }}</span>
      </div>
      <div class="card-footer">
        <StarRating v-model="rating" @update:model-value="onRate" />
        <span class="rating-hint" v-if="!rating">评分</span>
      </div>
    </div>
  </router-link>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import StarRating from './StarRating.vue'
import { useGamesStore } from '../stores/games'

const props = defineProps({ game: Object, rank: Number })
const store = useGamesStore()
const rating = ref(store.myRatings[props.game.id] || 0)
const imgLoaded = ref(false)     // 图片加载成功 → 显示
const imgRetry = ref(0)          // 重试次数

const imgSrc = computed(() => {
  const appid = props.game.steam_app_id
  // 第 0 次：用 image_url；第 1 次：用 CDN fallback
  if (imgRetry.value === 0) {
    const url = props.game.image_url || ''
    if (url) return url
  }
  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${appid}/header.jpg`
})

function onImgLoad() {
  imgLoaded.value = true
}

function onImgError() {
  if (imgRetry.value === 0) {
    imgRetry.value = 1  // 切到 CDN 重试
  }
  // CDN 也失败 → 保持占位符
}

watch(() => store.myRatings[props.game.id], (val) => {
  if (val !== undefined) rating.value = val
})

function onRate(score) {
  store.rate(props.game.id, score)
}
</script>

<style scoped>
.game-card {
  position: relative;
  display: flex;
  text-decoration: none;
  color: inherit;
  gap: 20px;
  background: var(--surface);
  border: 1px solid rgba(255,255,255,0.04);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 10px;
  overflow: hidden;
  transition: border-color 0.3s, box-shadow 0.3s, transform 0.3s;
}
.game-card:hover {
  border-color: var(--border-glow);
  box-shadow: 0 0 24px rgba(0, 229, 255, 0.06), inset 0 1px 0 rgba(255,255,255,0.02);
  transform: translateY(-2px);
}
.card-glow {
  position: absolute;
  top: -40%; left: -20%;
  width: 60%;
  height: 180%;
  background: radial-gradient(ellipse, rgba(0, 229, 255, 0.03) 0%, transparent 70%);
  pointer-events: none;
  transition: opacity 0.3s;
  opacity: 0;
}
.game-card:hover .card-glow { opacity: 1; }

.card-image-wrap {
  position: relative;
  flex-shrink: 0;
  width: 200px;
  height: 113px;
  border-radius: 6px;
  overflow: hidden;
  background: linear-gradient(135deg, var(--surface-raised) 0%, rgba(0,229,255,0.04) 50%, var(--surface-raised) 100%);
}
.card-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 0.35s ease, transform 0.4s;
}
.card-image.loaded {
  opacity: 1;
}
.game-card:hover .card-image.loaded { transform: scale(1.04); }

.card-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.placeholder-icon {
  width: 44px;
  height: 33px;
  color: var(--neon-cyan);
  opacity: 0.25;
  transition: opacity 0.3s;
}
.game-card:hover .placeholder-icon {
  opacity: 0.45;
}

.card-rank {
  position: absolute;
  top: 6px; left: 6px;
  width: 26px; height: 26px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(6,6,11,0.85);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 4px;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--neon-cyan);
  backdrop-filter: blur(4px);
}
.price-badge {
  position: absolute;
  bottom: 6px; right: 6px;
  padding: 2px 8px;
  background: rgba(6,6,11,0.85);
  border-radius: 3px;
  font-size: 13px;
  font-weight: 600;
  color: var(--neon-amber);
  backdrop-filter: blur(4px);
}

.card-body { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.card-title { margin-bottom: 8px; line-height: 1.4; }
.title-en {
  display: block;
  font-size: 15px; font-weight: 600; color: var(--text-primary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.title-cn {
  display: block;
  font-size: 13px; font-weight: 400; color: var(--text-secondary);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-top: 1px;
}
.tags { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px; }
.tag {
  padding: 3px 10px;
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 3px;
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 0.3px;
}
.card-footer { margin-top: auto; display: flex; align-items: center; gap: 8px; }
.rating-hint {
  font-size: 12px;
  color: var(--text-muted);
  letter-spacing: 0.5px;
}
</style>

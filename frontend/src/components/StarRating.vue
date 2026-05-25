<template>
  <span class="star-rating">
    <button
      v-for="n in 5" :key="n"
      class="star"
      :class="{ active: n <= modelValue, pop: n === lastClicked }"
      :style="{ animationDelay: n * 0.04 + 's' }"
      @click="handleClick(n)"
    >&#9733;</button>
  </span>
</template>

<script setup>
import { ref } from 'vue'
const props = defineProps({ modelValue: { type: Number, default: 0 } })
const emit = defineEmits(['update:modelValue'])
const lastClicked = ref(-1)

function handleClick(n) {
  lastClicked.value = n
  emit('update:modelValue', n)
  setTimeout(() => { lastClicked.value = -1 }, 400)
}
</script>

<style scoped>
.star-rating { display: inline-flex; gap: 4px; }
.star {
  background: none;
  border: none;
  font-size: 22px;
  color: rgba(255,255,255,0.1);
  cursor: pointer;
  padding: 0;
  line-height: 1;
  transition: color 0.15s, text-shadow 0.15s, transform 0.15s;
  will-change: transform;
}
.star:hover {
  color: rgba(255, 184, 0, 0.5);
  transform: scale(1.18);
}
.star.active {
  color: #ffb800;
  text-shadow: 0 0 10px rgba(255, 184, 0, 0.5), 0 0 20px rgba(255, 184, 0, 0.2);
}
.star.pop {
  animation: star-pop 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes star-pop {
  0% { transform: scale(1); }
  50% { transform: scale(1.45); text-shadow: 0 0 24px rgba(255, 184, 0, 0.8); }
  100% { transform: scale(1); }
}
</style>

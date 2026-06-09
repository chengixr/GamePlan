<template>
  <teleport to="body">
    <div class="toast-container">
      <transition-group name="toast">
        <div v-for="msg in messages" :key="msg.id" class="toast" :class="msg.type">
          <span class="toast-text">{{ msg.text }}</span>
          <button class="toast-close" @click="remove(msg.id)">&times;</button>
        </div>
      </transition-group>
    </div>
  </teleport>
</template>

<script setup>
import { ref } from 'vue'

const messages = ref([])
let nextId = 0

function show(text, type = 'info', duration = 3000) {
  const id = ++nextId
  messages.value.push({ id, text, type })
  if (duration > 0) {
    setTimeout(() => remove(id), duration)
  }
}

function remove(id) {
  messages.value = messages.value.filter(m => m.id !== id)
}

function success(text) { show(text, 'success') }
function error(text) { show(text, 'error', 5000) }
function info(text) { show(text, 'info') }

defineExpose({ show, success, error, info, remove })
</script>

<style scoped>
.toast-container {
  position: fixed; top: 16px; right: 16px; z-index: 9999;
  display: flex; flex-direction: column; gap: 8px;
  max-width: 360px;
}
.toast {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px;
  background: var(--surface);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  backdrop-filter: blur(8px);
}
.toast.success { border-left: 3px solid #10b981; }
.toast.error   { border-left: 3px solid var(--neon-magenta); }
.toast.info    { border-left: 3px solid var(--neon-cyan); }

.toast-text { flex: 1; font-size: 14px; color: var(--text-primary); line-height: 1.4; }
.toast-close {
  background: none; border: none; color: var(--text-muted);
  font-size: 18px; cursor: pointer; padding: 0; line-height: 1;
}
.toast-close:hover { color: var(--text-primary); }

.toast-enter-active { transition: all 0.3s ease; }
.toast-leave-active { transition: all 0.2s ease; }
.toast-enter-from { opacity: 0; transform: translateX(40px); }
.toast-leave-to   { opacity: 0; transform: translateX(40px); }
</style>

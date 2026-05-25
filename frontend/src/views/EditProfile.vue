<template>
  <div class="auth-wrapper">
    <div class="auth-card">
      <div class="auth-header">
        <svg class="header-icon" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="11" r="5" stroke="var(--neon-cyan)" stroke-width="2"/><path d="M6 27c0-5.5 4.5-10 10-10s10 4.5 10 10" stroke="var(--neon-cyan)" stroke-width="2" stroke-linecap="round"/></svg>
        <h2>编辑信息</h2>
      </div>
      <form @submit.prevent="onSave">
        <div class="field">
          <label>选择头像</label>
          <div class="avatar-grid">
            <button
              v-for="av in avatars" :key="av.id"
              class="avatar-option"
              :class="{ selected: selectedAvatar === av.id }"
              @click.prevent="selectedAvatar = av.id"
              v-html="av.svg"
            ></button>
          </div>
        </div>
        <div class="field">
          <label>用户昵称</label>
          <input v-model="nickname" type="text" placeholder="设置显示昵称" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" class="btn-submit" :disabled="loading">保存修改</button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { PRESET_AVATARS } from '../constants/avatars'

const router = useRouter()
const auth = useAuthStore()
const avatars = PRESET_AVATARS
const selectedAvatar = ref(auth.user?.avatar || '1')
const nickname = ref(auth.user?.nickname || auth.user?.username || '')
const error = ref('')
const loading = ref(false)

onMounted(async () => {
  await auth.checkAuth()
  if (auth.user) {
    selectedAvatar.value = auth.user.avatar || '1'
    nickname.value = auth.user.nickname || auth.user.username || ''
  }
})

async function onSave() {
  loading.value = true; error.value = ''
  try {
    await auth.updateProfile({ nickname: nickname.value, avatar: selectedAvatar.value })
    router.replace('/hot')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-wrapper {
  display: flex; align-items: center; justify-content: center;
  min-height: 70vh; padding: 24px;
}
.auth-card {
  width: 100%; max-width: 440px;
  background: var(--surface); border: 1px solid rgba(0,229,255,0.08);
  border-radius: 12px; padding: 36px;
}
.auth-header { text-align: center; margin-bottom: 28px; }
.header-icon { width: 40px; height: 40px; margin-bottom: 14px; opacity: 0.6; }
.auth-header h2 { font-family: var(--font-display); font-size: 18px; font-weight: 700; letter-spacing: 2px; }

.avatar-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; padding: 4px 8px; }
.avatar-option {
  width: 100%; aspect-ratio: 1; max-width: 56px; margin: 0 auto;
  border-radius: 8px; overflow: hidden;
  border: 2px solid transparent; background: transparent;
  cursor: pointer; padding: 0; transition: all 0.15s;
}
.avatar-option :deep(svg) { width: 100%; height: 100%; display: block; }
.avatar-option:hover { transform: scale(1.08); }
.avatar-option.selected { border-color: var(--neon-cyan); box-shadow: 0 0 10px rgba(0,229,255,0.3); }

.field { margin-bottom: 18px; }
.field label {
  display: block; font-size: 13px; font-weight: 500;
  color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.5px;
}
.field input {
  width: 100%; padding: 12px 14px;
  font-family: var(--font-body); font-size: 15px;
  color: var(--text-primary); background: var(--void);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 6px;
  outline: none; transition: border-color 0.2s, box-shadow 0.2s;
}
.field input:focus { border-color: var(--neon-cyan); box-shadow: 0 0 0 3px rgba(0,229,255,0.08); }
.field input::placeholder { color: var(--text-muted); }

.error { font-size: 13px; color: var(--neon-magenta); margin-bottom: 14px; padding: 8px 12px; background: rgba(255,45,120,0.06); border-radius: 4px; }

.btn-submit {
  width: 100%; padding: 13px; font-family: var(--font-display);
  font-size: 15px; font-weight: 600; letter-spacing: 3px; text-transform: uppercase;
  color: var(--void); background: var(--neon-cyan);
  border: none; border-radius: 6px; cursor: pointer;
  transition: box-shadow 0.2s, transform 0.15s;
}
.btn-submit:hover:not(:disabled) { box-shadow: 0 0 24px rgba(0,229,255,0.3); transform: translateY(-1px); }
.btn-submit:disabled { opacity: 0.5; cursor: default; }
</style>

<template>
  <div class="auth-wrapper">
    <div class="auth-card">
      <div class="auth-header">
        <svg class="header-icon" viewBox="0 0 32 32" fill="none"><rect x="6" y="14" width="20" height="14" rx="3" stroke="var(--neon-magenta)" stroke-width="2"/><path d="M10 14V9a6 6 0 0 1 12 0v5" stroke="var(--neon-magenta)" stroke-width="2" stroke-linecap="round"/><circle cx="16" cy="21" r="2" fill="var(--neon-magenta)"/></svg>
        <h2>修改密码</h2>
      </div>
      <form @submit.prevent="onSave">
        <div class="field">
          <label>原密码</label>
          <input v-model="oldPassword" type="password" placeholder="输入当前密码" required />
        </div>
        <div class="field">
          <label>新密码</label>
          <input v-model="newPassword" type="password" placeholder="至少 6 个字符" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="success" class="success">{{ success }}</p>
        <button type="submit" class="btn-submit" :disabled="loading">
          <span v-if="!loading">更新密码</span>
          <span v-else class="spinner"></span>
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const oldPassword = ref('')
const newPassword = ref('')
const error = ref('')
const success = ref('')
const loading = ref(false)

onMounted(async () => { await auth.checkAuth() })

async function onSave() {
  loading.value = true; error.value = ''; success.value = ''
  try {
    await auth.changePassword({ old_password: oldPassword.value, new_password: newPassword.value })
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
  width: 100%; max-width: 420px;
  background: var(--surface); border: 1px solid rgba(255,45,120,0.08);
  border-radius: 12px; padding: 40px 36px;
}
.auth-header { text-align: center; margin-bottom: 32px; }
.header-icon { width: 40px; height: 40px; margin-bottom: 14px; opacity: 0.6; }
.auth-header h2 { font-family: var(--font-display); font-size: 18px; font-weight: 700; letter-spacing: 2px; }

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
.field input:focus { border-color: var(--neon-magenta); box-shadow: 0 0 0 3px rgba(255,45,120,0.08); }
.field input::placeholder { color: var(--text-muted); }

.error { font-size: 13px; color: var(--neon-magenta); margin-bottom: 14px; padding: 8px 12px; background: rgba(255,45,120,0.06); border-radius: 4px; }
.success { font-size: 13px; color: #10b981; margin-bottom: 14px; padding: 8px 12px; background: rgba(16,185,129,0.06); border-radius: 4px; }

.btn-submit {
  width: 100%; padding: 13px; font-family: var(--font-display);
  font-size: 15px; font-weight: 600; letter-spacing: 3px; text-transform: uppercase;
  color: var(--void); background: var(--neon-magenta);
  border: none; border-radius: 6px; cursor: pointer;
  transition: box-shadow 0.2s, transform 0.15s;
}
.btn-submit:hover:not(:disabled) { box-shadow: 0 0 24px rgba(255,45,120,0.3); transform: translateY(-1px); }
.btn-submit:disabled { opacity: 0.5; cursor: default; }
.spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid transparent; border-top-color: var(--void); border-radius: 50%; animation: spin 0.6s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>

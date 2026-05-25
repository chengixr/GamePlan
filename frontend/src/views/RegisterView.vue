<template>
  <div class="auth-wrapper">
    <div class="auth-card">
      <div class="auth-header">
        <div class="auth-icon">&#9670;</div>
        <h2>注册</h2>
        <p class="auth-desc">加入 GamePlan，发现你的下一款游戏</p>
      </div>
      <form @submit.prevent="onRegister">
        <div class="field">
          <label>用户名</label>
          <input v-model="username" type="text" placeholder="取个名字吧" required autocomplete="username" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="至少 6 个字符" required autocomplete="new-password" />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" class="btn-submit" :disabled="loading">
          <span v-if="!loading">创建账号</span>
          <span v-else class="spinner"></span>
        </button>
      </form>
      <p class="switch-link">已有账号？<router-link to="/login">去登录</router-link></p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function onRegister() {
  loading.value = true; error.value = ''
  try { await auth.register(username.value, password.value); router.push('/hot') }
  catch (e) { error.value = e.message }
  finally { loading.value = false }
}
</script>

<style scoped>
.auth-wrapper {
  display: flex; align-items: center; justify-content: center;
  min-height: 70vh; padding: 24px;
}
.auth-card {
  width: 100%; max-width: 420px;
  background: var(--surface);
  border: 1px solid rgba(255, 45, 120, 0.08);
  border-radius: 12px;
  padding: 40px 36px;
}
.auth-header { text-align: center; margin-bottom: 32px; }
.auth-icon {
  font-size: 28px; color: var(--neon-magenta);
  margin-bottom: 12px;
  filter: drop-shadow(0 0 8px rgba(255, 45, 120, 0.4));
}
.auth-header h2 { font-family: var(--font-display); font-size: 24px; font-weight: 700; letter-spacing: 4px; }
.auth-desc { margin-top: 6px; font-size: 14px; color: var(--text-muted); }

.field { margin-bottom: 18px; }
.field label {
  display: block; font-size: 13px; font-weight: 500;
  color: var(--text-secondary); margin-bottom: 6px; letter-spacing: 0.5px;
}
.field input {
  width: 100%; padding: 12px 14px;
  font-family: var(--font-body); font-size: 15px;
  color: var(--text-primary);
  background: var(--void);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.field input:focus {
  border-color: var(--neon-magenta);
  box-shadow: 0 0 0 3px rgba(255, 45, 120, 0.08);
}
.field input::placeholder { color: var(--text-muted); }

.error {
  font-size: 13px; color: var(--neon-magenta);
  margin-bottom: 14px; padding: 8px 12px;
  background: rgba(255, 45, 120, 0.06);
  border-radius: 4px;
}
.btn-submit {
  width: 100%; padding: 13px;
  font-family: var(--font-display); font-size: 15px; font-weight: 600;
  letter-spacing: 3px; text-transform: uppercase;
  color: var(--void); background: var(--neon-magenta);
  border: none; border-radius: 6px; cursor: pointer;
  transition: box-shadow 0.2s, transform 0.15s;
}
.btn-submit:hover:not(:disabled) {
  box-shadow: 0 0 24px rgba(255, 45, 120, 0.3);
  transform: translateY(-1px);
}
.btn-submit:disabled { opacity: 0.5; cursor: default; }

.spinner {
  display: inline-block; width: 18px; height: 18px;
  border: 2px solid transparent; border-top-color: var(--void);
  border-radius: 50%; animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.switch-link { margin-top: 24px; text-align: center; font-size: 14px; color: var(--text-muted); }
.switch-link a { font-weight: 500; color: var(--neon-cyan); }
</style>

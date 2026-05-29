<template>
  <nav class="navbar">
    <router-link to="/" class="logo">
      <span class="logo-icon">&#9650;</span>
      <span class="logo-text">GAME<span class="logo-accent">PLAN</span></span>
    </router-link>
    <div class="nav-links">
      <router-link to="/hot" class="nav-link">热销榜</router-link>
      <router-link v-if="auth.user" to="/recommend" class="nav-link">推荐</router-link>
    </div>
    <div class="nav-right">
      <template v-if="auth.user">
        <div class="user-menu" ref="menuRef">
          <button class="avatar-btn" @click="open = !open">
            <span class="avatar-img" v-html="avatarHTML"></span>
            <span class="username">{{ auth.user.nickname || auth.user.username }}</span>
            <span class="arrow">&#9662;</span>
          </button>
          <div class="dropdown" v-if="open" @click.stop>
            <router-link to="/profile" class="dropdown-item" @click="open=false">编辑信息</router-link>
            <router-link to="/password" class="dropdown-item" @click="open=false">修改密码</router-link>
            <router-link v-if="auth.user?.is_admin" to="/admin" class="dropdown-item admin-item" @click="open=false">管理后台</router-link>
            <button class="dropdown-item logout" @click="onLogout">退出</button>
          </div>
        </div>
      </template>
      <template v-else>
        <router-link to="/login" class="nav-link">登录</router-link>
        <router-link to="/register" class="nav-link nav-link--accent">注册</router-link>
      </template>
    </div>
  </nav>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'
import { getAvatarSVG } from '../constants/avatars'

const auth = useAuthStore()
const router = useRouter()
const open = ref(false)
const menuRef = ref(null)

const avatarHTML = computed(() => getAvatarSVG(auth.user?.avatar || '1'))

function closeMenu(e) {
  if (menuRef.value && !menuRef.value.contains(e.target)) open.value = false
}

onMounted(() => document.addEventListener('click', closeMenu))
onBeforeUnmount(() => document.removeEventListener('click', closeMenu))

async function onLogout() {
  await auth.logout()
  router.push('/login')
  open.value = false
}
</script>

<style scoped>
.navbar {
  position: sticky; top: 0; z-index: 100;
  display: flex; align-items: center; gap: 28px;
  padding: 12px 32px;
  background: rgba(13,13,26,0.85);
  backdrop-filter: blur(16px) saturate(180%);
  border-bottom: 1px solid rgba(0,229,255,0.08);
}
.logo { display: flex; align-items: center; gap: 8px; text-decoration: none; }
.logo-icon { font-size: 14px; color: var(--neon-cyan); filter: drop-shadow(0 0 6px rgba(0,229,255,0.6)); }
.logo-text { font-family: var(--font-display); font-size: 20px; font-weight: 700; color: var(--text-primary); letter-spacing: 2px; }
.logo-accent { color: var(--neon-cyan); }
.nav-links { display: flex; gap: 8px; }
.nav-link {
  position: relative; padding: 6px 14px; font-size: 14px; font-weight: 500;
  color: var(--text-secondary); text-decoration: none; border-radius: 4px; transition: all 0.2s;
}
.nav-link:hover { color: var(--text-primary); background: rgba(255,255,255,0.04); }
.nav-link.router-link-active { color: var(--neon-cyan); background: rgba(0,229,255,0.06); }
.nav-link.router-link-active::after {
  content: ''; position: absolute; bottom: 0; left: 14px; right: 14px;
  height: 2px; background: var(--neon-cyan); box-shadow: 0 0 8px var(--neon-cyan);
}
.nav-link--accent { color: var(--neon-cyan) !important; border: 1px solid rgba(0,229,255,0.3); }
.nav-link--accent:hover { background: rgba(0,229,255,0.1) !important; box-shadow: 0 0 12px rgba(0,229,255,0.15); }
.nav-right { margin-left: auto; display: flex; align-items: center; }

.user-menu { position: relative; }
.avatar-btn {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 10px 4px 4px;
  background: transparent; border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px; cursor: pointer;
  transition: border-color 0.2s;
}
.avatar-btn:hover { border-color: rgba(0,229,255,0.3); }
.avatar-img {
  display: inline-block; width: 32px; height: 32px; border-radius: 6px; overflow: hidden;
}
.avatar-img :deep(svg) { width: 32px; height: 32px; }
.username { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.arrow { font-size: 10px; color: var(--text-muted); }

.dropdown {
  position: absolute; top: calc(100% + 6px); right: 0;
  min-width: 140px;
  background: var(--surface); border: 1px solid rgba(0,229,255,0.12);
  border-radius: 8px; padding: 4px; z-index: 200;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
.dropdown-item {
  display: block; width: 100%; padding: 10px 14px;
  font-family: var(--font-body); font-size: 14px; color: var(--text-secondary);
  background: transparent; border: none; border-radius: 4px;
  cursor: pointer; text-align: left; text-decoration: none;
  transition: all 0.15s;
}
.dropdown-item:hover { background: var(--surface-raised); color: var(--text-primary); }
.dropdown-item.admin-item { color: var(--neon-amber); }
.dropdown-item.admin-item:hover { background: rgba(255,184,0,0.06); }
.dropdown-item.logout { color: var(--neon-magenta); }
.dropdown-item.logout:hover { background: rgba(255,45,120,0.08); }
</style>

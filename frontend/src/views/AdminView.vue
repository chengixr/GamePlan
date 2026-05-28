<template>
  <div class="admin">
    <h1 class="admin-title">管理后台</h1>
    <div class="admin-tabs">
      <button v-for="tab in tabs" :key="tab.key" class="admin-tab" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
        {{ tab.label }}
      </button>
    </div>
    <AdminUsers v-if="activeTab === 'users'" />
    <AdminSync v-if="activeTab === 'sync'" />
    <AdminLogs v-if="activeTab === 'logs'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AdminUsers from '../components/AdminUsers.vue'
import AdminSync from '../components/AdminSync.vue'
import AdminLogs from '../components/AdminLogs.vue'

const activeTab = ref('users')
const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'sync', label: '同步监控' },
  { key: 'logs', label: '日志查看' },
]
</script>

<style scoped>
.admin { max-width: 1200px; margin: 0 auto; padding: 24px; }

.admin-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 4px;
  margin-bottom: 28px;
  color: var(--text-primary);
}

.admin-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 28px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.admin-tab {
  background: transparent;
  border: none;
  padding: 10px 22px;
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.2s;
}
.admin-tab:hover { color: var(--text-primary); }
.admin-tab.active {
  color: var(--neon-cyan);
  border-bottom-color: var(--neon-cyan);
}
</style>

<template>
  <div class="au-wrap">
    <div class="au-toolbar">
      <input v-model="search" class="au-search" placeholder="搜索用户名或昵称..." @keyup.enter="loadUsers" />
      <button class="au-btn" @click="loadUsers">搜索</button>
    </div>

    <div class="au-table-wrap" v-if="!loading">
      <table class="au-table" v-if="users.length">
        <thead>
          <tr><th>ID</th><th>用户名</th><th>昵称</th><th>评分</th><th>注册时间</th><th>状态</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id" :class="{ inactive: !u.is_active }">
            <td>{{ u.id }}</td>
            <td>{{ u.username }}</td>
            <td>{{ u.nickname }}</td>
            <td>{{ u.rating_count }}</td>
            <td>{{ u.created_at }}</td>
            <td><span class="au-status" :class="{ off: !u.is_active }">{{ u.is_active ? '启用' : '禁用' }}</span></td>
            <td class="au-actions">
              <button class="au-action-btn" @click="toggleStatus(u)">{{ u.is_active ? '禁用' : '启用' }}</button>
              <button class="au-action-btn" @click="viewRatings(u)">评分</button>
              <button class="au-action-btn danger" @click="deleteUser(u)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="au-empty" v-else>暂无用户数据</div>
    </div>
    <div class="au-empty" v-else>加载中...</div>

    <div class="au-pager" v-if="total > pageSize">
      <button :disabled="page <= 1" @click="page--; loadUsers()">上一页</button>
      <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button :disabled="page >= Math.ceil(total / pageSize)" @click="page++; loadUsers()">下一页</button>
    </div>

    <div class="au-modal-overlay" v-if="ratingUser" @click.self="ratingUser = null">
      <div class="au-modal">
        <h3>{{ ratingUser.username }} 的评分记录</h3>
        <div class="au-ratings-list" v-if="ratings.length">
          <div v-for="r in ratings" :key="r.game_id" class="au-rating-row">
            <span>{{ r.game_name }}</span>
            <span class="au-stars">{{ '★'.repeat(r.score) }}{{ '☆'.repeat(5 - r.score) }}</span>
            <span class="au-rating-date">{{ r.created_at }}</span>
          </div>
        </div>
        <div v-else class="au-empty">暂无评分</div>
        <button class="au-btn" style="margin-top:16px" @click="ratingUser = null">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const search = ref('')
const users = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const ratingUser = ref(null)
const ratings = ref([])

async function loadUsers() {
  loading.value = true
  try {
    const res = await api.adminUsers(search.value, page.value, pageSize)
    users.value = res.items
    total.value = res.total
  } catch { users.value = [] }
  finally { loading.value = false }
}

async function toggleStatus(u) {
  const newStatus = !u.is_active
  try {
    await api.adminUserStatus(u.id, newStatus)
    u.is_active = newStatus
  } catch (e) { alert(e.message) }
}

async function deleteUser(u) {
  if (!confirm(`确定删除用户 "${u.username}" 吗？该操作不可撤销。`)) return
  try {
    await api.adminDeleteUser(u.id)
    loadUsers()
  } catch (e) { alert(e.message) }
}

async function viewRatings(u) {
  ratingUser.value = u
  try {
    const res = await api.adminUserRatings(u.id)
    ratings.value = res.ratings || []
  } catch { ratings.value = [] }
}

onMounted(() => loadUsers())
</script>

<style scoped>
.au-wrap { color: var(--text-primary); }
.au-toolbar { display: flex; gap: 10px; margin-bottom: 20px; }
.au-search {
  flex: 1; max-width: 320px;
  padding: 8px 14px;
  background: var(--surface);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}
.au-search:focus { border-color: var(--neon-cyan); }
.au-btn {
  padding: 8px 18px;
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.au-btn:hover { border-color: var(--neon-cyan); color: var(--neon-cyan); }

.au-table-wrap { overflow-x: auto; }
.au-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.au-table th {
  text-align: left; padding: 10px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  color: var(--text-muted); font-weight: 500; font-size: 12px;
  letter-spacing: 1px;
}
.au-table td { padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.03); }
.au-table tr.inactive td { opacity: 0.45; }
.au-status { font-size: 12px; padding: 2px 8px; border-radius: 3px; background: rgba(16,185,129,0.12); color: #10b981; }
.au-status.off { background: rgba(255,45,120,0.1); color: var(--neon-magenta); }
.au-actions { display: flex; gap: 6px; }
.au-action-btn {
  padding: 3px 10px; font-size: 12px;
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 4px; color: var(--text-secondary);
  cursor: pointer; transition: all 0.15s;
}
.au-action-btn:hover { color: var(--neon-cyan); border-color: rgba(0,229,255,0.2); }
.au-action-btn.danger:hover { color: var(--neon-magenta); border-color: rgba(255,45,120,0.2); }

.au-pager { display: flex; align-items: center; gap: 14px; margin-top: 20px; justify-content: center; }
.au-pager button {
  padding: 6px 16px;
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 4px; color: var(--text-secondary);
  font-size: 13px; cursor: pointer;
}
.au-pager button:hover:not(:disabled) { color: var(--neon-cyan); border-color: rgba(0,229,255,0.2); }
.au-pager button:disabled { opacity: 0.3; cursor: default; }

.au-modal-overlay {
  position: fixed; inset: 0; z-index: 500;
  background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center;
}
.au-modal {
  background: var(--surface);
  border: 1px solid rgba(0,229,255,0.12);
  border-radius: 12px;
  padding: 28px;
  min-width: 420px;
  max-width: 560px;
  max-height: 70vh;
  overflow-y: auto;
}
.au-modal h3 { margin-bottom: 16px; font-size: 16px; }
.au-ratings-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.au-rating-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
.au-stars { color: var(--neon-amber); font-size: 13px; }
.au-rating-date { font-size: 12px; color: var(--text-muted); }
.au-empty { text-align: center; padding: 40px; color: var(--text-muted); }
</style>

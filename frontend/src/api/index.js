const BASE = '/api'

async function request(path, options = {}) {
  const headers = { ...options.headers }
  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  try {
    const res = await fetch(`${BASE}${path}`, {
      credentials: 'include',
      headers,
      signal: controller.signal,
      ...options,
    })
    clearTimeout(timeout)
    return handleResponse(res)
  } catch (e) {
    clearTimeout(timeout)
    if (e.name === 'AbortError') throw new Error('请求超时，请重试')
    throw e
  }
}

async function handleResponse(res) {
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('请先登录')
    }
    const err = await res.json().catch(() => ({}))
    // Pydantic 校验错误返回数组，提取第一条消息
    let msg = err.detail || `请求失败 (${res.status})`
    if (Array.isArray(msg)) {
      msg = msg.map(e => e.msg || e.message || JSON.stringify(e)).join('; ')
    }
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  register: (body) => request('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  login: (body) => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),
  gameDetail: (id) => request('/games/' + id),
  getTags: () => request('/games/tags'),
  search: (q, page = 1, pageSize = 20) => request(`/games/search?q=${encodeURIComponent(q)}&page=${page}&page_size=${pageSize}`),
  topSellers: (page = 1, pageSize = 20) => request(`/games/top-sellers?page=${page}&page_size=${pageSize}`),
  dismissGame: (gameId) => request(`/games/${gameId}/dismiss`, { method: 'POST' }),
  recommended: (page = 1, pageSize = 20) => request(`/games/recommended?page=${page}&page_size=${pageSize}`),
  rate: (gameId, score) => request('/ratings/', { method: 'POST', body: JSON.stringify({ game_id: gameId, score }) }),
  myRatings: () => request('/ratings/mine'),
  historyDates: () => request('/games/top-sellers/dates'),
  history: (targetDate, page = 1, pageSize = 20) =>
    request(`/games/top-sellers/history?target_date=${targetDate}&page=${page}&page_size=${pageSize}`),
  rankHistory: (gameId, days = 7) => request(`/games/${gameId}/rank-history?days=${days}`),
  updateProfile: (body) => request('/auth/profile', { method: 'PUT', body: JSON.stringify(body) }),
  changePassword: (body) => request('/auth/password', { method: 'PUT', body: JSON.stringify(body) }),
  adminUsers: (search = '', page = 1, pageSize = 20) =>
    request(`/admin/users?search=${encodeURIComponent(search)}&page=${page}&page_size=${pageSize}`),
  adminUserStatus: (userId, isActive) =>
    request(`/admin/users/${userId}/status`, { method: 'PUT', body: JSON.stringify({ is_active: isActive }) }),
  adminUserAdmin: (userId, isAdmin) =>
    request(`/admin/users/${userId}/admin`, { method: 'PUT', body: JSON.stringify({ is_admin: isAdmin }) }),
  adminDeleteUser: (userId) =>
    request(`/admin/users/${userId}`, { method: 'DELETE' }),
  adminUserRatings: (userId) =>
    request(`/admin/users/${userId}/ratings`),
  adminSyncStatus: () => request('/admin/sync/status'),
  adminSyncTrigger: () => request('/admin/sync/trigger', { method: 'POST' }),
  adminSyncStats: () => request('/admin/sync/stats'),
  adminSyncGame: (gameId) => request(`/admin/sync/game/${gameId}`),
  adminLogs: (date = '', level = 'ALL', lines = 100) =>
    request(`/admin/logs?target_date=${date}&level=${level}&lines=${lines}`),
  adminSchedulerJobs: () => request('/admin/scheduler/jobs'),
  adminSchedulerTrigger: (jobId) => request(`/admin/scheduler/jobs/${jobId}/trigger`, { method: 'POST' }),
  toggleFavorite: (gameId) => request(`/favorites/${gameId}`, { method: 'POST' }),
  favoriteIds: () => request('/favorites/ids'),
  favorites: (page = 1, pageSize = 20) => request(`/favorites?page=${page}&page_size=${pageSize}`),
}

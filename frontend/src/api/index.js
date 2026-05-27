const BASE = '/api'

async function request(path, options = {}) {
  const headers = { ...options.headers }
  // 仅对带 body 的请求设置 Content-Type
  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers,
    ...options,
  })
  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('请先登录')
    }
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `请求失败 (${res.status})`)
  }
  return res.json()
}

export const api = {
  register: (body) => request('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  login: (body) => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),
  gameDetail: (id) => request('/games/' + id),
  topSellers: (page = 1, pageSize = 20) => request(`/games/top-sellers?page=${page}&page_size=${pageSize}`),
  recommended: (page = 1, pageSize = 20) => request(`/games/recommended?page=${page}&page_size=${pageSize}`),
  rate: (gameId, score) => request('/ratings/', { method: 'POST', body: JSON.stringify({ game_id: gameId, score }) }),
  myRatings: () => request('/ratings/mine'),
  historyDates: () => request('/games/top-sellers/dates'),
  history: (targetDate, page = 1, pageSize = 20) =>
    request(`/games/top-sellers/history?target_date=${targetDate}&page=${page}&page_size=${pageSize}`),
  rankHistory: (gameId, days = 7) => request(`/games/${gameId}/rank-history?days=${days}`),
  updateProfile: (body) => request('/auth/profile', { method: 'PUT', body: JSON.stringify(body) }),
  changePassword: (body) => request('/auth/password', { method: 'PUT', body: JSON.stringify(body) }),
}

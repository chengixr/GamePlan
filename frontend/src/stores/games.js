import { defineStore } from 'pinia'
import { api } from '../api'

export const useGamesStore = defineStore('games', {
  state: () => ({
    hotGames: [],
    hotTotal: 0,
    hotPage: 1,
    recGames: [],
    recTotal: 0,
    recPage: 1,
    currentGame: null,
    myRatings: {},
    historyDates: [],
    historyDate: '',
    historyGames: [],
    historyTotal: 0,
    historyPage: 1,
  }),
  actions: {
    // === 热销榜（支持追加） ===
    async loadHot(page = 1, pageSize = 20, append = false) {
      const data = await api.topSellers(page, pageSize)
      if (append) {
        this.hotGames.push(...data.items)
      } else {
        this.hotGames = data.items
      }
      this.hotTotal = data.total
      this.hotPage = page
    },

    // === 推荐 ===
    async loadRecommended(page = 1, pageSize = 20, append = false) {
      const data = await api.recommended(page, pageSize)
      if (append) {
        this.recGames.push(...data.items)
      } else {
        this.recGames = data.items
      }
      this.recTotal = data.total
      this.recPage = page
    },

    // === 游戏详情 ===
    async loadGameDetail(id) {
      this.currentGame = await api.gameDetail(id)
    },

    // === 评分 ===
    async rate(gameId, score) {
      await api.rate(gameId, score)
      this.myRatings = { ...this.myRatings, [gameId]: score }
    },
    async loadMyRatings() {
      try {
        const ratings = await api.myRatings()
        const map = {}
        for (const r of ratings) map[r.game_id] = r.score
        this.myRatings = map
      } catch { /* 未登录时忽略 */ }
    },

    // === 历史记录 ===
    async loadHistoryDates() {
      try {
        this.historyDates = await api.historyDates()
      } catch { this.historyDates = [] }
    },
    async loadHistory(targetDate, page = 1, pageSize = 20, append = false) {
      const data = await api.history(targetDate, page, pageSize)
      if (append) {
        this.historyGames.push(...data.items)
      } else {
        this.historyGames = data.items
      }
      this.historyTotal = data.total
      this.historyDate = targetDate
      this.historyPage = page
    },
  },
})

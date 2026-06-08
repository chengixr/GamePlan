import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/', redirect: '/hot' },
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue') },
  { path: '/register', name: 'Register', component: () => import('../views/RegisterView.vue') },
  { path: '/hot', name: 'Hot', component: () => import('../views/HotView.vue') },
  { path: '/recommend', name: 'Recommend', component: () => import('../views/RecommendView.vue'), meta: { requiresAuth: true } },
  { path: '/favorites', name: 'Favorites', component: () => import('../views/FavoritesView.vue'), meta: { requiresAuth: true } },
  { path: '/profile', name: 'Profile', component: () => import('../views/EditProfile.vue'), meta: { requiresAuth: true } },
  { path: '/password', name: 'Password', component: () => import('../views/ChangePassword.vue'), meta: { requiresAuth: true } },
  { path: '/game/:id', name: 'GameDetail', component: () => import('../views/GameDetail.vue') },
  { path: '/admin', name: 'Admin', component: () => import('../views/AdminView.vue'), meta: { requiresAdmin: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()
  if (!auth.user) {
    try { await auth.checkAuth() } catch {}
  }
  if (to.meta.requiresAdmin && !auth.user?.is_admin) {
    next('/hot')
  } else if (to.meta.requiresAuth && !auth.user) {
    next('/login')
  } else {
    next()
  }
})

export default router

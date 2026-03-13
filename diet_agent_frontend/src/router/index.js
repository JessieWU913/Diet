// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'

import LoginView from '../views/LoginView.vue'
import DietLogView from '../views/DietLogView.vue'
import RecipeView from '../views/RecipeView.vue'
import StatsView from '../views/StatsView.vue'
import ChatView from '../views/ChatView.vue'
import HealthLogView from '../views/HealthLogView.vue'
import FavoritesView from '../views/FavoritesView.vue'
import IngredientSearchView from '../views/IngredientSearchView.vue'
import AdminView from '../views/AdminView.vue'

const routes = [
  { path: '/', redirect: '/diet-log' },
  { path: '/login', name: 'Login', component: LoginView },
  { path: '/diet-log', name: 'DietLog', component: DietLogView, meta: { requiresAuth: true } },
  { path: '/recipes', name: 'Recipes', component: RecipeView, meta: { requiresAuth: true } },
  { path: '/stats', name: 'Stats', component: StatsView, meta: { requiresAuth: true } },
  { path: '/chat', name: 'Chat', component: ChatView, meta: { requiresAuth: true } },
  { path: '/health-log', name: 'HealthLog', component: HealthLogView, meta: { requiresAuth: true } },
  { path: '/favorites', name: 'Favorites', component: FavoritesView, meta: { requiresAuth: true } },
  { path: '/ingredient-search', name: 'IngredientSearch', component: IngredientSearchView, meta: { requiresAuth: true } },
  { path: '/admin', name: 'Admin', component: AdminView, meta: { requiresAdmin: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const isAuthenticated = localStorage.getItem('user_id')
  const isAdmin = localStorage.getItem('is_admin') === '1'
  const adminToken = localStorage.getItem('admin_token')

  if (to.meta.requiresAdmin && !(isAdmin && adminToken)) {
    next({ name: 'Login' })
  } else if (to.meta.requiresAuth && !isAuthenticated) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && isAdmin && adminToken) {
    next({ name: 'Admin' })
  } else if (to.name === 'Login' && isAuthenticated) {
    next({ name: 'DietLog' })
  } else {
    next()
  }
})

export default router

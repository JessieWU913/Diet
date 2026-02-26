import { createRouter, createWebHistory } from 'vue-router'

// 引入组件
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/stats',
      name: 'stats',
      // 路由懒加载：访问时才加载，提升性能
      component: () => import('../views/StatsView.vue')
    },
    {
      path: '/meals',
      name: 'meals',
      component: () => import('../views/MealView.vue')
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('../views/ProfileView.vue')
    },
    {
      path: '/other',
      name: 'other',
      component: () => import('../views/OtherView.vue')
    }
  ]
})

export default router

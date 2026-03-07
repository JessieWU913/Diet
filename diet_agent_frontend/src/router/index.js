// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ProfileView from '../views/ProfileView.vue'
import MealView from '../views/MealView.vue'
// 预留热量统计页 (如果你还没建文件，可以先让它指向 HomeView，或者建个空的 StatsView.vue)
// import StatsView from '../views/StatsView.vue'

const routes = [
  { path: '/', name: 'Home', component: HomeView }, // 暂时把首页设为对话页
  { path: '/chat', name: 'Chat', component: HomeView },
  { path: '/meal', name: 'Meal', component: MealView },
  { path: '/stats', name: 'Stats', component: HomeView },
  { path: '/profile', name: 'Profile', component: ProfileView },
  { path: '/profile', name: 'Profile', component: ProfileView },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router

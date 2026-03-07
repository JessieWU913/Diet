<template>
  <div id="app">
    <header v-if="$route.path !== '/login'" class="app-header">
      <h1>智能膳食助手</h1>
      <nav class="main-nav">
        <router-link to="/chat">智能咨询</router-link>
        <router-link to="/meals">菜谱排期</router-link>
        <router-link to="/profile">个人中心</router-link>
      </nav>
      <button @click="logout" class="logout-btn">退出</button>
    </header>

    <main class="main-content">
      <router-view></router-view>
    </main>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()

const logout = () => {
  localStorage.removeItem('user_id')
  router.push('/login')
}
</script>

<style>
/* ... 原有的样式 ... */
.logout-btn {
  background: #e74c3c; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; margin-left: auto;
}
.logout-btn:hover { background: #c0392b; }
</style>

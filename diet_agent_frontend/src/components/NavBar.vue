<template>
  <nav class="navbar">
    <div class="logo">
      <span class="icon">🥗</span>
      <span class="title">膳食 Agent</span>
    </div>

    <div class="nav-links">
      <router-link to="/chat">🏠 主页/对话</router-link>
      <router-link to="/meal">📅 菜谱单</router-link>
      <router-link to="/stats">📊 热量统计</router-link>
      <router-link to="/profile">👤 个人中心</router-link>
    </div>
  </nav>
</template>

<style scoped>
/* 保持你之前的样式不变即可 */
.navbar { display: flex; justify-content: space-between; align-items: center; padding: 0 40px; height: 60px; background-color: #ffffff; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05); z-index: 10; }
.logo { display: flex; align-items: center; gap: 8px; }
.logo .icon { font-size: 24px; }
.logo .title { font-size: 18px; font-weight: bold; color: #2c3e50; }
.nav-links { display: flex; gap: 20px; }
.nav-links a { text-decoration: none; color: #7f8c8d; font-weight: 600; font-size: 15px; padding: 6px 12px; border-radius: 6px; transition: all 0.3s ease; }
.nav-links a:hover { background-color: #f8f9fa; color: #42b983; }
.nav-links a.router-link-active { color: #42b983; background-color: #ebf7f1; }
</style>

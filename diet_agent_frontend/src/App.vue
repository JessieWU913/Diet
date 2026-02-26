<script setup>
import { RouterView } from 'vue-router'
// 引入上一轮写好的导航栏组件
import NavBar from '@/components/NavBar.vue'
</script>

<template>
  <div class="app-layout">
    <NavBar />

    <main class="main-content">
      <RouterView v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </RouterView>
    </main>
  </div>
</template>

<style>
/* --- 全局样式重置 --- */
body {
  margin: 0;
  padding: 0;
  font-family: 'PingFang SC', 'Helvetica Neue', Helvetica, 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif;
  background-color: #f5f7fa; /* 统一浅灰背景，突出卡片 */
  color: #303133;
  -webkit-font-smoothing: antialiased;
}

* {
  box-sizing: border-box;
}

/* 链接无下划线 */
a {
  text-decoration: none;
  color: inherit;
}

/* --- 布局样式 --- */
.app-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.main-content {
  flex: 1; /* 让内容区撑满剩余高度 */
  width: 100%;
  /* 如果你的 NavBar 高度是 80px，这里不需要 margin-top，因为 NavBar 是 position: sticky */
}

/* --- 过渡动画 (可选) --- */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

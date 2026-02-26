<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search, User, Menu as IconMenu } from '@element-plus/icons-vue'

const router = useRouter()
const activeIndex = ref('/')
const isMobileMenuOpen = ref(false)
const searchQuery = ref('')

const handleSelect = (key) => {
  router.push(key)
  isMobileMenuOpen.value = false
}
</script>

<template>
  <nav class="navbar">
    <div class="nav-container">
      <div class="logo" @click="router.push('/')">
        🥗 DietAI
      </div>

      <div class="desktop-menu">
        <el-menu
          :default-active="activeIndex"
          mode="horizontal"
          :ellipsis="false"
          @select="handleSelect"
          class="el-menu-demo"
        >
          <el-menu-item index="/">主页</el-menu-item>
          <el-menu-item index="/stats">数据统计</el-menu-item>
          <el-menu-item index="/meals">我的餐食</el-menu-item>
          <el-menu-item index="/other">其他</el-menu-item>
        </el-menu>
      </div>

      <div class="nav-right">
        <el-input
          v-model="searchQuery"
          placeholder="搜索食材/食谱..."
          class="search-bar"
          :prefix-icon="Search"
        />
        <el-avatar :icon="User" class="user-icon" @click="router.push('/profile')" />

        <div class="hamburger" @click="isMobileMenuOpen = !isMobileMenuOpen">
          <el-icon size="24"><IconMenu /></el-icon>
        </div>
      </div>
    </div>

    <div v-if="isMobileMenuOpen" class="mobile-menu">
      <div @click="handleSelect('/')">主页</div>
      <div @click="handleSelect('/stats')">数据统计</div>
      <div @click="handleSelect('/meals')">我的餐食</div>
      <div @click="handleSelect('/other')">其他</div>
    </div>
  </nav>
</template>

<style scoped>
.navbar {
  position: sticky; /* 粘性固定 */
  top: 0;
  z-index: 1000;
  height: 80px;
  background: white;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  width: 100%;
}

.nav-container {
  max-width: 1440px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.logo {
  font-size: 24px;
  font-weight: bold;
  color: #03bdac;
  cursor: pointer;
}

.desktop-menu {
  flex: 1;
  display: flex;
  justify-content: center;
}
.el-menu-demo { border-bottom: none !important; }

.nav-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.search-bar { width: 200px; }
.user-icon { cursor: pointer; background: #4CAF50; }
.hamburger { display: none; cursor: pointer; }

/* 响应式 */
@media (max-width: 768px) {
  .desktop-menu { display: none; }
  .search-bar { display: none; } /* 移动端可隐藏搜索或折叠 */
  .hamburger { display: block; }

  .mobile-menu {
    background: white;
    border-top: 1px solid #eee;
    padding: 20px;
  }
  .mobile-menu div {
    padding: 15px;
    border-bottom: 1px solid #f5f5f5;
  }
}
</style>

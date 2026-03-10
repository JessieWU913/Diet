<template>
  <div id="app" :class="{ 'no-sidebar': $route.path === '/login' }">
    <!-- 侧边导航栏 -->
    <aside v-if="$route.path !== '/login'" class="sidebar">
      <div class="sidebar-logo">
        <span class="logo-icon">🥗</span>
        <span class="logo-text">DietAI</span>
      </div>

      <nav class="sidebar-nav">
        <router-link to="/diet-log" class="nav-item">
          <span class="nav-icon">📝</span><span>饮食记录</span>
        </router-link>
        <router-link to="/recipes" class="nav-item">
          <span class="nav-icon">🍽️</span><span>食谱推荐</span>
        </router-link>
        <router-link to="/stats" class="nav-item">
          <span class="nav-icon">📊</span><span>营养分析</span>
        </router-link>
        <router-link to="/chat" class="nav-item">
          <span class="nav-icon">🤖</span><span>AI 助手</span>
        </router-link>
        <router-link to="/health-log" class="nav-item">
          <span class="nav-icon">📖</span><span>健康日志</span>
        </router-link>
        <router-link to="/favorites" class="nav-item">
          <span class="nav-icon">⭐</span><span>收藏夹</span>
        </router-link>
      </nav>

      <div class="sidebar-bottom">
        <div class="avatar-section" @click="showProfileModal = true">
          <div class="avatar-circle">{{ userInitial }}</div>
          <span class="avatar-name">{{ userName || '未登录' }}</span>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main :class="$route.path === '/login' ? 'main-full' : 'main-content'">
      <router-view></router-view>
    </main>

    <!-- 个人中心弹窗 -->
    <div v-if="showProfileModal" class="modal-overlay" @click.self="showProfileModal = false">
      <div class="profile-modal">
        <div class="pm-header">
          <h3>👤 个人中心</h3>
          <button class="close-btn" @click="showProfileModal = false">×</button>
        </div>
        <div class="pm-body">
          <div class="pm-avatar-row">
            <div class="pm-avatar-big">{{ userInitial }}</div>
            <div class="pm-info">
              <p class="pm-name">{{ userName || '未设置昵称' }}</p>
              <p class="pm-id">ID: {{ userId || '—' }}</p>
            </div>
          </div>

          <div class="pm-form">
            <div class="pm-row">
              <div class="pm-field">
                <label>昵称</label>
                <input v-model="profileForm.name" placeholder="输入昵称" />
              </div>
              <div class="pm-field">
                <label>性别</label>
                <select v-model="profileForm.gender">
                  <option value="male">男</option>
                  <option value="female">女</option>
                </select>
              </div>
            </div>
            <div class="pm-row">
              <div class="pm-field">
                <label>出生日期</label>
                <input type="date" v-model="profileForm.birthDate" />
              </div>
              <div class="pm-field">
                <label>身高 (cm)</label>
                <input type="number" v-model.number="profileForm.height" placeholder="175" />
              </div>
            </div>
            <div class="pm-row">
              <div class="pm-field">
                <label>体重 (kg)</label>
                <input type="number" v-model.number="profileForm.weight" placeholder="65" />
              </div>
              <div class="pm-field">
                <label>新密码 (可选)</label>
                <input type="password" v-model="profileForm.newPassword" placeholder="留空不修改" />
              </div>
            </div>

            <div class="pm-field full">
              <label>过敏源</label>
              <div class="tag-box">
                <span class="tag" v-for="(t, i) in profileForm.allergies" :key="'a'+i">
                  {{ t }} <span class="tag-x" @click="profileForm.allergies.splice(i, 1)">×</span>
                </span>
                <input v-model="allergyInput" @keyup.enter.prevent="addAllergy" placeholder="回车添加..." class="tag-input" />
              </div>
            </div>
            <div class="pm-field full">
              <label>不喜欢的食材</label>
              <div class="tag-box">
                <span class="tag" v-for="(t, i) in profileForm.dislikes" :key="'d'+i">
                  {{ t }} <span class="tag-x" @click="profileForm.dislikes.splice(i, 1)">×</span>
                </span>
                <input v-model="dislikeInput" @keyup.enter.prevent="addDislike" placeholder="回车添加..." class="tag-input" />
              </div>
            </div>
          </div>

          <div class="pm-actions">
            <button class="pm-save" @click="saveProfile" :disabled="saving">{{ saving ? '保存中...' : '💾 保存' }}</button>
            <button class="pm-logout" @click="logout">退出登录</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import API from './api.js'

const router = useRouter()
const route = useRoute()

const showProfileModal = ref(false)
const saving = ref(false)
const userId = ref(localStorage.getItem('user_id') || '')
const userName = ref(localStorage.getItem('user_name') || '')
const allergyInput = ref('')
const dislikeInput = ref('')

const userInitial = computed(() => {
  return (userName.value || userId.value || '?')[0].toUpperCase()
})

const profileForm = ref({
  name: '', gender: 'female', birthDate: '', height: '', weight: '',
  allergies: [], dislikes: [], newPassword: ''
})

const loadProfile = async () => {
  if (!userId.value) return
  try {
    const res = await API.get(`/profile/?user_id=${userId.value}`)
    if (res.data) {
      profileForm.value.gender = res.data.gender || 'female'
      profileForm.value.birthDate = res.data.birthDate || ''
      profileForm.value.height = res.data.height || ''
      profileForm.value.weight = res.data.weight || ''
      profileForm.value.allergies = res.data.allergies || []
      profileForm.value.dislikes = res.data.dislikes || []
    }
  } catch (e) { console.error('加载画像失败', e) }
}

const addAllergy = () => {
  const v = allergyInput.value.trim()
  if (v && !profileForm.value.allergies.includes(v)) {
    profileForm.value.allergies.push(v)
  }
  allergyInput.value = ''
}
const addDislike = () => {
  const v = dislikeInput.value.trim()
  if (v && !profileForm.value.dislikes.includes(v)) {
    profileForm.value.dislikes.push(v)
  }
  dislikeInput.value = ''
}

const saveProfile = async () => {
  saving.value = true
  try {
    await API.post('/profile/', {
      user_id: userId.value,
      birthDate: profileForm.value.birthDate,
      gender: profileForm.value.gender,
      height: profileForm.value.height,
      weight: profileForm.value.weight,
      allergies: profileForm.value.allergies,
      dislikes: profileForm.value.dislikes
    })
    if (profileForm.value.name) {
      userName.value = profileForm.value.name
      localStorage.setItem('user_name', profileForm.value.name)
    }
    alert('保存成功！')
    showProfileModal.value = false
  } catch (e) { alert('保存失败') }
  finally { saving.value = false }
}

const logout = () => {
  localStorage.removeItem('user_id')
  localStorage.removeItem('user_name')
  showProfileModal.value = false
  router.push('/login')
}

watch(showProfileModal, (v) => { if (v) loadProfile() })

onMounted(() => {
  userId.value = localStorage.getItem('user_id') || ''
  userName.value = localStorage.getItem('user_name') || ''
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f6fa; }

#app { display: flex; min-height: 100vh; }
#app.no-sidebar { display: block; }

/* ========== 侧边栏 ========== */
.sidebar {
  width: 220px; background: #fff; border-right: 1px solid #e8ecf1;
  display: flex; flex-direction: column; position: fixed; top: 0; left: 0; bottom: 0; z-index: 100;
}
.sidebar-logo {
  padding: 24px 20px 20px; display: flex; align-items: center; gap: 10px;
  border-bottom: 1px solid #f0f2f5;
}
.logo-icon { font-size: 28px; }
.logo-text { font-size: 20px; font-weight: 700; color: #2d3436; }

.sidebar-nav { flex: 1; padding: 12px 10px; display: flex; flex-direction: column; gap: 4px; }
.nav-item {
  display: flex; align-items: center; gap: 12px; padding: 12px 16px;
  border-radius: 10px; text-decoration: none; color: #636e72;
  font-size: 15px; font-weight: 500; transition: all .2s;
}
.nav-item:hover { background: #f0f4f8; color: #2d3436; }
.nav-item.router-link-active { background: #e8f5e9; color: #27ae60; font-weight: 600; }
.nav-icon { font-size: 18px; width: 24px; text-align: center; }

.sidebar-bottom { padding: 16px; border-top: 1px solid #f0f2f5; }
.avatar-section {
  display: flex; align-items: center; gap: 12px; padding: 10px;
  border-radius: 10px; cursor: pointer; transition: .2s;
}
.avatar-section:hover { background: #f0f4f8; }
.avatar-circle {
  width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #43e97b, #38f9d7);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 16px;
}
.avatar-name { font-size: 14px; color: #636e72; font-weight: 500; }

/* ========== 主内容 ========== */
.main-content { margin-left: 220px; flex: 1; padding: 24px 32px; min-height: 100vh; }
.main-full { width: 100%; }

/* ========== 弹窗 ========== */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.4);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.profile-modal {
  background: #fff; width: 560px; max-height: 90vh; overflow-y: auto;
  border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.15);
}
.pm-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 20px 24px; border-bottom: 1px solid #f0f2f5;
}
.pm-header h3 { font-size: 18px; color: #2d3436; }
.close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #b2bec3; }
.close-btn:hover { color: #636e72; }

.pm-body { padding: 24px; }
.pm-avatar-row { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.pm-avatar-big {
  width: 56px; height: 56px; border-radius: 50%;
  background: linear-gradient(135deg, #43e97b, #38f9d7);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 24px; font-weight: 700;
}
.pm-name { font-size: 18px; font-weight: 600; color: #2d3436; }
.pm-id { font-size: 13px; color: #b2bec3; margin-top: 2px; }

.pm-form { display: flex; flex-direction: column; gap: 16px; }
.pm-row { display: flex; gap: 16px; }
.pm-field { flex: 1; display: flex; flex-direction: column; gap: 6px; }
.pm-field.full { width: 100%; }
.pm-field label { font-size: 13px; font-weight: 600; color: #636e72; }
.pm-field input, .pm-field select {
  padding: 10px 12px; border: 1px solid #dfe6e9; border-radius: 8px;
  font-size: 14px; outline: none; transition: .2s;
}
.pm-field input:focus, .pm-field select:focus { border-color: #27ae60; }

.tag-box {
  display: flex; flex-wrap: wrap; gap: 6px; padding: 8px;
  border: 1px solid #dfe6e9; border-radius: 8px; min-height: 40px; align-items: center;
}
.tag-box:focus-within { border-color: #27ae60; }
.tag {
  background: #e8f5e9; color: #27ae60; padding: 4px 10px; border-radius: 16px;
  font-size: 13px; display: flex; align-items: center; gap: 4px;
}
.tag-x { cursor: pointer; font-weight: 700; color: #e74c3c; }
.tag-input { border: none; outline: none; flex: 1; min-width: 80px; font-size: 14px; padding: 4px; }

.pm-actions { display: flex; gap: 12px; margin-top: 24px; }
.pm-save {
  flex: 1; padding: 12px; background: #27ae60; color: #fff;
  border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer;
}
.pm-save:hover { background: #219a52; }
.pm-save:disabled { background: #95a5a6; }
.pm-logout {
  padding: 12px 24px; background: #fff0f0; color: #e74c3c;
  border: 1px solid #ffdcdc; border-radius: 8px; font-weight: 600; cursor: pointer;
}
.pm-logout:hover { background: #e74c3c; color: #fff; }
</style>

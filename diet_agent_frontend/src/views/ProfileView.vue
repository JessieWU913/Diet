<template>
  <div class="profile-container">

    <transition name="toast-fade">
      <div v-if="showToast" class="toast" :class="messageType">
        {{ profileMessage }}
      </div>
    </transition>

    <div class="page-header">
      <h2>个人健康中心</h2>
      <p class="subtitle">完善您的健康画像，让 Agent 更懂你</p>
    </div>

    <div v-if="!isLoggedIn" class="card auth-card">
      <h3>{{ isLoginMode ? '用户登录' : '账号注册' }}</h3>

      <div class="form-group">
        <label>用户名</label>
        <input v-model="authForm.username" type="text" placeholder="请输入用户名" />
      </div>

      <div class="form-group">
        <label>密码</label>
        <input v-model="authForm.password" type="password" placeholder="请输入密码" @keyup.enter="handleAuth" />
      </div>

      <div class="action-buttons">
        <button class="primary-btn" @click="handleAuth" :disabled="isLoading">
          {{ isLoading ? '提交中...' : (isLoginMode ? '登 录' : '注 册') }}
        </button>
        <span class="toggle-link" @click="isLoginMode = !isLoginMode">
          {{ isLoginMode ? '没有账号？去注册' : '已有账号？去登录' }}
        </span>
      </div>
    </div>

    <div v-else class="card profile-card">
      <div class="profile-header">
        <div class="user-greeting">
          <div class="avatar-placeholder">{{ userName.charAt(0).toUpperCase() }}</div>
          <h3>您好，{{ userName }}</h3>
        </div>
        <button class="logout-btn" @click="handleLogout">退出登录</button>
      </div>

      <div class="form-group row">
        <div class="half">
          <label>性别</label>
          <select v-model="profileForm.gender">
            <option value="female">女</option>
            <option value="male">男</option>
          </select>
        </div>
      </div>

      <div class="form-group row">
        <div class="half">
          <label>身高 (cm)</label>
          <input v-model.number="profileForm.height" type="number" class="no-spin" placeholder="例: 165" />
        </div>
        <div class="half">
          <label>体重 (kg)</label>
          <input v-model.number="profileForm.weight" type="number" class="no-spin" placeholder="例: 55" />
        </div>
      </div>

      <div class="form-group">
        <label>过敏源 (Allergies)</label>
        <p class="hint">输入后按 <b>回车</b> 或 <b>空格</b> 生成标签</p>
        <div class="tags-input-container" @click="focusInput('allergiesInput')">
          <div class="tags-list">
            <span v-for="(tag, index) in profileForm.allergies" :key="'a'+index" class="tag">
              {{ tag }} <span class="remove-tag" @click.stop="removeTag('allergies', index)">×</span>
            </span>
          </div>
          <input
            ref="allergiesInput"
            type="text"
            v-model="tempInput.allergies"
            @keydown.enter.prevent="addTag('allergies')"
            @keydown.space.prevent="addTag('allergies')"
            placeholder="如：花生 (按回车添加)"
            class="tag-input-field"
          />
        </div>
      </div>

      <div class="form-group">
        <label>忌口/不喜欢 (Dislikes)</label>
        <p class="hint">输入后按 <b>回车</b> 或 <b>空格</b> 生成标签</p>
        <div class="tags-input-container" @click="focusInput('dislikesInput')">
          <div class="tags-list">
            <span v-for="(tag, index) in profileForm.dislikes" :key="'d'+index" class="tag">
              {{ tag }} <span class="remove-tag" @click.stop="removeTag('dislikes', index)">×</span>
            </span>
          </div>
          <input
            ref="dislikesInput"
            type="text"
            v-model="tempInput.dislikes"
            @keydown.enter.prevent="addTag('dislikes')"
            @keydown.space.prevent="addTag('dislikes')"
            placeholder="如：香菜, 鱼 (按回车添加)"
            class="tag-input-field"
          />
        </div>
      </div>

      <button class="primary-btn full-width" @click="saveProfile" :disabled="isLoading">
        {{ isLoading ? '保存中...' : '确认修改并同步至大模型' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'

const isLoggedIn = ref(false)
const isLoginMode = ref(true)
const isLoading = ref(false)
const userName = ref('')

// 🌟 新增：控制 Toast 弹窗的状态
const showToast = ref(false)
const profileMessage = ref('')
const messageType = ref('success') // 'success' 或 'error'

const allergiesInput = ref(null)
const dislikesInput = ref(null)

const authForm = reactive({ username: '', password: '' })
const profileForm = reactive({ gender: 'female', height: '', weight: '', allergies: [], dislikes: [] })
const tempInput = reactive({ allergies: '', dislikes: '' })

onMounted(async () => {
  const storedUserId = localStorage.getItem('user_id')
  const storedName = localStorage.getItem('user_name')
  if (storedUserId) {
    isLoggedIn.value = true
    userName.value = storedName || '用户'

    try {
      const res = await fetch(`http://127.0.0.1:8000/api/profile/?user_id=${storedUserId}`)
      const data = await res.json()
      if (res.ok && data.data) {
        // 将拉取到的数据填入表单
        profileForm.gender = data.data.gender || 'female'
        profileForm.height = data.data.height || ''
        profileForm.weight = data.data.weight || ''
        profileForm.allergies = data.data.allergies || []
        profileForm.dislikes = data.data.dislikes || []
      }
    } catch (e) {
      console.error("画像数据回显失败", e)
    }
  }
})

const triggerToast = (msg, type = 'success') => {
  profileMessage.value = msg
  messageType.value = type
  showToast.value = true
  // 3秒后自动消失
  setTimeout(() => {
    showToast.value = false
  }, 3000)
}

const focusInput = (refName) => {
  if (refName === 'allergiesInput' && allergiesInput.value) allergiesInput.value.focus()
  if (refName === 'dislikesInput' && dislikesInput.value) dislikesInput.value.focus()
}

const addTag = (field) => {
  const value = tempInput[field].trim()
  if (value && !profileForm[field].includes(value)) {
    profileForm[field].push(value)
  }
  tempInput[field] = ''
}

const removeTag = (field, index) => {
  profileForm[field].splice(index, 1)
}

const handleAuth = async () => {
  if (!authForm.username || !authForm.password) {
    triggerToast('用户名和密码不能为空', 'error')
    return
  }

  isLoading.value = true
  const action = isLoginMode.value ? 'login' : 'register'

  try {
    const response = await fetch('http://127.0.0.1:8000/api/auth/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: action, username: authForm.username, password: authForm.password })
    })
    const data = await response.json()

    if (response.ok) {
      localStorage.setItem('user_id', data.user_id)
      localStorage.setItem('user_name', authForm.username)
      isLoggedIn.value = true
      userName.value = authForm.username
      authForm.password = ''
      triggerToast(isLoginMode.value ? '登录成功！' : '注册成功！', 'success')
    } else {
      triggerToast(data.error || '操作失败', 'error')
    }
  } catch (error) {
    triggerToast('网络请求失败，请检查 Django 后端是否启动', 'error')
  } finally {
    isLoading.value = false
  }
}

const handleLogout = () => {
  localStorage.removeItem('user_id')
  localStorage.removeItem('user_name')
  isLoggedIn.value = false
  Object.assign(profileForm, { gender: 'female', height: '', weight: '', allergies: [], dislikes: [] })
  triggerToast('已退出登录', 'success')
}

const saveProfile = async () => {
  const userId = localStorage.getItem('user_id')
  if (!userId) {
    triggerToast('登录状态已失效，请重新登录', 'error')
    return
  }

  if (tempInput.allergies.trim()) addTag('allergies')
  if (tempInput.dislikes.trim()) addTag('dislikes')

  isLoading.value = true

  try {
    const response = await fetch('http://127.0.0.1:8000/api/profile/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        gender: profileForm.gender,
        height: profileForm.height || 0,
        weight: profileForm.weight || 0,
        allergies: profileForm.allergies,
        dislikes: profileForm.dislikes
      })
    })

    const data = await response.json()
    if (response.ok) {
      triggerToast('✨ 修改成功！健康画像已同步至知识图谱', 'success')
    } else {
      triggerToast(data.error || '保存失败', 'error')
    }
  } catch (error) {
    triggerToast('网络请求失败', 'error')
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
/* ===================================== */
/* 🌟 新增：Toast 悬浮提示框样式 */
/* ===================================== */
.toast {
  position: fixed;
  top: 30px;
  left: 50%;
  transform: translateX(-50%);
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: bold;
  font-size: 14px;
  color: white;
  z-index: 9999;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
}
.toast.success {
  background-color: #27ae60;
}
.toast.error {
  background-color: #e74c3c;
}

/* Toast 出现和消失的平滑动画 */
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.4s cubic-bezier(0.18, 0.89, 0.32, 1.28);
}
.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -30px);
}
/* ===================================== */

.profile-container { max-width: 550px; margin: 40px auto; padding: 0 20px 40px 20px; }
.page-header { text-align: center; margin-bottom: 30px; }
.page-header h2 { color: #2c3e50; margin: 0 0 8px 0; font-size: 24px; }
.subtitle { color: #7f8c8d; margin: 0; font-size: 14px; }
.card { background: #ffffff; border-radius: 12px; padding: 35px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06); }
.card h3 { margin-top: 0; color: #2c3e50; margin-bottom: 25px; font-size: 20px; }
.profile-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; padding-bottom: 20px; border-bottom: 1px solid #f0f2f5; }
.user-greeting { display: flex; align-items: center; gap: 12px; }
.user-greeting h3 { margin: 0; font-size: 18px; }
.avatar-placeholder { width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #42b983, #3aa876); color: white; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 18px; }
.form-group { margin-bottom: 20px; }
.form-group.row { display: flex; gap: 20px; }
.form-group.row .half { flex: 1; }
label { display: block; font-weight: 600; margin-bottom: 8px; color: #34495e; font-size: 14px; }
.hint { font-size: 12px; color: #95a5a6; margin-top: -4px; margin-bottom: 8px; }
input[type="text"], input[type="password"], input[type="number"], select { width: 100%; padding: 12px 15px; border: 1px solid #dfe6e9; border-radius: 8px; box-sizing: border-box; font-size: 14px; transition: all 0.2s; background-color: #fcfcfc; }
.no-spin::-webkit-inner-spin-button, .no-spin::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.no-spin { -moz-appearance: textfield; }
input:focus, select:focus { outline: none; border-color: #42b983; background-color: #ffffff; box-shadow: 0 0 0 3px rgba(66, 185, 131, 0.1); }
.tags-input-container { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid #dfe6e9; border-radius: 8px; background-color: #fcfcfc; transition: all 0.2s; cursor: text; }
.tags-input-container:focus-within { border-color: #42b983; box-shadow: 0 0 0 3px rgba(66, 185, 131, 0.1); background-color: #ffffff; }
.tags-list { display: flex; flex-wrap: wrap; gap: 8px; }
.tag { background-color: #ebf7f1; color: #27ae60; padding: 5px 12px; border-radius: 16px; font-size: 13px; display: flex; align-items: center; gap: 6px; }
.remove-tag { cursor: pointer; font-weight: bold; opacity: 0.6; font-size: 14px; }
.remove-tag:hover { opacity: 1; }
.tag-input-field { border: none !important; outline: none !important; background: transparent !important; padding: 4px 0 !important; font-size: 14px !important; width: 100% !important; box-shadow: none !important; }
.action-buttons { display: flex; justify-content: space-between; align-items: center; margin-top: 30px; }
.primary-btn { background-color: #42b983; color: white; border: none; padding: 12px 28px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 15px; transition: all 0.2s; }
.primary-btn:hover:not(:disabled) { background-color: #3aa876; transform: translateY(-1px); }
.primary-btn:disabled { background-color: #bdc3c7; cursor: not-allowed; }
.primary-btn.full-width { width: 100%; margin-top: 15px; }
.logout-btn { background: none; border: 1px solid #e74c3c; color: #e74c3c; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s; }
.logout-btn:hover { background: #e74c3c; color: white; }
.toggle-link { color: #42b983; cursor: pointer; font-size: 14px; transition: color 0.2s; }
.toggle-link:hover { color: #2c3e50; text-decoration: underline; }
</style>

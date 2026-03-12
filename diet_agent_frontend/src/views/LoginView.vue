<template>
  <div class="auth-container">
    <div class="auth-card">
      <h2 class="auth-title">{{ isLoginMode ? '欢迎回来' : '创建新账号' }}</h2>

      <form @submit.prevent="handleSubmit" class="auth-form">
        <div class="form-group">
          <label>账号 (User ID)</label>
          <input
            type="text"
            v-model="userId"
            placeholder="请输入账号"
            required
            class="form-control"
          />
        </div>

        <div v-if="!isLoginMode" class="form-group">
          <label>昵称 (可选)</label>
          <input
            type="text"
            v-model="userName"
            placeholder="怎么称呼您？"
            class="form-control"
          />
        </div>

        <div class="form-group">
          <label>密码</label>
          <input
            type="password"
            v-model="password"
            placeholder="请输入密码"
            required
            class="form-control"
          />
        </div>

        <div v-if="!isLoginMode" class="form-group">
          <label>确认密码</label>
          <input
            type="password"
            v-model="confirmPassword"
            placeholder="请再次输入密码"
            required
            class="form-control"
          />
        </div>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '处理中...' : (isLoginMode ? '立即登录' : '注册账号') }}
        </button>
      </form>

      <div class="auth-switch">
        <span>{{ isLoginMode ? '还没有账号？' : '已有账号？' }}</span>
        <a href="#" @click.prevent="toggleMode">
          {{ isLoginMode ? '立即注册' : '直接登录' }}
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const isLoginMode = ref(true)
const userId = ref('')
const password = ref('')
const confirmPassword = ref('')
const userName = ref('')
const loading = ref(false)

const toggleMode = () => {
  isLoginMode.value = !isLoginMode.value
  userId.value = ''
  password.value = ''
  confirmPassword.value = ''
  userName.value = ''
}

const handleSubmit = async () => {
  const cleanUserId = userId.value.trim()
  const cleanPassword = password.value.trim()
  const cleanConfirm = confirmPassword.value.trim()
  const cleanName = userName.value.trim()

  if (!cleanUserId || !cleanPassword) {
    alert('账号和密码不能为空！')
    return
  }

  if (!isLoginMode.value && cleanPassword !== cleanConfirm) {
    alert('两次输入的密码不一致，请重新输入！')
    return
  }

  loading.value = true
  try {
    const response = await axios.post('http://127.0.0.1:8000/api/auth/', {
      user_id: cleanUserId,
      password: cleanPassword,
      name: cleanName,
      action: isLoginMode.value ? 'login' : 'register'
    })

    if (response.data.status === 'success') {
      if (isLoginMode.value) {
        localStorage.setItem('user_id', cleanUserId)
        router.push('/chat')
      } else {
        alert('注册成功，请登录！')
        isLoginMode.value = true
        password.value = ''
        confirmPassword.value = ''
      }
    } else {
      alert(response.data.error || '操作失败')
    }
  } catch (error) {
    console.error(error)
    alert(error.response?.data?.error || '网络请求失败，请检查密码是否正确')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  background: linear-gradient(135deg, #2d2346 0%, #7761e5 100%); display: flex; justify-content: center; align-items: center; z-index: 9999;
}
.auth-card {
  background: white; width: 100%; max-width: 400px; padding: 40px; border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2); text-align: center;
}
.auth-title { margin-top: 0; margin-bottom: 30px; color: #2d2346; font-size: 24px; }
.form-group { text-align: left; margin-bottom: 15px; }
.form-group label { display: block; margin-bottom: 8px; font-weight: bold; color: #34495e; font-size: 14px; }
.form-control { width: 100%; padding: 12px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 15px; box-sizing: border-box; outline: none; transition: border 0.2s; }
.form-control:focus { border-color: #7761e5; }
.submit-btn { width: 100%; background: #7761e5; color: white; border: none; padding: 14px; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: background 0.2s; margin-top: 10px; }
.submit-btn:hover:not(:disabled) { background: #6350d0; }
.submit-btn:disabled { background: #95a5a6; cursor: not-allowed; }
.auth-switch { margin-top: 20px; font-size: 14px; color: #7f8c8d; }
.auth-switch a { color: #7761e5; text-decoration: none; font-weight: bold; margin-left: 5px; }
.auth-switch a:hover { text-decoration: underline; }
</style>

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
            placeholder="请输入您的专属ID"
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

// 核心状态控制
const isLoginMode = ref(true)
const userId = ref('')
const userName = ref('')
const loading = ref(false)

const toggleMode = () => {
  isLoginMode.value = !isLoginMode.value
  userId.value = '' // 切换时清空输入框
  userName.value = ''
}

const handleSubmit = async () => {
  if (!userId.value.trim()) {
    alert('账号不能为空！')
    return
  }

  loading.value = true
  try {
    // 假设你的后端接口是 /api/auth/，用 action 区分登录还是注册
    const response = await axios.post('http://127.0.0.1:8000/api/auth/', {
      user_id: userId.value,
      name: userName.value,
      action: isLoginMode.value ? 'login' : 'register'
    })

    if (response.data.status === 'success') {
      if (isLoginMode.value) {
        // 🌟 解决痛点 1：登录成功后，存入本地并强制跳转到主界面 (如 /chat)
        localStorage.setItem('user_id', userId.value)
        alert('登录成功！')
        router.push('/chat')
      } else {
        // 🌟 解决痛点 2：注册成功后，不乱跳，而是切换回登录模式
        alert('注册成功，请登录！')
        isLoginMode.value = true
      }
    } else {
      alert(response.data.error || '操作失败')
    }
  } catch (error) {
    console.error(error)
    alert(error.response?.data?.error || '网络请求失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 充满全屏的背景，盖住原来的布局 */
.auth-container {
  position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
  background: #f4f7f6; display: flex; justify-content: center; align-items: center; z-index: 9999;
}
.auth-card {
  background: white; width: 100%; max-width: 400px; padding: 40px; border-radius: 16px;
  box-shadow: 0 10px 25px rgba(0,0,0,0.05); text-align: center;
}
.auth-title { margin-top: 0; margin-bottom: 30px; color: #2c3e50; font-size: 24px; }
.form-group { text-align: left; margin-bottom: 20px; }
.form-group label { display: block; margin-bottom: 8px; font-weight: bold; color: #34495e; font-size: 14px; }
.form-control { width: 100%; padding: 12px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 15px; box-sizing: border-box; outline: none; transition: border 0.2s; }
.form-control:focus { border-color: #42b983; }
.submit-btn { width: 100%; background: #42b983; color: white; border: none; padding: 14px; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: background 0.2s; margin-top: 10px; }
.submit-btn:hover:not(:disabled) { background: #369f6e; }
.submit-btn:disabled { background: #95a5a6; cursor: not-allowed; }
.auth-switch { margin-top: 20px; font-size: 14px; color: #7f8c8d; }
.auth-switch a { color: #3498db; text-decoration: none; font-weight: bold; margin-left: 5px; }
.auth-switch a:hover { text-decoration: underline; }
</style>

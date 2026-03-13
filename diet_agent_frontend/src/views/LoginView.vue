<template>
  <div class="auth-container">
    <div class="auth-card">
      <h2 class="auth-title">{{ isLoginMode ? '欢迎回来' : '创建新账号' }}</h2>

      <div class="login-type-switch">
        <button :class="['type-btn', { active: !isAdminMode }]" @click="switchAdminMode(false)">用户</button>
        <button :class="['type-btn', { active: isAdminMode }]" @click="switchAdminMode(true)">管理员</button>
      </div>

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

        <div v-if="!isLoginMode && !isAdminMode" class="form-group">
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
          <div class="password-wrap">
            <input
              :type="showPassword ? 'text' : 'password'"
              v-model="password"
              placeholder="请输入密码"
              required
              class="form-control"
            />
            <button type="button" class="eye-btn" @click="showPassword = !showPassword">
              <svg v-if="showPassword" viewBox="0 0 24 24" aria-hidden="true" class="eye-icon">
                <path d="M3 3l18 18" />
                <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                <path d="M9.9 4.2A10.9 10.9 0 0 1 12 4c5.2 0 9.3 3.1 11 8-0.5 1.5-1.3 2.9-2.4 4" />
                <path d="M6.2 6.2A12.3 12.3 0 0 0 1 12c1.7 4.9 5.8 8 11 8 1.7 0 3.2-.3 4.6-.9" />
              </svg>
              <svg v-else viewBox="0 0 24 24" aria-hidden="true" class="eye-icon">
                <path d="M1 12c1.7-4.9 5.8-8 11-8s9.3 3.1 11 8c-1.7 4.9-5.8 8-11 8s-9.3-3.1-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          </div>
        </div>

        <div v-if="!isLoginMode && !isAdminMode" class="form-group">
          <label>确认密码</label>
          <div class="password-wrap">
            <input
              :type="showConfirmPassword ? 'text' : 'password'"
              v-model="confirmPassword"
              placeholder="请再次输入密码"
              required
              class="form-control"
            />
            <button type="button" class="eye-btn" @click="showConfirmPassword = !showConfirmPassword">
              <svg v-if="showConfirmPassword" viewBox="0 0 24 24" aria-hidden="true" class="eye-icon">
                <path d="M3 3l18 18" />
                <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                <path d="M9.9 4.2A10.9 10.9 0 0 1 12 4c5.2 0 9.3 3.1 11 8-0.5 1.5-1.3 2.9-2.4 4" />
                <path d="M6.2 6.2A12.3 12.3 0 0 0 1 12c1.7 4.9 5.8 8 11 8 1.7 0 3.2-.3 4.6-.9" />
              </svg>
              <svg v-else viewBox="0 0 24 24" aria-hidden="true" class="eye-icon">
                <path d="M1 12c1.7-4.9 5.8-8 11-8s9.3 3.1 11 8c-1.7 4.9-5.8 8-11 8s-9.3-3.1-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            </button>
          </div>
        </div>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '处理中...' : (isAdminMode ? '管理员登录' : (isLoginMode ? '立即登录' : '注册账号')) }}
        </button>
      </form>

      <div class="auth-switch" v-if="!isAdminMode">
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
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const isAdminMode = ref(false)

const switchAdminMode = (enabled) => {
  isAdminMode.value = enabled
  isLoginMode.value = true
  userId.value = ''
  password.value = ''
  confirmPassword.value = ''
  userName.value = ''
}

const toggleMode = () => {
  isLoginMode.value = !isLoginMode.value
  userId.value = ''
  password.value = ''
  confirmPassword.value = ''
  userName.value = ''
  showPassword.value = false
  showConfirmPassword.value = false
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
    if (isAdminMode.value) {
      const adminRes = await axios.post('http://127.0.0.1:8000/api/admin/auth/', {
        admin_id: cleanUserId,
        password: cleanPassword
      })
      if (adminRes.data.status === 'success') {
        localStorage.setItem('is_admin', '1')
        localStorage.setItem('admin_token', adminRes.data.token)
        localStorage.setItem('user_name', '管理员')
        localStorage.removeItem('user_id')
        router.push('/admin')
        return
      }
      alert(adminRes.data.error || '管理员登录失败')
      return
    }

    const response = await axios.post('http://127.0.0.1:8000/api/auth/', {
      user_id: cleanUserId,
      password: cleanPassword,
      name: cleanName,
      action: isLoginMode.value ? 'login' : 'register'
    })

    if (response.data.status === 'success') {
      if (isLoginMode.value) {
        localStorage.removeItem('is_admin')
        localStorage.removeItem('admin_token')
        localStorage.setItem('user_id', cleanUserId)
        localStorage.setItem('user_name', response.data.user_name || cleanUserId)
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
.login-type-switch {
  margin: -10px auto 20px;
  background: #f2f5fb;
  border-radius: 999px;
  padding: 4px;
  width: 220px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
}
.type-btn {
  border: none;
  border-radius: 999px;
  padding: 8px 10px;
  background: transparent;
  cursor: pointer;
  color: #62717f;
  font-weight: 700;
}
.type-btn.active {
  background: #7761e5;
  color: #fff;
}
.form-group { text-align: left; margin-bottom: 15px; }
.form-group label { display: block; margin-bottom: 8px; font-weight: bold; color: #34495e; font-size: 14px; }
.form-control { width: 100%; padding: 12px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 15px; box-sizing: border-box; outline: none; transition: border 0.2s; }
.form-control:focus { border-color: #7761e5; }
.password-wrap { position: relative; }
.password-wrap .form-control { padding-right: 42px; }
.eye-btn {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  border: none; background: transparent; cursor: pointer; line-height: 1;
  color: #6c7a89; padding: 2px 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.eye-icon {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.submit-btn { width: 100%; background: #7761e5; color: white; border: none; padding: 14px; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: background 0.2s; margin-top: 10px; }
.submit-btn:hover:not(:disabled) { background: #6350d0; }
.submit-btn:disabled { background: #95a5a6; cursor: not-allowed; }
.auth-switch { margin-top: 20px; font-size: 14px; color: #7f8c8d; }
.auth-switch a { color: #7761e5; text-decoration: none; font-weight: bold; margin-left: 5px; }
.auth-switch a:hover { text-decoration: underline; }
</style>

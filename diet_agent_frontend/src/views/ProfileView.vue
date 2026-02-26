<script setup>
import { reactive, computed, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

// 初始化表单，匹配你的基础数据
const form = reactive({
  user_id: 'xiaowu_001', // 模拟当前登录用户
  name: '小吴',
  gender: 'female',
  birthday: '2004-10-26',
  height: 165,
  weight: 52,
  allergies: [],
  dislikes: []
})

// 自动计算年龄
const age = computed(() => {
  if (!form.birthday) return 0
  return new Date().getFullYear() - new Date(form.birthday).getFullYear()
})

// 页面加载时从后端拉取数据
onMounted(async () => {
  try {
    const res = await axios.get(`http://127.0.0.1:8000/api/profile/?user_id=${form.user_id}`)
    if (res.data.status === 'success' && res.data.data) {
      Object.assign(form, res.data.data) // 将后端数据合并到表单
    }
  } catch (error) {
    console.error("无法加载用户数据", error)
  }
})

// 点击保存提交到后端
const saveProfile = async () => {
  try {
    const res = await axios.post('http://127.0.0.1:8000/api/profile/', form)
    if (res.data.status === 'success') {
      ElMessage.success('个人资料已同步至 AI 记忆库！')
    }
  } catch (error) {
    ElMessage.error('保存失败')
  }
}
</script>

<template>
  <div class="profile-container">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: bold; color: #03bdac;">👤 个人资料设置</span>
          <el-button type="primary" color="#03bdac" @click="saveProfile">保存修改</el-button>
        </div>
      </template>

      <el-form :model="form" label-width="120px">
        <el-row :gutter="40">
          <el-col :span="12">
            <el-form-item label="昵称"><el-input v-model="form.name" /></el-form-item>
            <el-form-item label="性别">
              <el-radio-group v-model="form.gender">
                <el-radio label="female">女</el-radio>
                <el-radio label="male">男</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="出生日期">
              <el-date-picker v-model="form.birthday" type="date" value-format="YYYY-MM-DD" />
              <span style="margin-left: 10px; color: #999;">({{ age }}岁)</span>
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="身高 (cm)"><el-input-number v-model="form.height" :min="100" :max="250"/></el-form-item>
            <el-form-item label="体重 (kg)"><el-input-number v-model="form.weight" :min="30" :max="200"/></el-form-item>
            <el-divider content-position="left">图谱偏好设定</el-divider>
            <el-form-item label="食材过敏">
              <el-select v-model="form.allergies" multiple filterable allow-create placeholder="如：花生、海鲜"></el-select>
            </el-form-item>
            <el-form-item label="忌口">
              <el-select v-model="form.dislikes" multiple filterable allow-create placeholder="如：香菜、内脏"></el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.profile-container { padding: 40px; max-width: 900px; margin: 0 auto; }
</style>

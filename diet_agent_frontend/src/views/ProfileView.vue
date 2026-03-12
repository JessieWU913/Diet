<template>
  <div class="profile-container">
    <div class="profile-card">
      <h2>个人健康中心</h2>
      <p class="subtitle">完善健康画像，让 Agent 更精准</p>

      <form @submit.prevent="saveProfile" class="profile-form">
        <div class="form-row">
          <div class="form-group">
            <label>出生日期</label>
            <input type="date" v-model="profile.birthDate" class="form-control" required />
          </div>
          <div class="form-group">
            <label>性别</label>
            <select v-model="profile.gender" class="form-control">
              <option value="male">男</option>
              <option value="female">女</option>
            </select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label>身高 (cm)</label>
            <input type="tel" v-model.number="profile.height" class="form-control" placeholder="例如: 175" required />
          </div>
          <div class="form-group">
            <label>体重 (kg)</label>
            <input type="tel" v-model.number="profile.weight" class="form-control" placeholder="例如: 65" required />
          </div>
        </div>

        <div class="form-group full-width">
          <label>明确过敏源 (输入后按回车添加)</label>
          <div class="tag-input-box">
            <span class="tag" v-for="(tag, index) in allergies" :key="index">
              {{ tag }} <span class="remove-tag" @click="removeAllergy(index)">×</span>
            </span>
            <input type="text" v-model="currentAllergy" @keyup.enter.prevent="addAllergy" placeholder="输入过敏源..." class="tag-input"/>
          </div>
        </div>

        <div class="form-group full-width">
          <label>不喜欢的食材 (输入后按回车添加)</label>
          <div class="tag-input-box">
            <span class="tag" v-for="(tag, index) in dislikes" :key="index">
              {{ tag }} <span class="remove-tag" @click="removeDislike(index)">×</span>
            </span>
            <input type="text" v-model="currentDislike" @keyup.enter.prevent="addDislike" placeholder="输入忌口..." class="tag-input"/>
          </div>
        </div>

        <button type="submit" class="save-btn" :disabled="loading">
          {{ loading ? '图谱写入中...' : '保存健康档案' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const userId = localStorage.getItem('user_id')
const loading = ref(false)

const profile = reactive({ birthDate: '', gender: 'female', height: '', weight: '' })

const allergies = ref([])
const currentAllergy = ref('')
const dislikes = ref([])
const currentDislike = ref('')

const addAllergy = () => { if(currentAllergy.value.trim()){ allergies.value.push(currentAllergy.value.trim()); currentAllergy.value = ''; } }
const removeAllergy = (index) => { allergies.value.splice(index, 1) }

const addDislike = () => { if(currentDislike.value.trim()){ dislikes.value.push(currentDislike.value.trim()); currentDislike.value = ''; } }
const removeDislike = (index) => { dislikes.value.splice(index, 1) }

onMounted(async () => {
  if (!userId) return
  try {
    const res = await axios.get(`http://127.0.0.1:8000/api/profile/?user_id=${userId}`)
    if (res.data) {
      profile.birthDate = res.data.birthDate || ''
      profile.gender = res.data.gender || 'female'
      profile.height = res.data.height || ''
      profile.weight = res.data.weight || ''
      allergies.value = res.data.allergies || []
      dislikes.value = res.data.dislikes || []
    }
  } catch (e) { console.error("提取画像失败", e) }
})

const saveProfile = async () => {
  loading.value = true
  try {
    await axios.post('http://127.0.0.1:8000/api/profile/', {
      user_id: userId, birthDate: profile.birthDate, gender: profile.gender,
      height: profile.height, weight: profile.weight,
      allergies: allergies.value, dislikes: dislikes.value
    })
    alert('保存成功！')
  } catch (e) { alert('保存失败，请检查网络') }
  finally { loading.value = false }
}
</script>

<style scoped>
.profile-container { padding: 20px; display: flex; justify-content: center; }
.profile-card { background: white; width: 100%; max-width: 600px; padding: 40px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); }
h2 { margin-top: 0; color: #2c3e50; text-align: center; }
.subtitle { text-align: center; color: #7f8c8d; margin-bottom: 30px; }
.form-row { display: flex; gap: 20px; margin-bottom: 20px; }
.form-group { flex: 1; text-align: left; }
.form-group.full-width { margin-bottom: 20px; }
.form-group label { display: block; margin-bottom: 8px; font-weight: bold; color: #34495e; font-size: 14px; }
.form-control { width: 100%; padding: 12px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 15px; box-sizing: border-box; outline: none; transition: 0.2s; }
.form-control:focus { border-color: #42b983; }

.tag-input-box { display: flex; flex-wrap: wrap; gap: 8px; padding: 8px; border: 1px solid #dfe6e9; border-radius: 8px; min-height: 45px; align-items: center; }
.tag-input-box:focus-within { border-color: #42b983; }
.tag { background: #e8f5e9; color: #2ecc71; padding: 5px 10px; border-radius: 20px; font-size: 14px; display: flex; align-items: center; gap: 5px; }
.remove-tag { cursor: pointer; font-weight: bold; color: #e74c3c; }
.tag-input { border: none; outline: none; flex: 1; min-width: 100px; font-size: 15px; padding: 4px; }

.save-btn { width: 100%; background: #42b983; color: white; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: 0.2s; margin-top: 10px; }
.save-btn:hover { background: #369f6e; }
</style>

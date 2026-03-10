<template>
  <div class="history-container">
    <h2>📖 我的饮食档案</h2>

    <div v-if="loading" class="loading">正在翻阅图谱记忆...</div>

    <div v-else-if="historyList.length === 0" class="empty">
      近期还没有保存过饮食排期哦，快去让 Agent 帮你安排吧！
    </div>

    <div class="timeline" v-else>
      <div v-for="(record, index) in historyList" :key="index" class="timeline-item">
        <div class="time-dot"></div>
        <div class="record-content">
          <h4>{{ parseDate(record) }}</h4>
          <p>{{ parseRecipes(record) }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const historyList = ref([])
const loading = ref(true)
const userId = localStorage.getItem('user_id') || 'guest'

onMounted(async () => {
  try {
    const res = await axios.get(`http://127.0.0.1:8000/api/meal-event/?user_id=${userId}`)
    historyList.value = res.data.history
  } catch (err) {
    console.error("提取历史失败", err)
  } finally {
    loading.value = false
  }
})

// 简单处理一下后端传来的字符串格式
const parseDate = (str) => {
  try {
    return str?.split('安排了:')[0]?.trim() || '未知日期'
  } catch { return '未知日期' }
}
const parseRecipes = (str) => {
  try {
    return str?.split('安排了:')[1]?.trim() || '无记录'
  } catch { return '无记录' }
}
</script>

<style scoped>
/* 这里你可以发挥你的 CSS 天赋，画一个漂亮的左侧竖线时间轴样式 */
.timeline { border-left: 2px solid #42b983; padding-left: 20px; margin-top: 20px; }
.timeline-item { position: relative; margin-bottom: 20px; }
.time-dot { position: absolute; left: -26px; top: 0; width: 10px; height: 10px; border-radius: 50%; background: #42b983; border: 2px solid white; box-shadow: 0 0 0 2px #42b983; }
.record-content h4 { margin: 0; color: #34495e; }
.record-content p { color: #7f8c8d; margin-top: 5px; background: #f8f9fa; padding: 10px; border-radius: 8px; }
</style>

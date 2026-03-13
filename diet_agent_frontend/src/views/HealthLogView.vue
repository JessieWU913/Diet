<template>
  <div class="health-log-view">
    <div class="page-header">
      <h2>健康日志</h2>
      <div class="date-nav">
        <button @click="prevMonth">◀</button>
        <span>{{ currentMonth }}</span>
        <button @click="nextMonth">▶</button>
      </div>
    </div>

    <div class="health-content">
    <div v-if="loading" class="loading-state">正在翻阅图谱记忆...</div>

    <div v-else-if="allLogs.length === 0" class="empty-state">
      <p>还没有饮食记录哦</p>
      <p>去「饮食记录」或「AI助手」页面开始记录吧！</p>
    </div>

    <div v-else class="log-timeline">
      <div v-for="group in groupedLogs" :key="group.date" class="day-group">
        <div class="day-header">
          <div class="day-dot"></div>
          <span class="day-date">{{ formatDate(group.date) }}</span>
          <span class="day-cal">共 {{ group.totalCalories }} kcal</span>
        </div>

        <div class="day-content">
          <!-- 饮食记录 -->
          <div v-if="group.dietLogs.length > 0" class="section-block">
            <div v-for="log in group.dietLogs" :key="log.id" class="log-item">
              <span class="li-icon">{{ mealIcon(log.meal_type) }}</span>
              <span class="li-name">{{ log.food_name }}</span>
              <span class="li-cal">{{ log.calories }} kcal</span>
              <span class="li-macros">P{{ log.protein }}g · F{{ log.fat }}g · C{{ log.carbs }}g</span>
            </div>
          </div>

          <!-- 事件记录 -->
          <div v-if="group.events.length > 0" class="section-block events-block">
            <div v-for="evt in group.events" :key="evt" class="event-item">
              <span class="ei-icon"></span>
              <span class="ei-text">{{ evt }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史对话记录 -->
    <div class="chat-history-section">
      <h3>历史对话记录</h3>
      <div v-if="chatSessions.length === 0" class="ch-empty">暂无对话记录</div>
      <div v-for="session in chatSessions" :key="session.session_id" class="ch-card">
        <div class="ch-header" @click="toggleSession(session)">
          <span class="ch-title">{{ session.title || '对话' }}</span>
          <span class="ch-date">{{ session.created_at ? session.created_at.slice(0, 16) : '' }}</span>
          <span class="ch-arrow">{{ session.expanded ? '▾' : '▸' }}</span>
        </div>
        <div v-if="session.expanded" class="ch-messages">
          <div v-for="(msg, mIdx) in (session.msgs || [])" :key="mIdx" :class="['ch-msg', msg.role === 'user' ? 'ch-user' : 'ch-ai']">
            <span class="ch-role">{{ msg.role === 'user' ? '我' : 'AI' }}</span>
            <span class="ch-text">{{ msg.content?.slice(0, 200) }}{{ msg.content?.length > 200 ? '...' : '' }}</span>
          </div>
        </div>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import API from '../api.js'

const userId = localStorage.getItem('user_id') || ''
const loading = ref(true)
const dietLogs = ref([])
const mealEvents = ref([])
const monthOffset = ref(0)

const currentMonth = computed(() => {
  const d = new Date()
  d.setMonth(d.getMonth() + monthOffset.value)
  return `${d.getFullYear()}年${d.getMonth() + 1}月`
})

const prevMonth = () => { monthOffset.value--; loadData() }
const nextMonth = () => { monthOffset.value++; loadData() }

const loadData = async () => {
  loading.value = true
  try {
    const d = new Date()
    d.setMonth(d.getMonth() + monthOffset.value)
    const year = d.getFullYear()
    const month = d.getMonth()
    const startDate = new Date(year, month, 1).toISOString().split('T')[0]
    const endDate = new Date(year, month + 1, 0).toISOString().split('T')[0]

    const [dietRes, eventRes] = await Promise.all([
      API.get(`/diet-log/?user_id=${userId}&start_date=${startDate}&end_date=${endDate}`),
      API.get(`/meal-event/?user_id=${userId}`).catch(() => ({ data: { history: [] } }))
    ])
    dietLogs.value = dietRes.data.logs || []
    mealEvents.value = eventRes.data.history || []
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const allLogs = computed(() => [...dietLogs.value, ...mealEvents.value])

const groupedLogs = computed(() => {
  const groups = {}

  for (const log of dietLogs.value) {
    const date = log.date || '未知日期'
    if (!groups[date]) groups[date] = { date, dietLogs: [], events: [], totalCalories: 0 }
    groups[date].dietLogs.push(log)
    groups[date].totalCalories += log.calories || 0
  }

  for (const evt of mealEvents.value) {
    const datePart = evt?.split('安排了:')[0]?.trim() || ''
    // 尝试提取日期
    const dateMatch = datePart.match(/\d{4}-\d{2}-\d{2}/)
    const date = dateMatch ? dateMatch[0] : datePart
    if (date) {
      if (!groups[date]) groups[date] = { date, dietLogs: [], events: [], totalCalories: 0 }
      groups[date].events.push(evt)
    }
  }

  return Object.values(groups).sort((a, b) => b.date.localeCompare(a.date))
})

const formatDate = (dateStr) => {
  try {
    const d = new Date(dateStr + 'T00:00:00')
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return `${d.getMonth() + 1}月${d.getDate()}日 ${weekdays[d.getDay()]}`
  } catch { return dateStr }
}

const mealIcon = (type) => {
  const icons = { breakfast: '', lunch: '', dinner: '', snack: '' }
  return icons[type] || ''
}

// 历史对话
const chatSessions = ref([])

const loadChatHistory = async () => {
  if (!userId) return
  try {
    const res = await API.get(`/chat-history/?user_id=${userId}`)
    const sessions = (res.data.sessions || []).map(s => ({ ...s, expanded: false }))
    sessions.sort((a, b) => {
      const ta = new Date(a.created_at || 0).getTime()
      const tb = new Date(b.created_at || 0).getTime()
      return ta - tb
    })
    chatSessions.value = sessions
  } catch (e) { console.error(e) }
}

const toggleSession = (session) => {
  session.expanded = !session.expanded
}

onMounted(() => {
  loadData()
  loadChatHistory()
})
</script>

<style scoped>
.health-log-view { width: 100%; }
.health-content { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; align-items: start; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h2 { font-size: 22px; color: #2d3436; }
.date-nav { display: flex; align-items: center; gap: 12px; }
.date-nav button { background: #fff; border: 1px solid #dfe6e9; border-radius: 8px; padding: 6px 12px; cursor: pointer; font-size: 14px; }
.date-nav button:hover { background: #f0f2f5; }
.date-nav span { font-size: 15px; font-weight: 600; color: #2d3436; min-width: 100px; text-align: center; }

.loading-state, .empty-state { text-align: center; padding: 60px 20px; color: #636e72; }
.empty-state p:first-child { font-size: 18px; margin-bottom: 8px; }
.empty-state p:last-child { font-size: 14px; color: #b2bec3; }

/* 时间线 */
.log-timeline { position: relative; padding-left: 24px; }
.log-timeline::before { content: ''; position: absolute; left: 8px; top: 0; bottom: 0; width: 2px; background: #e0e4e8; }

.day-group { margin-bottom: 28px; }
.day-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; position: relative; }
.day-dot { position: absolute; left: -20px; width: 12px; height: 12px; border-radius: 50%; background: #7761e5; border: 3px solid #fff; box-shadow: 0 0 0 2px #7761e5; }
.day-date { font-size: 15px; font-weight: 700; color: #2d3436; }
.day-cal { font-size: 13px; color: #636e72; background: #f0f2f5; padding: 2px 10px; border-radius: 10px; }

.day-content { margin-left: 4px; }
.section-block { background: #fff; border-radius: 12px; padding: 14px 18px; box-shadow: 0 2px 8px rgba(0,0,0,.04); margin-bottom: 10px; }

.log-item { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid #f8f9fa; }
.log-item:last-child { border-bottom: none; }
.li-icon { font-size: 18px; }
.li-name { flex: 1; font-weight: 500; color: #2d3436; font-size: 14px; }
.li-cal { font-size: 13px; color: #636e72; font-weight: 600; min-width: 70px; text-align: right; }
.li-macros { font-size: 11px; color: #b2bec3; min-width: 140px; text-align: right; }

.events-block { background: #fef9e7; border: 1px solid #f6c342; }
.event-item { display: flex; align-items: flex-start; gap: 8px; padding: 6px 0; font-size: 13px; color: #636e72; line-height: 1.5; }
.ei-icon { font-size: 14px; flex-shrink: 0; margin-top: 2px; }

/* 历史对话 */
.chat-history-section { margin-top: 0; }
.chat-history-section h3 { font-size: 18px; color: #2d3436; margin-bottom: 16px; }
.ch-empty { color: #b2bec3; font-size: 14px; text-align: center; padding: 20px; }
.ch-card { background: #fff; border-radius: 12px; margin-bottom: 10px; box-shadow: 0 2px 8px rgba(0,0,0,.04); overflow: hidden; }
.ch-header { display: flex; align-items: center; gap: 10px; padding: 14px 18px; cursor: pointer; transition: .15s; }
.ch-header:hover { background: #f8f9fa; }
.ch-title { flex: 1; font-weight: 600; color: #2d3436; font-size: 14px; }
.ch-date { font-size: 12px; color: #b2bec3; }
.ch-arrow { color: #b2bec3; font-size: 12px; }
.ch-messages { padding: 0 18px 14px; border-top: 1px solid #f0f2f5; }
.ch-msg { display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f8f9fa; align-items: flex-start; }
.ch-msg:last-child { border-bottom: none; }
.ch-role { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 10px; flex-shrink: 0; }
.ch-user .ch-role { background: #ede9fc; color: #7761e5; }
.ch-ai .ch-role { background: #e3f5e8; color: #4aa458; }
.ch-text { font-size: 13px; color: #636e72; line-height: 1.5; }
</style>

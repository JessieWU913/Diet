<template>
  <div class="chat-view">
    <!-- 左侧：个性化推荐面板 -->
    <aside class="side-panel">
      <h3>🎯 个性化偏好</h3>

      <!-- 模式切换 -->
      <div class="mode-block">
        <label class="mode-toggle" @click="toggleMode">
          <span class="mode-dot" :class="{ active: isWeightLossMode }"></span>
          <span>{{ isWeightLossMode ? '🔥 减脂模式' : '🍽️ 标准模式' }}</span>
        </label>
      </div>

      <!-- 偏好食材 -->
      <div class="fav-section">
        <h4>💚 偏好食材 <span class="fav-hint">(会自动融入对话)</span></h4>
        <div class="tag-cloud">
          <span v-for="tag in favorites" :key="tag" class="fav-tag">
            {{ tag }}
            <button class="tag-del" @click="removeFavorite(tag)">×</button>
          </span>
        </div>
        <div class="add-row">
          <input v-model="newFav" placeholder="添加食材..." @keyup.enter="addFavorite" />
          <button @click="addFavorite">+</button>
        </div>
      </div>

      <!-- 历史对话 -->
      <div class="history-section">
        <h4>💬 历史对话</h4>
        <button class="new-chat-btn" @click="startNewChat">✨ 新对话</button>
        <div v-for="s in chatSessions" :key="s.session_id" class="session-item" :class="{ active: s.session_id === currentSessionId }" @click="loadSession(s)">
          <span class="si-title">{{ s.title }}</span>
          <span class="si-date">{{ formatSessionDate(s.created_at) }}</span>
          <button class="si-del" @click.stop="deleteSession(s.session_id)">×</button>
        </div>
      </div>

      <!-- 快捷问题 -->
      <div class="quick-section">
        <h4>⚡ 快捷提问</h4>
        <button v-for="q in quickQuestions" :key="q" class="quick-btn" @click="askQuick(q)">{{ q }}</button>
      </div>
    </aside>

    <!-- 右侧：Gemini 风格 AI 对话框 -->
    <main class="chat-main">
      <div class="chat-messages" ref="chatWindowRef">
        <div v-for="(msg, idx) in messages" :key="idx" :class="['msg-row', msg.role === 'user' ? 'is-user' : 'is-ai']">
          <div class="msg-avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
          <div class="msg-body">
            <div class="msg-content" v-html="formatMessage(msg.content)"></div>

            <!-- 菜谱导出 -->
            <div v-if="msg.role === 'assistant' && isRecipeReply(msg.content)" class="export-block">
              <div v-if="!msg.exported" class="export-prompt">
                <span>🍱 检测到菜谱推荐</span>
                <div class="export-row">
                  <input type="date" v-model="msg.exportDate" class="date-input" />
                  <button class="export-btn" @click="exportToMenu(msg)">📥 导出至食谱推荐</button>
                </div>
              </div>
              <div v-else class="export-done">✅ 已导出至食谱推荐页</div>
            </div>

            <!-- 反馈按钮 -->
            <div v-if="msg.role === 'assistant' && idx > 0" class="feedback-row">
              <button :class="{ active: msg.feedback === 'up' }" @click="rate(msg, 'up')" :disabled="msg.feedbackSubmitted">👍</button>
              <button :class="{ active: msg.feedback === 'down' }" @click="rate(msg, 'down')" :disabled="msg.feedbackSubmitted">👎</button>
            </div>

            <!-- 差评原因 -->
            <div v-if="msg.showReasons && !msg.feedbackSubmitted" class="reason-panel">
              <p>请选择原因（Agent 会更新图谱黑名单）：</p>
              <div class="reason-tags">
                <span v-for="r in reasons" :key="r.text" class="r-tag" @click="submitFeedback(msg, r.text)">{{ r.icon }} {{ r.label }}</span>
              </div>
            </div>

            <div v-if="msg.feedbackSubmitted" class="fb-thanks">✨ 感谢反馈！图谱已更新。</div>
          </div>
        </div>

        <!-- Loading -->
        <div v-if="isLoading" class="msg-row is-ai">
          <div class="msg-avatar">AI</div>
          <div class="msg-body loading-dots"><span></span><span></span><span></span></div>
        </div>
      </div>

      <!-- 输入框 -->
      <div class="chat-input-area">
        <input v-model="userInput" @keyup.enter="sendMessage" placeholder="说点什么吧，例如：推荐一道低卡晚餐..." :disabled="isLoading" />
        <button @click="sendMessage" :disabled="isLoading || !userInput.trim()">发送</button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { marked } from 'marked'
import API from '../api.js'

const userId = ref(localStorage.getItem('user_id') || '')
const userName = ref(localStorage.getItem('user_name') || '')
const isWeightLossMode = ref(false)
const userInput = ref('')
const isLoading = ref(false)
const chatWindowRef = ref(null)
const currentSessionId = ref('')

const messages = ref([
  { role: 'assistant', content: `你好${userName.value ? '，' + userName.value : ''}！我是智能膳食助手。告诉我你想吃什么，或者冰箱有什么食材，我来帮你搭配！`, feedback: null, showReasons: false, feedbackSubmitted: false, exported: false }
])

// 偏好食材
const favorites = ref([])
const newFav = ref('')

// 历史对话
const chatSessions = ref([])

const quickQuestions = [
  '冰箱里有鸡蛋和番茄，推荐晚餐',
  '推荐一份500卡以下的午餐',
  '减脂期能吃什么零食？',
  '今天吃了火锅，怎么补救？',
]

const reasons = [
  { icon: '🚫', label: '菜品拉黑', text: '推荐的菜品难吃，加入黑名单' },
  { icon: '🛢️', label: '太油腻', text: '烹饪做法太油腻/不健康' },
  { icon: '⚖️', label: '热量不符', text: '热量或分量不符合我的减脂预期' },
  { icon: '🥣', label: '吃不饱', text: '推荐的食物吃不饱，缺乏饱腹感' },
]

const toggleMode = () => { isWeightLossMode.value = !isWeightLossMode.value }

// 偏好食材 CRUD
const loadFavorites = async () => {
  if (!userId.value) return
  try {
    const res = await API.get(`/favorite-ingredients/?user_id=${userId.value}`)
    favorites.value = res.data.favorites || []
  } catch (e) { console.error(e) }
}

const addFavorite = async () => {
  const tag = newFav.value.trim()
  if (!tag || favorites.value.includes(tag)) { newFav.value = ''; return }
  favorites.value.push(tag)
  newFav.value = ''
  if (userId.value) {
    try { await API.post('/favorite-ingredients/', { user_id: userId.value, ingredients: favorites.value }) } catch (e) { console.error(e) }
  }
}

const removeFavorite = async (tag) => {
  favorites.value = favorites.value.filter(t => t !== tag)
  if (userId.value) {
    try { await API.post('/favorite-ingredients/', { user_id: userId.value, ingredients: favorites.value }) } catch (e) { console.error(e) }
  }
}

// 历史对话
const loadChatHistory = async () => {
  if (!userId.value) return
  try {
    const res = await API.get(`/chat-history/?user_id=${userId.value}`)
    chatSessions.value = res.data.sessions || []
  } catch (e) { console.error(e) }
}

const saveCurrentSession = async () => {
  if (!userId.value || messages.value.length <= 1) return
  const firstUserMsg = messages.value.find(m => m.role === 'user')
  const title = firstUserMsg ? firstUserMsg.content.slice(0, 20) : '新对话'
  if (!currentSessionId.value) currentSessionId.value = Date.now().toString(36)
  try {
    await API.post('/chat-history/', {
      user_id: userId.value,
      session_id: currentSessionId.value,
      title,
      messages: messages.value.map(m => ({ role: m.role, content: m.content }))
    })
    loadChatHistory()
  } catch (e) { console.error(e) }
}

const loadSession = (session) => {
  currentSessionId.value = session.session_id
  const msgs = session.msgs || []
  if (msgs.length > 0 && msgs[0].content) {
    messages.value = msgs.map(m => ({
      role: m.role, content: m.content,
      feedback: null, showReasons: false, feedbackSubmitted: false, exported: false
    }))
  }
  scrollBottom()
}

const startNewChat = () => {
  currentSessionId.value = ''
  messages.value = [
    { role: 'assistant', content: `你好${userName.value ? '，' + userName.value : ''}！有什么想吃的？`, feedback: null, showReasons: false, feedbackSubmitted: false, exported: false }
  ]
}

const deleteSession = async (sid) => {
  try {
    await API.delete(`/chat-history/?user_id=${userId.value}&session_id=${sid}`)
    chatSessions.value = chatSessions.value.filter(s => s.session_id !== sid)
    if (currentSessionId.value === sid) startNewChat()
  } catch (e) { console.error(e) }
}

const formatSessionDate = (dt) => {
  if (!dt) return ''
  return dt.slice(5, 16)
}

// 发送消息 —— 将偏好食材融入提问
const sendMessage = async () => {
  const text = userInput.value.trim()
  if (!text || isLoading.value) return
  messages.value.push({ role: 'user', content: text })
  userInput.value = ''
  isLoading.value = true
  scrollBottom()

  // 将偏好食材拼入实际发给后端的 query
  let enrichedQuery = text
  if (favorites.value.length > 0) {
    enrichedQuery += `\n（用户偏好食材：${favorites.value.join('、')}，请在推荐时优先考虑这些食材）`
  }

  try {
    const res = await API.post('/chat/', {
      query: enrichedQuery,
      mode: isWeightLossMode.value ? 'weight_loss' : 'standard',
      user_id: userId.value,
      session_id: userId.value ? `session_${userId.value}` : 'guest_session'
    })
    const today = new Date().toISOString().split('T')[0]
    messages.value.push({
      role: 'assistant', content: res.data.response,
      feedback: null, showReasons: false, feedbackSubmitted: false,
      exportDate: today, exported: false
    })
    // 自动保存对话
    saveCurrentSession()
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '[网络异常] 无法连接后端，请确认 Django 已启动。', feedback: null, showReasons: false, feedbackSubmitted: false, exported: false })
  } finally {
    isLoading.value = false
    scrollBottom()
  }
}

const askQuick = (q) => { userInput.value = q; sendMessage() }

const formatMessage = (text) => marked.parse(text || '')

const scrollBottom = async () => {
  await nextTick()
  if (chatWindowRef.value) chatWindowRef.value.scrollTop = chatWindowRef.value.scrollHeight
}

// 菜谱导出 —— 导出到 localStorage，RecipeView 会读取
const isRecipeReply = (text) => text && (text.includes('热量') || text.includes('卡')) && text.includes('**')

const extractRecipeNames = (text) => {
  const names = []
  const regex = /\*\*([^*]+)\*\*/g
  let m
  const exclude = ['主食','主菜','配菜','晚餐','加餐','早餐','午餐','注意','建议','总计','热量','蛋白质','特点']
  while ((m = regex.exec(text)) !== null) {
    let name = m[1].trim().replace(/^[0-9.\-\s]+/, '')
    if (name && !exclude.includes(name) && name.length < 15) names.push(name)
  }
  return [...new Set(names)]
}

const exportToMenu = async (msg) => {
  if (!msg.exportDate) { alert('请选择日期！'); return }
  const recipeNames = extractRecipeNames(msg.content)
  if (recipeNames.length === 0) { alert('未能提取到有效菜名。'); return }

  try {
    const res = await API.post('/recipe/', { names: recipeNames })
    if (res.data.data?.length > 0) {
      const key = `diet_meals_${userId.value || 'guest'}`
      const saved = JSON.parse(localStorage.getItem(key) || '{}')
      if (!saved[msg.exportDate]) saved[msg.exportDate] = []

      const formatted = res.data.data.map(item => {
        let md = ''
        if (item.ingredients) {
          try {
            const arr = JSON.parse(item.ingredients)
            md += `**🛒 食材清单**：\n${arr.map(i => '- ' + (i.raw_text || i)).join('\n')}\n\n`
          } catch { md += `**🛒 食材清单**：\n${item.ingredients}\n\n` }
        }
        if (item.steps) {
          try {
            const arr = JSON.parse(item.steps)
            if (Array.isArray(arr)) md += `**🍳 烹饪步骤**：\n${arr.map((s, i) => (i + 1) + '. ' + s).join('\n')}`
            else md += `**🍳 烹饪步骤**：\n${item.steps}`
          } catch { md += `**🍳 烹饪步骤**：\n${item.steps}` }
        }
        return {
          id: Date.now() + Math.random().toString(36).substr(2, 5),
          name: item.name,
          calories: item.calories || '未知',
          protein: item.protein || 0,
          fat: item.fat || 0,
          carbs: item.carbs || 0,
          ingredients: item.ingredients || '',
          steps: item.steps || '',
          details: md || '暂无详细做法记录。'
        }
      })

      saved[msg.exportDate].push(...formatted)
      localStorage.setItem(key, JSON.stringify(saved))
      msg.exported = true
    } else { alert(`数据库中未找到这些菜的详细数据：${recipeNames.join(', ')}`) }
  } catch (e) { alert('请求菜谱详情失败') }
}

// 反馈
const rate = (msg, type) => {
  if (msg.feedbackSubmitted) return
  msg.feedback = type
  msg.showReasons = type === 'down'
}

const submitFeedback = async (msg, reason) => {
  if (!userId.value) { alert('请先登录后再反馈！'); return }
  msg.showReasons = false
  msg.feedbackSubmitted = true
  try {
    await API.post('/feedback/', { user_id: userId.value, reason, content: msg.content })
  } catch (e) { msg.feedbackSubmitted = false }
}

onMounted(() => {
  loadFavorites()
  loadChatHistory()
})
</script>

<style scoped>
.chat-view { display: flex; height: 100%; gap: 0; }

/* === 左侧面板 === */
.side-panel { width: 260px; flex-shrink: 0; background: #fff; border-right: 1px solid #f0f2f5; padding: 24px 20px; display: flex; flex-direction: column; gap: 24px; overflow-y: auto; }
.side-panel h3 { font-size: 16px; color: #2d3436; margin: 0; }
.side-panel h4 { font-size: 13px; color: #636e72; margin: 0 0 8px; font-weight: 600; }

.mode-block { }
.mode-toggle { display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 10px 14px; border-radius: 10px; background: #f8f9fa; transition: .2s; font-size: 14px; }
.mode-toggle:hover { background: #f0f2f5; }
.mode-dot { width: 10px; height: 10px; border-radius: 50%; background: #b2bec3; transition: .2s; }
.mode-dot.active { background: #e74c3c; box-shadow: 0 0 8px rgba(231,76,60,.4); }

.tag-cloud { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.fav-tag { display: flex; align-items: center; gap: 4px; background: #e8f5e9; color: #27ae60; padding: 4px 10px; border-radius: 12px; font-size: 13px; }
.tag-del { background: none; border: none; color: #27ae60; cursor: pointer; font-size: 14px; padding: 0; margin-left: 2px; }
.tag-del:hover { color: #c0392b; }
.add-row { display: flex; gap: 6px; }
.add-row input { flex: 1; padding: 8px 10px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 13px; }
.add-row button { padding: 8px 12px; background: #27ae60; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }

.quick-btn { display: block; width: 100%; text-align: left; padding: 10px 12px; background: #f8f9fa; border: 1px solid #f0f2f5; border-radius: 10px; margin-bottom: 6px; font-size: 13px; color: #2d3436; cursor: pointer; transition: .2s; }
.quick-btn:hover { background: #e3f2fd; border-color: #90caf9; }

/* === 历史对话 === */
.history-section { display: flex; flex-direction: column; gap: 6px; }
.fav-hint { font-size: 11px; color: #b2bec3; font-weight: 400; }
.new-chat-btn { width: 100%; padding: 8px 0; background: #42b983; color: #fff; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; margin-bottom: 4px; }
.new-chat-btn:hover { background: #3aa876; }
.session-item { display: flex; align-items: center; gap: 4px; padding: 8px 10px; border-radius: 8px; cursor: pointer; transition: .15s; background: #f8f9fa; }
.session-item:hover { background: #e3f2fd; }
.session-item.active { background: #e1f5fe; border: 1px solid #90caf9; }
.si-title { flex: 1; font-size: 12px; color: #2d3436; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.si-date { font-size: 11px; color: #b2bec3; flex-shrink: 0; }
.si-del { background: none; border: none; color: #b2bec3; cursor: pointer; font-size: 14px; padding: 0 2px; }
.si-del:hover { color: #e74c3c; }

/* === 右侧对话框 === */
.chat-main { flex: 1; display: flex; flex-direction: column; background: #fafbfc; overflow: hidden; }

.chat-messages { flex: 1; overflow-y: auto; padding: 24px 24px 12px; display: flex; flex-direction: column; gap: 16px; }

.msg-row { display: flex; align-items: flex-start; max-width: 80%; gap: 10px; }
.msg-row.is-user { align-self: flex-end; flex-direction: row-reverse; }

.msg-avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; color: #fff; flex-shrink: 0; }
.is-user .msg-avatar { background: linear-gradient(135deg, #6dd5ed, #2193b0); }
.is-ai .msg-avatar { background: linear-gradient(135deg, #84fab0, #8fd3f4); color: #2d3436; }

.msg-body { background: #fff; padding: 14px 18px; border-radius: 14px; box-shadow: 0 2px 6px rgba(0,0,0,.04); line-height: 1.7; color: #2d3436; word-break: break-word; font-size: 14px; }
.is-user .msg-body { background: #e1f0fa; border-top-right-radius: 4px; }
.is-ai .msg-body { border-top-left-radius: 4px; border: 1px solid #f0f2f5; }

/* Markdown 穿透 */
.msg-content :deep(p) { margin: 0 0 8px; }
.msg-content :deep(p:last-child) { margin: 0; }
.msg-content :deep(strong) { color: #2d3436; }
.msg-content :deep(ul), .msg-content :deep(ol) { margin: 8px 0; padding-left: 18px; }

.loading-dots { display: flex; gap: 5px; align-items: center; height: 24px; }
.loading-dots span { width: 7px; height: 7px; background: #b2bec3; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
.loading-dots span:nth-child(1) { animation-delay: -.32s; }
.loading-dots span:nth-child(2) { animation-delay: -.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

/* 导出块 */
.export-block { margin-top: 12px; padding-top: 10px; border-top: 1px dashed #e1e8ed; }
.export-prompt { font-size: 13px; color: #e67e22; font-weight: 600; }
.export-row { display: flex; gap: 8px; margin-top: 6px; align-items: center; }
.date-input { padding: 5px 8px; border: 1px solid #dfe6e9; border-radius: 6px; font-size: 12px; }
.export-btn { background: #e67e22; color: #fff; border: none; padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; }
.export-btn:hover { background: #d35400; }
.export-done { font-size: 13px; color: #27ae60; font-weight: 600; }

/* 反馈 */
.feedback-row { display: flex; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: 1px dashed #eaeaea; }
.feedback-row button { background: none; border: 1px solid #dfe6e9; padding: 4px 12px; border-radius: 12px; font-size: 13px; cursor: pointer; color: #7f8c8d; transition: .2s; }
.feedback-row button.active { background: #fdf0ed; border-color: #e74c3c; color: #c0392b; font-weight: 600; }
.feedback-row button:hover:not(.active):not(:disabled) { background: #f8f9fa; }
.feedback-row button:disabled { opacity: .6; cursor: not-allowed; }

.reason-panel { margin-top: 10px; background: #f9fbfc; padding: 10px 12px; border-radius: 8px; border: 1px solid #e1e8ed; }
.reason-panel p { font-size: 12px; color: #2d3436; font-weight: 600; margin: 0 0 8px; }
.reason-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.r-tag { background: #fff; border: 1px solid #dfe6e9; color: #7f8c8d; font-size: 12px; padding: 4px 10px; border-radius: 14px; cursor: pointer; transition: .2s; }
.r-tag:hover { border-color: #e74c3c; color: #e74c3c; background: #fdf0ed; }
.fb-thanks { margin-top: 8px; font-size: 12px; color: #27ae60; font-weight: 600; }

/* 输入区 */
.chat-input-area { display: flex; padding: 16px 24px; background: #fff; border-top: 1px solid #f0f2f5; gap: 12px; }
.chat-input-area input { flex: 1; padding: 14px 18px; border: 1px solid #dfe6e9; border-radius: 12px; font-size: 14px; outline: none; background: #f8f9fa; transition: .2s; }
.chat-input-area input:focus { border-color: #42b983; background: #fff; box-shadow: 0 0 0 3px rgba(66,185,131,.1); }
.chat-input-area button { background: #42b983; color: #fff; border: none; padding: 0 28px; border-radius: 12px; font-weight: 600; cursor: pointer; font-size: 14px; transition: .2s; }
.chat-input-area button:disabled { background: #b2bec3; cursor: not-allowed; }
.chat-input-area button:not(:disabled):hover { background: #3aa876; }
</style>

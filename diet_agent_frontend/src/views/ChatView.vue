<template>
  <div class="chat-view">

    <aside class="side-panel">
      <h3>个性化偏好</h3>

      <!-- 模式切换 -->
      <div class="mode-block">
        <label class="mode-toggle" @click="toggleMode">
          <span class="mode-dot" :class="{ active: isWeightLossMode }"></span>
          <span>{{ isWeightLossMode ? '减脂模式' : '标准模式' }}</span>
        </label>
      </div>

      <!-- 偏好食材 -->
      <div class="fav-section">
        <h4>偏好食材 <span class="fav-hint">(会自动融入对话)</span></h4>
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
        <h4>历史对话</h4>
        <button class="new-chat-btn" @click="startNewChat">新对话</button>
        <div v-for="s in chatSessions" :key="s.session_id" class="session-item" :class="{ active: s.session_id === currentSessionId }" @click="loadSession(s)">
          <span class="si-title">{{ s.title }}</span>
          <span class="si-date">{{ formatSessionDate(s.created_at) }}</span>
          <button class="si-del" @click.stop="deleteSession(s.session_id)">×</button>
        </div>
      </div>

      <!-- 快捷问题 -->
      <div class="quick-section">
        <h4>快捷提问</h4>
        <button v-for="q in quickQuestions" :key="q" class="quick-btn" @click="askQuick(q)">{{ q }}</button>
      </div>
    </aside>

    <main class="chat-main">
      <div class="chat-messages" ref="chatWindowRef">
        <div v-for="(msg, idx) in messages" :key="idx" :class="['msg-row', msg.role === 'user' ? 'is-user' : 'is-ai']">
          <div class="msg-avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
          <div class="msg-body">
            <div v-if="msg.thinking" class="thinking-block">
              <div class="thinking-toggle" @click="msg.thinkingCollapsed = !msg.thinkingCollapsed">
                <span class="thinking-label">深度思考</span>
                <span class="tk-chevron">{{ msg.thinkingCollapsed ? '▸ 展开' : '▾ 收起' }}</span>
              </div>
              <div v-if="!msg.thinkingCollapsed" class="thinking-content">{{ msg.thinking }}</div>
            </div>
            <div class="msg-content" v-html="formatMessage(msg.answer || msg.content)"></div>

            <div v-if="msg.role === 'assistant' && idx > 0" class="msg-actions">
              <button class="act-btn thumb-btn" :class="{ active: msg.feedback === 'up' }" @click="rate(msg, 'up')" :disabled="msg.feedbackSubmitted" title="点赞反馈" aria-label="点赞反馈">
                <ThumbsUp class="icon-lucide" :size="16" :stroke-width="1.9" aria-hidden="true" />
              </button>
              <button class="act-btn thumb-btn" :class="{ active: msg.feedback === 'down' }" @click="rate(msg, 'down')" :disabled="msg.feedbackSubmitted" title="点踩反馈" aria-label="点踩反馈">
                <ThumbsDown class="icon-lucide" :size="16" :stroke-width="1.9" aria-hidden="true" />
              </button>
              <button class="act-btn icon-btn" @click="regenerateReply(idx)" :disabled="isLoading" title="重新生成这条回复" aria-label="重新生成">
                <RotateCcw class="icon-lucide" :size="18" :stroke-width="1.9" aria-hidden="true" />
              </button>
              <button class="act-btn icon-btn" @click="copyMessage(msg)" title="复制这条回复" aria-label="复制">
                <Copy class="icon-lucide" :size="18" :stroke-width="1.9" aria-hidden="true" />
              </button>
              <button class="act-btn icon-btn" @click="openExportModal(msg)" :disabled="(msg.detectedRecipeNames || []).length === 0" title="导出到食谱推荐页" aria-label="导出">
                <Upload class="icon-lucide" :size="18" :stroke-width="1.9" aria-hidden="true" />
                <span v-if="(msg.detectedRecipeNames || []).length > 0" class="icon-badge">{{ (msg.detectedRecipeNames || []).length }}</span>
              </button>
            </div>

            <!-- 差评原因 -->
            <div v-if="msg.showReasons && !msg.feedbackSubmitted" class="reason-panel">
              <p>请选择不满意的菜品与原因（不会默认拉黑所有菜）：</p>

              <div class="reason-block">
                <div class="reason-label">针对菜品（可多选）</div>
                <div class="reason-tags">
                  <span
                    v-for="name in msg.feedbackRecipes"
                    :key="name"
                    class="r-tag"
                    :class="{ active: (msg.selectedRecipes || []).includes(name) }"
                    @click="toggleSelectedRecipe(msg, name)"
                  >{{ name }}</span>
                </div>
              </div>

              <div class="reason-block">
                <div class="reason-label">不满意类型</div>
                <div class="reason-tags">
                  <span
                    v-for="r in reasonTypes"
                    :key="r.value"
                    class="r-tag"
                    :class="{ active: msg.feedbackReasonType === r.value }"
                    @click="msg.feedbackReasonType = r.value"
                  >{{ r.label }}</span>
                </div>
              </div>

              <div v-if="msg.feedbackReasonType === 'ingredient'" class="reason-block">
                <div class="reason-label">不满意食材（可选）</div>
                <input v-model="msg.selectedIngredient" class="reason-input" placeholder="例如：香菜、洋葱、辣椒" />
              </div>

              <div class="reason-block">
                <div class="reason-label">补充说明（可选）</div>
                <textarea v-model="msg.customReason" class="reason-textarea" rows="2" placeholder="可填写更具体的原因"></textarea>
              </div>

              <div class="reason-actions">
                <button class="reason-cancel" @click="msg.showReasons = false">取消</button>
                <button class="reason-submit" @click="submitDownFeedback(msg)">提交反馈</button>
              </div>
            </div>

            <div v-if="msg.feedbackSubmitted" class="fb-thanks">✨ 感谢反馈！图谱已更新。</div>
          </div>
        </div>

        <div v-if="isLoading" class="msg-row is-ai">
          <div class="msg-avatar">AI</div>
          <div class="msg-body loading-dots"><span></span><span></span><span></span></div>
        </div>
      </div>

      <div class="chat-input-area">
        <input v-model="userInput" @keyup.enter="sendMessage" placeholder="说点什么吧，例如：推荐一道低卡晚餐..." :disabled="isLoading" />
        <button @click="sendMessage" :disabled="isLoading || !userInput.trim()">发送</button>
      </div>

      <div v-if="showExportModal" class="export-modal-overlay" @click.self="showExportModal = false">
        <div class="export-modal">
          <h4>导出到食谱推荐页</h4>
          <p>已识别 {{ exportCandidates.length }} 个菜名，请勾选后导出</p>

          <div class="export-preview">
            <div class="export-preview-header">
              <span>可导出菜名</span>
              <button class="preview-toggle" @click="toggleSelectAllExportCandidates">
                {{ selectedExportNames.length === exportCandidates.length ? '全不选' : '全选' }}
              </button>
            </div>
            <div class="export-preview-list">
              <label v-for="name in exportCandidates" :key="name" class="export-preview-item">
                <input type="checkbox" :value="name" v-model="selectedExportNames" />
                <span>{{ name }}</span>
              </label>
            </div>
          </div>

          <input type="date" v-model="exportDate" class="export-date-input" />
          <div class="export-modal-actions">
            <button class="em-cancel" @click="showExportModal = false">取消</button>
            <button class="em-confirm" :disabled="!exportDate || selectedExportNames.length === 0 || isExporting" @click="confirmExport">{{ isExporting ? '导出中...' : '确认导出' }}</button>
          </div>
        </div>
      </div>

      <div v-if="toastText" class="chat-toast">{{ toastText }}</div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { marked } from 'marked'
import { ThumbsUp, ThumbsDown, RotateCcw, Copy, Upload } from 'lucide-vue-next'
import API from '../api.js'

const userId = ref(localStorage.getItem('user_id') || '')
const userName = ref(localStorage.getItem('user_name') || '')
const isWeightLossMode = ref(false)
const userInput = ref('')
const isLoading = ref(false)
const chatWindowRef = ref(null)
const currentSessionId = ref('')
const showExportModal = ref(false)
const pendingExportMsg = ref(null)
const exportDate = ref(new Date().toISOString().split('T')[0])
const exportCandidates = ref([])
const selectedExportNames = ref([])
const isExporting = ref(false)
const toastText = ref('')
let toastTimer = null

const messages = ref([
  {
    role: 'assistant',
    content: `你好${userName.value ? '，' + userName.value : ''}！我是智能膳食助手。告诉我你想吃什么，或者冰箱有什么食材，我来帮你搭配！`,
    thinking: '', answer: '', thinkingCollapsed: true,
    feedback: null, showReasons: false, feedbackSubmitted: false, exported: false,
    feedbackRecipes: [], selectedRecipes: [], feedbackReasonType: 'dish', selectedIngredient: '', customReason: '',
    detectedRecipeNames: []
  }
])

const parseAIResponse = (text) => {
  if (!text) return { thinking: '', answer: '' }
  const match = text.match(/<think>([\s\S]*?)<\/think>/i)
  if (match) {
    const thinking = match[1].trim()
    const answer = text.replace(/<think>[\s\S]*?<\/think>/i, '').trim()
    return { thinking, answer }
  }
  return { thinking: '', answer: text }
}

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

const reasonTypes = [
  { value: 'dish', label: '菜品不满意' },
  { value: 'ingredient', label: '食材不满意' },
  { value: 'nutrition', label: '营养不符合预期' },
  { value: 'other', label: '其他原因' },
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
    messages.value = msgs.map(m => {
      const { thinking, answer } = parseAIResponse(m.content || '')
      return {
        role: m.role, content: m.content,
        thinking, answer, thinkingCollapsed: true,
        feedback: null, showReasons: false, feedbackSubmitted: false, exported: false,
        feedbackRecipes: [], selectedRecipes: [], feedbackReasonType: 'dish', selectedIngredient: '', customReason: '',
        detectedRecipeNames: []
      }
    })
    hydrateDetectedRecipeNames(messages.value)
  }
  scrollBottom()
}

const startNewChat = () => {
  currentSessionId.value = ''
  messages.value = [
    { role: 'assistant', content: `你好${userName.value ? '，' + userName.value : ''}！有什么想吃的？`, thinking: '', answer: '', thinkingCollapsed: true, feedback: null, showReasons: false, feedbackSubmitted: false, exported: false, feedbackRecipes: [], selectedRecipes: [], feedbackReasonType: 'dish', selectedIngredient: '', customReason: '', detectedRecipeNames: [] }
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

const buildEnrichedQuery = (text) => {
  let enriched = text
  if (favorites.value.length > 0) {
    enriched += `\n（用户偏好食材：${favorites.value.join('、')}，请在推荐时优先考虑这些食材）`
  }
  return enriched
}

// 发送消息 —— 将偏好食材融入提问
const sendMessage = async () => {
  const text = userInput.value.trim()
  if (!text || isLoading.value) return
  messages.value.push({ role: 'user', content: text })
  userInput.value = ''
  isLoading.value = true
  scrollBottom()

  const enrichedQuery = buildEnrichedQuery(text)

  try {
    const res = await API.post('/chat/', {
      query: enrichedQuery,
      mode: isWeightLossMode.value ? 'weight_loss' : 'standard',
      user_id: userId.value,
      session_id: userId.value ? `session_${userId.value}` : 'guest_session'
    })
    const today = new Date().toISOString().split('T')[0]
    const { thinking, answer } = parseAIResponse(res.data.response)
    messages.value.push({
      role: 'assistant', content: res.data.response,
      thinking, answer, thinkingCollapsed: true,
      feedback: null, showReasons: false, feedbackSubmitted: false,
      exportDate: today, exported: false,
      feedbackRecipes: [], selectedRecipes: [], feedbackReasonType: 'dish', selectedIngredient: '', customReason: '',
      detectedRecipeNames: extractRecipeNames(answer || res.data.response || '')
    })
    // 自动保存对话
    saveCurrentSession()
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '[网络异常] 无法连接后端，请确认 Django 已启动。', feedback: null, showReasons: false, feedbackSubmitted: false, exported: false, feedbackRecipes: [], selectedRecipes: [], feedbackReasonType: 'other', selectedIngredient: '', customReason: '', detectedRecipeNames: [] })
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
const extractRecipeNames = (text) => {
  const names = []
  const safeText = text || ''
  const exclude = new Set([
    '主食', '主菜', '配菜', '晚餐', '加餐', '早餐', '午餐', '注意', '建议', '总计', '热量', '蛋白质',
    '特点', '步骤', '食材', '做法', '准备', '总结', '搭配', '方案', '推荐', '菜单', '营养', '说明',
    '基础版', '升级建议', '可选项', '可替换项',
    '推荐组合', '蔬菜拼盘', '点睛之笔', '便当小贴士', '小贴士', '小技巧', '彩虹能量午餐盒',
    '优质蛋白', '膳食纤维', '维生素K', '特调酱汁', '隐藏彩蛋', '夜食秘诀', '营养解码', '主菜组合',
  ])

  const blockedFragments = [
    '升级建议', '如果还有', '可以加', '替代', '提升', '补充', '基础版', '可选', '建议', '做法',
    '推荐组合', '便当小贴士', '小技巧', '点睛之笔', '蔬菜拼盘', '总热量', '需要调整',
  ]

  const pushName = (raw) => {
    let name = (raw || '')
      .trim()
      .replace(/^[0-9一二三四五六七八九十]+[.、)\s-]*/, '')
      .replace(/^[\-•·●]\s*/, '')
      .replace(/[：:].*$/, '')
      .replace(/[（(].*$/, '')
      .trim()
    if (!name) return
    if (name.length < 2 || name.length > 14) return
    if (exclude.has(name)) return
    if (blockedFragments.some(f => name.includes(f))) return
    if (/^(加|撒|用).{1,12}$/.test(name)) return
    if (/(蛋白|脂肪|碳水|膳食纤维|维生素|含量|mg|μg|omega|Ω-?3)/i.test(name)) return
    if (/^(主菜|碳水|蔬菜拼盘|点睛之笔|小贴士)[：:]?$/.test(name)) return
    if (/^(热量|蛋白|脂肪|碳水|卡路里|kcal)/i.test(name)) return
    names.push(name)
  }

  // 固定导出格式优先
  const fixedTagRegex = /(?:^|\n)\s*(?:[-•·●]|\d+[.、)])?\s*(?:\[菜品\]|【菜品】)\s*([^\n（(：:]{2,20})/g
  let ft
  while ((ft = fixedTagRegex.exec(safeText)) !== null) {
    pushName(ft[1])
  }
  if (names.length > 0) {
    return [...new Set(names)]
  }

  // 结构化文本优先提取：
  const sectionDishRegex = /\d+[️⃣]?\s*\*{0,2}\s*(?:主菜|碳水|汤品|甜品|饮品)\s*[：:]\s*([^\n（(\*]{2,20})/g
  let sd
  while ((sd = sectionDishRegex.exec(safeText)) !== null) {
    pushName(sd[1])
  }

  // 食材条目提取：
  const ingredientLineRegex = /(?:^|\n)\s*[-•·●]\s*([^\n：:（(]{2,20}?)(?:（|\d+\s*(?:g|克|颗|个))/g
  let il
  while ((il = ingredientLineRegex.exec(safeText)) !== null) {
    pushName(il[1])
  }

  // 优先提取“推荐菜式/推荐菜品/推荐菜谱”主菜名
  const mainDishPatterns = [
    /[【\[]?推荐菜式[】\]]?\s*(?:[：:]\s*)?([^\n。；;]+)/g,
    /[【\[]?推荐菜品[】\]]?\s*(?:[：:]\s*)?([^\n。；;]+)/g,
    /[【\[]?推荐菜谱[】\]]?\s*(?:[：:]\s*)?([^\n。；;]+)/g,
    /[【\[]?推荐方案[】\]]?\s*(?:[：:]\s*)?([^\n。；;]+)/g,
  ]

  for (const pattern of mainDishPatterns) {
    let m
    while ((m = pattern.exec(safeText)) !== null) {
      const part = (m[1] || '').split(/[、，,\/|]/)
      part.forEach(pushName)
    }
  }

  // 1) 加粗提取
  const boldRegex = /\*\*([^*\n]+)\*\*/g
  let m
  while ((m = boldRegex.exec(safeText)) !== null) {
    pushName(m[1])
  }

  // 2) 按行提取（仅在明显是菜品列表时启用，避免把“升级建议”当菜名）
  safeText
    .split('\n')
    .map(l => l.trim())
    .filter(Boolean)
    .forEach((line) => {
      const likelyDishList = /(推荐菜|菜单|今日推荐|可选菜品|套餐)/.test(safeText)
      const hasSuggestionHints = /(升级建议|如果还有|可以加|替代|提升|补充)/.test(line)
      if (likelyDishList && !hasSuggestionHints && /^([0-9一二三四五六七八九十]+[.、)]|[\-•·●])/.test(line)) {
        pushName(line)
      }
    })

  // 3) 兜底：句内“推荐：A、B、C”样式
  const recommendMatch = safeText.match(/推荐[^\n：:]*[：:]\s*([^\n]+)/)
  if (recommendMatch && recommendMatch[1]) {
    recommendMatch[1]
      .split(/[、，,\/|]/)
      .map(s => s.trim())
      .forEach(pushName)
  }

  return [...new Set(names)]
}

const isRecipeReply = (msg) => {
  return getDetectedRecipeCount(msg) > 0
}

const getDetectedRecipeCount = (msg) => {
  if (!msg || msg.role !== 'assistant') return 0
  if (!Array.isArray(msg.detectedRecipeNames)) {
    const text = msg.answer || msg.content || ''
    msg.detectedRecipeNames = extractRecipeNames(text).filter(n => !/^(加|撒|用).{1,12}$/.test(n))
  }
  return msg.detectedRecipeNames.length
}

const hydrateDetectedRecipeNames = (list) => {
  ;(list || []).forEach((msg) => {
    if (msg.role !== 'assistant') return
    if (!Array.isArray(msg.detectedRecipeNames)) {
      const text = msg.answer || msg.content || ''
      msg.detectedRecipeNames = extractRecipeNames(text).filter(n => !/^(加|撒|用).{1,12}$/.test(n))
    }
  })
}

const openExportModal = (msg) => {
  getDetectedRecipeCount(msg)
  const names = msg.detectedRecipeNames || []

  pendingExportMsg.value = msg
  exportDate.value = msg.exportDate || new Date().toISOString().split('T')[0]
  if (names.length === 0) {
    showToast('未识别到可导出的菜名')
    return
  }
  exportCandidates.value = [...new Set(names)]
  selectedExportNames.value = [...exportCandidates.value]
  showExportModal.value = true
}

const toggleSelectAllExportCandidates = () => {
  if (selectedExportNames.value.length === exportCandidates.value.length) {
    selectedExportNames.value = []
  } else {
    selectedExportNames.value = [...exportCandidates.value]
  }
}

const showToast = (text) => {
  toastText.value = text
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toastText.value = '' }, 1800)
}

const confirmExport = async () => {
  if (!pendingExportMsg.value || isExporting.value) return
  isExporting.value = true
  try {
    pendingExportMsg.value.exportDate = exportDate.value
    await exportToMenu(pendingExportMsg.value, selectedExportNames.value)
    showExportModal.value = false
    showToast('已导出到食谱推荐页')
  } finally {
    isExporting.value = false
  }
}

const exportToMenu = async (msg, overrideRecipeNames = null) => {
  if (!msg.exportDate) { alert('请选择日期！'); return }
  const answerText = msg.answer || msg.content
  const recipeNames = overrideRecipeNames && overrideRecipeNames.length > 0
    ? [...new Set(overrideRecipeNames)]
    : extractRecipeNames(answerText).filter(n => !/^(加|撒|用).{1,12}$/.test(n))
  if (recipeNames.length === 0) { alert('未能提取到有效菜名，请让 AI 明确列出菜品名称后再导出。'); return }

  const key = `diet_meals_${userId.value || 'guest'}`
  const saved = JSON.parse(localStorage.getItem(key) || '{}')
  if (!saved[msg.exportDate]) saved[msg.exportDate] = []

  try {
    const res = await API.post('/recipe/', { names: recipeNames })
    const dbItems = res.data.data || []

    const returnedNameKeys = new Set(dbItems.map(item => item.requested_name || item.name))

    // 命中Neo4j或AI补全后的结果都统一导出
    dbItems.forEach(item => {
      saved[msg.exportDate].push({
        id: Date.now() + '_' + Math.random().toString(36).substr(2, 5),
        name: item.name,
        calories: item.calories || 0,
        protein: item.protein || 0,
        fat: item.fat || 0,
        carbs: item.carbs || 0,
        ingredients: item.ingredients || '',
        steps: item.steps || '',
        source: item.source || 'unknown'
      })
    })

    // 后端若有漏返回，兜底仍保留菜名
    recipeNames.filter(name => !returnedNameKeys.has(name)).forEach(name => {
      saved[msg.exportDate].push({
        id: Date.now() + '_' + Math.random().toString(36).substr(2, 5),
        name,
        calories: 0,
        protein: 0,
        fat: 0,
        carbs: 0,
        ingredients: '',
        steps: '',
        source: 'fallback_name_only'
      })
    })
  } catch (e) {
    // 接口异常时，至少先导出菜名，不阻断用户流程
    recipeNames.forEach(name => {
      saved[msg.exportDate].push({
        id: Date.now() + '_' + Math.random().toString(36).substr(2, 5),
        name,
        calories: 0,
        protein: 0,
        fat: 0,
        carbs: 0,
        ingredients: '',
        steps: '',
        source: 'fallback_name_only'
      })
    })
  }

  localStorage.setItem(key, JSON.stringify(saved))
  msg.exported = true
}

// 反馈
const rate = (msg, type) => {
  if (msg.feedbackSubmitted) return
  msg.feedback = type
  if (type === 'down') {
    const recipeNames = extractRecipeNames(msg.answer || msg.content || '')
    msg.feedbackRecipes = recipeNames
    msg.selectedRecipes = recipeNames.length > 0 ? [recipeNames[0]] : []
    msg.feedbackReasonType = 'dish'
    msg.selectedIngredient = ''
    msg.customReason = ''
    msg.showReasons = true
  } else {
    msg.showReasons = false
    submitFeedback(msg, '回答有帮助，方向正确', 'up')
  }
}

const toggleSelectedRecipe = (msg, name) => {
  const current = new Set(msg.selectedRecipes || [])
  if (current.has(name)) {
    current.delete(name)
  } else {
    current.add(name)
  }
  msg.selectedRecipes = [...current]
}

const submitDownFeedback = (msg) => {
  const selected = msg.selectedRecipes || []
  const reasonTypeMap = {
    dish: '菜品不满意',
    ingredient: '食材不满意',
    nutrition: '营养不符合预期',
    other: '其他原因',
  }

  const parts = []
  parts.push(`类型：${reasonTypeMap[msg.feedbackReasonType] || '其他原因'}`)
  if (selected.length > 0) parts.push(`菜品：${selected.join('、')}`)
  if (msg.selectedIngredient) parts.push(`食材：${msg.selectedIngredient}`)
  if (msg.customReason) parts.push(`补充：${msg.customReason}`)

  if (parts.length === 1 && !msg.customReason) {
    alert('请至少选择具体菜品，或填写食材/补充原因。')
    return
  }

  submitFeedback(msg, parts.join('；'), 'down')
}

const submitFeedback = async (msg, reason, feedbackType = 'down') => {
  if (!userId.value) { alert('请先登录后再反馈！'); return }
  msg.showReasons = false
  msg.feedbackSubmitted = true
  try {
    await API.post('/feedback/', {
      user_id: userId.value,
      reason,
      content: msg.content,
      feedback_type: feedbackType
    })
  } catch (e) { msg.feedbackSubmitted = false }
}

const copyMessage = async (msg) => {
  const text = msg.answer || msg.content || ''
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    showToast('已复制到剪贴板')
  } catch {
    alert('复制失败，请检查浏览器权限。')
  }
}

const regenerateReply = async (idx) => {
  if (isLoading.value) return
  const msg = messages.value[idx]
  if (!msg || msg.role !== 'assistant') return

  let previousUserText = ''
  for (let i = idx - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') {
      previousUserText = messages.value[i].content || ''
      break
    }
  }
  if (!previousUserText) {
    alert('未找到该回答对应的用户提问，无法重新生成。')
    return
  }

  isLoading.value = true
  try {
    const res = await API.post('/chat/', {
      query: buildEnrichedQuery(previousUserText),
      mode: isWeightLossMode.value ? 'weight_loss' : 'standard',
      user_id: userId.value,
      session_id: userId.value ? `session_${userId.value}` : 'guest_session'
    })
    const { thinking, answer } = parseAIResponse(res.data.response)
    const today = new Date().toISOString().split('T')[0]
    msg.content = res.data.response
    msg.thinking = thinking
    msg.answer = answer
    msg.thinkingCollapsed = true
    msg.feedback = null
    msg.showReasons = false
    msg.feedbackSubmitted = false
    msg.exported = false
    msg.exportDate = today
    msg.feedbackRecipes = []
    msg.selectedRecipes = []
    msg.feedbackReasonType = 'dish'
    msg.selectedIngredient = ''
    msg.customReason = ''
    msg.detectedRecipeNames = extractRecipeNames(answer || msg.content || '')
  } catch (e) {
    alert('重新生成失败，请稍后重试。')
  } finally {
    isLoading.value = false
    scrollBottom()
  }
}

onMounted(() => {
  loadFavorites()
  loadChatHistory()
})
</script>

<style scoped>
.chat-view { display: flex; height: calc(100vh - 48px); gap: 0; }

/* === 左侧面板 === */
.side-panel { width: 260px; flex-shrink: 0; background: #fff; border-right: 1px solid #ede9fc; padding: 24px 20px; display: flex; flex-direction: column; gap: 24px; overflow-y: auto; height: 100%; }
.side-panel h3 { font-size: 16px; color: #2d3436; margin: 0; }
.side-panel h4 { font-size: 13px; color: #636e72; margin: 0 0 8px; font-weight: 600; }

.mode-block { margin: 0; }
.mode-toggle { display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 10px 14px; border-radius: 10px; background: #f8f9fa; transition: .2s; font-size: 14px; }
.mode-toggle:hover { background: #f0f2f5; }
.mode-dot { width: 10px; height: 10px; border-radius: 50%; background: #b2bec3; transition: .2s; }
.mode-dot.active { background: #e74c3c; box-shadow: 0 0 8px rgba(231,76,60,.4); }

.tag-cloud { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.fav-tag { display: flex; align-items: center; gap: 4px; background: #ede9fc; color: #7761e5; padding: 4px 10px; border-radius: 12px; font-size: 13px; }
.tag-del { background: none; border: none; color: #7761e5; cursor: pointer; font-size: 14px; padding: 0; margin-left: 2px; }
.tag-del:hover { color: #c0392b; }
.add-row { display: flex; gap: 6px; }
.add-row input { flex: 1; padding: 8px 10px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 13px; }
.add-row button { padding: 8px 12px; background: #7761e5; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }

.quick-btn { display: block; width: 100%; text-align: left; padding: 10px 12px; background: #f8f9fa; border: 1px solid #f0f2f5; border-radius: 10px; margin-bottom: 6px; font-size: 13px; color: #2d3436; cursor: pointer; transition: .2s; }
.quick-btn:hover { background: #ede9fc; border-color: #c4b8f0; }

/* === 历史对话 === */
.history-section { display: flex; flex-direction: column; gap: 6px; }
.fav-hint { font-size: 11px; color: #b2bec3; font-weight: 400; }
.new-chat-btn { width: 100%; padding: 8px 0; background: #7761e5; color: #fff; border: none; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; margin-bottom: 4px; }
.new-chat-btn:hover { background: #6350d0; }
.session-item { display: flex; align-items: center; gap: 4px; padding: 8px 10px; border-radius: 8px; cursor: pointer; transition: .15s; background: #f8f9fa; }
.session-item:hover { background: #ede9fc; }
.session-item.active { background: #ddd6f9; border: 1px solid #c4b8f0; }
.si-title { flex: 1; font-size: 12px; color: #2d3436; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.si-date { font-size: 11px; color: #b2bec3; flex-shrink: 0; }
.si-del { background: none; border: none; color: #b2bec3; cursor: pointer; font-size: 14px; padding: 0 2px; }
.si-del:hover { color: #e74c3c; }

/* === 右侧对话框 === */
.chat-main { flex: 1; display: flex; flex-direction: column; background: #fff; overflow: hidden; height: 100%; }

.chat-messages { flex: 1; overflow-y: auto; padding: 32px 34px 16px; display: flex; flex-direction: column; gap: 18px; }

.msg-row { display: flex; align-items: flex-start; max-width: 920px; width: 100%; gap: 10px; }
.msg-row.is-user { align-self: flex-end; flex-direction: row-reverse; }

.msg-row.is-ai { align-self: flex-start; }

.msg-avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; color: #fff; flex-shrink: 0; }
.is-user .msg-avatar { background: linear-gradient(135deg, #8ac3f9, #7761e5); }
.is-ai .msg-avatar { background: linear-gradient(135deg, #f6c342, #4aa458); color: #fff; }

.msg-body { background: #fff; padding: 14px 18px; border-radius: 14px; box-shadow: 0 1px 2px rgba(0,0,0,.06); line-height: 1.7; color: #2d3436; word-break: break-word; font-size: 14px; }
.is-user .msg-body { background: #ede9fc; border-top-right-radius: 4px; }
.is-ai .msg-body { border-top-left-radius: 4px; border: 1px solid #eef1f6; box-shadow: none; }

.thinking-block { margin-bottom: 10px; border: 1px solid #e9ecef; border-radius: 8px; overflow: hidden; background: #f8f9fa; }
.thinking-toggle { display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; cursor: pointer; user-select: none; }
.thinking-toggle:hover { background: #f0f2f5; }
.thinking-label { font-size: 11px; color: #868e96; font-weight: 500; letter-spacing: 0.3px; }
.tk-chevron { font-size: 11px; color: #adb5bd; }
.thinking-content { padding: 8px 12px 10px; font-size: 12px; color: #adb5bd; line-height: 1.65; font-style: italic; white-space: pre-wrap; border-top: 1px solid #e9ecef; max-height: 200px; overflow-y: auto; }

.msg-content :deep(p) { margin: 0 0 8px; }
.msg-content :deep(p:last-child) { margin: 0; }
.msg-content :deep(strong) { color: #2d3436; }
.msg-content :deep(ul), .msg-content :deep(ol) { margin: 8px 0; padding-left: 18px; }

.loading-dots { display: flex; gap: 5px; align-items: center; height: 24px; }
.loading-dots span { width: 7px; height: 7px; background: #b2bec3; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
.loading-dots span:nth-child(1) { animation-delay: -.32s; }
.loading-dots span:nth-child(2) { animation-delay: -.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

.msg-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f3f7;
  opacity: .72;
  transition: opacity .18s ease;
}

.is-ai .msg-body:hover .msg-actions { opacity: 1; }

.act-btn {
  border: 1px solid transparent;
  background: transparent;
  color: #1f2329;
  border-radius: 8px;
  padding: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: .18s;
}

.act-btn:hover:not(:disabled) { color: #000; }
.act-btn.active { color: #000; }
.act-btn:disabled { opacity: .5; cursor: not-allowed; }

.thumb-btn {
  width: 30px;
  height: 30px;
  border: 1.2px solid #1f2329;
  border-radius: 999px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.thumb-btn.active {
  border-color: #000;
  background: transparent;
}

.icon-btn {
  width: 30px;
  height: 30px;
  padding: 0;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.icon-lucide {
  display: block;
}

.icon-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 16px;
  height: 16px;
  border-radius: 999px;
  background: #1f2329;
  color: #fff;
  border: 1px solid #fff;
  font-size: 10px;
  line-height: 14px;
  text-align: center;
  padding: 0 4px;
}

.reason-panel { margin-top: 10px; background: #f9fbfc; padding: 10px 12px; border-radius: 8px; border: 1px solid #e1e8ed; }
.reason-panel p { font-size: 12px; color: #2d3436; font-weight: 600; margin: 0 0 8px; }
.reason-block { margin-top: 8px; }
.reason-label { font-size: 12px; color: #636e72; margin-bottom: 6px; font-weight: 600; }
.reason-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.r-tag { background: #fff; border: 1px solid #dfe6e9; color: #7f8c8d; font-size: 12px; padding: 4px 10px; border-radius: 14px; cursor: pointer; transition: .2s; }
.r-tag:hover { border-color: #e74c3c; color: #e74c3c; background: #fdf0ed; }
.r-tag.active { border-color: #7761e5; color: #7761e5; background: #ede9fc; }
.reason-input, .reason-textarea {
  width: 100%; border: 1px solid #dfe6e9; border-radius: 8px; padding: 8px 10px;
  font-size: 12px; outline: none; background: #fff;
}
.reason-input:focus, .reason-textarea:focus { border-color: #7761e5; }
.reason-actions { margin-top: 10px; display: flex; justify-content: flex-end; gap: 8px; }
.reason-cancel, .reason-submit {
  border: 1px solid #dfe6e9; background: #fff; border-radius: 8px; padding: 6px 12px;
  font-size: 12px; cursor: pointer;
}
.reason-submit { background: #7761e5; border-color: #7761e5; color: #fff; }
.fb-thanks { margin-top: 8px; font-size: 12px; color: #4aa458; font-weight: 600; }

.export-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, .32);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1300;
}

.export-modal {
  width: 360px;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e9edf3;
  box-shadow: 0 20px 50px rgba(0,0,0,.16);
  padding: 18px;
}

.export-modal h4 { margin: 0 0 6px; font-size: 18px; color: #2d3436; }
.export-modal p { margin: 0 0 12px; color: #7c8a96; font-size: 13px; }

.export-preview {
  border: 1px solid #edf1f6;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 10px;
  background: #fbfcfe;
}

.export-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: #60707d;
  font-weight: 600;
}

.preview-toggle {
  border: 1px solid #dfe7f0;
  border-radius: 999px;
  background: #fff;
  color: #60707d;
  font-size: 11px;
  padding: 4px 8px;
  cursor: pointer;
}

.export-preview-list {
  max-height: 140px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.export-preview-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #35424b;
}

.export-date-input {
  width: 100%;
  border: 1px solid #dfe6ef;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  outline: none;
}

.export-date-input:focus { border-color: #7761e5; }

.export-modal-actions { margin-top: 14px; display: flex; justify-content: flex-end; gap: 8px; }
.em-cancel, .em-confirm { border-radius: 8px; border: 1px solid #dfe6ef; padding: 8px 12px; font-size: 13px; cursor: pointer; }
.em-confirm { background: #7761e5; color: #fff; border-color: #7761e5; }
.em-confirm:disabled { opacity: .5; cursor: not-allowed; }

.chat-toast {
  position: fixed;
  right: 26px;
  bottom: 24px;
  z-index: 1500;
  background: rgba(45, 52, 54, .92);
  color: #fff;
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 999px;
  box-shadow: 0 8px 22px rgba(0,0,0,.2);
}

.chat-input-area { display: flex; padding: 16px 24px; background: #fff; border-top: 1px solid #f0f2f5; gap: 12px; }
.chat-input-area input { flex: 1; padding: 14px 18px; border: 1px solid #dfe6e9; border-radius: 12px; font-size: 14px; outline: none; background: #f8f9fa; transition: .2s; }
.chat-input-area input:focus { border-color: #7761e5; background: #fff; box-shadow: 0 0 0 3px rgba(119,97,229,.12); }
.chat-input-area button { background: #7761e5; color: #fff; border: none; padding: 0 28px; border-radius: 12px; font-weight: 600; cursor: pointer; font-size: 14px; transition: .2s; }
.chat-input-area button:disabled { background: #b2bec3; cursor: not-allowed; }
.chat-input-area button:not(:disabled):hover { background: #6350d0; }
</style>

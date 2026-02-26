<script setup>
import { ref, nextTick, watch } from 'vue'
import axios from 'axios'
import MarkdownIt from 'markdown-it'
import { User, Service, Promotion, Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// --- Markdown 配置 ---
const md = new MarkdownIt()
const renderMarkdown = (text) => {
  return md.render(text)
}

// --- 核心状态 ---
const input = ref('')
const messages = ref([
  { role: 'ai', content: '你好！我是你的膳食规划智能体。请问今天想吃点什么？' }
])
const isLoading = ref(false)
const chatContainer = ref(null)
const userMode = ref('standard') // 'standard' | 'weight_loss'

// --- 反馈系统状态 ---
const feedbackDialogVisible = ref(false)
const feedbackReason = ref([])
const currentFeedbackMsgIndex = ref(null)
const feedbackOptions = ['口味不喜欢', '食材过敏', '热量太高', '做法太难', '吃不饱/量太少', '其他']

// --- 监听模式切换 (调试用) ---
watch(userMode, (newVal) => {
  console.log('🔴 前端开关已切换:', newVal)
  ElMessage.info(`已切换为：${newVal === 'weight_loss' ? '减脂模式 (严格)' : '日常模式 (宽松)'}`)
})

// --- 滚动到底部 ---
const scrollToBottom = async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

// --- 发送消息 ---
const sendMessage = async () => {
  const query = input.value.trim()
  if (!query || isLoading.value) return

  // 1. 用户消息上屏
  messages.value.push({ role: 'user', content: query })
  input.value = ''
  isLoading.value = true
  scrollToBottom()

  try {
    // 2. 发送请求
    const res = await axios.post('http://127.0.0.1:8000/api/chat/', {
      query: query,
      mode: userMode.value
    })

    // 3. AI 回复上屏 (初始化 feedback 状态)
    messages.value.push({
      role: 'ai',
      content: res.data.response,
      feedback: null // null | 'like' | 'dislike'
    })
  } catch (error) {
    console.error(error)
    messages.value.push({ role: 'system', content: '🔴 服务器连接失败，请检查后端。' })
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

// --- 点赞逻辑 ---
const handleLike = (index) => {
  if (messages.value[index].feedback === 'like') return // 防止重复
  messages.value[index].feedback = 'like'
  ElMessage.success('感谢反馈！我会继续保持 😄')

  // 发送给后端记录 (可选)
  // axios.post('/api/feedback/', { type: 'like', content: messages.value[index].content })
}

// --- 点踩逻辑 ---
const handleDislike = (index) => {
  currentFeedbackMsgIndex.value = index
  feedbackDialogVisible.value = true // 打开弹窗
}

// --- 提交踩的原因 ---
const submitDislike = async () => {
  const index = currentFeedbackMsgIndex.value
  if (index !== null) {
    messages.value[index].feedback = 'dislike'

    // 这里可以打印或发送给后端
    console.log('用户反馈不喜欢:', {
      reason: feedbackReason.value,
      content: messages.value[index].content
    })

    ElMessage.warning('收到反馈，我会努力改进！😤')
  }

  // 重置弹窗状态
  feedbackDialogVisible.value = false
  feedbackReason.value = []
  currentFeedbackMsgIndex.value = null
}
</script>

<template>
  <div class="chat-layout">
    <div class="sidebar">
      <div class="avatar-area">
        <el-avatar :size="60" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png" />
        <h3 class="username">小吴</h3>
        <p class="status">武汉大学 · 计算机学院</p>
      </div>

      <div class="mode-switch-area">
        <span class="mode-label">减脂模式</span>
        <el-switch
          v-model="userMode"
          active-value="weight_loss"
          inactive-value="standard"
          active-color="#13ce66"
          inactive-color="#909399"
        />
        <div class="mode-desc">
          {{ userMode === 'weight_loss' ? '🟢 严格控热 & 饱腹感' : '⚪ 日常营养 & 口味' }}
        </div>
      </div>

      <div class="menu">
        <div class="menu-item active">💬 智能对话</div>
        <div class="menu-item">📊 个人档案 (开发中)</div>
      </div>
    </div>

    <div class="main-chat">
      <div class="chat-header">
        <span>🥗 膳食规划智能体 (Agent)</span>
        <el-tag v-if="userMode==='weight_loss'" type="success" effect="dark" size="small" style="margin-left: 10px;">减脂中</el-tag>
      </div>

      <div class="messages-container" ref="chatContainer">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="message-row"
          :class="msg.role === 'user' ? 'row-right' : 'row-left'"
        >
          <el-avatar v-if="msg.role === 'ai'" :icon="Service" class="msg-avatar ai-avatar" size="small" />

          <div class="bubble-wrapper">
            <div class="bubble" :class="msg.role">
              <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
            </div>

            <div v-if="msg.role === 'ai'" class="feedback-actions">
              <el-button
                type="primary" link
                :icon="CircleCheck"
                :class="{ 'active-like': msg.feedback === 'like' }"
                @click="handleLike(index)"
                size="small"
              >有用</el-button>
              <el-button
                type="danger" link
                :icon="CircleClose"
                :class="{ 'active-dislike': msg.feedback === 'dislike' }"
                @click="handleDislike(index)"
                size="small"
              >不行</el-button>
            </div>
          </div>

          <el-avatar v-if="msg.role === 'user'" :icon="User" class="msg-avatar user-avatar" size="small" />
        </div>

        <div v-if="isLoading" class="message-row row-left">
          <el-avatar :icon="Service" class="msg-avatar ai-avatar" size="small" />
          <div class="bubble ai">
            <el-icon class="is-loading"><Loading /></el-icon> 思考中...
          </div>
        </div>
      </div>

      <div class="input-area">
        <el-input
          v-model="input"
          type="textarea"
          :rows="3"
          placeholder="请输入需求，例如：'晚餐吃什么能瘦？'..."
          @keydown.enter.prevent="sendMessage"
        />
        <div class="action-bar">
          <el-button type="primary" :icon="Promotion" @click="sendMessage" :loading="isLoading">发送</el-button>
        </div>
      </div>
    </div>

    <el-dialog v-model="feedbackDialogVisible" title="👎 请告诉我哪里不好？" width="400px">
      <p style="margin-bottom: 10px; color: #666;">您的反馈将直接优化后续的推荐逻辑：</p>
      <el-checkbox-group v-model="feedbackReason">
        <div v-for="opt in feedbackOptions" :key="opt" style="margin-bottom: 5px;">
          <el-checkbox :label="opt">{{ opt }}</el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="feedbackDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitDislike">提交改进</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 布局样式 */
.chat-layout { display: flex; height: 100vh; width: 100vw; background-color: #f5f7fa; font-family: 'PingFang SC', sans-serif; }
.sidebar { width: 260px; background-color: #2c3e50; color: white; display: flex; flex-direction: column; align-items: center; padding-top: 40px; }
.avatar-area { text-align: center; margin-bottom: 20px; }
.username { margin-top: 15px; font-size: 18px; }
.status { font-size: 12px; color: #a0cfff; }

.mode-switch-area { background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; width: 80%; margin-bottom: 30px; text-align: center; }
.mode-switch-area .el-switch.is-checked .el-switch__core { background-color: #03bdac; }
.mode-label { display: block; margin-bottom: 8px; font-size: 14px; font-weight: bold; }
.mode-desc { margin-top: 5px; font-size: 12px; color: #ccc; }

.menu { width: 100%; }
.menu-item { padding: 15px 30px; cursor: pointer; transition: background 0.3s; }
.menu-item:hover { background-color: #34495e; }
.menu-item.active { background-color: #409eff; }

.main-chat { flex: 1; display: flex; flex-direction: column; background-color: white; }
.chat-header { height: 60px; border-bottom: 1px solid #e4e7ed; display: flex; align-items: center; padding-left: 20px; font-weight: bold; font-size: 16px; color: #303133; }
.messages-container { flex: 1; padding: 20px; overflow-y: auto; background-color: #f4f6f8; }

.message-row { display: flex; align-items: flex-start; margin-bottom: 20px; }
.row-right { justify-content: flex-end; }
.row-left { justify-content: flex-start; }
.msg-avatar { margin: 0 10px; flex-shrink: 0; }
.ai-avatar { background-color: #03bdac; }
.user-avatar { background-color: #409eff; }

/* 气泡与反馈按钮包裹层 */
.bubble-wrapper { display: flex; flex-direction: column; max-width: 70%; }
.bubble { padding: 12px 16px; border-radius: 8px; font-size: 14px; line-height: 1.6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
.bubble.ai { background-color: white; color: #303133; border-top-left-radius: 0; }
.bubble.user { background-color: #e6f0ff; color: #303133; border-top-right-radius: 0; }

/* 反馈按钮样式 */
.feedback-actions { margin-top: 6px; display: flex; gap: 10px; }
.active-like { color: #67c23a; font-weight: bold; }
.active-dislike { color: #f56c6c; font-weight: bold; }

.input-area { padding: 20px; border-top: 1px solid #e4e7ed; background-color: white; }
.action-bar { margin-top: 10px; text-align: right; }

/* Markdown 样式微调 */
.markdown-body ul, .markdown-body ol { padding-left: 20px; margin: 5px 0; }
.markdown-body p { margin-bottom: 8px; }
.markdown-body strong { color: #d32f2f; } /* 重点文字标红 */
</style>

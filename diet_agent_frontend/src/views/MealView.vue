<script setup>
import { ref, nextTick } from 'vue'
import axios from 'axios'
import MarkdownIt from 'markdown-it'
import { ShoppingCart, ChatDotRound, Promotion } from '@element-plus/icons-vue'

const md = new MarkdownIt()
const currentDate = ref(new Date())
const activeTab = ref('lunch')
const hasMealPlan = ref(false)

// AI 对话窗口状态
const dialogVisible = ref(false)
const aiInput = ref('')
const aiMessages = ref([])
const isAiLoading = ref(false)
const chatBody = ref(null)

// 开启规划
const startPlanning = () => {
  dialogVisible.value = true
  if (aiMessages.value.length === 0) {
    aiMessages.value.push({ role: 'ai', content: `你好！我是你的专属营养师。需要我为你规划**${activeTab.value === 'lunch' ? '午餐' : '餐食'}**吗？你可以告诉我你想吃什么，或者有什么特殊要求。` })
  }
}

// 在弹窗里发送消息
const sendAiMessage = async () => {
  const query = aiInput.value.trim()
  if (!query || isAiLoading.value) return

  aiMessages.value.push({ role: 'user', content: query })
  aiInput.value = ''
  isAiLoading.value = true

  // 滚动到底部
  await nextTick()
  if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight

  try {
    const res = await axios.post('http://127.0.0.1:8000/api/chat/', {
      query: query,
      mode: 'standard' // 或者从 profile 里取
    })
    aiMessages.value.push({ role: 'ai', content: res.data.response })

    // 假设 AI 返回了确定的食谱，这里可以加个按钮让用户点击“采纳”，然后 hasMealPlan = true
  } catch (error) {
    aiMessages.value.push({ role: 'system', content: '连接失败' })
  } finally {
    isAiLoading.value = false
    await nextTick()
    if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight
  }
}
</script>

<template>
  <div class="page-container">
    <div class="control-bar">
      <el-date-picker v-model="currentDate" type="date" placeholder="选择日期" />
      <el-radio-group v-model="activeTab" style="margin-left: 20px;">
        <el-radio-button label="breakfast">早餐</el-radio-button>
        <el-radio-button label="lunch">午餐</el-radio-button>
        <el-radio-button label="dinner">晚餐</el-radio-button>
      </el-radio-group>
      <el-button color="#03bdac" :icon="ShoppingCart" plain style="margin-left: auto;">导出清单</el-button>
    </div>

    <div class="meal-content">
      <div v-if="hasMealPlan" class="meal-grid">
         <el-card shadow="hover">已生成的餐食详情...</el-card>
      </div>

      <div v-else class="empty-state">
        <el-empty description="当前时段暂无餐食计划">
          <el-button color="#03bdac" size="large" :icon="ChatDotRound" @click="startPlanning">呼叫 AI 生成餐食</el-button>
        </el-empty>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" title="🤖 智能餐食规划" width="600px" top="5vh">
      <div class="chat-body" ref="chatBody">
        <div v-for="(msg, idx) in aiMessages" :key="idx" :class="['msg-row', msg.role]">
          <div class="bubble" v-html="md.render(msg.content)"></div>
        </div>
        <div v-if="isAiLoading" class="msg-row ai"><div class="bubble">正在思考搭配方案...</div></div>
      </div>

      <div class="chat-footer">
        <el-input v-model="aiInput" placeholder="输入你想吃的，比如：给我安排一份饱腹感强的鸡肉餐..." @keyup.enter="sendAiMessage">
          <template #append>
            <el-button :icon="Promotion" color="#03bdac" style="color: white;" @click="sendAiMessage" />
          </template>
        </el-input>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-container { padding: 20px; max-width: 1440px; margin: 0 auto; }
.control-bar { display: flex; align-items: center; margin-bottom: 20px; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.empty-state { background: white; padding: 60px 0; border-radius: 8px; text-align: center; }

/* 对话窗口专用样式 */
.chat-body { height: 400px; overflow-y: auto; background: #f5f7fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
.msg-row { display: flex; margin-bottom: 15px; }
.msg-row.user { justify-content: flex-end; }
.msg-row.ai { justify-content: flex-start; }
.bubble { max-width: 80%; padding: 10px 15px; border-radius: 8px; font-size: 14px; line-height: 1.5; }
.user .bubble { background-color: #03bdac; color: white; border-bottom-right-radius: 0; }
.ai .bubble { background-color: white; border: 1px solid #ebeef5; border-bottom-left-radius: 0; }
/* 覆盖 Markdown 里 p 标签自带的 margin */
:deep(.bubble p) { margin: 0; }
</style>

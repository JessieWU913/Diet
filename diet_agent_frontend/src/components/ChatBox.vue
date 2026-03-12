<template>
  <div class="chat-box-container">
    <header class="chat-header">
      <div class="header-info">
        <h3>AI 营养师</h3>
        <span v-if="userName" class="welcome-text">为 {{ userName }} 定制</span>
      </div>

      <div class="mode-switch">
        <label>
          <input type="checkbox" v-model="isWeightLossMode" />
          <span class="slider" :class="{ active: isWeightLossMode }">
            {{ isWeightLossMode ? '严格减脂模式' : '日常标准模式' }}
          </span>
        </label>
      </div>
    </header>

    <main class="chat-window" ref="chatWindow">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['message-wrapper', msg.role === 'user' ? 'is-user' : 'is-ai']"
      >
        <div class="avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>

        <div class="message-bubble">
          <div v-html="formatMessage(msg.content)"></div>

          <div v-if="msg.role === 'assistant' && isRecipeRecommendation(msg.content)" class="export-module">
            <div v-if="!msg.exported" class="export-prompt">
              <p>检测到菜谱推荐，是否加入您的菜谱单？</p>
              <div class="export-controls">
                <input type="date" v-model="msg.exportDate" class="mini-date" />
                <button class="export-btn" @click="exportToMenu(msg)">导出完整做法</button>
              </div>
            </div>
            <div v-else class="export-success">
              已成功导出至 {{ msg.exportDate }} <router-link to="/meals">去查看</router-link>
            </div>
          </div>

          <div v-if="msg.role === 'assistant' && index !== 0" class="feedback-actions">
            <button
              :class="{ active: msg.feedback === 'up' }"
              @click="rateMessage(msg, 'up')"
              :disabled="msg.feedbackSubmitted"
            >👍 满意</button>
            <button
              :class="{ active: msg.feedback === 'down' }"
              @click="rateMessage(msg, 'down')"
              :disabled="msg.feedbackSubmitted"
            >👎 不满意</button>
          </div>

          <div v-if="msg.showReasonOptions && !msg.feedbackSubmitted" class="reason-selector">
            <p class="reason-title">请告诉我们原因，Agent 会将其写入图谱黑名单：</p>
            <div class="reason-tags">
              <span class="r-tag" @click="submitFeedback(msg, '推荐的菜品难吃，加入黑名单')">菜品拉黑</span>
              <span class="r-tag" @click="submitFeedback(msg, '烹饪做法太油腻/不健康')">做法太油腻</span>
              <span class="r-tag" @click="submitFeedback(msg, '热量或分量不符合我的减脂预期')">热量不符</span>
              <span class="r-tag" @click="submitFeedback(msg, '推荐的食物吃不饱，缺乏饱腹感')">吃不饱</span>
            </div>
          </div>

          <div v-if="msg.feedbackSubmitted" class="feedback-thanks">
            ✨ 感谢反馈！知识图谱已更新该特征，下次绝不再犯。
          </div>

        </div>
      </div>

      <div v-if="isLoading" class="message-wrapper is-ai">
        <div class="avatar">AI</div>
        <div class="message-bubble loading-bubble">
          <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        </div>
      </div>
    </main>

    <footer class="chat-footer">
      <input
        type="text"
        v-model="userInput"
        @keyup.enter="sendMessage"
        placeholder="例如：冰箱有鸡蛋和西红柿，推荐个晚餐..."
        :disabled="isLoading"
      />
      <button @click="sendMessage" :disabled="isLoading || !userInput.trim()">
        发 送
      </button>
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { marked } from 'marked'

// --- 状态管理 ---
const messages = ref([
  {
    role: 'assistant',
    content: '你好！我是智能膳食助手。请问今天想吃什么？如果已在个人中心填写忌口和身体数据，系统会自动为您精准推荐哦！',
    feedback: null, showReasonOptions: false, feedbackSubmitted: false, exported: false
  }
])
const userInput = ref('')
const isLoading = ref(false)
const isWeightLossMode = ref(false)
const chatWindow = ref(null)

const userId = ref('')
const userName = ref('')

// 每次组件挂载时，从本地读取最新的用户身份
onMounted(() => {
  userId.value = localStorage.getItem('user_id') || ''
  userName.value = localStorage.getItem('user_name') || ''
})

// Markdown 文本格式化
const formatMessage = (text) => {
  return marked.parse(text || '')
}

// 自动滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (chatWindow.value) {
    chatWindow.value.scrollTop = chatWindow.value.scrollHeight
  }
}

// ==========================================
// 核心：发送聊天消息
// ==========================================
const sendMessage = async () => {
  const text = userInput.value.trim()
  if (!text || isLoading.value) return

  messages.value.push({ role: 'user', content: text })
  userInput.value = ''
  isLoading.value = true
  scrollToBottom()

  try {
    const requestBody = {
      query: text,
      mode: isWeightLossMode.value ? 'weight_loss' : 'standard',
      user_id: userId.value,
      session_id: userId.value ? `session_${userId.value}` : 'guest_session'
    }

    const response = await fetch('http://127.0.0.1:8000/api/chat/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    })

    const data = await response.json()

    if (response.ok) {
      // 记录今天日期，作为导出的默认日期
      const today = new Date().toISOString().split('T')[0]
      messages.value.push({
        role: 'assistant',
        content: data.response,
        feedback: null,
        showReasonOptions: false,
        feedbackSubmitted: false,
        exportDate: today,
        exported: false
      })
    } else {
      messages.value.push({ role: 'assistant', content: `[系统错误] ${data.error || '请求失败'}` })
    }
  } catch (error) {
    messages.value.push({ role: 'assistant', content: '[网络异常] 无法连接到后端，请确认 Django 已启动。' })
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

const isRecipeRecommendation = (text) => {
  if (!text) return false
  return (text.includes('热量') || text.includes('卡')) && text.includes('**')
}

const extractRecipeNames = (text) => {
  const names = [];
  // 匹配被 ** 包围的内容
  const regex = /\*\*([^\*]+)\*\*/g;
  let match;

  // 严苛的黑名单：只要名字里包含这些字，绝对不当成菜名去数据库查！
  const excludeWords = ['主食', '主菜', '配菜', '晚餐', '加餐', '早餐', '午餐', '注意', '建议', '总计', '热量', '蛋白质', '特点'];

  while ((match = regex.exec(text)) !== null) {
    let name = match[1].trim();
    name = name.replace(/^[0-9\.\-\s]+/, ''); // 剥离前面的序号，比如 "1. 宫保鸡丁" -> "宫保鸡丁"

    if (name && !excludeWords.includes(name) && name.length < 15) {
      names.push(name);
    }
  }
  return [...new Set(names)]; // 去重
}

const exportToMenu = async (msg) => {
  if (!msg.exportDate) {
    alert("请选择要导出的日期！");
    return;
  }

  const recipeNames = extractRecipeNames(msg.content);
  if (recipeNames.length === 0) {
    alert("未能从对话中提取到有效菜名。");
    return;
  }

  try {
    const response = await fetch('http://127.0.0.1:8000/api/recipe/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ names: recipeNames })
    });

    const resData = await response.json();

    if (response.ok && resData.data && resData.data.length > 0) {
      const storageKey = `diet_meals_${userId.value || 'guest'}`;
      const savedData = JSON.parse(localStorage.getItem(storageKey) || '{}');

      if (!savedData[msg.exportDate]) {
        savedData[msg.exportDate] = [];
      }

      const formattedRecipes = resData.data.map(item => {
        let detailsMd = '';

        // 1. 处理食材清单
        if (item.ingredients) {
          try {
            // 尝试把图谱里的 JSON 字符串解析为数组
            const ingArray = JSON.parse(item.ingredients);
            const ingList = ingArray.map(ing => `- ${ing.raw_text}`).join('\n');
            detailsMd += `**食材清单**：\n${ingList}\n\n`;
          } catch (e) {
            detailsMd += `**食材清单**：\n${item.ingredients}\n\n`;
          }
        }

        if (item.steps) {
          try {
            const stepArray = JSON.parse(item.steps);
            if (Array.isArray(stepArray)) {
               const stepList = stepArray.map((step, idx) => `${idx + 1}. ${step}`).join('\n');
               detailsMd += `**烹饪步骤**：\n${stepList}`;
            } else {
               detailsMd += `**烹饪步骤**：\n${item.steps}`;
            }
          } catch (e) {
            // 普通文本直接展示
            detailsMd += `**烹饪步骤**：\n${item.steps}`;
          }
        }

        if (!detailsMd) detailsMd = '暂无详细做法记录。';

        return {
          id: Date.now() + Math.random().toString(36).substr(2, 5),
          name: item.name,
          calories: item.calories || '未知',
          details: detailsMd
        };
      });

      savedData[msg.exportDate].push(...formattedRecipes);
      localStorage.setItem(storageKey, JSON.stringify(savedData));

      msg.exported = true; // 导出成功，切换 UI 状态
    } else {
      alert(`抱歉，数据库中未找到这几道菜的详细数据：${recipeNames.join(', ')}`);
    }
  } catch (error) {
    console.error("请求菜谱详情失败", error);
    alert("请求菜谱详情失败，请检查 Django 后端状态。");
  }
}

const rateMessage = (msg, type) => {
  if (msg.feedbackSubmitted) return
  msg.feedback = type
  if (type === 'down') {
    msg.showReasonOptions = true
  } else {
    msg.showReasonOptions = false
  }
}

const submitFeedback = async (msg, reason) => {
  if (!userId.value) {
    alert("请先前往「个人中心」登录/注册后再进行反馈！")
    return
  }
  msg.showReasonOptions = false
  msg.feedbackSubmitted = true

  try {
    await fetch('http://127.0.0.1:8000/api/feedback/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId.value,
        reason: reason,
        content: msg.content
      })
    })
  } catch (error) {
    console.error("反馈提交失败", error)
    msg.feedbackSubmitted = false
  }
}
</script>

<style scoped>
.chat-box-container {
  display: flex; flex-direction: column; width: 100%; max-width: 800px; height: 85vh;
  background: #ffffff; border-radius: 12px; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08); overflow: hidden;
}
.chat-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 15px 20px; background: #fafbfc; border-bottom: 1px solid #eaeaea;
}
.header-info h3 { margin: 0; font-size: 16px; color: #2c3e50; }
.welcome-text { font-size: 12px; color: #42b983; margin-top: 4px; display: block; }
.mode-switch label { display: flex; align-items: center; cursor: pointer; font-size: 13px; }
.mode-switch input { display: none; }
.slider {
  padding: 6px 12px; background: #ecf0f1; color: #7f8c8d; border-radius: 20px;
  transition: all 0.3s; user-select: none;
}
.slider.active { background: #e74c3c; color: white; font-weight: bold; }

.chat-window {
  flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; background-color: #f9fbfc;
}
.message-wrapper { display: flex; align-items: flex-start; max-width: 85%; }
.message-wrapper.is-user { align-self: flex-end; flex-direction: row-reverse; }

.avatar {
  width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: bold; color: white; margin: 0 10px; flex-shrink: 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.is-user .avatar { background: linear-gradient(135deg, #6dd5ed, #2193b0); }
.is-ai .avatar { background: linear-gradient(135deg, #84fab0, #8fd3f4); color: #2c3e50; }

.message-bubble {
  background: #ffffff; padding: 12px 16px; border-radius: 12px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
  line-height: 1.6; color: #34495e; word-break: break-word; font-size: 14px;
}
.is-user .message-bubble { background: #e1f0fa; border-top-right-radius: 2px; }
.is-ai .message-bubble { border-top-left-radius: 2px; border: 1px solid #f1f1f1; }

/* Markdown 穿透样式 */
.message-bubble :deep(p) { margin: 0 0 8px 0; }
.message-bubble :deep(p:last-child) { margin: 0; }
.message-bubble :deep(strong) { color: #2c3e50; font-weight: 600; }
.message-bubble :deep(ul), .message-bubble :deep(ol) { margin: 8px 0; padding-left: 20px; }
.message-bubble :deep(li) { margin-bottom: 4px; }

.loading-bubble { display: flex; gap: 4px; align-items: center; height: 24px; }
.dot { width: 6px; height: 6px; background: #bdc3c7; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

/* 菜谱导出模块样式 */
.export-module { margin-top: 15px; padding-top: 12px; border-top: 1px dashed #e1e8ed; }
.export-prompt p { font-size: 13px; color: #e67e22; margin: 0 0 8px 0; font-weight: bold; }
.export-controls { display: flex; gap: 10px; align-items: center; }
.mini-date { padding: 4px 8px; border: 1px solid #bdc3c7; border-radius: 6px; font-size: 12px; outline: none; }
.export-btn { background: #e67e22; color: white; border: none; padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: bold; cursor: pointer; transition: 0.2s; }
.export-btn:hover { background: #d35400; }
.export-success { font-size: 13px; color: #27ae60; font-weight: bold; }
.export-success a { color: #3498db; margin-left: 10px; text-decoration: none; }

/* RLHF 反馈系统 */
.feedback-actions { display: flex; gap: 10px; margin-top: 12px; padding-top: 12px; border-top: 1px dashed #eaeaea; }
.feedback-actions button {
  background: none; border: 1px solid #dfe6e9; padding: 4px 12px; border-radius: 12px;
  font-size: 12px; cursor: pointer; color: #7f8c8d; transition: all 0.2s;
}
.feedback-actions button.active { background: #fdf0ed; border-color: #e74c3c; color: #c0392b; font-weight: bold; }
.feedback-actions button:hover:not(.active):not(:disabled) { background: #f8f9fa; border-color: #bdc3c7; }
.feedback-actions button:disabled { opacity: 0.6; cursor: not-allowed; }

.reason-selector { margin-top: 10px; background-color: #f9fbfc; padding: 10px 12px; border-radius: 8px; border: 1px solid #e1e8ed; }
.reason-title { font-size: 12px; color: #34495e; margin: 0 0 8px 0; font-weight: 600; }
.reason-tags { display: flex; gap: 8px; flex-wrap: wrap; }
.r-tag {
  background-color: #ffffff; border: 1px solid #bdc3c7; color: #7f8c8d;
  font-size: 12px; padding: 4px 10px; border-radius: 14px; cursor: pointer; transition: all 0.2s;
}
.r-tag:hover { border-color: #e74c3c; color: #e74c3c; background-color: #fdf0ed; }
.feedback-thanks { margin-top: 10px; font-size: 12px; color: #27ae60; font-weight: bold; }

/* 底部输入框 */
.chat-footer { display: flex; padding: 15px 20px; background: #ffffff; border-top: 1px solid #eaeaea; gap: 12px; }
.chat-footer input {
  flex: 1; padding: 12px 16px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 14px;
  outline: none; transition: all 0.2s; background-color: #f8f9fa;
}
.chat-footer input:focus { border-color: #42b983; background-color: #ffffff; box-shadow: 0 0 0 3px rgba(66, 185, 131, 0.1); }
.chat-footer button {
  background: #42b983; color: white; border: none; padding: 0 24px; border-radius: 8px;
  font-weight: 600; cursor: pointer; transition: all 0.2s; font-size: 14px;
}
.chat-footer button:disabled { background: #bdc3c7; cursor: not-allowed; }
.chat-footer button:not(:disabled):hover { background: #3aa876; transform: translateY(-1px); }
</style>

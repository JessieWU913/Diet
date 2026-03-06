<template>
  <div class="meal-view-container">
    <header class="view-header">
      <h2>📅 个人菜谱单</h2>
      <div class="global-actions">
        <button class="action-btn list-btn" @click="generateShoppingList">🛒 购物清单</button>
        <button class="action-btn pic-btn" @click="exportBoardImage">🖼️ 导出总看板</button>
      </div>

      <div class="controls">
        <div class="view-toggle">
          <button :class="{ active: viewMode === '1day' }" @click="viewMode = '1day'">单日</button>
          <button :class="{ active: viewMode === '3days' }" @click="viewMode = '3days'">近3天</button>
        </div>
        <input type="date" v-model="selectedDate" class="date-picker" />
      </div>
    </header>

    <div class="menu-board">
      <div v-for="date in displayDates" :key="date" class="day-column">
        <h3 class="day-title">{{ formatDateLabel(date) }}</h3>
        <div v-if="getMealsForDate(date).length === 0" class="empty-state">
          <p>这一天还没有安排哦</p>
          <router-link to="/chat">去问问 Agent 吧</router-link>
        </div>
        <div class="meal-list" v-else>
          <MealCard
            v-for="recipe in getMealsForDate(date)"
            :key="recipe.id"
            :recipe="recipe" :date="date" @delete="removeRecipe"
          />
        </div>
      </div>
    </div>

    <div class="export-canvas-wrapper" ref="exportBoardRef">
      <div class="ec-header">
        <h2>📅 个人菜谱单 ({{ viewMode === '1day' ? '单日' : '近3天' }})</h2>
        <p>生成日期: {{ new Date().toLocaleDateString() }}</p>
      </div>
      <div class="ec-body">
        <div v-for="date in displayDates" :key="'exp'+date" class="ec-day-section">
          <h3 class="ec-day-title">{{ formatDateLabel(date) }}</h3>
          <div v-if="getMealsForDate(date).length === 0" class="ec-empty">无安排</div>

          <div v-for="recipe in getMealsForDate(date)" :key="'exp'+recipe.id" class="ec-recipe-card">
            <div class="ec-recipe-header">
              <span class="ec-name">{{ recipe.name }}</span>
              <span class="ec-cal">🔥 {{ recipe.calories }} kcal</span>
            </div>
            <div class="ec-details" v-html="formatCompactDetails(recipe.details)"></div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showShoppingModal" class="modal-overlay" @click.self="showShoppingModal = false">
      <div class="modal-content" ref="shoppingModalRef" :class="{ 'export-mode': isExportingList }">
        <div class="modal-header">
          <h3>🛒 智能购物清单 ({{ viewMode === '1day' ? '单日' : '近3天' }})</h3>
          <div class="header-right" v-if="!isExportingList">
            <button class="export-list-btn" @click="exportShoppingList">📸 导出长图</button>
            <button class="close-btn" @click="showShoppingModal = false">×</button>
          </div>
        </div>
        <div class="modal-body">
          <div v-if="shoppingList.length === 0" class="empty-list">当前视图暂无需要采购的食材。</div>
          <ul v-else class="shopping-list-ul">
            <li v-for="(item, index) in shoppingList" :key="index" class="shopping-item">
              <div class="item-main">
                <span class="item-name">{{ item.name }}</span>
                <span class="item-amount">{{ item.amount }}</span>
              </div>
              <div class="item-recipes">用料菜品：{{ item.recipes }}</div>
            </li>
          </ul>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import MealCard from '../components/MealCard.vue'
import html2canvas from 'html2canvas'
import { marked } from 'marked'

const userId = ref(localStorage.getItem('user_id') || 'guest')
const allMeals = ref({})
const selectedDate = ref(new Date().toISOString().split('T')[0])
const viewMode = ref('1day')

// 截图引用
const exportBoardRef = ref(null)
const shoppingModalRef = ref(null)

const showShoppingModal = ref(false)
const shoppingList = ref([])
const isExportingList = ref(false) // 购物清单导出锁

onMounted(() => loadMeals())

const loadMeals = () => {
  const savedData = localStorage.getItem(`diet_meals_${userId.value}`)
  if (savedData) allMeals.value = JSON.parse(savedData)
}

const saveMeals = () => {
  localStorage.setItem(`diet_meals_${userId.value}`, JSON.stringify(allMeals.value))
}

const displayDates = computed(() => {
  const dates = [selectedDate.value]
  if (viewMode.value === '3days') {
    const baseDate = new Date(selectedDate.value)
    for (let i = 1; i <= 2; i++) {
      const nextDate = new Date(baseDate)
      nextDate.setDate(baseDate.getDate() + i)
      dates.push(nextDate.toISOString().split('T')[0])
    }
  }
  return dates
})

const getMealsForDate = (date) => allMeals.value[date] || []
const formatDateLabel = (dateStr) => {
  const today = new Date().toISOString().split('T')[0]
  if (dateStr === today) return `今天 (${dateStr})`
  return dateStr
}

const removeRecipe = (recipeId, date) => {
  if (allMeals.value[date]) {
    allMeals.value[date] = allMeals.value[date].filter(r => r.id !== recipeId)
    saveMeals()
  }
}

// 🌟 核心：将食材列表压扁成“一行文字”，极大地节省截图空间
const formatCompactDetails = (detailsMd) => {
  if (!detailsMd) return '';
  let compactMd = detailsMd;

  // 使用正则提取 **🛒 食材清单** 到 **🍳 烹饪步骤** 之间的内容
  const ingMatch = compactMd.match(/\*\*🛒 食材清单\*\*：\n([\s\S]*?)(?=\n\n\*\*🍳|\n*$)/);
  if (ingMatch) {
    const listText = ingMatch[1];
    // 提取所有带横杠的列表项，去掉横杠，用逗号连接
    const inlineList = listText.split('\n')
      .map(line => line.replace(/^- /, '').trim())
      .filter(Boolean)
      .join('，');

    // 替换原有的列表结构为紧凑结构
    compactMd = compactMd.replace(ingMatch[0], `**🛒 食材：** ${inlineList}\n\n`);
  }
  return marked.parse(compactMd);
}

// 🌟 导出完整的总看板长图
const exportBoardImage = async () => {
  if (!exportBoardRef.value) return;
  try {
    const canvas = await html2canvas(exportBoardRef.value, {
      backgroundColor: '#f4f7f6',
      scale: 2,
      useCORS: true
    });
    const link = document.createElement('a');
    link.download = `完整菜谱单_${selectedDate.value}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  } catch (err) {
    alert("导出长图失败！");
    console.error(err);
  }
}

// 🌟 导出购物清单截图
const exportShoppingList = async () => {
  if (!shoppingModalRef.value) return;
  isExportingList.value = true; // 移除高度限制，准备截长图

  await nextTick();
  await new Promise(resolve => setTimeout(resolve, 100));

  try {
    const canvas = await html2canvas(shoppingModalRef.value, {
      backgroundColor: '#ffffff', scale: 2
    });
    const link = document.createElement('a');
    link.download = `购物清单_${selectedDate.value}.png`;
    link.href = canvas.toDataURL('image/png');
    link.click();
  } catch (err) {
    alert("生成图片失败！");
  } finally {
    isExportingList.value = false;
  }
}

// 生成智能购物清单 (解析、去重、合并)
const generateShoppingList = () => {
  const itemsMap = {}
  displayDates.value.forEach(date => {
    getMealsForDate(date).forEach(meal => {
      const match = meal.details.match(/\*\*🛒 食材清单\*\*：\n([\s\S]*?)(?=\n\n\*\*🍳|$)/)
      if (match) {
        match[1].split('\n').forEach(line => {
          if (line.trim().startsWith('-')) {
            const itemStr = line.replace('-', '').trim()
            const parseMatch = itemStr.match(/^([^\d]+)\s*(\d+.*|适量|少许)?$/)
            let name = itemStr, amount = '适量'

            if (parseMatch) {
              name = parseMatch[1].trim()
              amount = parseMatch[2] ? parseMatch[2].trim() : '适量'
            }

            if (!itemsMap[name]) {
              itemsMap[name] = { amount: amount, recipes: new Set() }
            } else {
              if (itemsMap[name].amount !== amount && itemsMap[name].amount !== '适量') {
                 if (amount !== '适量') itemsMap[name].amount += ` + ${amount}`
              }
            }
            itemsMap[name].recipes.add(meal.name)
          }
        })
      }
    })
  })

  shoppingList.value = Object.keys(itemsMap).map(name => ({
    name, amount: itemsMap[name].amount, recipes: Array.from(itemsMap[name].recipes).join('、')
  }))
  showShoppingModal.value = true
}
</script>

<style scoped>
.meal-view-container { max-width: 1000px; margin: 30px auto; padding: 0 20px; }
.view-header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; margin-bottom: 20px; gap: 15px; }
.view-header h2 { color: #2c3e50; margin: 0; }

.global-actions { display: flex; gap: 10px; }
.action-btn { padding: 8px 16px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s; font-size: 14px; }
.action-btn.list-btn { background: #e67e22; color: white; }
.action-btn.list-btn:hover { background: #d35400; }
.action-btn.pic-btn { background: #3498db; color: white; }
.action-btn.pic-btn:hover { background: #2980b9; }

.controls { display: flex; gap: 15px; align-items: center; }
.view-toggle { display: flex; background: #ecf0f1; border-radius: 8px; overflow: hidden; }
.view-toggle button { border: none; background: none; padding: 8px 16px; cursor: pointer; color: #7f8c8d; font-weight: bold; transition: all 0.2s; }
.view-toggle button.active { background: #42b983; color: white; }
.date-picker { padding: 8px 12px; border: 1px solid #dfe6e9; border-radius: 8px; font-family: inherit; color: #2c3e50; outline: none; }
.date-picker:focus { border-color: #42b983; }

.menu-board { display: flex; gap: 20px; align-items: flex-start; overflow-x: auto; padding-bottom: 20px; }
.day-column { flex: 1; min-width: 300px; background: #ffffff; border-radius: 12px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); border: 1px solid #eaeaea; }
.day-title { margin: 0 0 20px 0; font-size: 16px; color: #34495e; border-bottom: 2px solid #42b983; padding-bottom: 8px; display: inline-block; }

.empty-state { text-align: center; color: #95a5a6; padding: 40px 0; font-size: 14px; }
.empty-state a { color: #42b983; text-decoration: none; font-weight: bold; display: block; margin-top: 8px; }

/* ===================================== */
/* 🌟 专门用于截图的隐形结构 (不出现在屏幕可视区) */
/* ===================================== */
.export-canvas-wrapper {
  position: absolute; top: -9999px; left: -9999px; /* 把元素扔到十万八千里外 */
  width: 800px; background: #f4f7f6; padding: 30px; box-sizing: border-box; z-index: -1;
}
.ec-header { text-align: center; margin-bottom: 30px; }
.ec-header h2 { margin: 0; color: #2c3e50; font-size: 24px; }
.ec-header p { color: #7f8c8d; font-size: 14px; margin-top: 5px; }
.ec-day-section { margin-bottom: 30px; background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
.ec-day-title { color: #42b983; border-bottom: 1px solid #eee; padding-bottom: 10px; margin-top: 0; }
.ec-empty { color: #95a5a6; font-size: 14px; }
.ec-recipe-card { margin-top: 15px; border-bottom: 1px dashed #eee; padding-bottom: 15px; }
.ec-recipe-card:last-child { border-bottom: none; padding-bottom: 0; }
.ec-recipe-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.ec-name { font-weight: bold; font-size: 16px; color: #2c3e50; }
.ec-cal { color: #e74c3c; font-size: 13px; font-weight: bold; background: #fdf0ed; padding: 2px 8px; border-radius: 6px; }
.ec-details { font-size: 13px; color: #34495e; line-height: 1.6; }
.ec-details :deep(p) { margin: 0 0 6px 0; }
.ec-details :deep(strong) { color: #2c3e50; }

/* ===================================== */
/* 购物清单弹窗样式 */
/* ===================================== */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: white; width: 90%; max-width: 500px; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: #f8f9fa; border-bottom: 1px solid #eee; }
.modal-header h3 { margin: 0; font-size: 18px; color: #2c3e50; }
.header-right { display: flex; align-items: center; gap: 15px; }
.export-list-btn { background: #3498db; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: bold; cursor: pointer; transition: 0.2s; }
.export-list-btn:hover { background: #2980b9; }
.close-btn { background: none; border: none; font-size: 24px; color: #95a5a6; cursor: pointer; transition: 0.2s; line-height: 1; padding: 0; }
.close-btn:hover { color: #e74c3c; }

.modal-body { padding: 20px; max-height: 60vh; overflow-y: auto; }
.empty-list { text-align: center; color: #95a5a6; padding: 20px 0; }
.shopping-list-ul { list-style: none; padding: 0; margin: 0; }
.shopping-item { border-bottom: 1px dashed #eee; padding: 12px 0; }
.shopping-item:last-child { border-bottom: none; }
.item-main { display: flex; justify-content: space-between; margin-bottom: 6px; }
.item-name { font-weight: bold; color: #2c3e50; font-size: 15px; }
.item-amount { color: #e67e22; font-weight: bold; font-size: 14px; background: #fff3e0; padding: 2px 8px; border-radius: 6px; }
.item-recipes { font-size: 12px; color: #7f8c8d; }

/* 🌟 购物清单导出模式：去除高度限制 */
.export-mode .modal-body { max-height: none !important; overflow: visible !important; }
</style>

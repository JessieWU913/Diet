<template>
  <div class="diet-log">
    <div class="page-header">
      <h2>饮食记录</h2>
      <div class="date-nav">
        <button @click="changeDate(-1)">◀</button>
        <input type="date" v-model="selectedDate" />
        <button @click="changeDate(1)">▶</button>
      </div>
    </div>

    <!-- 搜索添加区 -->
    <div class="search-section">
      <div class="search-bar">
        <input v-model="searchQuery" @input="debounceSearch" placeholder="搜索食物，如：鸡蛋、米饭、西红柿炒蛋..." />
        <select v-model="addMealType" class="meal-type-select">
          <option value="breakfast">早餐</option>
          <option value="lunch">午餐</option>
          <option value="dinner">晚餐</option>
          <option value="snack">加餐</option>
        </select>
      </div>
      <div v-if="searchResults.length > 0" class="search-results">
        <div v-for="item in searchResults" :key="item.name" class="search-item" @click="openAddModal(item)">
          <span class="si-name">{{ item.name }}</span>
          <span class="si-type">{{ item.type === 'Recipe' ? '菜谱' : '食材' }}</span>
          <span class="si-cal">{{ item.calories || '—' }} kcal</span>
          <span class="si-add">+ 添加</span>
        </div>
      </div>
      <!-- 手动添加按钮 -->
      <button class="manual-add-btn" @click="openManualAdd">手动添加食物</button>
    </div>

    <!-- 今日记录 -->
    <div class="meal-grid">
      <div v-for="section in mealSections" :key="section.key" class="meal-section">
        <div class="ms-header">
          <span class="ms-icon">{{ section.icon }}</span>
          <span class="ms-title">{{ section.label }}</span>
          <span class="ms-total">{{ getSectionCalories(section.key) }} kcal</span>
        </div>
        <div v-if="getLogsForMeal(section.key).length === 0" class="ms-empty">暂无记录</div>
        <div v-for="log in getLogsForMeal(section.key)" :key="log.id" class="log-item" @click="openDetailModal(log)">
          <div class="li-info">
            <span class="li-name">{{ log.food_name }}</span>
            <span class="li-macros">
              {{ log.calories }} kcal · 蛋白 {{ log.protein }}g · 脂肪 {{ log.fat }}g · 碳水 {{ log.carbs }}g
            </span>
          </div>
          <button class="li-delete" @click.stop="deleteLog(log.id)">×</button>
        </div>
      </div>
    </div>

    <div class="daily-summary">
      <h3>每日汇总</h3>
      <div class="summary-grid">
        <div class="summary-card cal">
          <span class="sc-value">{{ dailyTotals.calories }}</span>
          <span class="sc-label">总热量 (kcal)</span>
        </div>
        <div class="summary-card protein">
          <span class="sc-value">{{ dailyTotals.protein }}g</span>
          <span class="sc-label">蛋白质</span>
        </div>
        <div class="summary-card fat">
          <span class="sc-value">{{ dailyTotals.fat }}g</span>
          <span class="sc-label">脂肪</span>
        </div>
        <div class="summary-card carbs">
          <span class="sc-value">{{ dailyTotals.carbs }}g</span>
          <span class="sc-label">碳水</span>
        </div>
      </div>
    </div>

    <!-- 添加食物弹窗（搜索结果或手动新增） -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="add-modal">
        <div class="am-header">
          <h3>{{ addForm.food_name ? '添加 ' + addForm.food_name : '手动添加食物' }}</h3>
          <button class="close-btn" @click="showAddModal = false">×</button>
        </div>
        <div class="am-body">
          <div class="am-row" v-if="!addForm.food_name">
            <label>食物名称</label>
            <input v-model="addForm.manual_name" placeholder="输入食物名称" />
          </div>
          <div class="am-row">
            <label>餐次</label>
            <select v-model="addForm.meal_type">
              <option value="breakfast">早餐</option>
              <option value="lunch">午餐</option>
              <option value="dinner">晚餐</option>
              <option value="snack">加餐</option>
            </select>
          </div>
          <div class="am-grid">
            <div class="am-field">
              <label>热量 (kcal)</label>
              <input type="number" v-model.number="addForm.calories" />
            </div>
            <div class="am-field">
              <label>蛋白质 (g)</label>
              <input type="number" v-model.number="addForm.protein" />
            </div>
            <div class="am-field">
              <label>脂肪 (g)</label>
              <input type="number" v-model.number="addForm.fat" />
            </div>
            <div class="am-field">
              <label>碳水 (g)</label>
              <input type="number" v-model.number="addForm.carbs" />
            </div>
          </div>
          <button class="am-save" @click="confirmAdd">确认添加</button>
        </div>
      </div>
    </div>

    <!-- 菜品详情弹窗 -->
    <div v-if="showDetailModal" class="modal-overlay" @click.self="showDetailModal = false">
      <div class="detail-modal">
        <div class="dm-header">
          <h3>{{ detailItem.food_name }}</h3>
          <button class="close-btn" @click="showDetailModal = false">×</button>
        </div>
        <div class="dm-body">
          <div class="dm-macros">
            <span>{{ detailItem.calories }} kcal</span>
            <span>{{ detailItem.protein }}g 蛋白</span>
            <span>{{ detailItem.fat }}g 脂肪</span>
            <span>{{ detailItem.carbs }}g 碳水</span>
          </div>
          <div v-if="detailLoading" class="dm-loading">加载详情中...</div>
          <div v-else-if="detailRecipe" class="dm-content">
            <div v-if="!isBlankRecipeText(detailRecipe.ingredients)" class="dm-section">
              <h4>食材清单</h4>
              <div v-html="formatIngredients(detailRecipe.ingredients)"></div>
            </div>
            <div v-if="!isBlankRecipeText(detailRecipe.steps)" class="dm-section">
              <h4>烹饪步骤</h4>
              <div v-html="formatSteps(detailRecipe.steps)"></div>
            </div>
            <div v-if="isBlankRecipeText(detailRecipe.ingredients) && isBlankRecipeText(detailRecipe.steps)" class="dm-empty">
              暂无详细菜谱信息
            </div>
          </div>
          <div v-else class="dm-empty">暂无详细菜谱信息</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import API from '../api.js'
import { formatRecipeStepsHtml } from '../utils/recipeStepFormatter.js'

const userId = localStorage.getItem('user_id') || ''
const selectedDate = ref(new Date().toISOString().split('T')[0])
const searchQuery = ref('')
const searchResults = ref([])
const addMealType = ref('lunch')
const logs = ref([])

// 添加弹窗
const showAddModal = ref(false)
const addForm = ref({ food_name: '', manual_name: '', meal_type: 'lunch', calories: 0, protein: 0, fat: 0, carbs: 0 })

// 详情弹窗
const showDetailModal = ref(false)
const detailItem = ref({})
const detailRecipe = ref(null)
const detailLoading = ref(false)

const isBlankRecipeText = (v) => {
  if (v === null || v === undefined) return true
  if (Array.isArray(v)) return v.length === 0
  const s = String(v).trim()
  return !s || s === '[]' || s === '{}' || s.toLowerCase() === 'null'
}

const mealSections = [
  { key: 'breakfast', label: '早餐', icon: '' },
  { key: 'lunch', label: '午餐', icon: '' },
  { key: 'dinner', label: '晚餐', icon: '' },
  { key: 'snack', label: '加餐', icon: '' },
]

let searchTimer = null
const debounceSearch = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    if (!searchQuery.value.trim()) { searchResults.value = []; return }
    try {
      const res = await API.get(`/food-search/?q=${searchQuery.value.trim()}`)
      searchResults.value = res.data.data || []
    } catch (e) { console.error(e) }
  }, 300)
}

const loadLogs = async () => {
  try {
    const res = await API.get(`/diet-log/?user_id=${userId}&date=${selectedDate.value}`)
    logs.value = res.data.logs || []
  } catch (e) { console.error(e) }
}

const openAddModal = (item) => {
  addForm.value = {
    food_name: item.name,
    manual_name: '',
    meal_type: addMealType.value,
    calories: item.calories || 0,
    protein: item.protein || 0,
    fat: item.fat || 0,
    carbs: item.carbs || 0
  }
  searchQuery.value = ''
  searchResults.value = []
  showAddModal.value = true
}

const openManualAdd = () => {
  addForm.value = { food_name: '', manual_name: '', meal_type: addMealType.value, calories: 0, protein: 0, fat: 0, carbs: 0 }
  showAddModal.value = true
}

const confirmAdd = async () => {
  const name = addForm.value.food_name || addForm.value.manual_name.trim()
  if (!name) { alert('请输入食物名称'); return }
  try {
    await API.post('/diet-log/', {
      user_id: userId, date: selectedDate.value,
      meal_type: addForm.value.meal_type, food_name: name,
      calories: addForm.value.calories, protein: addForm.value.protein,
      fat: addForm.value.fat, carbs: addForm.value.carbs, amount: 1
    })
    showAddModal.value = false
    await loadLogs()
  } catch (e) { alert('添加失败') }
}

const openDetailModal = async (log) => {
  detailItem.value = log
  detailRecipe.value = null
  detailLoading.value = true
  showDetailModal.value = true
  try {
    const res = await API.post('/recipe/', { names: [log.food_name] })
    if (res.data.data?.length > 0) {
      const r = res.data.data[0]
      const hasText = !isBlankRecipeText(r?.ingredients) || !isBlankRecipeText(r?.steps)
      if (hasText) {
        detailRecipe.value = r
      }
    }

    // 如果 recipe 接口返回为空/缺失，尝试使用 recipe-detail 兜底。
    if (!detailRecipe.value) {
      const fullRes = await API.get(`/recipe-detail/?name=${encodeURIComponent(log.food_name)}`)
      const full = fullRes?.data?.data
      if (full) {
        const ingredients = Array.isArray(full.ingredients_detail)
          ? JSON.stringify(full.ingredients_detail)
          : ''
        const steps = Array.isArray(full.steps_detail)
          ? JSON.stringify(full.steps_detail)
          : ''
        detailRecipe.value = {
          name: full.name || log.food_name,
          calories: detailItem.value.calories,
          protein: detailItem.value.protein,
          fat: detailItem.value.fat,
          carbs: detailItem.value.carbs,
          ingredients,
          steps
        }
      }
    }
  } catch (e) { console.error(e) }
  finally { detailLoading.value = false }
}

const formatIngredients = (raw) => {
  if (!raw) return ''
  if (Array.isArray(raw)) {
    return raw.map(i => `<span class="ing-tag">${(i?.raw_text || i?.ingredient_name || i?.name || i)}</span>`).join(' ')
  }
  try {
    const arr = JSON.parse(raw)
    if (Array.isArray(arr)) {
      return arr.map(i => `<span class="ing-tag">${i?.raw_text || i?.ingredient_name || i?.name || i}</span>`).join(' ')
    }
    return String(raw)
  } catch { return raw }
}

const formatSteps = (raw) => {
  return formatRecipeStepsHtml(raw)
}

const deleteLog = async (logId) => {
  try {
    await API.delete(`/diet-log/?user_id=${userId}&log_id=${logId}`)
    await loadLogs()
  } catch (e) { alert('删除失败') }
}

const getLogsForMeal = (type) => logs.value.filter(l => l.meal_type === type)
const getSectionCalories = (type) => {
  return Math.round(getLogsForMeal(type).reduce((sum, l) => sum + (l.calories || 0), 0))
}

const dailyTotals = computed(() => {
  const totals = { calories: 0, protein: 0, fat: 0, carbs: 0 }
  logs.value.forEach(l => {
    totals.calories += l.calories || 0
    totals.protein += l.protein || 0
    totals.fat += l.fat || 0
    totals.carbs += l.carbs || 0
  })
  return {
    calories: Math.round(totals.calories),
    protein: Math.round(totals.protein),
    fat: Math.round(totals.fat),
    carbs: Math.round(totals.carbs)
  }
})

const changeDate = (offset) => {
  const d = new Date(selectedDate.value)
  d.setDate(d.getDate() + offset)
  selectedDate.value = d.toISOString().split('T')[0]
}

watch(selectedDate, () => loadLogs())
onMounted(() => loadLogs())
</script>

<style scoped>
.diet-log { width: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h2 { font-size: 22px; color: #2d3436; }
.date-nav { display: flex; align-items: center; gap: 8px; }
.date-nav button { background: #fff; border: 1px solid #dfe6e9; border-radius: 8px; padding: 8px 12px; cursor: pointer; font-size: 14px; }
.date-nav button:hover { background: #f0f4f8; }
.date-nav input { padding: 8px 12px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 14px; }

.search-section { margin-bottom: 24px; position: relative; }
.search-bar { display: flex; gap: 8px; }
.search-bar input { flex: 1; padding: 12px 16px; border: 2px solid #dfe6e9; border-radius: 12px; font-size: 15px; outline: none; transition: .2s; }
.search-bar input:focus { border-color: #7761e5; }
.meal-type-select { padding: 10px 14px; border: 1px solid #dfe6e9; border-radius: 10px; font-size: 14px; background: #fff; }
.manual-add-btn { margin-top: 8px; padding: 8px 16px; background: #f8f9fa; border: 1px dashed #b2bec3; border-radius: 8px; cursor: pointer; font-size: 13px; color: #636e72; transition: .2s; }
.manual-add-btn:hover { background: #ede9fc; border-color: #7761e5; color: #7761e5; }

.search-results { position: absolute; top: 52px; left: 0; right: 0; background: #fff; border: 1px solid #dfe6e9; border-radius: 12px; margin-top: 4px; max-height: 300px; overflow-y: auto; z-index: 10; box-shadow: 0 8px 24px rgba(0,0,0,.1); }
.search-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; transition: .15s; }
.search-item:hover { background: #f7f5fd; }
.si-name { flex: 1; font-weight: 500; color: #2d3436; }
.si-type { font-size: 12px; color: #b2bec3; background: #f0f4f8; padding: 2px 8px; border-radius: 10px; }
.si-cal { font-size: 13px; color: #636e72; min-width: 70px; text-align: right; }
.si-add { color: #7761e5; font-weight: 600; font-size: 13px; }

.meal-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 24px; }
.meal-section { background: #fff; border-radius: 14px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.ms-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.ms-icon { font-size: 20px; }
.ms-title { font-size: 16px; font-weight: 600; color: #2d3436; flex: 1; }
.ms-total { font-size: 14px; color: #636e72; font-weight: 500; }
.ms-empty { color: #b2bec3; font-size: 14px; padding: 8px 0; }

.log-item { display: flex; align-items: center; padding: 10px 0; border-top: 1px solid #f0f2f5; cursor: pointer; transition: .15s; border-radius: 6px; }
.log-item:hover { background: #f8f9fa; }
.li-info { flex: 1; }
.li-name { display: block; font-weight: 500; color: #2d3436; font-size: 15px; }
.li-macros { display: block; font-size: 12px; color: #b2bec3; margin-top: 2px; }
.li-delete { background: none; border: none; color: #e74c3c; font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 6px; }
.li-delete:hover { background: #fff0f0; }

.daily-summary { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.04); width: 100%; }
.daily-summary h3 { margin-bottom: 16px; color: #2d3436; font-size: 16px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.summary-card { text-align: center; padding: 16px; border-radius: 12px; }
.summary-card.cal { background: #ede9fc; }
.summary-card.protein { background: #e3f5e8; }
.summary-card.fat { background: #fef5e0; }
.summary-card.carbs { background: #e6f2fe; }
.sc-value { display: block; font-size: 24px; font-weight: 700; color: #2d3436; }
.sc-label { display: block; font-size: 12px; color: #636e72; margin-top: 4px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.add-modal { background: #fff; width: 440px; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.15); }
.am-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid #f0f2f5; }
.am-header h3 { font-size: 17px; color: #2d3436; }
.am-body { padding: 24px; }
.am-row { margin-bottom: 16px; }
.am-row label { display: block; font-size: 13px; font-weight: 600; color: #636e72; margin-bottom: 6px; }
.am-row input, .am-row select { width: 100%; padding: 10px 12px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 14px; }
.am-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }
.am-field label { display: block; font-size: 12px; font-weight: 600; color: #636e72; margin-bottom: 4px; }
.am-field input { width: 100%; padding: 10px 12px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 14px; }
.am-save { width: 100%; padding: 12px; background: #7761e5; color: #fff; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; }
.am-save:hover { background: #6350d0; }

.detail-modal { background: #fff; width: 520px; max-height: 80vh; overflow-y: auto; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.15); }
.dm-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid #f0f2f5; }
.dm-header h3 { font-size: 18px; color: #2d3436; }
.close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #b2bec3; }
.dm-body { padding: 24px; }
.dm-macros { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.dm-macros span { font-size: 14px; padding: 6px 12px; background: #f8f9fa; border-radius: 8px; color: #636e72; }
.dm-section { margin-bottom: 20px; }
.dm-section h4 { font-size: 15px; color: #2d3436; margin-bottom: 10px; }
.dm-loading, .dm-empty { text-align: center; padding: 20px; color: #b2bec3; }
.dm-content :deep(.ing-tag) { display: inline-block; background: #ede9fc; color: #7761e5; padding: 3px 10px; border-radius: 12px; margin: 2px 4px; font-size: 13px; }
.dm-content :deep(.recipe-steps-list) { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.dm-content :deep(.recipe-step-item) { display: flex; align-items: flex-start; gap: 10px; }
.dm-content :deep(.step-index) {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: #efe8ff;
  border: 1px solid #d6c5ff;
  color: #5e46c8;
  font-weight: 700;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 24px;
  margin-top: 2px;
}
.dm-content :deep(.step-text) { color: #2d3436; line-height: 1.72; font-size: 14px; }
.dm-content :deep(.step-verb) {
  display: inline-block;
  margin: 0 2px;
  padding: 0 6px;
  border-radius: 999px;
  background: #fff4d6;
  color: #9a5d00;
  font-weight: 700;
}
</style>

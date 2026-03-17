<template>
  <div class="recipe-view">
    <div class="page-header">
      <h2>食谱推荐</h2>
      <button class="refresh-btn" @click="loadRecommendations" :disabled="loading">
        {{ loading ? '加载中...' : '换一批' }}
      </button>
    </div>

    <div class="filter-bar">
      <div class="filter-item">
        <label>热量上限</label>
        <div class="input-wrap">
          <input type="number" v-model.number="filters.maxCalories" placeholder="700" />
          <span class="unit">kcal</span>
        </div>
      </div>
      <div class="filter-item">
        <label>蛋白质下限</label>
        <div class="input-wrap">
          <input type="number" v-model.number="filters.minProtein" placeholder="0" />
          <span class="unit">g</span>
        </div>
      </div>
      <div class="filter-item">
        <label>脂肪上限</label>
        <div class="input-wrap">
          <input type="number" v-model.number="filters.maxFat" placeholder="50" />
          <span class="unit">g</span>
        </div>
      </div>
      <div class="filter-action">
        <button class="reset-btn" @click="resetFilters">重置</button>
        <button class="apply-btn" @click="applyFilters">应用筛选</button>
      </div>
    </div>

    <div v-if="loading" class="loading-state">正在为您智能配餐...</div>
    <div v-else class="meals-grid">
      <div v-for="section in mealSections" :key="section.key" class="meal-column">
        <div class="mc-header">
          <component :is="section.icon" class="mc-icon" :size="20" :stroke-width="1.9" />
          <span class="mc-title">{{ section.label }}</span>
        </div>
        <div v-if="!recommendations[section.key] || recommendations[section.key].length === 0" class="mc-empty">
          暂无推荐
        </div>
        <div v-for="recipe in getFilteredRecipes(section.key)" :key="recipe.name" class="recipe-card">
          <div class="rc-head">
            <div class="rc-name">{{ recipe.name }}</div>
            <span class="recipe-kind">{{ recipe.category || '未分类' }}</span>
          </div>
          <div class="rc-macros">
            <span class="macro cal">热量 {{ recipe.calories || '—' }} kcal</span>
            <span class="macro protein">蛋白 {{ recipe.protein || '—' }}g</span>
            <span class="macro fat">脂肪 {{ recipe.fat || '—' }}g</span>
            <span class="macro carbs">碳水 {{ recipe.carbs || '—' }}g</span>
          </div>
          <div class="rc-actions">
            <button class="rc-add" @click="addToDietLog(recipe, section.key)">记录饮食</button>
            <button class="rc-detail" @click="viewDetail(recipe)">查看做法</button>
            <button class="rc-fav" @click="addToCollection(recipe)">收藏</button>
          </div>
        </div>

        <div class="mc-subtotal" v-if="getFilteredRecipes(section.key).length > 0">
          小计：{{ getMealTotalCalories(section.key) }} kcal
        </div>
      </div>
    </div>

    <div v-if="Object.keys(exportedMeals).length > 0" class="exported-section">
      <h3>AI 导出的菜谱</h3>
      <div v-for="(recipes, date) in exportedMeals" :key="date" class="exported-day">
        <h4 class="ed-date">{{ date }}</h4>
        <div class="exported-grid">
          <div v-for="r in recipes" :key="r.id" class="exported-card">
            <div class="ec-name">{{ r.name }}</div>
            <div class="ec-macros">
              <span>热量 {{ r.calories || '—' }} kcal</span>
              <span v-if="r.protein">蛋白 {{ r.protein }}g</span>
              <span v-if="r.fat">脂肪 {{ r.fat }}g</span>
              <span v-if="r.carbs">碳水 {{ r.carbs }}g</span>
            </div>
            <div class="ec-actions">
              <button class="ec-log" @click="openRecordMealModal(r)">记录饮食</button>
              <button class="ec-detail" @click="viewDetail(r)">查看做法</button>
              <button class="ec-fav" @click="addToCollection(r)">收藏</button>
              <button class="ec-del" @click="deleteExportedMeal(date, r.id)">删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showDetail" class="modal-overlay" @click.self="showDetail = false">
      <div class="detail-modal">
        <div class="dm-header">
          <h3>{{ detailRecipe.name }}</h3>
          <button class="close-btn" @click="showDetail = false">×</button>
        </div>
        <div class="dm-body">
          <div class="dm-macros">
            <span>热量 {{ detailRecipe.calories }} kcal</span>
            <span>蛋白 {{ detailRecipe.protein }}g</span>
            <span>脂肪 {{ detailRecipe.fat }}g</span>
            <span>碳水 {{ detailRecipe.carbs }}g</span>
            <div v-if="detailData && detailData.source" class="dm-source">来源：{{ sourceLabel(detailData.source, detailData.matched_name) }}</div>
          </div>
          <div v-if="detailData" class="dm-content">
            <div v-if="detailData.ingredients" class="dm-section">
              <h4>食材清单</h4>
              <div v-html="formatIngredients(detailData.ingredients)"></div>
            </div>
            <div v-if="detailData.steps" class="dm-section">
              <h4>烹饪步骤</h4>
              <div v-html="formatSteps(detailData.steps)"></div>
            </div>
          </div>
          <div v-else class="dm-loading">加载中...</div>
        </div>
      </div>
    </div>

    <div v-if="showRecordMealModal" class="modal-overlay" @click.self="showRecordMealModal = false">
      <div class="record-modal">
        <div class="rm-header">
          <h3>记录饮食</h3>
          <button class="close-btn" @click="showRecordMealModal = false">×</button>
        </div>
        <div class="rm-body">
          <p class="rm-name">{{ pendingRecordRecipe?.name }}</p>
          <label>选择餐次</label>
          <select v-model="pendingMealType">
            <option value="breakfast">早餐</option>
            <option value="lunch">午餐</option>
            <option value="dinner">晚餐</option>
          </select>
          <button class="rm-save" @click="confirmRecordMeal">确认记录</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Coffee, Soup, MoonStar } from 'lucide-vue-next'
import API from '../api.js'
import { formatRecipeStepsHtml } from '../utils/recipeStepFormatter.js'

const userId = localStorage.getItem('user_id') || ''
const loading = ref(false)
const recommendations = ref({ breakfast: [], lunch: [], dinner: [] })
const showDetail = ref(false)
const detailRecipe = ref({})
const detailData = ref(null)
const showRecordMealModal = ref(false)
const pendingRecordRecipe = ref(null)
const pendingMealType = ref('lunch')

const filters = reactive({ maxCalories: 700, minProtein: 0, maxFat: 50 })

const mealSections = [
  { key: 'breakfast', label: '早餐', icon: Coffee },
  { key: 'lunch', label: '午餐', icon: Soup },
  { key: 'dinner', label: '晚餐', icon: MoonStar },
]

const getLocalDateString = () => {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const exportedMeals = ref({})
const loadExportedMeals = async () => {
  const key = `diet_meals_${userId || 'guest'}`
  const data = localStorage.getItem(key)
  if (!data) return
  const parsed = JSON.parse(data)

  const needLookup = []
  for (const date in parsed) {
    for (const r of parsed[date]) {
      if (!r.calories || r.calories === 0) needLookup.push(r.name)
    }
  }

  if (needLookup.length > 0) {
    try {
      const res = await API.post('/recipe/', { names: [...new Set(needLookup)] })
      const dbMap = {}
      for (const item of (res.data.data || [])) {
        dbMap[item.name] = item
      }
      for (const date in parsed) {
        for (const r of parsed[date]) {
          if ((!r.calories || r.calories === 0) && dbMap[r.name]) {
            const db = dbMap[r.name]
            r.calories = db.calories || 0
            r.protein = db.protein || 0
            r.fat = db.fat || 0
            r.carbs = db.carbs || 0
            r.ingredients = db.ingredients || ''
            r.steps = db.steps || ''
          }
        }
      }
      localStorage.setItem(key, JSON.stringify(parsed))
    } catch (e) { console.error('补全菜谱信息失败', e) }
  }

  exportedMeals.value = parsed
}

const loadRecommendations = async () => {
  loading.value = true
  try {
    const res = await API.get(`/recommend-meals/?user_id=${userId}`)
    recommendations.value = {
      breakfast: res.data.breakfast || [],
      lunch: res.data.lunch || [],
      dinner: res.data.dinner || []
    }
  } catch (e) { console.error('推荐失败', e) }
  finally { loading.value = false }
}

const getFilteredRecipes = (mealKey) => {
  const recipes = recommendations.value[mealKey] || []
  return recipes.filter(r => {
    if (filters.maxCalories && r.calories > filters.maxCalories) return false
    if (filters.minProtein && (r.protein || 0) < filters.minProtein) return false
    if (filters.maxFat && (r.fat || 0) > filters.maxFat) return false
    return true
  })
}

const getMealTotalCalories = (mealKey) => {
  return Math.round(getFilteredRecipes(mealKey).reduce((s, r) => s + (r.calories || 0), 0))
}

const applyFilters = () => { /* reactive filters auto-apply */ }

const resetFilters = () => {
  filters.maxCalories = 700
  filters.minProtein = 0
  filters.maxFat = 50
}

const addToDietLog = async (recipe, mealType) => {
  if (!userId) { alert('请先登录！'); return }
  try {
    await API.post('/diet-log/', {
      user_id: userId,
      date: getLocalDateString(),
      meal_type: mealType,
      food_name: recipe.name,
      calories: recipe.calories || 0,
      protein: recipe.protein || 0,
      fat: recipe.fat || 0,
      carbs: recipe.carbs || 0,
      amount: 1
    })
    alert(`已将「${recipe.name}」记入今日${mealType === 'breakfast' ? '早餐' : mealType === 'lunch' ? '午餐' : '晚餐'}`)
  } catch (e) { alert('记录失败') }
}

const openRecordMealModal = (recipe) => {
  pendingRecordRecipe.value = recipe
  pendingMealType.value = 'lunch'
  showRecordMealModal.value = true
}

const confirmRecordMeal = async () => {
  const recipe = pendingRecordRecipe.value
  if (!recipe) return
  await addToDietLog(recipe, pendingMealType.value)
  showRecordMealModal.value = false
  pendingRecordRecipe.value = null
}

const viewDetail = async (recipe) => {
  detailRecipe.value = recipe
  detailData.value = null
  showDetail.value = true
  try {
    const res = await API.post('/recipe/', { names: [recipe.name] })
    if (res.data.data && res.data.data.length > 0) {
      detailData.value = res.data.data[0]
    }
  } catch (e) { console.error(e) }
}

const formatIngredients = (raw) => {
  if (!raw) return ''
  try {
    const arr = JSON.parse(raw)
    return arr.map(i => `<span class="ing-tag">${i.raw_text || i}</span>`).join(' ')
  } catch { return raw }
}

const formatSteps = (raw) => {
  return formatRecipeStepsHtml(raw)
}

const sourceLabel = (source, matchedName) => {
  if (source === 'exact') return '知识图谱精确匹配'
  if (source === 'fuzzy') return matchedName ? `知识图谱模糊匹配（匹配到：${matchedName}）` : '知识图谱模糊匹配'
  if (source === 'ai_fallback') return 'AI 补全估算'
  return '未知来源'
}

const persistExportedMeals = () => {
  const key = `diet_meals_${userId || 'guest'}`
  localStorage.setItem(key, JSON.stringify(exportedMeals.value))
}

const deleteExportedMeal = (date, mealId) => {
  const dayMeals = exportedMeals.value[date] || []
  const nextMeals = dayMeals.filter(m => m.id !== mealId)
  if (nextMeals.length > 0) {
    exportedMeals.value[date] = nextMeals
  } else {
    delete exportedMeals.value[date]
  }
  exportedMeals.value = { ...exportedMeals.value }
  persistExportedMeals()
}

const addToCollection = async (recipe) => {
  if (!userId) { alert('请先登录！'); return }
  try {
    await API.post('/collection/', {
      user_id: userId,
      recipe_name: recipe.name,
      calories: recipe.calories || 0,
      protein: recipe.protein || 0,
      fat: recipe.fat || 0,
      carbs: recipe.carbs || 0,
      ingredients: recipe.ingredients || '',
      steps: recipe.steps || ''
    })
    alert(`已收藏「${recipe.name}」`)
  } catch (e) { alert('收藏失败，可能已经收藏过了') }
}

onMounted(() => {
  loadRecommendations()
  loadExportedMeals()
})
</script>

<style scoped>
.recipe-view { width: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 22px; color: #2d3436; }
.refresh-btn { padding: 10px 20px; background: #7761e5; color: #fff; border: none; border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 14px; }
.refresh-btn:hover { background: #6350d0; }
.refresh-btn:disabled { background: #95a5a6; }

.filter-bar {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  align-items: end;
  gap: 14px;
  background: #fff;
  padding: 16px 20px;
  border-radius: 12px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
.filter-item { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.filter-item label { font-size: 12px; color: #636e72; font-weight: 600; }
.input-wrap { position: relative; }
.filter-item input {
  width: 100%;
  padding: 9px 40px 9px 10px;
  border: 1px solid #dfe6e9;
  border-radius: 8px;
  font-size: 14px;
}
.unit {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  color: #94a1b0;
}
.filter-action { display: flex; justify-content: flex-end; gap: 8px; }
.reset-btn,
.apply-btn {
  padding: 9px 16px;
  border: 1px solid #dfe6e9;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.apply-btn {
  min-width: 132px;
  background: #f0f4f8;
}

.reset-btn {
  min-width: 100px;
  background: #fff;
}

.reset-btn:hover,
.apply-btn:hover {
  background: #eaf0f6;
}

.loading-state { text-align: center; padding: 60px; color: #636e72; font-size: 16px; }

.meals-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
.meal-column { background: #fff; border-radius: 14px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.mc-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 2px solid #f0f2f5; }
.mc-icon { color: #2d3436; flex: 0 0 auto; }
.mc-title { font-size: 17px; font-weight: 700; color: #2d3436; }
.mc-empty { color: #b2bec3; font-size: 14px; text-align: center; padding: 20px 0; }

.recipe-card { padding: 14px 0; border-bottom: 1px solid #f8f9fa; }
.rc-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.rc-name { font-weight: 600; color: #2d3436; font-size: 15px; margin-bottom: 0; }
.recipe-kind {
  flex: 0 0 auto;
  font-size: 11px;
  color: #4f5f76;
  background: #eef3fb;
  border: 1px solid #d8e2f1;
  border-radius: 999px;
  padding: 2px 8px;
}
.rc-macros { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.macro { font-size: 11px; padding: 3px 8px; border-radius: 10px; background: #f8f9fa; color: #636e72; }
.rc-actions { display: flex; gap: 6px; }
.rc-add, .rc-detail { padding: 6px 10px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 12px; cursor: pointer; background: #fff; transition: .2s; }
.rc-add:hover { background: #ede9fc; border-color: #7761e5; color: #7761e5; }
.rc-detail:hover { background: #e6f2fe; border-color: #8ac3f9; color: #2b7de9; }
.rc-fav { padding: 6px 10px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 12px; cursor: pointer; background: #fff; transition: .2s; }
.rc-fav:hover { background: #fef5e0; border-color: #f6c342; color: #d4a017; }

.mc-subtotal { margin-top: 12px; padding-top: 12px; border-top: 2px solid #f0f2f5; font-size: 14px; font-weight: 600; color: #636e72; text-align: right; }

.exported-section { margin-top: 32px; }
.exported-section h3 { font-size: 18px; color: #2d3436; margin-bottom: 16px; }
.exported-day { margin-bottom: 20px; }
.ed-date { font-size: 14px; color: #636e72; margin-bottom: 10px; font-weight: 600; }
.exported-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.exported-card { background: #fff; border-radius: 12px; padding: 14px 16px; box-shadow: 0 2px 8px rgba(0,0,0,.06); display: flex; flex-direction: column; gap: 8px; }
.ec-name { font-weight: 600; color: #2d3436; font-size: 15px; }
.ec-macros { display: flex; flex-wrap: wrap; gap: 4px; }
.ec-macros span { font-size: 11px; padding: 3px 8px; background: #f8f9fa; border-radius: 8px; color: #636e72; }
.ec-actions { display: flex; gap: 6px; margin-top: 2px; }
.ec-log { padding: 5px 10px; border: 1px solid #7761e5; border-radius: 8px; font-size: 12px; cursor: pointer; background: #fff; color: #7761e5; transition: .2s; }
.ec-log:hover { background: #efeaff; }
.ec-detail { padding: 5px 10px; border: 1px solid #2196f3; border-radius: 8px; font-size: 12px; cursor: pointer; background: #fff; color: #2196f3; transition: .2s; }
.ec-detail:hover { background: #e3f2fd; }
.ec-fav { padding: 5px 10px; border: 1px solid #dfe6e9; border-radius: 8px; font-size: 12px; cursor: pointer; background: #fff; transition: .2s; }
.ec-fav:hover { background: #fef5e0; border-color: #f6c342; color: #d4a017; }
.ec-del { padding: 5px 10px; border: 1px solid #e6d1d1; border-radius: 8px; font-size: 12px; cursor: pointer; background: #fff; color: #b35b5b; transition: .2s; }
.ec-del:hover { background: #fff1f1; border-color: #d98c8c; color: #9f3d3d; }

/* 详情弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.detail-modal { background: #fff; width: 520px; max-height: 80vh; overflow-y: auto; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.15); }
.dm-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid #f0f2f5; }
.dm-header h3 { font-size: 18px; color: #2d3436; }
.close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #b2bec3; }
.dm-body { padding: 24px; }
.dm-macros { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
.dm-source { font-size: 12px; color: #6c7a89; margin-bottom: 10px; }
.dm-macros span { font-size: 14px; padding: 6px 12px; background: #f8f9fa; border-radius: 8px; color: #636e72; }
.dm-section { margin-bottom: 20px; }
.dm-section h4 { font-size: 15px; color: #2d3436; margin-bottom: 10px; }
.dm-loading { text-align: center; padding: 20px; color: #b2bec3; }
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

.record-modal {
  background: #fff;
  width: 360px;
  border-radius: 14px;
  box-shadow: 0 20px 60px rgba(0,0,0,.16);
  border: 1px solid #e9edf3;
}

.rm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid #eef2f6;
}

.rm-header h3 {
  margin: 0;
  font-size: 17px;
  color: #2d3436;
}

.rm-body {
  padding: 16px 18px 18px;
  display: grid;
  gap: 10px;
}

.rm-name {
  margin: 0;
  font-size: 14px;
  color: #4e5968;
  font-weight: 700;
}

.rm-body label {
  font-size: 13px;
  color: #647285;
}

.rm-body select {
  border: 1px solid #dfe6e9;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 14px;
}

.rm-save {
  border: 1px solid #1f2329;
  background: #fff;
  color: #1f2329;
  border-radius: 8px;
  padding: 9px 12px;
  font-size: 13px;
  cursor: pointer;
}

.rm-save:hover { background: #f5f7fa; }

@media (max-width: 1100px) {
  .filter-bar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filter-action { grid-column: 1 / -1; justify-content: flex-end; }
}

@media (max-width: 700px) {
  .filter-bar { grid-template-columns: 1fr; }
  .filter-action { justify-content: stretch; }
  .reset-btn,
  .apply-btn { width: 100%; }
}
</style>

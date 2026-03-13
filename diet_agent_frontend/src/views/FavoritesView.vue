<template>
  <div class="favorites-view">
    <div class="page-header">
      <h2>我的收藏夹</h2>
      <button class="export-btn" @click="exportShoppingList" :disabled="collections.length === 0">导出购物清单</button>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>
    <div v-else-if="collections.length === 0" class="empty-state">
      <p>暂无收藏，去食谱推荐页收藏你喜欢的菜品吧！</p>
    </div>

    <div v-else class="fav-list">
      <div v-for="(item, idx) in collections" :key="idx" class="fav-card">
        <div class="fc-header">
          <h3>{{ item.recipe_name }}</h3>
          <div class="fc-btns">
            <button class="fc-detail" @click="viewDetail(item)">查看做法</button>
            <button class="fc-remove" @click="removeCollection(item.recipe_name)">取消收藏</button>
          </div>
        </div>
        <div class="fc-macros">
          <span>{{ item.calories || '—' }} kcal</span>
          <span>{{ item.protein || '—' }}g 蛋白</span>
          <span>{{ item.fat || '—' }}g 脂肪</span>
          <span>{{ item.carbs || '—' }}g 碳水</span>
        </div>

        <div class="fc-ingredients" v-if="item.parsedIngredients && item.parsedIngredients.length > 0">
          <h4>食材清单</h4>
          <div v-for="(ing, iIdx) in item.parsedIngredients" :key="iIdx" class="ing-row">
            <span class="ing-name">{{ ing.name }}</span>
            <span v-if="ing.amount" class="ing-amount">{{ ing.amount }}</span>
            <button class="ing-replace-btn" @click="findSimilar(item, iIdx, ing.lookupName)">替换</button>
            <button class="ing-conflict-btn" @click="checkConflict(item, iIdx, ing.lookupName)">同食禁忌</button>

            <div v-if="ing.showSimilar" class="similar-panel">
              <div v-if="ing.similarLoading" class="sp-loading">搜索中...</div>
              <div v-else-if="ing.similars && ing.similars.length > 0" class="sp-list">
                <span v-for="s in ing.similars" :key="s" class="sp-tag" @click="replaceIngredient(item, iIdx, s)">{{ s }}</span>
              </div>
              <div v-else class="sp-empty">未找到相似食材</div>
            </div>

            <div v-if="ing.showConflict" class="conflict-panel">
              <div v-if="ing.conflictLoading" class="cp-loading">查询中...</div>
              <div v-else-if="ing.conflicts && ing.conflicts.length > 0" class="cp-list">
                <span v-for="c in ing.conflicts" :key="c" class="cp-tag">{{ c }}</span>
              </div>
              <div v-else class="cp-safe">暂无已知同食禁忌</div>
            </div>
          </div>
        </div>
        <div class="fc-ingredients-empty" v-else>
          食材补全中或暂无食材信息
        </div>
      </div>
    </div>

    <div v-if="showDetail" class="modal-overlay" @click.self="closeDetail">
      <div class="detail-modal">
        <div class="dm-header">
          <h3>{{ detailRecipe.recipe_name }}</h3>
          <button class="close-btn" @click="closeDetail">×</button>
        </div>
        <div class="dm-body">
          <div class="dm-macros">
            <span>{{ detailRecipe.calories || '—' }} kcal</span>
            <span>{{ detailRecipe.protein || '—' }}g 蛋白</span>
            <span>{{ detailRecipe.fat || '—' }}g 脂肪</span>
            <span>{{ detailRecipe.carbs || '—' }}g 碳水</span>
          </div>
          <div v-if="detailLoading" class="dm-loading">AI 正在补全做法...</div>
          <div>
            <div v-if="detailData && detailData.ingredients" class="dm-section">
              <h4>食材清单</h4>
              <div class="ing-tags" v-html="formatIngredients(detailData.ingredients)"></div>
            </div>
            <div v-else-if="detailRecipe.ingredients" class="dm-section">
              <h4>食材清单</h4>
              <div class="ing-tags" v-html="formatIngredients(detailRecipe.ingredients)"></div>
            </div>
            <div v-if="detailData && detailData.steps" class="dm-section">
              <h4>烹饪步骤</h4>
              <div class="steps-content" v-html="formatSteps(detailData.steps)"></div>
            </div>
            <div v-else-if="detailRecipe.steps" class="dm-section">
              <h4>烹饪步骤</h4>
              <div class="steps-content" v-html="formatSteps(detailRecipe.steps)"></div>
            </div>
            <div v-if="!detailLoading && !detailData && !detailRecipe.ingredients && !detailRecipe.steps" class="dm-empty">
              暂无详细信息
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showShoppingList" class="modal-overlay" @click.self="showShoppingList = false">
      <div class="shopping-modal">
        <div class="sm-header">
          <h3>购物清单</h3>
          <button class="close-btn" @click="showShoppingList = false">×</button>
        </div>
        <div class="sm-body">
          <div v-if="shoppingGroups.length === 0 || shoppingGroups.every(g => g.ingredients.length === 0)" class="sl-empty">
            收藏的菜品暂无食材信息
          </div>
          <div v-else>
            <div v-for="(group, gIdx) in shoppingGroups" :key="gIdx" class="sl-group">
              <div class="sl-recipe-name">{{ group.recipeName }}</div>
              <div v-if="group.ingredients.length === 0" class="sl-no-ing">（无食材信息）</div>
              <div v-for="(ing, iIdx) in group.ingredients" :key="iIdx" class="sl-item">
                <span>{{ ing }}</span>
              </div>
            </div>
          </div>
          <button class="copy-btn" @click="copyShoppingList">复制到剪贴板</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import API from '../api.js'

const userId = localStorage.getItem('user_id') || ''
const loading = ref(false)
const collections = ref([])
const showShoppingList = ref(false)
const shoppingGroups = ref([])
const showDetail = ref(false)
const detailRecipe = ref({})
const detailData = ref(null)
const detailLoading = ref(false)

const isBlank = (v) => v === undefined || v === null || String(v).trim() === '' || String(v).trim() === '[]'

const normalizeIngredientName = (name) => {
  const raw = String(name || '').trim()
  if (!raw) return ''
  const noParen = raw
    .replace(/（[^）]*）/g, '')
    .replace(/\([^)]*\)/g, '')
    .trim()
  return (noParen || raw).replace(/[\s·•]+/g, '').trim()
}

const splitIngredientText = (text) => {
  const raw = String(text || '').trim()
  if (!raw) return { name: '', amount: '' }

  const amountRegex = /(\d+(?:\.\d+)?\s*(?:g|克|kg|千克|ml|毫升|L|升|斤|两|个|只|根|片|块|勺|杯)|适量|少许|一些)$/i
  const matched = raw.match(amountRegex)

  if (!matched) {
    return { name: raw, amount: '' }
  }

  const amount = matched[1].trim()
  const name = raw.slice(0, raw.length - matched[0].length).trim().replace(/[：:，,、\-]+$/, '').trim()
  return { name: name || raw, amount }
}

// 解析食材字符串为数组
const parseIngredients = (raw) => {
  if (!raw) return []
  try {
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return []
    return arr.map(i => {
      const text = i.raw_text || (typeof i === 'string' ? i : JSON.stringify(i))
      const split = splitIngredientText(text)
      const name = split.name || text
      return {
        display: text,
        name,
        amount: split.amount,
        lookupName: normalizeIngredientName(name),
        showSimilar: false,
        similars: [],
        similarLoading: false,
        showConflict: false,
        conflicts: [],
        conflictLoading: false
      }
    })
  } catch {
    return raw.split(/[,，、\n]/).filter(Boolean).map(t => {
      const text = t.trim()
      const split = splitIngredientText(text)
      const name = split.name || text
      return {
        display: text,
        name,
        amount: split.amount,
        lookupName: normalizeIngredientName(name),
        showSimilar: false,
        similars: [],
        similarLoading: false,
        showConflict: false,
        conflicts: [],
        conflictLoading: false
      }
    })
  }
}

const loadCollections = async () => {
  if (!userId) return
  loading.value = true
  try {
    const res = await API.get(`/collection/?user_id=${userId}`)
    const items = res.data.collections || []
    const merged = items.map(c => ({
      ...c,
      parsedIngredients: parseIngredients(c.ingredients)
    }))
    collections.value = merged
    await enrichCollections(merged)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const enrichCollections = async (items) => {
  const needLookup = items
    .filter(i => isBlank(i.ingredients) || isBlank(i.steps))
    .map(i => i.recipe_name)

  if (needLookup.length === 0) return

  try {
    const res = await API.post('/recipe/', { names: [...new Set(needLookup)] })
    const list = res.data.data || []
    const detailMap = {}
    list.forEach((d) => {
      const k1 = d.requested_name || d.name
      const k2 = d.name
      if (k1) detailMap[k1] = d
      if (k2 && !detailMap[k2]) detailMap[k2] = d
    })

    const persistTasks = []
    items.forEach((item) => {
      const detail = detailMap[item.recipe_name]
      if (!detail) return

      const beforeIngredients = item.ingredients
      const beforeSteps = item.steps

      if (isBlank(item.ingredients) && !isBlank(detail.ingredients)) {
        item.ingredients = detail.ingredients
      }
      if (isBlank(item.steps) && !isBlank(detail.steps)) {
        item.steps = detail.steps
      }
      if ((!item.calories || item.calories === 0) && detail.calories) item.calories = detail.calories
      if ((!item.protein || item.protein === 0) && detail.protein) item.protein = detail.protein
      if ((!item.fat || item.fat === 0) && detail.fat) item.fat = detail.fat
      if ((!item.carbs || item.carbs === 0) && detail.carbs) item.carbs = detail.carbs

      item.parsedIngredients = parseIngredients(item.ingredients)

      // 回写收藏，避免下次进入再次补全
      if (beforeIngredients !== item.ingredients || beforeSteps !== item.steps) {
        persistTasks.push(API.post('/collection/', {
          user_id: userId,
          recipe_name: item.recipe_name,
          calories: item.calories || 0,
          protein: item.protein || 0,
          fat: item.fat || 0,
          carbs: item.carbs || 0,
          ingredients: item.ingredients || '',
          steps: item.steps || ''
        }))
      }
    })

    if (persistTasks.length > 0) {
      await Promise.allSettled(persistTasks)
    }
    collections.value = [...items]
  } catch (e) {
    console.error('收藏补全失败', e)
  }
}

const removeCollection = async (recipeName) => {
  try {
    await API.delete(`/collection/?user_id=${userId}&recipe_name=${encodeURIComponent(recipeName)}`)
    collections.value = collections.value.filter(c => c.recipe_name !== recipeName)
  } catch (e) {
    alert('取消收藏失败')
  }
}

// 查看详情：展示本地缓存数据，同时异步补充完整做法
const viewDetail = async (item) => {
  detailRecipe.value = item
  detailData.value = null
  detailLoading.value = isBlank(item.steps)
  showDetail.value = true
  try {
    const res = await API.post('/recipe/', { names: [item.recipe_name] })
    if (res.data.data && res.data.data.length > 0) {
      detailData.value = res.data.data[0]
      if (isBlank(item.ingredients) && !isBlank(detailData.value.ingredients)) item.ingredients = detailData.value.ingredients
      if (isBlank(item.steps) && !isBlank(detailData.value.steps)) item.steps = detailData.value.steps
      item.parsedIngredients = parseIngredients(item.ingredients)

      await API.post('/collection/', {
        user_id: userId,
        recipe_name: item.recipe_name,
        calories: item.calories || detailData.value.calories || 0,
        protein: item.protein || detailData.value.protein || 0,
        fat: item.fat || detailData.value.fat || 0,
        carbs: item.carbs || detailData.value.carbs || 0,
        ingredients: item.ingredients || detailData.value.ingredients || '',
        steps: item.steps || detailData.value.steps || ''
      })
    }
  } catch (e) {
    console.error(e)
  } finally {
    detailLoading.value = false
  }
}

const closeDetail = () => {
  showDetail.value = false
  detailData.value = null
}

// 替换食材
const findSimilar = async (item, iIdx, name) => {
  const ing = item.parsedIngredients[iIdx]
  ing.showSimilar = !ing.showSimilar
  ing.showConflict = false
  if (!ing.showSimilar) return
  if (ing.similars.length > 0) return
  ing.similarLoading = true
  try {
    const res = await API.get(`/similar-ingredient/?name=${encodeURIComponent(name)}`)
    ing.similars = res.data.similar || []
  } catch (e) {
    console.error(e)
  } finally {
    ing.similarLoading = false
  }
}

const replaceIngredient = (item, iIdx, newName) => {
  const ing = item.parsedIngredients[iIdx]
  ing.display = newName
  ing.name = newName
  ing.lookupName = normalizeIngredientName(newName)
  ing.showSimilar = false
  ing.similars = []
}

// 冲突检查
const checkConflict = async (item, iIdx, name) => {
  const ing = item.parsedIngredients[iIdx]
  ing.showConflict = !ing.showConflict
  ing.showSimilar = false
  if (!ing.showConflict) return
  if (ing.conflicts.length > 0) return
  ing.conflictLoading = true
  try {
    const res = await API.get(`/food-conflict/?name=${encodeURIComponent(name)}`)
    ing.conflicts = res.data.conflicts || []
  } catch (e) {
    console.error(e)
  } finally {
    ing.conflictLoading = false
  }
}

// 购物清单：按菜品分组列出所有食材
const exportShoppingList = () => {
  const groups = collections.value.map(c => ({
    recipeName: c.recipe_name,
    ingredients: c.parsedIngredients ? c.parsedIngredients.map(i => i.display) : []
  }))
  shoppingGroups.value = groups
  showShoppingList.value = true
}

const copyShoppingList = () => {
  const lines = shoppingGroups.value.map(g => {
    const ings = g.ingredients.length > 0 ? g.ingredients.join('、') : '（无食材信息）'
    return `【${g.recipeName}】${ings}`
  })
  navigator.clipboard.writeText(lines.join('\n')).then(() => alert('已复制到剪贴板'))
}

// 格式化食材（弹窗显示）
const formatIngredients = (raw) => {
  if (!raw) return ''
  try {
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return raw
    return arr.map(i => `<span class="ing-tag">${i.raw_text || i}</span>`).join(' ')
  } catch {
    return raw.split(/[,，、\n]/).filter(Boolean).map(t => `<span class="ing-tag">${t.trim()}</span>`).join(' ')
  }
}

// 格式化步骤
const formatSteps = (raw) => {
  if (!raw) return ''
  try {
    const arr = JSON.parse(raw)
    if (Array.isArray(arr)) return '<ol>' + arr.map(s => `<li>${s}</li>`).join('') + '</ol>'
    return raw
  } catch {
    return raw.replace(/\n/g, '<br>')
  }
}

onMounted(() => loadCollections())
</script>

<style scoped>
.favorites-view { width: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h2 { font-size: 22px; color: #2d3436; }
.export-btn { padding: 10px 20px; background: #f6c342; color: #2d3436; border: none; border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 14px; }
.export-btn:hover { background: #e5b336; }
.export-btn:disabled { background: #95a5a6; cursor: not-allowed; }

.loading-state { text-align: center; padding: 60px; color: #636e72; }
.empty-state { text-align: center; padding: 80px; color: #b2bec3; font-size: 16px; }

.fav-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.fav-card { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.fc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.fc-header h3 { font-size: 18px; color: #2d3436; flex: 1; margin-right: 12px; }
.fc-btns { display: flex; gap: 8px; flex-shrink: 0; }
.fc-detail { padding: 6px 14px; border: 1px solid #7761e5; color: #7761e5; border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; transition: .2s; }
.fc-detail:hover { background: #ede9fc; }
.fc-remove { padding: 6px 14px; border: 1px solid #e74c3c; color: #e74c3c; border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; transition: .2s; }
.fc-remove:hover { background: #fdf0ed; }

.fc-macros { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.fc-macros span { font-size: 13px; padding: 5px 12px; background: #f8f9fa; border-radius: 8px; color: #636e72; }

.fc-ingredients { margin-bottom: 4px; }
.fc-ingredients h4 { font-size: 15px; color: #2d3436; margin-bottom: 10px; }
.fc-ingredients-empty { font-size: 13px; color: #8c98a4; margin-top: 6px; }
.ing-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 6px 0; border-bottom: 1px solid #f8f9fa; }
.ing-name { font-size: 14px; color: #2d3436; min-width: 80px; padding: 4px 10px; border-radius: 999px; background: #f2f5f8; border: 1px solid #e2e8ef; }
.ing-amount { font-size: 13px; color: #5f6d7a; padding: 4px 10px; border-radius: 999px; background: #fff8ea; border: 1px solid #f3dfae; }
.ing-replace-btn, .ing-conflict-btn { padding: 3px 10px; border: 1px solid #dfe6e9; border-radius: 6px; font-size: 12px; cursor: pointer; background: #fff; transition: .2s; }
.ing-replace-btn:hover { background: #ede9fc; border-color: #7761e5; color: #7761e5; }
.ing-conflict-btn:hover { background: #fef5e0; border-color: #f6c342; color: #d4a017; }

.similar-panel, .conflict-panel { width: 100%; padding: 8px 12px; margin-top: 4px; border-radius: 8px; }
.similar-panel { background: #ede9fc; }
.conflict-panel { background: #fef5e0; }
.sp-loading, .cp-loading { font-size: 12px; color: #636e72; }
.sp-empty, .cp-safe { font-size: 12px; color: #4aa458; }
.sp-list { display: flex; flex-wrap: wrap; gap: 6px; }
.sp-tag { background: #fff; border: 1px solid #c4b8f0; color: #7761e5; padding: 4px 10px; border-radius: 12px; font-size: 12px; cursor: pointer; transition: .2s; }
.sp-tag:hover { background: #7761e5; color: #fff; }
.cp-list { display: flex; flex-wrap: wrap; gap: 6px; }
.cp-tag { background: #fff; border: 1px solid #f6c342; color: #b38600; padding: 4px 10px; border-radius: 12px; font-size: 12px; }

/* 弹窗通用 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #b2bec3; line-height: 1; padding: 0; }
.close-btn:hover { color: #636e72; }

/* 详情弹窗 */
.detail-modal { background: #fff; width: 540px; max-height: 82vh; overflow-y: auto; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.15); }
.dm-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid #f0f2f5; position: sticky; top: 0; background: #fff; z-index: 1; }
.dm-header h3 { font-size: 18px; color: #2d3436; }
.dm-body { padding: 24px; }
.dm-macros { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
.dm-macros span { font-size: 13px; padding: 6px 12px; background: #f8f9fa; border-radius: 8px; color: #636e72; }
.dm-section { margin-bottom: 20px; }
.dm-section h4 { font-size: 15px; color: #2d3436; margin-bottom: 10px; font-weight: 600; }
.dm-loading { text-align: center; padding: 30px; color: #b2bec3; }
.dm-empty { text-align: center; padding: 20px; color: #b2bec3; font-size: 14px; }
.ing-tags :deep(.ing-tag) { display: inline-block; background: #ede9fc; color: #7761e5; padding: 4px 12px; border-radius: 12px; margin: 3px 4px; font-size: 13px; }
.steps-content :deep(ol) { padding-left: 20px; }
.steps-content :deep(li) { margin-bottom: 10px; color: #2d3436; line-height: 1.7; font-size: 14px; }

/* 购物清单弹窗 */
.shopping-modal { background: #fff; width: 460px; max-height: 75vh; overflow-y: auto; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.15); }
.sm-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid #f0f2f5; position: sticky; top: 0; background: #fff; z-index: 1; }
.sm-header h3 { font-size: 18px; color: #2d3436; }
.sm-body { padding: 16px 24px 24px; }
.sl-empty { text-align: center; padding: 20px; color: #b2bec3; font-size: 14px; }
.sl-group { margin-bottom: 14px; }
.sl-recipe-name { font-size: 13px; font-weight: 600; color: #2d3436; padding: 6px 0 4px; border-bottom: 1px solid #f0f2f5; margin-bottom: 6px; }
.sl-no-ing { font-size: 12px; color: #b2bec3; padding: 4px 0; }
.sl-item { padding: 5px 8px; font-size: 14px; color: #636e72; }
.sl-item::before { content: '• '; color: #7761e5; }
.copy-btn { margin-top: 16px; width: 100%; padding: 12px 0; background: #7761e5; color: #fff; border: none; border-radius: 10px; font-weight: 600; font-size: 14px; cursor: pointer; }
.copy-btn:hover { background: #6350d0; }
</style>

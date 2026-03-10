<template>
  <div class="favorites-view">
    <div class="page-header">
      <h2>⭐ 我的收藏夹</h2>
      <button class="export-btn" @click="exportShoppingList" :disabled="collections.length === 0">🛒 导出购物清单</button>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>
    <div v-else-if="collections.length === 0" class="empty-state">
      <p>暂无收藏，去食谱推荐页收藏你喜欢的菜品吧！</p>
    </div>

    <div v-else class="fav-list">
      <div v-for="(item, idx) in collections" :key="idx" class="fav-card">
        <div class="fc-header">
          <h3>{{ item.recipe_name }}</h3>
          <button class="fc-remove" @click="removeCollection(item.recipe_name)">🗑️ 取消收藏</button>
        </div>
        <div class="fc-macros">
          <span>🔥 {{ item.calories || '—' }} kcal</span>
          <span>💪 {{ item.protein || '—' }}g 蛋白</span>
          <span>🫒 {{ item.fat || '—' }}g 脂肪</span>
          <span>🌾 {{ item.carbs || '—' }}g 碳水</span>
        </div>

        <!-- 食材列表 + 替换 + 冲突 -->
        <div class="fc-ingredients" v-if="item.parsedIngredients && item.parsedIngredients.length > 0">
          <h4>🛒 食材清单</h4>
          <div v-for="(ing, iIdx) in item.parsedIngredients" :key="iIdx" class="ing-row">
            <span class="ing-name">{{ ing.display }}</span>
            <button class="ing-replace-btn" @click="findSimilar(item, iIdx, ing.name)">🔄 替换</button>
            <button class="ing-conflict-btn" @click="checkConflict(item, iIdx, ing.name)">⚠️ 同食禁忌</button>

            <!-- 替换结果 -->
            <div v-if="ing.showSimilar" class="similar-panel">
              <div v-if="ing.similarLoading" class="sp-loading">搜索中...</div>
              <div v-else-if="ing.similars && ing.similars.length > 0" class="sp-list">
                <span v-for="s in ing.similars" :key="s" class="sp-tag" @click="replaceIngredient(item, iIdx, s)">{{ s }}</span>
              </div>
              <div v-else class="sp-empty">未找到相似食材</div>
            </div>

            <!-- 冲突结果 -->
            <div v-if="ing.showConflict" class="conflict-panel">
              <div v-if="ing.conflictLoading" class="cp-loading">查询中...</div>
              <div v-else-if="ing.conflicts && ing.conflicts.length > 0" class="cp-list">
                <span v-for="c in ing.conflicts" :key="c" class="cp-tag">🚫 {{ c }}</span>
              </div>
              <div v-else class="cp-safe">✅ 暂无已知同食禁忌</div>
            </div>
          </div>
        </div>

        <!-- 步骤 -->
        <div class="fc-steps" v-if="item.steps">
          <h4>🍳 烹饪步骤</h4>
          <div v-html="formatSteps(item.steps)"></div>
        </div>
      </div>
    </div>

    <!-- 购物清单弹窗 -->
    <div v-if="showShoppingList" class="modal-overlay" @click.self="showShoppingList = false">
      <div class="shopping-modal">
        <div class="sm-header">
          <h3>🛒 购物清单</h3>
          <button class="close-btn" @click="showShoppingList = false">×</button>
        </div>
        <div class="sm-body">
          <div v-for="(ing, idx) in shoppingList" :key="idx" class="sl-item">
            <span>{{ ing }}</span>
          </div>
          <button class="copy-btn" @click="copyShoppingList">📋 复制到剪贴板</button>
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
const shoppingList = ref([])

// 解析食材字符串为数组
const parseIngredients = (raw) => {
  if (!raw) return []
  try {
    const arr = JSON.parse(raw)
    return arr.map(i => {
      const text = i.raw_text || (typeof i === 'string' ? i : JSON.stringify(i))
      // 尝试提取食材名（去掉数量）
      const name = text.replace(/[\d.]+\s*(g|克|ml|毫升|斤|两|个|只|根|片|块|勺|杯|适量|少许|一些)/g, '').trim() || text
      return { display: text, name, showSimilar: false, similars: [], similarLoading: false, showConflict: false, conflicts: [], conflictLoading: false }
    })
  } catch {
    return raw.split(/[,，、\n]/).filter(Boolean).map(t => ({
      display: t.trim(), name: t.trim(),
      showSimilar: false, similars: [], similarLoading: false,
      showConflict: false, conflicts: [], conflictLoading: false
    }))
  }
}

const loadCollections = async () => {
  if (!userId) return
  loading.value = true
  try {
    const res = await API.get(`/collection/?user_id=${userId}`)
    const items = res.data.collections || []
    collections.value = items.map(c => ({
      ...c,
      parsedIngredients: parseIngredients(c.ingredients)
    }))
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

const removeCollection = async (recipeName) => {
  try {
    await API.delete(`/collection/?user_id=${userId}&recipe_name=${encodeURIComponent(recipeName)}`)
    collections.value = collections.value.filter(c => c.recipe_name !== recipeName)
  } catch (e) { alert('取消收藏失败') }
}

// 替换食材
const findSimilar = async (item, iIdx, name) => {
  const ing = item.parsedIngredients[iIdx]
  ing.showSimilar = !ing.showSimilar
  ing.showConflict = false
  if (!ing.showSimilar) return
  if (ing.similars.length > 0) return // 已缓存
  ing.similarLoading = true
  try {
    const res = await API.get(`/similar-ingredient/?name=${encodeURIComponent(name)}`)
    ing.similars = res.data.similar || []
  } catch (e) { console.error(e) }
  finally { ing.similarLoading = false }
}

const replaceIngredient = (item, iIdx, newName) => {
  const ing = item.parsedIngredients[iIdx]
  ing.display = newName
  ing.name = newName
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
  } catch (e) { console.error(e) }
  finally { ing.conflictLoading = false }
}

// 购物清单
const exportShoppingList = () => {
  const allIngs = new Set()
  collections.value.forEach(c => {
    if (c.parsedIngredients) {
      c.parsedIngredients.forEach(i => allIngs.add(i.display))
    }
  })
  shoppingList.value = [...allIngs]
  showShoppingList.value = true
}

const copyShoppingList = () => {
  const text = shoppingList.value.join('\n')
  navigator.clipboard.writeText(text).then(() => alert('✅ 已复制到剪贴板'))
}

const formatSteps = (raw) => {
  if (!raw) return ''
  try {
    const arr = JSON.parse(raw)
    if (Array.isArray(arr)) return '<ol>' + arr.map(s => `<li>${s}</li>`).join('') + '</ol>'
    return raw
  } catch { return raw.replace(/\n/g, '<br>') }
}

onMounted(() => loadCollections())
</script>

<style scoped>
.favorites-view { max-width: 900px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h2 { font-size: 22px; color: #2d3436; }
.export-btn { padding: 10px 20px; background: #e67e22; color: #fff; border: none; border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 14px; }
.export-btn:hover { background: #d35400; }
.export-btn:disabled { background: #95a5a6; cursor: not-allowed; }

.loading-state { text-align: center; padding: 60px; color: #636e72; }
.empty-state { text-align: center; padding: 80px; color: #b2bec3; font-size: 16px; }

.fav-list { display: flex; flex-direction: column; gap: 20px; }
.fav-card { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.fc-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.fc-header h3 { font-size: 18px; color: #2d3436; }
.fc-remove { padding: 6px 14px; border: 1px solid #e74c3c; color: #e74c3c; border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.fc-remove:hover { background: #fdf0ed; }
.fc-macros { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.fc-macros span { font-size: 13px; padding: 5px 12px; background: #f8f9fa; border-radius: 8px; color: #636e72; }

.fc-ingredients { margin-bottom: 16px; }
.fc-ingredients h4 { font-size: 15px; color: #2d3436; margin-bottom: 10px; }
.ing-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 6px 0; border-bottom: 1px solid #f8f9fa; }
.ing-name { font-size: 14px; color: #2d3436; min-width: 80px; }
.ing-replace-btn, .ing-conflict-btn { padding: 3px 10px; border: 1px solid #dfe6e9; border-radius: 6px; font-size: 12px; cursor: pointer; background: #fff; transition: .2s; }
.ing-replace-btn:hover { background: #e3f2fd; border-color: #2196f3; color: #2196f3; }
.ing-conflict-btn:hover { background: #fff3e0; border-color: #ff9800; color: #ff9800; }

.similar-panel, .conflict-panel { width: 100%; padding: 8px 12px; margin-top: 4px; border-radius: 8px; }
.similar-panel { background: #e3f2fd; }
.conflict-panel { background: #fff3e0; }
.sp-loading, .cp-loading { font-size: 12px; color: #636e72; }
.sp-empty, .cp-safe { font-size: 12px; color: #27ae60; }
.sp-list { display: flex; flex-wrap: wrap; gap: 6px; }
.sp-tag { background: #fff; border: 1px solid #90caf9; color: #1976d2; padding: 4px 10px; border-radius: 12px; font-size: 12px; cursor: pointer; transition: .2s; }
.sp-tag:hover { background: #1976d2; color: #fff; }
.cp-list { display: flex; flex-wrap: wrap; gap: 6px; }
.cp-tag { background: #fff; border: 1px solid #ffcc80; color: #e65100; padding: 4px 10px; border-radius: 12px; font-size: 12px; }

.fc-steps { margin-top: 12px; }
.fc-steps h4 { font-size: 15px; color: #2d3436; margin-bottom: 10px; }
.fc-steps :deep(ol) { padding-left: 20px; }
.fc-steps :deep(li) { margin-bottom: 8px; color: #2d3436; line-height: 1.6; }

/* 购物清单弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.shopping-modal { background: #fff; width: 440px; max-height: 70vh; overflow-y: auto; border-radius: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.15); }
.sm-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; border-bottom: 1px solid #f0f2f5; }
.sm-header h3 { font-size: 18px; color: #2d3436; }
.close-btn { background: none; border: none; font-size: 24px; cursor: pointer; color: #b2bec3; }
.sm-body { padding: 20px 24px; }
.sl-item { padding: 8px 12px; border-bottom: 1px solid #f8f9fa; font-size: 14px; color: #2d3436; }
.copy-btn { margin-top: 16px; width: 100%; padding: 12px 0; background: #27ae60; color: #fff; border: none; border-radius: 10px; font-weight: 600; font-size: 14px; cursor: pointer; }
.copy-btn:hover { background: #219a52; }
</style>

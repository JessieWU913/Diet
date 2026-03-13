<template>
  <div class="ingredient-search-view">
    <div class="page-header">
      <h2>{{ queryType === 'ingredient' ? '食材具体查询' : '菜谱具体查询' }}</h2>
      <p>{{ queryType === 'ingredient' ? '输入食材名称，查看完整营养信息与互补/互斥/重叠关系。' : '输入菜谱名称，查看完整属性、营养、配料与步骤信息。' }}</p>
    </div>

    <div class="search-bar">
      <select v-model="queryType" class="type-select" :disabled="loading">
        <option value="ingredient">食材</option>
        <option value="recipe">菜谱</option>
      </select>
      <div class="autocomplete-wrap">
        <input
          v-model="keyword"
          @keyup.enter="searchCurrent"
          @focus="showSuggestions = true"
          @blur="hideSuggestionsWithDelay"
          :placeholder="queryType === 'ingredient' ? '例如：菠菜、鸡蛋、三文鱼' : '例如：番茄鸡蛋汤、青椒肉丝'"
          :disabled="loading"
        />
        <div v-if="showSuggestions && suggestions.length > 0" class="search-results">
          <button
            v-for="item in suggestions"
            :key="`${item.type}-${item.name}`"
            class="search-item"
            @mousedown.prevent="selectSuggestion(item)"
          >
            <span class="si-name" v-html="highlightMatch(item.name, keyword)"></span>
            <span class="si-right">
              <span class="si-type">{{ item.type === 'Recipe' ? '菜谱' : '食材' }}</span>
              <span class="si-cal">{{ item.calories ?? '—' }} kcal</span>
            </span>
          </button>
        </div>
      </div>
      <button class="query-btn" @click="searchCurrent" :disabled="loading || !keyword.trim()">
        {{ loading ? '查询中...' : '查询' }}
      </button>
    </div>

    <div v-if="errorText" class="error-box">{{ errorText }}</div>

    <div v-if="!result" class="season-board" :class="[boardThemeClass, { loading: boardLoading }]">
      <div class="sb-glow"></div>
      <div class="sb-head">
        <div>
          <h3>时令食材展板</h3>
          <p>{{ toneLine }}</p>
        </div>
        <button class="sb-refresh" @click="refreshBoard" :disabled="boardLoading">
          {{ boardLoading ? '生成中...' : '换一条' }}
        </button>
      </div>

      <div class="sb-meta-grid">
        <div class="sb-meta-card">
          <div class="sb-label">日期时间</div>
          <div class="sb-value">{{ nowText }}</div>
        </div>
        <div class="sb-meta-card">
          <div class="sb-label">季节</div>
          <div class="sb-value">{{ seasonText }}</div>
        </div>
        <div class="sb-meta-card">
          <div class="sb-label">天气</div>
          <div class="sb-value">{{ weatherText }}</div>
        </div>
        <div class="sb-meta-card">
          <div class="sb-label">时段主题</div>
          <div class="sb-value">{{ periodText }}</div>
        </div>
      </div>

      <div class="sb-recommend">
        <div class="sb-r-title">今日 AI 推荐食材（3条）</div>
        <div class="sb-r-list">
          <div v-for="(item, idx) in seasonalSuggestion.ingredients" :key="`ing-${idx}`" class="sb-r-item">
            <div class="sb-r-index">{{ idx + 1 }}</div>
            <div class="sb-r-main">
              <div class="sb-r-name">{{ item.name }}</div>
              <div class="sb-r-reason">{{ item.reason }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="sb-tips-grid">
        <div class="sb-tip-card">
          <h4>相宜小贴士</h4>
          <ul>
            <li v-for="(tip, idx) in seasonalSuggestion.goodTips" :key="`g-${idx}`">{{ tip }}</li>
          </ul>
        </div>
        <div class="sb-tip-card avoid">
          <h4>相克/避坑提示</h4>
          <ul>
            <li v-for="(tip, idx) in seasonalSuggestion.avoidTips" :key="`a-${idx}`">{{ tip }}</li>
          </ul>
        </div>
      </div>
    </div>

    <div v-if="result" class="result-wrap">
      <section class="card">
        <h3>{{ result.name }}</h3>
      </section>

      <section class="card">
        <h4>全部营养与属性字段</h4>
        <div v-if="mergedEntries.length === 0" class="empty">暂无属性数据</div>
        <div v-else class="property-grid">
          <div v-for="entry in mergedEntries" :key="entry.key" class="property-item">
            <div class="pk">{{ entry.key }}</div>
            <div class="pv">{{ entry.value }}</div>
          </div>
        </div>
      </section>

      <section v-if="isIngredientResult" class="relation-grid">
        <div class="card">
          <h4>互补食材</h4>
          <div v-if="result.relations.complements.length === 0" class="empty">暂无数据</div>
          <ul v-else class="rel-list">
            <li v-for="(r, idx) in result.relations.complements" :key="`c-${idx}`">
              <strong>{{ r.name }}</strong>
              <span>{{ relationDesc(r) }}</span>
            </li>
          </ul>
        </div>

        <div class="card">
          <h4>互斥/禁忌食材</h4>
          <div v-if="result.relations.conflicts.length === 0" class="empty">暂无数据</div>
          <ul v-else class="rel-list">
            <li v-for="(r, idx) in result.relations.conflicts" :key="`f-${idx}`">
              <strong>{{ r.name }}</strong>
              <span>{{ relationDesc(r) }}</span>
            </li>
          </ul>
        </div>

        <div class="card">
          <h4>重叠/类似食材</h4>
          <div v-if="result.relations.overlaps.length === 0" class="empty">暂无数据</div>
          <ul v-else class="rel-list">
            <li v-for="(r, idx) in result.relations.overlaps" :key="`o-${idx}`">
              <strong>{{ r.name }}</strong>
              <span>{{ relationDesc(r) }}</span>
            </li>
          </ul>
        </div>
      </section>

      <section v-if="isIngredientResult" class="card">
        <h4>全部关系明细</h4>
        <div v-if="result.relations.all.length === 0" class="empty">暂无关系数据</div>
        <table v-else class="rel-table">
          <thead>
            <tr>
              <th>关系类型</th>
              <th>关联食材</th>
              <th>方向</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, idx) in result.relations.all" :key="`a-${idx}`">
              <td>{{ r.relation_type }}</td>
              <td>{{ r.name }}</td>
              <td>{{ r.direction }}</td>
              <td>{{ r.reason || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="isRecipeResult" class="card">
        <h4>配料明细</h4>
        <div v-if="recipeIngredientRows.length === 0" class="empty">暂无配料数据</div>
        <table v-else class="rel-table">
          <thead>
            <tr>
              <th>食材名</th>
              <th>重量(g)</th>
              <th>原始文本</th>
              <th>已结构化</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, idx) in recipeIngredientRows" :key="`ri-${idx}`">
              <td>{{ r.ingredient_name || r.name || '—' }}</td>
              <td>{{ r.weight_g ?? '—' }}</td>
              <td>{{ r.raw_text || '—' }}</td>
              <td>{{ r.is_linked === true ? '是' : (r.is_linked === false ? '否' : '—') }}</td>
              <td>
                <button
                  class="ing-jump-btn"
                  :disabled="!(r.ingredient_name || r.name)"
                  @click="jumpToIngredient(r.ingredient_name || r.name)"
                >
                  查食材详情
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="isRecipeResult" class="card">
        <h4>制作步骤</h4>
        <div v-if="recipeSteps.length === 0" class="empty">暂无步骤数据</div>
        <div v-else class="steps-content" v-html="formattedRecipeSteps"></div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import API from '../api.js'
import { formatRecipeStepsHtml } from '../utils/recipeStepFormatter.js'

const keyword = ref('')
const queryType = ref('ingredient')
const loading = ref(false)
const errorText = ref('')
const result = ref(null)
const suggestions = ref([])
const showSuggestions = ref(false)
let suggestTimer = null
let clockTimer = null

const boardLoading = ref(false)
const nowText = ref('')
const seasonText = ref('')
const weatherText = ref('获取中...')
const seasonalSuggestion = ref({
  ingredients: [
    { name: '菠菜', reason: '清爽耐搭配，焯拌或清炒都能快速上桌。搭配蛋类或豆制品可提升整体蛋白质量，口感也更有层次。' },
    { name: '鸡蛋', reason: '优质蛋白稳定，适合晨间或午间补给。和高纤维蔬菜同餐可延长饱腹感，减少加餐冲动。' },
    { name: '南瓜', reason: '口感柔和，蒸煮都能保留自然甜感。作为主食替代的一部分，有助于控制总油脂摄入与晚间负担。' }
  ],
  goodTips: [
    '优先选择当季新鲜原料，减少重口调味。',
    '每餐保留蛋白质+蔬菜+主食的基本结构。',
    '烹饪以蒸煮炖为主，控制额外油脂。'
  ],
  avoidTips: [
    '避免空腹高糖饮品，减少血糖大起伏。',
    '辛辣油炸不宜与高盐加工食品叠加。',
    '已知过敏食材与器具要分开处理。'
  ]
})

const prettyValue = (v) => {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'object') return JSON.stringify(v, null, 2)
  return String(v)
}

const displayValue = (v) => (v === null || v === undefined || v === '' ? '—' : v)

const fieldLabelMap = {
  name: '名称',
  original_name: '原始名称',
  category: '种类',
  updated_at: '更新时间',
  cal_per_100g: '每100g热量',
  unit_info: '单位换算信息',
  nutrient_count: '营养项数量',
}

const formatUpdatedAt = (value) => {
  if (!value) return ''
  return String(value).replace('T', ' ').replace('Z', '')
}

const formatNutrientValue = (value) => {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object' && value !== null) {
    const v = value.value ?? ''
    const u = value.unit ?? ''
    if (v === '' && u === '') return '—'
    return `${v}${u}`
  }
  return String(value)
}

const baseFieldOrder = [
  '名称',
  '种类',
  '更新时间',
  '每100g热量',
  '原始名称',
  '单位换算信息',
  '营养项数量'
]

const nutrientFieldOrder = [
  '热量', '蛋白质', '脂肪', '碳水化合物', '纤维素',
  '胆固醇',
  '维生素A', '维生素C', '维生素D', '维生素E', '维生素K',
  '硫胺素', '核黄素', '烟酸', '叶酸',
  '钙', '铁', '锌', '镁', '钾', '磷', '钠', '铜', '锰', '硒'
]

const sortByOrder = (entries, order) => {
  const rank = new Map(order.map((k, i) => [k, i]))
  return [...entries].sort((a, b) => {
    const ra = rank.has(a.key) ? rank.get(a.key) : Number.MAX_SAFE_INTEGER
    const rb = rank.has(b.key) ? rank.get(b.key) : Number.MAX_SAFE_INTEGER
    if (ra !== rb) return ra - rb
    return a.key.localeCompare(b.key, 'zh-Hans-CN')
  })
}

const parseUnitInfo = (raw) => {
  if (!raw) return '—'
  try {
    const arr = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!Array.isArray(arr) || arr.length === 0) return '—'
    return arr.map((item) => {
      if (item && typeof item === 'object') {
        const key = Object.keys(item)[0]
        return key ? `${key}: ${item[key]}` : JSON.stringify(item)
      }
      return String(item)
    }).join('；')
  } catch {
    return String(raw)
  }
}

const propertyEntries = computed(() => {
  if (!result.value || !result.value.all_properties) return []
  const props = result.value.all_properties
  const hiddenKeys = new Set(['nutrients_raw', 'calories', 'protein', 'fat', 'carbs', 'fiber'])

  const entries = Object.entries(props)
    .filter(([key]) => !hiddenKeys.has(key))
    .map(([key, value]) => {
      if (key === 'unit_info') {
        return { key: fieldLabelMap[key] || key, value: parseUnitInfo(value) }
      }
      if (key === 'updated_at') {
        return { key: fieldLabelMap[key] || key, value: formatUpdatedAt(value) || '—' }
      }
      if (key === 'cal_per_100g') {
        return { key: fieldLabelMap[key] || key, value: `${value} 大卡` }
      }
      return {
        key: fieldLabelMap[key] || key,
        value: prettyValue(value)
      }
    })

  return sortByOrder(entries, baseFieldOrder)
})

const nutrientEntries = computed(() => {
  if (!result.value || !result.value.nutrients_detail) return []
  const entries = Object.entries(result.value.nutrients_detail).map(([key, value]) => ({
    key,
    value: formatNutrientValue(value)
  }))
  return sortByOrder(entries, nutrientFieldOrder)
})

const mergedEntries = computed(() => {
  return [...propertyEntries.value, ...nutrientEntries.value]
})

const isRecipeResult = computed(() => result.value?.query_type === 'recipe')
const isIngredientResult = computed(() => !isRecipeResult.value)

const recipeIngredientRows = computed(() => {
  if (!isRecipeResult.value) return []
  const rows = result.value?.contains_relations
  if (Array.isArray(rows) && rows.length > 0) return rows
  const rawRows = result.value?.ingredients_detail
  return Array.isArray(rawRows) ? rawRows : []
})

const recipeSteps = computed(() => {
  if (!isRecipeResult.value) return []
  const rows = result.value?.steps_detail
  return Array.isArray(rows) ? rows.filter((x) => String(x || '').trim()) : []
})

const formattedRecipeSteps = computed(() => {
  return formatRecipeStepsHtml(recipeSteps.value)
})

const relationDesc = (r) => r.reason || r.relation_type

const getSeason = (d = new Date()) => {
  const m = d.getMonth() + 1
  if (m >= 3 && m <= 5) return '春季'
  if (m >= 6 && m <= 8) return '夏季'
  if (m >= 9 && m <= 11) return '秋季'
  return '冬季'
}

const formatNowText = (d = new Date()) => {
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const mi = String(d.getMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
}

const getTimePeriod = (d = new Date()) => {
  const h = d.getHours()
  if (h >= 5 && h < 11) return 'morning'
  if (h >= 11 && h < 17) return 'noon'
  return 'night'
}

const timePeriod = computed(() => {
  const text = nowText.value || ''
  const m = text.match(/\s(\d{2}):/)
  const hour = m ? Number(m[1]) : new Date().getHours()
  if (hour >= 5 && hour < 11) return 'morning'
  if (hour >= 11 && hour < 17) return 'noon'
  return 'night'
})

const periodText = computed(() => {
  if (timePeriod.value === 'morning') return '晨间焕新'
  if (timePeriod.value === 'noon') return '午间能量'
  return '晚间舒缓'
})

const boardThemeClass = computed(() => `theme-${timePeriod.value}`)

const toneLine = computed(() => {
  if (timePeriod.value === 'morning') return '早安模式：轻盈、清爽、稳态启动今天。'
  if (timePeriod.value === 'noon') return '午间模式：高效、饱腹、帮你稳住专注力。'
  return '夜间模式：温和、舒缓、减少肠胃负担。'
})

const expandReason = (reasonText) => {
  const raw = String(reasonText || '').trim()
  const suffix = timePeriod.value === 'morning'
    ? '建议搭配一份优质蛋白和少量全谷物，让上午体感更稳定。'
    : timePeriod.value === 'noon'
      ? '建议搭配高纤维蔬菜与适量主食，避免午后困倦和能量回落。'
      : '建议以清蒸或炖煮为主，减少夜间油脂负担并提升舒适度。'
  if (!raw) return `优先选择当季新鲜食材，兼顾口感与营养密度。${suffix}`
  return raw.length < 26 ? `${raw}${suffix}` : raw
}

const weatherCodeToText = (code) => {
  const map = {
    0: '晴朗', 1: '基本晴', 2: '多云', 3: '阴天',
    45: '有雾', 48: '雾凇',
    51: '小毛雨', 53: '毛毛雨', 55: '强毛雨',
    61: '小雨', 63: '中雨', 65: '大雨',
    71: '小雪', 73: '中雪', 75: '大雪',
    80: '阵雨', 81: '较强阵雨', 82: '强阵雨',
    95: '雷暴'
  }
  return map[code] || '天气未知'
}

const extractAnswerText = (raw) => {
  const text = String(raw || '')
  return text.replace(/<think>[\s\S]*?<\/think>/i, '').trim()
}

const extractJson = (raw) => {
  try {
    return JSON.parse(raw)
  } catch {
    const m = String(raw || '').match(/\{[\s\S]*\}/)
    if (!m) return null
    try {
      return JSON.parse(m[0])
    } catch {
      return null
    }
  }
}

const fetchWeather = async () => {
  try {
    if (!navigator.geolocation) {
      weatherText.value = '无法获取定位（浏览器不支持）'
      return
    }

    const pos = await new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 4000 })
    })

    const lat = pos.coords.latitude
    const lon = pos.coords.longitude
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&timezone=auto`
    const res = await fetch(url)
    const data = await res.json()
    const cw = data?.current_weather
    if (!cw) {
      weatherText.value = '天气信息暂不可用'
      return
    }
    weatherText.value = `${weatherCodeToText(cw.weathercode)} · ${Math.round(cw.temperature)}°C`
  } catch {
    weatherText.value = '天气信息暂不可用'
  }
}

const generateBoardSuggestion = async () => {
  boardLoading.value = true
  try {
    const userId = localStorage.getItem('user_id') || 'guest'
    const styleTone = timePeriod.value === 'morning'
      ? '语气清晨感、积极轻快。'
      : timePeriod.value === 'noon'
        ? '语气简洁有力、注重效率与饱腹。'
        : '语气温柔沉稳、强调舒缓与易消化。'
    const query = `请根据今天的时间与体感给出时令食材建议。\n时间：${nowText.value}\n季节：${seasonText.value}\n天气：${weatherText.value}\n时段主题：${periodText.value}\n${styleTone}\n要求：推荐食材3条；每条理由必须是两句、信息具体、40-65字，不要空泛口号；相宜小贴士3条；相克/避坑提示3条。\n只返回JSON：{"ingredients":[{"name":"","reason":""},{"name":"","reason":""},{"name":"","reason":""}],"good_tips":["","",""],"avoid_tips":["","",""]}`
    const res = await API.post('/chat/', {
      query,
      mode: 'standard',
      user_id: userId,
      session_id: `season_board_${userId}`
    })
    const answer = extractAnswerText(res?.data?.response)
    const payload = extractJson(answer)

    if (payload && Array.isArray(payload.ingredients) && payload.ingredients.length > 0) {
      const normalized = payload.ingredients
        .map((item) => {
          if (item && typeof item === 'object') {
            return {
              name: displayValue(item.name || '推荐食材'),
              reason: expandReason(displayValue(item.reason || '建议选择当季新鲜食材。'))
            }
          }
          return {
            name: displayValue(item),
            reason: expandReason('建议选择当季新鲜食材。')
          }
        })
        .filter((x) => x.name !== '—')
        .slice(0, 3)
      seasonalSuggestion.value = {
        ingredients: normalized.length > 0 ? normalized : getFallbackIngredients(),
        goodTips: Array.isArray(payload.good_tips) && payload.good_tips.length > 0
          ? payload.good_tips.slice(0, 3)
          : getFallbackGoodTips(),
        avoidTips: Array.isArray(payload.avoid_tips) && payload.avoid_tips.length > 0
          ? payload.avoid_tips.slice(0, 3)
          : getFallbackAvoidTips()
      }
      return
    }

    seasonalSuggestion.value = {
      ingredients: getFallbackIngredients(),
      goodTips: getFallbackGoodTips(),
      avoidTips: getFallbackAvoidTips()
    }
  } catch {
    seasonalSuggestion.value = {
      ingredients: getFallbackIngredients(),
      goodTips: getFallbackGoodTips(),
      avoidTips: getFallbackAvoidTips()
    }
  } finally {
    boardLoading.value = false
  }
}

const getFallbackIngredients = () => {
  if (timePeriod.value === 'morning') {
    return [
      { name: '燕麦', reason: '复合碳水释放更平稳，适合晨间启动。搭配牛奶或无糖酸奶与坚果碎，可同时提升口感与饱腹层次。' },
      { name: '鸡蛋', reason: '优质蛋白稳定饱腹感，避免早间能量下滑。与全麦主食和蔬菜组合，能让上午工作专注度更平稳。' },
      { name: '菠菜', reason: '清爽好搭配，做汤或快炒都高效。与豆制品同烹可提升餐盘完整度，同时保持清爽口感。' }
    ]
  }
  if (timePeriod.value === 'noon') {
    return [
      { name: '糙米', reason: '饱腹与能量释放更持久，适合午后工作。作为精白米饭的部分替代，可减少餐后困倦感。' },
      { name: '鸡胸肉', reason: '高蛋白低负担，提升午餐结构完整度。采用煎烤或焖煮少油做法，更有利于控制总热量。' },
      { name: '西兰花', reason: '纤维与微量营养补充均衡，易于搭配主菜。与优质蛋白同餐能提升饱腹感并减少零食摄入。' }
    ]
  }
  return [
    { name: '南瓜', reason: '口感温和，晚间进食更舒缓。蒸煮后自然甜感明显，可减少对重口味调味的依赖。' },
    { name: '豆腐', reason: '蛋白来源轻盈，适合夜间控制油脂。搭配菌菇或绿叶菜做汤，既有饱腹感又不压胃。' },
    { name: '白萝卜', reason: '炖煮后温润易消化，适合晚餐和宵夜。与瘦肉小火慢炖能增强风味，同时维持较低油脂。' }
  ]
}

const getFallbackGoodTips = () => [
  '一餐里保证蛋白质、蔬菜、主食三要素齐全。',
  '食材尽量使用蒸煮炖，减少复炸和反复加热。',
  '调味先轻后重，先尝再加盐，控制总钠摄入。'
]

const getFallbackAvoidTips = () => [
  '避免高油高盐和高糖饮品同餐叠加。',
  '首次尝试新食材先少量，观察是否不适。',
  '夜间不建议高辣高油，减少睡前肠胃负担。'
]

const refreshBoard = async () => {
  nowText.value = formatNowText(new Date())
  seasonText.value = getSeason(new Date())
  await fetchWeather()
  await generateBoardSuggestion()
}

const escapeHtml = (s) => {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const escapeRegExp = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const highlightMatch = (text, q) => {
  const source = String(text || '')
  const kw = String(q || '').trim()
  if (!kw) return escapeHtml(source)

  const reg = new RegExp(`(${escapeRegExp(kw)})`, 'ig')
  return source
    .split(reg)
    .map(part => (part.toLowerCase() === kw.toLowerCase()
      ? `<mark class="kw-highlight">${escapeHtml(part)}</mark>`
      : escapeHtml(part)))
    .join('')
}

const fetchSuggestions = async (q) => {
  if (!q) {
    suggestions.value = []
    return
  }
  try {
    const res = await API.get(`/food-search/?q=${encodeURIComponent(q)}`)
    const rows = res.data.data || []
    const uniq = new Map()
    rows.forEach((row) => {
      const name = (row.name || '').trim()
      if (!name) return
      const type = row.type || 'Unknown'
      if (queryType.value === 'ingredient' && type !== 'Ingredient') return
      if (queryType.value === 'recipe' && type !== 'Recipe') return
      if (!uniq.has(name)) {
        uniq.set(name, { name, type, calories: row.calories })
      }
    })
    suggestions.value = Array.from(uniq.values()).slice(0, 8)
  } catch {
    suggestions.value = []
  }
}

watch(keyword, (val) => {
  const q = (val || '').trim()
  if (suggestTimer) clearTimeout(suggestTimer)
  suggestTimer = setTimeout(() => {
    fetchSuggestions(q)
  }, 250)
})

watch(queryType, () => {
  showSuggestions.value = false
  suggestions.value = []
  result.value = null
  errorText.value = ''
})

const selectSuggestion = (item) => {
  keyword.value = item?.name || ''
  showSuggestions.value = false
  searchCurrent()
}

const hideSuggestionsWithDelay = () => {
  setTimeout(() => {
    showSuggestions.value = false
  }, 120)
}

const jumpToIngredient = (name) => {
  const n = String(name || '').trim()
  if (!n) return
  queryType.value = 'ingredient'
  keyword.value = n
  searchCurrent()
}

const searchCurrent = async () => {
  const q = keyword.value.trim()
  if (!q || loading.value) return

  loading.value = true
  showSuggestions.value = false
  errorText.value = ''
  result.value = null

  try {
    const endpoint = queryType.value === 'recipe' ? '/recipe-detail/' : '/ingredient-detail/'
    const res = await API.get(`${endpoint}?name=${encodeURIComponent(q)}`)
    result.value = res.data.data
  } catch (e) {
    errorText.value = e?.response?.data?.error || '查询失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  nowText.value = formatNowText(new Date())
  seasonText.value = getSeason(new Date())
  clockTimer = setInterval(() => {
    nowText.value = formatNowText(new Date())
  }, 60000)
  await refreshBoard()
})

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<style scoped>
.ingredient-search-view { width: 100%; }
.page-header { margin-bottom: 18px; }
.page-header h2 { margin: 0 0 8px; color: #2d3436; font-size: 24px; }
.page-header p { margin: 0; color: #6c7a89; font-size: 14px; }

.search-bar { display: flex; gap: 10px; margin-bottom: 16px; }
.autocomplete-wrap { position: relative; flex: 1; }
.type-select {
  border: 2px solid #dfe6e9;
  border-radius: 12px;
  padding: 0 12px;
  font-size: 15px;
  background: #fff;
  color: #2d3436;
  min-width: 92px;
  outline: none;
}
.type-select:focus { border-color: #7761e5; }
.search-bar input {
  width: 100%;
  border: 2px solid #dfe6e9;
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 16px;
  outline: none;
  transition: .2s;
}
.search-bar input:focus { border-color: #7761e5; }

.search-results {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #dfe6e9;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0,0,0,.10);
  z-index: 20;
  max-height: 360px;
  overflow-y: auto;
}

.search-item {
  width: 100%;
  appearance: none;
  border: none;
  border-bottom: 1px solid #f1f5f8;
  background: #fff;
  text-align: left;
  cursor: pointer;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.search-item:last-child { border-bottom: none; }
.search-item:hover { background: #f7f5fd; }
.si-name { flex: 1; font-size: 16px; color: #2d3436; font-weight: 600; }
.si-right { display: inline-flex; align-items: center; gap: 10px; }
.si-type {
  font-size: 12px;
  color: #9aa8b5;
  background: #f0f4f8;
  padding: 2px 8px;
  border-radius: 999px;
}
.si-cal { font-size: 15px; color: #636e72; min-width: 92px; text-align: right; }
.si-name :deep(.kw-highlight) {
  background: #fff2b3;
  color: inherit;
  border-radius: 4px;
  padding: 0 2px;
}

.search-bar > .query-btn {
  border: none;
  border-radius: 10px;
  background: #42b983;
  color: #fff;
  font-weight: 600;
  padding: 0 18px;
  cursor: pointer;
}
.search-bar > .query-btn:disabled { opacity: .6; cursor: not-allowed; }

.error-box {
  margin-bottom: 14px;
  background: #fff1f0;
  color: #b63b30;
  border: 1px solid #f2b8b5;
  border-radius: 10px;
  padding: 10px 12px;
}

.season-board {
  position: relative;
  overflow: hidden;
  margin-bottom: 14px;
  border-radius: 16px;
  padding: 18px;
  min-height: calc(100vh - 185px);
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 8px;
  background: linear-gradient(135deg, #10213d 0%, #1f3a68 45%, #274f88 100%);
  color: #ecf3ff;
  border: 1px solid rgba(255,255,255,.12);
}

.season-board.theme-morning {
  background: linear-gradient(135deg, #ffe39c 0%, #ffb57a 48%, #ff8a74 100%);
  color: #40271f;
}

.season-board.theme-noon {
  background: linear-gradient(135deg, #68d6ff 0%, #5bb3ff 42%, #3b7dff 100%);
  color: #082a52;
}

.season-board.theme-night {
  background: linear-gradient(135deg, #161b3a 0%, #2a2f63 45%, #47307a 100%);
  color: #ecf3ff;
}

.sb-glow {
  position: absolute;
  inset: -60% auto auto -20%;
  width: 280px;
  height: 280px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(127,173,255,.35), transparent 65%);
  animation: glowFloat 7s ease-in-out infinite;
  pointer-events: none;
}

@keyframes glowFloat {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(24px, 16px); }
}

.sb-head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.sb-head h3 { margin: 0 0 4px; font-size: 22px; color: #fff; }
.sb-head p { margin: 0; color: #c9daf8; font-size: 13px; }

.season-board.theme-morning .sb-head h3,
.season-board.theme-morning .sb-head p,
.season-board.theme-morning .sb-label,
.season-board.theme-morning .sb-r-title,
.season-board.theme-morning .sb-r-reason,
.season-board.theme-morning .sb-tip-card li { color: #5a2f24; }

.season-board.theme-noon .sb-head h3,
.season-board.theme-noon .sb-head p,
.season-board.theme-noon .sb-label,
.season-board.theme-noon .sb-r-title,
.season-board.theme-noon .sb-r-reason,
.season-board.theme-noon .sb-tip-card li { color: #0e2f57; }

.sb-refresh {
  border: 1px solid rgba(255,255,255,.24);
  background: rgba(255,255,255,.12);
  color: #fff;
  border-radius: 10px;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 600;
}
.sb-refresh:disabled { opacity: .55; cursor: not-allowed; }

.sb-meta-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}

.sb-meta-card {
  border: 1px solid rgba(255,255,255,.18);
  background: rgba(255,255,255,.08);
  border-radius: 12px;
  padding: 14px 14px;
  min-height: 88px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.sb-label { font-size: 11px; color: #c9daf8; margin-bottom: 4px; }
.sb-value { font-size: 18px; color: #fff; font-weight: 700; }

.sb-recommend {
  position: relative;
  z-index: 1;
  border: 1px solid rgba(255,255,255,.2);
  background: rgba(255,255,255,.1);
  border-radius: 14px;
  padding: 14px 14px;
  margin-bottom: 8px;
}
.sb-r-title { font-size: 14px; color: #c9daf8; margin-bottom: 8px; font-weight: 700; }
.sb-r-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 6px;
  align-items: stretch;
}

.sb-r-item {
  display: flex;
  gap: 8px;
  border: 1px solid rgba(255,255,255,.2);
  border-radius: 12px;
  padding: 12px 12px;
  min-height: 188px;
  height: 188px;
  background: rgba(255,255,255,.08);
  align-items: center;
}

.sb-r-index {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  border: 1px solid rgba(255,255,255,.35);
  background: rgba(255,255,255,.14);
  flex: 0 0 30px;
}

.sb-r-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.sb-r-name { font-size: 30px; font-weight: 900; color: #fff; letter-spacing: .2px; line-height: 1.1; }
.sb-r-reason { margin-top: 8px; font-size: 15px; color: #dbe7ff; line-height: 1.62; }

.sb-tips-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.sb-tip-card {
  border: 1px solid rgba(255,255,255,.2);
  background: rgba(255,255,255,.08);
  border-radius: 12px;
  padding: 14px 14px;
  min-height: 156px;
}
.sb-tip-card.avoid { background: rgba(255, 210, 210, .12); }
.sb-tip-card h4 { margin: 0 0 8px; font-size: 16px; color: #fff; }
.sb-tip-card ul { margin: 0; padding-left: 18px; }
.sb-tip-card li { margin-bottom: 6px; font-size: 14px; color: #e9f1ff; line-height: 1.55; }

.sb-tips-grid { margin-top: auto; }

.season-board.theme-morning .sb-value,
.season-board.theme-morning .sb-r-name,
.season-board.theme-morning .sb-tip-card h4,
.season-board.theme-morning .sb-refresh { color: #3f271d; }

.season-board.theme-noon .sb-value,
.season-board.theme-noon .sb-r-name,
.season-board.theme-noon .sb-tip-card h4,
.season-board.theme-noon .sb-refresh { color: #06284b; }

.season-board.theme-morning .sb-meta-card,
.season-board.theme-morning .sb-recommend,
.season-board.theme-morning .sb-tip-card,
.season-board.theme-morning .sb-r-item {
  background: rgba(255,255,255,.24);
  border-color: rgba(255,255,255,.45);
}

.season-board.theme-noon .sb-meta-card,
.season-board.theme-noon .sb-recommend,
.season-board.theme-noon .sb-tip-card,
.season-board.theme-noon .sb-r-item {
  background: rgba(255,255,255,.2);
  border-color: rgba(255,255,255,.4);
}

.season-board.theme-morning .sb-tip-card.avoid,
.season-board.theme-noon .sb-tip-card.avoid {
  background: rgba(255, 228, 206, .35);
}

.season-board.loading { opacity: .94; }

.result-wrap { display: flex; flex-direction: column; gap: 14px; }
.card {
  background: #fff;
  border: 1px solid #e9edf3;
  border-radius: 12px;
  padding: 14px 16px;
}
.card h3 { margin: 0 0 10px; font-size: 22px; color: #2d3436; }
.card h4 { margin: 0 0 10px; font-size: 16px; color: #34495e; }

.property-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px;
}
.property-item {
  border: 1px solid #edf1f5;
  border-radius: 10px;
  background: #fbfcfe;
  padding: 8px 10px;
}
.pk { font-size: 12px; color: #81909d; margin-bottom: 4px; }
.pv {
  font-size: 13px;
  color: #2d3436;
  white-space: pre-wrap;
  word-break: break-word;
}

.relation-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.rel-list { margin: 0; padding-left: 18px; }
.rel-list li { margin-bottom: 8px; }
.rel-list span { color: #6c7a89; margin-left: 6px; font-size: 12px; }

.rel-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.rel-table th, .rel-table td {
  border-bottom: 1px solid #eef2f6;
  text-align: left;
  padding: 8px 6px;
  vertical-align: top;
}
.rel-table th { color: #60707d; font-weight: 600; }

.ing-jump-btn {
  border: 1px solid #d8dbe6;
  background: #fff;
  color: #4b5b6b;
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
.ing-jump-btn:hover { background: #eef6ff; border-color: #9ec6ff; color: #1f6fcb; }
.ing-jump-btn:disabled { opacity: .55; cursor: not-allowed; }

.steps-content :deep(.recipe-steps-list) { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.steps-content :deep(.recipe-step-item) { display: flex; align-items: flex-start; gap: 10px; }
.steps-content :deep(.step-index) {
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
.steps-content :deep(.step-text) { color: #2d3436; line-height: 1.72; font-size: 14px; }
.steps-content :deep(.step-verb) {
  display: inline-block;
  margin: 0 2px;
  padding: 0 6px;
  border-radius: 999px;
  background: #fff4d6;
  color: #9a5d00;
  font-weight: 700;
}

.empty { color: #95a5a6; font-size: 13px; }

@media (max-width: 1100px) {
  .relation-grid { grid-template-columns: 1fr; }
  .sb-r-list { grid-template-columns: 1fr; }
  .sb-r-item {
    min-height: 168px;
    height: auto;
  }
  .sb-meta-grid { grid-template-columns: 1fr; }
  .sb-tips-grid { grid-template-columns: 1fr; }
  .season-board { min-height: calc(100vh - 160px); }
  .sb-r-name { font-size: 24px; }
  .sb-r-reason { font-size: 14px; }
}
</style>

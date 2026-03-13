<template>
  <div class="stats-view">
    <div class="page-header">
      <h2>健康管理</h2>
      <div class="header-tools">
        <label>
          选择日期
          <input type="date" v-model="selectedDate" />
        </label>
      </div>
    </div>

    <div class="ring-grid">
      <section class="ring-card main">
        <div class="ring-top">
          <span>动态食谱</span>
          <strong>{{ selectedDate }}</strong>
        </div>

        <div class="center-row">
          <div class="side-col">
            <div class="side-label">饮食摄入</div>
            <div class="side-value">{{ dayTotals.calories }} kcal</div>
          </div>

          <div class="ring-wrap">
            <div class="ring" :style="ringStyle">
              <div class="ring-inner">
                <div class="ring-title">还可以吃</div>
                <div class="ring-value">{{ remainCalories }}</div>
                <div class="ring-sub">推荐预算 {{ plan.calories }} kcal</div>
              </div>
            </div>
          </div>

          <div class="side-col">
            <div class="side-label">运动消耗</div>
            <div class="side-value">{{ exerciseTotalCalories }} kcal</div>
          </div>
        </div>

        <div class="macro-row">
          <div class="macro-item">
            <div class="macro-name">碳水化合物</div>
            <div class="macro-num">{{ dayTotals.carbs }} / {{ plan.carbs }} 克</div>
            <div class="macro-bar"><span :style="{ width: macroPct(dayTotals.carbs, plan.carbs) + '%' }"></span></div>
          </div>
          <div class="macro-item">
            <div class="macro-name">蛋白质</div>
            <div class="macro-num">{{ dayTotals.protein }} / {{ plan.protein }} 克</div>
            <div class="macro-bar"><span :style="{ width: macroPct(dayTotals.protein, plan.protein) + '%' }"></span></div>
          </div>
          <div class="macro-item">
            <div class="macro-name">脂肪</div>
            <div class="macro-num">{{ dayTotals.fat }} / {{ plan.fat }} 克</div>
            <div class="macro-bar"><span :style="{ width: macroPct(dayTotals.fat, plan.fat) + '%' }"></span></div>
          </div>
        </div>
      </section>

      <section class="ring-card info">
        <h3>今日预算依据</h3>
        <ul>
          <li>年龄：{{ profileAge }} 岁</li>
          <li>性别：{{ profile.gender === 'male' ? '男' : '女' }}</li>
          <li>身高：{{ profile.height || 0 }} cm</li>
          <li>当前体重：{{ profile.weight || 0 }} kg</li>
          <li>目标体重：{{ profile.targetWeight || 0 }} kg</li>
          <li>减脂时长：{{ profile.fatLossWeeks || 0 }} 周</li>
          <li>BMR：{{ plan.bmr }} kcal</li>
          <li>TDEE：{{ plan.tdee }} kcal</li>
          <li>建议缺口：{{ plan.deficit }} kcal/天</li>
        </ul>

        <div class="exercise-entry">
          <h4>运动消耗录入（MET 估算）</h4>
          <div class="ee-row">
            <select v-model="exerciseForm.exerciseType">
              <option v-for="opt in metOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <input type="number" min="1" v-model.number="exerciseForm.durationMinutes" placeholder="时长(分钟)" />
          </div>
          <div class="ee-row">
            <input type="number" min="0" step="0.1" v-model.number="exerciseForm.met" placeholder="MET（可改）" />
            <input type="number" min="0" step="1" v-model.number="exerciseForm.manualCalories" placeholder="手动 kcal（可选）" />
          </div>
          <div class="ee-preview">预计消耗：{{ estimatedExerciseCalories }} kcal</div>
          <button class="ee-add-btn" @click="addExerciseLog" :disabled="exerciseSaving">
            {{ exerciseSaving ? '记录中...' : '记录运动消耗' }}
          </button>

          <div class="ee-list" v-if="exerciseLogs.length > 0">
            <div class="ee-item" v-for="log in exerciseLogs" :key="log.id">
              <span>{{ log.exercise_type }} · {{ Math.round(Number(log.duration_minutes || 0)) }} 分钟</span>
              <span>{{ Math.round(Number(log.calories || 0)) }} kcal</span>
              <button @click="removeExerciseLog(log.id)">删除</button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import API from '../api.js'

const userId = localStorage.getItem('user_id') || ''
const selectedDate = ref(new Date().toISOString().split('T')[0])

const profile = ref({
  gender: 'female',
  birthDate: '',
  height: 0,
  weight: 0,
  targetWeight: 0,
  fatLossWeeks: 0,
})

const dayTotals = ref({ calories: 0, protein: 0, fat: 0, carbs: 0 })
const exerciseLogs = ref([])
const exerciseTotalCalories = ref(0)
const exerciseSaving = ref(false)

const metOptions = [
  { value: 'walk', label: '快走', met: 4.3 },
  { value: 'run', label: '慢跑', met: 7.5 },
  { value: 'cycle', label: '骑行', met: 6.8 },
  { value: 'swim', label: '游泳', met: 8.0 },
  { value: 'strength', label: '力量训练', met: 5.0 },
  { value: 'hiit', label: 'HIIT', met: 9.0 },
  { value: 'yoga', label: '瑜伽', met: 3.0 },
]

const exerciseForm = ref({
  exerciseType: 'walk',
  durationMinutes: 30,
  met: 4.3,
  manualCalories: null,
})

const toInt = (v) => Math.max(0, Math.round(Number(v || 0)))

const profileAge = computed(() => {
  const b = profile.value.birthDate
  if (!b) return 25
  const birth = new Date(`${b}T00:00:00`)
  if (Number.isNaN(birth.getTime())) return 25
  const now = new Date()
  let age = now.getFullYear() - birth.getFullYear()
  const m = now.getMonth() - birth.getMonth()
  if (m < 0 || (m === 0 && now.getDate() < birth.getDate())) age -= 1
  return Math.max(15, age)
})

const plan = computed(() => {
  const weight = Number(profile.value.weight || 0) || 60
  const target = Number(profile.value.targetWeight || 0) || weight
  const height = Number(profile.value.height || 0) || 165
  const age = profileAge.value

  const isMale = profile.value.gender === 'male'
  const bmrRaw = 10 * weight + 6.25 * height - 5 * age + (isMale ? 5 : -161)
  const bmr = Math.max(900, Math.round(bmrRaw))

  const tdee = Math.round(bmr * 1.35)

  const loseKg = Math.max(0, weight - target)
  const weeks = Math.max(1, Number(profile.value.fatLossWeeks || 0) || 8)
  const deficitRaw = loseKg > 0 ? (loseKg * 7700) / (weeks * 7) : 0
  const deficit = Math.min(900, Math.max(0, Math.round(deficitRaw)))

  let calories = tdee - deficit
  const minSafe = isMale ? 1400 : 1200
  calories = Math.max(minSafe, calories)

  const protein = Math.max(Math.round(weight * 1.6), Math.round((calories * 0.30) / 4))
  const fat = Math.max(Math.round(weight * 0.8), Math.round((calories * 0.25) / 9))
  const carbs = Math.max(60, Math.round((calories - protein * 4 - fat * 9) / 4))

  return {
    bmr: toInt(bmr),
    tdee: toInt(tdee),
    deficit: toInt(deficit),
    calories: toInt(calories),
    protein: toInt(protein),
    fat: toInt(fat),
    carbs: toInt(carbs)
  }
})

const remainCalories = computed(() => {
  const remain = plan.value.calories + toInt(exerciseTotalCalories.value) - toInt(dayTotals.value.calories)
  return Math.max(0, remain)
})

const ringStyle = computed(() => {
  const consumed = toInt(dayTotals.value.calories)
  const budget = Math.max(1, plan.value.calories + toInt(exerciseTotalCalories.value))
  const ratio = Math.max(0, Math.min(1, consumed / budget))
  const deg = Math.round(ratio * 360)
  return {
    background: `conic-gradient(#37c78b ${deg}deg, #ecedf2 0deg)`
  }
})

const selectedExerciseLabel = computed(() => {
  const opt = metOptions.find((x) => x.value === exerciseForm.value.exerciseType)
  return opt ? opt.label : '运动'
})

const estimatedExerciseCalories = computed(() => {
  if (Number(exerciseForm.value.manualCalories || 0) > 0) {
    return toInt(exerciseForm.value.manualCalories)
  }
  const weight = Number(profile.value.weight || 0) || 60
  const met = Number(exerciseForm.value.met || 0)
  const min = Number(exerciseForm.value.durationMinutes || 0)
  if (met <= 0 || min <= 0) return 0
  return toInt(met * weight * (min / 60))
})

const macroPct = (value, goal) => {
  const g = Math.max(1, Number(goal || 1))
  return Math.max(0, Math.min(100, Math.round((Number(value || 0) / g) * 100)))
}

const loadProfile = async () => {
  if (!userId) return
  try {
    const res = await API.get(`/profile/?user_id=${userId}`)
    profile.value = {
      gender: res.data.gender || 'female',
      birthDate: res.data.birthDate || '',
      height: Number(res.data.height || 0),
      weight: Number(res.data.weight || 0),
      targetWeight: Number(res.data.targetWeight || 0),
      fatLossWeeks: Number(res.data.fatLossWeeks || 0),
    }
  } catch (e) {
    console.error(e)
  }
}

const loadDateTotals = async () => {
  if (!userId || !selectedDate.value) return
  try {
    const res = await API.get(`/diet-log/?user_id=${userId}&date=${selectedDate.value}`)
    const logs = res?.data?.logs || []
    const sum = logs.reduce((acc, item) => {
      acc.calories += Number(item.calories || 0)
      acc.protein += Number(item.protein || 0)
      acc.fat += Number(item.fat || 0)
      acc.carbs += Number(item.carbs || 0)
      return acc
    }, { calories: 0, protein: 0, fat: 0, carbs: 0 })

    dayTotals.value = {
      calories: toInt(sum.calories),
      protein: toInt(sum.protein),
      fat: toInt(sum.fat),
      carbs: toInt(sum.carbs)
    }
  } catch (e) {
    console.error(e)
    dayTotals.value = { calories: 0, protein: 0, fat: 0, carbs: 0 }
  }
}

const loadExerciseTotals = async () => {
  if (!userId || !selectedDate.value) return
  try {
    const res = await API.get(`/exercise-log/?user_id=${userId}&date=${selectedDate.value}`)
    exerciseLogs.value = res?.data?.logs || []
    exerciseTotalCalories.value = toInt(res?.data?.total_calories || 0)
  } catch (e) {
    console.error(e)
    exerciseLogs.value = []
    exerciseTotalCalories.value = 0
  }
}

const addExerciseLog = async () => {
  if (!userId || !selectedDate.value) return
  if (Number(exerciseForm.value.durationMinutes || 0) <= 0 && Number(exerciseForm.value.manualCalories || 0) <= 0) {
    return
  }

  exerciseSaving.value = true
  try {
    await API.post('/exercise-log/', {
      user_id: userId,
      date: selectedDate.value,
      exercise_type: selectedExerciseLabel.value,
      duration_minutes: Number(exerciseForm.value.durationMinutes || 0),
      met: Number(exerciseForm.value.met || 0),
      calories: Number(exerciseForm.value.manualCalories || 0),
    })
    exerciseForm.value.manualCalories = null
    await loadExerciseTotals()
  } catch (e) {
    console.error(e)
  } finally {
    exerciseSaving.value = false
  }
}

const removeExerciseLog = async (logId) => {
  try {
    await API.delete(`/exercise-log/?user_id=${userId}&log_id=${logId}`)
    await loadExerciseTotals()
  } catch (e) {
    console.error(e)
  }
}

watch(selectedDate, () => {
  loadDateTotals()
  loadExerciseTotals()
})

watch(() => exerciseForm.value.exerciseType, (type) => {
  const opt = metOptions.find((x) => x.value === type)
  if (opt) exerciseForm.value.met = opt.met
})

onMounted(async () => {
  await loadProfile()
  await loadDateTotals()
  await loadExerciseTotals()
})
</script>

<style scoped>
.stats-view { width: 100%; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.page-header h2 { margin: 0; font-size: 24px; color: #2c3348; }
.header-tools label { font-size: 13px; color: #67717f; display: inline-flex; gap: 8px; align-items: center; }
.header-tools input {
  border: 1px solid #dbe2ea;
  border-radius: 10px;
  padding: 7px 10px;
  font-size: 13px;
}

.ring-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 14px; }
.ring-card {
  background: #fff;
  border: 1px solid #e9edf3;
  border-radius: 18px;
  box-shadow: 0 8px 30px rgba(16, 24, 40, .05);
  padding: 18px;
}
.ring-top { display: flex; justify-content: space-between; color: #637082; font-weight: 700; margin-bottom: 8px; }
.ring-top strong { color: #2c3348; }

.center-row {
  display: grid;
  grid-template-columns: 1fr 280px 1fr;
  align-items: center;
  gap: 10px;
}
.side-col { text-align: center; }
.side-label { font-size: 14px; color: #637082; margin-bottom: 4px; font-weight: 700; }
.side-value { font-size: 34px; color: #2c3348; font-weight: 800; }

.ring-wrap { display: flex; justify-content: center; }
.ring {
  width: 260px;
  height: 260px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ring-inner {
  width: 212px;
  height: 212px;
  border-radius: 50%;
  background: #fff;
  box-shadow: inset 0 0 0 1px #edf2f7;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.ring-title { font-size: 20px; color: #637082; font-weight: 700; }
.ring-value { font-size: 62px; line-height: 1; color: #242a3f; font-weight: 800; margin: 6px 0; }
.ring-sub { font-size: 16px; color: #9aa3b2; font-weight: 600; }

.macro-row { margin-top: 14px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.macro-item { padding: 10px; border-radius: 12px; background: #f8fafc; border: 1px solid #edf1f5; }
.macro-name { color: #5f6a79; font-size: 14px; font-weight: 700; }
.macro-num { margin-top: 4px; color: #8d97a5; font-size: 13px; }
.macro-bar {
  margin-top: 8px;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: #e6ebf1;
}
.macro-bar span { display: block; height: 100%; background: #3bc48b; border-radius: 999px; }

.ring-card.info h3 { margin: 0 0 10px; font-size: 16px; color: #2c3348; }
.ring-card.info ul { margin: 0; padding-left: 18px; display: grid; gap: 6px; }
.ring-card.info li { color: #5d6878; font-size: 13px; }

.exercise-entry {
  margin-top: 14px;
  border-top: 1px dashed #e3e8ef;
  padding-top: 12px;
}
.exercise-entry h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #2c3348;
}
.ee-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}
.ee-row select,
.ee-row input {
  border: 1px solid #dbe2ea;
  border-radius: 8px;
  padding: 7px 9px;
  font-size: 12px;
}
.ee-preview {
  font-size: 12px;
  color: #5f6a79;
  margin: 4px 0 8px;
}
.ee-add-btn {
  border: 1px solid #1f2329;
  border-radius: 8px;
  background: #fff;
  color: #1f2329;
  padding: 8px 10px;
  font-size: 12px;
  cursor: pointer;
}
.ee-add-btn:disabled { opacity: .5; cursor: not-allowed; }

.ee-list {
  margin-top: 10px;
  display: grid;
  gap: 6px;
}
.ee-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 8px;
  border: 1px solid #edf1f5;
  background: #fafbfd;
  border-radius: 8px;
  padding: 6px 8px;
  font-size: 12px;
  color: #5d6878;
}
.ee-item button {
  border: 1px solid #cfd8e6;
  border-radius: 6px;
  background: #fff;
  color: #415064;
  font-size: 11px;
  padding: 4px 7px;
  cursor: pointer;
}

@media (max-width: 1100px) {
  .ring-grid { grid-template-columns: 1fr; }
  .center-row { grid-template-columns: 1fr; }
}
</style>

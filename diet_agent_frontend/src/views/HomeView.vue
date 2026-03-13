<template>
  <div class="home-view">
    <div class="page-header">
      <h2>主页</h2>
      <p>体重管理概览</p>
    </div>

    <section class="wm-card">
      <div class="wm-head">
        <h3>体重管理方案</h3>
        <span class="wm-week">第 {{ progress.currentWeek }}/{{ progress.totalWeeks }} 周</span>
      </div>

      <div class="wm-main">
        <div class="wm-col">
          <div class="wm-num">{{ formatNum(profile.initialWeight) }}</div>
          <div class="wm-label">初始 (kg)</div>
        </div>

        <div class="wm-ring-wrap">
          <div class="wm-ring" :style="ringStyle">
            <div class="wm-ring-inner">
              <div class="wm-loss">{{ formatNum(progress.lostKg) }}</div>
              <div class="wm-loss-label">已减去(公斤)</div>
              <div class="wm-rate">进度 {{ Math.round(progress.ratio * 100) }}%</div>
            </div>
          </div>
        </div>

        <div class="wm-col">
          <div class="wm-num">{{ formatNum(profile.targetWeight) }}</div>
          <div class="wm-label">目标 (kg)</div>
        </div>
      </div>

      <div class="wm-foot">
        <div>当前体重：{{ formatNum(profile.weight) }} kg</div>
        <div>还需减重：{{ formatNum(progress.leftKg) }} kg</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import API from '../api.js'

const userId = localStorage.getItem('user_id') || ''

const profile = ref({
  initialWeight: 0,
  targetWeight: 0,
  weight: 0,
  fatLossWeeks: 0,
  fatLossStartDate: ''
})

const formatNum = (v) => Number(v || 0).toFixed(2)

const progress = computed(() => {
  const initial = Number(profile.value.initialWeight || 0)
  const target = Number(profile.value.targetWeight || 0)
  const current = Number(profile.value.weight || 0)
  const total = Math.max(0, initial - target)
  const lost = Math.max(0, initial - current)
  const ratio = total > 0 ? Math.max(0, Math.min(1, lost / total)) : 0
  const leftKg = Math.max(0, total - lost)

  const totalWeeks = Math.max(1, Number(profile.value.fatLossWeeks || 0) || 1)
  let currentWeek = 1
  if (profile.value.fatLossStartDate) {
    const start = new Date(profile.value.fatLossStartDate)
    if (!Number.isNaN(start.getTime())) {
      const days = Math.floor((Date.now() - start.getTime()) / (1000 * 60 * 60 * 24))
      currentWeek = Math.max(1, Math.min(totalWeeks, Math.floor(days / 7) + 1))
    }
  }

  return {
    ratio,
    lostKg: lost,
    leftKg,
    totalWeeks,
    currentWeek,
  }
})

const ringStyle = computed(() => {
  const angle = `${Math.round(progress.value.ratio * 360)}deg`
  return {
    background: `conic-gradient(#3dcf8e ${angle}, #e9edf3 0deg)`
  }
})

const loadProfile = async () => {
  if (!userId) return
  try {
    const res = await API.get(`/profile/?user_id=${userId}`)
    profile.value = {
      initialWeight: Number(res.data.initialWeight || 0),
      targetWeight: Number(res.data.targetWeight || 0),
      weight: Number(res.data.weight || 0),
      fatLossWeeks: Number(res.data.fatLossWeeks || 0),
      fatLossStartDate: res.data.fatLossStartDate || ''
    }
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadProfile()
})
</script>

<style scoped>
.home-view { width: 100%; }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 24px; color: #2d3436; }
.page-header p { margin: 4px 0 0; color: #7a8793; }

.wm-card {
  background: #fff;
  border-radius: 18px;
  border: 1px solid #e8edf3;
  box-shadow: 0 8px 26px rgba(16, 24, 40, .06);
  padding: 22px;
}

.wm-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.wm-head h3 { margin: 0; font-size: 34px; color: #353a53; font-weight: 800; }
.wm-week {
  font-size: 36px;
  font-weight: 800;
  color: #272b3f;
  background: #d8f3e5;
  border-radius: 12px;
  padding: 4px 12px;
}

.wm-main {
  display: grid;
  grid-template-columns: 1fr 320px 1fr;
  align-items: center;
  gap: 18px;
}
.wm-col { text-align: center; }
.wm-num { font-size: 58px; font-weight: 800; color: #353a53; line-height: 1; }
.wm-label { margin-top: 6px; font-size: 40px; color: #a6acbb; font-weight: 600; }

.wm-ring-wrap { display: flex; justify-content: center; }
.wm-ring {
  width: 300px;
  height: 300px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 0 0 1px #e8edf3;
}
.wm-ring-inner {
  width: 248px;
  height: 248px;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 0%, #e3fff1 0%, #f9fcfb 52%, #fff 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.wm-loss { font-size: 56px; font-weight: 800; color: #3b3f5c; line-height: 1; }
.wm-loss-label { margin-top: 6px; font-size: 24px; color: #a6acbb; font-weight: 700; }
.wm-rate { margin-top: 8px; font-size: 18px; color: #4aa979; font-weight: 700; }

.wm-foot {
  margin-top: 16px;
  border-top: 1px dashed #e5ebf2;
  padding-top: 12px;
  display: flex;
  justify-content: space-between;
  color: #5b6572;
  font-size: 14px;
}

@media (max-width: 1100px) {
  .wm-main { grid-template-columns: 1fr; }
  .wm-week { font-size: 22px; }
  .wm-head h3 { font-size: 24px; }
  .wm-label { font-size: 18px; }
  .wm-num { font-size: 36px; }
}
</style>

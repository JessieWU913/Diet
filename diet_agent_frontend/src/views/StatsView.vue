<template>
  <div class="stats-view">
    <div class="page-header">
      <h2>📊 营养分析</h2>
      <div class="period-tabs">
        <button v-for="p in periods" :key="p.days" :class="{ active: days === p.days }" @click="changePeriod(p.days)">{{ p.label }}</button>
      </div>
    </div>

    <!-- 今日概览 -->
    <div class="today-row">
      <div class="today-card" v-for="item in todaySummary" :key="item.label">
        <span class="tc-icon">{{ item.icon }}</span>
        <div class="tc-info">
          <span class="tc-value">{{ item.value }}</span>
          <span class="tc-label">{{ item.label }}</span>
        </div>
        <div class="tc-bar">
          <div class="tc-fill" :style="{ width: item.pct + '%', background: item.color }"></div>
        </div>
        <span class="tc-goal">/ {{ item.goal }}{{ item.unit }}</span>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="charts-row">
      <div class="chart-card">
        <h3>每日热量摄入趋势</h3>
        <div ref="calorieChartRef" class="chart-box"></div>
      </div>
      <div class="chart-card">
        <h3>宏量营养素分布</h3>
        <div ref="macroChartRef" class="chart-box"></div>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-card wide">
        <h3>蛋白质 / 脂肪 / 碳水趋势对比</h3>
        <div ref="trendChartRef" class="chart-box"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import API from '../api.js'

const userId = localStorage.getItem('user_id') || ''
const days = ref(7)
const periods = [
  { days: 3, label: '近3天' },
  { days: 7, label: '近7天' },
  { days: 14, label: '近14天' },
  { days: 30, label: '近30天' },
]

const calorieChartRef = ref(null)
const macroChartRef = ref(null)
const trendChartRef = ref(null)
let calorieChart = null
let macroChart = null
let trendChart = null

const rawData = ref([])

// 目标（简易，可从后端个人信息获取）
const goals = { calories: 2000, protein: 60, fat: 65, carbs: 250 }

const todaySummary = ref([])

const buildTodaySummary = () => {
  const today = new Date().toISOString().split('T')[0]
  const todayData = rawData.value.find(d => d.date === today) || { calories: 0, protein: 0, fat: 0, carbs: 0 }
  todaySummary.value = [
    { icon: '🔥', label: '热量', value: Math.round(todayData.calories), goal: goals.calories, unit: 'kcal', pct: Math.min(100, (todayData.calories / goals.calories) * 100), color: '#ff6b6b' },
    { icon: '💪', label: '蛋白质', value: Math.round(todayData.protein), goal: goals.protein, unit: 'g', pct: Math.min(100, (todayData.protein / goals.protein) * 100), color: '#4ecdc4' },
    { icon: '🫒', label: '脂肪', value: Math.round(todayData.fat), goal: goals.fat, unit: 'g', pct: Math.min(100, (todayData.fat / goals.fat) * 100), color: '#ffd93d' },
    { icon: '🌾', label: '碳水', value: Math.round(todayData.carbs), goal: goals.carbs, unit: 'g', pct: Math.min(100, (todayData.carbs / goals.carbs) * 100), color: '#6c5ce7' },
  ]
}

const loadData = async () => {
  try {
    const res = await API.get(`/nutrition-summary/?user_id=${userId}&days=${days.value}`)
    rawData.value = res.data.summary || []
  } catch (e) { console.error(e) }
  buildTodaySummary()
  await nextTick()
  renderCharts()
}

const changePeriod = (d) => {
  days.value = d
  loadData()
}

const renderCharts = () => {
  const dates = rawData.value.map(d => d.date)
  const cals = rawData.value.map(d => Math.round(d.calories))
  const proteins = rawData.value.map(d => Math.round(d.protein))
  const fats = rawData.value.map(d => Math.round(d.fat))
  const carbs = rawData.value.map(d => Math.round(d.carbs))

  // 热量柱状图
  if (calorieChartRef.value) {
    if (!calorieChart) calorieChart = echarts.init(calorieChartRef.value)
    calorieChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', name: 'kcal' },
      series: [
        { data: cals, type: 'bar', itemStyle: { color: '#ff6b6b', borderRadius: [6, 6, 0, 0] }, barMaxWidth: 36 },
        { data: Array(dates.length).fill(goals.calories), type: 'line', lineStyle: { type: 'dashed', color: '#dfe6e9' }, symbol: 'none', name: '目标' }
      ],
      grid: { top: 30, bottom: 30, left: 50, right: 20 }
    })
  }

  // 宏量营养素圆环
  const totalP = proteins.reduce((a, b) => a + b, 0)
  const totalF = fats.reduce((a, b) => a + b, 0)
  const totalC = carbs.reduce((a, b) => a + b, 0)
  if (macroChartRef.value) {
    if (!macroChart) macroChart = echarts.init(macroChartRef.value)
    macroChart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c}g ({d}%)' },
      legend: { bottom: 0, textStyle: { fontSize: 12 } },
      series: [{
        type: 'pie', radius: ['45%', '70%'], center: ['50%', '45%'],
        label: { show: false },
        data: [
          { value: totalP, name: '蛋白质', itemStyle: { color: '#4ecdc4' } },
          { value: totalF, name: '脂肪', itemStyle: { color: '#ffd93d' } },
          { value: totalC, name: '碳水', itemStyle: { color: '#6c5ce7' } },
        ]
      }]
    })
  }

  // 三线趋势
  if (trendChartRef.value) {
    if (!trendChart) trendChart = echarts.init(trendChartRef.value)
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['蛋白质', '脂肪', '碳水'], bottom: 0 },
      xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', name: 'g' },
      series: [
        { name: '蛋白质', data: proteins, type: 'line', smooth: true, lineStyle: { color: '#4ecdc4' }, itemStyle: { color: '#4ecdc4' } },
        { name: '脂肪', data: fats, type: 'line', smooth: true, lineStyle: { color: '#ffd93d' }, itemStyle: { color: '#ffd93d' } },
        { name: '碳水', data: carbs, type: 'line', smooth: true, lineStyle: { color: '#6c5ce7' }, itemStyle: { color: '#6c5ce7' } },
      ],
      grid: { top: 30, bottom: 40, left: 50, right: 20 }
    })
  }
}

const handleResize = () => {
  calorieChart?.resize()
  macroChart?.resize()
  trendChart?.resize()
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  calorieChart?.dispose()
  macroChart?.dispose()
  trendChart?.dispose()
})
</script>

<style scoped>
.stats-view { width: 100%; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.page-header h2 { font-size: 22px; color: #2d3436; }
.period-tabs { display: flex; gap: 6px; }
.period-tabs button { padding: 7px 16px; border: 1px solid #dfe6e9; border-radius: 20px; background: #fff; font-size: 13px; cursor: pointer; color: #636e72; transition: .2s; }
.period-tabs button.active { background: #7761e5; color: #fff; border-color: #7761e5; }

.today-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }
.today-card { background: #fff; border-radius: 14px; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,.04); display: flex; flex-direction: column; gap: 8px; }
.tc-icon { font-size: 24px; }
.tc-info { display: flex; align-items: baseline; gap: 6px; }
.tc-value { font-size: 26px; font-weight: 700; color: #2d3436; }
.tc-label { font-size: 13px; color: #b2bec3; }
.tc-bar { height: 6px; background: #f0f2f5; border-radius: 3px; overflow: hidden; }
.tc-fill { height: 100%; border-radius: 3px; transition: width .5s; }
.tc-goal { font-size: 12px; color: #b2bec3; }

.charts-row { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 16px; }
.charts-row:has(.wide) { grid-template-columns: 1fr; }
.chart-card { background: #fff; border-radius: 14px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
.chart-card.wide { grid-column: 1 / -1; }
.chart-card h3 { font-size: 15px; color: #2d3436; margin: 0 0 12px; }
.chart-box { width: 100%; height: 320px; }
</style>

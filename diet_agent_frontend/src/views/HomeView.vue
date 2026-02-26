<script setup>
import { ref } from 'vue'
// 这里可以用 ECharts 做简单的仪表盘
</script>

<template>
  <div class="page-container">
    <el-row :gutter="20">
      <el-col :xs="24" :md="6">
        <el-card class="profile-card info-card">
          <div class="avatar-wrapper">
            <el-avatar :size="100" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png" />
            <h2>小吴</h2>
            <p class="subtitle">减脂中 🔥</p>
          </div>
          <div class="metrics">
            <div class="metric-item">
              <span>BMI</span>
              <strong>21.5</strong>
            </div>
            <div class="metric-item">
              <span>体重</span>
              <strong>52kg</strong>
            </div>
          </div>
          <el-progress type="dashboard" :percentage="70" color="#4CAF50">
            <template #default="{ percentage }">
              <span class="progress-label">今日热量<br>{{ percentage }}%</span>
            </template>
          </el-progress>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="18">
        <div class="right-content">
          <el-card class="section-card">
            <template #header>
              <div class="card-header">📅 本周记录概览</div>
            </template>
            <div class="week-grid">
               <div v-for="i in 7" :key="i" class="day-box">
                 <span class="day-name">周{{ i }}</span>
                 <div class="status-dot success"></div>
               </div>
            </div>
          </el-card>

          <el-card class="section-card">
             <template #header>📊 营养分布</template>
             <div class="nutrition-row">
               <el-progress :text-inside="true" :stroke-width="20" :percentage="50" status="success" />
               <span class="label">蛋白质 (50g/100g)</span>
             </div>
             <div class="nutrition-row">
               <el-progress :text-inside="true" :stroke-width="20" :percentage="80" status="warning" />
               <span class="label">碳水 (160g/200g)</span>
             </div>
          </el-card>

          <el-card class="section-card ai-card">
             <template #header>🤖 AI 今日建议</template>
             <div class="ai-suggestion">
               <p>根据您昨日的摄入，建议今日晚餐增加深色蔬菜摄入。推荐：【白灼菜心】。</p>
             </div>
          </el-card>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.page-container { padding: 20px; max-width: 1440px; margin: 0 auto; }
.info-card { text-align: center; height: 100%; }
.avatar-wrapper { margin-bottom: 20px; }
.metrics { display: flex; justify-content: space-around; margin-bottom: 20px; }
.section-card { margin-bottom: 20px; }
.week-grid { display: flex; justify-content: space-between; }
.day-box { text-align: center; padding: 10px; background: #f9f9f9; border-radius: 8px; width: 12%; }
.status-dot { width: 10px; height: 10px; border-radius: 50%; background: #ddd; margin: 5px auto; }
.status-dot.success { background: #67C23A; }
.nutrition-row { margin-bottom: 15px; }
.label { font-size: 12px; color: #666; display: block; margin-top: 5px; }
</style>

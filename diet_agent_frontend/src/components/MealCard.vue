<template>
  <div class="meal-card" :class="{ 'export-mode': isExporting }" ref="cardRef">
    <div class="card-header" @click="isExpanded = !isExpanded">
      <div class="title-area">
        <h4 class="dish-name">{{ recipe.name }}</h4>
        <span class="calories">{{ recipe.calories }} kcal</span>
      </div>
      <div class="header-actions">
        <span class="expand-icon" v-if="!isExporting">{{ isExpanded ? '收起 ▴' : '展开 ▾' }}</span>
      </div>
    </div>

    <transition name="expand">
      <div v-if="isExpanded || isExporting" class="card-details">
        <div class="divider"></div>

        <div class="card-toolbar" v-if="!isExporting">
          <button class="tool-btn export" @click.stop="exportCardImage">存为图片</button>
          <button class="tool-btn delete" @click.stop="deleteCard">删除该菜</button>
        </div>

        <div class="details-content" v-html="formattedDetails"></div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { marked } from 'marked'
import html2canvas from 'html2canvas'

const props = defineProps({
  recipe: { type: Object, required: true },
  date: { type: String, required: true }
})
const emit = defineEmits(['delete'])

const cardRef = ref(null)
const isExpanded = ref(false)
const isExporting = ref(false)

const formattedDetails = computed(() => {
  return marked.parse(props.recipe.details || '暂无详细做法')
})

const deleteCard = () => {
  if(confirm(`确定要从菜谱单中移除【${props.recipe.name}】吗？`)){
    emit('delete', props.recipe.id, props.date)
  }
}

const exportCardImage = async () => {
  if (!cardRef.value || isExporting.value) return

  const originalExpanded = isExpanded.value
  isExporting.value = true

  await nextTick()
  await new Promise(resolve => setTimeout(resolve, 100))

  try {
    const canvas = await html2canvas(cardRef.value, {
      backgroundColor: '#ffffff',
      scale: 2,
      useCORS: true
    })
    const link = document.createElement('a')
    link.download = `菜谱_${props.recipe.name}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  } catch (err) {
    alert("生成图片失败！")
    console.error(err)
  } finally {
    isExporting.value = false
    isExpanded.value = originalExpanded
  }
}
</script>

<style scoped>
.meal-card { background: white; border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); transition: all 0.2s; border: 1px solid transparent; }
.meal-card:hover { box-shadow: 0 6px 16px rgba(0,0,0,0.08); border-color: #42b983; }

.card-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
.title-area { display: flex; align-items: center; gap: 10px; }
.dish-name { margin: 0; font-size: 16px; color: #2c3e50; }
.calories { font-size: 12px; font-weight: bold; color: #e74c3c; background: #fdf0ed; padding: 4px 8px; border-radius: 8px; }
.expand-icon { font-size: 12px; color: #95a5a6; }
.divider { height: 1px; background: #eee; margin: 12px 0; }

.card-toolbar { display: flex; gap: 10px; margin-bottom: 12px; justify-content: flex-end; }
.tool-btn { border: none; padding: 4px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; transition: 0.2s; font-weight: bold; }
.tool-btn.export { background: #e1f0fa; color: #2980b9; }
.tool-btn.export:hover { background: #3498db; color: white; }
.tool-btn.delete { background: #fdf0ed; color: #c0392b; }
.tool-btn.delete:hover { background: #e74c3c; color: white; }

.card-details { overflow: hidden; }
.details-content { max-height: 250px; overflow-y: auto; font-size: 13px; color: #34495e; line-height: 1.6; padding-right: 5px; }
.details-content::-webkit-scrollbar { width: 6px; }
.details-content::-webkit-scrollbar-thumb { background: #bdc3c7; border-radius: 4px; }
.details-content::-webkit-scrollbar-track { background: #f1f1f1; }

.details-content :deep(p) { margin: 0 0 8px 0; }
.details-content :deep(strong) { color: #2c3e50; }
.details-content :deep(ul) { margin: 4px 0; padding-left: 20px; }

.expand-enter-active, .expand-leave-active { transition: all 0.3s ease; max-height: 600px; opacity: 1; }
.expand-enter-from, .expand-leave-to { max-height: 0; opacity: 0; }

.export-mode { box-shadow: none !important; border: 1px solid #eee; }
.export-mode .card-details { transition: none !important; }
.export-mode .details-content {
  max-height: none !important;
  overflow: visible !important;
}
</style>

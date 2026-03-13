<template>
  <div class="admin-view">
    <div class="admin-head">
      <div>
        <h2>管理员控制台</h2>
        <p>查看用户注册信息、用户偏好与用户历史记录。</p>
      </div>
      <button class="ui-btn primary" @click="activeTab === 'overview' ? loadOverview() : submitImport()" :disabled="loading || (activeTab === 'update' && (importing || !importFile))">
        {{ activeTab === 'overview' ? (loading ? '加载中...' : '刷新数据') : (importing ? '导入中...' : '开始导入') }}
      </button>
    </div>

    <div v-if="errorText" class="error-box">{{ errorText }}</div>

    <section v-if="activeTab === 'update'" class="card import-card">
      <h3>数据更新模块</h3>
      <p class="import-desc">
        上传 JSON 文件并选择导入类型：食材、菜谱或食材关系。系统会做去重导入并补全可补全字段。
      </p>
      <p class="import-tip">目录不受限制。请填写真实绝对路径导入（必填）。</p>

      <div class="import-form-row full-width">
        <label class="import-label">导入类型</label>
        <select v-model="importType" class="import-select" :disabled="importing">
          <option value="ingredient">食材 JSON</option>
          <option value="recipe">菜谱 JSON</option>
          <option value="relation">食材关系 JSON</option>
        </select>
      </div>

      <div class="import-form-row full-width">
        <label class="import-label">真实文件绝对路径（自动回填，可手动修正）</label>
        <input
          v-model.trim="absolutePath"
          class="path-input"
          :disabled="importing"
          placeholder="例如：/xxx/xxx/xxx.json"
        />
      </div>

      <div class="import-form-row full-width">
        <label class="import-label">选择文件</label>
        <div class="file-picker-wrap">
          <input ref="fileInputRef" class="import-file-hidden" type="file" accept="application/json,.json" @change="onFileChange" :disabled="importing" />
          <button type="button" class="ui-btn ghost" :disabled="importing" @click="openFilePicker">选择 JSON 文件</button>
          <span class="file-name">{{ importFile ? importFile.name : '未选择文件' }}</span>
        </div>
      </div>

      <div class="import-actions">
        <button class="ui-btn accent" :disabled="importing || (!absolutePath && !importFile)" @click="submitImport">
          {{ importing ? '导入中...' : '开始导入' }}
        </button>
        <button class="ui-btn ghost" :disabled="importing" @click="previewImport">导入前预览</button>
        <button class="ui-btn ghost danger" :disabled="importing || !importFile" @click="cancelUpload">取消上传</button>
      </div>

      <div class="progress-wrap" v-if="importing || importProgress > 0">
        <div class="progress-head">
          <span>{{ importStageText }}</span>
          <span>{{ importProgress }}%</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: `${importProgress}%` }"></div>
        </div>
      </div>

      <div class="path-box" v-if="displayImportPath">
        <div class="path-label">当前用于导入的路径</div>
        <div class="path-value">{{ displayImportPath }}</div>
      </div>

      <div v-if="importResult" class="import-result">
        <h4>导入结果</h4>
        <ul>
          <li>类型：{{ importResult.import_type }}</li>
          <li v-for="(v, k) in importResult.stats" :key="k">{{ k }}: {{ v }}</li>
        </ul>
      </div>

      <div v-if="previewResult" class="import-result">
        <h4>导入预览（Dry-run）</h4>
        <ul>
          <li v-for="(v, k) in previewResult.preview" :key="`pv-${k}`" v-show="k !== 'diff_samples'">{{ k }}: {{ formatPreviewValue(v) }}</li>
        </ul>
        <div v-if="Array.isArray(previewResult.preview?.diff_samples) && previewResult.preview.diff_samples.length > 0" class="diff-box">
          <div class="path-label">关键差异示例</div>
          <ul>
            <li v-for="(d, idx) in previewResult.preview.diff_samples" :key="`d-${idx}`">
              {{ d.name }} / {{ d.action }} / {{ (d.changed_fields || []).join(', ') }}
            </li>
          </ul>
        </div>
      </div>

      <div class="import-result">
        <div class="quality-head">
          <h4>导入任务日志与回滚</h4>
          <div class="q-actions">
            <button class="ui-btn ghost" @click="loadImportTasks">刷新日志</button>
            <button class="ui-btn ghost danger" @click="rollbackLatestRelationImport">回滚最近关系导入</button>
          </div>
        </div>
        <div class="task-empty" v-if="importTasks.length === 0">暂无导入任务</div>
        <table v-else class="task-table">
          <thead>
            <tr>
              <th>任务ID</th>
              <th>类型</th>
              <th>来源</th>
              <th>文件</th>
              <th>开始</th>
              <th>结束</th>
              <th>耗时(ms)</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in importTasks" :key="t.id">
              <td>{{ t.id }}</td>
              <td>{{ t.import_type }}</td>
              <td>{{ t.source }}</td>
              <td>{{ t.file_name || '—' }}</td>
              <td>{{ t.started_at || '—' }}</td>
              <td>{{ t.ended_at || '—' }}</td>
              <td>{{ t.duration_ms ?? 0 }}</td>
              <td>{{ t.status }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="import-result">
        <div class="quality-head">
          <h4>数据质量巡检面板</h4>
          <div class="q-actions">
            <button class="ui-btn ghost" @click="scanDataQuality">开始巡检</button>
            <button class="ui-btn ghost" @click="fixDataQuality('fix_missing_info')">修复 missing_info</button>
            <button class="ui-btn ghost" @click="fixDataQuality('fill_empty_relation_desc')">修复空描述关系</button>
          </div>
        </div>
        <ul v-if="qualityChecks" class="qc-list">
          <li v-for="(v, k) in qualityChecks" :key="`qc-${k}`">{{ k }}: {{ v }}</li>
        </ul>
        <div v-if="qualitySuggestions.length > 0" class="diff-box">
          <div class="path-label">修复建议</div>
          <ul>
            <li v-for="(s, i) in qualitySuggestions" :key="`qs-${i}`">{{ s }}</li>
          </ul>
        </div>
      </div>
    </section>

    <template v-if="activeTab === 'overview'">
    <section class="stats-grid" v-if="stats">
      <div class="stat-card">
        <div class="k">用户数</div>
        <div class="v">{{ stats.user_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="k">饮食日志总数</div>
        <div class="v">{{ stats.diet_log_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="k">聊天会话总数</div>
        <div class="v">{{ stats.chat_session_count ?? 0 }}</div>
      </div>
    </section>

    <section class="card">
      <h3>用户总览</h3>
      <div v-if="users.length === 0" class="empty">
        暂无用户数据。若你之前执行过 import_full_graph.py --clear-all（或旧版本 --clear），用户节点可能已被清空，需要重新注册用户。
      </div>
      <table v-else class="u-table">
        <thead>
          <tr>
            <th>用户ID</th>
            <th>昵称</th>
            <th>注册时间</th>
            <th>性别</th>
            <th>生日</th>
            <th>身高</th>
            <th>体重</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.user_id" @click="selectUser(u)" :class="{ active: activeUserId === u.user_id }">
            <td>{{ u.user_id }}</td>
            <td>{{ u.registration.name || '—' }}</td>
            <td>{{ u.registration.created_at || '—' }}</td>
            <td>{{ u.registration.gender || '—' }}</td>
            <td>{{ u.registration.birth_date || '—' }}</td>
            <td>{{ numberOrDash(u.registration.height, 'cm') }}</td>
            <td>{{ numberOrDash(u.registration.weight, 'kg') }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="activeUser" class="detail-grid">
      <div class="card">
        <h3>用户偏好</h3>
        <div class="pref-group">
          <div class="pk">过敏源</div>
          <div class="pv">{{ joinOrDash(activeUser.preferences.allergies) }}</div>
        </div>
        <div class="pref-group">
          <div class="pk">不喜欢食材</div>
          <div class="pv">{{ joinOrDash(activeUser.preferences.dislikes) }}</div>
        </div>
        <div class="pref-group">
          <div class="pk">常用食材偏好</div>
          <div class="pv">{{ joinOrDash(activeUser.preferences.favorite_ingredients) }}</div>
        </div>
        <div class="pref-group">
          <div class="pk">最近点赞学习</div>
          <div class="pv">{{ joinOrDash(activeUser.preferences.positive_feedback) }}</div>
        </div>
      </div>

      <div class="card">
        <h3>用户历史记录</h3>
        <div class="history-block">
          <h4>饮食日志</h4>
          <div v-if="activeUser.history.diet_logs.length === 0" class="empty">暂无饮食日志</div>
          <ul v-else class="history-list">
            <li v-for="log in activeUser.history.diet_logs" :key="log.log_id">
              {{ log.date || '—' }} / {{ log.meal_type || '—' }} / {{ log.food_name || '—' }} / {{ log.calories ?? 0 }} kcal
            </li>
          </ul>
        </div>

        <div class="history-block">
          <h4>聊天历史</h4>
          <div v-if="activeUser.history.chat_sessions.length === 0" class="empty">暂无聊天会话</div>
          <ul v-else class="history-list">
            <li v-for="s in activeUser.history.chat_sessions" :key="s.session_id">
              {{ s.created_at || '—' }} / {{ s.title || '未命名会话' }} / {{ s.msg_count ?? 0 }} 条消息
            </li>
          </ul>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="quality-head">
        <h3>用户行为审计</h3>
        <div class="audit-filter">
          <input type="date" v-model="auditStartDate" class="audit-date" />
          <input type="date" v-model="auditEndDate" class="audit-date" />
          <button class="ui-btn ghost" @click="loadUserAudit">查询</button>
        </div>
      </div>
      <div v-if="auditData" class="audit-grid">
        <div class="stat-card">
          <div class="k">日志活跃用户</div>
          <div class="v">{{ auditData.active_users?.by_diet_log ?? 0 }}</div>
        </div>
        <div class="stat-card">
          <div class="k">聊天活跃用户</div>
          <div class="v">{{ auditData.active_users?.by_chat ?? 0 }}</div>
        </div>
        <div class="stat-card">
          <div class="k">记录到的失败请求</div>
          <div class="v">{{ auditData.failed_requests_recorded ?? 0 }}</div>
        </div>
      </div>
      <table v-if="auditData?.top_users?.length" class="task-table">
        <thead>
          <tr>
            <th>用户ID</th>
            <th>日志数</th>
            <th>会话数</th>
            <th>收藏数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in auditData.top_users" :key="`au-${u.user_id}`">
            <td>{{ u.user_id }}</td>
            <td>{{ u.log_count }}</td>
            <td>{{ u.chat_count }}</td>
            <td>{{ u.collect_count }}</td>
          </tr>
        </tbody>
      </table>
    </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import API from '../api.js'

const route = useRoute()

const loading = ref(false)
const errorText = ref('')
const stats = ref(null)
const users = ref([])
const activeUserId = ref('')
const importType = ref('ingredient')
const importFile = ref(null)
const importing = ref(false)
const importResult = ref(null)
const previewResult = ref(null)
const absolutePath = ref('')
const fileInputRef = ref(null)
const activeTab = computed(() => (route.name === 'AdminUpdate' ? 'update' : 'overview'))
const displayImportPath = computed(() => absolutePath.value)
const importProgress = ref(0)
const importStageText = ref('')
const importTasks = ref([])
const qualityChecks = ref(null)
const qualitySuggestions = ref([])
const auditData = ref(null)
const auditStartDate = ref('')
const auditEndDate = ref('')

const activeUser = computed(() => users.value.find((u) => u.user_id === activeUserId.value) || null)

const numberOrDash = (v, suffix = '') => {
  if (v === null || v === undefined || v === '' || Number(v) === 0) return '—'
  return `${v}${suffix ? ` ${suffix}` : ''}`
}

const joinOrDash = (arr) => {
  if (!Array.isArray(arr) || arr.length === 0) return '—'
  return arr.join('、')
}

const selectUser = (u) => {
  activeUserId.value = u.user_id
}

const onFileChange = (e) => {
  const f = e?.target?.files?.[0]
  importFile.value = f || null
  if (!f) return

  // In desktop-like runtimes (e.g., Electron), File.path may contain absolute path.
  const candidate = String(f.path || '').trim()
  const isAbs = candidate.startsWith('/') || /^[A-Za-z]:[\\/]/.test(candidate)
  const isFake = candidate.toLowerCase().includes('fakepath')
  if (isAbs && !isFake) {
    absolutePath.value = candidate
  }
}

const openFilePicker = () => {
  if (fileInputRef.value) fileInputRef.value.click()
}

const cancelUpload = () => {
  importFile.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
}

const submitImport = async () => {
  const token = localStorage.getItem('admin_token') || ''
  if (!token) {
    errorText.value = '管理员登录已失效，请重新登录'
    return
  }
  if (!absolutePath.value && !importFile.value) {
    errorText.value = '请先选择 JSON 文件或填写真实路径'
    return
  }

  importing.value = true
  importProgress.value = 5
  importStageText.value = '准备导入任务...'
  errorText.value = ''
  importResult.value = null
  previewResult.value = null
  try {
    const fd = new FormData()
    fd.append('import_type', importType.value)
    const usePathMode = !!absolutePath.value
    if (usePathMode) {
      fd.append('file_path', absolutePath.value)
      importProgress.value = 20
      importStageText.value = '服务器按绝对路径读取文件...'
    } else if (importFile.value) {
      fd.append('file', importFile.value)
      importProgress.value = 10
      importStageText.value = '上传文件到服务器...'
    }

    const res = await API.post('/admin/import-json/', fd, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (evt) => {
        if (!importing.value || usePathMode) return
        const total = evt.total || 0
        if (total <= 0) return
        const ratio = Math.min(1, evt.loaded / total)
        const p = Math.round(10 + ratio * 55)
        importProgress.value = Math.max(importProgress.value, p)
        importStageText.value = '上传中...'
      },
    })
    importProgress.value = Math.max(importProgress.value, 85)
    importStageText.value = '服务器处理中...'
    importResult.value = res.data
    if (res?.data?.file_path) {
      absolutePath.value = res.data.file_path
    }
    importProgress.value = 100
    importStageText.value = '导入完成'
    await loadImportTasks()
    await scanDataQuality()
    await loadOverview()
  } catch (e) {
    errorText.value = e?.response?.data?.error || '导入失败'
    importStageText.value = '导入失败'
  } finally {
    importing.value = false
    if (importProgress.value >= 100) {
      setTimeout(() => {
        importProgress.value = 0
        importStageText.value = ''
      }, 1200)
    }
  }
}

const formatPreviewValue = (v) => {
  if (typeof v === 'object') return JSON.stringify(v)
  return v
}

const previewImport = async () => {
  const token = localStorage.getItem('admin_token') || ''
  if (!token) {
    errorText.value = '管理员登录已失效，请重新登录'
    return
  }
  if (!absolutePath.value && !importFile.value) {
    errorText.value = '请先选择 JSON 文件或填写真实路径'
    return
  }
  try {
    errorText.value = ''
    const fd = new FormData()
    fd.append('import_type', importType.value)
    if (absolutePath.value) fd.append('file_path', absolutePath.value)
    if (importFile.value) fd.append('file', importFile.value)
    const res = await API.post('/admin/import-preview/', fd, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      }
    })
    previewResult.value = res.data
  } catch (e) {
    errorText.value = e?.response?.data?.error || '导入预览失败'
  }
}

const loadImportTasks = async () => {
  const token = localStorage.getItem('admin_token') || ''
  if (!token) return
  try {
    const res = await API.get('/admin/import-tasks/?limit=20', {
      headers: { Authorization: `Bearer ${token}` }
    })
    importTasks.value = res.data?.tasks || []
  } catch {
    importTasks.value = []
  }
}

const rollbackLatestRelationImport = async () => {
  const token = localStorage.getItem('admin_token') || ''
  if (!token) return
  try {
    const res = await API.post('/admin/import-rollback/', {}, {
      headers: { Authorization: `Bearer ${token}` }
    })
    importResult.value = { import_type: 'rollback', stats: res.data }
    await loadImportTasks()
    await scanDataQuality()
  } catch (e) {
    errorText.value = e?.response?.data?.error || '回滚失败'
  }
}

const scanDataQuality = async () => {
  const token = localStorage.getItem('admin_token') || ''
  if (!token) return
  try {
    const res = await API.get('/admin/data-quality/', {
      headers: { Authorization: `Bearer ${token}` }
    })
    qualityChecks.value = res.data?.checks || null
    qualitySuggestions.value = res.data?.suggestions || []
  } catch {
    qualityChecks.value = null
    qualitySuggestions.value = []
  }
}

const fixDataQuality = async (action) => {
  const token = localStorage.getItem('admin_token') || ''
  if (!token) return
  try {
    const res = await API.post('/admin/data-quality/fix/', { action }, {
      headers: { Authorization: `Bearer ${token}` }
    })
    importResult.value = { import_type: `fix:${action}`, stats: res.data }
    await scanDataQuality()
  } catch (e) {
    errorText.value = e?.response?.data?.error || '修复失败'
  }
}

const loadUserAudit = async () => {
  const token = localStorage.getItem('admin_token') || ''
  if (!token) return
  try {
    const params = new URLSearchParams()
    if (auditStartDate.value) params.set('start_date', auditStartDate.value)
    if (auditEndDate.value) params.set('end_date', auditEndDate.value)
    const res = await API.get(`/admin/user-audit/?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    auditData.value = res.data || null
  } catch {
    auditData.value = null
  }
}

const loadOverview = async () => {
  const token = localStorage.getItem('admin_token') || ''
  if (!token) {
    errorText.value = '管理员登录已失效，请重新登录'
    return
  }

  loading.value = true
  errorText.value = ''
  try {
    const res = await API.get('/admin/overview/', {
      headers: { Authorization: `Bearer ${token}` }
    })
    const data = res.data || {}
    stats.value = data.stats || null
    users.value = Array.isArray(data.users) ? data.users : []
    if (users.value.length > 0) {
      activeUserId.value = users.value[0].user_id
    }
  } catch (e) {
    errorText.value = e?.response?.data?.error || '加载管理员数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const today = new Date()
  const prev = new Date(today.getTime() - 29 * 24 * 3600 * 1000)
  auditEndDate.value = today.toISOString().slice(0, 10)
  auditStartDate.value = prev.toISOString().slice(0, 10)
  loadOverview()
  loadImportTasks()
  scanDataQuality()
  loadUserAudit()
})
</script>

<style scoped>
.admin-view { width: 100%; display: flex; flex-direction: column; gap: 14px; }
.admin-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.admin-head h2 { margin: 0 0 6px; font-size: 28px; color: #263238; }
.admin-head p { margin: 0; color: #60707d; }

.ui-btn {
  border: none;
  border-radius: 12px;
  padding: 10px 16px;
  font-weight: 700;
  cursor: pointer;
  font-size: 14px;
}

.ui-btn.primary {
  background: #1f7a6a;
  color: #fff;
}

.ui-btn.accent {
  background: #2b8f77;
  color: #fff;
}

.ui-btn.ghost {
  background: #fff;
  color: #1f5468;
  border: 1px solid #c9dbe6;
}

.ui-btn.ghost.danger {
  color: #8b2e2e;
  border-color: #e5c2c2;
  min-width: 124px;
  white-space: nowrap;
}

.ui-btn:disabled { opacity: .65; cursor: not-allowed; }

.stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.stat-card {
  border: 1px solid #dbe7ef; border-radius: 12px; background: #fff; padding: 12px 14px;
}
.stat-card .k { color: #60707d; font-size: 13px; margin-bottom: 4px; }
.stat-card .v { color: #13202a; font-size: 26px; font-weight: 800; }

.card { border: 1px solid #dbe7ef; border-radius: 12px; background: #fff; padding: 14px; }
.card h3 { margin: 0 0 10px; color: #2d3436; }
.card h4 { margin: 8px 0; color: #3e5563; }

.import-card { border-color: #cce4df; background: linear-gradient(180deg, #ffffff 0%, #f7fcfb 100%); }
.import-desc { margin: 0 0 6px; color: #40535d; }
.import-tip { margin: 0 0 12px; color: #6b7f8d; font-size: 13px; }
.import-form-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.import-form-row.full-width {
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}
.import-label { color: #40535d; font-weight: 700; font-size: 15px; }
.import-select, .path-input {
  border: 1px solid #cfe0eb;
  border-radius: 14px;
  padding: 12px 14px;
  font-size: 16px;
  background: #fff;
  width: 100%;
}

.file-picker-wrap {
  width: 100%;
  border: 1px solid #cfe0eb;
  border-radius: 14px;
  background: #fff;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.import-file-hidden {
  display: none;
}

.import-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  width: 100%;
}

.import-actions .ui-btn.accent {
  flex: 1;
  padding: 13px 16px;
  border-radius: 14px;
  font-size: 17px;
}

.file-name {
  color: #60707d;
  font-size: 15px;
  font-weight: 600;
}

.progress-wrap {
  width: 100%;
  margin-top: 10px;
  border: 1px solid #d7e5ee;
  border-radius: 12px;
  background: #f8fcff;
  padding: 10px 12px;
}

.progress-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  color: #375164;
  font-size: 13px;
  font-weight: 600;
}

.progress-track {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: #e6eff5;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2c8b74 0%, #1f6e93 100%);
  transition: width .2s ease;
}

.path-box {
  margin-top: 10px;
  border: 1px solid #dde8ef;
  border-radius: 14px;
  background: #f8fbfd;
  padding: 12px 14px;
  width: 100%;
}

.path-label { font-size: 12px; color: #6a7d8a; margin-bottom: 4px; }
.path-value {
  color: #243845;
  font-size: 13px;
  word-break: break-all;
}
.import-result {
  margin-top: 12px;
  border: 1px solid #dceaf3;
  background: #f8fcff;
  border-radius: 14px;
  padding: 12px 14px;
  width: 100%;
}
.import-result ul { margin: 0; padding-left: 18px; }
.import-result li { margin-bottom: 4px; color: #1f2e38; }

.diff-box {
  margin-top: 10px;
  border: 1px dashed #bfd5e2;
  border-radius: 10px;
  background: #f9fcff;
  padding: 8px 10px;
}

.quality-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.q-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.task-empty { color: #8ba0ae; }

.task-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.task-table th, .task-table td {
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  padding: 8px 6px;
}

.qc-list { margin: 0; padding-left: 18px; }
.qc-list li { margin-bottom: 4px; color: #1f2e38; }

.audit-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.audit-date {
  border: 1px solid #d2e0ea;
  border-radius: 10px;
  padding: 8px 10px;
}

.audit-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}

.u-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.u-table th, .u-table td {
  border-bottom: 1px solid #edf2f7;
  text-align: left;
  padding: 10px 8px;
}
.u-table tbody tr { cursor: pointer; }
.u-table tbody tr:hover { background: #f7fbff; }
.u-table tbody tr.active { background: #eaf6ff; }

.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.pref-group { margin-bottom: 10px; }
.pk { font-size: 13px; color: #688192; margin-bottom: 4px; }
.pv { font-size: 14px; color: #1f2e38; line-height: 1.5; }

.history-block { margin-bottom: 10px; }
.history-list { margin: 0; padding-left: 18px; }
.history-list li { margin-bottom: 6px; color: #1f2e38; font-size: 14px; }

.error-box {
  background: #fff1f0; color: #b63b30; border: 1px solid #f2b8b5;
  border-radius: 10px; padding: 10px 12px;
}
.empty { color: #8ca1af; }

@media (max-width: 1080px) {
  .stats-grid { grid-template-columns: 1fr; }
  .detail-grid { grid-template-columns: 1fr; }
}
</style>

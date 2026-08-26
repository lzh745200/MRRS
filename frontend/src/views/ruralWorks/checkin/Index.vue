<template>
  <div class="checkin-workbench">
    <div class="page-header">
      <h2>驻村工作台</h2>
      <div class="header-actions">
        <el-button :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <!-- 今日打卡 -->
      <el-col :span="10">
        <el-card>
          <template #header><span>今日驻村打卡</span></template>
          <el-alert
            v-if="checkedToday"
            type="success"
            show-icon
            :closable="false"
            :title="`今日已打卡（${checkinLocation || '未记录位置'}）`"
            class="mb"
          />
          <el-form label-width="90px">
            <el-form-item label="打卡地点">
              <el-input v-model="location" placeholder="如：甲村村委会 / 村口广场" />
            </el-form-item>
            <el-form-item label="工作内容">
              <el-input
                v-model="content"
                type="textarea"
                :rows="3"
                placeholder="今日主要工作（可选）"
              />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                :disabled="checkedToday"
                :loading="checking"
                @click="doCheckin"
              >
                {{ checkedToday ? '今日已完成打卡' : '驻村打卡' }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 月度总结 -->
      <el-col :span="14">
        <el-card>
          <template #header>
            <span>月度工作总结</span>
            <div class="header-right">
              <el-date-picker
                v-model="summaryMonth"
                type="month"
                value-format="YYYY-MM"
                size="small"
                @change="loadSummary"
              />
            </div>
          </template>
          <div v-if="summary" class="summary-body">
            <el-descriptions :column="3" border size="small" class="mb">
              <el-descriptions-item label="工作项数">{{ summary.total_logs }}</el-descriptions-item>
              <el-descriptions-item label="打卡天数">{{
                summary.checkin_days
              }}</el-descriptions-item>
              <el-descriptions-item label="分类">
                <span v-for="(v, k) in summary.category_counts" :key="k" class="cat-tag">
                  {{ k }}:{{ v }}
                </span>
              </el-descriptions-item>
            </el-descriptions>
            <div class="summary-text">{{ summary.summary_text }}</div>
            <div v-if="summary.items.length" class="summary-list">
              <div v-for="(it, i) in summary.items" :key="i" class="sum-item">
                <span class="sum-date">{{ it.work_date }}</span>
                <span class="sum-content">{{ it.content }}</span>
                <el-tag size="small" type="info">{{ it.category }}</el-tag>
              </div>
            </div>
          </div>
          <EmptyState v-else text="暂无月度数据" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { get, post } from '@/api/request'

const loading = ref(false)
const checking = ref(false)
const location = ref('')
const content = ref('')
const checkedToday = ref(false)
const checkinLocation = ref('')
const summaryMonth = ref('')
const summary = ref<any>(null)

const todayStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
})

async function checkToday() {
  try {
    const res = await get('/work-logs', { page: 1, page_size: 50 })
    const items = res?.items ?? []
    const today = items.find(
      (it: any) =>
        it.log_date === todayStr.value && (it.category === 'checkin' || it.log_type === 'checkin')
    )
    checkedToday.value = !!today
    checkinLocation.value = today?.location ?? ''
  } catch {
    checkedToday.value = false
  }
}

async function doCheckin() {
  if (!location.value.trim()) {
    ElMessage.warning('请填写打卡地点')
    return
  }
  checking.value = true
  try {
    await post('/work-logs', {
      log_date: todayStr.value,
      content: content.value.trim() || '驻村打卡',
      category: 'checkin',
      location: location.value.trim(),
    })
    ElMessage.success('打卡成功')
    checkedToday.value = true
    checkinLocation.value = location.value.trim()
    location.value = ''
    content.value = ''
    await loadSummary()
  } catch (e: any) {
    // axios 将后端 HTTPException.detail 放在 e.response.data.detail
    const detail = e?.response?.data?.detail || e?.detail
    if (detail === '今天已完成驻村打卡') {
      ElMessage.info('今天已完成驻村打卡')
      checkedToday.value = true
    } else {
      ElMessage.error(detail || '打卡失败')
    }
  } finally {
    checking.value = false
  }
}

async function loadSummary() {
  if (!summaryMonth.value) return
  const [y, m] = summaryMonth.value.split('-')
  try {
    const res = await get(`/work-logs/monthly-summary?year=${y}&month=${Number(m)}`)
    summary.value = res ?? null
  } catch {
    ElMessage.error('加载月度总结失败')
  }
}

async function loadAll() {
  loading.value = true
  try {
    await checkToday()
    await loadSummary()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const now = new Date()
  summaryMonth.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  loadAll()
})
</script>

<style scoped>
.checkin-workbench {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.page-header h2 {
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.header-right {
  float: right;
}
.mb {
  margin-bottom: 12px;
}
.summary-body {
  min-height: 200px;
}
.summary-text {
  background: var(--el-fill-color-light);
  border-radius: 6px;
  padding: 10px 12px;
  margin: 10px 0;
  font-size: 14px;
  line-height: 1.7;
}
.cat-tag {
  margin-right: 8px;
  font-size: 12px;
}
.summary-list {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sum-item {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  padding: 6px 8px;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}
.sum-date {
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}
.sum-content {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

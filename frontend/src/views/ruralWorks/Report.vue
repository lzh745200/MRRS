<template>
  <div class="rural-report-page">
    <el-card class="filter-card">
      <el-form :model="filterForm" inline>
        <el-form-item label="年份">
          <el-select v-model="filterForm.year" placeholder="选择年份" @change="loadReport">
            <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="daterange"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="loadReport">生成报告</el-button>
          <el-button :disabled="!reportData" @click="exportCSV">导出 CSV</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-if="loading" class="loading-box">
      <el-icon class="is-loading" :size="32" />
      <p>正在生成报告...</p>
    </div>

    <template v-if="reportData">
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-val">{{ reportData.summary?.total || 0 }}</div>
          <div class="stat-label">工作总数</div>
        </div>
        <div class="stat-card success">
          <div class="stat-val">{{ reportData.summary?.completed || 0 }}</div>
          <div class="stat-label">已完成</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-val">{{ reportData.summary?.inProgress || 0 }}</div>
          <div class="stat-label">进行中</div>
        </div>
        <div class="stat-card danger">
          <div class="stat-val">{{ reportData.summary?.delayed || 0 }}</div>
          <div class="stat-label">已延迟</div>
        </div>
      </div>

      <el-card class="table-card">
        <template #header><span>工作明细</span></template>
        <el-table :data="items" stripe border max-height="500">
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="title" label="工作标题" min-width="180" show-overflow-tooltip />
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="village_name" label="帮扶村" width="120" />
          <el-table-column prop="start_date" label="开始日期" width="110" />
          <el-table-column prop="end_date" label="结束日期" width="110" />
        </el-table>
      </el-card>
    </template>

    <el-empty v-if="!loading && !reportData" description='选择年份后点击"生成报告"' />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { get } from '@/api/request'

const currentYear = new Date().getFullYear()
const yearOptions = Array.from({ length: 10 }, (_, i) => currentYear - i)
const filterForm = ref({
  year: currentYear,
  dateRange: null as string[] | null,
})
const loading = ref(false)
const reportData = ref<any>(null)
const items = ref<any[]>([])

onMounted(() => loadReport())

async function loadReport() {
  loading.value = true
  try {
    const params: any = { year: filterForm.value.year }
    const dr = filterForm.value.dateRange
    if (dr?.length === 2) {
      params.start_date = dr[0]
      params.end_date = dr[1]
    }
    const res: any = await get('/rural-works/report/generate', params)
    reportData.value = res?.data || res
    items.value = reportData.value?.items || reportData.value?.works || []
    // 统计卡兼容后端两种结构：summary 对象（新）或 by_status 映射（旧）
    const d = reportData.value || {}
    const bs = d.by_status || {}
    const summary = d.summary || {}
    d.summary = {
      total: summary.total ?? d.total ?? 0,
      completed: summary.completed ?? bs.completed ?? 0,
      inProgress: summary.inProgress ?? bs.in_progress ?? 0,
      delayed: summary.delayed ?? bs.delayed ?? 0,
    }
    if (!items.value.length) {
      ElMessage.info('暂无符合条件的报告数据')
    }
  } catch (e: any) {
    const msg =
      e?.response?.data?.detail || e?.response?.data?.message || e?.message || '报告生成失败'
    ElMessage.error(typeof msg === 'string' ? msg : '报告生成失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function statusType(s: string): 'success' | 'warning' | 'danger' | 'info' {
  const m: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    completed: 'success',
    in_progress: 'warning',
    delayed: 'danger',
  }
  return m[s] || 'info'
}

function exportCSV() {
  if (!items.value.length) return
  const h = '序号,工作标题,类型,状态,帮扶村,开始日期,结束日期'
  const rows = items.value.map((r: any, i: number) =>
    [i + 1, r.title, r.type, r.status, r.village_name, r.start_date, r.end_date].join(',')
  )
  const blob = new Blob([h + '\n' + rows.join('\n')], { type: 'text/csv' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `乡村振兴工作报告_${filterForm.value.year}.csv`
  link.click()
}
</script>

<style scoped>
.rural-report-page {
  padding: 20px;
}
.filter-card {
  margin-bottom: 20px;
}
.loading-box {
  text-align: center;
  padding: 60px;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.stat-card.success {
  border-left: 4px solid var(--color-success);
}
.stat-card.warning {
  border-left: 4px solid var(--color-warning);
}
.stat-card.danger {
  border-left: 4px solid var(--color-danger);
}
.stat-val {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}
.table-card {
  background: #fff;
}
</style>

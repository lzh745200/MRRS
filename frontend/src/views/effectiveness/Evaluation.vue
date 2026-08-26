<template>
  <div class="evaluation-page">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">成效评估</h2>
        <p class="page-desc">评估帮扶村庄的综合成效并查看报告</p>
      </div>
    </div>

    <!-- 评估表单 -->
    <div class="form-card">
      <el-form :model="evalForm" inline>
        <el-form-item label="村庄">
          <el-select
            v-model="evalForm.villageId"
            placeholder="请选择村庄"
            style="width: 240px"
            filterable
            @change="handleFormChange"
          >
            <el-option v-for="v in villageOptions" :key="v.id" :label="v.name" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="评估年度">
          <el-select v-model="evalForm.year" style="width: 140px" @change="handleFormChange">
            <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isAdmin">
          <el-button type="primary" :loading="evaluating" @click="handleEvaluate">
            <el-icon><DataAnalysis /></el-icon>开始评估
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 加载/结果 -->
    <div v-if="evaluating || reportLoading" class="state-container">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>{{ evaluating ? '正在评估中...' : '报告加载中...' }}</p>
    </div>

    <template v-if="evaluationResult">
      <!-- 评估报告 -->
      <div class="result-card">
        <div class="card-header">
          <h3>评估报告</h3>
          <div class="header-tags">
            <el-tag>{{ currentVillageName }}</el-tag>
            <el-tag>{{ evalForm.year }}年度</el-tag>
          </div>
        </div>
        <div class="card-body">
          <el-descriptions :column="3" border>
            <el-descriptions-item v-for="item in reportItems" :key="item.label" :label="item.label">
              {{ item.value }}
            </el-descriptions-item>
          </el-descriptions>
          <template v-if="indicatorItems.length">
            <h4 class="section-title">评估指标明细</h4>
            <el-descriptions :column="3" border>
              <el-descriptions-item
                v-for="item in indicatorItems"
                :key="item.label"
                :label="item.label"
              >
                {{ item.value }}
              </el-descriptions-item>
            </el-descriptions>
          </template>
        </div>
      </div>

      <!-- 对比评估 -->
      <div class="result-card">
        <div class="card-header">
          <h3>年度对比</h3>
          <el-form :model="compareForm" inline>
            <el-form-item label="对比年度">
              <el-select v-model="compareForm.year1" style="width: 120px">
                <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
              </el-select>
            </el-form-item>
            <el-form-item label="对比年度">
              <el-select v-model="compareForm.year2" style="width: 120px">
                <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" plain :loading="comparing" @click="handleCompare">
                对比
              </el-button>
            </el-form-item>
          </el-form>
        </div>
        <div v-if="compareItems.length" class="card-body">
          <el-descriptions :column="3" border>
            <el-descriptions-item
              v-for="item in compareItems"
              :key="item.label"
              :label="item.label"
            >
              {{ item.value }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else class="empty-hint">
          <p>选择两个不同年度进行对比分析</p>
        </div>
      </div>
    </template>

    <!-- 未评估 -->
    <div v-if="!evaluationResult && !evaluating && !reportLoading" class="state-container">
      <el-empty :description="emptyHint">
        <template #image>
          <el-icon :size="60" class="empty-icon"><DataAnalysis /></el-icon>
        </template>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading, DataAnalysis } from '@element-plus/icons-vue'
import { evaluateVillage, compareEvaluations, getEvaluationReport } from '@/api/effectiveness'
import { apiRequest } from '@/api/request'
import { useUserStore } from '@/stores/user'
import { getYearOptions } from '@/utils/yearOptions'

const route = useRoute()
const userStore = useUserStore()
// 仅管理员可发起评估（后端 /effectiveness/evaluate 限 super_admin/admin）
const isAdmin = computed(
  () =>
    ['admin', 'super_admin'].includes(userStore.currentUser?.role || '') ||
    !!userStore.currentUser?.is_superuser
)

const currentYear = new Date().getFullYear()
// 年份范围：当前年-4 ~ 当前年+10（滚动窗口，见 utils/yearOptions）
const yearOptions = getYearOptions({ start: currentYear - 4 })

const evalForm = reactive({
  villageId: 0,
  year: currentYear,
})

const compareForm = reactive({
  year1: currentYear - 1,
  year2: currentYear,
})

const villageOptions = ref<{ id: number; name: string }[]>([])
const evaluating = ref(false)
const comparing = ref(false)
const reportLoading = ref(false)
const evaluationResult = ref<any>(null)
const compareResult = ref<any>(null)

const currentVillageName = computed(
  () => villageOptions.value.find((v) => v.id === evalForm.villageId)?.name || ''
)

const emptyHint = computed(() =>
  isAdmin.value ? '选择村庄和年度后点击"开始评估"' : '选择村庄和年度查看评估报告'
)

function fmtScore(v: any): string {
  return v == null ? '-' : Number(v).toFixed(1)
}

function fmtDateTime(v: any): string {
  if (!v) return '-'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString('zh-CN', { hour12: false })
}

function gradeLabel(grade: any): string {
  const map: Record<string, string> = {
    excellent: '优秀',
    good: '良好',
    average: '一般',
    poor: '较差',
  }
  return map[grade] || grade || '-'
}

// 按后端 /effectiveness 真实响应结构渲染（_eval_to_dict 契约）
const reportItems = computed(() => {
  const r = evaluationResult.value
  if (!r) return []
  return [
    { label: '评估年度', value: r.year != null ? `${r.year} 年` : '-' },
    { label: '总分', value: fmtScore(r.total_score) },
    { label: '等级', value: gradeLabel(r.grade) },
    { label: '排名', value: r.rank != null ? `第 ${r.rank} 名` : '-' },
    { label: '经济得分', value: fmtScore(r.economic_score) },
    { label: '社会得分', value: fmtScore(r.social_score) },
    { label: '生态得分', value: fmtScore(r.ecological_score) },
    { label: '评估时间', value: fmtDateTime(r.evaluated_at) },
  ]
})

const indicatorItems = computed(() => {
  const ind = evaluationResult.value?.indicators
  if (!ind || typeof ind !== 'object') return []
  return [
    { label: '人均收入（元）', value: ind.per_capita_income ?? '-' },
    {
      label: '收入增长率',
      value: ind.income_growth_rate != null ? `${ind.income_growth_rate}%` : '-',
    },
    { label: '基础设施项目数', value: ind.infrastructure_count ?? '-' },
    { label: '产业项目数', value: ind.industry_count ?? '-' },
    { label: '年度数据', value: ind.data_complete ? '已录入' : '未录入（按基线评估）' },
  ]
})

// 年度对比：后端返回 {year1_data, year2_data, delta} 三层嵌套，仅渲染 delta 与两年总分
const compareItems = computed(() => {
  const c = compareResult.value
  if (!c?.delta) return []
  const d = c.delta
  const sign = (v: any) => (v == null ? '-' : v > 0 ? `+${v}` : `${v}`)
  return [
    { label: `${c.year1} 年总分`, value: fmtScore(c.year1_data?.total_score) },
    { label: `${c.year2} 年总分`, value: fmtScore(c.year2_data?.total_score) },
    { label: '总分变化', value: sign(d.total_score) },
    { label: '经济得分变化', value: sign(d.economic_score) },
    { label: '社会得分变化', value: sign(d.social_score) },
    { label: '生态得分变化', value: sign(d.ecological_score) },
  ]
})

// 切换村庄/年度后旧结果一律清空，避免误读
function handleFormChange() {
  evaluationResult.value = null
  compareResult.value = null
}

async function loadVillages() {
  try {
    const response = await apiRequest({
      method: 'GET',
      url: '/supported-villages',
      params: { page_size: 200 },
    })
    const data = response?.data ?? response
    const inner = data
    const items = inner?.items || (Array.isArray(inner) ? inner : [])
    villageOptions.value = items.map((v: any) => ({
      id: v.id,
      name: v.name || v.village_name || `ID:${v.id}`,
    }))
  } catch (e: any) {
    villageOptions.value = []
    ElMessage.error(e?.userMessage || '村庄列表加载失败，请刷新重试')
  }
}

// 查看已有报告（只读）；404 表示该年度尚未评估
async function loadExistingReport() {
  reportLoading.value = true
  evaluationResult.value = null
  compareResult.value = null
  try {
    const response = await getEvaluationReport(evalForm.villageId, evalForm.year)
    evaluationResult.value = response?.data ?? response
  } catch (e: any) {
    if (e?.response?.status === 404) {
      ElMessage.info(
        isAdmin.value ? '该年度尚未评估，可点击"开始评估"' : '该年度尚未评估，请联系管理员评估'
      )
    } else {
      ElMessage.error(e?.userMessage || '评估报告加载失败')
    }
  } finally {
    reportLoading.value = false
  }
}

async function handleEvaluate() {
  if (!evalForm.villageId) {
    ElMessage.warning('请选择村庄')
    return
  }
  evaluating.value = true
  evaluationResult.value = null
  compareResult.value = null
  try {
    const response = await evaluateVillage({
      village_id: evalForm.villageId,
      year: evalForm.year,
    })
    evaluationResult.value = response?.data ?? response
    ElMessage.success('评估完成')
  } catch (e: any) {
    ElMessage.error(e?.userMessage || e?.response?.data?.detail || '评估失败')
  } finally {
    evaluating.value = false
  }
}

async function handleCompare() {
  if (!evalForm.villageId) {
    ElMessage.warning('请先选择村庄')
    return
  }
  if (compareForm.year1 === compareForm.year2) {
    ElMessage.warning('请选择不同的年度进行对比')
    return
  }
  comparing.value = true
  compareResult.value = null
  try {
    const response = await compareEvaluations(
      evalForm.villageId,
      compareForm.year1,
      compareForm.year2
    )
    compareResult.value = response?.data ?? response
  } catch (e: any) {
    ElMessage.error(e?.userMessage || e?.response?.data?.detail || '对比失败')
  } finally {
    comparing.value = false
  }
}

onMounted(() => {
  loadVillages()
  // 从URL参数初始化（排名页"评估/查看"入口）：先尝试加载已有报告，不直接触发写操作
  const villageId = route.query.villageId
  const year = route.query.year
  if (villageId) evalForm.villageId = Number(villageId)
  if (year) evalForm.year = Number(year)
  if (villageId) loadExistingReport()
})
</script>

<style lang="scss" scoped>
.evaluation-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.form-card {
  background: var(--color-bg-card, var(----color-bg-card));
  border-radius: 8px;
  padding: 16px 20px 4px;
  margin-bottom: 20px;
  border: 1px solid var(--color-border);
}

.state-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: var(--color-text-secondary);
}

.result-card {
  background: var(--color-bg-card, var(----color-bg-card));
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: linear-gradient(135deg, var(--color-primary-dark), var(--color-primary));
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-inverse);
}

.header-tags {
  display: flex;
  gap: 8px;
}

.section-title {
  margin: 20px 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.card-body {
  padding: 24px;
}

.empty-hint {
  padding: 40px;
  text-align: center;
  color: var(--color-info);
}

.empty-icon {
  color: var(--color-text-secondary);
}
</style>

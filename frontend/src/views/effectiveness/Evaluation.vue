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
          >
            <el-option v-for="v in villageOptions" :key="v.id" :label="v.name" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="评估年度">
          <el-select v-model="evalForm.year" style="width: 140px">
            <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="evaluating" @click="handleEvaluate">
            <el-icon><DataAnalysis /></el-icon>开始评估
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 加载/结果 -->
    <div v-if="evaluating" class="state-container">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>正在评估中...</p>
    </div>

    <template v-if="evaluationResult">
      <!-- 评估报告 -->
      <div class="result-card">
        <div class="card-header">
          <h3>评估报告</h3>
          <el-tag>{{ evalForm.year }}年度</el-tag>
        </div>
        <div class="card-body">
          <el-descriptions :column="3" border>
            <el-descriptions-item
              v-for="(value, key) in flatResult"
              :key="key"
              :label="fieldLabel(String(key))"
            >
              {{ formatValue(String(key), value) }}
            </el-descriptions-item>
          </el-descriptions>
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
        <div v-if="compareResult" class="card-body">
          <el-descriptions :column="3" border>
            <el-descriptions-item
              v-for="(value, key) in flatCompareResult"
              :key="key"
              :label="fieldLabel(String(key))"
            >
              {{ formatValue(String(key), value) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
        <div v-else class="empty-hint">
          <p>选择两个不同年度进行对比分析</p>
        </div>
      </div>
    </template>

    <!-- 未评估 -->
    <div v-if="!evaluationResult && !evaluating" class="state-container">
      <el-empty description='选择村庄和年度后点击"开始评估"'>
        <template #image>
          <el-icon :size="60" color="#ccc"><DataAnalysis /></el-icon>
        </template>
      </el-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { logger } from '@/utils/logger'
import { Loading, DataAnalysis } from '@element-plus/icons-vue'
import { evaluateVillage, compareEvaluations } from '@/api/effectiveness'
import { apiRequest } from '@/api/request'

const route = useRoute()

const currentYear = new Date().getFullYear()
const yearOptions = Array.from({ length: 5 }, (_, i) => currentYear - i)

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
const evaluationResult = ref<any>(null)
const compareResult = ref<any>(null)

const flatResult = computed(() => {
  if (!evaluationResult.value) return {}
  const r = evaluationResult.value
  if (r?.result) return r.result
  const exclude = ['village_id', 'village_name']
  return Object.fromEntries(Object.entries(r).filter(([k]) => !exclude.includes(k)))
})

const flatCompareResult = computed(() => {
  if (!compareResult.value) return {}
  return compareResult.value
})

function fieldLabel(key: string): string {
  const map: Record<string, string> = {
    total_score: '总分',
    economic: '经济得分',
    social: '社会得分',
    project_completion: '项目完成率',
    fund_execution: '资金执行率',
    level: '等级',
    rank: '排名',
    per_capita_income: '人均收入',
    collective_income: '集体收入',
    total_projects: '项目总数',
    completed_projects: '已完成项目',
    project_completion_rate: '项目完成率',
    total_funds: '资金总额',
    growth_rate: '增长率',
    score: '得分',
  }
  return map[key] || key.replace(/_/g, ' ')
}

function formatValue(key: string, value: any): string {
  if (value == null) return '-'
  if (typeof value === 'number') {
    if (key.includes('rate') || key.includes('percent')) {
      return (value * 100).toFixed(1) + '%'
    }
    if (key.includes('income') || key.includes('funds') || key.includes('amount')) {
      return value.toLocaleString()
    }
    return Number(value).toFixed(1)
  }
  return String(value)
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
    logger.warn('[Evaluation] 加载村庄列表失败', e)
    villageOptions.value = []
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
    const data = response?.data ?? response
    evaluationResult.value = data
    ElMessage.success('评估完成')
  } catch {
    ElMessage.error('评估失败')
  } finally {
    evaluating.value = false
  }
}

async function handleCompare() {
  if (!evalForm.villageId) {
    ElMessage.warning('请先完成评估')
    return
  }
  if (compareForm.year1 === compareForm.year2) {
    ElMessage.warning('请选择不同的年度进行对比')
    return
  }
  comparing.value = true
  try {
    const response = await compareEvaluations(
      evalForm.villageId,
      compareForm.year1,
      compareForm.year2
    )
    const data = response?.data ?? response
    compareResult.value = data
    ElMessage.success('对比完成')
  } catch {
    ElMessage.error('对比失败')
  } finally {
    comparing.value = false
  }
}

onMounted(() => {
  loadVillages()
  // 从URL参数初始化
  const villageId = route.query.villageId
  const year = route.query.year
  if (villageId) evalForm.villageId = Number(villageId)
  if (year) evalForm.year = Number(year)
  if (villageId) handleEvaluate()
})
</script>

<style scoped>
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
  color: #1b4332;
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: #666;
}

.form-card {
  background: white;
  border-radius: 8px;
  padding: 16px 20px 4px;
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
}

.state-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: #666;
}

.result-card {
  background: white;
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
  background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 100%);
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.card-body {
  padding: 24px;
}

.empty-hint {
  padding: 40px;
  text-align: center;
  color: var(--color-info);
}
</style>

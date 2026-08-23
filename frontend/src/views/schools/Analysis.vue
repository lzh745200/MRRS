<template>
  <div class="school-analysis">
    <el-row :gutter="16">
      <el-col :span="24">
        <el-card>
          <template #header><span>学校分析</span></template>
          <el-row :gutter="16">
            <el-col :span="4"><StatsCard title="学校总数" :value="stats.total_schools" /></el-col>
            <el-col :span="4"
              ><StatsCard title="帮扶中" :value="stats.active" type="warning"
            /></el-col>
            <el-col :span="4"
              ><StatsCard title="已完成" :value="stats.completed" type="success"
            /></el-col>
            <el-col :span="4"><StatsCard title="学生总数" :value="stats.total_students" /></el-col>
            <el-col :span="4"><StatsCard title="教师总数" :value="stats.total_teachers" /></el-col>
            <el-col :span="4"
              ><StatsCard title="助学项目" :value="stats.project_count" type="info"
            /></el-col>
          </el-row>
          <el-row :gutter="16" style="margin-top: 16px">
            <el-col :span="12"
              ><StatsCard title="项目预算(万元)" :value="budget" type="warning"
            /></el-col>
            <el-col :span="12"
              ><StatsCard title="助学金总额(元)" :value="scholarshipAmount" type="success"
            /></el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card>
          <template #header><span>帮扶状态分布</span></template>
          <BaseChart :option="statusOption" height="350" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header><span>地区分布</span></template>
          <BaseChart :option="regionOption" height="350" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import BaseChart from '@/components/common/BaseChart.vue'
import StatsCard from '@/components/common/StatsCard.vue'
import { schoolsApi } from '@/api/schools'
import { format } from '@/utils'

const stats = ref({
  total_schools: 0,
  active: 0,
  completed: 0,
  total_students: 0,
  total_teachers: 0,
  project_count: 0,
  project_total_budget: 0,
  scholarship_count: 0,
  scholarship_total_amount: 0,
})

const statusDist = ref<Record<string, number>>({})
const regionDist = ref<Record<string, number>>({})

const budget = computed(() => format.formatMoney4((stats.value.project_total_budget || 0) / 10000))
const scholarshipAmount = computed(() =>
  Number(stats.value.scholarship_total_amount || 0).toLocaleString('zh-CN')
)

const statusLabels: Record<string, string> = {
  active: '帮扶中',
  completed: '已完成',
  pending: '待帮扶',
}

const statusOption = computed(() => {
  const entries = Object.entries(statusDist.value).filter(([, v]) => v > 0)
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        data: entries.map(([key, value]) => ({
          name: statusLabels[key] || key,
          value,
        })),
      },
    ],
  }
})

const regionOption = computed(() => {
  const entries = Object.entries(regionDist.value)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 100, right: 20, top: 20, bottom: 60 },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: entries.map(([k]) => k), inverse: true },
    series: [{ type: 'bar', data: entries.map(([, v]) => v), barMaxWidth: 20 }],
  }
})

async function loadData() {
  try {
    const res: any = await schoolsApi.getStatistics()
    const data = res?.data ?? res ?? {}
    stats.value = { ...stats.value, ...data }

    // 聚合状态/地区分布(取全量列表)
    const listRes: any = await schoolsApi.list({ page: 1, page_size: 1000, all: true })
    const rows: any[] = listRes?.data?.items ?? listRes?.data ?? listRes?.items ?? []
    const statusCount: Record<string, number> = {}
    const regionCount: Record<string, number> = {}
    for (const row of rows) {
      const s = row.support_status || row.status || 'pending'
      statusCount[s] = (statusCount[s] || 0) + 1
      const region = row.district || row.county || row.region || '未知'
      regionCount[region] = (regionCount[region] || 0) + 1
    }
    statusDist.value = statusCount
    regionDist.value = regionCount
  } catch (err) {
    ElMessage.error('加载学校分析数据失败')
    console.error('[SchoolAnalysis] loadData error', err)
  }
}

onMounted(loadData)
</script>

<style scoped lang="scss">
.school-analysis {
  padding: 16px;
}
</style>

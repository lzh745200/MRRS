<template>
  <div class="assessment-page">
    <div class="page-header">
      <h2>成效评估</h2>
      <p class="page-desc">乡村振兴帮扶工作成效综合评估</p>
    </div>

    <!-- 无数据时显示空状态 -->
    <el-empty
      v-if="!loading && !error && scores.length === 0"
      description="暂无评估数据，请先录入帮扶村年度收入数据"
      :image-size="160"
    />

    <!-- 错误状态 -->
    <el-alert
      v-else-if="error"
      :title="error"
      type="error"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <template v-else>
      <!-- 统计卡片 -->
      <el-row :gutter="16">
        <el-col v-for="c in cards" :key="c.label" :span="6">
          <el-card shadow="hover" class="stat-card">
            <el-statistic :title="c.label" :value="c.value" :suffix="c.suffix" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 图表行 -->
      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="12">
          <el-card>
            <template #header>各村总分概览</template>
            <BaseChart :option="barOpt" height="350" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>评分等级分布</template>
            <BaseChart :option="pieOpt" height="350" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 明细表 -->
      <el-card style="margin-top: 16px">
        <template #header>评估指标明细</template>
        <el-table v-loading="loading" :data="scores" border stripe>
          <el-table-column prop="rank" label="排名" width="70" />
          <el-table-column prop="village_name" label="帮扶村" min-width="140" />
          <el-table-column prop="support_unit" label="帮扶单位" min-width="140" />
          <el-table-column label="经济效益" width="90">
            <template #default="{ row }">{{ row.scores.economic }}</template>
          </el-table-column>
          <el-table-column label="社会效益" width="90">
            <template #default="{ row }">{{ row.scores.social }}</template>
          </el-table-column>
          <el-table-column label="项目完成" width="90">
            <template #default="{ row }">{{ row.scores.project_completion }}</template>
          </el-table-column>
          <el-table-column label="经费执行" width="90">
            <template #default="{ row }">{{ row.scores.fund_execution }}</template>
          </el-table-column>
          <el-table-column prop="total_score" label="总分" width="80" sortable />
          <el-table-column label="等级" width="90">
            <template #default="{ row }">
              <el-tag :type="levelTag(row.level)">{{ row.level }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseChart from '@/components/common/BaseChart.vue'
import { get } from '@/api/request'

interface VillageScoreItem {
  village_id: number
  village_name: string
  support_unit: string
  scores: {
    economic: number
    social: number
    project_completion: number
    fund_execution: number
  }
  total_score: number
  level: string
  rank: number
}

const loading = ref(true)
const error = ref('')
const scores = ref<VillageScoreItem[]>([])

// 统计卡片
const cards = computed(() => {
  const total = scores.value.length
  const excellent = scores.value.filter((s) => s.level === '优秀').length
  const avgScore = total
    ? Math.round(scores.value.reduce((sum, s) => sum + s.total_score, 0) / total)
    : 0
  const needsImprove = scores.value.filter((s) => s.total_score < 60).length
  return [
    { label: '评估村数', value: total, suffix: '个' },
    { label: '优秀等级', value: excellent, suffix: '个' },
    { label: '平均总分', value: avgScore, suffix: '分' },
    { label: '待改进', value: needsImprove, suffix: '个' },
  ]
})

// 各村总分柱状图
const barOpt = computed(() => ({
  tooltip: { trigger: 'axis' as const },
  xAxis: {
    type: 'category' as const,
    data: scores.value.map((s) => s.village_name),
    axisLabel: { rotate: 30 },
  },
  yAxis: { type: 'value' as const, max: 100 },
  series: [
    {
      type: 'bar',
      data: scores.value.map((s) => s.total_score),
      itemStyle: { color: '#4a7c59' },
    },
  ],
  grid: { bottom: 60 },
}))

// 等级分布饼图
const pieOpt = computed(() => {
  const levelCount: Record<string, number> = {}
  scores.value.forEach((s) => {
    levelCount[s.level] = (levelCount[s.level] || 0) + 1
  })
  const colorMap: Record<string, string> = {
    优秀: '#4a7c59',
    良好: '#6a9c7a',
    合格: '#d4af37',
    待改进: '#c45656',
  }
  return {
    tooltip: { trigger: 'item' as const },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        data: Object.entries(levelCount).map(([name, value]) => ({
          name,
          value,
          itemStyle: { color: colorMap[name] || '#999' },
        })),
      },
    ],
  }
})

function levelTag(
  level: string
): 'success' | 'warning' | 'danger' | 'info' | 'primary' | undefined {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary' | undefined> = {
    优秀: 'success',
    良好: 'primary',
    合格: 'warning',
    待改进: 'danger',
  }
  return map[level] || 'info'
}

onMounted(async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await get<{
      code: number
      data: {
        items: VillageScoreItem[]
        total: number
        year: number
        weights: Record<string, number>
      }
    }>('/assessment/village-scores')
    if (res.code === 200 && res.data?.items) {
      scores.value = res.data.items
    }
  } catch (e: any) {
    error.value = e?.response?.data?.message || e?.message || '获取评估数据失败'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  font-size: 24px;
  font-weight: 700;
  color: #1a3c2a;
  margin: 0;
}
.page-desc {
  color: var(--color-text-regular);
  font-size: 14px;
  margin: 4px 0 0;
}
.stat-card {
  text-align: center;
}
</style>

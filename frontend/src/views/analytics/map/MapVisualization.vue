<template>
  <div class="map-page">
    <div class="page-header">
      <h2>地图可视化</h2>
      <p class="page-desc">帮扶村地理分布与数据概览</p>
    </div>

    <el-row :gutter="16">
      <!-- 统计卡片 -->
      <el-col v-for="card in statCards" :key="card.key" :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic :title="card.label" :value="card.value">
            <template v-if="card.suffix" #suffix>{{ card.suffix }}</template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="16">
        <el-card>
          <template #header>帮扶村省份分布</template>
          <BaseChart :option="barOpt" height="400" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>振兴层级占比</template>
          <BaseChart :option="pieOpt" height="400" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据表格 -->
    <el-card style="margin-top: 16px">
      <template #header>帮扶村列表</template>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="village_name" label="村庄名称" min-width="120" />
        <el-table-column prop="province" label="省份" width="100" />
        <el-table-column prop="county" label="县市" width="120" />
        <el-table-column prop="township" label="乡镇" width="120" />
        <el-table-column
          prop="support_unit"
          label="帮扶单位"
          min-width="160"
          show-overflow-tooltip
        />
        <el-table-column prop="is_revitalization_tier" label="振兴梯队" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.is_revitalization_tier" type="success">是</el-tag>
            <el-tag v-else type="info">否</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import BaseChart from '@/components/common/BaseChart.vue'
import { get } from '@/api/request'

interface Village {
  id: number
  village_name: string
  province: string
  county: string
  township: string
  support_unit: string
  is_revitalization_tier: boolean
}

const loading = ref(false)
const tableData = ref<Village[]>([])

const statCards = computed(() => [
  {
    key: 'total',
    label: '帮扶村总数',
    value: tableData.value.length,
    suffix: '个',
  },
  {
    key: 'townships',
    label: '覆盖乡镇',
    value: new Set(tableData.value.map((v) => v.township).filter(Boolean)).size,
    suffix: '个',
  },
  {
    key: 'counties',
    label: '覆盖县市',
    value: new Set(tableData.value.map((v) => v.county).filter(Boolean)).size,
    suffix: '个',
  },
  {
    key: 'provinces',
    label: '覆盖省份',
    value: new Set(tableData.value.map((v) => v.province).filter(Boolean)).size,
    suffix: '个',
  },
])

const provinceData = computed(() => {
  const map: Record<string, number> = {}
  tableData.value.forEach((v) => {
    if (v.province) map[v.province] = (map[v.province] || 0) + 1
  })
  return Object.entries(map).map(([k, v]) => ({ name: k, value: v }))
})

const tierData = computed(() => {
  const map: Record<string, number> = {}
  tableData.value.forEach((v) => {
    const t = v.is_revitalization_tier ? '振兴梯队' : '非振兴梯队'
    map[t] = (map[t] || 0) + 1
  })
  return Object.entries(map).map(([k, v]) => ({ name: k, value: v }))
})

const barOpt = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: {
    type: 'category',
    data: provinceData.value.map((d) => d.name),
    axisLabel: { rotate: 45 },
  },
  yAxis: { type: 'value', name: '村庄数' },
  series: [
    {
      type: 'bar',
      data: provinceData.value.map((d) => d.value),
      itemStyle: { color: '#4a7c59' },
    },
  ],
  grid: { bottom: 80 },
}))

const pieOpt = computed(() => ({
  tooltip: { trigger: 'item' },
  series: [
    {
      type: 'pie',
      data: tierData.value,
      radius: ['40%', '70%'],
      label: { formatter: '{b}: {c}' },
    },
  ],
}))

onMounted(async () => {
  loading.value = true
  try {
    const res = await get<{ code: number; data: Village[]; total?: number }>(
      '/supported-villages',
      { page: 1, page_size: 200 }
    )
    // 后端 ok_list 信封 → 拦截器把 items 提升到顶层，res.data 是 {items,total} 对象
    const payload: any = res
    const list = Array.isArray(res?.data) ? res.data : payload?.items || payload?.data?.items || []
    tableData.value = list
  } catch {
    /* silent */
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
  color: var(--color-primary-dark-1);
  margin: 0 0 4px 0;
}
.page-desc {
  color: var(--color-text-regular);
  font-size: 14px;
  margin: 0;
}
.stat-card {
  text-align: center;
}
</style>

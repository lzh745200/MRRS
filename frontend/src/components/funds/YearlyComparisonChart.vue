<template>
  <el-card class="chart-card">
    <template #header><span class="title">年度对比</span></template>
    <el-skeleton v-if="loading" :rows="5" animated />
    <ChartErrorState v-else-if="loadError" :message="loadError" @retry="load" />
    <BaseChart v-else-if="chartOption" :option="chartOption" height="320px" />
    <el-empty v-else description="暂无年度对比数据" />
  </el-card>
</template>
<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import BaseChart from '@/components/common/BaseChart.vue'
import ChartErrorState from '@/components/common/ChartErrorState.vue'
import { get } from '@/api/request'
import { getErrorMessage } from '@/utils/getErrorMessage'
import type { EChartsOption } from 'echarts'

const props = defineProps<{
  yearStart?: number
  yearEnd?: number
  department?: string
}>()

const yearlyData = ref<any[]>([])
const loading = ref(false)
const loadError = ref('')

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const params: any = {}
    if (props.yearStart) params.year_start = props.yearStart
    if (props.yearEnd) params.year_end = props.yearEnd
    if (props.department) params.department = props.department
    const res: any = await get('/funds/supported-village/statistics/yearly-comparison', params)
    // 兼容 {success, data} 信封 / 裸数组 / 裸 data 三种形态
    const data = Array.isArray(res?.data) ? res.data : Array.isArray(res) ? res : []
    yearlyData.value = data
    // 仅显式失败（success:false）进入错误态；空数据/null 保持空态
    if (res && typeof res === 'object' && res.success === false) {
      loadError.value = res.message || '暂无年度对比数据'
    }
  } catch (e) {
    // 请求异常 → 内联错误态 + 重试（不再静默空白）
    yearlyData.value = []
    loadError.value = getErrorMessage(e, '年度对比数据加载失败')
  } finally {
    loading.value = false
  }
}

const chartOption = computed<EChartsOption | null>(() => {
  if (!yearlyData.value.length) return null
  const years = yearlyData.value.map((d: any) => String(d.year || ''))
  const amounts = yearlyData.value.map((d: any) => Number(d.total_actual || d.amount || 0))
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['经费总额'] },
    xAxis: { type: 'category', data: years },
    yAxis: { type: 'value', name: '万元' },
    series: [
      {
        name: '经费总额',
        type: 'bar',
        data: amounts,
        itemStyle: { color: '#40916c' },
      },
    ],
  }
})

watch(() => [props.yearStart, props.yearEnd, props.department], load, {
  immediate: true,
})

defineExpose({ refresh: load })
</script>

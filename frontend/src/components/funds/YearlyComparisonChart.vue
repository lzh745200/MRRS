<template>
  <el-card class="chart-card">
    <template #header><span class="title">年度对比</span></template>
    <!-- 后端 /funds/supported-village/statistics/yearly-comparison 只接受 year_start/year_end，
         部门维度并未实现（FastAPI 会静默忽略未知查询参数）。此处显式告知，
         避免用户把"全部部门数据"误读为"已按部门过滤"（静默降级）。 -->
    <div v-if="departmentFilterUnsupported" class="dept-filter-notice">
      当前接口暂不支持按部门筛选，以下为全部部门的年度对比数据
    </div>
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

/** 传入了部门筛选但后端不支持该维度 → 展示显式提示（不静默当成已过滤） */
const departmentFilterUnsupported = computed(() => Boolean(props.department))

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    // 不发送 department：后端未声明该参数（未知查询参数被静默忽略），
    // 发出去只会造成"看起来按部门过滤了"的假象（提示见 departmentFilterUnsupported）
    const params: any = {}
    if (props.yearStart) params.year_start = props.yearStart
    if (props.yearEnd) params.year_end = props.yearEnd
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

<style scoped>
.dept-filter-notice {
  margin-bottom: 8px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--color-warning-dark);
  background: var(--color-warning-lightest);
  border-radius: 4px;
}
</style>

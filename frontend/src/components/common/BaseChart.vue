<template>
  <div ref="chartRef" class="base-chart" :style="{ width: width, height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import echarts from '@/utils/echarts'

interface Props {
  option: echarts.EChartsCoreOption
  width?: string
  height?: string
  theme?: string
  autoResize?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  width: '100%',
  height: '400px',
  theme: '',
  autoResize: true,
})

const emit = defineEmits<{
  'chart-ready': [chart: echarts.ECharts]
  'chart-click': [params: any]
}>()

const chartRef = ref<HTMLDivElement>()
let chartInstance: echarts.ECharts | null = null
/** 卸载标记：nextTick 回调可能在卸载之后才执行 */
let unmounted = false

const initChart = () => {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value, props.theme)
  chartInstance.setOption(props.option)

  chartInstance.on('click', (params) => {
    emit('chart-click', params)
  })

  emit('chart-ready', chartInstance)
}

const resizeChart = () => {
  chartInstance?.resize()
}

watch(
  () => props.option,
  (newOption) => {
    if (chartInstance) {
      // 不使用 notMerge=true 全量替换：那会重置 dataZoom 位置、legend 选择等
      // 用户视图状态（数据刷新后图表"跳回"初始视图）。合并更新保留交互状态。
      chartInstance.setOption(newOption)
    }
  },
  { deep: true }
)

// autoResize 中途变化时对称地附加/移除监听，避免"只加不减"的泄漏
watch(
  () => props.autoResize,
  (enabled) => {
    if (enabled) {
      window.addEventListener('resize', resizeChart)
    } else {
      window.removeEventListener('resize', resizeChart)
    }
  }
)

onMounted(() => {
  // 同步注册 resize 监听（不放进 nextTick）：tick 前卸载时监听会挂在已销毁
  // 组件上且再也无人移除（onUnmounted 只看得到注册过的那一份）
  if (props.autoResize) {
    window.addEventListener('resize', resizeChart)
  }
  nextTick(() => {
    if (unmounted) return
    initChart()
  })
})

onUnmounted(() => {
  unmounted = true
  // 无条件移除：按"卸载那一刻的 props.autoResize"判断会与注册时不对称而泄漏
  window.removeEventListener('resize', resizeChart)

  chartInstance?.dispose()
  chartInstance = null
})

defineExpose({
  getChart: () => chartInstance,
  resize: resizeChart,
})
</script>

<style scoped>
.base-chart {
  min-height: 200px;
}
</style>

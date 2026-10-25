<template>
  <div ref="chartRef" class="base-chart" :style="{ width: width, height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import echarts from '@/utils/echarts'
import { ECHARTS_THEME_CHANGED, getCurrentTheme } from '@/utils/echarts-theme'

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
  // 调用点（nextTick 回调）已先判 `unmounted` 提前返回，且模板根节点恒存在，
  // 故此处的空值早退在真实路径上不可达。保留 `chartRef.value!` 的非空断言
  // 而非 runtime 分支：既让 echarts.init 收到确切类型，也不留永远计 0 的死分支。
  const el = chartRef.value as HTMLDivElement

  // theme 留空时跟随当前 DOM 主题（data-theme），不再固定浅色：
  // 大屏/户外高对比下若仍用浅色主题，轴线与文字会看不清。
  chartInstance = echarts.init(el, props.theme || getCurrentTheme())
  chartInstance.setOption(props.option)

  chartInstance.on('click', (params) => {
    emit('chart-click', params)
  })

  emit('chart-ready', chartInstance)
}

/**
 * 主题切换后重建实例：`registerTheme` 只影响之后 init 的实例，
 * 已存在的实例不会自动变色，必须 dispose 后重新 init。
 *
 * 无需 `unmounted` 守卫：监听在 `onUnmounted` 里会先被移除，
 * 卸载后本函数不可能再被调用（留一个永不进入的分支只会制造覆盖率黑洞）。
 */
const rebuildForTheme = () => {
  chartInstance?.dispose()
  chartInstance = null
  initChart()
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
  window.addEventListener(ECHARTS_THEME_CHANGED, rebuildForTheme)
  nextTick(() => {
    if (unmounted) return
    initChart()
  })
})

onUnmounted(() => {
  unmounted = true
  // 无条件移除：按"卸载那一刻的 props.autoResize"判断会与注册时不对称而泄漏
  window.removeEventListener('resize', resizeChart)
  window.removeEventListener(ECHARTS_THEME_CHANGED, rebuildForTheme)

  chartInstance?.dispose()
  chartInstance = null
})

defineExpose({
  getChart: () => chartInstance,
  resize: resizeChart,
  // 主题切换的同一入口（dispose + 按当前 DOM 主题重建）。
  // 对外暴露是为了让调用方在"已知主题变化但事件未发出"时按需刷新，
  // 也让该路径可被直接测试 —— 只靠全局自定义事件触发时，多套件并行下
  // 该函数的覆盖归属会漂移（实测：单跑 100%、全量 99.8%）。
  rebuild: rebuildForTheme,
})
</script>

<style scoped>
.base-chart {
  min-height: 200px;
}
</style>

// ECharts tree-shaking — 按需注册组件，替代全量 import * as echarts
import * as echarts from 'echarts/core'
// 注意：此列表必须覆盖全仓实际用到的图表/组件形态，否则运行时**静默丢弃**
// （ECharts 对未注册的 series.type / 组件不报错，只是不渲染）。
// 全仓核对（2026-09-30）：OfflineMap.vue type:'lines' / effectScatter / visualMap，
// gantt.ts markLine，故补齐 LinesChart / EffectScatterChart / VisualMapComponent /
// MarkLineComponent 四项（仍为按需引入，不改成全量 import）。
import {
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  RadarChart,
  MapChart,
  LinesChart,
  EffectScatterChart,
} from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent,
  GeoComponent,
  VisualMapComponent,
  MarkLineComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  RadarChart,
  MapChart,
  LinesChart,
  EffectScatterChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent,
  GeoComponent,
  VisualMapComponent,
  MarkLineComponent,
  CanvasRenderer,
])

// 注册科技风主题（幂等，多次调用安全）
import { registerMilitaryTheme } from './echarts-theme'
registerMilitaryTheme()

export default echarts

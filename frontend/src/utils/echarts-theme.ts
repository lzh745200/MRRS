/**
 * ECharts "科技风" 主题配置
 *
 * 设计理念：
 * - 品牌蓝 (#1e4d8c) + 振兴绿 (#2d6a4f) + 点缀金 (#b8960c) 为品牌色系
 * - 低饱和度配色，去除冗余视觉噪音
 * - 干净克制的坐标轴、网格线、Tooltip
 * - 与 dashboard-theme.scss 中的 CSS 变量保持一致
 *
 * 使用方式：
 *   import { registerMilitaryTheme } from "@/utils/echarts-theme";
 *   registerMilitaryTheme(); // 在应用初始化时调用一次
 *   // 之后 echarts.init(dom, "militaryTech") 即可使用
 */

import type { EChartsCoreOption } from 'echarts/core'
import { shallowRef } from 'vue'
// 直接从 echarts/core 导入，避免与 @/utils/echarts 形成循环导入
// （echarts.ts 顶层会调用本模块的 registerMilitaryTheme()）
import * as echarts from 'echarts/core'

// ============================================================================
// 色彩体系
// ============================================================================

/** 品牌色板 —— 16 色，覆盖饼图/柱图等多系列场景 */
const COLOR_PALETTE_FALLBACK: readonly string[] = [
  '#1e4d8c', // 品牌蓝（主）
  '#2d6a4f', // 振兴绿
  '#b8960c', // 点缀金
  '#3b82f6', // 亮蓝
  '#52b788', // 亮绿
  '#f59e0b', // 琥珀
  '#ef4444', // 警示红
  '#8b5cf6', // 紫罗兰
  '#06b6d4', // 青色
  '#84cc16', // 柠檬绿
  '#f97316', // 橙色
  '#ec4899', // 粉红
  '#6366f1', // 靛蓝
  '#14b8a6', // 薄荷
  '#e11d48', // 玫红
  '#64748b', // 石板灰
]

/**
 * 调色板与设计 Token 的对应关系（索引与 `COLOR_PALETTE` 对齐）。
 * `null` 表示该色无对应 Token，保留原字面量 —— 与其编一个近似值造成"看着变了其实没变"，
 * 不如明确标注"未纳入 Token 体系"。
 */
const PALETTE_TOKEN_NAMES: readonly (string | null)[] = [
  '--color-primary',
  '--color-success',
  '--color-gold',
  null,
  null,
  '--color-warning',
  '--color-danger',
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
  null,
]

/**
 * **实时**调色板：内容由 `syncPaletteFromTokens()` 原地替换（不换引用），
 * 因此 `COLOR_PALETTE[5]` 这类既有调用点无需改动，也能在主题切换后拿到新值。
 */
/**
 * 主题版本号：主题切换时自增。`COLOR_PALETTE` 的读取会自动登记它（见下方 Proxy），
 * 于是**任何**在 computed / render 里读过调色板的视图，都会在切换主题后自动重算 ——
 * 5 个图表页（Dashboard / BigScreen / ChartRow / ruralWorks-Analysis / schools-List）
 * 因此一行都不用改就有正确颜色。
 */
export const chartThemeRevision = shallowRef(0)

/**
 * 调色板的**实际存储**：`syncPaletteFromTokens()` 原地替换内容（引用不变）。
 */
const PALETTE_TARGET: string[] = [...COLOR_PALETTE_FALLBACK]

/**
 * **实时**调色板（对外仍是数组，`COLOR_PALETTE[5]` 这类既有调用点无需改动）。
 *
 * 为什么用 Proxy：视图里的图表 option 多在 `computed` 中拼装，若直接读普通数组，
 * 主题切换后 computed 不会重算，option 里存的还是旧色值字面量 —— 于是"切了主题、
 * 图表没变"。这里在 `get` 里读一次 `chartThemeRevision.value`，把主题版本登记成
 * **依赖**：主题一变，所有读过调色板的 computed 自动失效重算。
 * 这是"零侵入接线"，比逐个改 5 个视图更不容易漏、也更不容易被后续复制粘贴带偏。
 */
export const COLOR_PALETTE: string[] = new Proxy(PALETTE_TARGET, {
  get(target, prop, receiver) {
    // 仅登记依赖，不做值变换：返回值仍是数组自身语义（length / 迭代器 / 方法都照旧）
    void chartThemeRevision.value
    return Reflect.get(target, prop, receiver)
  },
})

/** 把 Token 值灌进调色板（原地替换；无 DOM 环境自动回退字面量）。 */
export function syncPaletteFromTokens(): void {
  const next = COLOR_PALETTE_FALLBACK.map((fallback, index) => {
    const token = PALETTE_TOKEN_NAMES[index]
    return token ? themeColor(token, fallback) : fallback
  })
  PALETTE_TARGET.splice(0, PALETTE_TARGET.length, ...next)
}

// ============================================================================
// 主题配置
// ============================================================================

interface ThemeConfig {
  color: string[]
  backgroundColor: string
  textStyle: {
    color: string
    fontFamily: string
  }
  title: {
    textStyle: { color: string; fontWeight: number | string; fontSize: number }
    subtextStyle: { color: string; fontSize: number }
  }
  line: {
    itemStyle: { borderWidth: number }
    lineStyle: { width: number }
    symbolSize: number
    symbol: string
    smooth: boolean
  }
  bar: {
    itemStyle: {
      barBorderWidth: number
      barBorderColor: string
      borderRadius: number[]
    }
    emphasis: {
      itemStyle: {
        barBorderWidth: number
        barBorderColor: string
      }
    }
  }
  pie: {
    itemStyle: {
      borderWidth: number
      borderColor: string
      borderRadius: number
    }
    emphasis: {
      itemStyle: {
        shadowBlur: number
        shadowOffsetX: number
        shadowColor: string
      }
    }
  }
  categoryAxis: {
    axisLine: {
      show: boolean
      lineStyle: { color: string }
    }
    axisTick: { show: boolean }
    axisLabel: { color: string; fontSize: number }
    splitLine: { show: boolean }
    nameTextStyle: { color: string; fontSize: number }
  }
  valueAxis: {
    axisLine: { show: boolean }
    axisTick: { show: boolean }
    axisLabel: { color: string; fontSize: number }
    splitLine: {
      show: boolean
      lineStyle: { color: string; type: string; width: number }
    }
    nameTextStyle: { color: string; fontSize: number }
  }
  logAxis: {
    axisLine: { show: boolean }
    axisTick: { show: boolean }
    axisLabel: { color: string; fontSize: number }
    splitLine: {
      show: boolean
      lineStyle: { color: string; type: string; width: number }
    }
  }
  timeAxis: {
    axisLine: { show: boolean; lineStyle: { color: string } }
    axisTick: { show: boolean }
    axisLabel: { color: string; fontSize: number }
    splitLine: { show: boolean }
  }
  toolbox: {
    iconStyle: {
      borderColor: string
    }
    emphasis: {
      iconStyle: {
        borderColor: string
      }
    }
  }
  legend: {
    textStyle: { color: string; fontSize: number }
  }
  tooltip: {
    axisPointer: {
      lineStyle: { color: string; width: number }
      crossStyle: { color: string; width: number }
    }
  }
  dataZoom: {
    dataBackground: {
      lineStyle: { color: string }
      areaStyle: { color: string }
    }
    selectedDataBackground: {
      lineStyle: { color: string }
      areaStyle: { color: string }
    }
    handleStyle: { color: string }
    textStyle: { color: string }
  }
}

// ============================================================================
// 浅色主题 —— 干净、克制、科技感
// ============================================================================

const militaryTechTheme: ThemeConfig = {
  color: COLOR_PALETTE,

  backgroundColor: 'transparent',

  textStyle: {
    color: '#1e293b',
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Microsoft YaHei', 'PingFang SC', sans-serif",
  },

  // ── 标题 ──
  title: {
    textStyle: {
      color: '#0f172a',
      fontWeight: 600,
      fontSize: 16,
    },
    subtextStyle: {
      color: '#94a3b8',
      fontSize: 12,
    },
  },

  // ── 折线图 ──
  line: {
    itemStyle: {
      borderWidth: 2,
    },
    lineStyle: {
      width: 3,
    },
    symbolSize: 6,
    symbol: 'circle',
    smooth: false,
  },

  // ── 柱状图 ──
  bar: {
    itemStyle: {
      barBorderWidth: 0,
      barBorderColor: 'transparent',
      borderRadius: [6, 6, 0, 0],
    },
    emphasis: {
      itemStyle: {
        barBorderWidth: 0,
        barBorderColor: 'transparent',
      },
    },
  },

  // ── 饼图 ──
  pie: {
    itemStyle: {
      borderWidth: 3,
      borderColor: '#ffffff',
      borderRadius: 4,
    },
    emphasis: {
      itemStyle: {
        shadowBlur: 20,
        shadowOffsetX: 0,
        shadowColor: 'rgba(0, 0, 0, 0.12)',
      },
    },
  },

  // ── 类目轴（X 轴） ──
  categoryAxis: {
    axisLine: {
      show: true,
      lineStyle: { color: '#e2e8f0' },
    },
    axisTick: { show: false },
    axisLabel: {
      color: '#94a3b8',
      fontSize: 11,
    },
    splitLine: { show: false },
    nameTextStyle: {
      color: '#94a3b8',
      fontSize: 11,
    },
  },

  // ── 数值轴（Y 轴） ──
  valueAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: '#94a3b8',
      fontSize: 11,
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: '#f1f5f9',
        type: 'dashed',
        width: 1,
      },
    },
    nameTextStyle: {
      color: '#94a3b8',
      fontSize: 11,
    },
  },

  // ── 对数轴 ──
  logAxis: {
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: '#94a3b8',
      fontSize: 11,
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: '#f1f5f9',
        type: 'dashed',
        width: 1,
      },
    },
  },

  // ── 时间轴 ──
  timeAxis: {
    axisLine: {
      show: true,
      lineStyle: { color: '#e2e8f0' },
    },
    axisTick: { show: false },
    axisLabel: {
      color: '#94a3b8',
      fontSize: 11,
    },
    splitLine: { show: false },
  },

  // ── 工具箱 ──
  toolbox: {
    iconStyle: {
      borderColor: '#94a3b8',
    },
    emphasis: {
      iconStyle: {
        borderColor: '#1e4d8c',
      },
    },
  },

  // ── 图例 ──
  legend: {
    textStyle: {
      color: '#64748b',
      fontSize: 12,
    },
  },

  // ── 提示框辅助线 ──
  tooltip: {
    axisPointer: {
      lineStyle: {
        color: '#94a3b8',
        width: 1,
      },
      crossStyle: {
        color: '#94a3b8',
        width: 1,
      },
    },
  },

  // ── 数据缩放 ──
  dataZoom: {
    dataBackground: {
      lineStyle: { color: '#cbd5e1' },
      areaStyle: { color: 'rgba(203, 213, 225, 0.15)' },
    },
    selectedDataBackground: {
      lineStyle: { color: '#1e4d8c' },
      areaStyle: { color: 'rgba(30, 77, 140, 0.1)' },
    },
    handleStyle: { color: '#94a3b8' },
    textStyle: { color: '#94a3b8' },
  },
}

// ============================================================================
// 暗色主题变体 —— 兼容 [data-theme="dark-bigscreen"]
// ============================================================================

const militaryTechDarkTheme: ThemeConfig = {
  ...militaryTechTheme,

  backgroundColor: 'transparent',

  textStyle: {
    ...militaryTechTheme.textStyle,
    color: '#e2e8f0',
  },

  title: {
    textStyle: {
      color: '#f1f5f9',
      fontWeight: 600,
      fontSize: 16,
    },
    subtextStyle: {
      color: '#64748b',
      fontSize: 12,
    },
  },

  categoryAxis: {
    ...militaryTechTheme.categoryAxis,
    axisLine: {
      show: true,
      lineStyle: { color: '#334155' },
    },
    axisLabel: {
      color: '#64748b',
      fontSize: 11,
    },
  },

  valueAxis: {
    ...militaryTechTheme.valueAxis,
    axisLabel: {
      color: '#64748b',
      fontSize: 11,
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: 'rgba(51, 65, 85, 0.5)',
        type: 'dashed',
        width: 1,
      },
    },
  },

  legend: {
    textStyle: {
      color: '#94a3b8',
      fontSize: 12,
    },
  },

  tooltip: {
    axisPointer: {
      lineStyle: {
        color: '#475569',
        width: 1,
      },
      crossStyle: {
        color: '#475569',
        width: 1,
      },
    },
  },

  // ── 以下为 2026-09-30 补齐：此前暗色变体只覆盖 textStyle/title/categoryAxis/
  //    valueAxis/legend/tooltip，饼图描边、对数轴/时间轴、工具箱图标、数据缩放
  //    仍沿用浅色取值（#ffffff 描边、#cbd5e1 缩放条、#94a3b8 图标）→ 在暗底上
  //    出现白边/刺眼条。取值沿用本文件暗色族的 slate 色阶。──
  pie: {
    ...militaryTechTheme.pie,
    itemStyle: {
      ...militaryTechTheme.pie.itemStyle,
      // 分隔描边用暗色表面色，替代浅色主题的纯白 #ffffff
      borderColor: '#1e293b',
    },
  },

  logAxis: {
    ...militaryTechTheme.logAxis,
    axisLabel: {
      color: '#64748b',
      fontSize: 11,
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: 'rgba(51, 65, 85, 0.5)',
        type: 'dashed',
        width: 1,
      },
    },
  },

  timeAxis: {
    ...militaryTechTheme.timeAxis,
    axisLine: {
      show: true,
      lineStyle: { color: '#334155' },
    },
    axisLabel: {
      color: '#64748b',
      fontSize: 11,
    },
  },

  toolbox: {
    iconStyle: {
      borderColor: '#64748b',
    },
    emphasis: {
      iconStyle: {
        // 浅色主题的强调色是品牌深蓝 #1e4d8c，在暗底上几乎不可见 → 用亮蓝
        borderColor: '#3b82f6',
      },
    },
  },

  dataZoom: {
    dataBackground: {
      lineStyle: { color: '#334155' },
      areaStyle: { color: 'rgba(51, 65, 85, 0.3)' },
    },
    selectedDataBackground: {
      lineStyle: { color: '#3b82f6' },
      areaStyle: { color: 'rgba(59, 130, 246, 0.15)' },
    },
    handleStyle: { color: '#64748b' },
    textStyle: { color: '#94a3b8' },
  },
}

// ============================================================================
// 主题注册
// ============================================================================

let isThemeRegistered = false

/**
 * 注册 ECharts 科技风主题。
 * 幂等调用——多次调用仅首次生效。
 *
 * 注册后可通过以下方式使用：
 * - `echarts.init(dom, "militaryTech")`     → 浅色主题
 * - `echarts.init(dom, "militaryTechDark")` → 暗色主题
 */
export function registerMilitaryTheme(): void {
  if (isThemeRegistered) return

  // 调色板先与当前主题的 Token 同步，再注册 —— 否则注册进去的永远是字面量色值，
  // 切换"户外高对比"时图表仍是军绿，这就是 2026-10-25 修掉的那个观感缺陷。
  syncPaletteFromTokens()

  echarts.registerTheme('militaryTech', militaryTechTheme as unknown as EChartsCoreOption)
  echarts.registerTheme('militaryTechDark', militaryTechDarkTheme as unknown as EChartsCoreOption)

  isThemeRegistered = true
}

/** 主题切换事件名：图表组件监听它 → dispose + 重建，让新主题立即生效。 */
export const ECHARTS_THEME_CHANGED = 'mrrs:echarts-theme-changed'

/**
 * 主题切换后调用：同步调色板 → 重新注册主题 → 通知所有图表重建。
 *
 * 为什么必须重建：`echarts.registerTheme` 只影响**之后** `init` 的实例，
 * 已存在的实例不会因为重新注册而变色。所以事件里各组件自行 dispose + init。
 */
export function refreshMilitaryTheme(): void {
  isThemeRegistered = false
  registerMilitaryTheme()
  chartThemeRevision.value += 1
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(new CustomEvent(ECHARTS_THEME_CHANGED))
  }
}

/**
 * 根据当前 DOM 环境自动选择主题。
 * 检测 document.documentElement 的 data-theme 属性：
 * - `data-theme="dark-bigscreen"` / `"outdoor"` → "militaryTechDark"
 * - 其他 → "militaryTech"（默认浅色）
 */
export function getCurrentTheme(): string {
  if (typeof document !== 'undefined') {
    const theme = document.documentElement.getAttribute('data-theme')
    if (theme === 'dark-bigscreen' || theme === 'outdoor') return 'militaryTechDark'
  }
  return 'militaryTech'
}

// ============================================================================
// 导出色彩常量（供外部直接引用，无需走 registerTheme）
// ============================================================================
// 注：COLOR_PALETTE 已在上方以 `export const` 声明（Proxy 实时调色板），此处不再重复导出。

export const MILITARY_BLUE = '#1e4d8c'
export const REVITALIZATION_GREEN = '#2d6a4f'
export const BADGE_GOLD = '#b8960c'

/**
 * 读取当前主题的 CSS 变量值 —— 图表轴/文字/分割线颜色必须跟随主题
 * （W11-T45：暗色主题下写死浅色 hex 会刺眼）。
 *
 * 无 DOM 环境（SSR / 未挂载的单测）回退到 fallback，保证纯函数可测。
 *
 * @param name CSS 变量名（如 `--color-text-primary`）
 * @param fallback 变量缺失或不可读时的回退色
 */
export function themeColor(name: string, fallback: string): string {
  if (typeof document === 'undefined' || typeof getComputedStyle !== 'function') {
    return fallback
  }
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

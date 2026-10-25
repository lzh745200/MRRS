/**
 * W23 视觉回归基线（Playwright DOM 结构快照）公共辅助
 *
 * 设计目标（契约 `.scratch/w23-ui-redesign/000-contract.md` §3）：
 * - **不比较像素**：只采集 DOM 结构（路由、标题、内容长度、关键区域存在性、表头数量）；
 * - **CI 稳定**：基线只记录不随业务数据/并行 UI 改造漂移的稳定字段；
 * - **能挡住白屏/路由坏掉**：内容长度 + 至少一个内容区域存在 + 无 console error。
 *
 * 页面清单固定为 10 个关键页面（工作台/帮扶村/项目/经费/一户一档/影像库/消费帮扶/
 * 系统管理/数据校验/大屏），与契约 W6 交付一致。
 */
import { expect, type Page } from '@playwright/test'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

/** 页面级稳定基线：route meta title 由 router/guards.ts 写入 document.title（W2-W5 不改 router） */
export interface VisualBaseline {
  /** 用例名（同时用于快照名） */
  name: string
  /** 访问路径 */
  path: string
  /** 期望的路由前缀（URL 校验） */
  pathPrefix: string
  /** 期望的 document.title（router meta.title，稳定契约） */
  title: string
  /**
   * 关键内容区域「任意一组命中即可」（组间为 AND、组内为 OR）：
   * 例如 [['table', 'empty']] 表示页面必须有表格或空态之一。
   */
  requiredAnyOf: string[][]
}

export const VISUAL_BASELINES: VisualBaseline[] = [
  {
    name: 'dashboard',
    path: '/dashboard',
    pathPrefix: '/dashboard',
    title: '工作台',
    requiredAnyOf: [['statCard', 'table', 'empty', 'card', 'controls']],
  },
  {
    name: 'supported-villages',
    path: '/supported-villages',
    pathPrefix: '/supported-villages',
    title: '帮扶村管理',
    requiredAnyOf: [['table', 'empty']],
  },
  {
    name: 'projects',
    path: '/projects',
    pathPrefix: '/projects',
    title: '帮扶项目管理',
    requiredAnyOf: [['table', 'empty']],
  },
  {
    name: 'funds',
    path: '/funds',
    pathPrefix: '/funds',
    title: '经费管理',
    requiredAnyOf: [['table', 'empty']],
  },
  {
    name: 'households',
    path: '/households',
    pathPrefix: '/households',
    title: '一户一档',
    requiredAnyOf: [['table', 'empty', 'card']],
  },
  {
    name: 'media',
    path: '/media',
    pathPrefix: '/media',
    title: '影像库',
    requiredAnyOf: [['table', 'empty', 'card', 'tabs']],
  },
  {
    name: 'consumption',
    path: '/consumption',
    pathPrefix: '/consumption',
    title: '消费帮扶',
    requiredAnyOf: [['table', 'empty']],
  },
  {
    name: 'system-console',
    path: '/system/console/org',
    pathPrefix: '/system/console',
    title: '系统管理',
    requiredAnyOf: [['table', 'empty', 'card', 'form', 'tabs', 'controls']],
  },
  {
    name: 'data-verify',
    path: '/data-verify',
    pathPrefix: '/data-verify',
    title: '数据校验',
    // W22 数据校验页为「Tabs + 自绘筛选区 + 结果区」，不保证使用 el-table/el-empty，
    // 因此允许 tabs / controls（按钮、下拉、输入框）作为内容区域存在性证据。
    requiredAnyOf: [['table', 'empty', 'card', 'form', 'tabs', 'controls']],
  },
  {
    name: 'bigscreen',
    path: '/bigscreen',
    pathPrefix: '/bigscreen',
    title: '帮扶成效大屏',
    requiredAnyOf: [['bigscreen']],
  },
]

/**
 * ⑨ 视觉回归扩容（2026-10-26）：从 10 页扩到「30 个 console tab + 4 个核心表单」。
 *
 * 为什么覆盖 console 的每一个 tab：系统管理 6 个聚合页共 30 个 tab，此前只有
 * `/system/console/org` 一个落地页在基线上 —— 任一 tab 的组件映射坏掉（菜单有、组件缺）
 * 都不会被视觉回归发现，而这类故障的表现正是"点进去白屏"。
 *
 * 为什么覆盖新增表单：录入态是最容易被 UI 改造打破的界面（栅格、校验、字段布局），
 * 且没有列表页那种"至少还有表格"的兜底观感。
 */
const CONSOLE_TAB_BASELINES: Array<[group: string, tab: string]> = [
  ['org', 'users-orgs'],
  ['org', 'roles'],
  ['org', 'menus'],
  ['org', 'system-permission-packs'],
  ['org', 'organizations'],
  ['org', 'system-org-grant'],
  ['org', 'system-grant-import'],
  ['security', 'audit'],
  ['security', 'zero-trust'],
  ['security', 'secrets'],
  ['security', 'data-tier'],
  ['security', 'encryption'],
  ['security', 'machine-code'],
  ['ops', 'system-overview'],
  ['ops', 'health-check'],
  ['ops', 'monitor'],
  ['ops', 'cache'],
  ['ops', 'tasks'],
  ['ops', 'environment'],
  ['ops', 'error-reports'],
  ['storage', 'backup'],
  ['storage', 'chunked-upload'],
  ['storage', 'map-tiles'],
  ['storage', 'control-package'],
  ['storage', 'config-package'],
  ['settings', 'update-logs'],
  ['about', 'about'],
  ['about', 'feedback'],
  ['about', 'help'],
  ['about', 'admin-dashboard'],
]

const FORM_BASELINES: VisualBaseline[] = [
  {
    name: 'form-policy-create',
    path: '/policies/create',
    pathPrefix: '/policies',
    title: '添加政策',
    requiredAnyOf: [['form', 'card']],
  },
  {
    name: 'form-project-create',
    path: '/projects/create',
    pathPrefix: '/projects',
    title: '添加项目',
    requiredAnyOf: [['form', 'card']],
  },
  {
    name: 'form-school-create',
    path: '/schools/create',
    pathPrefix: '/schools',
    title: '添加学校',
    requiredAnyOf: [['form', 'card']],
  },
  {
    name: 'form-fund-create',
    path: '/funds/create',
    pathPrefix: '/funds',
    title: '经费登记',
    requiredAnyOf: [['form', 'card']],
  },
]

VISUAL_BASELINES.push(
  ...CONSOLE_TAB_BASELINES.map(([group, tab]) => ({
    name: `console-${group}-${tab}`,
    path: `/system/console/${group}?tab=${tab}`,
    pathPrefix: '/system/console',
    title: '系统管理',
    requiredAnyOf: [['table', 'empty', 'card', 'form', 'tabs', 'controls']],
  })),
  ...FORM_BASELINES
)

/** 采集到的页面结构（供断言与快照） */
export interface PageStructure {
  /** 实际路由 pathname（去掉 query） */
  urlPath: string
  /** document.title */
  title: string
  /** 主内容区可见文本长度（去掉首尾空白） */
  contentLength: number
  /** 关键区域存在性 */
  landmarks: Record<string, boolean>
  /** 首个表格的表头数量（无表格为 0） */
  tableHeaderCount: number
  /** 页面标题类元素数量 */
  headingCount: number
}

/** 关键区域选择器（命中即 true） */
const LANDMARK_SELECTORS: Record<string, string> = {
  table: '.el-table',
  empty: '.app-empty, .el-empty',
  statCard: '.app-stat-card, .stats-row, .kpi-item',
  card: '.app-card, .el-card, .filter-card, .table-card',
  form: '.el-form',
  tabs: '.el-tabs',
  controls: 'button, .el-select, .el-input, .el-radio-group',
  bigscreen: '.big-screen',
}

/** 主内容容器：优先 main / #main-content，回退 #app（布局差异时仍能采集） */
const MAIN_SELECTOR = 'main, #main-content, #app'

/**
 * 注册页面错误收集器（console.error + 未捕获异常），返回数组供用例断言为空。
 * 必须在 page.goto 之前调用。
 *
 * 已知噪声过滤：浏览器对 4xx 资源请求自动输出的
 * 「Failed to load resource: ... 4xx」属**页面/接口契约**问题
 * （当前 E2E 观测到 `page_size=500` 等参数超后端上限 → 422），
 * 由页面包修复，不属于视觉结构回归判据；另 Axios 取消请求（CanceledError，
 * 组件卸载/重复加载时的正常 abort）也不作为失败判据。
 * 视觉基线仍严格拦截：
 * - 未捕获 JS 异常（pageerror）；
 * - 5xx 资源加载失败；
 * - 其他非资源/非取消类 console.error。
 */
const RESOURCE_4XX_PATTERN =
  /Failed to load resource: the server responded with a status of 4\d\d\b/
/** Axios/浏览器取消请求（导航或组件卸载触发，属正常中止而非页面缺陷） */
const CANCELED_PATTERN = /CanceledError|canceled|ERR_ABORTED|请求已取消/i

export function collectPageErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    if (RESOURCE_4XX_PATTERN.test(message.text()) || CANCELED_PATTERN.test(message.text())) {
      if (process.env.DEBUG_VISUAL === '1') {
        console.log(`[visual-debug] 忽略已知噪声: ${message.text()}`)
      }
      return
    }
    const location = message.location()
    const suffix = location.url ? ` @ ${location.url}` : ''
    errors.push(`console.error: ${message.text()}${suffix}`)
  })
  page.on('pageerror', (error) => {
    errors.push(`pageerror: ${error.message}`)
  })
  if (process.env.DEBUG_VISUAL === '1') {
    page.on('response', (response) => {
      if (response.status() >= 400) {
        // 调试用：定位 4xx/5xx 请求；正式断言只看上面收集的 console/pageerror
        console.log(`[visual-debug] ${response.status()} ${response.url()}`)
      }
    })
  }
  return errors
}

/** 等待页面进入“有内容”状态：主内容区文本非空 */
async function waitForContent(page: Page): Promise<void> {
  await page.waitForFunction(
    (selector) => {
      const root = document.querySelector(selector)
      return (root?.textContent ?? '').trim().length > 0
    },
    MAIN_SELECTOR,
    { timeout: 15000 }
  )
}

/** 等待至少一个关键区域出现（超时不抛，交给断言给出可读失败信息） */
async function waitForLandmark(page: Page): Promise<void> {
  const selector = Object.values(LANDMARK_SELECTORS).join(', ')
  await page.waitForSelector(selector, { timeout: 10000 }).catch(() => undefined)
}

/** 打开页面并采集 DOM 结构（不截图、不比较像素） */
export async function captureStructure(page: Page, path: string): Promise<PageStructure> {
  await page.goto(path)
  await page.waitForLoadState('domcontentloaded')
  await page.locator('#app').waitFor({ state: 'attached', timeout: 10000 })
  await waitForContent(page)
  await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => undefined)
  await waitForLandmark(page)

  return page.evaluate(
    ({ mainSelector, landmarkSelectors }) => {
      const main = document.querySelector(mainSelector) as HTMLElement | null
      const landmarks: Record<string, boolean> = {}
      for (const [name, selector] of Object.entries(landmarkSelectors)) {
        landmarks[name] = document.querySelectorAll(selector).length > 0
      }
      const tableHeaders = document.querySelectorAll('.el-table th .cell')
      const headings = document.querySelectorAll('h1, h2, .page-header__title, .header-title')
      return {
        urlPath: window.location.pathname,
        title: document.title,
        contentLength: (main?.textContent ?? '').replace(/\s+/g, ' ').trim().length,
        landmarks,
        tableHeaderCount: tableHeaders.length,
        headingCount: headings.length,
      }
    },
    { mainSelector: MAIN_SELECTOR, landmarkSelectors: LANDMARK_SELECTORS }
  )
}

/** 断言基线要求的“任一内容区域”至少命中一组 */
export function expectRequiredLandmarks(baseline: VisualBaseline, structure: PageStructure): void {
  for (const anyOf of baseline.requiredAnyOf) {
    const hit = anyOf.some((landmark) => structure.landmarks[landmark] === true)
    expect(
      hit,
      `[${baseline.name}] 缺少内容区域：期望 ${anyOf.join(' / ')} 至少一个，实际 landmarks=${JSON.stringify(
        structure.landmarks
      )}`
    ).toBe(true)
  }
}

/** 可选：断言存在表格时表头正常渲染（防止“空壳表格”回归） */
export function expectTableHeadersIfPresent(
  baseline: VisualBaseline,
  structure: PageStructure
): void {
  if (structure.landmarks.table) {
    expect(structure.tableHeaderCount, `[${baseline.name}] 表格存在但表头为空`).toBeGreaterThan(0)
  }
}

// ════════════════════════════════════════════════════════════════════
//  文件化 DOM 结构快照（跨平台稳定，不比较像素）
//
//  不用 Playwright 的 toMatchSnapshot：其默认快照文件名带平台后缀
//  （-chromium-win32 / -chromium-linux），Windows 本地生成、Linux CI 会因
//  缺快照而失败，无法满足“CI 稳定运行”。这里改为自持 JSON 基线：
//  只记录稳定字段（路由/标题/内容存在/关键区域是否命中），跨平台一致；
//  确需更新时运行 `UPDATE_VISUAL_BASELINE=1 npx playwright test tests/e2e/visual`。
// ════════════════════════════════════════════════════════════════════

/** 单页 DOM 结构快照记录（稳定字段，不含业务数据/像素） */
export interface VisualSnapshotRecord {
  name: string
  path: string
  title: string
  /** 主内容区是否有可见文本 */
  contentPresent: boolean
  /** 基线声明的每组「关键内容区域」是否命中（顺序与 requiredAnyOf 一致） */
  landmarksHit: boolean[]
}

/** 结构快照文件（仓库内、跨平台共享） */
const SNAPSHOT_FILE = resolve(process.cwd(), 'tests/e2e/visual/__baselines__/visual-baseline.json')

/** 由采集结果生成快照记录（只保留稳定字段） */
export function buildSnapshotRecord(
  baseline: VisualBaseline,
  structure: PageStructure
): VisualSnapshotRecord {
  return {
    name: baseline.name,
    path: structure.urlPath,
    title: structure.title,
    contentPresent: structure.contentLength > 0,
    landmarksHit: baseline.requiredAnyOf.map((anyOf) =>
      anyOf.some((landmark) => structure.landmarks[landmark] === true)
    ),
  }
}

/** 读取已提交的结构快照基线（容忍编辑器写入的 UTF-8 BOM） */
export function loadVisualSnapshots(): VisualSnapshotRecord[] {
  if (!existsSync(SNAPSHOT_FILE)) return []
  const raw = readFileSync(SNAPSHOT_FILE, 'utf8').replace(/^\uFEFF/, '')
  return JSON.parse(raw) as VisualSnapshotRecord[]
}

/** 覆盖写入结构快照基线（仅在 UPDATE_VISUAL_BASELINE=1 时调用） */
export function writeVisualSnapshots(records: VisualSnapshotRecord[]): void {
  mkdirSync(dirname(SNAPSHOT_FILE), { recursive: true })
  writeFileSync(SNAPSHOT_FILE, `${JSON.stringify(records, null, 2)}\n`, 'utf8')
}

/** 断言当前页面结构与已提交基线逐字段一致（差异即 UI 结构回归） */
export function expectSnapshotMatches(
  record: VisualSnapshotRecord,
  saved: VisualSnapshotRecord[]
): void {
  const baselineRecord = saved.find((item) => item.name === record.name)
  expect(
    baselineRecord,
    `缺少 ${record.name} 的 DOM 结构基线；确属结构调整时运行 UPDATE_VISUAL_BASELINE=1 更新`
  ).toBeDefined()
  expect(record, `[${record.name}] DOM 结构变化（确属结构调整请更新基线）`).toEqual(baselineRecord)
}

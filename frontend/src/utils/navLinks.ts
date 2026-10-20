/**
 * 导航死链检查（纯函数，供单测与 CI 复用）。
 *
 * 背景：`SettingsOverview.vue` 的快捷导航曾指向 `/system/i18n` 与 `/system/email`，
 * 两者都没有对应路由 —— 点击直接 404，而且现有门禁完全发现不了（该页面没有被
 * 任何单测执行）。
 *
 * 做法：把「导航配置里的 path 字面量」与「路由表里的 path 字面量」都当作文本抽取，
 * 逐个比对。两侧语法都是 `path: '/xxx'`，同一套正则即可。
 *
 * 局限（有意接受）：只做**字面量**比对，不处理运行时拼装的路径；带参路由
 * （`/system/:id`）不视为导航目标。对"防止再出现死链"这个目标足够。
 */
import fs from 'node:fs'
import path from 'node:path'

/** 参与死链检查的导航配置文件（相对 frontend/） */
export const NAV_SOURCES = [
  'src/views/system/SettingsOverview.vue',
  'src/views/system/console/SystemConsole.vue',
]

/** 路由表来源（相对 frontend/） */
export const ROUTER_SOURCE = 'src/router/index.ts'

/** 抽取 `path: '/xxx'` / `path: "/xxx"` 里的字面量 */
export function extractPathLiterals(source: string): string[] {
  const out: string[] = []
  const re = /path:\s*['"]([^'"]+)['"]/g
  let match = re.exec(source)
  while (match !== null) {
    out.push(match[1])
    match = re.exec(source)
  }
  return out
}

/** 去掉带参路由（含 `:`）与非绝对路径，得到可静态直达的路径集合 */
export function staticRoutes(paths: string[]): Set<string> {
  return new Set(paths.filter((p) => p.startsWith('/') && !p.includes(':')))
}

/** 找出死链：导航里出现、路由表里没有的路径（去重排序） */
export function findDeadLinks(navPaths: string[], routes: Set<string> | string[]): string[] {
  const routeSet = routes instanceof Set ? routes : new Set(routes)
  const dead = new Set<string>()
  for (const p of navPaths) {
    if (!p.startsWith('/')) continue // 外部链接/锚点不参与
    if (!routeSet.has(p)) dead.add(p)
  }
  return [...dead].sort()
}

function readSource(rel: string, root: string): string {
  return fs.readFileSync(path.join(root, rel), 'utf8')
}

/** 扫描真实仓库，返回死链清单与统计（root 默认取当前工作目录的上一级） */
export function checkRepo(root: string = process.cwd()): {
  dead: string[]
  navCount: number
  routeCount: number
} {
  const routes = staticRoutes(extractPathLiterals(readSource(ROUTER_SOURCE, root)))
  const navPaths = NAV_SOURCES.flatMap((rel) => extractPathLiterals(readSource(rel, root)))
  return {
    dead: findDeadLinks(navPaths, routes),
    navCount: navPaths.length,
    routeCount: routes.size,
  }
}

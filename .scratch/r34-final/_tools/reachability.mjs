#!/usr/bin/env node
/** 生产可达性分析：从 main.ts/App.vue 出发 BFS import 图，列出"生产不可达"的 src 文件
 * （仅用于最终冗余清理候选，删除前仍需人工确认测试依赖）。 */
import fs from 'node:fs'
import path from 'node:path'
const ROOT = process.cwd()
const SRC = path.join(ROOT, 'frontend/src')
function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) { if (!['node_modules', '__tests__', 'test'].includes(e.name)) walk(p, out) }
    else if (/\.(ts|vue)$/.test(e.name) && !e.name.endsWith('.d.ts')) out.push(p)
  }
  return out
}
const files = walk(SRC)
const fileSet = new Set(files)
function resolve(from, spec) {
  if (!spec.startsWith('@/') && !spec.startsWith('.')) return null
  const base = spec.startsWith('@/') ? path.join(SRC, spec.slice(2)) : path.resolve(path.dirname(from), spec)
  for (const c of [base, base + '.ts', base + '.vue', path.join(base, 'index.ts'), path.join(base, 'index.vue')]) {
    if (fileSet.has(c)) return c
  }
  return null
}
function importsOf(f) {
  const t = fs.readFileSync(f, 'utf-8')
  const specs = []
  for (const m of t.matchAll(/from\s*['"]([^'"]+)['"]/g)) specs.push(m[1])
  for (const m of t.matchAll(/import\s*\(\s*['"]([^'"]+)['"]\s*\)/g)) specs.push(m[1])
  return specs
}
const graph = new Map()
for (const f of files) graph.set(f, importsOf(f).map(s => resolve(f, s)).filter(Boolean))
const entries = [path.join(SRC, 'main.ts'), path.join(SRC, 'App.vue')].filter(f => fileSet.has(f))
const reach = new Set(entries)
const queue = [...entries]
const compRe = /<(?:([A-Z][\w]*)|([a-z][\w-]*))/g // 粗粒度模板标签
while (queue.length) {
  const cur = queue.shift()
  for (const nxt of graph.get(cur) || []) if (!reach.has(nxt)) { reach.add(nxt); queue.push(nxt) }
  // .vue 模板中使用的组件标签 -> 自动导入组件（src/components 下，directoryAsNamespace 命名）
  if (cur.endsWith('.vue')) {
    const t = fs.readFileSync(cur, 'utf-8')
    const tags = new Set()
    for (const m of t.matchAll(/<([A-Z][A-Za-z0-9]*)/g)) tags.add(m[1])
    for (const cf of files.filter(x => x.includes(path.sep + 'components' + path.sep) && x.endsWith('.vue'))) {
      if (reach.has(cf)) continue
      const relToComp = path.relative(path.join(SRC, 'components'), cf).replace(/\\/g, '/').replace(/\.vue$/, '')
      const parts = relToComp.split('/')
      const pascal = s => s.replace(/(^|[-_])(\w)/g, (_m, _p, c) => c.toUpperCase())
      const auto = pascal(parts[0]) + parts.slice(1).map(pascal).join('')
      if (tags.has(auto)) { reach.add(cf); queue.push(cf) }
    }
  }
}
// 额外：utils/index.ts 等 barrel 若无外部引用也属死代码（仅测试引用）
const unreachable = files.filter(f => !reach.has(f))
const rel = p => path.relative(ROOT, p).replace(/\\/g, '/')
fs.writeFileSync(path.join(ROOT, '.scratch/r34-final/reachability.json'), JSON.stringify(unreachable.map(rel), null, 1))
console.log('生产入口:', entries.map(rel).join(', '))
console.log('src 文件总数:', files.length, ' 可达:', reach.size, ' 不可达:', unreachable.length)
console.log('=== 生产不可达文件 ===')
for (const f of unreachable) console.log(rel(f))

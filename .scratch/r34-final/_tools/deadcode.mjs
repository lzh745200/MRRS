#!/usr/bin/env node
/** 前端死代码/冗余静态引用分析（R34 最终复检）
 * 输出：未引用视图、未引用组件、未被任何 src 文件引用的导出、仅在测试中被引用的导出等。
 * 用法：node .scratch/r34-final/_tools/deadcode.mjs
 */
import fs from 'node:fs'
import path from 'node:path'

const ROOT = process.cwd()
const SRC = path.join(ROOT, 'frontend/src')
const TESTS = path.join(ROOT, 'frontend/tests')
const ROUTER = path.join(SRC, 'router/index.ts')

function walk(dir, exts, out = []) {
  if (!fs.existsSync(dir)) return out
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) { if (!['node_modules', '__tests__', 'test'].includes(e.name)) walk(p, exts, out) }
    else if (exts.some(x => e.name.endsWith(x))) out.push(p)
  }
  return out
}

const srcFiles = walk(SRC, ['.ts', '.vue'])
const testFiles = walk(TESTS, ['.ts', '.vue']).concat(walk(SRC, ['.spec.ts']))

// import 解析：返回 [{ specifier, names: [] }]
const importRe = /import\s+(?:type\s+)?(?:([\w$]+)\s*,?\s*)?(?:\{([^}]*)\})?\s*(?:\*\s+as\s+[\w$]+\s*)?from\s*['"]([^'"]+)['"]/g
const bareImportRe = /import\s*['"]([^'"]+)['"]/g
const dynamicImportRe = /import\(\s*['"]([^'"]+)['"]\s*\)/g
const requireRe = /require\(\s*['"]([^'"]+)['"]\s*\)/g

function resolveSpecifier(fromFile, spec) {
  if (spec.startsWith('@/')) return path.join(SRC, spec.slice(2))
  if (spec.startsWith('.')) return path.resolve(path.dirname(fromFile), spec)
  return null // 第三方/样式
}

const edges = [] // {from, to, names}
function addEdge(from, spec, names) {
  if (/^(vue|vue-router|pinia|axios|element-plus|dayjs|@element-plus|echarts|sortablejs|dompurify|xlsx|@e965|driver\.js|@vueuse)/.test(spec)) return
  if (!spec.startsWith('@/') && !spec.startsWith('.')) return
  const base = resolveSpecifier(from, spec)
  if (!base) return
  // 候选：原样、+.ts、+.vue、+/index.ts、+/index.vue
  const candidates = [base, base + '.ts', base + '.vue', path.join(base, 'index.ts'), path.join(base, 'index.vue')]
  const hit = candidates.find(c => fs.existsSync(c) && fs.statSync(c).isFile())
  edges.push({ from, to: hit || base, spec, names })
}

function parseImports(file) {
  const text = fs.readFileSync(file, 'utf-8')
  let m
  const out = []
  while ((m = importRe.exec(text))) {
    const names = []
    if (m[1]) names.push('default')
    if (m[2]) for (const part of m[2].split(',')) {
      const n = part.trim().replace(/^type\s+/, '').split(/\s+as\s+/)[0].trim()
      if (n) names.push(n)
    }
    out.push({ spec: m[3], names })
  }
  while ((m = bareImportRe.exec(text))) out.push({ spec: m[1], names: [] })
  while ((m = dynamicImportRe.exec(text))) out.push({ spec: m[1], names: ['*dynamic'] })
  while ((m = requireRe.exec(text))) out.push({ spec: m[1], names: ['*require'] })
  return out
}

for (const f of srcFiles.concat(testFiles)) {
  for (const imp of parseImports(f)) {
    if (imp.spec.startsWith('.') || imp.spec.startsWith('@/')) addEdge(f, imp.spec, imp.names)
  }
}

// 被引用的文件 & 被引用的命名导出
const referencedFiles = new Map() // to -> Set(from)
const referencedNames = new Map() // to -> Set(name)
for (const e of edges) {
  if (!referencedFiles.has(e.to)) referencedFiles.set(e.to, new Set())
  referencedFiles.get(e.to).add(e.from)
  if (!referencedNames.has(e.to)) referencedNames.set(e.to, new Set())
  for (const n of e.names) referencedNames.get(e.to).add(n)
}

// 1) 视图/组件文件引用情况
const routerText = fs.readFileSync(ROUTER, 'utf-8')
const routerLazy = new Set()
for (const m of routerText.matchAll(/import\(\s*['"]([^'"]+)['"]\s*\)/g)) routerLazy.add(m[1])

const vueFiles = srcFiles.filter(f => f.endsWith('.vue'))
const viewFiles = vueFiles.filter(f => f.includes(path.sep + 'views' + path.sep))
const compFiles = vueFiles.filter(f => f.includes(path.sep + 'components' + path.sep))

function rel(p) { return path.relative(ROOT, p).replace(/\\/g, '/') }
function isReferencedByApp(f) {
  const bySrc = [...(referencedFiles.get(f) || [])].filter(x => x.startsWith(SRC))
  return bySrc
}
// 组件自动导入（unplugin-vue-components dirs=['src/components'], directoryAsNamespace=true）
function autoImportName(f) {
  const relToComp = path.relative(path.join(SRC, 'components'), f).replace(/\\/g, '/').replace(/\.vue$/, '')
  const parts = relToComp.split('/')
  const pascal = s => s.replace(/(^|[-_])(\w)/g, (_m, _p, c) => c.toUpperCase()).replace(/\./g, '')
  const first = pascal(parts[0])
  const rest = parts.slice(1).map(pascal).join('')
  return first + rest
}
function templateTagUsage(name) {
  const kebab = name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase()
  const hits = []
  for (const f of srcFiles) {
    if (!f.endsWith('.vue')) continue
    const t = fs.readFileSync(f, 'utf-8')
    if (t.includes('<' + name) || t.includes('<' + kebab)) hits.push(f)
  }
  return hits
}

const orphanViews = []
const orphanComps = []
for (const f of viewFiles) {
  const refs = isReferencedByApp(f)
  if (refs.length === 0) orphanViews.push(f)
}
for (const f of compFiles) {
  const refs = isReferencedByApp(f)
  const auto = autoImportName(f)
  const tagRefs = templateTagUsage(auto)
  if (refs.length === 0 && tagRefs.length === 0) orphanComps.push({ file: f, autoName: auto })
}

// 2) 未被任何 src 文件引用的导出（可能只被测试引用）
const exportRe = /export\s+(?:default\s+)?(?:async\s+)?(?:const|let|var|function|class|enum|interface|type)\s+([A-Za-z_$][\w$]*)/g
const exportsByFile = new Map()
for (const f of srcFiles.filter(x => x.endsWith('.ts'))) {
  const text = fs.readFileSync(f, 'utf-8')
  const names = []
  let m
  while ((m = exportRe.exec(text))) names.push(m[1])
  // export { a, b as c }
  for (const mm of text.matchAll(/export\s*\{([^}]*)\}/g)) {
    for (const part of mm[1].split(',')) {
      const n = part.trim().split(/\s+as\s+/).pop().trim()
      if (n) names.push(n)
    }
  }
  if (names.length) exportsByFile.set(f, [...new Set(names)])
}
const srcOnlyRefs = new Map() // name -> count of src refs (excluding own file)
const testRefs = new Map()
for (const e of edges) {
  const isTest = e.from.startsWith(TESTS) || e.from.endsWith('.spec.ts')
  for (const n of e.names) {
    if (isTest) testRefs.set(n, (testRefs.get(n) || 0) + 1)
    else srcOnlyRefs.set(n, (srcOnlyRefs.get(n) || 0) + 1)
  }
}
// 同名跨文件会误报；用「文件名 + name」粒度近似：统计全仓 import 名称即可（名字唯一性足够）
const unusedExports = []      // src 与 tests 都未引用
const testOnlyExports = []    // 仅 tests 引用（生产死代码）
for (const [f, names] of exportsByFile) {
  for (const n of names) {
    const inSrc = (srcOnlyRefs.get(n) || 0) > 0
    const inTest = (testRefs.get(n) || 0) > 0
    if (!inSrc && !inTest) unusedExports.push({ file: f, name: n })
    else if (!inSrc && inTest) testOnlyExports.push({ file: f, name: n })
  }
}

// 3) 死导出（index.ts 汇总再导出：检查 index 中的 re-export 是否被使用）
// 4) 报告
const out = { orphanViews, orphanComps, unusedExports, testOnlyExports }
fs.writeFileSync(path.join(ROOT, '.scratch/r34-final/deadcode.json'), JSON.stringify(out, null, 1))

console.log('=== 1) 未被 src 任何文件引用的 views（' + orphanViews.length + '）===')
for (const f of orphanViews) {
  const testHit = [...(referencedFiles.get(f) || [])].filter(x => x.startsWith(TESTS) || x.endsWith('.spec.ts'))
  console.log(rel(f) + (testHit.length ? '   [仅测试引用: ' + testHit.map(rel).join(',') + ']' : '   [无测试引用]'))
}
console.log('\n=== 2) 未被引用且模板无标签使用的 components（' + orphanComps.length + '）===')
for (const c of orphanComps) console.log(rel(c.file) + '  autoName=' + c.autoName)
console.log('\n=== 3) 完全未被引用的导出（src+tests 均无）（' + unusedExports.length + '）===')
for (const e of unusedExports) console.log(rel(e.file) + ' :: ' + e.name)
console.log('\n=== 4) 仅被测试引用的导出（生产死代码，' + testOnlyExports.length + '）===')
for (const e of testOnlyExports) console.log(rel(e.file) + ' :: ' + e.name)

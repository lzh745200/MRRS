const cov = require('./coverage/coverage-final.json')
const targets = [
  'components/funds/YearlyComparisonChart.vue',
  'views/funds/EnhancedList.vue',
  'views/organization/Detail.vue',
  'views/policies/Category.vue',
  'views/projects/Import.vue',
]
for (const t of targets) {
  const key = Object.keys(cov).find((k) => k.split('\\').join('/').endsWith(t))
  if (!key) {
    console.log('NOT FOUND:', t)
    continue
  }
  const f = cov[key]
  const uncovS = Object.entries(f.statementMap)
    .filter(([id]) => f.s[id] === 0)
    .map(([id, m]) => m.start.line + '-' + m.end.line)
  const uncovB = Object.entries(f.branchMap)
    .filter(([id]) => f.b[id].some((c) => c === 0))
    .map(([id, m]) => ({
      id,
      line: m.loc && m.loc.start.line,
      col: m.loc && m.loc.start.column,
      end: m.loc && m.loc.end.line + ':' + (m.loc && m.loc.end.column),
      counts: f.b[id],
      type: m.type,
    }))
  const uncovF = Object.entries(f.fnMap)
    .filter(([id]) => f.f[id] === 0)
    .map(([id, m]) => (m.name || '(anon)') + '@' + (m.decl ? m.decl.start.line : m.loc.start.line))
  console.log('=== ' + t + ' ===')
  console.log('uncov stmts:', JSON.stringify(uncovS))
  console.log('uncov funcs:', JSON.stringify(uncovF))
  console.log('uncov branches:', JSON.stringify(uncovB))
}

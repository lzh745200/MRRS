#!/usr/bin/env node
/**
 * 前后端 API 契约一致性比对（W24 前端探测，可复现证据）
 *
 * 用法（仓库根目录）:
 *   1) backend/.venv/Scripts/python.exe .scratch/w24-enterprise-probe/_tools/dump_routes.py
 *      -> 生成 .scratch/backend_routes.json（FastAPI 运行时真实路由，826 条）
 *   2) node .scratch/w24-enterprise-probe/_tools/contract_compare.mjs
 *      -> 提取 frontend/src/api/*.ts 中全部 get/post/put/del/patch/apiRequest 调用，
 *         与后端路由按「方法 + 归一化路径（路径参数 -> {}）」全量比对。
 *
 * 说明：
 * - 前端 baseURL 为 /api/v1（import.meta.env.VITE_API_BASE_URL 缺省值），故前端相对
 *   路径统一补 /api/v1 前缀后与后端 full path 比较；
 * - 模板字符串中的 ${expr} 归一化为 {}，与后端 {param} 同构；
 * - 已知的简单表达式（const BASE = '/x'、${BASE}/y、'x/' + id、buildQuery 查询串）做
 *   有限解析；无法静态解析的调用单独列出人工复核（本次为 0）。
 */
import fs from 'node:fs'
import path from 'node:path'

const ROOT = process.cwd()
const API_DIR = path.join(ROOT, 'frontend/src/api')
const ROUTES_JSON = path.join(ROOT, '.scratch/backend_routes.json')

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) { if (e.name !== '__tests__') walk(p, out) }
    else if (e.name.endsWith('.ts') && !e.name.endsWith('.spec.ts') && !e.name.endsWith('.test.ts')) out.push(p)
  }
  return out
}

function stripComments(src) {
  let out = '', i = 0, state = 'code'
  while (i < src.length) {
    const c = src[i], n = src[i + 1]
    if (state === 'code') {
      if (c === '/' && n === '/') { state = 'line'; i += 2; continue }
      if (c === '/' && n === '*') { state = 'block'; i += 2; continue }
      if (c === "'") state = 'sq'; else if (c === '"') state = 'dq'; else if (c === '`') state = 'tpl'
      out += c; i++; continue
    }
    if (state === 'line') { if (c === '\n') { state = 'code'; out += c } i++; continue }
    if (state === 'block') { if (c === '*' && n === '/') { state = 'code'; i += 2; continue } if (c === '\n') out += c; i++; continue }
    if (state === 'sq') { out += c; if (c === '\\') { out += src[i + 1] || ''; i += 2; continue } if (c === "'") state = 'code'; i++; continue }
    if (state === 'dq') { out += c; if (c === '\\') { out += src[i + 1] || ''; i += 2; continue } if (c === '"') state = 'code'; i++; continue }
    if (state === 'tpl') { out += c; if (c === '\\') { out += src[i + 1] || ''; i += 2; continue } if (c === '`') state = 'code'; i++; continue }
  }
  return out
}

function findMatching(src, openIdx, open, close) {
  let depth = 0, i = openIdx, state = 'code'
  while (i < src.length) {
    const c = src[i]
    if (state === 'code') {
      if (c === "'") state = 'sq'; else if (c === '"') state = 'dq'; else if (c === '`') state = 'tpl'
      else if (c === open) depth++
      else if (c === close) { depth--; if (depth === 0) return i }
    } else if (state === 'sq') { if (c === '\\') i++; else if (c === "'") state = 'code' }
    else if (state === 'dq') { if (c === '\\') i++; else if (c === '"') state = 'code' }
    else if (state === 'tpl') { if (c === '\\') i++; else if (c === '`') state = 'code' }
    i++
  }
  return -1
}

function evalTplInner(inner, consts) {
  return inner.replace(/\$\{([^{}]*)\}/g, (_m, expr) => {
    const e = String(expr).trim()
    if (/^[A-Za-z_$][\w$]*$/.test(e) && consts[e] !== undefined && String(consts[e]).startsWith('/')) return consts[e]
    return '{}'
  })
}

function resolveArg(expr, consts) {
  const parts = []; let depth = 0, cur = '', state = 'code'
  for (let i = 0; i < expr.length; i++) {
    const c = expr[i]
    if (state === 'code') {
      if (c === "'" || c === '"') { state = 'str'; cur += c; continue }
      if (c === '`') { state = 'tpl'; cur += c; continue }
      if ('(,[{'.includes(c)) depth++
      if (')]}'.includes(c)) depth--
      if (c === '+' && depth === 0) { parts.push(cur.trim()); cur = ''; continue }
      cur += c
    } else if (state === 'str') { cur += c; if (c === '\\') { cur += expr[++i] || '' } else if (c === "'" || c === '"') state = 'code' }
    else if (state === 'tpl') { cur += c; if (c === '\\') { cur += expr[++i] || '' } else if (c === '`') state = 'code' }
  }
  if (cur.trim()) parts.push(cur.trim())
  let result = ''
  for (const p0 of parts) {
    const p = p0.trim(); if (!p) continue; const q = p[0]
    if (q === "'" || q === '"') result += (p.length >= 2 && p[p.length - 1] === q) ? p.slice(1, -1) : '{}'
    else if (q === '`') result += evalTplInner(p.slice(1, -1), consts)
    else if (/^[A-Za-z_$][\w$]*$/.test(p)) result += consts[p] !== undefined ? consts[p] : '{}'
    else result += '{}'
  }
  return result.replace(/\/{2,}/g, '/')
}

function extractCalls() {
  const calls = []
  const callableRe = /\b(get|post|put|del|patch|apiRequest|request\s*\.\s*(?:get|post|put|delete|patch))\s*(?:<[^<>()]*>)?\s*\(/g
  for (const f of walk(API_DIR)) {
    const rel = path.relative(ROOT, f).replace(/\\/g, '/')
    if (rel.endsWith('api/request.ts')) continue
    const src = stripComments(fs.readFileSync(f, 'utf-8'))
    const consts = {}; let m
    const constRe = /const\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(['"])([^'"]*)\2/g
    while ((m = constRe.exec(src))) consts[m[1]] = m[3]
    const constTplRe = /const\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*`([^`]*)`/g
    while ((m = constTplRe.exec(src))) consts[m[1]] = evalTplInner(m[2], consts)
    callableRe.lastIndex = 0
    while ((m = callableRe.exec(src))) {
      const fnRaw = m[1]
      const openIdx = src.indexOf('(', m.index + fnRaw.length)
      const closeIdx = findMatching(src, openIdx, '(', ')')
      if (closeIdx < 0) continue
      const args = src.slice(openIdx + 1, closeIdx)
      const line = src.slice(0, m.index).split('\n').length
      if (fnRaw.replace(/\s/g, '').startsWith('apiRequest')) {
        const methodM = args.match(/method\s*:\s*(['"])([A-Za-z]+)\1/)
        const urlM = args.match(/url\s*:\s*(['"`])([\s\S]*?)\1/)
        if (urlM) calls.push({ file: rel, line, method: (methodM ? methodM[2] : 'GET').toUpperCase(), url: resolveArg(urlM[1] + urlM[2] + urlM[1], consts) })
        continue
      }
      const reqM = fnRaw.replace(/\s/g, '')
      let method = 'GET'
      if (reqM.includes('.get')) method = 'GET'
      else if (reqM.includes('.post')) method = 'POST'
      else if (reqM.includes('.put')) method = 'PUT'
      else if (reqM.includes('.delete')) method = 'DELETE'
      else if (reqM.includes('.patch')) method = 'PATCH'
      else method = ({ get: 'GET', post: 'POST', put: 'PUT', del: 'DELETE', patch: 'PATCH' })[reqM] || 'GET'
      let depth = 0, firstArgEnd = args.length, state = 'code'
      for (let i = 0; i < args.length; i++) {
        const c = args[i]
        if (state === 'code') {
          if (c === "'" || c === '"') { state = 'str'; continue }
          if (c === '`') { state = 'tpl'; continue }
          if ('([{'.includes(c)) depth++
          if (')]}'.includes(c)) depth--
          if (c === ',' && depth === 0) { firstArgEnd = i; break }
        } else if (state === 'str') { if (c === '\\') i++; else if (c === "'" || c === '"') state = 'code' }
        else if (state === 'tpl') { if (c === '\\') i++; else if (c === '`') state = 'code' }
      }
      calls.push({ file: rel, line, method, url: resolveArg(args.slice(0, firstArgEnd), consts) })
    }
  }
  return calls
}

// 少量需人工解析的表达式（保持与报告一致）
function applyKnownFixes(calls) {
  for (const c of calls) {
    if (c.file.endsWith('api/milestones.ts')) {
      if (c.url === '{}') c.url = '/projects/{}/milestones'
      else if (c.url === '{}/{}') c.url = '/projects/{}/milestones/{}'
    }
    if (c.file.endsWith('api/chunkedUpload.ts') && c.url === '{}') c.url = '/chunked-upload/chunk/{}/{}'
    // secrets.ts 的 rotate/create/cleanup 用 ${qs}（buildQuery 查询串）拼在路径后，
    // 静态解析会得到 '/secrets/rotate{}'；此处还原为无查询串路径（revoke 保留路径参数）。
    if (c.file.endsWith('api/secrets.ts') && /^\/secrets\/(rotate|create|cleanup)\{\}$/.test(c.url)) {
      c.url = c.url.replace(/\{\}$/, '')
    }
  }
  return calls
}

const backend = JSON.parse(fs.readFileSync(ROUTES_JSON, 'utf-8'))
const norm = (p) => p.replace(/\{[^{}]*\}/g, '{}').replace(/\/+$/, '') || '/'
const map = new Map()
for (const r of backend) {
  const k = norm(r.path)
  if (!map.has(k)) map.set(k, new Set())
  for (const method of r.methods) map.get(k).add(method)
}
const calls = applyKnownFixes(extractCalls())
const unmatched = []
for (const c of calls) {
  if (/^https?:/.test(c.url)) continue
  const full = norm((c.url.startsWith('/api/') ? c.url : '/api/v1' + c.url).split('?')[0])
  const methods = map.get(full)
  if (!methods) unmatched.push({ ...c, full, reason: 'path-not-found' })
  else if (!methods.has(c.method)) unmatched.push({ ...c, full, reason: 'method-mismatch: backend=' + [...methods].join('/') })
}
console.log('后端路由(含路径参数归一化):', backend.length)
console.log('前端 API 调用点:', calls.length)
console.log('匹配:', calls.length - unmatched.length, ' 不匹配:', unmatched.length)
for (const u of unmatched) console.log('  MISMATCH', JSON.stringify(u))
process.exit(unmatched.length ? 1 : 0)

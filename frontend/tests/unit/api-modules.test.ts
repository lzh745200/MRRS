/**
 * API 模块结构完整性验证
 * 确保所有 API 模块可正常导入且导出结构正确
 */
import { describe, it, expect } from 'vitest'

const API_MODULES = [
  { name: 'funds', path: '@/api/funds' },
  { name: 'schools', path: '@/api/schools' },
  { name: 'audit', path: '@/api/audit' },
  { name: 'approval', path: '@/api/approval' },
  { name: 'backup', path: '@/api/backup' },
  { name: 'export', path: '@/api/export' },
  { name: 'dataPackage', path: '@/api/dataPackage' },
  { name: 'map', path: '@/api/map' },
  { name: 'fundLifecycle', path: '@/api/fundLifecycle' },
  { name: 'policy', path: '@/api/policy' },
  { name: 'ruralWork', path: '@/api/ruralWork' },
  { name: 'todos', path: '@/api/todos' },
  { name: 'organization', path: '@/api/organization' },
  { name: 'offlineMap', path: '@/api/offlineMap' },
  { name: 'organizationPassCode', path: '@/api/organizationPassCode' },
  { name: 'machineCode', path: '@/api/machineCode' },
  { name: 'dataSync', path: '@/api/dataSync' },
  { name: 'env', path: '@/api/env' },
  { name: 'i18n', path: '@/api/i18n' },
  { name: 'twoFactor', path: '@/api/twoFactor' },
  { name: 'supportedVillage', path: '@/api/supportedVillage' },
  { name: 'dashboard', path: '@/api/dashboard' },
  { name: 'analytics', path: '@/api/analytics' },
  { name: 'batchOperations', path: '@/api/batchOperations' },
  { name: 'chunkedUpload', path: '@/api/chunkedUpload' },
  { name: 'dataTier', path: '@/api/dataTier' },
  { name: 'effectiveness', path: '@/api/effectiveness' },
  { name: 'errorReport', path: '@/api/errorReport' },
  { name: 'fundStatistics', path: '@/api/fundStatistics' },
  { name: 'help', path: '@/api/help' },
  { name: 'import', path: '@/api/import' },
  { name: 'message', path: '@/api/message' },
  { name: 'secrets', path: '@/api/secrets' },
  { name: 'sentiment', path: '@/api/sentiment' },
  { name: 'systemMonitor', path: '@/api/systemMonitor' },
  { name: 'tasks', path: '@/api/tasks' },
  { name: 'updateLogs', path: '@/api/updateLogs' },
  { name: 'userManagement', path: '@/api/userManagement' },
  { name: 'validationRules', path: '@/api/validationRules' },
  { name: 'zeroTrust', path: '@/api/zeroTrust' },
  { name: 'ai', path: '@/api/ai' },
]

describe('API module structural integrity', () => {
  for (const mod of API_MODULES) {
    it(`${mod.name} 模块可导入且导出非空对象`, async () => {
      const m = await import(mod.path)
      const keys = Object.keys(m)
      // 必须至少有一个非 default 导出
      const hasNamedExport = keys.some((k) => k !== 'default')
      expect(hasNamedExport).toBe(true)
    })
  }
})

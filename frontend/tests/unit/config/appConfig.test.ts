import { describe, it, expect } from 'vitest'
import { appConfig } from '@/config/appConfig'

describe('config/appConfig', () => {
  it('has appName', () => expect(appConfig.appName).toBe('帮扶管理信息系统'))
  it('has version', () => expect(appConfig.version).toBe('1.10.0'))
  it('has apiBaseURL defaulting to /api/v1', () => {
    expect(appConfig.apiBaseURL).toBe('/api/v1')
  })
})

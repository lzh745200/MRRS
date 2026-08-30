import { describe, it, expect } from 'vitest'
import { SYSTEM_VERSION, COPYRIGHT_OWNER, SYSTEM_NAME } from '@/config/constants'

describe('config/constants', () => {
  it('SYSTEM_VERSION is a semver string', () => expect(SYSTEM_VERSION).toMatch(/^\d+\.\d+\.\d+$/))
  it('COPYRIGHT_OWNER', () => expect(COPYRIGHT_OWNER).toBe('梁正辉'))
  it('SYSTEM_NAME', () => expect(SYSTEM_NAME).toBe('帮扶管理信息系统'))
})

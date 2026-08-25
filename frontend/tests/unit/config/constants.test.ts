import { describe, it, expect } from 'vitest'
import { SYSTEM_VERSION, COPYRIGHT_OWNER, SYSTEM_NAME } from '@/config/constants'

describe('config/constants', () => {
  it('SYSTEM_VERSION is 1.10.0', () => expect(SYSTEM_VERSION).toBe('1.10.0'))
  it('COPYRIGHT_OWNER', () => expect(COPYRIGHT_OWNER).toBe('梁正辉'))
  it('SYSTEM_NAME', () => expect(SYSTEM_NAME).toBe('帮扶管理信息系统'))
})

import { describe, it, expect, vi, beforeEach } from 'vitest'

const canAccessMenu = vi.fn()

vi.mock('@/stores/menu', () => ({
  useMenuStore: () => ({ canAccessMenu }),
}))

import { useMenuPermission } from '@/composables/useMenuPermission'

describe('composables/useMenuPermission', () => {
  beforeEach(() => {
    canAccessMenu.mockReset()
  })

  it('delegates to menuStore.canAccessMenu', () => {
    canAccessMenu.mockReturnValue(true)
    const p = useMenuPermission()
    expect(p.hasPermission('system')).toBe(true)
    expect(canAccessMenu).toHaveBeenCalledWith('system')
  })

  it('returns false when menu denies access', () => {
    canAccessMenu.mockReturnValue(false)
    const p = useMenuPermission()
    expect(p.hasPermission('system')).toBe(false)
  })

  it('empty key short-circuits to true', () => {
    const p = useMenuPermission()
    expect(p.hasPermission('')).toBe(true)
    expect(canAccessMenu).not.toHaveBeenCalled()
  })
})

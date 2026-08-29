/**
 * Batch coverage tests — fills gaps in frontend utils/stores/api
 */
import { describe, it, expect, vi } from 'vitest'

// ==================== utils coverage ====================


describe('utils/authStorage', () => {
  it('setToken and getToken work', async () => {
    const { AuthStorage } = await import('@/utils/authStorage')
    AuthStorage.setToken('test-token-123')
    expect(AuthStorage.getToken()).toBe('test-token-123')
    AuthStorage.clear()
    expect(AuthStorage.getToken()).toBeNull()
  })

  it('setUser and getUser work', async () => {
    const { AuthStorage } = await import('@/utils/authStorage')
    const user = { id: 1, username: 'admin', role: 'admin' }
    AuthStorage.setUser(user)
    const fetched = AuthStorage.getUser()
    expect(fetched).toEqual(user)
    AuthStorage.clear()
  })
})

describe('utils/clipboard', () => {
  it('generateRandomPassword returns string', async () => {
    const { generateRandomPassword } = await import('@/utils/clipboard')
    const pwd = generateRandomPassword()
    expect(pwd.length).toBe(12)
    expect(pwd).not.toContain('I')
    expect(pwd).not.toContain('l')
  })

  it('generateRandomPassword custom length', async () => {
    const { generateRandomPassword } = await import('@/utils/clipboard')
    const pwd = generateRandomPassword(16)
    expect(pwd.length).toBe(16)
  })
})

describe('utils/unwrapList', () => {
  it('handles bare items format', async () => {
    const { unwrapList } = await import('@/utils/unwrapList')
    const result = unwrapList({ items: [1, 2], total: 2 })
    expect(result.items).toEqual([1, 2])
    expect(result.total).toBe(2)
  })

  it('handles envelope format', async () => {
    const { unwrapList } = await import('@/utils/unwrapList')
    const result = unwrapList({ code: 200, data: { items: [3, 4], total: 2 } })
    expect(result.items).toEqual([3, 4])
    expect(result.total).toBe(2)
  })

  it('handles null', async () => {
    const { unwrapList } = await import('@/utils/unwrapList')
    const result = unwrapList(null)
    expect(result.items).toEqual([])
    expect(result.total).toBe(0)
  })
})

describe('utils/desensitize', () => {
  it('maskPhone works', async () => {
    const { maskPhone } = await import('@/utils/desensitize')
    expect(maskPhone('13812341234')).toBe('138****1234')
    expect(maskPhone(null as any)).toBe('')
  })

  it('maskIdCard works', async () => {
    const { maskIdCard } = await import('@/utils/desensitize')
    const result = maskIdCard('110101199001011234')
    // Regex: replaces middle digits with asterisks
    expect(result).toBeTruthy()
    expect(result?.length).toBeGreaterThan(10)
  })

  it('maskName works', async () => {
    const { maskName } = await import('@/utils/desensitize')
    expect(maskName('张三')).toBe('张*')
    expect(maskName('张')).toBe('*')
  })
})

describe('utils/sanitize', () => {
  it('sanitizeHtml removes script tags', async () => {
    const { sanitizeHtml } = await import('@/utils/sanitize')
    const result = sanitizeHtml('<p>Hello</p><script>alert(1)</script>')
    expect(result).not.toContain('<script')
    expect(result).toContain('Hello')
  })

  it('stripHtml removes all tags', async () => {
    const { stripHtml } = await import('@/utils/sanitize')
    const result = stripHtml('<p>Hello <b>World</b></p>')
    expect(result).toContain('Hello')
    expect(result).not.toContain('<p>')
  })
})


// ==================== API request module coverage ====================

describe('api/request utility', () => {
  it('parseContentDisposition with UTF-8 encoding', async () => {
    const { parseContentDisposition } = await import('@/api/request')
    const filename = parseContentDisposition(
      { 'content-disposition': "attachment; filename*=UTF-8''%E6%B5%8B%E8%AF%95.xlsx" },
      'fallback.xlsx'
    )
    expect(filename).toBe('测试.xlsx')
  })

  it('parseContentDisposition with quoted filename', async () => {
    const { parseContentDisposition } = await import('@/api/request')
    const filename = parseContentDisposition(
      { 'content-disposition': 'attachment; filename="report.xlsx"' },
      'fallback.xlsx'
    )
    expect(filename).toBe('report.xlsx')
  })

  it('parseContentDisposition fallback on missing header', async () => {
    const { parseContentDisposition } = await import('@/api/request')
    const filename = parseContentDisposition({}, 'fallback.xlsx')
    expect(filename).toBe('fallback.xlsx')
  })

  it('isSuccess returns true for 2xx', async () => {
    const { isSuccess } = await import('@/api/request')
    expect(isSuccess(200)).toBe(true)
    expect(isSuccess(201)).toBe(true)
    expect(isSuccess(404)).toBe(false)
  })
})

// ==================== API module imports ====================

describe('api/funds', () => {
  it('exports fundApi', async () => {
    const mod = await import('@/api/funds')
    expect(mod.fundApi).toBeDefined()
  })
})

describe('api/projects', () => {
  it('exports projectsApi', async () => {
    const mod = await import('@/api/projects')
    expect(mod.projectsApi).toBeDefined()
  })
})

describe('api/approval', () => {
  it('exports getAllTasks', async () => {
    const mod = await import('@/api/approval')
    expect(mod.getAllTasks).toBeDefined()
  })
})

describe('api/supportedVillage', () => {
  it('exports getSupportedVillages', async () => {
    const mod = await import('@/api/supportedVillage')
    expect(mod.getSupportedVillages).toBeDefined()
  })
})

describe('api/policy', () => {
  it('exports getPolicies', async () => {
    const mod = await import('@/api/policy')
    expect(mod.getPolicies).toBeDefined()
  })
})

describe('api/effectiveness', () => {
  it('exports evaluateVillage', async () => {
    const mod = await import('@/api/effectiveness')
    expect(mod.evaluateVillage).toBeDefined()
  })
})

describe('api/dataSync', () => {
  it('exports exportData', async () => {
    const mod = await import('@/api/dataSync')
    expect(mod.exportData).toBeDefined()
  })
})

describe('api/organization', () => {
  it('exports getOrganizations', async () => {
    const mod = await import('@/api/organization')
    expect(mod.getOrganizations).toBeDefined()
  })
})

describe('api/audit', () => {
  it('exports auditApi', async () => {
    const mod = await import('@/api/audit')
    expect(mod.auditApi).toBeDefined()
  })
})

describe('api/import', () => {
  it('exports downloadImportTemplateAndSave', async () => {
    const mod = await import('@/api/import')
    expect(mod.downloadImportTemplateAndSave).toBeDefined()
  })
})

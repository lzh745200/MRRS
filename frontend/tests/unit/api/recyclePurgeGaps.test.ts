/**
 * 回收站 / 清空类 API 缺口补测（任务#19）
 *
 * 覆盖此前 0 调用的导出：
 *  - api/supportedVillage.ts：restoreSupportedVillage / previewPurgeSupportedVillage /
 *    purgeSupportedVillage / resolveSectionApiKey / deleteYearlySection
 *  - api/projects.ts：projectsApi.{restore,purgePreview,purge} 与具名导出
 *    restoreProject / previewPurgeProject / purgeProject
 *  - api/message.ts：clearReadMessages
 *
 * Mock 约定（AGENTS.md「Test-Writing Conventions」#1~#4）：
 *  - 三个源模块 + 其 import 链上的 helpers/blobDownload.ts 共用到 `@/api/request` 的
 *    default / get / post / put / del / apiRequest / parseContentDisposition / downloadBlob，
 *    mock 必须全部提供，否则报 No "X" export is defined on the mock。
 *  - get/post 的 helper 返回「已解包的 body」，故 mockResolvedValue(body)。
 *  - `get(url, params)` 第二参直接是 params；用 rest 区分 get(url) 与 get(url, undefined)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { mockGet, mockPost, mockPut, mockDel, mockApiRequest, mockDownloadBlob } = vi.hoisted(
  () => ({
    mockGet: vi.fn(),
    mockPost: vi.fn(),
    mockPut: vi.fn(),
    mockDel: vi.fn(),
    mockApiRequest: vi.fn(),
    mockDownloadBlob: vi.fn(),
  })
)

vi.mock('@/api/request', () => ({
  // rest 参数：区分 fn(url) 与 fn(url, params)，避免断言里被迫写 undefined
  get: (url: string, ...rest: unknown[]) =>
    rest.length > 0 ? mockGet(url, rest[0]) : mockGet(url),
  post: (url: string, ...rest: unknown[]) =>
    rest.length > 0 ? mockPost(url, rest[0]) : mockPost(url),
  put: (url: string, ...rest: unknown[]) =>
    rest.length > 0 ? mockPut(url, rest[0]) : mockPut(url),
  del: (url: string) => mockDel(url),
  apiRequest: (...args: unknown[]) => mockApiRequest(...args),
  // blobDownload.ts 在 import 链上，缺这两个导出会让 vi.mock 直接报错
  parseContentDisposition: (_headers: unknown, fallback = 'download') => fallback,
  downloadBlob: (...args: unknown[]) => mockDownloadBlob(...args),
  default: {
    get: (url: string, config?: unknown) => mockGet(url, config),
    post: (url: string, data?: unknown, config?: unknown) => mockPost(url, data, config),
  },
}))

import {
  restoreSupportedVillage,
  previewPurgeSupportedVillage,
  purgeSupportedVillage,
  resolveSectionApiKey,
  deleteYearlySection,
  SECTION_KEY_OVERRIDE,
} from '@/api/supportedVillage'
import {
  projectsApi,
  restoreProject,
  previewPurgeProject,
  purgeProject,
} from '@/api/projects'
import { clearReadMessages } from '@/api/message'

describe('api/supportedVillage —— 回收站（恢复 / 彻底删除）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPost.mockResolvedValue({ success: true })
    mockGet.mockResolvedValue({ id: 7 })
  })

  it('restoreSupportedVillage POST /supported-villages/{id}/restore，body 为空对象', async () => {
    const res = await restoreSupportedVillage(7)
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/7/restore', {})
    expect(res).toEqual({ success: true })
  })

  it('previewPurgeSupportedVillage GET /supported-villages/{id}/purge/preview，不带 params', async () => {
    await previewPurgeSupportedVillage(7)
    // 第二参省略：确认没有多传 params（get(url) 而非 get(url, undefined)）
    expect(mockGet).toHaveBeenCalledWith('/supported-villages/7/purge/preview')
    expect(mockGet.mock.calls[0]).toHaveLength(1)
  })

  it('purgeSupportedVillage 透传确认密码', async () => {
    await purgeSupportedVillage(7, 's3cret')
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/7/purge', {
      confirm_password: 's3cret',
    })
  })

  it('purgeSupportedVillage 省略密码时回退为空串（后端据此拒绝高危操作）', async () => {
    await purgeSupportedVillage(7)
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/7/purge', {
      confirm_password: '',
    })
  })

  it('purgeSupportedVillage 显式传 undefined 同样回退为空串', async () => {
    await purgeSupportedVillage(7, undefined)
    expect(mockPost).toHaveBeenCalledWith('/supported-villages/7/purge', {
      confirm_password: '',
    })
  })
})

describe('api/supportedVillage —— section key 映射（单一映射源）', () => {
  it('SECTION_KEY_OVERRIDE 只登记两个连字符板块', () => {
    expect(SECTION_KEY_OVERRIDE).toEqual({
      force_investment: 'force-investment',
      party_building: 'party-building',
    })
  })

  it('下划线内部 key 映射为后端连字符 key', () => {
    expect(resolveSectionApiKey('force_investment')).toBe('force-investment')
    expect(resolveSectionApiKey('party_building')).toBe('party-building')
  })

  it('单单词 key 两侧一致，原样返回', () => {
    for (const k of ['population', 'income', 'industry', 'education', 'medical']) {
      expect(resolveSectionApiKey(k)).toBe(k)
    }
  })

  it('未知 key 原样返回（不抛错，交由后端校验）', () => {
    expect(resolveSectionApiKey('not_a_section')).toBe('not_a_section')
  })

  it('幂等：对已映射的连字符 key 再调一次不变', () => {
    const once = resolveSectionApiKey('force_investment')
    expect(resolveSectionApiKey(once)).toBe('force-investment')
  })
})

describe('api/supportedVillage —— deleteYearlySection 走映射', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockDel.mockResolvedValue({ success: true })
  })

  it('force_investment 映射为 force-investment 后再拼 URL（历史缺陷：漏映射恒 400）', async () => {
    await deleteYearlySection(1, 2024, 'force_investment')
    expect(mockDel).toHaveBeenCalledWith('/supported-villages/1/yearly/2024/force-investment')
  })

  it('party_building 同样映射', async () => {
    await deleteYearlySection(2, 2025, 'party_building')
    expect(mockDel).toHaveBeenCalledWith('/supported-villages/2/yearly/2025/party-building')
  })

  it('单单词 section 不改变 URL', async () => {
    await deleteYearlySection(3, 2026, 'income')
    expect(mockDel).toHaveBeenCalledWith('/supported-villages/3/yearly/2026/income')
  })
})

describe('api/projects —— projectsApi 对象上的回收站方法', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPost.mockResolvedValue({ success: true })
    mockGet.mockResolvedValue({ id: 3 })
  })

  it('projectsApi.restore POST /projects/{id}/restore', async () => {
    await projectsApi.restore(3)
    expect(mockPost).toHaveBeenCalledWith('/projects/3/restore', {})
  })

  it('projectsApi.purgePreview GET /projects/{id}/purge/preview', async () => {
    await projectsApi.purgePreview(3)
    expect(mockGet).toHaveBeenCalledWith('/projects/3/purge/preview')
    expect(mockGet.mock.calls[0]).toHaveLength(1)
  })

  it('projectsApi.purge 携带确认密码', async () => {
    await projectsApi.purge(3, 'pw')
    expect(mockPost).toHaveBeenCalledWith('/projects/3/purge', { confirm_password: 'pw' })
  })

  it('projectsApi.purge 省略密码回退空串', async () => {
    await projectsApi.purge(3)
    expect(mockPost).toHaveBeenCalledWith('/projects/3/purge', { confirm_password: '' })
  })
})

describe('api/projects —— 具名导出的回收站函数（列表页直接使用）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockPost.mockResolvedValue({ success: true })
    mockGet.mockResolvedValue({ id: 9 })
  })

  it('restoreProject POST /projects/{id}/restore', async () => {
    await restoreProject(9)
    expect(mockPost).toHaveBeenCalledWith('/projects/9/restore', {})
  })

  it('previewPurgeProject GET /projects/{id}/purge/preview', async () => {
    await previewPurgeProject(9)
    expect(mockGet).toHaveBeenCalledWith('/projects/9/purge/preview')
  })

  it('purgeProject 携带确认密码', async () => {
    await purgeProject(9, 'pw')
    expect(mockPost).toHaveBeenCalledWith('/projects/9/purge', { confirm_password: 'pw' })
  })

  it('purgeProject 省略密码回退空串', async () => {
    await purgeProject(9)
    expect(mockPost).toHaveBeenCalledWith('/projects/9/purge', { confirm_password: '' })
  })
})

describe('api/message —— clearReadMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // helper 已解包：mock 直接给 body，而不是 { data: body }
    mockApiRequest.mockResolvedValue({ count: 5 })
  })

  it('以 DELETE /messages/read 调用 apiRequest', async () => {
    await clearReadMessages()
    expect(mockApiRequest).toHaveBeenCalledWith({
      method: 'DELETE',
      url: '/messages/read',
    })
  })

  it('返回后端给出的已清空条数', async () => {
    await expect(clearReadMessages()).resolves.toBe(5)
  })

  it('后端返回 0 条时如实返回 0（不被 ?? / || 吞掉）', async () => {
    mockApiRequest.mockResolvedValue({ count: 0 })
    await expect(clearReadMessages()).resolves.toBe(0)
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_PAGE_SIZE,
  MAX_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
  normalizePageSize,
  pageSizeStorageKey,
  readPageSize,
  usePageSize,
  writePageSize,
} from '@/composables/usePageSize'

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('常量与归一化', () => {
  it('选项包含默认值与后端硬上限', () => {
    expect(PAGE_SIZE_OPTIONS).toContain(DEFAULT_PAGE_SIZE)
    expect(PAGE_SIZE_OPTIONS).toContain(MAX_PAGE_SIZE)
  })

  it('只接受选项内的值，其它一律回退默认（不做就近取整）', () => {
    expect(normalizePageSize(50)).toBe(50)
    expect(normalizePageSize('200')).toBe(200)
    expect(normalizePageSize(37)).toBe(DEFAULT_PAGE_SIZE)
    expect(normalizePageSize(0)).toBe(DEFAULT_PAGE_SIZE)
    expect(normalizePageSize(-1)).toBe(DEFAULT_PAGE_SIZE)
    expect(normalizePageSize('abc')).toBe(DEFAULT_PAGE_SIZE)
    expect(normalizePageSize(null)).toBe(DEFAULT_PAGE_SIZE)
    expect(normalizePageSize(undefined)).toBe(DEFAULT_PAGE_SIZE)
  })
})

describe('读写存储', () => {
  it('键带统一前缀（按业务域记忆）', () => {
    expect(pageSizeStorageKey('projects')).toBe('ui:pageSize:projects')
  })

  it('写入后可读回；非法写入值被归一', () => {
    writePageSize('projects', 100)
    expect(readPageSize('projects')).toBe(100)

    writePageSize('projects', 37)
    expect(readPageSize('projects')).toBe(DEFAULT_PAGE_SIZE)
  })

  it('存储为空 → 默认值', () => {
    expect(readPageSize('projects')).toBe(DEFAULT_PAGE_SIZE)
  })

  it('不同业务域互不干扰', () => {
    writePageSize('projects', 50)
    writePageSize('policies', 200)
    expect(readPageSize('projects')).toBe(50)
    expect(readPageSize('policies')).toBe(200)
  })

  it('存储抛错（隐私模式/配额）静默降级', () => {
    vi.spyOn(localStorage, 'getItem').mockImplementation(() => {
      throw new Error('denied')
    })
    expect(readPageSize('projects')).toBe(DEFAULT_PAGE_SIZE)
    vi.restoreAllMocks()

    vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(() => writePageSize('projects', 50)).not.toThrow()
  })
})

describe('usePageSize', () => {
  it('初始化读取已存偏好', () => {
    writePageSize('projects', 100)
    const { pageSize } = usePageSize('projects')
    expect(pageSize.value).toBe(100)
  })

  it('setPageSize 归一化 + 持久化 + 返回生效值', () => {
    const { pageSize, setPageSize } = usePageSize('projects')
    expect(setPageSize(50)).toBe(50)
    expect(pageSize.value).toBe(50)
    expect(localStorage.getItem(pageSizeStorageKey('projects'))).toBe('50')

    expect(setPageSize(37)).toBe(DEFAULT_PAGE_SIZE)
    expect(pageSize.value).toBe(DEFAULT_PAGE_SIZE)
  })

  it('options 暴露给下拉框', () => {
    const { options } = usePageSize('projects')
    expect(options.value).toEqual(PAGE_SIZE_OPTIONS)
  })
})

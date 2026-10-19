import { describe, it, expect, vi } from 'vitest'

/**
 * common/index.ts barrel 导出面测试。
 *
 * 单执行者规程：这里 **mock** 六个 .vue 模块，只验证 barrel 的 re-export 结构，
 * 不会第二次真实执行任何组件模块（各组件只由其专属测试文件执行）。
 */
vi.mock('@/components/common/AppPageHeader.vue', () => ({ default: { name: 'AppPageHeader' } }))
vi.mock('@/components/common/AppStatCard.vue', () => ({ default: { name: 'AppStatCard' } }))
vi.mock('@/components/common/AppEmpty.vue', () => ({ default: { name: 'AppEmpty' } }))
vi.mock('@/components/common/AppLoading.vue', () => ({ default: { name: 'AppLoading' } }))
vi.mock('@/components/common/AppError.vue', () => ({ default: { name: 'AppError' } }))
vi.mock('@/components/common/AppTableToolbar.vue', () => ({ default: { name: 'AppTableToolbar' } }))

import * as common from '@/components/common/index'

describe('common/index barrel 导出面', () => {
  it('导出全部 6 个通用组件且指向对应模块', () => {
    expect(Object.keys(common).sort()).toEqual(
      [
        'AppEmpty',
        'AppError',
        'AppLoading',
        'AppPageHeader',
        'AppStatCard',
        'AppTableToolbar',
      ].sort()
    )
    expect(common.AppPageHeader).toEqual({ name: 'AppPageHeader' })
    expect(common.AppStatCard).toEqual({ name: 'AppStatCard' })
    expect(common.AppEmpty).toEqual({ name: 'AppEmpty' })
    expect(common.AppLoading).toEqual({ name: 'AppLoading' })
    expect(common.AppError).toEqual({ name: 'AppError' })
    expect(common.AppTableToolbar).toEqual({ name: 'AppTableToolbar' })
  })
})

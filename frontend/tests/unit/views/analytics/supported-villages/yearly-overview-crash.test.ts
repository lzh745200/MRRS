/**
 * 复现测试：YearlyOverview 页面是否触发 setAttribute('0') 崩溃
 * 用户线上错误：Failed to execute 'setAttribute' on 'Element': '0' is not a valid attribute name
 */
import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import YearlyOverview from '@/views/analytics/supported-villages/YearlyOverview.vue'

vi.mock('@/api/supportedVillage', () => ({
  getSupportedVillage: vi.fn(),
  getYearlyData: vi.fn(),
  downloadTemplate: vi.fn(),
  importSectionData: vi.fn(),
  downloadAllTemplates: vi.fn(),
  importAllSectionsData: vi.fn(),
  getSectionAttachments: vi.fn(),
  deleteSectionAttachment: vi.fn(),
  uploadSectionAttachment: vi.fn(),
  savePopulationData: vi.fn(),
  saveIncomeData: vi.fn(),
  saveIndustryData: vi.fn(),
  saveInfrastructureData: vi.fn(),
  saveEducationData: vi.fn(),
  saveForceInvestmentData: vi.fn(),
  savePartyBuildingData: vi.fn(),
  saveMedicalData: vi.fn(),
  saveConsumptionData: vi.fn(),
  saveEmploymentData: vi.fn(),
  saveCommitteeData: vi.fn(),
  getTransitionFunding: vi.fn(),
  saveTransitionFunding: vi.fn(),
  deleteYearlySection: vi.fn(),
  resolveSectionApiKey: (k: string) =>
    (({ force_investment: 'force-investment', party_building: 'party-building' } as any)[k] ?? k),
}))

import { getSupportedVillage, getYearlyData } from '@/api/supportedVillage'

describe('YearlyOverview 页面挂载（setAttribute 崩溃回归）', () => {
  it('正常数据挂载不抛 InvalidCharacterError', async () => {
    ;(getSupportedVillage as any).mockResolvedValue({ id: 1, villageName: '示范村', village_name: '示范村' })
    ;(getYearlyData as any).mockResolvedValue({
      villageId: 1,
      year: 2026,
      sections: [
        { key: 'population', title: '人口', icon: 'User', stats: [] },
        { key: 'income', title: '收入', icon: 'Money', stats: [] },
      ],
    })
    const wrapper = mount(YearlyOverview as any, {
      global: {
        stubs: {
          'el-icon': { template: '<span><slot /></span>' },
          'el-button': true,
          'el-tag': true,
          'el-card': { template: '<div><slot /></div>' },
          'el-dialog': { template: '<div v-if="modelValue"><slot /></div>' },
          'el-skeleton': true,
          'el-empty': true,
        },
      },
    })
    await flushPromises()
    // 不抛 InvalidCharacterError 即通过
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).not.toContain('页面异常')
  })

  it('后端返回异常数据结构（sections 为数组含空对象）不崩溃', async () => {
    ;(getSupportedVillage as any).mockResolvedValue({ id: 1, villageName: '示范村' })
    ;(getYearlyData as any).mockResolvedValue({
      villageId: 1,
      year: 2026,
      sections: [{}, null, { key: undefined, title: undefined, icon: undefined, stats: undefined }],
    })
    const wrapper = mount(YearlyOverview as any, {
      global: {
        stubs: {
          'el-icon': { template: '<span><slot /></span>' },
          'el-button': true,
          'el-tag': true,
          'el-card': { template: '<div><slot /></div>' },
          'el-dialog': { template: '<div v-if="modelValue"><slot /></div>' },
          'el-skeleton': true,
          'el-empty': true,
        },
      },
    })
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).not.toContain('页面异常')
  })
})

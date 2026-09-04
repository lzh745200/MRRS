/**
 * 回归测试：附件 fileType 缺失（undefined）时渲染不崩溃
 * 修复背景：YearlyOverview 页面异常 "Cannot read properties of undefined (reading 'toLowerCase')"
 * 根因：后端附件数据缺 fileType 字段 → SectionDataForm 的 isPreviewable(undefined) → undefined.toLowerCase() 崩溃
 */
import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SectionDataForm from '@/views/analytics/supported-villages/components/SectionDataForm.vue'

vi.mock('@/api/supportedVillage', () => ({
  getYearlyData: vi.fn(),
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
  uploadSectionAttachment: vi.fn(),
  getSectionAttachments: vi.fn(),
  deleteSectionAttachment: vi.fn(),
  resolveSectionApiKey: (k: string) =>
    (({ force_investment: 'force-investment', party_building: 'party-building' } as any)[k] ?? k),
}))

import { getSectionAttachments } from '@/api/supportedVillage'

function mountForm(attachments: any[]) {
  ;(getSectionAttachments as any).mockResolvedValue(attachments)
  const wrapper = mount(SectionDataForm as any, {
    props: { villageId: 1, villageName: '村A', sectionKey: 'basic_info', initialYear: 2026 },
    global: {
      stubs: {
        'el-icon': true,
        'el-button': true,
        'el-tag': true,
        'el-dialog': true,
        'el-upload': true,
        'el-form': true,
        'el-form-item': true,
        'el-input': true,
        'el-select': true,
        'el-option': true,
        'el-date-picker': true,
        'el-input-number': true,
        'el-checkbox': true,
        'el-radio-group': true,
        'el-radio': true,
      },
    },
  } as any)
  return wrapper
}

describe('SectionDataForm 附件 fileType 防御（回归）', () => {
  it('fileType=undefined 的附件加载后渲染不抛 toLowerCase 异常', async () => {
    // 模拟后端附件记录缺 fileType 字段（线上真实崩溃场景）
    const wrapper = mountForm([{ id: 1, fileName: '年度报告.xlsx', fileSize: 1024 }])
    await flushPromises()
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Cannot read properties')
  })

  it('fileType 缺失时不显示预览按钮（isPreviewable 返回 false）', async () => {
    const wrapper = mountForm([{ id: 1, fileName: 'a.pdf', fileSize: 10 }])
    await flushPromises()
    const previewBtns = wrapper.findAll('button').filter((b) => b.text().includes('预览'))
    expect(previewBtns.length).toBe(0)
  })
})

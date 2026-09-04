/**
 * SectionDataForm.vue 测试
 * 覆盖：保存（成功/校验失败/未知板块/API失败）、取消、上传（大小限制/超限/成功/失败）、
 * 附件（删除确认/取消/失败）、预览类型判断、下载、文件大小格式化
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'

enableAutoUnmount(afterEach)

afterEach(() => {
  vi.restoreAllMocks()
})

const mocks = vi.hoisted(() => ({
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
  logger: { error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn(), log: vi.fn() },
}))

vi.mock('@/api/supportedVillage', () => ({
  getYearlyData: (...a: any[]) => mocks.getYearlyData(...a),
  savePopulationData: (...a: any[]) => mocks.savePopulationData(...a),
  saveIncomeData: (...a: any[]) => mocks.saveIncomeData(...a),
  saveIndustryData: (...a: any[]) => mocks.saveIndustryData(...a),
  saveInfrastructureData: (...a: any[]) => mocks.saveInfrastructureData(...a),
  saveEducationData: (...a: any[]) => mocks.saveEducationData(...a),
  saveForceInvestmentData: (...a: any[]) => mocks.saveForceInvestmentData(...a),
  savePartyBuildingData: (...a: any[]) => mocks.savePartyBuildingData(...a),
  saveMedicalData: (...a: any[]) => mocks.saveMedicalData(...a),
  saveConsumptionData: (...a: any[]) => mocks.saveConsumptionData(...a),
  saveEmploymentData: (...a: any[]) => mocks.saveEmploymentData(...a),
  saveCommitteeData: (...a: any[]) => mocks.saveCommitteeData(...a),
  uploadSectionAttachment: (...a: any[]) => mocks.uploadSectionAttachment(...a),
  getSectionAttachments: (...a: any[]) => mocks.getSectionAttachments(...a),
  deleteSectionAttachment: (...a: any[]) => mocks.deleteSectionAttachment(...a),
  resolveSectionApiKey: (k: string) =>
    (({ force_investment: 'force-investment', party_building: 'party-building' } as any)[k] ?? k),
}))

vi.mock('@/utils/logger', () => ({ logger: mocks.logger }))

import SectionDataForm from '@/views/analytics/supported-villages/components/SectionDataForm.vue'

const attachment = {
  id: 1,
  fileName: '证明.pdf',
  fileSize: 2048,
  fileType: 'application/pdf',
  fileUrl: 'http://x/file.pdf',
}

function mountForm(props: Record<string, unknown> = {}) {
  return mount(SectionDataForm, {
    props: {
      villageId: 1,
      villageName: '示范村',
      sectionKey: 'population',
      ...props,
    },
    global: {
      plugins: [ElementPlus],
      stubs: {
        'el-icon': { template: '<i class="stub-icon"><slot /></i>' },
      },
    },
  })
}

function state(wrapper: ReturnType<typeof mountForm>) {
  return (wrapper.vm as any).$.setupState
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getYearlyData.mockResolvedValue({})
  mocks.getSectionAttachments.mockResolvedValue([])
  mocks.savePopulationData.mockResolvedValue({ success: true })
  mocks.uploadSectionAttachment.mockResolvedValue(attachment)
  mocks.deleteSectionAttachment.mockResolvedValue({ success: true })
})

describe('SectionDataForm.vue 保存/取消', () => {
  it('保存成功：校验通过 → 调用保存 API → success + saved/close 事件', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.formRef = { validate: vi.fn().mockResolvedValue(true) }
    await st.handleSave()
    expect(mocks.savePopulationData).toHaveBeenCalledWith(1, expect.any(Number), expect.any(Object))
    const emitted = wrapper.emitted()
    expect(emitted.saved).toHaveLength(1)
    expect(emitted.close).toHaveLength(1)
  })

  it('保存校验失败：warning 且不调用保存 API', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.formRef = { validate: vi.fn().mockRejectedValue(new Error('invalid')) }
    const warnSpy = vi.spyOn(ElMessage, 'warning')
    await st.handleSave()
    expect(warnSpy).toHaveBeenCalled()
    expect(mocks.savePopulationData).not.toHaveBeenCalled()
    expect(wrapper.emitted('saved')).toBeUndefined()
  })

  it('未知板块类型：error 提示且不保存', async () => {
    const wrapper = mountForm({ sectionKey: 'unknown_section' })
    await flushPromises()
    const st = state(wrapper)
    st.formRef = { validate: vi.fn().mockResolvedValue(true) }
    const errSpy = vi.spyOn(ElMessage, 'error')
    await st.handleSave()
    expect(errSpy).toHaveBeenCalledWith('未知板块类型')
    expect(mocks.savePopulationData).not.toHaveBeenCalled()
  })

  it('保存 API 失败：error 提示并复位 saving', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.formRef = { validate: vi.fn().mockResolvedValue(true) }
    mocks.savePopulationData.mockRejectedValue(new Error('网络错误'))
    const errSpy = vi.spyOn(ElMessage, 'error')
    await st.handleSave()
    expect(errSpy).toHaveBeenCalledWith('网络错误')
    expect(st.saving).toBe(false)
    expect(mocks.logger.error).toHaveBeenCalled()
  })

  it('保存 API 失败且无 message：回退默认文案', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.formRef = { validate: vi.fn().mockResolvedValue(true) }
    mocks.savePopulationData.mockRejectedValue(new Error())
    const errSpy = vi.spyOn(ElMessage, 'error')
    await st.handleSave()
    expect(errSpy).toHaveBeenCalledWith('保存失败，请重试')
  })

  it('committee 板块保存：走 committee 专属 saveFn（含 members 组装）', async () => {
    const wrapper = mountForm({ sectionKey: 'committee' })
    await flushPromises()
    const st = state(wrapper)
    st.formRef = { validate: vi.fn().mockResolvedValue(true) }
    st.committeeMembers = [{ name: '张三', position: '支书', phone: '', isVeteran: true, remark: '' }]
    await st.handleSave()
    expect(mocks.saveCommitteeData).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        year: expect.any(Number),
        members: [{ name: '张三', position: '支书', phone: '', isVeteran: true, remark: '' }],
      }),
    )
  })

  it('取消：emit close', async () => {
    const wrapper = mountForm()
    await flushPromises()
    state(wrapper).handleClose()
    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})

describe('SectionDataForm.vue 文件上传', () => {
  it('beforeUpload：超过 20MB 拒绝，正常文件放行', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    const errSpy = vi.spyOn(ElMessage, 'error')
    expect(st.handleBeforeUpload({ size: 21 * 1024 * 1024 } as any)).toBe(false)
    expect(errSpy).toHaveBeenCalledWith('文件大小不能超过20MB')
    expect(st.handleBeforeUpload({ size: 1024 } as any)).toBe(true)
  })

  it('exceed：warning 提示最多 10 个', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const warnSpy = vi.spyOn(ElMessage, 'warning')
    state(wrapper).handleExceed()
    expect(warnSpy).toHaveBeenCalledWith('最多上传10个文件')
  })

  it('customUpload 成功：追加附件并提示', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    const sucSpy = vi.spyOn(ElMessage, 'success')
    await st.handleCustomUpload({ file: new File(['x'], 'a.jpg') } as any)
    expect(mocks.uploadSectionAttachment).toHaveBeenCalledWith(1, 'population', expect.any(File))
    expect(st.attachments).toContainEqual(attachment)
    expect(sucSpy).toHaveBeenCalledWith('上传成功')
  })

  it('customUpload 失败：error 提示', async () => {
    const wrapper = mountForm()
    await flushPromises()
    mocks.uploadSectionAttachment.mockRejectedValue(new Error('上传失败'))
    const st = state(wrapper)
    const errSpy = vi.spyOn(ElMessage, 'error')
    await st.handleCustomUpload({ file: new File(['x'], 'a.jpg') } as any)
    expect(errSpy).toHaveBeenCalledWith('上传失败')
  })

  it('customUpload 失败且无 message：回退默认文案', async () => {
    const wrapper = mountForm()
    await flushPromises()
    mocks.uploadSectionAttachment.mockRejectedValue({})
    const st = state(wrapper)
    const errSpy = vi.spyOn(ElMessage, 'error')
    await st.handleCustomUpload({ file: new File(['x'], 'a.jpg') } as any)
    expect(errSpy).toHaveBeenCalledWith('上传失败')
  })

  it('uploadRemove：空实现可调用（el-upload 内部移除回调）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    expect(() => st.handleUploadRemove({} as any)).not.toThrow()
  })
})

describe('SectionDataForm.vue 初始化与年份切换', () => {
  it('附件加载失败 → 回退空数组', async () => {
    mocks.getSectionAttachments.mockRejectedValue(new Error('net'))
    const wrapper = mountForm()
    await flushPromises()
    expect(state(wrapper).attachments).toEqual([])
  })

  it('handleYearChange → 重新加载数据与附件', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.handleYearChange()
    await flushPromises()
    expect(mocks.getYearlyData).toHaveBeenCalledTimes(2)
    expect(mocks.getSectionAttachments).toHaveBeenCalledTimes(2)
  })

  it('年度数据存在 → 回填表单（null/undefined 字段跳过）', async () => {
    mocks.getYearlyData.mockResolvedValue({
      population: { totalHouseholds: 12, totalPopulation: 30, laborForce: null, migrantWorkers: undefined },
    })
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    expect(st.formData.totalHouseholds).toBe(12)
    expect(st.formData.totalPopulation).toBe(30)
    expect(st.formData.laborForce).toBe(0)
  })

  it('committee 板块含成员数据 → 加载成员列表', async () => {
    mocks.getYearlyData.mockResolvedValue({
      committee: {
        overview: '概况',
        members: [{ name: '李四', position: '主任', phone: '138', isVeteran: true, remark: 'r' }],
      },
    })
    const wrapper = mountForm({ sectionKey: 'committee' })
    await flushPromises()
    const st = state(wrapper)
    expect(st.committeeMembers).toEqual([
      { name: '李四', position: '主任', phone: '138', isVeteran: true, remark: 'r' },
    ])
  })

  it('committee 成员字段缺失 → 空字符串兜底', async () => {
    mocks.getYearlyData.mockResolvedValue({
      committee: { members: [{ name: null, isVeteran: 1 }] },
    })
    const wrapper = mountForm({ sectionKey: 'committee' })
    await flushPromises()
    expect(state(wrapper).committeeMembers).toEqual([
      { name: '', position: '', phone: '', isVeteran: true, remark: '' },
    ])
  })

  it('addCommitteeMember → 追加空成员', async () => {
    const wrapper = mountForm({ sectionKey: 'committee' })
    await flushPromises()
    const st = state(wrapper)
    st.addCommitteeMember()
    expect(st.committeeMembers).toHaveLength(1)
    expect(st.committeeMembers[0]).toEqual({ name: '', position: '', phone: '', isVeteran: false, remark: '' })
  })

  it('年度数据加载失败 → 使用默认值（catch 分支）', async () => {
    mocks.getYearlyData.mockRejectedValue(new Error('net'))
    const wrapper = mountForm()
    await flushPromises()
    expect(state(wrapper).formData.totalHouseholds).toBe(0)
  })

  it('population 表单校验：总人数≤0 被拒绝（validator error 分支）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    const validators = st.formRules.totalPopulation.filter((r: any) => r.validator)
    const rule = validators[validators.length - 1] // 业务校验在规则数组末尾
    const err = await new Promise((resolve) => {
      rule.validator({}, 0, (e?: Error) => resolve(e))
    })
    expect(err).toBeInstanceOf(Error)
  })

  it('population 表单校验：总人数>0 通过（callback 无错分支）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    const validators = st.formRules.totalPopulation.filter((r: any) => r.validator)
    const rule = validators[validators.length - 1]
    const err = await new Promise((resolve) => {
      rule.validator({}, 10, (e?: Error) => resolve(e))
    })
    expect(err).toBeUndefined()
  })

  it('population 表单校验：总人数为 null → 跳过校验（value != null false 分支）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    const validators = st.formRules.totalPopulation.filter((r: any) => r.validator)
    const rule = validators[validators.length - 1]
    const err = await new Promise((resolve) => {
      rule.validator({}, null, (e?: Error) => resolve(e))
    })
    expect(err).toBeUndefined()
  })

  it('population 表单校验：常住人口超过总人数被拒绝', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.formData.totalPopulation = 10
    const validators = st.formRules.residentPopulation.filter((r: any) => r.validator)
    const rule = validators[validators.length - 1]
    const err = await new Promise((resolve) => {
      rule.validator({}, 15, (e?: Error) => resolve(e))
    })
    expect(err).toBeInstanceOf(Error)
  })

  it('population 表单校验：总人数为 0 时常住人口判定（|| 0 兜底分支）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.formData.totalPopulation = 0
    const validators = st.formRules.residentPopulation.filter((r: any) => r.validator)
    const rule = validators[validators.length - 1]
    const err = await new Promise((resolve) => {
      rule.validator({}, 5, (e?: Error) => resolve(e))
    })
    // totalPopulation=0 → (0 || 0)=0 → 5>0 → 校验拒绝
    expect(err).toBeInstanceOf(Error)
  })

  it('population 表单校验：常住人口未超总人数通过', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.formData.totalPopulation = 10
    const validators = st.formRules.residentPopulation.filter((r: any) => r.validator)
    const rule = validators[validators.length - 1]
    const err = await new Promise((resolve) => {
      rule.validator({}, 5, (e?: Error) => resolve(e))
    })
    expect(err).toBeUndefined()
  })

  it('population 表单校验：常住人口为 null → 跳过校验（value != null false 分支）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.formData.totalPopulation = 10
    const validators = st.formRules.residentPopulation.filter((r: any) => r.validator)
    const rule = validators[validators.length - 1]
    const err = await new Promise((resolve) => {
      rule.validator({}, null, (e?: Error) => resolve(e))
    })
    expect(err).toBeUndefined()
  })

  it('非负校验：负数被拒绝（nonNegativeRule error 分支）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    const rule = st.formRules.totalHouseholds.find((r: any) => r.validator)
    const err = await new Promise((resolve) => {
      rule.validator({}, -1, (e?: Error) => resolve(e))
    })
    expect(err).toBeInstanceOf(Error)
  })

  it('非负校验：非负数通过（nonNegativeRule else 分支）', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    const rule = st.formRules.totalHouseholds.find((r: any) => r.validator)
    const err = await new Promise((resolve) => {
      rule.validator({}, 5, (e?: Error) => resolve(e))
    })
    expect(err).toBeUndefined()
  })
})

describe('SectionDataForm.vue 附件管理', () => {
  it('删除附件：确认后调用删除 API 并从列表移除', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.attachments = [{ ...attachment }]
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    const sucSpy = vi.spyOn(ElMessage, 'success')
    await st.handleDeleteAttachment(attachment)
    expect(mocks.deleteSectionAttachment).toHaveBeenCalledWith(1, 'population', 1)
    expect(st.attachments).toHaveLength(0)
    expect(sucSpy).toHaveBeenCalledWith('删除成功')
  })

  it('删除附件：用户取消确认则跳过', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.attachments = [{ ...attachment }]
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue(new Error('cancel'))
    await st.handleDeleteAttachment(attachment)
    expect(mocks.deleteSectionAttachment).not.toHaveBeenCalled()
    expect(st.attachments).toHaveLength(1)
  })

  it('删除附件：API 失败提示 error', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.attachments = [{ ...attachment }]
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    mocks.deleteSectionAttachment.mockRejectedValue(new Error('删除失败'))
    const errSpy = vi.spyOn(ElMessage, 'error')
    await st.handleDeleteAttachment(attachment)
    expect(errSpy).toHaveBeenCalledWith('删除失败')
  })

  it('删除附件：API 失败且无 message：回退默认文案', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.attachments = [{ ...attachment }]
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    mocks.deleteSectionAttachment.mockRejectedValue({})
    const errSpy = vi.spyOn(ElMessage, 'error')
    await st.handleDeleteAttachment(attachment)
    expect(errSpy).toHaveBeenCalledWith('删除失败')
  })

  it('预览：设置预览状态并打开弹窗', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.handlePreview(attachment)
    expect(st.previewAttachment).toEqual(attachment)
    expect(st.previewTitle).toBe('证明.pdf')
    expect(st.previewUrl).toBe('http://x/file.pdf')
    expect(st.previewType).toBe('pdf')
    expect(st.previewVisible).toBe(true)
  })

  it('预览弹窗关闭：触发 v-model 更新函数', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    st.handlePreview(attachment)
    await nextTick()
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    dialog.vm.$emit('update:modelValue', false)
    await nextTick()
    expect(st.previewVisible).toBe(false)
  })

  it('下载：创建 a 标签并触发点击', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    st.handleDownload(attachment)
    expect(clickSpy).toHaveBeenCalled()
  })

  it('formatFileSize：B / KB / MB 三分支', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    expect(st.formatFileSize(512)).toBe('512 B')
    expect(st.formatFileSize(2048)).toBe('2.0 KB')
    expect(st.formatFileSize(5 * 1024 * 1024)).toBe('5.0 MB')
  })
})

describe('SectionDataForm.vue 预览类型判断', () => {
  it('isPreviewable：图片/PDF 可预览，其他不可', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    expect(st.isPreviewable('image/png')).toBe(true)
    expect(st.isPreviewable('application/pdf')).toBe(true)
    expect(st.isPreviewable('image/png')).toBe(true)
    expect(st.isPreviewable('x.jpg')).toBe(true)
    expect(st.isPreviewable('text/plain')).toBe(false)
    expect(st.isPreviewable(undefined)).toBe(false)
  })

  it('getPreviewType：image / pdf / other 三分支', async () => {
    const wrapper = mountForm()
    await flushPromises()
    const st = state(wrapper)
    expect(st.getPreviewType('image/jpeg')).toBe('image')
    expect(st.getPreviewType('a.png')).toBe('image')
    expect(st.getPreviewType('application/pdf')).toBe('pdf')
    expect(st.getPreviewType('report.pdf')).toBe('pdf')
    expect(st.getPreviewType('text/plain')).toBe('other')
    expect(st.getPreviewType(undefined)).toBe('other')
  })
})

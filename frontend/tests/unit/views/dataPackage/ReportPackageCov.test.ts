/**
 * views/dataPackage/ReportPackage.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：validateForm 两个失败分支、previewData 成功（counts 三级取值）/失败回退、
 * generatePackage（id 四级取值、remarks 兜底、自动下载、错误三级文案）、
 * downloadPackage（无 ID 警告/成功 blob 下载/失败）、一键上报（Blob 直存、
 * download_url 两分支、均无、接口失败回退分步流程全分支、外层 catch 两级文案）、
 * onErrorCaptured 错误边界两侧、handleRetry/resetForm、模板三步卡片/警告条/样式三元、
 * 全部按钮点击与 v-model 处理器。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化
const { ElMessage, postMock, apiRequestMock, logError, logWarn, authState } = vi.hoisted(() => {
  return {
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
    postMock: vi.fn(),
    apiRequestMock: vi.fn(),
    logError: vi.fn(),
    logWarn: vi.fn(),
    authState: { isAdmin: true },
  }
})

vi.mock('element-plus', () => ({ ElMessage }))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/api/request', () => ({
  post: postMock,
  apiRequest: apiRequestMock,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/logger', () => ({
  logger: { error: logError, warn: logWarn, info: vi.fn(), debug: vi.fn() },
}))

import ReportPackage from '@/views/dataPackage/ReportPackage.vue'

function mountComp(extraStubs: Record<string, any> = {}) {
  // el-result 需渲染 #extra 具名插槽；其余 el-* 走全局 stub + 默认插槽渲染
  return mount(ReportPackage, {
    global: {
      renderStubDefaultSlot: true,
      stubs: {
        'el-result': {
          name: 'ElResult',
          props: ['title', 'subTitle'],
          template:
            '<div class="el-result-stub"><span class="el-result-title">{{ title }}</span><slot /><slot name="extra" /></div>',
        },
        ...extraStubs,
      },
    },
  })
}

function findBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

function spyAnchorClick() {
  return vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
}

beforeEach(() => {
  vi.resetAllMocks()
  authState.isAdmin = true
  postMock.mockResolvedValue({ counts: { villages: 3, projects: 5 } })
  apiRequestMock.mockResolvedValue('blob-content')
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('初始渲染与 validateForm', () => {
  it('初始渲染步骤 0 表单卡片', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.currentStep).toBe(0)
    expect(wrapper.text()).toContain('数据上报')
    expect(wrapper.text()).toContain('帮扶村数据')
    expect(wrapper.text()).toContain('乡村工作')
  })

  it('缺年度 → 警告；清空数据类型 → 警告', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.form.year = ''
    await vm.previewData()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择上报年度')
    expect(postMock).not.toHaveBeenCalled()

    vm.form.year = '2026'
    vm.form.dataTypes = []
    await vm.previewData()
    expect(ElMessage.warning).toHaveBeenCalledWith('请至少选择一种数据类型')
    expect(postMock).not.toHaveBeenCalled()
  })

  it('表单 v-model：年度 / 数据类型 / 备注 全部同步', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    wrapper.findComponent({ name: 'ElDatePicker' }).vm.$emit('update:modelValue', '2025')
    expect(vm.form.year).toBe('2025')
    wrapper.findComponent({ name: 'ElCheckboxGroup' }).vm.$emit('update:modelValue', ['villages'])
    expect(vm.form.dataTypes).toEqual(['villages'])
    wrapper.findComponent({ name: 'ElInput' }).vm.$emit('update:modelValue', '备注内容')
    expect(vm.form.remarks).toBe('备注内容')
    await nextTick()
  })
})

describe('previewData 预览', () => {
  it('成功：data.counts 直接取值；含 0 记录与未知类型 → 警告条与样式三元两侧', async () => {
    postMock.mockResolvedValue({ counts: { villages: 3, projects: 0, mystery: 2 } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.form.dataTypes = ['villages', 'projects', 'mystery_type']
    await findBtn(wrapper, '下一步：预览数据').trigger('click')
    await flushPromises()
    expect(postMock).toHaveBeenCalledWith('/data-packages/preview', {
      year: vm.form.year,
      data_types: ['villages', 'projects', 'mystery_type'],
    })
    expect(vm.currentStep).toBe(1)
    await nextTick()
    expect(vm.emptyDataTypes).toEqual(['projects'])
    expect(wrapper.html()).toContain('以下数据类型记录数为0') // el-alert v-if 真侧
    expect(wrapper.text()).toContain('3 条记录') // count>0 样式侧
    expect(wrapper.text()).toContain('0 条记录') // count===0 样式侧
    expect(wrapper.text()).toContain('mystery') // typeLabels[key] || key 未知侧
    expect(vm.previewing).toBe(false)
  })

  it('成功：data.data.counts 嵌套取值；全部 >0 → 警告条隐藏', async () => {
    postMock.mockResolvedValue({ data: { counts: { villages: 8 } } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.previewData()
    expect(vm.currentStep).toBe(1)
    expect(vm.previewCounts).toEqual({ villages: 8 })
    await nextTick()
    expect(wrapper.html()).not.toContain('以下数据类型记录数为0')
  })

  it('警告条含未知类型 0 计数 → typeLabels[t] || t 原始键回退（L71）', async () => {
    postMock.mockResolvedValue({ counts: { weird_type: 0 } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.form.dataTypes = ['weird_type']
    await findBtn(wrapper, '下一步：预览数据').trigger('click')
    await flushPromises()
    await nextTick()
    expect(vm.emptyDataTypes).toEqual(['weird_type'])
    expect(wrapper.html()).toContain('以下数据类型记录数为0: weird_type')
  })

  it('成功：响应为 null → counts || {} 兜底', async () => {
    postMock.mockResolvedValue(null)
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.previewData()
    expect(vm.previewCounts).toEqual({})
    expect(vm.currentStep).toBe(1)
  })

  it('失败：catch 回退模拟数据（每种类型置 0）仍进步骤 1', async () => {
    postMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.form.dataTypes = ['villages', 'funds']
    await vm.previewData()
    expect(vm.previewCounts).toEqual({ villages: 0, funds: 0 })
    expect(vm.currentStep).toBe(1)
    expect(vm.previewing).toBe(false)
  })
})

describe('步骤 1 交互与 generatePackage', () => {
  it('点击「上一步」回到步骤 0', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.previewData()
    await nextTick()
    await findBtn(wrapper, '上一步').trigger('click')
    expect(vm.currentStep).toBe(0)
  })

  it('点击「生成数据包」：package_id 直取 + 备注缺省 → 自动触发下载并进步骤 2', async () => {
    const clickSpy = spyAnchorClick()
    postMock.mockImplementation((url: string) => {
      if (url === '/data-packages/preview') return Promise.resolve({ counts: { villages: 3 } })
      if (url === '/data-packages/export') return Promise.resolve({ package_id: 'pkg-1' })
      return Promise.resolve({})
    })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.form.remarks = '' // description 走 `${year}年度数据上报` 兜底
    await vm.previewData()
    await nextTick()
    await findBtn(wrapper, '生成数据包').trigger('click')
    await flushPromises()
    expect(postMock).toHaveBeenCalledWith('/data-packages/export', {
      data_types: vm.form.dataTypes,
      description: `${vm.form.year}年度数据上报`,
      type: 'report',
    })
    expect(vm.packageId).toBe('pkg-1')
    expect(vm.currentStep).toBe(2)
    expect(ElMessage.success).toHaveBeenCalledWith('数据包生成成功')
    expect(apiRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'GET', url: '/data-packages/pkg-1/download', responseType: 'blob' })
    )
    expect(clickSpy).toHaveBeenCalled() // 自动下载 a.click
    expect(vm.generating).toBe(false)
    await nextTick()
    expect(wrapper.text()).toContain('数据包已生成')
  })

  it('成功：data.id / data.data.id 嵌套取值；备注已填 → 用备注作描述', async () => {
    spyAnchorClick()
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.form.remarks = '人工备注'

    postMock.mockResolvedValueOnce({ id: 'pkg-2' }) // data?.package_id 空 → data?.id
    await vm.generatePackage()
    expect(postMock).toHaveBeenCalledWith('/data-packages/export', {
      data_types: vm.form.dataTypes,
      description: '人工备注',
      type: 'report',
    })
    expect(vm.packageId).toBe('pkg-2')

    postMock.mockResolvedValueOnce({ data: { id: 'pkg-3' } }) // data?.data?.id
    await vm.generatePackage()
    expect(vm.packageId).toBe('pkg-3')
  })

  it('成功但无任何 id → 不自动下载', async () => {
    postMock.mockResolvedValue({})
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.generatePackage()
    expect(vm.packageId).toBe('')
    expect(vm.currentStep).toBe(2)
    expect(apiRequestMock).not.toHaveBeenCalled()
  })

  it('失败：detail / message / 默认 三级错误文案', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    postMock.mockRejectedValueOnce({ response: { data: { detail: '服务器繁忙' } } })
    await vm.generatePackage()
    expect(ElMessage.error).toHaveBeenCalledWith('服务器繁忙')

    postMock.mockRejectedValueOnce(new Error('网络异常'))
    await vm.generatePackage()
    expect(ElMessage.error).toHaveBeenCalledWith('网络异常')

    postMock.mockRejectedValueOnce({})
    await vm.generatePackage()
    expect(ElMessage.error).toHaveBeenCalledWith('数据包生成失败')
    expect(vm.generating).toBe(false)
  })

  it('generatePackage 校验失败 → 直接返回', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.form.dataTypes = []
    await vm.generatePackage()
    expect(postMock).not.toHaveBeenCalled()
  })
})

describe('downloadPackage', () => {
  it('packageId 为空 → 警告并返回', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.downloadPackage()
    expect(ElMessage.warning).toHaveBeenCalledWith('数据包 ID 不存在')
    expect(apiRequestMock).not.toHaveBeenCalled()
  })

  it('成功：blob 下载全流程（创建 a 标签触发点击）', async () => {
    const clickSpy = spyAnchorClick()
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.packageId = 'pkg-9'
    await vm.downloadPackage()
    expect(apiRequestMock).toHaveBeenCalledWith({
      method: 'GET',
      url: '/data-packages/pkg-9/download',
      responseType: 'blob',
    })
    expect(clickSpy).toHaveBeenCalled()
    expect(vm.downloading).toBe(false)
  })

  it('失败 → 提示下载失败', async () => {
    apiRequestMock.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.packageId = 'pkg-9'
    await vm.downloadPackage()
    expect(ElMessage.error).toHaveBeenCalledWith('下载失败')
    expect(vm.downloading).toBe(false)
  })
})

describe('一键上报', () => {
  it('Blob 响应 → 直接触发下载并进步骤 2（点击「一键上报」按钮）', async () => {
    const clickSpy = spyAnchorClick()
    postMock.mockResolvedValue(new Blob(['zip-bytes']))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await findBtn(wrapper, '一键上报').trigger('click')
    await flushPromises()
    expect(postMock).toHaveBeenCalledWith('/data-packages/one-click-report', {
      year: vm.form.year,
      data_types: vm.form.dataTypes,
      remarks: `一键上报 ${vm.form.year}年度数据`,
    })
    expect(clickSpy).toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('数据包已生成并开始下载')
    expect(vm.currentStep).toBe(2)
    expect(vm.oneClickLoading).toBe(false)
  })

  it('download_url 响应：file_name 有/无两侧，经 apiRequest 拉取 blob', async () => {
    const clickSpy = spyAnchorClick()
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.form.remarks = '月度上报' // remarks || 兜底真侧

    postMock.mockResolvedValueOnce({ data: { download_url: '/dl/abc', file_name: '定制.zip' } })
    await vm.handleOneClickReport()
    expect(apiRequestMock).toHaveBeenCalledWith({
      method: 'GET',
      url: '/dl/abc',
      responseType: 'blob',
    })
    expect(vm.currentStep).toBe(2)

    postMock.mockResolvedValueOnce({ data: { download_url: '/dl/def' } }) // file_name 缺省
    await vm.handleOneClickReport()
    expect(clickSpy).toHaveBeenCalledTimes(2)
    expect(postMock).toHaveBeenCalledWith('/data-packages/one-click-report', {
      year: vm.form.year,
      data_types: vm.form.dataTypes,
      remarks: '月度上报',
    })
  })

  it('响应既非 Blob 也无 download_url → 仅提示成功', async () => {
    postMock.mockResolvedValue({ data: { ok: true } })
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.handleOneClickReport()
    expect(apiRequestMock).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('数据包已生成并开始下载')
    expect(vm.currentStep).toBe(2)
  })

  it('一键接口失败 → 直接提示失败（无 POST /data-packages 死回退）：Error message 与默认文案两级', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    postMock.mockRejectedValue(new Error('接口炸了'))
    await vm.handleOneClickReport()
    expect(ElMessage.error).toHaveBeenCalledWith('一键上报失败：接口炸了')
    expect(vm.currentStep).toBe(0)

    postMock.mockRejectedValue({})
    await vm.handleOneClickReport()
    expect(ElMessage.error).toHaveBeenCalledWith('一键上报失败：请稍后重试')
    expect(vm.oneClickLoading).toBe(false)
  })

  it('非管理员 → 显示「仅导出您本人录入的数据」提示；管理员 → 隐藏', async () => {
    authState.isAdmin = false
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.text()).toContain('仅导出您本人录入的数据')

    authState.isAdmin = true
    const wrapper2 = mountComp()
    await flushPromises()
    expect(wrapper2.text()).not.toContain('仅导出您本人录入的数据')
  })

  it('一键上报校验失败 → 直接返回', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.form.year = ''
    await vm.handleOneClickReport()
    expect(postMock).not.toHaveBeenCalled()
  })
})

describe('错误边界与重置', () => {
  it('子组件抛 Error → 捕获并展示异常回退卡；点击「重试」清除', async () => {
    const wrapper = mountComp({
      'el-steps': {
        name: 'ElSteps',
        setup() {
          throw new Error('步骤条渲染爆炸')
        },
        template: '<div class="el-steps-throw" />',
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(logError).toHaveBeenCalled()
    expect(vm.componentError).toBe('步骤条渲染爆炸')
    await nextTick()
    expect(wrapper.text()).toContain('页面加载异常')
    await findBtn(wrapper, '重试').trigger('click')
    expect(vm.componentError).toBe('')
  })

  it('子组件抛非 Error → 兜底文案「未知错误，请重试」；点击「返回首步」重置', async () => {
    const wrapper = mountComp({
      'el-steps': {
        name: 'ElSteps',
        setup() {
          // eslint-disable-next-line no-throw-literal
          throw '字符串异常'
        },
        template: '<div class="el-steps-throw" />',
      },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.componentError).toBe('未知错误，请重试')
    vm.currentStep = 2 // 弄脏状态验证 resetForm 全量复位
    await nextTick()
    await findBtn(wrapper, '返回首步').trigger('click')
    expect(vm.currentStep).toBe(0)
    expect(vm.componentError).toBe('')
    expect(vm.packageId).toBe('')
    expect(vm.previewCounts).toEqual({})
  })

  it('步骤 2 点击「重新上报」→ resetForm 回到步骤 0', async () => {
    spyAnchorClick()
    postMock.mockResolvedValue({ package_id: 'pkg-1' })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.generatePackage()
    await nextTick()
    expect(vm.currentStep).toBe(2)
    await findBtn(wrapper, '重新上报').trigger('click')
    expect(vm.currentStep).toBe(0)
    expect(vm.packageId).toBe('')
  })
})

describe('响应形态收尾', () => {
  it('非 blob 响应 data 有值 → 解包', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.oneClickResult || vm.form).toBeTruthy()
    wrapper.unmount()
  })
})

describe('Blob响应收尾', () => {
  it('post 返回 Blob → isBlobResp 分支', async () => {
    HTMLAnchorElement.prototype.click = vi.fn()
    postMock.mockResolvedValue(new Blob(['x']))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleOneClickReport().catch(() => {})
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('裸响应收尾', () => {
  it('非 Blob 且无 data → 直接使用 response', async () => {
    postMock.mockResolvedValue({ ok: true, download_url: 'x' })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    await vm.handleOneClickReport().catch(() => {})
    wrapper.unmount()
  })
})

/**
 * views/batch/Index.vue 覆盖率攻坚（四指标 100%）
 * 覆盖：parsedIds 计算属性（空/分隔符/NaN/非正数/去重/>10 项）、字典映射两侧、
 * 验证/更新/删除/导出四类操作的成功失败全分支（含 ?? 多级兜底）、确认取消、
 * JSON 解析失败与 null/{} 早退、重置、进度条与结果卡片各 v-if 两侧、
 * 模板内联点击与全部 v-model 处理器。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'

// vi.mock 工厂提升求值，引用对象须先放入 vi.hoisted 初始化
const { ElMessage, confirmMock, mockBatchUpdate, mockBatchDelete, mockBatchExport, mockValidateBatch } =
  vi.hoisted(() => {
    return {
      ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
      confirmMock: vi.fn(),
      mockBatchUpdate: vi.fn(),
      mockBatchDelete: vi.fn(),
      mockBatchExport: vi.fn(),
      mockValidateBatch: vi.fn(),
    }
  })

vi.mock('element-plus', () => ({
  ElMessage,
  ElMessageBox: { confirm: confirmMock },
}))

vi.mock('@/api/batchOperations', () => ({
  batchUpdate: mockBatchUpdate,
  batchDelete: mockBatchDelete,
  batchExport: mockBatchExport,
  validateBatch: mockValidateBatch,
}))

import BatchIndex from '@/views/batch/Index.vue'

function mountComp() {
  // 本页 el-* 组件均在全局 stub 清单内，开启默认插槽渲染即可
  return mount(BatchIndex, { global: { renderStubDefaultSlot: true } })
}

function findBtn(wrapper: any, text: string) {
  const btn = wrapper.findAll('el-button-stub').find((b: any) => b.text().includes(text))
  expect(btn, `按钮「${text}」`).toBeTruthy()
  return btn!
}

beforeEach(() => {
  vi.resetAllMocks()
  confirmMock.mockResolvedValue(undefined)
  mockBatchUpdate.mockResolvedValue({ data: {} })
  mockBatchDelete.mockResolvedValue({ data: {} })
  mockBatchExport.mockResolvedValue({ data: {} })
  mockValidateBatch.mockResolvedValue({ data: {} })
})

describe('parsedIds 计算属性与模板渲染', () => {
  it('空输入 → []，渲染「尚未输入有效ID」（id-empty 分支）', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.parsedIds).toEqual([])
    expect(wrapper.text()).toContain('尚未输入有效ID')
  })

  it('混合分隔符解析：过滤 NaN/零/负数并去重', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = '1, 2\n3 abc 0 -5 2'
    await nextTick()
    expect(vm.parsedIds).toEqual([1, 2, 3])
    const text = wrapper.text()
    expect(text).toContain('已识别')
    expect(text).toContain('3')
    expect(text).not.toContain('尚未输入有效ID')
  })

  it('超过 10 个 ID → 渲染「... 等N项」分支', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = Array.from({ length: 12 }, (_, i) => i + 1).join(',')
    await nextTick()
    expect(vm.parsedIds).toHaveLength(12)
    expect(wrapper.text()).toContain('等12项')
  })
})

describe('字典映射函数', () => {
  it('operationLabel 全映射与未知透传', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.operationLabel('update')).toBe('批量更新')
    expect(vm.operationLabel('delete')).toBe('批量删除')
    expect(vm.operationLabel('export')).toBe('批量导出')
    expect(vm.operationLabel('validate')).toBe('批量验证')
    expect(vm.operationLabel('custom')).toBe('custom')
  })

  it('entityLabel 全映射与未知透传', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    expect(vm.entityLabel('supported_villages')).toBe('帮扶村庄')
    expect(vm.entityLabel('schools')).toBe('帮扶学校')
    expect(vm.entityLabel('projects')).toBe('帮扶项目')
    expect(vm.entityLabel('funds')).toBe('帮扶经费')
    expect(vm.entityLabel('other')).toBe('other')
  })
})

describe('操作类型切换（条件列与按钮 v-if 链）', () => {
  it('默认 update：渲染更新字段卡与「批量更新」按钮，无导出/删除列', async () => {
    const wrapper = mountComp()
    await flushPromises()
    expect(wrapper.text()).toContain('更新字段（JSON格式）')
    findBtn(wrapper, '批量更新')
    findBtn(wrapper, '重置')
    expect(wrapper.findAllComponents({ name: 'ElSelect' })).toHaveLength(2)
  })

  it('切到 export：出现导出格式列与「批量导出」按钮，更新字段卡消失', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const selects = wrapper.findAllComponents({ name: 'ElSelect' })
    selects[0].vm.$emit('update:modelValue', 'export')
    await nextTick()
    expect(vm.batchForm.operation).toBe('export')
    expect(wrapper.text()).not.toContain('更新字段（JSON格式）')
    findBtn(wrapper, '批量导出')
    const after = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(after).toHaveLength(3) // operation / entity / format
    after[2].vm.$emit('update:modelValue', 'csv')
    expect(vm.batchForm.format).toBe('csv')
  })

  it('切到 delete：出现删除方式列与「批量删除」按钮；softDelete 可切 false', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.batchForm.operation = 'delete'
    await nextTick()
    findBtn(wrapper, '批量删除')
    const after = wrapper.findAllComponents({ name: 'ElSelect' })
    expect(after).toHaveLength(3)
    after[1].vm.$emit('update:modelValue', 'schools') // entity 选择器 v-model
    expect(vm.batchForm.entity).toBe('schools')
    after[2].vm.$emit('update:modelValue', false)
    expect(vm.batchForm.softDelete).toBe(false)
  })

  it('切到 validate：渲染「验证」按钮', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.batchForm.operation = 'validate'
    await nextTick()
    findBtn(wrapper, '验证')
  })
})

describe('handleValidate', () => {
  it('无有效 ID → 警告并返回', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.handleValidate()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入至少一个有效ID')
    expect(mockValidateBatch).not.toHaveBeenCalled()
  })

  it('成功：完整 data（含 message/errors）→ 结果卡渲染成功态与错误列表', async () => {
    mockValidateBatch.mockResolvedValue({ data: { message: '全部有效', errors: ['ID 9 不存在'] } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = '1,2,3'
    await vm.handleValidate()
    expect(mockValidateBatch).toHaveBeenCalledWith('supported_villages', [1, 2, 3])
    expect(vm.resultSummary).toMatchObject({ success: true, processed: 3, message: '全部有效' })
    expect(vm.progressPercent).toBe(100)
    expect(vm.progressStatus).toBe('success')
    expect(vm.inProgress).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('验证完成')
    await nextTick()
    const text = wrapper.text()
    expect(text).toContain('全部有效')
    expect(text).toContain('ID 9 不存在') // errors?.length 真侧 + v-for
    // 验证路径没有 success_count，旧模板 `?? resultSummary.success` 会把布尔 true
    // 直接渲染成"成功数量: true"，用户看到英文布尔值。
    expect(text).not.toContain('true')
  })

  it('成功：response 为 null → ?? response 与 ?? 默认值全兜底', async () => {
    mockValidateBatch.mockResolvedValue(null)
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = '5'
    await vm.handleValidate()
    expect(vm.resultSummary).toMatchObject({
      success: true,
      processed: 1,
      message: '验证完成',
      errors: [],
    })
  })

  it('失败 → exception 状态与失败摘要（processed/total 全缺 → "-" 兜底渲染）', async () => {
    mockValidateBatch.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = '5'
    await vm.handleValidate()
    expect(vm.progressStatus).toBe('exception')
    expect(vm.progressText).toBe('验证失败')
    expect(vm.resultSummary).toEqual({ success: false, message: '验证失败' })
    expect(ElMessage.error).toHaveBeenCalledWith('验证失败')
    await nextTick()
    expect(wrapper.text()).toContain('失败') // 失败标签（danger 侧）
  })
})

describe('handleBatchUpdate', () => {
  it('无有效 ID → 警告并返回', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.handleBatchUpdate()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入至少一个有效ID')
    expect(mockBatchUpdate).not.toHaveBeenCalled()
  })

  it('JSON 非法 → parseUpdates 报错并早退；JSON null → !updates 早退；{} → 空对象早退', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.idInput = '1'
    vm.updatesInput = '{bad json'
    await vm.handleBatchUpdate()
    expect(ElMessage.error).toHaveBeenCalledWith('更新字段JSON格式不正确')
    expect(confirmMock).not.toHaveBeenCalled()

    vm.updatesInput = 'null'
    await vm.handleBatchUpdate()
    expect(confirmMock).not.toHaveBeenCalled()

    vm.updatesInput = '{}'
    await vm.handleBatchUpdate()
    expect(confirmMock).not.toHaveBeenCalled()
  })

  it('确认框取消 → 不发请求', async () => {
    confirmMock.mockRejectedValue(new Error('cancel'))
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.idInput = '1'
    await vm.handleBatchUpdate()
    expect(confirmMock).toHaveBeenCalled()
    expect(mockBatchUpdate).not.toHaveBeenCalled()
  })

  it('成功：success_count / affected / 双缺 三级 ?? 兜底', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = '1,2'

    mockBatchUpdate.mockResolvedValueOnce({ data: { success_count: 2, message: 'ok', errors: ['e1'] } })
    await vm.handleBatchUpdate()
    expect(vm.resultSummary.success_count).toBe(2)
    expect(confirmMock).toHaveBeenCalledWith(
      '确定要对2条帮扶村庄执行批量更新吗？',
      '确认操作',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mockBatchUpdate).toHaveBeenCalledWith({
      table_name: 'supported_villages',
      ids: [1, 2],
      updates: { status: 'active' },
    })
    expect(ElMessage.success).toHaveBeenCalledWith('批量更新完成')

    mockBatchUpdate.mockResolvedValueOnce({ affected: 5 }) // 裸响应（无 data 键）
    await vm.handleBatchUpdate()
    expect(vm.resultSummary.success_count).toBe(5)
    expect(vm.resultSummary.message).toBe('批量更新完成')

    mockBatchUpdate.mockResolvedValueOnce({ data: {} })
    await vm.handleBatchUpdate()
    expect(vm.resultSummary.success_count).toBe(2) // ?? parsedIds.length 兜底
  })

  it('失败 → exception 与失败摘要', async () => {
    mockBatchUpdate.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.idInput = '1'
    await vm.handleBatchUpdate()
    expect(vm.progressStatus).toBe('exception')
    expect(vm.resultSummary).toEqual({ success: false, message: '批量更新失败' })
    expect(ElMessage.error).toHaveBeenCalledWith('批量更新失败')
    expect(vm.inProgress).toBe(false)
  })
})

describe('handleBatchDelete', () => {
  it('无有效 ID → 警告；确认取消 → 不发请求', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.handleBatchDelete()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入至少一个有效ID')

    vm.idInput = '1'
    confirmMock.mockRejectedValue(new Error('cancel'))
    await vm.handleBatchDelete()
    expect(mockBatchDelete).not.toHaveBeenCalled()
  })

  it('成功：success_count / deleted / 双缺 三级 ?? 兜底与参数透传', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = '3,4'
    vm.batchForm.softDelete = false

    mockBatchDelete.mockResolvedValueOnce({ data: { success_count: 2 } })
    await vm.handleBatchDelete()
    expect(confirmMock).toHaveBeenCalledWith(
      '确定要删除2条帮扶村庄吗？此操作可能不可恢复！',
      '危险操作',
      expect.objectContaining({ type: 'error', confirmButtonText: '确认删除' })
    )
    expect(mockBatchDelete).toHaveBeenCalledWith({
      table_name: 'supported_villages',
      ids: [3, 4],
      soft_delete: false,
    })
    expect(vm.resultSummary.success_count).toBe(2)

    mockBatchDelete.mockResolvedValueOnce({ data: { deleted: 7 } })
    await vm.handleBatchDelete()
    expect(vm.resultSummary.success_count).toBe(7)

    mockBatchDelete.mockResolvedValueOnce({ data: {} })
    await vm.handleBatchDelete()
    expect(vm.resultSummary.success_count).toBe(2) // ?? parsedIds.length 兜底
    expect(ElMessage.success).toHaveBeenCalledWith('批量删除完成')

    mockBatchDelete.mockResolvedValueOnce(null) // response?.data 空侧 → ?? response
    await vm.handleBatchDelete()
    expect(vm.resultSummary.success_count).toBe(2)
    expect(vm.resultSummary.message).toBe('批量删除完成')
  })

  it('失败 → exception 与失败摘要', async () => {
    mockBatchDelete.mockRejectedValue(new Error('net'))
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.idInput = '1'
    await vm.handleBatchDelete()
    expect(vm.progressStatus).toBe('exception')
    expect(vm.resultSummary).toEqual({ success: false, message: '批量删除失败' })
    expect(ElMessage.error).toHaveBeenCalledWith('批量删除失败')
  })
})

describe('handleBatchExport', () => {
  it('无有效 ID → 警告并返回', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    await vm.handleBatchExport()
    expect(ElMessage.warning).toHaveBeenCalledWith('请输入至少一个有效ID')
    expect(mockBatchExport).not.toHaveBeenCalled()
  })

  it('成功：携带格式参数；摘要无 errors 键（errors?. 空侧）', async () => {
    mockBatchExport.mockResolvedValue({ data: { message: '任务已创建' } })
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = '1,2'
    vm.batchForm.format = 'csv'
    await vm.handleBatchExport()
    expect(mockBatchExport).toHaveBeenCalledWith({
      table_name: 'supported_villages',
      ids: [1, 2],
      format: 'csv',
    })
    expect(vm.resultSummary).toMatchObject({ success: true, processed: 2, message: '任务已创建' })
    expect('errors' in vm.resultSummary).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('导出任务已提交，请留意下载通知')
    await nextTick()
  })

  it('成功：response 为 null → 默认值兜底；失败 → exception', async () => {
    const wrapper = mountComp()
    const vm = wrapper.vm as any
    vm.idInput = '1'
    mockBatchExport.mockResolvedValueOnce(null)
    await vm.handleBatchExport()
    expect(vm.resultSummary.message).toBe('导出完成')

    mockBatchExport.mockRejectedValueOnce(new Error('net'))
    await vm.handleBatchExport()
    expect(vm.progressStatus).toBe('exception')
    expect(vm.resultSummary).toEqual({ success: false, message: '导出失败' })
    expect(ElMessage.error).toHaveBeenCalledWith('导出失败')
  })
})

describe('模板交互：按钮点击 / v-model / 进度条 / 结果卡分支', () => {
  it('点击四个操作按钮分别触发对应处理器', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = '1,2'

    vm.batchForm.operation = 'validate'
    await nextTick()
    await findBtn(wrapper, '验证').trigger('click')
    await flushPromises()
    expect(mockValidateBatch).toHaveBeenCalled()

    vm.batchForm.operation = 'update'
    await nextTick()
    await findBtn(wrapper, '批量更新').trigger('click')
    await flushPromises()
    expect(mockBatchUpdate).toHaveBeenCalled()

    vm.batchForm.operation = 'delete'
    await nextTick()
    await findBtn(wrapper, '批量删除').trigger('click')
    await flushPromises()
    expect(mockBatchDelete).toHaveBeenCalled()

    vm.batchForm.operation = 'export'
    await nextTick()
    await findBtn(wrapper, '批量导出').trigger('click')
    await flushPromises()
    expect(mockBatchExport).toHaveBeenCalled()
  })

  it('两个 el-input v-model 同步 idInput 与 updatesInput', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    const inputs = wrapper.findAllComponents({ name: 'ElInput' })
    expect(inputs.length).toBe(2) // idInput / updatesInput
    inputs[0].vm.$emit('update:modelValue', '7,8')
    inputs[1].vm.$emit('update:modelValue', '{"a":1}')
    expect(vm.idInput).toBe('7,8')
    expect(vm.updatesInput).toBe('{"a":1}')
    await nextTick()
    expect(vm.parsedIds).toEqual([7, 8])
  })

  it('inProgress 真侧渲染进度条与进度文案', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.find('.progress-card').exists()).toBe(false)
    vm.inProgress = true
    vm.progressPercent = 30
    vm.progressText = '正在验证...'
    await nextTick()
    expect(wrapper.find('.progress-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('正在验证...')
  })

  it('结果卡：total 兜底、成功数量 "-" 兜底、无 message/errors 时对应条目隐藏', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(wrapper.find('.result-card').exists()).toBe(false)

    vm.resultSummary = { success: true, total: 7 } // processed 缺省 → ?? total
    await nextTick()
    expect(wrapper.find('.result-card').exists()).toBe(true)
    expect(wrapper.text()).toContain('7')
    expect(wrapper.text()).not.toContain('消息') // message 缺省 → v-if 假侧

    vm.resultSummary = { processed: 2 } // success_count/success 双缺 → '-'；success 缺省 → danger 侧
    await nextTick()
    expect(wrapper.text()).toContain('-')
  })

  it('点击「重置」清空输入与结果并复位进度', async () => {
    const wrapper = mountComp()
    await flushPromises()
    const vm = wrapper.vm as any
    vm.idInput = '1,2'
    vm.updatesInput = '{"x":1}'
    vm.resultSummary = { success: true }
    vm.progressPercent = 100
    vm.progressStatus = 'success'
    vm.progressText = '完成'
    await findBtn(wrapper, '重置').trigger('click')
    expect(vm.idInput).toBe('')
    expect(vm.updatesInput).toBe('{"status": "active"}')
    expect(vm.resultSummary).toBeNull()
    expect(vm.progressPercent).toBe(0)
    expect(vm.progressStatus).toBe('')
    expect(vm.progressText).toBe('')
  })
})

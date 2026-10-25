import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { ocrVoucherMock } = vi.hoisted(() => ({ ocrVoucherMock: vi.fn() }))
vi.mock('@/api/funds', () => ({ fundApi: { ocrVoucher: ocrVoucherMock } }))

import OcrVoucherSuggest from '@/components/funds/OcrVoucherSuggest.vue'

const FAKE_FILE = { name: 'voucher.jpg' } as unknown as File

function mountSuggest(props: Record<string, unknown> = {}) {
  return mount(OcrVoucherSuggest, {
    props,
    global: {
      stubs: {
        'el-upload': {
          props: ['httpRequest', 'showFileList', 'accept'],
          emits: ['http-request'],
          template: `<div class="upload-stub">
            <button class="upload-trigger" @click="$props.httpRequest({ file: { name: 'v.jpg' } })">up</button><button class="upload-empty" @click="$props.httpRequest({})">no-file</button>
            <slot />
          </div>`,
        },
        'el-button': {
          props: ['loading', 'disabled'],
          template:
            '<button class="btn-stub" :data-loading="loading" @click="$emit(\'click\')"><slot /></button>',
        },
        'el-tag': { props: ['type'], template: '<span class="tag-stub" :data-type="type"><slot /></span>' },
        'el-alert': { props: ['title'], template: '<div class="alert-stub">{{ title }}</div>' },
      },
    },
  })
}

async function upload(wrapper: ReturnType<typeof mountSuggest>) {
  await wrapper.find('.upload-trigger').trigger('click')
  await flushPromises()
}

beforeEach(() => {
  ocrVoucherMock.mockReset()
})

describe('OcrVoucherSuggest', () => {
  it('初始显示引导文案（尚未上传）', () => {
    const wrapper = mountSuggest()
    expect(wrapper.find('[data-testid="ocr-empty"]').exists()).toBe(true)
    expect(ocrVoucherMock).not.toHaveBeenCalled()
  })

  it('上传后按字段给出建议（当前值 → 识别值 + 置信度）', async () => {
    ocrVoucherMock.mockResolvedValue({
      amount: '¥1,234.50元',
      date: '2024年1月2日',
      confidence: 0.92,
      engine: 'rapidocr',
    })
    const wrapper = mountSuggest({ current: { amount: '100', transfer_date: '' } })
    await upload(wrapper)

    expect(ocrVoucherMock).toHaveBeenCalledWith(expect.objectContaining({ name: 'v.jpg' }))
    const amountRow = wrapper.find('[data-testid="ocr-row-amount"]')
    expect(amountRow.text()).toContain('1234.50')
    expect(amountRow.text()).toContain('100')
    expect(amountRow.find('.tag-stub').text()).toBe('高置信')
    expect(wrapper.find('[data-testid="ocr-engine"]').text()).toContain('rapidocr')
  })

  it('与当前值相同 → 标注"与当前值相同"且不提供采纳按钮', async () => {
    ocrVoucherMock.mockResolvedValue({ amount: '100', confidence: 0.95 })
    const wrapper = mountSuggest({ current: { amount: '100' } })
    await upload(wrapper)

    expect(wrapper.find('[data-testid="ocr-row-amount"]').text()).toContain('与当前值相同')
    expect(wrapper.find('[data-testid="ocr-adopt-amount"]').exists()).toBe(false)
  })

  it('采纳单个字段 → emit apply 并移除该行', async () => {
    ocrVoucherMock.mockResolvedValue({ amount: '100', date: '2024-01-02', confidence: 0.7 })
    const wrapper = mountSuggest()
    await upload(wrapper)

    await wrapper.find('[data-testid="ocr-adopt-amount"]').trigger('click')

    expect(wrapper.emitted('apply')?.[0]).toEqual([{ key: 'amount', value: '100' }])
    expect(wrapper.find('[data-testid="ocr-row-amount"]').exists()).toBe(false)
  })

  it('忽略 → 仅移除该行，不 emit', async () => {
    ocrVoucherMock.mockResolvedValue({ amount: '100', date: '2024-01-02', confidence: 0.7 })
    const wrapper = mountSuggest()
    await upload(wrapper)

    await wrapper.find('[data-testid="ocr-ignore-transfer_date"]').trigger('click')

    expect(wrapper.find('[data-testid="ocr-row-transfer_date"]').exists()).toBe(false)
    expect(wrapper.emitted('apply')).toBeFalsy()
  })

  it('全部采纳 → 一次 emit apply-all 并清空列表', async () => {
    ocrVoucherMock.mockResolvedValue({ amount: '100', date: '2024-01-02', confidence: 0.9 })
    const wrapper = mountSuggest()
    await upload(wrapper)

    await wrapper.find('[data-testid="ocr-adopt-all"]').trigger('click')

    expect(wrapper.emitted('apply-all')?.[0]).toEqual([{ amount: '100', transfer_date: '2024-01-02' }])
    expect(wrapper.find('[data-testid="ocr-list"]').exists()).toBe(false)
  })

  it('识别不出金额/日期 → 提示手工录入', async () => {
    ocrVoucherMock.mockResolvedValue({ text: '一片模糊', confidence: 0.2 })
    const wrapper = mountSuggest()
    await upload(wrapper)

    expect(wrapper.find('[data-testid="ocr-error"]').text()).toContain('未能识别出金额或日期')
  })

  it('503 引擎不可用 → 友善提示（不阻断经费业务）', async () => {
    ocrVoucherMock.mockRejectedValue({ status: 503 })
    const wrapper = mountSuggest()
    await upload(wrapper)

    expect(wrapper.find('[data-testid="ocr-error"]').text()).toContain('引擎不可用')
  })

  it('其它错误取 detail 文案；无 detail 给通用兜底', async () => {
    ocrVoucherMock.mockRejectedValueOnce({ detail: '图片格式不支持' })
    const first = mountSuggest()
    await upload(first)
    expect(first.find('[data-testid="ocr-error"]').text()).toContain('图片格式不支持')

    ocrVoucherMock.mockRejectedValueOnce({})
    const second = mountSuggest()
    await upload(second)
    expect(second.find('[data-testid="ocr-error"]').text()).toContain('识别失败')
  })

  it('上传回调缺 file 时直接返回（不请求接口）', async () => {
    const wrapper = mountSuggest()
    await wrapper.find('.upload-empty').trigger('click')
    await flushPromises()
    expect(ocrVoucherMock).not.toHaveBeenCalled()
  })

  it('接口返回空体（null）→ 按未识别处理，不崩', async () => {
    ocrVoucherMock.mockResolvedValue(null)
    const wrapper = mountSuggest()
    await upload(wrapper)
    expect(wrapper.find('[data-testid="ocr-error"]').text()).toContain('未能识别出金额或日期')
  })

  it('异常值为 null / 携带 response.status=503 → 都能翻译成人话', async () => {
    ocrVoucherMock.mockRejectedValueOnce(null)
    const first = mountSuggest()
    await upload(first)
    expect(first.find('[data-testid="ocr-error"]').text()).toContain('识别失败')

    ocrVoucherMock.mockRejectedValueOnce({ response: { status: 503 } })
    const second = mountSuggest()
    await upload(second)
    expect(second.find('[data-testid="ocr-error"]').text()).toContain('引擎不可用')
  })

  it('上传中按钮进入 loading（上传完成复位）', async () => {
    let resolve: (v: unknown) => void = () => {}
    ocrVoucherMock.mockImplementation(() => new Promise((r) => (resolve = r)))
    const wrapper = mountSuggest()

    const pending = wrapper.find('.upload-trigger').trigger('click')
    await pending
    // 请求未完成时按钮应处于 loading
    expect(wrapper.find('[data-testid="ocr-upload-btn"]').attributes('data-loading')).toBe('true')

    resolve({ amount: '1', confidence: 0.9 })
    await flushPromises()
    expect(wrapper.find('[data-testid="ocr-upload-btn"]').attributes('data-loading')).toBe('false')
  })
})

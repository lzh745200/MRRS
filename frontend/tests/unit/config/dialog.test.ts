import { describe, it, expect } from 'vitest'
import {
  DIALOG_SM,
  DIALOG_MD,
  DIALOG_LG,
  DIALOG_WIDTH,
  FORM_LABEL_WIDTH,
} from '@/config/dialog'

describe('config/dialog 弹窗三档常量', () => {
  it('三档取值与 tokens.scss --dialog-* 对齐（480/720/960）', () => {
    expect(DIALOG_SM).toBe('480px')
    expect(DIALOG_MD).toBe('720px')
    expect(DIALOG_LG).toBe('960px')
  })

  it('DIALOG_WIDTH 别名映射一致', () => {
    expect(DIALOG_WIDTH.sm).toBe(DIALOG_SM)
    expect(DIALOG_WIDTH.md).toBe(DIALOG_MD)
    expect(DIALOG_WIDTH.lg).toBe(DIALOG_LG)
  })

  it('表单标签宽两档', () => {
    expect(FORM_LABEL_WIDTH.normal).toBe(100)
    expect(FORM_LABEL_WIDTH.wide).toBe(120)
  })
})

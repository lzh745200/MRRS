import { describe, it, expect } from 'vitest'
import { permission } from '@/directives/permission'

describe('v-permission 指令', () => {
  it('导出为合法 Vue 指令对象：mounted/updated 钩子成对且为函数（可逆隐藏的契约前提）', () => {
    expect(permission).toBeTruthy()
    expect(typeof permission.mounted).toBe('function')
    expect(typeof permission.updated).toBe('function')
  })
})

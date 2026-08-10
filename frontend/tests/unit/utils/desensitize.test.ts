import { describe, it, expect } from 'vitest'
import {
  maskPhone,
  maskIdCard,
  maskName,
  maskBankCard,
  maskEmail,
  maskAddress,
  maskAmount,
  maskMilitaryID,
  getDesensitizeLevel,
  desensitizeByLevel,
  desensitizeByRole,
  autoDesensitize,
  desensitizeObject,
  DesensitizeLevel,
} from '@/utils/desensitize'

describe('desensitize edge branches', () => {
  it('maskBankCard: null/短卡号返回原值', () => {
    expect(maskBankCard(null)).toBe('')
    expect(maskBankCard('123')).toBe('123')
  })
  it('maskEmail: 无@返回原值', () => {
    expect(maskEmail('no-at-sign')).toBe('no-at-sign')
  })
  it('maskAddress: 空地址返回空串', () => {
    expect(maskAddress('')).toBe('')
  })
  it('maskName: 2字姓名', () => {
    expect(maskName('张三')).toBe('张*')
  })
  it('maskAmount: showAmount 数字格式', () => {
    expect(maskAmount(12345, true)).toBe('12,345')
  })
})

describe('desensitize', () => {
  describe('maskPhone', () => {
    it('11位手机号: 138****1234', () => {
      expect(maskPhone('13812341234')).toBe('138****1234')
    })
    it('少于7位返回原值', () => {
      expect(maskPhone('12345')).toBe('12345')
    })
    it('null 返回空', () => {
      expect(maskPhone(null)).toBe('')
    })
    it('undefined 返回空', () => {
      expect(maskPhone(undefined)).toBe('')
    })
  })

  describe('maskIdCard', () => {
    it('18位身份证', () => {
      const result = maskIdCard('110101199001011234')
      expect(result).toContain('110')
      expect(result).toContain('1234')
      expect(result).toContain('*')
    })
    it('15位身份证', () => {
      const result = maskIdCard('110101900101123')
      expect(result).toContain('*')
    })
    it('null 返回空', () => {
      expect(maskIdCard(null)).toBe('')
    })
  })

  describe('maskName', () => {
    it('单字姓名: *', () => {
      expect(maskName('张')).toBe('*')
    })
    it('2字姓名: 张*', () => {
      expect(maskName('张三')).toBe('张*')
    })
    it('3字姓名: 张*明', () => {
      expect(maskName('张小明')).toBe('张*明')
    })
    it('null 返回空', () => {
      expect(maskName(null)).toBe('')
    })
  })

  describe('maskBankCard', () => {
    it('银行卡保留前4后4', () => {
      const result = maskBankCard('6222021234567890123')
      expect(result).toContain('6222')
      expect(result).toContain('0123')
      expect(result).toContain('*')
    })
    it('null 返回空', () => {
      expect(maskBankCard(null)).toBe('')
    })
  })

  describe('maskEmail', () => {
    it('邮箱脱敏', () => {
      const result = maskEmail('alice@example.com')
      expect(result).toContain('@example.com')
      expect(result).toContain('*')
    })
    it('null 返回空', () => {
      expect(maskEmail(null)).toBe('')
    })
  })

  describe('maskAddress', () => {
    it('地址保留前3位+****', () => {
      const result = maskAddress('贵州省黔南州都匀市')
      expect(result).toContain('贵州省')
      expect(result).toContain('****')
    })
    it('少于等于4位时返回首字符+****', () => {
      const result = maskAddress('北京市')
      expect(result).toContain('****')
    })
    it('null 返回空', () => {
      expect(maskAddress(null)).toBe('')
    })
  })

  describe('maskAmount', () => {
    it('showAmount=true 数字格式化为字符串', () => {
      expect(maskAmount(100, true)).toContain('100')
    })
    it('showAmount=false 返回 ****', () => {
      expect(maskAmount(100, false)).toBe('****')
    })
    it('null 返回 ****', () => {
      expect(maskAmount(null, true)).toBe('****')
    })
    it('字符串 + showAmount=true 返回字符串', () => {
      expect(maskAmount('100', true)).toBe('100')
    })
  })

  describe('maskMilitaryID', () => {
    it('军号保留首2尾2', () => {
      const result = maskMilitaryID('1234567890')
      expect(result.startsWith('12')).toBe(true)
      expect(result.endsWith('90')).toBe(true)
      expect(result).toContain('****')
    })
    it('null 返回空', () => {
      expect(maskMilitaryID(null)).toBe('')
    })
  })

  describe('getDesensitizeLevel', () => {
    it('super_admin/admin -> FULL', () => {
      expect(getDesensitizeLevel('super_admin')).toBe(DesensitizeLevel.FULL)
      expect(getDesensitizeLevel('admin')).toBe(DesensitizeLevel.FULL)
    })
    it('viewer -> HIDDEN', () => {
      expect(getDesensitizeLevel('viewer')).toBe(DesensitizeLevel.HIDDEN)
    })
    it('历史角色归一化: manager/approval_leader/editor->FULL, operator->PARTIAL', () => {
      expect(getDesensitizeLevel('manager')).toBe(DesensitizeLevel.FULL)
      expect(getDesensitizeLevel('approval_leader')).toBe(DesensitizeLevel.FULL)
      expect(getDesensitizeLevel('editor')).toBe(DesensitizeLevel.FULL)  // 与 roleAccess.ts 一致
      expect(getDesensitizeLevel('operator')).toBe(DesensitizeLevel.PARTIAL)
      expect(getDesensitizeLevel('unknown')).toBe(DesensitizeLevel.PARTIAL)
    })
  })

  describe('desensitizeByLevel', () => {
    it('FULL 级别返回原值字符串', () => {
      expect(desensitizeByLevel('13812341234', 'phone', DesensitizeLevel.FULL)).toBe('13812341234')
    })
    it('HIDDEN 级别返回 ****', () => {
      expect(desensitizeByLevel('13812341234', 'phone', DesensitizeLevel.HIDDEN)).toBe('****')
    })
    it('PARTIAL 级别使用规则', () => {
      const result = desensitizeByLevel('13812341234', 'phone', DesensitizeLevel.PARTIAL)
      expect(result).toContain('*')
    })
    it('null 值', () => {
      expect(desensitizeByLevel(null, 'phone', DesensitizeLevel.PARTIAL)).toBe('')
    })
  })

  describe('desensitizeByRole', () => {
    it('admin 角色不脱敏', () => {
      expect(desensitizeByRole('13812341234', 'phone', 'admin')).toBe('13812341234')
    })
    it('viewer 角色完全隐藏', () => {
      expect(desensitizeByRole('13812341234', 'phone', 'viewer')).toBe('****')
    })
    it('manager 历史角色归一化为 admin -> 不脱敏', () => {
      expect(desensitizeByRole('13812341234', 'phone', 'manager')).toBe('13812341234')
    })
    it('空角色字符串 → normalizeRoleLocal falsy 分支 → PARTIAL 脱敏', () => {
      expect(desensitizeByRole('13812341234', 'phone', '')).toBe('138****1234')
    })
  })

  describe('desensitize 补充分支', () => {
    it('maskEmail 单字符 local → *@domain', () => {
      expect(maskEmail('a@example.com')).toBe('*@example.com')
    })
    it('FULL 级别 + null 值 → 空串 (value?.toString() ?? \'\')', () => {
      expect(desensitizeByLevel(null, 'phone', DesensitizeLevel.FULL)).toBe('')
    })
    it('PARTIAL + 未知类型 → rule 兜底原样返回', () => {
      expect(desensitizeByLevel('123', 'unknown' as any, DesensitizeLevel.PARTIAL)).toBe('123')
      expect(desensitizeByLevel(null, 'unknown' as any, DesensitizeLevel.PARTIAL)).toBe('')
    })
  })

  describe('autoDesensitize', () => {
    it('phone 字段脱敏', () => {
      const result = autoDesensitize('13812341234', 'user_phone', 'operator')
      expect(result).toContain('*')
    })
    it('email 字段脱敏', () => {
      const result = autoDesensitize('alice@example.com', 'user_email', 'operator')
      expect(result).toContain('@')
      expect(result).toContain('*')
    })
    it('未识别字段名原样返回', () => {
      expect(autoDesensitize('some text', 'description', 'operator')).toBe('some text')
    })
    it('null 返回空', () => {
      expect(autoDesensitize(null, 'phone')).toBe('')
    })
    it('无 role 时使用 PARTIAL 规则', () => {
      const result = autoDesensitize('13812341234', 'phone')
      expect(result).toContain('*')
    })
  })

  describe('desensitizeObject', () => {
    it('批量脱敏多个字段', () => {
      const result = desensitizeObject(
        { phone: '13812341234', name: '张三', count: 100 },
        'operator',
      )
      expect(result.phone).toContain('*')
      expect(result.name).toContain('*')
      expect(result.count).toBe(100)
    })
    it('非对象返回原值', () => {
      expect(desensitizeObject(null as any, 'operator')).toBeNull()
    })
  })
})

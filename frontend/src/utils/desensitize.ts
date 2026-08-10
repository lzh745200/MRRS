/**
 * 数据脱敏工具 — 安全增强版
 *
 * 用于前端展示时对敏感信息进行分级脱敏处理。
 * 支持基于用户角色的分级脱敏（管理员可见原文，查看者完全隐藏，其他角色脱敏展示）。
 *
 * 脱敏规则：
 * - 手机号:   138****1234
 * - 身份证:   110***********1234
 * - 姓名:     张*三 / 李*
 * - 银行卡:   6222 **** **** 1234
 * - 邮箱:     z***@example.com
 * - 地址:     贵州省黔南州****
 * - 金额:     ****  (无权限时)
 */

/** 用户角色类型（历史角色由 normalizeRole 归一化） */
export type UserRole = 'super_admin' | 'admin' | 'user' | 'viewer'

/** 脱敏级别 */
export enum DesensitizeLevel {
  /** 完整展示（管理员） */
  FULL = 'full',
  /** 部分脱敏（普通用户） */
  PARTIAL = 'partial',
  /** 完全隐藏（查看者） */
  HIDDEN = 'hidden',
}

// ══════════════════════════════════════════════════════════════
//  基础脱敏函数
// ══════════════════════════════════════════════════════════════

/** 手机号脱敏: 138****1234 */
export function maskPhone(phone: string | null | undefined): string {
  if (!phone || phone.length < 7) return phone ?? ''
  return phone.replace(/(\d{3})\d{4}(\d+)/, '$1****$2')
}

/** 身份证号脱敏: 110***********1234 */
export function maskIdCard(id: string | null | undefined): string {
  if (!id || id.length < 8) return id ?? ''
  return id.replace(/(\d{3})\d+(\d{4})/, '$1***********$2')
}

/** 姓名脱敏: 张*三 / 张* */
export function maskName(name: string | null | undefined): string {
  if (!name) return ''
  if (name.length <= 1) return '*'
  if (name.length === 2) return name[0] + '*'
  return name[0] + '*'.repeat(name.length - 2) + name[name.length - 1]
}

/** 银行卡号脱敏: 6222 **** **** 1234 */
export function maskBankCard(card: string | null | undefined): string {
  if (!card || card.length < 8) return card || ''
  // 处理 16-19 位银行卡号
  return card.replace(/(\d{4})\d{8,12}(\d{4})/, '$1 **** **** $2')
}

/** 邮箱脱敏: z***@example.com */
export function maskEmail(email: string | null | undefined): string {
  if (!email || !email.includes('@')) return email || ''
  const [local, domain] = email.split('@')
  if (local.length <= 1) return '*@' + domain
  return local[0] + '***@' + domain
}

/** 地址脱敏: 贵州省黔南州**** */
export function maskAddress(address: string | null | undefined): string {
  if (!address) return ''
  if (address.length <= 4) return address[0] + '****'
  // 保留前三字符，其余脱敏
  return address.slice(0, 3) + '****'
}

/** 金额脱敏（无权限时完全隐藏，有权限时返回格式化金额） */
export function maskAmount(amount: number | string | null | undefined, showAmount = false): string {
  if (amount === null || amount === undefined) return '****'
  if (showAmount) return typeof amount === 'number' ? amount.toLocaleString() : String(amount)
  return '****'
}

/** 证件编号脱敏 */
export function maskMilitaryID(id: string | null | undefined): string {
  if (!id || id.length < 4) return id || ''
  return id.slice(0, 2) + '****' + id.slice(-2)
}

// ══════════════════════════════════════════════════════════════
//  角色分级脱敏
// ══════════════════════════════════════════════════════════════

/**
 * 根据用户角色确定脱敏级别
 */
export function getDesensitizeLevel(role: UserRole | string): DesensitizeLevel {
  // 历史角色归一化：manager/approval_leader → admin, operator → user
  const normalized = normalizeRoleLocal(role)
  switch (normalized) {
    case 'super_admin':
    case 'admin':
      return DesensitizeLevel.FULL
    case 'viewer':
      return DesensitizeLevel.HIDDEN
    default:
      return DesensitizeLevel.PARTIAL
  }
}

function normalizeRoleLocal(role: string): string {
  const map: Record<string, string> = {
    approval_leader: 'admin',
    manager: 'admin',
    operator: 'user',
  }
  const r = (role || '').toLowerCase()
  return map[r] || r
}

/**
 * 根据脱敏级别处理敏感字段
 *
 * @param value  原始值
 * @param type   字段类型
 * @param level  脱敏级别
 */
export function desensitizeByLevel(
  value: string | number | null | undefined,
  type: keyof typeof desensitizeRules,
  level: DesensitizeLevel
): string {
  // 完整展示
  if (level === DesensitizeLevel.FULL) {
    return value?.toString() ?? ''
  }
  // 完全隐藏
  if (level === DesensitizeLevel.HIDDEN) {
    return '****'
  }
  // 部分脱敏
  const rule = desensitizeRules[type]
  if (rule) {
    return rule(value?.toString() ?? '')
  }
  return value?.toString() ?? ''
}

/**
 * 脱敏规则映射
 */
const desensitizeRules = {
  phone: maskPhone,
  idCard: maskIdCard,
  name: maskName,
  bankCard: maskBankCard,
  email: maskEmail,
  address: maskAddress,
  amount: maskAmount,
  militaryID: maskMilitaryID,
} as const

/**
 * 便捷方法：基于角色对值进行脱敏
 *
 * @example
 * desensitizeByRole("13812341234", "phone", "operator")
 * // => "138****1234"
 *
 * @example
 * desensitizeByRole("张小明", "name", "viewer")
 * // => "****"
 */
export function desensitizeByRole(
  value: string | number | null | undefined,
  type: keyof typeof desensitizeRules,
  role: UserRole | string
): string {
  const level = getDesensitizeLevel(role)
  return desensitizeByLevel(value, type, level)
}

// ══════════════════════════════════════════════════════════════
//  通用自动脱敏（根据字段名智能匹配）
// ══════════════════════════════════════════════════════════════

/** 敏感字段名模式匹配 */
const SENSITIVE_FIELD_PATTERNS: Array<{
  pattern: RegExp
  type: keyof typeof desensitizeRules
}> = [
  { pattern: /phone|tel|mobile|contact/i, type: 'phone' },
  { pattern: /id_card|idcard|identity|id_no|id_number/i, type: 'idCard' },
  { pattern: /bank|account_number|card_no|card_num/i, type: 'bankCard' },
  { pattern: /email|mail/i, type: 'email' },
  { pattern: /name|姓名|fullname|user_name/i, type: 'name' },
  { pattern: /address|addr|住址|地址|location/i, type: 'address' },
  { pattern: /amount|money|金额|balance|fund/i, type: 'amount' },
  { pattern: /military_id|军官证|士兵证|军/i, type: 'militaryID' },
]

/**
 * 通用脱敏：根据字段名自动选择脱敏方式
 *
 * @param value     原始值
 * @param fieldName 字段名
 * @param role      用户角色（可选，默认 partial）
 */
export function autoDesensitize(value: any, fieldName: string, role?: UserRole | string): string {
  if (value === null || value === undefined) return ''
  const str = String(value)
  const lower = fieldName.toLowerCase()

  // 匹配脱敏类型
  for (const { pattern, type } of SENSITIVE_FIELD_PATTERNS) {
    if (pattern.test(lower)) {
      if (role) {
        return desensitizeByRole(str, type, role)
      }
      return desensitizeRules[type](str)
    }
  }

  return str
}

/**
 * 批量脱敏对象中的敏感字段
 *
 * @param obj   数据对象
 * @param role  用户角色
 */
export function desensitizeObject<T extends Record<string, any>>(
  obj: T,
  role?: UserRole | string
): T {
  if (!obj || typeof obj !== 'object') return obj

  const result = { ...obj }
  for (const key of Object.keys(result)) {
    const value = result[key]
    if (typeof value === 'string' || typeof value === 'number') {
      const desensitized = autoDesensitize(value, key, role)
      if (desensitized !== String(value)) {
        ;(result as any)[key] = desensitized
      }
    }
  }
  return result
}

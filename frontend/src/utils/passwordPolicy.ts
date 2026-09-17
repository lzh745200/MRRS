/**
 * 用户密码策略 —— 前端单一事实源。
 *
 * 与后端 app/core/security.PasswordPolicy 严格对齐：
 *   >=12 位 + 大写 + 小写 + 数字 + 特殊字符（白名单内）+ 不得包含用户名。
 *
 * 背景（2026-09-14）：该策略此前在前端有 3 份独立实现（Register.vue /
 * ChangePassword.vue / UserManagement.vue），且特殊字符白名单与后端不一致
 * —— Register 曾接受 ~ \` ' " \ / 等**后端白名单之外**的字符，
 * 导致「前端放行、后端 400」。本模块为唯一实现，任何调用方不得再自行书写规则。
 */

/** 密码最短长度（对齐 PasswordPolicy.MIN_LENGTH） */
export const PASSWORD_MIN_LENGTH = 12

/** 界面允许的密码最长长度（后端未设上限，此处仅作输入约束） */
export const PASSWORD_MAX_LENGTH = 50

/** 特殊字符白名单（与 PasswordPolicy.SPECIAL_WHITELIST 逐字符一致） */
export const PASSWORD_SPECIAL_CHARS = '!@#$%^&*()-_=+[]{}|;:,.<>?'

export const PASSWORD_UPPER_RE = /[A-Z]/
export const PASSWORD_LOWER_RE = /[a-z]/
export const PASSWORD_DIGIT_RE = /\d/
export const PASSWORD_SPECIAL_RE = /[!@#$%^&*()\-_=+[\]{}|;:,.<>?]/

/** 逐项检查结果 */
export interface PasswordCheck {
  /** 长度达标 */
  length: boolean
  uppercase: boolean
  lowercase: boolean
  digit: boolean
  special: boolean
  /** 通过项数（0~5，含长度项） */
  passed: number
  /** 是否完全满足策略（5 项全过） */
  valid: boolean
}

/** 按后端同一口径逐项检查密码。 */
export function checkPassword(value: string): PasswordCheck {
  const v = value ?? ''
  const result: PasswordCheck = {
    length: v.length >= PASSWORD_MIN_LENGTH,
    uppercase: PASSWORD_UPPER_RE.test(v),
    lowercase: PASSWORD_LOWER_RE.test(v),
    digit: PASSWORD_DIGIT_RE.test(v),
    special: PASSWORD_SPECIAL_RE.test(v),
    passed: 0,
    valid: false,
  }
  result.passed = [
    result.length,
    result.uppercase,
    result.lowercase,
    result.digit,
    result.special,
  ].filter(Boolean).length
  result.valid = result.passed === 5
  return result
}

/** 返回未满足项的中文提示列表（顺序固定，与注册页历史措辞一致）。 */
export function passwordProblems(value: string): string[] {
  const c = checkPassword(value)
  const problems: string[] = []
  if (!c.length) problems.push('至少12个字符')
  if (!c.uppercase) problems.push('包含大写字母')
  if (!c.lowercase) problems.push('包含小写字母')
  if (!c.digit) problems.push('包含数字')
  if (!c.special) problems.push('包含特殊字符')
  return problems
}

/** 是否满足完整密码策略（含用户名子串约束）。 */
export function passwordMeetsPolicy(value: string, username?: string): boolean {
  const c = checkPassword(value)
  if (!c.valid) return false
  const uname = (username ?? '').trim().toLowerCase()
  if (uname && value.toLowerCase().includes(uname)) return false
  return true
}

/**
 * Element Plus 表单校验器工厂。
 *
 * @param getUsername 可选：返回当前用户名，用于「密码不得包含用户名」校验
 */
export function passwordValidator(
  getUsername?: () => string | undefined
): (_rule: unknown, value: string, callback: (error?: Error) => void) => void {
  return (_rule, value, callback) => {
    if (!value) {
      callback(new Error('请输入密码'))
      return
    }
    const problems = passwordProblems(value)
    if (problems.length > 0) {
      callback(new Error('密码需要：' + problems.join('、')))
      return
    }
    const uname = (getUsername?.() ?? '').trim().toLowerCase()
    if (uname && value.toLowerCase().includes(uname)) {
      callback(new Error('密码不能包含用户名'))
      return
    }
    callback()
  }
}

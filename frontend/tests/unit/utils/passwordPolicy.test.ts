/**
 * app 前端密码策略单一事实源测试（2026-09-14）。
 *
 * 背景：策略此前在 Register / ChangePassword / UserManagement 三处各自实现，
 * 且 Register 的特殊字符白名单比后端更宽 → 「前端放行、后端 400」。
 * 本文件锁定共享模块的全部口径与分支。
 */
import { describe, it, expect, vi } from 'vitest'
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  PASSWORD_SPECIAL_CHARS,
  checkPassword,
  passwordMeetsPolicy,
  passwordProblems,
  passwordValidator,
} from '@/utils/passwordPolicy'

const VALID = 'Abcdefgh1234!' // 12 位 + 大写 + 小写 + 数字 + 白名单特殊字符

describe('passwordPolicy 常量（与后端 PasswordPolicy 对齐）', () => {
  it('长度与特殊字符白名单', () => {
    expect(PASSWORD_MIN_LENGTH).toBe(12)
    expect(PASSWORD_MAX_LENGTH).toBe(50)
    expect(PASSWORD_SPECIAL_CHARS).toBe('!@#$%^&*()-_=+[]{}|;:,.<>?')
  })
})

describe('checkPassword', () => {
  it('完全合规 → valid + passed=5', () => {
    const c = checkPassword(VALID)
    expect(c).toMatchObject({ length: true, uppercase: true, lowercase: true, digit: true, special: true, passed: 5, valid: true })
  })

  it('逐项缺失判定（passed 含长度项）', () => {
    expect(checkPassword('abcdefghijkl').passed).toBe(2) // 长度 + 小写
    expect(checkPassword('ABCDEFGHIJKL').passed).toBe(2) // 长度 + 大写
    expect(checkPassword('123456789012').passed).toBe(2) // 长度 + 数字
    expect(checkPassword('!!!!!!!').passed).toBe(1) // 仅特殊（长度不足）
    const short = checkPassword('Abcdefgh123') // 11 位
    expect(short.length).toBe(false)
    expect(short.passed).toBe(3) // 大写 + 小写 + 数字
  })

  it('空值/未定义按空串处理（防御分支）', () => {
    expect(checkPassword(null as unknown as string).passed).toBe(0)
    expect(checkPassword(undefined as unknown as string).valid).toBe(false)
  })

  it('后端白名单之外的字符不算特殊字符', () => {
    // ~ 与空格不在 PasswordPolicy.SPECIAL_WHITELIST 内（Register 旧实现曾误放行 ~）
    expect(checkPassword('Abcdefgh123~').special).toBe(false)
    expect(checkPassword('Abcdefgh12 3').special).toBe(false)
  })
})

describe('passwordProblems', () => {
  it('空密码列出全部 5 项', () => {
    expect(passwordProblems('')).toEqual([
      '至少12个字符',
      '包含大写字母',
      '包含小写字母',
      '包含数字',
      '包含特殊字符',
    ])
  })

  it('合规密码无问题项', () => {
    expect(passwordProblems(VALID)).toEqual([])
  })

  it('仅缺特殊字符', () => {
    expect(passwordProblems('Abcdefgh1234')).toEqual(['包含特殊字符'])
  })
})

describe('passwordMeetsPolicy', () => {
  it('合规且未提供用户名 → true', () => {
    expect(passwordMeetsPolicy(VALID)).toBe(true)
  })

  it('密码包含用户名 → false（大小写不敏感）', () => {
    expect(passwordMeetsPolicy('AbcAdmin1234!', 'admin')).toBe(false)
    expect(passwordMeetsPolicy('AbcAdmin1234!', 'ADMIN')).toBe(false)
  })

  it('用户名为空白串 → 忽略该约束', () => {
    expect(passwordMeetsPolicy(VALID, '   ')).toBe(true)
  })

  it('不满足字符策略 → false', () => {
    expect(passwordMeetsPolicy('abcdefgh1234', 'zzz')).toBe(false)
  })
})

describe('passwordValidator', () => {
  const run = (validator: ReturnType<typeof passwordValidator>, value: string) =>
    new Promise<Error | undefined>((resolve) => {
      validator({}, value, (err?: Error) => resolve(err))
    })

  it('空值 → 请输入密码', async () => {
    expect((await run(passwordValidator(), ''))?.message).toBe('请输入密码')
  })

  it('缺项 → 一次性列出（与注册页同源措辞）', async () => {
    expect((await run(passwordValidator(), 'abc'))?.message).toBe(
      '密码需要：至少12个字符、包含大写字母、包含数字、包含特殊字符'
    )
  })

  it('合规 → 无错误', async () => {
    expect(await run(passwordValidator(), VALID)).toBeUndefined()
  })

  it('含用户名 → 密码不能包含用户名', async () => {
    expect((await run(passwordValidator(() => 'Admin'), 'AbcAdmin1234!'))?.message).toBe(
      '密码不能包含用户名'
    )
  })

  it('getUsername 返回空/未定义 → 跳过用户名约束', async () => {
    expect(await run(passwordValidator(() => undefined), VALID)).toBeUndefined()
    expect(await run(passwordValidator(() => ''), VALID)).toBeUndefined()
  })

  it('validator 以回调形式被调用（Element Plus 契约）', () => {
    const cb = vi.fn()
    passwordValidator()({}, VALID, cb)
    expect(cb).toHaveBeenCalledWith()
  })
})

# 005 双因素认证的会话强度加固（R19 探针发现，待排期）

- 状态: open（安全加固，需产品确认后再动 API 契约）
- 严重度: 中（不是漏洞，是"敏感操作缺少再认证"的纵深防御缺口）
- 波次: w14-deep-probe（2026-09-06 R19 探针附带发现）
- 关联: R19 已修复的两处高危缺陷（中间态令牌越权、恢复码可复用）见
  `001-r1-r2-probe-summary.md` §R19；本票记录**未修复**的观察项。

## 背景

R19 对 2FA 全链路做了真实 HTTP 探针。修复两处高危缺陷后链路 24/24 全绿，
但过程中确认了三个"能工作、但强度不足"的点。它们都不是"功能不完整"，
而是**敏感操作缺少再认证**（re-authentication）这一纵深防御层：

## 1. `/two-factor/enable` 与 `/disable` 不要求输入当前密码

- 现状：两个端点只要求一个有效的 access token（`get_current_active_user`）。
  前端 `TwoFactorSettings.vue` 的禁用流程只有 `ElMessageBox.confirm` 二次确认，
  不收集密码；后端也不校验。
- 影响：任何持有有效会话的场景（共用终端未锁屏、XSS 后窃取 token、
  被盗笔记本）都可以：
  ① 关掉受害者已启用的 2FA（`POST /two-factor/disable`），或
  ② 把 2FA 重新登记到攻击者自己的验证器上（`enable` → `verify`），
     从此以受害者身份通过后续所有 2FA 校验。
  即"会话已泄露"的后果被放大为"认证因子被永久替换"。
- 建议：`disable` 必须带 `password`（并校验），`enable` 在**已启用**状态下
  重新登记时也必须带 `password`；首次启用可豁免。参照已有的强校验先例
  （回收站彻底删除 `confirm_password`、备份恢复 `password`）。
- 代价与风险：改动 API 契约 + `TwoFactorSettings.vue` 弹窗 + 前后端测试 +
  e2e 用例。属**契约变更**，需与前端 e2e 套件（150 例）协调，故不在 R19 夹带。

## 2. 2FA 登录挑战不写 `login_attempts` 失败明细之外的上下文

- 现状：失败已记审计（`AuditLogger.log_login(failure_reason="2FA验证码错误")`），
  合规可追溯；但没有"同一账号连续 2FA 失败"的升级动作，只有共享的
  登录限流（`login:{ip}` 5 次/60 秒）。
- 影响：密码已泄露的攻击者可以在分布式/多 IP 场景下持续爆破 6 位 TOTP
  （TOTP 本身有 30 秒窗口 + ±1 窗口容忍，有效空间有限）。
- 建议：把 2FA 失败计入 `users.failed_login_count` 并复用既有的账户锁定
  （`locked_until`）逻辑——密码失败已走该路径，2FA 失败未走。
- 代价与风险：低（后端单点改动 + 测试）；但会改变"2FA 失败也锁定账号"的
  运维语义（离线单机场景下管理员可能被自己的验证器故障锁在门外），
  需产品确认锁定阈值与解锁通道（已有 `/machine-code/recover-admin-factory-password`
  与管理员重置两条兜底）。

## 3. 恢复码余量不对外可见

- 现状：`GET /two-factor/status` 只返回 `{enabled}`；用户无法知道还剩几个
  恢复码（R19 修复后才会真正递减）。
- 影响：无安全影响，属可用性——恢复码用尽前用户无感知，
  真到设备丢失时才发现无码可用。
- 建议：`status` 增加 `backup_codes_remaining`（仅返回计数，不返回码本身），
  设置页在余量 ≤2 时给出提示。

## 不在本票范围

- TOTP 算法/密钥存储：`secret_key` 已 `encrypt_field` 加密存储、
  备份码 8 位随机数字，未发现问题（探针已确认）。
- 恢复码消费：R19 已修复（`MutableList.as_mutable(JSON)`），本票不重复。

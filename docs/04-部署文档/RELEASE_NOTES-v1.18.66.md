# v1.18.66 发布说明

发布日期：2026-11-28

主题：账号开通包开箱即用——默认启用、自动生成签发密钥、导入端指纹确认信任。

## 本版重点

- **不再需要环境变量**：`ACCOUNT_PACKAGE_ENABLED` 默认 `true`；第一次打开账号开通包页面或第一次签发时，
  后端自动生成 Ed25519 签发密钥并持久化到本机 `runtime_secrets.json`，公钥/指纹由私钥派生。
  以前必须手工配 `ACCOUNT_PACKAGE_SIGNING_KEY` 才能签发的门槛已移除。
- **包内嵌签发公钥**：签名头新增 `signer_public_key` 并参与签名。目标机即使没有预置公钥，
  也能验证“包未被篡改”；但“这个签发机是否可信”仍由人工核对指纹决定，不会因为包自带公钥就自动信任。
- **指纹确认**：导入预览展示签发机公钥与指纹（SHA-256 前 16 字节，按 4 位分组）。未信任时，
  确认导入必须勾选“我已通过独立渠道核对上述指纹”；确认成功后该公钥写入本机信任列表，
  后续同一签发机导入不再逐次要求核对。未核对指纹直接确认会被 403 拒绝（`AP_SIGNING_UNTRUSTED`）。
- **密钥与信任管理**：新增 `GET /account-packages/signing-keys`、
  `POST /account-packages/signing-keys/trusted`、`DELETE /account-packages/signing-keys/trusted/{fingerprint}`；
  系统页面新增“本机签发密钥 / 信任签发机”面板，支持复制公钥、指纹和增删信任。
- **预登录导入页**：全新机器在登录前导入账号包时同样展示指纹并要求勾选核对；
  出厂管理员接管流程不变。

## 数据与兼容

- 不新增业务表、不改变账号包加密算法与 KDF 参数。
- **旧包兼容**：v1.18.65 及更早生成的包没有内嵌公钥，导入端仍需预置 `ACCOUNT_PACKAGE_PUBKEY`
  或已信任的签发机公钥；否则继续 fail-closed（提示“无法确认账号包来源”）。
- **新包在旧版本导入**：旧版本不认识 `signer_public_key`，但签名校验仍按原 header 进行；
  旧版本必须预置公钥。跨版本混用时建议先升级目标机。
- 默认启用改变了默认安全姿态：功能可用性与“开箱即用”优先；包仍强制签名，导入端仍强制来源核对。
  如需回到旧行为，可显式设置 `ACCOUNT_PACKAGE_ENABLED=false`。
- 本机签发私钥只保存在本机 `runtime_secrets.json`（打包态默认在应用数据目录），
  不上传到账号包，也不写入日志/审计。

## 验证

- 后端：`16,168` 用例收集；账号包/自检相关 **89** 例、相邻账号包链路 **34** 例通过；
  `flake8 app/ --max-line-length=120 --max-complexity=16` 无输出。
- 前端：账号包与登录前导入相关 **227** 例（9 文件）通过；`vue-tsc --noEmit`、ESLint 通过。
- 门禁：`check_stack_alignment.py`、`check_doc_numbers.py --full`、`check_changelog.py`
  与 `sync-version.js --check` 通过。

## 已知边界

- 指纹核对是“带外信任”流程：如果操作者不核对就勾选，仍可能信任伪造签发机；
  演练/现场必须把指纹与签发机屏幕或纸质记录逐位比对。
- 撤销信任只影响本机后续导入判断，不会追溯已导入的账号或已落库的包回执。
- 私钥轮换尚未提供 UI；如需更换签发机，删除本机信任并重新核对新指纹即可。
- 安装版为 PyInstaller onedir，代码不能热替换；本版修复需通过新安装包生效。

## 安装包

- Windows x64：`MRRS-Setup-1.18.66-x64.exe`（以 GitHub Release 资产为准）
- 麒麟 ARM64：`MRRS-Setup-1.18.66-arm64.deb`、`assistance-management-system_1.18.66_arm64.deb`

升级前请备份 `backend/data` 与上传目录。全新机器可直接在登录前通过账号开通包导入账号，
无需再配置签名环境变量；跨机导入时请按页面提示核对签发机指纹。

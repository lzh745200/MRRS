# ADR-0005: PII 字段透明加密（确定性 AES-SIV）

- 状态：Accepted（2026-08-30，W5-T7 实施）
- 关联工单：`.scratch/w5-perf-consistency/007-pii-encryption.md`

## 背景

身份证号、联系电话等 PII 字段此前明文落库（SQLite 单文件可直读），是军事审计红线。
加密需同时满足：ORM 读写透明、既有等值查询（按手机号/身份证检索）无需改写、
离线单机可自动供给密钥。

## 决策

1. **应用层列加密，不用 SQLCipher 做字段级需求**：`EncryptedText` TypeDecorator
   （`app/models/base.py`）+ `app/core/pii_crypto.py`，覆盖 9 列：
   villagers.id_card / villagers.phone / village_committee_members.phone /
   users.phone / organizations.contact_phone / projects.contact_phone /
   rural_works.contact_phone / rural_tasks.contact_phone / schools.contact_phone。
2. **确定性加密算法 AES-SIV（RFC 5297，cryptography 库 AESSIV）**：
   同明文恒同密文 → `WHERE phone = :v` 经绑定参数加密后直接命中密文，
   等值查询零改写。代价：暴露等值关系（同号可关联），无范围查询需求，可接受。
3. **密文标记前缀 `enc.v1:`**：迁移回填幂等（跳过已加密值）；读取侧对未标记的
   历史明文原样透出（兼容未迁移数据），解密失败记日志并原样返回（不抛异常炸页面）。
4. **密钥供给**（同 `encryption_service._get_cipher` 优先级语义）：
   - 显式配置 `ENCRYPTION_KEY` → SHA-512 派生 512-bit AESSIV 密钥。
     **多机离线同步部署必须配置相同 ENCRYPTION_KEY**，密文才能跨机互导；
   - 否则运行时密钥存储 `PII_AESSIV_KEY`（单机自动生成，跨重启保持）。
5. **SQLCipher 修正（database.py）**：原实现对 `PRAGMA key` 使用绑定参数——
   SQLCipher 不支持，且普通 sqlite3 驱动会**静默忽略** PRAGMA key 造成假加密。
   现行为：`DB_ENCRYPTION_ENABLED` 启用时先探测 `PRAGMA cipher_version`，
   非 SQLCipher 驱动**拒绝启动**（fail-closed）；key 必须为连接首条语句、字面量转义。

## 后果与已知限制

- 存量数据经 `alembic: pii_encrypt_001` 就地回填，可断点重跑。
- `data_sync_service` 裸 SQL 同步 users/organizations/projects/schools 时，
  PII 列以密文形态搬运：同机/同密钥部署无感；**异密钥跨机同步后 PII 列将显示
  密文**（同步管道本身在 W2-T7 重做，届时改为 ORM 写入）。
- 备份包/数据包内含密文：恢复到异密钥机器后 PII 列同样显示密文，属预期。
- 掩码展示不受影响：DataMaskingService 在 ORM 解密后的明文上按格式掩码。

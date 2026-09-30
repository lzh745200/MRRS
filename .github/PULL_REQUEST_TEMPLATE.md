## 变更说明

<!-- 一句话说明这个 PR 做了什么、为什么 -->

关联工单/缺陷：<!-- .scratch/... 工单号 或 缺陷描述 -->

## 变更类型

- [ ] 缺陷修复（bug fix）
- [ ] 新功能（feature）
- [ ] 重构 / 性能（refactor / perf）
- [ ] 文档 / 构建 / CI（docs / build / ci）
- [ ] 安全加固（security）

## 评审清单（P-5，勾选前请确认已实际验证）

### 门禁
- [ ] 后端：`cd backend && .venv/Scripts/python.exe -m pytest tests/ --cov=app -q` 全绿且覆盖率 **100%**（`backend/.coveragerc` fail_under=100）
- [ ] 前端：`cd frontend && npm test -- --run` 全绿；`npx vue-tsc --noEmit`、`npm run lint:check` 零错误
- [ ] `flake8 app/ --max-line-length=120 --max-complexity=16` 零违例
- [ ] 棘轮门禁 NEW=0：check_os_exit / check_unbounded_read / check_upload_endpoints / check_subprocess_encoding / check_dir_replace / check_scheduler_registration（+ 根目录前端侧 6 项）
- [ ] 版本单一来源一致：`node scripts/sync-version.js --check`
- [ ] Schema 变更：已写 Alembic 迁移且 `scripts/check_migrations.py` 单 head

### 安全与数据（本项目铁律，逐条对照）
- [ ] **fail-closed**：新增/修改的权限与输入校验在非法输入时显式 4xx，绝不静默放行或降级
- [ ] **数据范围**：新列表/导出/聚合端点已套 `app.core.data_permission` 或 `services.data_scope_query` 的既有入口（不新造过滤逻辑）；缓存键含调用者身份
- [ ] **错误细节不出站**：响应不包含 `str(e)`、异常类名、SQL 片段、路径等内部信息（只进日志）
- [ ] **上传与解压限长**：`UploadFile` 走 `read_upload_with_limit`/`save_upload_file`；ZIP 先 `ensure_zip_within_limit` 再 `read_zip_member`
- [ ] **PII 列**：未对 `EncryptedText` 列做裸 SQL 写入；脱敏输出未被绕过
- [ ] **软删**：列表默认过滤 `is_active=True`；详情/流转端点同样不可访问已软删记录
- [ ] **状态机**：状态变更只经专用端点，通用更新接口不接受 `status` 直写
- [ ] **审计留痕**：敏感操作（权限、配置、恢复、导出、删除）已写审计/工作日志
- [ ] **事务**：写操作使用 `safe_commit`/`transaction`；异常路径回滚；跨表写入原子（必要时 SAVEPOINT）

### 测试
- [ ] 修复类改动有**能复现原缺陷**的回归测试（去掉修复即失败）
- [ ] 未新增 `skip`/`xfail`；未删除或放宽既有断言（若既有测试固化了错误行为，已在测试内注明原因并改写）
- [ ] 列表端点响应使用 `ok_list()` 信封

## 验证记录

<!-- 贴关键命令与结果（测试数量、覆盖率、门禁输出） -->

```
```

## 风险与回滚

<!-- 行为变更点、对既有数据/部署的影响、回滚方式 -->

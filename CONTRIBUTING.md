# 贡献指南

感谢您对本项目的关注！

## Pull Request 流程

1. **Fork** 项目到您自己的 GitHub 账户
2. **创建分支**: `git checkout -b feature/your-feature-name`
3. **编写代码**: 遵循代码规范，添加必要的测试用例
4. **运行测试**: 后端 `cd backend && python -m pytest tests/ -q -n auto`，前端 `cd frontend && npx vitest run`（提交前建议再跑 `make test-local` 复跑 CI 六道门禁）
5. **提交变更**: `git commit -m "feat: 你的功能描述"`
6. **推送分支**: `git push origin feature/your-feature-name`
7. **创建 PR**: 在 GitHub 上创建 Pull Request

## Commit 规范

使用语义化提交信息：

```
feat:     新功能
fix:      修复 bug
refactor: 重构代码
docs:     文档更新
test:     添加测试
build:    构建系统变更
chore:    杂项（清理、格式化等）
```

## 代码风格

### 后端 (Python)
- 遵循 PEP 8，最大行宽 120 字符
- 使用 `flake8 app/ --max-line-length=120` 检查
- 函数/类/模块必须有 docstring
- 使用 Pydantic 模型进行请求/响应校验
- 所有新功能必须包含单元测试或集成测试

### 前端 (Vue 3 + TypeScript)
- 使用 `<script setup lang="ts">` 语法
- 组件命名使用 PascalCase
- 使用 `vue-tsc --noEmit` 检查类型
- 使用 `eslint src --ext .vue,.ts,.tsx` 检查代码
- 避免在模板中使用复杂表达式

## 测试要求
- 覆盖率门禁基线为 **100%**（后端口径见 `backend/.coveragerc` 的 `fail_under`，前端见 `frontend/vitest.config.ts` 的 `thresholds`）
- 100% 指「**可覆盖集** 100%」：所有未被 `exclude_lines` 排除、未标 `# pragma: no cover` 的可执行行都必须被测试覆盖
- 每一处 `# pragma: no cover` 豁免都必须附带理由（CI 由 `scripts/check_pragma_reasons.py` 校验），不得用豁免掩盖未测代码
- 新增/修改可执行行时必须同时补测试，否则 CI 的 `backend-test` / `frontend-check` 会因覆盖率不足红灯
- **不要**在命令行内联 `--cov-fail-under`（会屏蔽配置文件里的单一事实源口径）
- 集成测试覆盖关键 API 路径

## 问题反馈
- 使用 GitHub Issues 报告 Bug
- 清楚描述问题、复现步骤、预期行为
- 附上相关的日志和截图

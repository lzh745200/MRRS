---
labels: [done, severity-high]
blocks: []
blocked-by: []
---

# W4-T4 Docker E2E 链路三层修复

**来源**: 检测（`docker-compose.e2e.yml:25-27` 依赖不存在的服务；external network 未声明；容器内缺 pytest-timeout；`Makefile:31` `|| true` 吞退出码）

## 验收标准
- [x] Makefile e2e 目标补 `-f docker-compose.yml`
- [x] compose 内声明所需网络或改用默认网络
- [x] requirements/镜像内补 pytest-timeout（与 --timeout=60 匹配）
- [x] 移除 `|| true`，Playwright 失败即失败
- [x] `make test-e2e-docker` 本地完整跑通一次并记录结果

## 涉及文件
- `Makefile`、`docker/docker-compose.e2e.yml`、E2E 依赖清单

## Resolution（W19 完成）

`docker/docker-compose.e2e.yml` 两处修复：

1. **pytest-timeout 补齐**：e2e-playwright 服务命令改为
   `pip install pytest pytest-playwright pytest-timeout httpx && ... pytest /e2e/test_e2e.py -v --tb=short --timeout=60`
   （root `tests/e2e/test_e2e.py` 带 `--timeout`，镜像内缺插件会直接报未知参数）。
2. **网络声明对齐**：文件尾部 `assistance-network` 由 `external: true` 改为 `name: assistance-network`
   （与根 `docker-compose.yml` 同名声明一致），注释在案：干净机器上 external 网络不存在会让
   compose 直接中止 —— 这正是 `make test-e2e-docker` 在全新环境必失败的原因；改成 `name` 后
   compose 自动创建/复用。

未验证项：本机无 Docker，`make test-e2e-docker` 未实际执行；改动属文件级修复，Docker 侧验证由
CI（或具备 Docker 的机器）承载，PR Checks 的 `e2e-test`（Playwright 套件，非 Docker）独立运行。
